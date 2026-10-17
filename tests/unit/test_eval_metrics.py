"""Eval harness: Wilson CI, must_include/must_not/forbidden/both-sides scoring, golden-set sanity."""
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)


def test_wilson_known_values():
    lo, hi = run_eval.wilson(8, 10)
    assert lo == pytest.approx(0.490, abs=0.005) and hi == pytest.approx(0.943, abs=0.005)
    lo, hi = run_eval.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.278, abs=0.005)
    lo, hi = run_eval.wilson(10, 10)
    assert hi == 1.0 and lo == pytest.approx(0.722, abs=0.005)


def test_wilson_empty():
    assert run_eval.wilson(0, 0) == (None, None)


def test_rate_reports_ci_and_n():
    rows = [{"x": True}] * 9 + [{"x": False}]
    out = run_eval.rate(rows, "x")
    assert out.startswith("9/10 (90%)") and "95% CI" in out and "n=10" in out


def test_includes_all_with_any_of_groups_case_insensitive():
    assert run_eval.includes_all([["status audittrail"], ["PINNED", "pin"]], "Run TMFCOM STATUS   AUDITTRAIL; file is pinned")
    assert not run_eval.includes_all([["status audittrail"], ["overflow"]], "run status audittrail")
    assert run_eval.includes_all([], "anything")


def test_includes_any_and_forbidden_globs():
    assert run_eval.includes_any(["abort it early"], "You should ABORT it early")
    assert not run_eval.includes_any(["abort it early"], "wait")
    assert run_eval.forbidden_hits(["maria:*", "raj:h6"], ["doc:x", "maria:h7", "raj:h6", "raj:h8"]) == ["maria:h7", "raj:h6"]
    assert run_eval.forbidden_hits([], ["maria:h7"]) == []


def test_both_sides():
    groups = [["maria:h12"], ["raj:h6"]]
    assert run_eval.both_sides_ok(groups, ["maria:h12", "raj:h6", "doc:a"])
    assert not run_eval.both_sides_ok(groups, ["maria:h12"])
    assert run_eval.both_sides_ok([["maria:h11"], ["doc:a", "doc:b"]], ["doc:b", "maria:h11"])


ITEM = {"id": "n1", "category": "negation", "q": "?", "node": "node:PROD", "system": "sub:TMF", "version": "rvu:L",
        "gold_nodes": ["maria:h11"], "expect": "answer", "expert": "maria",
        "must_include": [["pinning"], ["do not", "don't"]], "must_not_include": ["start with filespervolume"],
        "forbidden_sources": ["raj:h8"], "both_sides": [["maria:h11"], ["doc:m"]]}


def resp(texts_sources, site="node:PROD", experts=()):
    return {"type": "answer", "context": {"system": "sub:TMF", "version": "rvu:L", "site": site},
            "claims": [{"text": t, "source_id": s} for t, s in texts_sources],
            "experts": [{"id": e} for e in experts]}


def test_score_all_new_metrics_pass():
    r = resp([("Do not bump it; find the pinning transaction.", "maria:h11"), ("Manual says otherwise", "doc:m")])
    row = run_eval.score(ITEM, r, {"maria:h11": "sub:TMF", "doc:m": "sub:TMF"})
    assert row["must_include_ok"] and row["must_not_ok"] and row["forbidden_clean"]
    assert row["both_sides_ok"] and row["expert_ok"] and row["context_ok"]


def test_score_new_metrics_fail():
    r = resp([("Start with FILESPERVOLUME.", "raj:h8")], site="node:DR")
    row = run_eval.score(ITEM, r, {"raj:h8": "sub:TMF"})
    assert row["must_include_ok"] is False and row["must_not_ok"] is False
    assert row["forbidden_clean"] is False and row["both_sides_ok"] is False
    assert row["context_ok"] is False  # session node not honoured


def test_score_non_answer_items_skip_text_metrics():
    refer_item = {**ITEM, "expect": "refer", "must_include": [], "both_sides": []}
    row = run_eval.score(refer_item, {"type": "refer", "experts": [{"id": "maria"}]}, {})
    assert row["must_include_ok"] is None and row["forbidden_clean"] is None and row["both_sides_ok"] is None
    assert row["correct_refusal"] and row["expert_ok"]
    # an answer item that got a refusal fails must_include
    row = run_eval.score(ITEM, {"type": "refer", "experts": []}, {})
    assert row["must_include_ok"] is False


def test_expert_ok_via_cited_owner_prefix():
    r = resp([("x", "maria:h3")])
    assert run_eval.score({**ITEM, "must_include": []}, r, {"maria:h3": "sub:TMF"})["expert_ok"]


def test_unreachable_api_exits_cleanly(monkeypatch):
    g = ROOT / "eval" / "golden.jsonl"
    monkeypatch.setattr(run_eval, "api_up", lambda: False)
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--golden", str(g)])
    with pytest.raises(SystemExit) as e:
        run_eval.main()
    assert "not reachable" in str(e.value)


# ---- golden set sanity (no DB / API) ----
GOLDEN = [json.loads(l) for l in (ROOT / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
CATS = {"doc", "veteran", "context_trap", "conflict", "negation", "must_refer", "must_clarify"}


def test_golden_schema():
    assert len({g["id"] for g in GOLDEN}) == len(GOLDEN)
    for g in GOLDEN:
        assert g["category"] in CATS and g["expect"] in {"answer", "refer", "clarify"}
        assert g["node"] in {"node:PROD", "node:DR"}
        assert isinstance(g["must_include"], list) and isinstance(g["must_not_include"], list)
        assert all(isinstance(x, str) and x == x.lower() for x in g["must_not_include"])
        assert all(isinstance(x, str) and x == x.lower() for grp in g["must_include"] for x in ([grp] if isinstance(grp, str) else grp))
        if g["expect"] == "answer":
            assert g["gold_nodes"], g["id"]
        if g["category"] == "conflict":
            assert len(g["both_sides"]) >= 2


def test_golden_node_scoping_is_consistent():
    prod_only = {"maria:h7", "maria:h11", "maria:h12", "maria:h3", "raj:h3", "raj:h4", "raj:h6", "lena:h4"}
    for g in GOLDEN:
        if g["node"] == "node:DR" and g["expect"] != "clarify":
            assert prod_only <= set(g["forbidden_sources"]) or g["id"] == "t09" and "maria:h7" in g["forbidden_sources"], g["id"]
            assert not prod_only & set(g["gold_nodes"]), g["id"]
        if g["node"] == "node:PROD" and g["forbidden_sources"]:
            assert "raj:h8" in g["forbidden_sources"]
