"""Conversational layer: reply guard, follow-up memory + node rules, status questions, refer next steps (no Docker/Ollama)."""
import pytest

from backend.pipeline import answer as A
from backend.pipeline import converse as C

CLAIMS = [{"text": "Do not raise FILESPERVOLUME before you clear the pinned file.", "source_id": "maria:h7", "lane": "veteran"},
          {"text": "TMFCOM STATUS AUDITTRAIL, DETAIL shows capacity used (65%) and the first pinned file.",
           "source_id": "doc:T:x", "lane": "doc"}]
CTX = r"\PROD · L-series · TMF"


def test_reply_guard_accepts_grounded_reply():
    ok = "No, do not raise FILESPERVOLUME yet [1]. Run TMFCOM STATUS AUDITTRAIL, DETAIL to see the first pinned file [2]."
    assert C.reply_ok(ok, CLAIMS, CTX)
    assert C.reply_citations(ok, CLAIMS) == {"1": "maria:h7", "2": "doc:T:x"}


@pytest.mark.parametrize("bad", [
    "Do not raise FILESPERVOLUME [1]. Capacity is at 80% [2].",              # number not in the claims
    "Do not raise FILESPERVOLUME [1]. Run TMFCOM ABORT TRANSACTION [2].",    # command name not in the claims
    "Do not raise FILESPERVOLUME [1]. Check \\DR first [2].",                # node name not in the claims
    "Do not raise FILESPERVOLUME [1]. Then check the pin.",                  # sentence without a marker
    "Do not raise FILESPERVOLUME [3].",                                      # marker beyond the claims
    "You can raise FILESPERVOLUME after the pin is cleared [1].",            # dropped the 'do not'
    "Do not raise FILESPERVOLUME [1]. Run TMFCOM STATUS AUDITTRAIL, DETAIL [2",  # cut off mid-sentence
    ""])
def test_reply_guard_rejects(bad):
    assert not C.reply_ok(bad, CLAIMS, CTX)


def test_write_reply_falls_back_to_none_when_guard_rejects(monkeypatch):
    monkeypatch.setattr(C.llm, "chat", lambda *a, **k: {"content": "Invented 99 things."})
    assert C.write_reply("q", CLAIMS) == (None, {})
    monkeypatch.setattr(C.llm, "chat", lambda *a, **k: {"content": "Do not raise FILESPERVOLUME [1]."})
    assert C.write_reply("q", CLAIMS)[1] == {"1": "maria:h7"}
    monkeypatch.setattr(C.llm, "chat", lambda *a, **k: 1 / 0)
    assert C.write_reply("q", CLAIMS) == (None, {})


HIST = [{"question": "TMF 185 has fired twice and the audit trail is at 65% and climbing, what should I check first?",
         "context": {"system": "sub:TMF", "site": "node:PROD", "version": "rvu:L"}, "entities": ["evt:TMF-185"]},
        {"question": "why?", "context": {"system": "sub:TMF", "site": "node:PROD"}, "entities": []}]


def test_short_followup_gets_previous_standalone_question():
    assert C.followup_text("why?", HIST).startswith("TMF 185 has fired twice")
    assert C.followup_text("what about on DR?", HIST).endswith("what about on DR?")
    assert C.followup_text("why?", []) is None
    assert C.followup_text("how do i recalibrate the coffee machine", HIST) is None  # a new question is not a follow-up
    assert C.last_system(HIST) == "sub:TMF" and C.last_system([]) is None


def test_status_question_detection():
    for q in ["is Pathway healthy?", "status of TMF", "Is the disk ok", "are the TCPs up?", "is tmf down"]:
        assert C.is_status_question(q), q
    for q in ["why is the audit trail filling?", "how do I add an overflow volume", "what is the SCF storage subsystem"]:
        assert not C.is_status_question(q), q


def test_status_reply_never_invents_a_state():
    t = C.status_reply("Pathway", r"\PROD", [], ["PATHCOM STATUS TCP *"])
    assert "can't tell its current state" in t and "PATHCOM STATUS TCP *" in t
    live = C.live_metrics("sub:TMF", {"series": [{"metric": "audit-capacity-pct", "points": [["t0", 40.0], ["t1", 62.0]]},
                                                 {"metric": "cpu-busy-time", "points": [["t1", 50.0]]}]})
    assert live == [{"metric": "audit-capacity-pct", "value": 62.0, "ts": "t1"}]
    assert "Simulated live data" in C.status_reply("TMF", r"\PROD", live, []) and C.live_metrics("sub:PATHWAY", {"series": []}) == []


def test_refer_next_steps_and_reply():
    steps = C.refer_next_steps([("PATHCOM STATUS TCP *", "Lists TCPs and their state; DETAIL shows more."), ("B", "x"), ("C", "y"), ("D", "z")])
    assert len(steps) == 3 and steps[0] == "Run PATHCOM STATUS TCP * (read-only): Lists TCPs and their state."
    r = C.refer_reply(r"\PROD · Pathway", steps[:1], [{"name": "Raj Patel", "availability": "on_call"}])
    assert r.startswith(r"I don't have verified knowledge for this on \PROD · Pathway. Next: Run") and r.endswith("Raj Patel (on call) knows this system.")


# --- through answer(): a node switch in a follow-up still goes through the node rules
SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "t"}


def test_node_switch_followup_clarifies_instead_of_leaking(monkeypatch):
    from tests.unit.test_answer import Conn
    monkeypatch.setattr(A, "connect", lambda: Conn())
    monkeypatch.setattr(A, "resolve", lambda conn, q, ctx: {
        "subsystem": "sub:TMF" if "TMF" in q else None, "entities": [],
        "nodes_mentioned": ["node:DR"] if q.rstrip("?").endswith("DR") else []})
    monkeypatch.setattr(A, "_rows", lambda conn, sql, params=(): [{"id": "node:DR", "name": "DR"}])
    r = A.answer("what about on DR?", SESSION, None, HIST)
    assert r["type"] == "clarify" and r["options"][0]["value"] == {"site": "node:DR"}
    # no history: nothing to inherit, the vague question asks for the subsystem as before
    assert A.answer("what about on PROD?", SESSION, None, [])["type"] == "clarify"
