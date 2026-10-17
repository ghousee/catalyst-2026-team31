"""Knowledge-graph queries on an in-memory SQLite mirror (no Docker): resolve(), walk(), lookup(), seed validation.

The key guarantee: a \\PROD-scoped veteran note is never returned (nor cited in the path) for a \\DR session.
"""
import json
import sqlite3

import pytest

from backend.graph import load
from backend.graph.query import lookup, resolve, tokens, walk

DDL = """
CREATE TABLE entity (id TEXT PRIMARY KEY, kind TEXT, name TEXT, aliases TEXT, parent_id TEXT, props TEXT);
CREATE TABLE edge (src TEXT, rel TEXT, dst TEXT, weight REAL DEFAULT 1, source_id TEXT, created_by TEXT);
CREATE TABLE person (id TEXT PRIMARY KEY, name TEXT, role TEXT, team TEXT, years INT, expertise TEXT,
                     availability TEXT, active INT, contact TEXT);
CREATE TABLE doc_chunk (id TEXT PRIMARY KEY, section TEXT, text TEXT, system_id TEXT, version_id TEXT, site_id TEXT,
                        all_versions INT, all_sites INT, edition TEXT, valid_to TEXT);
CREATE TABLE heuristic (id TEXT PRIMARY KEY, owner_id TEXT, trigger_text TEXT, call_text TEXT, why_text TEXT,
                        not_when_text TEXT, system_id TEXT, version_id TEXT, site_id TEXT, all_versions INT, all_sites INT,
                        provenance TEXT, status TEXT, endorsements INT, last_validated TEXT, captured_via TEXT, captured_at TEXT,
                        embedding TEXT);
"""


def ent(i, kind, name, aliases=(), parent=None, props=None):
    return (i, kind, name, json.dumps(list(aliases)), parent, json.dumps(props or {}))


ENTITIES = [
    ent("sub:TMF", "system", "TMF (TMFCOM)", ["TMF"]),
    ent("sub:PATHWAY", "system", "Pathway", ["Pathway"]),
    ent("node:PROD", "site", "PROD", ["\\PROD", "prod"]),
    ent("node:DR", "site", "DR", ["\\DR", "dr"]),
    ent("evt:TMF-185", "event", "TMF 185 - audit file pinned", ["audit trail filling", "pinned file"], "sub:TMF",
        {"ems": "TMF", "number": 185}),
    ent("evt:TMF-187", "event", "TMF 187 - audit trail critically full", ["audit trail full"], "sub:TMF",
        {"ems": "TMF", "number": 187}),
    ent("evt:PATHWAY-1034", "event", "Pathway 1034 - no server available", ["no server available"], "sub:PATHWAY",
        {"ems": "Pathway", "number": 1034}),
    ent("obj:MAT", "object", "Master audit trail", ["audit trail", "MAT"], "sub:TMF"),
    ent("obj:far", "object", "Far object", ["far away thing"], "sub:TMF"),
    ent("cmd:tmf.status", "command", "TMFCOM STATUS AUDITTRAIL", [], "sub:TMF",
        {"template_id": "tmf.status", "command": "TMFCOM STATUS AUDITTRAIL, DETAIL", "risk": "read_only",
         "explanation": "capacity", "source_id": "doc:T:status", "subsystem": "sub:TMF"}),
    ent("cmd:tmf.abort", "command", "ABORT", [], "sub:TMF",
        {"template_id": "tmf.abort", "command": "TMFCOM ABORT TRANSACTION x", "risk": "critical",
         "explanation": "abort", "source_id": "doc:T:abort", "subsystem": "sub:TMF"}),
    ent("cmd:path.status", "command", "PATHCOM STATUS TCP", [], "sub:PATHWAY",
        {"template_id": "path.status", "command": "PATHCOM STATUS TCP *", "risk": "read_only",
         "explanation": "tcp", "source_id": "doc:P:tcp", "subsystem": "sub:PATHWAY"}),
]
EDGES = [  # src, rel, dst, weight, source_id
    ("evt:TMF-185", "symptom_of", "obj:MAT", 1, "doc:T:status"),
    ("evt:TMF-185", "precedes", "evt:TMF-187", 1, "m:h7"),
    ("evt:TMF-185", "diagnosed_by", "cmd:tmf.status", 1, "doc:T:status"),
    ("evt:TMF-185", "fixed_by", "cmd:tmf.abort", 1, "doc:T:abort"),
    ("evt:TMF-185", "fixed_by", "doc:T:status", 1, "doc:T:status"),
    ("evt:TMF-185", "about", "sub:TMF", 1, "doc:T:status"),
    ("evt:PATHWAY-1034", "diagnosed_by", "cmd:path.status", 1, "doc:P:tcp"),
    ("obj:MAT", "depends_on", "obj:far", 1, "doc:T:status"),
    ("m:h7", "about", "evt:TMF-185", 1, "m:h7"),
    ("m:h7", "extends", "doc:T:status", 1, "m:h7"),
    ("m:h1", "about", "evt:TMF-185", 1, "m:h1"),
    ("m:h1", "contradicts", "doc:T:abort", 1, "m:h1"),
    ("m:h9", "about", "evt:TMF-185", 1, "m:h9"),
    ("d:h2", "about", "evt:TMF-185", 1, "d:h2"),
    ("m:h1", "disagrees_with", "d:h2", 1, "m:h1"),
    ("maria", "expert_in", "sub:TMF", 31, "m:h7"),
    ("raj", "expert_in", "sub:TMF", 4, "d:h2"),
]
PERSONS = [
    ("maria", "Maria Rossi", "Senior NonStop Operator", "Ops", 24, json.dumps(["TMF"]), "retired", 0, None),
    ("raj", "Raj Patel", "Specialist", "Ops", 15, json.dumps(["TMF"]), "on_call", 1, "ext. 1"),
]
CHUNKS = [  # id, section, text, system, version, site, all_versions, all_sites, edition  (manuals: all series, all nodes)
    ("doc:T:status", "STATUS AUDITTRAIL", "x", "sub:TMF", None, None, 1, 1, "TMF Ref, H-series edition"),
    ("doc:T:abort", "ABORT TRANSACTION", "x", "sub:TMF", None, None, 1, 1, "TMF Ref, H-series edition"),
    ("doc:P:tcp", "STATUS TCP", "x", "sub:PATHWAY", None, None, 1, 1, "Pathway, J/H-series edition"),
]


