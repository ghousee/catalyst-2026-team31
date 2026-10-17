"""Pure parts of knowledge capture, document diffing and command approval tiers (no DB, no Ollama)."""
import pytest
from fastapi import HTTPException

from backend import documents as D
from backend import knowledge as K


# ---------------------------------------------------------------- knowledge
def test_next_note_id_and_captured_via():
    assert K.next_note_id("lena", ["lena:h2", "lena:h4", "maria:h11"]) == "lena:h5"
    assert K.next_note_id("newperson", ["lena:h2"]) == "newperson:h1"
    assert K.next_note_id("raj", ["raj:h3", "raj:h10"]) == "raj:h11"  # numeric, not lexical
    assert K.captured_via("lena", "lena") == "interview"
    assert K.captured_via("raj", "lena") == "referral"


def test_only_the_owner_can_sign():
    K.check_signer("lena", "lena")
    with pytest.raises(PermissionError):
        K.check_signer("lena", "raj")


def test_approve_by_someone_else_is_403(monkeypatch):
    monkeypatch.setattr(K, "_note_row", lambda conn, nid: {"owner_id": "lena", "status": "draft"})
    with pytest.raises(HTTPException) as e:
        K.approve_note(object(), "lena:h5", "raj")
    assert e.value.status_code == 403


def test_approve_requires_a_draft(monkeypatch):
    monkeypatch.setattr(K, "_note_row", lambda conn, nid: {"owner_id": "lena", "status": "approved"})
    with pytest.raises(HTTPException) as e:
        K.approve_note(object(), "lena:h5", "lena")
    assert e.value.status_code == 409


ENTS = [{"id": "sub:SCF-STORAGE", "kind": "system", "parent_id": None},
        {"id": "cmd:scf.status_disk_detail", "kind": "command", "parent_id": "sub:SCF-STORAGE"},
        {"id": "evt:DISK-5015", "kind": "event", "parent_id": "sub:SCF-STORAGE"},
        {"id": "obj:audit-trail-MAT", "kind": "object", "parent_id": "sub:TMF"}]  # other subsystem: never linked


def test_autolink_edges_same_subsystem_only_and_node_scope():
    e = K.autolink_edges("lena:h5", "sub:SCF-STORAGE", ["node:DR"], ENTS)
    assert ("lena:h5", "about", "sub:SCF-STORAGE") in e
    assert ("lena:h5", "about", "cmd:scf.status_disk_detail") in e and ("lena:h5", "about", "evt:DISK-5015") in e
    assert ("lena:h5", "about", "obj:audit-trail-MAT") not in e
    assert ("lena:h5", "applies_to", "node:DR") in e and ("lena:h5", "applies_to", "node:PROD") not in e
    both = K.autolink_edges("lena:h5", "sub:SCF-STORAGE", ["node:PROD", "node:DR"], ENTS)
    assert {x[2] for x in both if x[1] == "applies_to"} == {"node:PROD", "node:DR"}
    assert len(set(both)) == len(both)


