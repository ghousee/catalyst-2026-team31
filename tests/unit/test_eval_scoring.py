"""Eval harness: contamination via source system lookup, and empty runs."""
import importlib.util
import pathlib

import pytest

_path = pathlib.Path(__file__).resolve().parents[2] / "eval" / "run_eval.py"
_spec = importlib.util.spec_from_file_location("run_eval", _path)
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

SYSTEMS = {"ravi:h12": "sys:P-201", "doc:P-201-manual:4.2": "sys:P-201",
           "doc:P-305-manual:3.1": "sys:P-305", "priya:h1": "sys:P-305"}
TRAP = {"id": "t01", "category": "context_trap", "q": "...", "system": "sys:P-305",
        "version": "ver:P-305:v1", "gold_nodes": ["doc:P-305-manual:3.1"], "expect": "answer",
        "expert": None}


def answer(*source_ids):
    return {"type": "answer", "context": {"system": "sys:P-305", "version": "ver:P-305:v1"},
            "claims": [{"text": "x", "source_id": s} for s in source_ids]}


def test_trap_citing_other_system_is_contaminated():
    resp = answer("doc:P-305-manual:3.1", "ravi:h12")  # gold hit + a P-201 leak
    assert run_eval.score(TRAP, resp, SYSTEMS)["contaminated"] is True


def test_trap_citing_only_own_system_is_clean():
    resp = answer("doc:P-305-manual:3.1", "priya:h1")
    assert run_eval.score(TRAP, resp, SYSTEMS)["contaminated"] is False


def test_unknown_source_counts_as_contaminated():
    assert run_eval.score(TRAP, answer("doc:made-up:9"), SYSTEMS)["contaminated"] is True


def test_refer_and_clarify_are_not_scored():
    assert run_eval.score(TRAP, {"type": "refer", "experts": []}, SYSTEMS)["contaminated"] is None
    clarify_item = {**TRAP, "system": None, "version": None, "expect": "clarify"}
    assert run_eval.score(clarify_item, answer("ravi:h12"), SYSTEMS)["contaminated"] is None


def test_db_unavailable_leaves_contamination_unscored():
    assert run_eval.score(TRAP, answer("ravi:h12"), None)["contaminated"] is None


def test_rate_with_no_items():
    assert run_eval.rate([], "behaviour_ok") == "n/a (0 items)"


def test_empty_golden_file(tmp_path, monkeypatch, capsys):
    g = tmp_path / "golden.jsonl"
    g.write_text("\n\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--golden", str(g)])
    run_eval.main()
    assert "nothing to evaluate" in capsys.readouterr().out


def test_missing_golden_file(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--golden", str(tmp_path / "nope.jsonl")])
    with pytest.raises(SystemExit):
        run_eval.main()
