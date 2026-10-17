"""Learning map shaping and user filtering (pure, no DB)."""
import pytest
from fastapi import HTTPException

from backend import learning as L

ENTS = [
    {"id": "sub:TMF", "kind": "system", "name": "TMF", "parent_id": None},
    {"id": "sub:TACL", "kind": "system", "name": "TACL", "parent_id": None},
    {"id": "evt:TMF-185", "kind": "event", "name": "TMF 185", "parent_id": "sub:TMF"},
    {"id": "evt:TMF-187", "kind": "event", "name": "TMF 187", "parent_id": "sub:TMF"},
    {"id": "obj:audit", "kind": "object", "name": "Audit trail", "parent_id": "sub:TMF"},
    {"id": "cmd:tacl.x", "kind": "command", "name": "X", "parent_id": "sub:TACL"},
]
NOTES = {"raj:h3": {"id": "raj:h3", "system_id": "sub:TMF", "owner_id": "raj", "owner_name": "Raj"}}
DOCS = {"doc:TMF:a": "sub:TMF", "doc:TACL:b": "sub:TACL"}
EDGES = [{"src": "raj:h3", "dst": "evt:TMF-185"}, {"src": "raj:h3", "dst": "sub:TMF"}, {"src": "doc:TMF:a", "dst": "obj:audit"}]


def log(ts, q, system, cites, outcome="answer"):
    return {"ts": ts, "question": q, "outcome": outcome, "system": system, "citations": cites}


def test_users_filter_and_order():
    rows = [{"user_id": u, "questions": n, "last_seen": ""} for u, n in
            [("eval", 205), ("t", 17), ("conncheck", 3), ("Test", 2), (None, 1), ("cli", 12), ("newhire1", 31), ("ana", 4)]]
    assert [r["user_id"] for r in L.real_users(rows)] == ["newhire1", "ana"]


def test_map_coverage_veterans_gaps():
    logs = [log("2026-10-17 10:00", "tmf 185?", "sub:TMF", ["raj:h3", "doc:TMF:a"]),
            log("2026-10-17 09:00", "hello", "sub:TACL", [], "answer")]
    m = L.shape_map("newhire1", logs, ENTS, NOTES, DOCS, EDGES)
    tmf = next(s for s in m["subsystems"] if s["id"] == "sub:TMF")
    assert tmf["questions"] == 1 and tmf["sections_cited"] == 1
    assert tmf["notes"] == [{"id": "raj:h3", "owner": "Raj"}]
    assert (tmf["entities_touched"], tmf["entities_total"], tmf["coverage"]) == (2, 3, 0.67)  # evt 185 via note, obj via doc; sub edge ignored
    assert tmf["last_seen"] == "2026-10-17 10:00"
    t = m["totals"]
    assert (t["questions"], t["subsystems_touched"], t["notes_seen"], t["entities_total"], t["coverage"]) == (2, 1, 1, 4, 0.5)
    assert m["veterans"] == [{"id": "raj", "name": "Raj", "notes": 1}]
    assert m["gaps"]["subsystems"] == ["TACL"]  # asked a question there but cited nothing: not "touched"
    assert [e["id"] for e in m["gaps"]["events"]] == ["evt:TMF-187"]
    assert m["recent"][0]["subsystem"] == "TMF"


def test_empty_citations_and_recent_cap():
    logs = [log(f"t{i}", "q", "", None, "refer") for i in range(15)]
    m = L.shape_map("u", logs, ENTS, NOTES, DOCS, EDGES)
    assert m["totals"]["subsystems_touched"] == 0 and m["totals"]["coverage"] == 0.0
    assert len(m["recent"]) == 10 and m["recent"][0]["subsystem"] is None
    assert len(m["gaps"]["subsystems"]) == 2


def test_test_ids_are_not_operators():
    with pytest.raises(HTTPException) as e:
        L.learning("eval")
    assert e.value.status_code == 404
