"""Pure parts of knowledge capture, document diffing and command approval tiers (no DB, no Ollama)."""
import pytest
from fastapi import HTTPException

from backend import commands as C
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


# ---------------------------------------------------------------- commands
def test_command_id_roundtrip_and_fill():
    cid = C.cmd_id("tmfcom.status_tmf", "node:PROD")
    assert cid == "tmfcom.status_tmf@PROD" and C.parse_id(cid) == ("tmfcom.status_tmf", "node:PROD")
    with pytest.raises(ValueError):
        C.parse_id("nonsense")
    assert C.fill(r"TMFCOM ABORT TRANSACTION \node(cpu).seq.num", "node:PROD") == r"TMFCOM ABORT TRANSACTION \PROD(cpu).seq.num"
    assert C.fill("SCF STATUS DISK $vol, DETAIL", "node:DR") == "SCF STATUS DISK $vol, DETAIL"  # other slots stay


def test_approval_tier_from_risk():
    assert [C.approval_for(r)["required"] for r in ("read_only", "state_changing", "critical", "weird")] == [
        "one_click", "type_node", "second_approver", "second_approver"]


def test_tier_enforcement():
    P, DR = "node:PROD", "node:DR"
    assert C.check_approval("read_only", P, P, "u")[0] == "approved"
    # type_node: the typed text must be the session node
    assert C.check_approval("state_changing", P, P, "u")[0] == "rejected"
    assert C.check_approval("state_changing", P, P, "u", typed_node=r"\DR")[0] == "rejected"
    assert C.check_approval("state_changing", P, P, "u", typed_node=r"\PROD")[0] == "approved"
    # second_approver: needed, must be someone else, must exist
    assert C.check_approval("critical", P, P, "u")[0] == "needs_second_approver"
    assert C.check_approval("critical", P, P, "u", second_approver="u")[0] == "rejected"
    assert C.check_approval("critical", P, P, "u", second_approver="ghost", known_people={"raj"})[0] == "rejected"
    assert C.check_approval("critical", P, P, "u", second_approver="raj", known_people={"raj"})[0] == "approved"
    # the node guard beats every tier: a command proposed for \PROD cannot be approved from a \DR session
    assert C.check_approval("read_only", P, DR, "u")[0] == "rejected"


def test_sim_output_is_labelled_simulated():
    assert "simulated" in C.sim_output("tmfcom.status_tmf", "TMFCOM STATUS TMF", "node:PROD").lower()
    assert "Simulated" in C.sim_output("unknown.template", "X", "node:DR") and r"\DR" in C.sim_output("unknown.template", "X", "node:DR")