def heur(i, owner, system, version, site, status="approved", via="interview", vec=(1, 0)):
    return (i, owner, f"trig {i}", f"call {i}", f"why {i}", f"notwhen {i}", system, version, site,
            int(version is None), int(site is None), "interview:2026-09-30", status, 2, "2026-09-30", via, "2026-09-30", json.dumps(list(vec)))


HEURISTICS = [
    heur("m:h7", "maria", "sub:TMF", "rvu:L", "node:PROD"),
    heur("m:h1", "maria", "sub:TMF", "rvu:L", "node:PROD"),                # contradicts the manual, \PROD only
    heur("m:h9", "maria", "sub:TMF", "rvu:L", "node:PROD", status="draft"),
    heur("d:h2", "raj", "sub:TMF", "rvu:L", "node:DR"),                    # \DR only
]
PROD = {"system": "sub:TMF", "version": "rvu:L", "site": "node:PROD"}
DR = {**PROD, "site": "node:DR"}


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.executemany("INSERT INTO entity VALUES (?,?,?,?,?,?)", ENTITIES)
    con.executemany("INSERT INTO edge (src, rel, dst, weight, source_id) VALUES (?,?,?,?,?)", EDGES)
    con.executemany("INSERT INTO person VALUES (?,?,?,?,?,?,?,?,?)", PERSONS)
    con.executemany("INSERT INTO doc_chunk (id,section,text,system_id,version_id,site_id,all_versions,all_sites,edition) VALUES (?,?,?,?,?,?,?,?,?)", CHUNKS)
    con.executemany("INSERT INTO heuristic VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", HEURISTICS)
    yield con
    con.close()


def ids(r):
    return [e["id"] for e in r["entities"]]


# ------------------------------------------------------------------ resolve
def test_tokens_stem_and_stopwords():
    assert tokens("the audit trail is filling up") == tokens("audit trail fills") == ["audit", "trail", "fill"]
    assert tokens("TMF185") == ["tmf", "185"]
    assert tokens("$AUDIT volume") == ["$audit", "volume"]


def test_alias_resolution_shop_floor_words(db):
    r = resolve(db, "why is the audit trail filling?", {})
    assert "evt:TMF-185" in ids(r) and "obj:MAT" in ids(r)
    assert r["subsystem"] == "sub:TMF"
    assert next(e for e in r["entities"] if e["id"] == "evt:TMF-185")["matched"] == "audit trail filling"


@pytest.mark.parametrize("text", ["what is TMF 185", "TMF185 again", "we see event 185", "got a 185 overnight"])
def test_event_number_resolves(db, text):
    assert "evt:TMF-185" in ids(resolve(db, text, {}))


def test_bare_number_prefers_named_subsystem(db):
    assert ids(resolve(db, "error 1034", {})) == ["evt:PATHWAY-1034"]
    assert resolve(db, "error 1034", {})["subsystem"] == "sub:PATHWAY"


