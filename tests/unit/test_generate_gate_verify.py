"""Pure logic of generate / gate / verify (no Ollama, no model download)."""
from backend.pipeline.gate import parse_gate
from backend.pipeline.generate import build_messages, keep_cited, parse_claims, unalias
from backend.pipeline.verify import windows

CHUNKS = [{"id": "doc:A:one", "text": "alpha"}, {"id": "doc:A:two", "text": "beta"}]


def test_parse_claims_accepts_valid_and_rejects_bad_shapes():
    assert parse_claims('[{"claim": "x", "source_id": "S1"}]') == [{"claim": "x", "source_id": "S1"}]
    assert parse_claims("[]") == []
    assert parse_claims("not json") is None
    assert parse_claims('{"claim": "x"}') is None
    assert parse_claims('[{"claim": "x"}]') is None
    assert parse_claims('[{"claim": 1, "source_id": "S1"}]') is None


def test_keep_cited_drops_claims_without_a_retrieved_source():
    claims = [{"claim": "a", "source_id": "doc:A:one"}, {"claim": "b", "source_id": "doc:A:ghost"}]
    kept, dropped = keep_cited(claims, ["doc:A:one", "doc:A:two"])
    assert [c["claim"] for c in kept] == ["a"] and [c["claim"] for c in dropped] == ["b"]


def test_alias_roundtrip_and_unknown_labels_stay_invalid():
    msgs = build_messages("q?", CHUNKS, alias=True)
    assert "[source_id: S1]" in msgs[1]["content"] and "doc:A:one" not in msgs[1]["content"]
    claims = [{"claim": "a", "source_id": "S2"}, {"claim": "b", "source_id": "S9"}]
    mapped = unalias(claims, CHUNKS)
    assert mapped[0]["source_id"] == "doc:A:two" and mapped[1]["source_id"] == "S9"
    assert keep_cited(mapped, [c["id"] for c in CHUNKS])[0] == [mapped[0]]


def test_build_messages_without_alias_uses_raw_ids_and_truncates():
    msgs = build_messages("q?", [{"id": "doc:A:one", "text": "x" * 100}], max_chars=10, alias=False)
    assert "[source_id: doc:A:one]" in msgs[1]["content"] and "x" * 11 not in msgs[1]["content"]


def test_parse_gate():
    assert parse_gate('{"sufficient": true, "reason": "ok"}') is True
    assert parse_gate('{"sufficient": false, "reason": "no"}') is False
    assert parse_gate('{"sufficient": tru') is None      # truncated output counts as "no verdict"
    assert parse_gate('{"reason": "x"}') is None


def test_verify_windows_split_by_words():
    w = windows(" ".join(str(i) for i in range(1000)), n=400)
    assert len(w) == 3 and len(w[0].split()) == 400 and len(w[2].split()) == 200
    assert windows("") == [""]