# ---------------------------------------------------------------- documents
def test_diff_chunks():
    d = D.diff_chunks({"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "2x", "d": "4"})
    assert d == {"added": ["d"], "changed": ["b"], "unchanged": ["a"], "removed": ["c"]}


def test_doc_key_matches_manual_keys():
    assert D.doc_key("TMF Reference") == "TMF-Reference" and D.doc_key("  My doc (v2)! ") == "My-doc-v2"


V1 = "Overview\n\nThe widget service restarts nightly.\n\nRestart\n\nRun WIDGET RESTART to restart it.\n\nCleanup\n\nRemove old logs weekly."
V2 = V1.replace("nightly", "weekly").replace("\n\nCleanup\n\nRemove old logs weekly.", "")


def test_generic_chunks_ids_are_stable_so_the_diff_is_per_section():
    one, two = D.generic_chunks(V1, "W"), D.generic_chunks(V2, "W")
    assert [c.id for c in one] == ["doc:W:overview", "doc:W:restart", "doc:W:cleanup"]
    d = D.diff_chunks({c.id: D.content_hash(c.text) for c in one}, {c.id: D.content_hash(c.text) for c in two})
    assert (d["changed"], d["unchanged"], d["removed"], d["added"]) == (["doc:W:overview"], ["doc:W:restart"], ["doc:W:cleanup"], [])


def test_generic_chunks_split_big_sections_and_keep_unique_ids():
    big = "Part\n\n" + "\n\n".join(f"Paragraph {i} " + "word " * 200 for i in range(12))
    ids = [c.id for c in D.generic_chunks(big, "B")]
    assert len(ids) > 1 and len(set(ids)) == len(ids)


def test_chunk_text_falls_back_to_generic_for_non_hpe_text():
    assert [c.id for c in D.chunk_text(V1, "W")] == ["doc:W:overview", "doc:W:restart", "doc:W:cleanup"]


def test_mentions_match_names_and_aliases_of_own_subsystem_only():
    ents = [{"id": "cmd:w.restart", "kind": "command", "name": "WIDGET RESTART", "aliases": ["restart the widget"]},
            {"id": "sub:W", "kind": "system", "name": "Widget", "aliases": ["Widget"]},
            {"id": "sub:TMF", "kind": "system", "name": "TMF", "aliases": ["TMF"]},
            {"id": "node:PROD", "kind": "site", "name": "PROD", "aliases": ["prod"]}]
    al = D.alias_tokens(ents, "sub:W")
    assert D.mentioned(al, "Run WIDGET RESTART on prod, TMF is unaffected") == ["cmd:w.restart", "sub:W"]
    assert D.mentioned(al, "nothing relevant") == []


# ---------------------------------------------------------------- GET /graph shaping
def test_shape_graph_counts_caps_and_recent():
    from backend.graph.view import shape_graph
    ents = [{"id": "sub:TMF", "kind": "system", "name": "TMF", "aliases": None},
            {"id": "node:PROD", "kind": "site", "name": "PROD", "aliases": ["prod"]}]
    edges = [{"src": "a", "rel": "about", "dst": "sub:TMF", "source_id": "a", "created_by": "seed"},
             {"src": "lena:h5", "rel": "about", "dst": "sub:TMF", "source_id": "lena:h5", "created_by": "auto"},
             {"src": "lena:h5", "rel": "applies_to", "dst": "node:PROD", "source_id": "lena:h5", "created_by": "auto"}]
    note = {"id": "lena:h5", "owner_name": "Lena", "kind": "note", "scope": "TMF / PROD", "status": "approved",
            "needs_review": True, "signed_at": "2026-10-17", "captured_at": "2026-10-16", "call_text": "x"}
    docs = [{"title": "TMF Ref", "chunks": 7, "last_loaded": "2026-10-15"}]
    g = shape_graph(ents, edges, [note], 3, docs, link_cap=2)
    assert g["counts"]["entities"] == {"site": 1, "system": 1}
    assert g["counts"]["links"] == {"about": 2, "applies_to": 1}
    assert g["counts"]["notes"] == {"approved": 1, "draft": 0, "retired": 0, "needs_review": 1}
    assert (g["counts"]["persons"], g["counts"]["doc_sections"], g["counts"]["documents"]) == (3, 7, 1)
    assert [e["links"] for e in g["entities"]] == [2, 1] and g["entities"][0]["aliases"] == []
    assert len(g["links"]) == 2 and g["links_total"] == 3
    assert all(x["created_by"] == "auto" for x in g["links"])  # auto links survive the cap, seed is cut
    assert [r["type"] for r in g["recent"]] == ["note_signed", "links_auto", "document_loaded"]


# ---------------------------------------------------------------- teach chat
SUBS = {"sub:SCF-STORAGE", "sub:TMF"}
SAID = "on DR, when SCF STATUS DISK shows a path DOWN after a CLIM restart, wait 5 minutes before resetting"
RAW = {"action": "draft", "question": "", "trigger_text": "SCF STATUS DISK shows a path DOWN after a CLIM restart",
       "call_text": "wait 5 minutes before resetting", "why_text": "", "not_when_text": "", "node": "DR",
       "subsystem": "sub:SCF-STORAGE", "kind": "note"}


def test_teach_complete_turn_is_a_draft():
    r = K.shape_turn(RAW, SAID, SUBS, 0)
    assert r["type"] == "draft" and r["draft"]["node"] == "DR" and r["draft"]["subsystem"] == "sub:SCF-STORAGE"


def test_teach_model_ask_is_a_question():
    r = K.shape_turn({**RAW, "action": "ask", "question": "Why wait?"}, SAID, SUBS, 0)
    assert r == {"type": "question", "text": "Why wait?"}


def test_teach_missing_content_forces_question_even_if_model_says_draft():
    assert K.shape_turn({**RAW, "call_text": ""}, SAID, SUBS, 0)["type"] == "question"


def test_teach_unknown_subsystem_asks_then_uses_hint():
    bad = {**RAW, "subsystem": "sub:MADEUP"}
    assert K.shape_turn(bad, SAID, SUBS, 0)["type"] == "question"
    assert K.shape_turn(bad, SAID, SUBS, 0, subsystem_hint="sub:TMF")["draft"]["subsystem"] == "sub:TMF"


def test_teach_after_max_followups_drafts_with_what_is_known():
    bad = {**RAW, "subsystem": "sub:MADEUP", "node": "unknown", "action": "ask", "question": "more?"}
    r = K.shape_turn(bad, SAID, SUBS, K.MAX_FOLLOWUPS)
    assert r["type"] == "draft" and r["draft"]["subsystem"] == "" and r["draft"]["node"] == "ALL"


def test_teach_never_returns_invented_fields():
    inv = {**RAW, "why_text": "because the controller firmware re-negotiates links slowly",
           "not_when_text": "if the storage pool is encrypted"}
    d = K.shape_turn(inv, SAID, SUBS, 0)["draft"]
    assert d["why_text"] == "" and d["not_when_text"] == ""
    said2 = SAID + ". It usually recovers on its own. Does not apply if both paths are down."
    ok = K.shape_turn({**RAW, "why_text": "it usually recovers on its own", "not_when_text": "both paths are down"},
                      said2, SUBS, 0)
    assert ok["draft"]["why_text"] and ok["draft"]["not_when_text"]


def test_teach_endpoint_makes_one_llm_call(monkeypatch):
    import contextlib
    import json as _j
    calls = []
    monkeypatch.setattr(K.llm, "chat", lambda *a, **k: calls.append(1) or {"content": _j.dumps(RAW)})

    @contextlib.contextmanager
    def fake():
        yield object()
    monkeypatch.setattr(K, "connect", fake)
    monkeypatch.setattr(K, "_rows", lambda c, q, p=(): [{"id": "sub:SCF-STORAGE", "name": "SCF"}] if "entity" in q else [{"x": 1}])
    out = K.teach(K.TeachIn(owner_id="lena", messages=[K.TeachMsg(role="veteran", text=SAID)]))
    assert out["type"] == "draft" and len(calls) == 1


def test_teach_schema_limits_subsystem_to_real_ids():
    s = K.teach_schema({"sub:TMF", "sub:FUP"})
    assert s["properties"]["subsystem"]["enum"] == ["sub:FUP", "sub:TMF", "unknown"]
    assert K.TEACH_SCHEMA["properties"]["subsystem"] == {"type": "string"}  # the shared schema is not mutated