def test_percent_and_unknown_numbers_ignored(db):
    assert ids(resolve(db, "cpu at 185% and 9999 users", {})) == []


def test_nodes_mentioned_and_no_match(db):
    r = resolve(db, "audit trail full on \\DR", {})
    assert r["nodes_mentioned"] == ["node:DR"] and "evt:TMF-187" in ids(r)
    empty = resolve(db, "hello there", {})
    assert empty == {"subsystem": None, "entities": [], "nodes_mentioned": []}


def test_subsystem_tie_is_none(db):
    r = resolve(db, "no server available, pinned file, MAT", {})
    assert r["subsystem"] is None  # two subsystems tie -> caller must clarify


# ------------------------------------------------------------------ walk
def test_walk_depth_and_hubs():
    edges = [{"src": s, "rel": r, "dst": d, "source_id": x} for s, r, d, _, x in EDGES]
    d1, _ = walk(edges, ["evt:TMF-185"], max_depth=1)
    assert "obj:MAT" in d1 and "obj:far" not in d1          # far is 2 hops away
    d2, used = walk(edges, ["evt:TMF-185"], max_depth=2)
    assert d2["obj:far"] == 2
    assert "sub:TMF" in d2 and not any(e["src"] == "sub:TMF" for e in used)   # hubs are reached, never expanded
    assert "maria" not in d2                                  # persons come from expert_in on anchors, not the walk


# ------------------------------------------------------------------ lookup + context
def test_prod_gets_prod_notes_never_drafts(db):
    res = lookup(db, ["evt:TMF-185"], PROD)
    got = {h["id"] for h in res["heuristics"]}
    assert got == {"m:h7", "m:h1"}          # approved + in scope; the draft and the DR note are absent
    rels = {h["id"]: h["relation"] for h in res["heuristics"]}
    assert rels["m:h1"] == "contradicts:doc:T:abort"      # contradicts beats the disagreement it also has
    assert rels["m:h7"] == "extends:doc:T:status"
    assert res["heuristics"][0]["id"] == "m:h1"           # contradictions are shown first
    assert "Maria Rossi" in res["heuristics"][0]["text"] and "notwhen m:h1" in res["heuristics"][0]["text"]


def test_note_search_is_context_scoped(db):
    from backend.graph.query import note_search
    prod = note_search(db, [1.0, 0.0], PROD, k=5)
    assert {h["id"] for h in prod} == {"m:h7", "m:h1"}      # no draft, no DR note
    assert prod[0]["call"].startswith("call ")
    dr = note_search(db, [1.0, 0.0], DR, k=5)
    assert {h["id"] for h in dr} == {"d:h2"}                # a \PROD note is never returned on \DR
    assert "m:h7" not in json.dumps(dr) and "m:h1" not in json.dumps(dr)
    assert note_search(db, [1.0, 0.0], {**PROD, "site": None}, k=5) == []
    assert note_search(db, [1.0, 0.0], {**PROD, "version": "rvu:J"}, k=5) == []


def test_note_search_ranks_by_cosine_and_fetch_notes_filters_context(db):
    from backend.graph.query import fetch_notes, note_search
    db.execute("UPDATE heuristic SET embedding = '[0, 1]' WHERE id = 'm:h1'")
    assert [h["id"] for h in note_search(db, [0.0, 1.0], PROD, k=1)] == ["m:h1"]
    assert set(fetch_notes(db, ["m:h7", "d:h2", "m:h9"], PROD)) == {"m:h7"}


def test_prod_only_note_never_returned_for_dr(db):
    res = lookup(db, ["evt:TMF-185"], DR)
    assert {h["id"] for h in res["heuristics"]} == {"d:h2"}
    blob = json.dumps(res)
    assert "m:h7" not in blob and "m:h1" not in blob      # not as a note, an expert reason, or a path citation


@pytest.mark.parametrize("site", [None, "node:OTHER"])
def test_unresolved_or_unknown_node_gets_no_node_scoped_notes(db, site):
    res = lookup(db, ["evt:TMF-185"], {**PROD, "site": site})
    assert res["heuristics"] == []


def test_series_mismatch_hides_series_scoped_notes_but_manuals_still_apply(db):
    res = lookup(db, ["evt:TMF-185"], {**PROD, "version": "rvu:J"})
    assert res["heuristics"] == []
    assert {d["id"] for d in res["doc_chunks"]} >= {"doc:T:status"}      # manuals are all-series (ADR-005)
    assert res["doc_chunks"][0]["edition"] == "TMF Ref, H-series edition"


