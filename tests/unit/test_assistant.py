"""Assistant mode: citation mapping, node rule, prompt shape. No Docker/Ollama."""
from backend.pipeline import assistant as A

SRC = [{"id": "doc:TMF:x", "kind": "doc", "text": "manual text"}, {"id": "maria:h7", "kind": "note", "text": "note"}]


def test_map_citations_keeps_real_sources_and_drops_unknown_numbers():
    text, cites, used = A.map_citations("Do X [1]. Maria says Y [2, 9]. Z [7].", SRC)
    assert cites == {"1": "doc:TMF:x", "2": "maria:h7"} and used == ["doc:TMF:x", "maria:h7"]
    assert "[7]" not in text and "[2]" in text


def test_build_messages_labels_sources_and_includes_history():
    msgs = A.build_messages("why?", SRC, "\PROD", "L-series", "Raj Patel (on_call)",
                            [{"question": "q1", "reply": "a1"}])
    assert msgs[0]["role"] == "system" and "\PROD" in msgs[0]["content"] and "Raj Patel" in msgs[0]["content"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert "[1] MANUAL" in msgs[-1]["content"] and "[2] VETERAN" in msgs[-1]["content"]


def test_other_node_mention_asks_which_node(monkeypatch):
    r = A.answer("is the audit trail filling on DR?", {"node": "node:PROD", "series": "rvu:L"})
    assert r["type"] == "clarify" and {o["label"] for o in r["options"]} == {"\PROD", "\DR"}


def test_note_text_states_owner_scope_and_not_when():
    n = {"site_id": "node:PROD", "trigger_text": "T", "call_text": "C", "why_text": "W", "not_when_text": "N",
         "owner_name": "Maria Rossi", "owner_role": "Senior", "years": 24}
    t = A.note_text(n)
    assert "Maria Rossi" in t and "\PROD" in t and "Does not apply when: N" in t
