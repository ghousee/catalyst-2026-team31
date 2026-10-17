"""answer() assembly with every stage faked (no Docker/Ollama/MiniCheck): lanes, dropped claims, refer/clarify shapes,
node-mismatch -> clarify."""
import pytest

from backend.pipeline import answer as A

SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "t"}
HEUR = {"id": "maria:h7", "owner_name": "Maria Rossi", "text": "veteran note text"}
DOC = {"id": "doc:TMF-Reference:x", "text": "doc text", "edition": "ed"}
EXPERT = {"id": "raj", "name": "Raj", "reason": "r", "active": True}


class Cur:
    def fetchall(self):
        return []

    def fetchone(self):
        return (42,)


class Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        return Cur()

    def commit(self):
        pass


@pytest.fixture
def fake(monkeypatch):
    state = {"resolved": {"subsystem": "sub:TMF", "nodes_mentioned": [], "entities": [
        {"id": "evt:TMF-185", "kind": "event", "name": "x", "matched": "x"}]},
        "gate": True, "claims": [], "scores": {}}
    monkeypatch.setattr(A, "connect", lambda: Conn())
    monkeypatch.setattr(A, "resolve", lambda conn, q, ctx: state["resolved"])
    monkeypatch.setattr(A, "lookup", lambda conn, ids, ctx: {
        "doc_chunks": [DOC], "heuristics": [HEUR], "experts": [EXPERT], "path": [], "commands": []})
    monkeypatch.setattr(A, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(A, "hybrid_search", lambda *a, **k: [])
    monkeypatch.setattr(A.gate, "sufficient", lambda q, c: (state["gate"], {"content": '{"reason": "why"}'}))
    monkeypatch.setattr(A.generate, "generate", lambda q, c, **kw: (state["claims"], {}))
    monkeypatch.setattr(A.verify, "support_probs", lambda pairs: [state["scores"][claim] for _, claim in pairs])
    monkeypatch.setattr(A, "source_card", lambda conn, i: {"id": i, "kind": "doc" if i.startswith("doc:") else "heuristic"})
    monkeypatch.setattr(A, "_rows", lambda conn, sql, params=(): [{"id": "node:DR", "name": "DR"}])
    return state


def test_answer_lanes_and_dropped(fake):
    fake["claims"] = [{"claim": "a", "source_id": "maria:h7"}, {"claim": "b", "source_id": "doc:TMF-Reference:x"},
                      {"claim": "weak", "source_id": "doc:TMF-Reference:x"}, {"claim": "ghost", "source_id": "nope"}]
    fake["scores"] = {"a": 0.9, "b": 0.8, "weak": 0.1}
    r = A.answer("why is the audit trail filling?", SESSION)
    assert r["type"] == "answer" and r["answer_log_id"] == 42
    assert [(c["lane"], c["source_id"], c["verified"]) for c in r["claims"]] == [
        ("veteran", "maria:h7", True), ("doc", "doc:TMF-Reference:x", True)]
    assert r["dropped_claims"] == 2  # one unsupported, one with an unknown source
    assert r["context"]["display"] == r"\PROD · L-series · TMF" and r["context"]["site"] == "node:PROD"
    assert {s["id"] for s in r["sources"]} == {"maria:h7", "doc:TMF-Reference:x"}
    q = r["quality"]
    assert (q["claims_total"], q["claims_verified"], q["dropped"]) == (4, 2, 2)
    assert q["sources_by_lane"] == {"doc": 1, "veteran": 1} and q["gate"]["sufficient"]


def test_insufficient_refers_with_experts(fake):
    # a subsystem-only match (confirmed by the user's override) still goes through the LLM gate
    fake["resolved"] = {**fake["resolved"], "entities": [{"id": "sub:TMF", "kind": "system", "name": "TMF", "matched": "TMF"}]}
    fake["gate"] = False
    r = A.answer("q", SESSION, {"system": "sub:TMF"})
    assert r["type"] == "refer" and r["experts"] == [EXPERT] and r["context"]["system"] == "sub:TMF"
    assert r["quality"]["gate"] == {"sufficient": False, "reason": "why"}


def test_all_claims_unsupported_refers(fake):
    fake["claims"] = [{"claim": "weak", "source_id": "maria:h7"}]
    fake["scores"] = {"weak": 0.0}
    assert A.answer("q", SESSION)["type"] == "refer"


def test_node_mismatch_clarifies(fake):
    fake["resolved"] = {**fake["resolved"], "nodes_mentioned": ["node:DR"]}
    r = A.answer("why is the audit trail filling on DR?", SESSION)
    assert r["type"] == "clarify" and r["options"] == [{"label": r"\DR", "value": {"site": "node:DR"}}]
    assert "context" not in r
    # the UI's override wins: no second clarify, and the context is the overridden node
    fake["gate"] = False
    r = A.answer("q", SESSION, {"site": "node:DR"})
    assert r["type"] == "refer" and r["context"]["site"] == "node:DR"


def test_unresolved_subsystem_clarifies(fake):
    fake["resolved"] = {**fake["resolved"], "subsystem": None}
    r = A.answer("the disk is acting up", SESSION)
    assert r["type"] == "clarify" and "system" in r["options"][0]["value"]


def test_specific_graph_match_skips_gate(fake):
    fake["gate"] = False  # would refer if the gate ran
    fake["claims"] = [{"claim": "a", "source_id": "maria:h7"}]
    fake["scores"] = {"a": 0.9}
    r = A.answer("why is the audit trail filling?", SESSION)
    assert r["type"] == "answer" and r["quality"]["gate"]["reason"].startswith("graph match")


def test_vague_subsystem_only_question_clarifies(fake):
    fake["resolved"] = {**fake["resolved"], "subsystem": "sub:SCF-STORAGE",
                        "entities": [{"id": "sub:SCF-STORAGE", "kind": "system", "name": "SCF Storage", "matched": "disk"}]}
    r = A.answer("the disk is acting up", SESSION)
    assert r["type"] == "clarify" and "more specific" in r["question"]


def test_misattributed_claims_are_dropped(fake):
    fake["claims"] = [{"claim": "The manual recommends raising FILESPERVOLUME first.", "source_id": "maria:h7"},
                      {"claim": "Maria says check the batch.", "source_id": "doc:TMF-Reference:x"},
                      {"claim": "Experienced operators check STATUS TRANSACTION first.", "source_id": "maria:h7"}]
    fake["scores"] = {c["claim"]: 0.97 for c in fake["claims"]}
    r = A.answer("why is the audit trail filling?", SESSION)
    assert [c["text"] for c in r["claims"]] == ["Experienced operators check STATUS TRANSACTION first."]
    assert r["dropped_claims"] == 2


def test_misattributed_rule():
    assert A.misattributed("The manual says X", "veteran")
    assert A.misattributed("According to the documentation, raise FILESPERVOLUME", "veteran")
    assert not A.misattributed("Don't rely on the manual's FILESPERVOLUME advice before clearing the pin", "veteran")
    assert not A.misattributed("Check STATUS TRANSACTION before adding overflow", "veteran")
    assert A.misattributed("Raj recommends THAW", "doc", ["Raj Patel"])
    assert not A.misattributed("THAW SERVER resumes the class", "doc", ["Raj Patel"])


def test_clean_restores_node_backslash():
    assert A._clean("♍PROD and УDR") == "\PROD and \DR"
