"""answer() assembly with every stage faked (no Docker/Ollama/MiniCheck): lanes, dropped claims, refer/clarify shapes,
node-mismatch -> clarify."""
import pytest

from backend.pipeline import answer as A

SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "t"}
HEUR = {"id": "maria:h7", "owner_name": "Maria Rossi", "text": "veteran note text", "call": "Check the pin first.",
        "relation": "extends:doc:x", "disagrees_with": []}
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
    monkeypatch.setattr(A, "note_search", lambda conn, qvec, ctx, k=3: state.get("found", [{**HEUR, "score": 0.9}]))
    monkeypatch.setattr(A, "fetch_notes", lambda conn, ids, ctx: {i: state["extra"][i] for i in ids if i in state.get("extra", {})})
    monkeypatch.setattr(A, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(A, "hybrid_search", lambda *a, **k: [])
    monkeypatch.setattr(A.gate, "sufficient", lambda q, c: (state["gate"], {"content": '{"reason": "why"}'}))
    monkeypatch.setattr(A.generate, "generate", lambda q, c, **kw: (state["claims"], {}))
    monkeypatch.setattr(A.verify, "support_probs", lambda pairs: [state["scores"][claim] for _, claim in pairs])
    monkeypatch.setattr(A.converse, "write_reply", lambda *a, **k: state.get("reply", (None, {})))
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
    assert r["claims"][0]["text"] == "Check the pin first." and r["claims"][0]["verbatim"] and r["claims"][0]["score"] == 1.0
    assert r["dropped_claims"] == 2  # one unsupported, one with an unknown source
    assert r["context"]["display"] == r"\PROD · L-series · TMF" and r["context"]["site"] == "node:PROD"
    assert {s["id"] for s in r["sources"]} == {"maria:h7", "doc:TMF-Reference:x"}
    q = r["quality"]
    assert (q["claims_total"], q["claims_verified"], q["dropped"]) == (4, 2, 2)
    assert q["sources_by_lane"] == {"doc": 1, "veteran": 1} and q["gate"]["sufficient"]


def test_no_surviving_claim_refers_with_experts_and_next_steps(fake):
    # a subsystem the user picked skips the gate; with nothing verified the refer still helps
    fake["claims"] = []
    r = A.answer("q", SESSION, {"system": "sub:TMF"})
    assert r["type"] == "refer" and r["experts"] == [EXPERT] and r["context"]["system"] == "sub:TMF"
    assert r["quality"]["gate"]["sufficient"] and 1 <= len(r["next_steps"]) <= 3
    assert all("read-only" in x for x in r["next_steps"]) and "Raj" in r["reply"] and r["entities"] == ["evt:TMF-185"]


def test_all_claims_unsupported_refers(fake):
    fake["claims"] = [{"claim": "weak", "source_id": "doc:TMF-Reference:x"}]
    fake["scores"] = {"weak": 0.0}
    assert A.answer("q", SESSION)["type"] == "refer"


def test_node_mismatch_clarifies(fake):
    fake["resolved"] = {**fake["resolved"], "nodes_mentioned": ["node:DR"]}
    r = A.answer("why is the audit trail filling on DR?", SESSION)
    assert r["type"] == "clarify" and r["options"] == [{"label": r"\DR", "value": {"site": "node:DR"}}]
    assert "context" not in r
    # the UI's override wins: no second clarify, and the context is the overridden node
    fake["claims"] = []
    r = A.answer("q", SESSION, {"site": "node:DR"})
    assert r["type"] == "refer" and r["context"]["site"] == "node:DR"


def test_unresolved_subsystem_clarifies(fake):
    fake["resolved"] = {**fake["resolved"], "subsystem": None}
    r = A.answer("the disk is acting up", SESSION)
    assert r["type"] == "clarify" and "system" in r["options"][0]["value"]


def test_graph_subsystem_skips_gate(fake):
    fake["gate"] = False  # would refer if the gate ran
    fake["claims"] = [{"claim": "a", "source_id": "maria:h7"}]
    fake["scores"] = {"a": 0.9}
    r = A.answer("why is the audit trail filling?", SESSION)
    assert r["type"] == "answer" and r["quality"]["gate"]["reason"].startswith("subsystem from the graph")


def test_subsystem_only_match_skips_gate_and_answers(fake):
    # "what is the SCF storage subsystem": the gate once refused it ("lacks a verb"); now claims are verified instead
    fake["resolved"] = {**fake["resolved"], "entities": [{"id": "sub:TMF", "kind": "system", "name": "TMF", "matched": "tmfcom"}]}
    fake["gate"] = False  # would refer if the gate ran
    fake["claims"] = [{"claim": "b", "source_id": "doc:TMF-Reference:x"}]
    fake["scores"] = {"b": 0.9}
    r = A.answer("what is the tmfcom subsystem", SESSION)
    assert r["type"] == "answer" and r["claims"][0]["lane"] == "doc" and "reply" not in r
    fake["reply"] = ("It is the TMF utility [1].", {"1": "doc:TMF-Reference:x"})
    r = A.answer("what is the tmfcom subsystem", SESSION)
    assert r["reply"] == "It is the TMF utility [1]." and r["reply_citations"] == {"1": "doc:TMF-Reference:x"}


def test_unmatched_short_question_clarifies(fake):
    fake["resolved"] = {"subsystem": None, "nodes_mentioned": [], "entities": []}
    r = A.answer("its slow", SESSION)
    assert r["type"] == "clarify" and "more specific" in r["question"]


def test_unmatched_long_question_infers_subsystem_from_manuals(fake, monkeypatch):
    fake["resolved"] = {"subsystem": None, "nodes_mentioned": [], "entities": []}
    monkeypatch.setattr(A, "hybrid_search", lambda *a, **k: [{"id": f"doc:{i}", "text": "t", "system_id": "sub:TMF"} for i in range(4)])
    fake["gate"] = False  # the gate still guards a subsystem inferred from search hits
    assert A.answer("abort of a txn just leaves it hung because of data errors on a file, what now", SESSION)["type"] == "refer"
    fake["gate"] = True
    fake["claims"] = [{"claim": "a", "source_id": "doc:TMF-Reference:x"}]
    fake["scores"] = {"a": 0.9}
    r = A.answer("abort of a txn just leaves it hung because of data errors on a file, what now", SESSION)
    assert r["type"] == "answer" and r["context"]["system"] == "sub:TMF"


def test_unmatched_long_question_without_agreement_refers(fake, monkeypatch):
    fake["resolved"] = {"subsystem": None, "nodes_mentioned": [], "entities": []}
    monkeypatch.setattr(A, "_all_experts", lambda conn: [EXPERT])
    r = A.answer("how do i set up replication so dr copies everything from prod nightly", SESSION)
    assert r["type"] == "refer"


def test_subsystem_from_hits():
    hits = [{"system_id": s} for s in ["sub:TMF", "sub:TMF", "sub:TMF", "sub:FUP", "sub:TACL"]]
    assert A.subsystem_from_hits(hits) == "sub:TMF"
    assert A.subsystem_from_hits(hits[2:]) is None


def test_misattributed_claims_are_dropped(fake):
    fake["claims"] = [{"claim": "The manual recommends raising FILESPERVOLUME first.", "source_id": "maria:h7"},
                      {"claim": "Maria says check the batch.", "source_id": "doc:TMF-Reference:x"},
                      {"claim": "Experienced operators check STATUS TRANSACTION first.", "source_id": "maria:h7"}]
    fake["scores"] = {c["claim"]: 0.97 for c in fake["claims"]}
    r = A.answer("why is the audit trail filling?", SESSION)
    # the veteran claim is the note's own call text, whatever Qwen wrote; the doc claim that names a veteran is dropped
    assert [c["text"] for c in r["claims"]] == ["Check the pin first."]
    assert r["dropped_claims"] == 1


def test_misattributed_rule():
    assert A.misattributed("The manual says X", "veteran")
    assert A.misattributed("According to the documentation, raise FILESPERVOLUME", "veteran")
    assert not A.misattributed("Don't rely on the manual's FILESPERVOLUME advice before clearing the pin", "veteran")
    assert not A.misattributed("Check STATUS TRANSACTION before adding overflow", "veteran")
    assert A.misattributed("Raj recommends THAW", "doc", ["Raj Patel"])
    assert not A.misattributed("THAW SERVER resumes the class", "doc", ["Raj Patel"])


def test_clean_restores_node_backslash():
    assert A._clean("♍PROD and УDR") == r"\PROD and \DR"


def test_supported_veteran_paraphrase_is_replaced_by_verbatim(fake):
    fake["claims"] = [{"claim": "Experienced operators start by checking the pin.", "source_id": "maria:h7"}]
    fake["scores"] = {"Experienced operators start by checking the pin.": 0.9}
    r = A.answer("q", SESSION)
    assert [(c["text"], c["verbatim"]) for c in r["claims"]] == [("Check the pin first.", True)]


def test_veteran_note_dropped_when_qwens_claim_about_it_is_unsupported(fake):
    # off-topic note cited out of habit: the claim is not supported by the note text -> the note is not used
    fake["found"] = [{**HEUR, "score": 0.6}]  # relevant enough to be offered, not a close match
    fake["claims"] = [{"claim": "Operators should free audit space.", "source_id": "maria:h7"},
                      {"claim": "b", "source_id": "doc:TMF-Reference:x"}]
    fake["scores"] = {"Operators should free audit space.": 0.1, "b": 0.9}
    r = A.answer("q", SESSION)
    assert [c["lane"] for c in r["claims"]] == ["doc"]
    assert any(d["why"] == "note_unsupported" for d in r["debug"]["dropped"])


def test_relevance_cutoff_removes_off_topic_notes(fake):
    fake["found"] = [{**HEUR, "score": 0.31}]  # cosine below NOTE_MIN_SIM: not even offered to Qwen
    fake["claims"] = [{"claim": "a", "source_id": "maria:h7"}, {"claim": "b", "source_id": "doc:TMF-Reference:x"}]
    fake["scores"] = {"a": 0.9, "b": 0.9}
    r = A.answer("q", SESSION)
    assert [c["lane"] for c in r["claims"]] == ["doc"]
    assert r["debug"]["notes_below_cutoff"] == {"maria:h7": 0.31}


def test_relevant_notes_pure():
    assert A.relevant_notes(["a", "b", "c"], {"a": 0.8, "b": 0.49, "c": 0.5}, 0.5) == ["a", "c"]
    assert A.relevant_notes(["x"], {}, 0.5) == []  # unknown similarity is not relevant


def test_contradicts_flag_only_when_the_manual_section_is_cited():
    n = {**HEUR, "relation": "contradicts:doc:T:abort", "needs_review": True}
    out = A.veteran_claims(["maria:h7"], {"maria:h7": n}, {"maria:h7": n}, doc_cited={"doc:T:other"})
    assert "contradicts" not in out[0] and out[0]["needs_review"] is True
    out = A.veteran_claims(["maria:h7"], {"maria:h7": n}, {"maria:h7": n}, doc_cited={"doc:T:abort"})
    assert out[0]["contradicts"] == "doc:T:abort"


def test_clean_title():
    assert A.clean_title("Com m and(s) > Com m ands") == "Command(s) > Commands"
    assert A.clean_title("Lexical Elem ents > Com ments") == "Lexical Elem ents > Comments"


def test_negation_guard_drops_doc_claim_that_inverts_source(fake):
    fake["claims"] = [{"claim": "Raise FILESPERVOLUME first.", "source_id": "doc:TMF-Reference:x"}]
    fake["scores"] = {"Raise FILESPERVOLUME first.": 0.99}
    DOC["text"] = "Do not raise FILESPERVOLUME first on a full trail."
    try:
        r = A.answer("q", SESSION)
    finally:
        DOC["text"] = "doc text"
    assert r["type"] == "refer"


def test_veteran_claims_conflict_and_contradicts_marking():
    n1 = {**HEUR, "id": "m:h12", "call": "Abort it early.", "disagrees_with": ["r:h6"], "relation": "extends:doc:a"}
    n2 = {**HEUR, "id": "r:h6", "call": "Do not abort it yet.", "disagrees_with": ["m:h12"],
          "relation": "contradicts:doc:T:abort"}
    out = A.veteran_claims(["m:h12"], {"m:h12": n1}, {"m:h12": n1, "r:h6": n2})
    assert [(c["source_id"], c["text"], c["conflict_with"]) for c in out] == [
        ("m:h12", "Abort it early.", "r:h6"), ("r:h6", "Do not abort it yet.", "m:h12")]
    assert "contradicts" not in out[0] and out[1]["contradicts"] == "doc:T:abort"
    # partner not in context (not in the pool): no conflict claim, no flag
    out = A.veteran_claims(["m:h12"], {"m:h12": n1}, {"m:h12": n1})
    assert len(out) == 1 and "conflict_with" not in out[0]


def test_verbatim_cuts_very_long_call_to_two_sentences():
    long = " ".join(f"Sentence number {i} is here and padded out." for i in range(20))
    assert A.verbatim({"call": long}).count(".") == 2
    assert A.verbatim({"call": "Short one. Two. Three."}) == "Short one. Two. Three."


def test_note_ok_close_match_overrides_a_weak_paraphrase_score():
    assert A.note_ok(0.9, 0.55) and A.note_ok(0.1, 0.75) and not A.note_ok(0.1, 0.6) and not A.note_ok(0.1, None)


def test_note_plain_has_no_card_header():
    n = {"text": "[x] Maria (24 years) ...", "trigger": "T.", "call": "C.", "why": "W.", "not_when": ""}
    assert A.note_plain(n) == "T. C. W."


def test_note_ok_graph_link_breaks_ties_in_the_middle_band():
    # raj:h8 on the DR question: cosine 0.60, MiniCheck 0.39 on a paraphrase, linked to the MAT the question names
    assert A.note_ok(0.39, 0.60, graph_linked=True)
    assert not A.note_ok(0.39, 0.60, graph_linked=False)
    assert not A.note_ok(0.1, 0.47, graph_linked=True)  # off-topic note below the entry cutoff stays out


def test_linked_to_specific_uses_only_specific_entities():
    path = [{"src": "raj:h8", "rel": "about", "dst": "obj:audit-trail-MAT"}, {"src": "maria:h3", "rel": "about", "dst": "sub:TMF"}]
    ents = [{"id": "obj:audit-trail-MAT", "kind": "object"}, {"id": "sub:TMF", "kind": "system"}]
    assert A.linked_to_specific(path, ents) == {"raj:h8"}


@pytest.mark.parametrize("q", ["hello", "Hi!", "thanks", "thank you.", "what can you do?", "good morning"])
def test_smalltalk_gets_help_not_referral(fake, q):
    r = A.answer(q, SESSION, {"system": "sub:TMF"})  # even after the user picked an area
    assert r["type"] == "clarify" and r["options"] == [] and "NonStop" in r["question"]


def test_real_questions_are_not_smalltalk():
    assert not A.is_smalltalk("hello, TMF 185 keeps firing")
    assert not A.is_smalltalk("help, the audit trail is full")


def test_refer_reason_hides_gate_reasoning(fake):
    fake["claims"] = []
    r = A.answer("something about tmf retention", SESSION, {"system": "sub:TMF"})
    assert r["type"] == "refer" and r["reason"] == "No verified answer for \PROD · L-series · TMF."