def test_commands_same_subsystem_only_ordered_by_risk(db):
    res = lookup(db, ["evt:TMF-185", "evt:PATHWAY-1034"], PROD)
    assert [c["template_id"] for c in res["commands"]] == ["tmf.status", "tmf.abort"]   # Pathway command filtered, read_only first
    assert {"template_id", "command", "risk", "explanation", "source_id", "subsystem"} == set(res["commands"][0])
    assert "doc:T:status" in [d["id"] for d in res["doc_chunks"]]
    assert all(d["system_id"] == "sub:TMF" for d in res["doc_chunks"])


def test_experts_active_first_and_reason(db):
    res = lookup(db, ["evt:TMF-185"], PROD)
    maria = next(x for x in res["experts"] if x["id"] == "maria")
    assert maria["active"] is False and "31" in maria["reason"]
    assert [x["id"] for x in res["experts"]][0] == "raj"        # active before retired
    assert {"id", "name", "role", "team", "years", "expertise", "availability", "contact", "reason", "active"} == set(maria)


def test_path_only_contains_returned_things(db):
    res = lookup(db, ["evt:TMF-185"], PROD)
    assert {"src": "evt:TMF-185", "rel": "symptom_of", "dst": "obj:MAT", "source_id": "doc:T:status"} in res["path"]
    returned = ({h["id"] for h in res["heuristics"]} | {d["id"] for d in res["doc_chunks"]}
                | {x["id"] for x in res["experts"]})
    for e in res["path"]:
        for end in (e["src"], e["dst"]):
            assert ":" in end and not end.startswith(("doc:", "m:h", "d:h")) or end in returned


def test_lookup_without_system_infers_or_refuses(db):
    ok = lookup(db, ["evt:TMF-185"], {"system": None, "version": "rvu:L", "site": "node:PROD"})
    assert {h["id"] for h in ok["heuristics"]} == {"m:h7", "m:h1"}
    with pytest.raises(ValueError):
        lookup(db, ["evt:TMF-185", "evt:PATHWAY-1034"], {"system": None, "version": None, "site": None})


# ------------------------------------------------------------------ seed files + loader validation
def test_seed_files_are_internally_consistent():
    entities, persons, heuristics, raw = load.read_seed()
    edges = load.seed_edges(raw) + load.heuristic_edges(heuristics)
    cited = {e[3] for e in edges} | {(e.get("props") or {}).get("source_id") for e in entities if e["kind"] == "command"}
    chunks = {c for c in cited | {t for e in edges for t in e[:3]} if c and c.startswith("doc:")}
    known = {"sub:TMF", "sub:PATHWAY", "sub:SCF-STORAGE", "sub:TACL", "sub:PEEK", "sub:MEASURE", "sub:FUP",
             "node:PROD", "node:DR", "rvu:L", "rvu:J", "rvu:H"}
    assert load.validate(entities, persons, heuristics, edges, chunks, known) == []
    assert len({h["id"] for h in heuristics}) == len(heuristics) >= 8
    prod_only = [h for h in heuristics if h["site"] == "node:PROD"]
    assert prod_only and any(h["site"] == "node:DR" for h in heuristics)
    assert any(h["kind"] == "warning_pattern" and h["pattern"] for h in heuristics)
    assert any(h.get("contradicts") for h in heuristics) and any(h.get("disagrees_with") for h in heuristics)


def test_validate_fails_on_missing_source():
    entities = [{"id": "cmd:x", "kind": "command", "props": {"source_id": "doc:nope"}}]
    problems = load.validate(entities, [], [], [("cmd:x", "about", "cmd:x", "doc:nope", 1.0)], {"doc:ok"}, set())
    assert any("doc:nope" in p for p in problems) and len(problems) == 2


def test_expert_note_count_is_approved_notes_of_the_owner_in_context(db):
    # maria has 3 notes (h7, h1 approved and \PROD; h9 draft): on \PROD the count is 2, on \DR (none in scope) 0
    prod = lookup(db, ["evt:TMF-185"], PROD)
    maria = next(x for x in prod["experts"] if x["id"] == "maria")
    assert "author of 2 approved note(s) that apply here" in maria["reason"]
    dr = lookup(db, ["evt:TMF-185"], DR)
    assert all("author of" not in x["reason"] or x["id"] == "raj" for x in dr["experts"])
    raj = next(x for x in dr["experts"] if x["id"] == "raj")
    assert "author of 1 approved note(s)" in raj["reason"]


def test_removed_chunks_are_not_returned(db):
    db.execute("UPDATE doc_chunk SET valid_to = date('now') WHERE id = 'doc:T:status'")  # removed today (exclusive end)
    ids_ = [d["id"] for d in lookup(db, ["evt:TMF-185"], PROD)["doc_chunks"]]
    assert "doc:T:status" not in ids_ and "doc:T:abort" in ids_
