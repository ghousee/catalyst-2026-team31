"""Learning map: what an operator has encountered through /chat (answer_log), per subsystem.
Not a test of knowledge. `shape_map` and `real_users` are pure (unit-tested); the routes only run simple queries."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.pipeline.answer import _rows, connect

TEST_USERS = {"eval", "conncheck", "check", "t", "test", "cli"}  # scripts and checks, not operators
RECENT_N = 10
CONTAINERS = ("sub:", "node:", "rvu:")  # `about` targets that are not entities inside a subsystem


def real_users(rows):
    """rows [{user_id, questions, last_seen}] -> operators only, most questions first."""
    keep = [r for r in rows if r["user_id"] and r["user_id"].strip().lower() not in TEST_USERS]
    return sorted(keep, key=lambda r: (-r["questions"], r["user_id"]))


def shape_map(user_id, logs, entities, notes, docs, edges):
    """logs [{ts,question,outcome,system,citations}] (newest first), entities [{id,kind,name,parent_id}] (subsystems have
    kind 'system'), notes {id: {system_id, owner_id, owner_name}}, docs {id: system_id}, edges [{src,dst}] (rel 'about')."""
    subs = {e["id"]: e for e in entities if e["kind"] == "system"}
    members = {s: [e for e in entities if e["parent_id"] == s] for s in subs}
    parent = {e["id"]: e["parent_id"] for e in entities if e["parent_id"] in subs}
    about = {}
    for e in edges:
        about.setdefault(e["src"], set()).add(e["dst"])

    rows = {s: {"questions": 0, "sections": set(), "notes": {}, "entities": set(), "last": None} for s in subs}
    seen_notes = {}
    for lg in logs:  # newest first, so the first ts seen for a subsystem is its last_seen
        def mark(sub):
            if sub in rows and rows[sub]["last"] is None:
                rows[sub]["last"] = lg["ts"]
        if lg["system"] in rows:
            rows[lg["system"]]["questions"] += 1
        for cid in lg["citations"] or []:
            if cid in docs:
                sub = docs[cid]
                if sub in rows:
                    rows[sub]["sections"].add(cid)
                    mark(sub)
            elif cid in notes:
                n = notes[cid]
                seen_notes[cid] = n
                if n["system_id"] in rows:
                    rows[n["system_id"]]["notes"][cid] = n["owner_name"]
                    mark(n["system_id"])
            else:
                continue
            for dst in about.get(cid, ()):
                if dst in parent:
                    rows[parent[dst]]["entities"].add(dst)

    out = []
    for s, r in rows.items():
        total = len(members[s])
        touched = len(r["entities"])
        out.append({"id": s, "name": subs[s]["name"], "questions": r["questions"], "sections_cited": len(r["sections"]),
                    "notes": [{"id": i, "owner": o} for i, o in sorted(r["notes"].items())],
                    "entities_touched": touched, "entities_total": total,
                    "coverage": round(touched / total, 2) if total else 0.0, "last_seen": r["last"]})
    out.sort(key=lambda x: (-(x["sections_cited"] + len(x["notes"]) + x["questions"]), x["id"]))

    touched_ids = {i for r in rows.values() for i in r["entities"]}
    total_ents = sum(len(m) for m in members.values())
    active = [x for x in out if x["sections_cited"] or x["notes"]]
    vets = {}
    for n in seen_notes.values():
        v = vets.setdefault(n["owner_id"], {"id": n["owner_id"], "name": n["owner_name"], "notes": 0})
        v["notes"] += 1
    return {
        "user_id": user_id,
        "totals": {"questions": len(logs), "subsystems_touched": len(active), "subsystems_total": len(subs),
                   "notes_seen": len(seen_notes), "sections_cited": sum(x["sections_cited"] for x in out),
                   "entities_touched": len(touched_ids), "entities_total": total_ents,
                   "coverage": round(len(touched_ids) / total_ents, 2) if total_ents else 0.0},
        "subsystems": out,
        "veterans": sorted(vets.values(), key=lambda v: (-v["notes"], v["name"])),
        "gaps": {"subsystems": [x["name"] for x in out if x not in active],
                 "events": [{"id": e["id"], "name": e["name"], "subsystem": subs[e["parent_id"]]["name"]}
                            for e in entities if e["kind"] == "event" and e["parent_id"] in subs and e["id"] not in touched_ids]},
        "recent": [{"ts": lg["ts"], "question": lg["question"], "outcome": lg["outcome"],
                    "subsystem": subs[lg["system"]]["name"] if lg["system"] in subs else None} for lg in logs[:RECENT_N]],
    }


LEVELS = ("new", "some", "confident")


def check_levels(levels, known_subsystems):
    """{sub_id: level} from the UI -> list of (sub_id, level); raises ValueError on an unknown subsystem or level."""
    out = []
    for sub, level in levels.items():
        if sub not in known_subsystems:
            raise ValueError(f"unknown subsystem {sub}")
        if level not in LEVELS:
            raise ValueError(f"level must be one of {', '.join(LEVELS)}")
        out.append((sub, level))
    return out


router = APIRouter()


class LevelsIn(BaseModel):
    levels: dict[str, str]


def _check_user(user_id):
    if not user_id.strip() or user_id.strip().lower() in TEST_USERS:
        raise HTTPException(404, "not an operator id")


@router.get("/learning/users")
def learning_users():
    with connect() as conn:
        rows = _rows(conn, "SELECT user_id, count(*) FILTER (WHERE q) AS questions, max(ts)::text AS last_seen FROM ("
                           "  SELECT user_id, ts, TRUE AS q FROM answer_log"
                           "  UNION ALL SELECT user_id, set_at, FALSE FROM self_level) x GROUP BY user_id")
    return real_users(rows)


@router.put("/learning/{user_id}/self")
def set_self_levels(user_id: str, body: LevelsIn):
    """A junior's own starting level per subsystem (self-reported; never used to answer)."""
    _check_user(user_id)
    with connect() as conn:
        subs = {r["id"] for r in _rows(conn, "SELECT id FROM entity WHERE kind = 'system'")}
        try:
            rows = check_levels(body.levels, subs)
        except ValueError as e:
            raise HTTPException(422, str(e))
        for sub, level in rows:
            conn.execute("INSERT INTO self_level (user_id, system_id, level) VALUES (%s,%s,%s) ON CONFLICT (user_id, system_id) "
                         "DO UPDATE SET level = EXCLUDED.level, set_at = now()", (user_id, sub, level))
        conn.commit()
    return learning(user_id)


@router.get("/learning/{user_id}")
def learning(user_id: str):
    """Always returns a map for an operator id; a brand-new junior gets an empty one (0 questions)."""
    _check_user(user_id)
    with connect() as conn:
        logs = _rows(conn, "SELECT ts::text AS ts, question, outcome, context->>'system' AS system, citations "
                           "FROM answer_log WHERE user_id = %s ORDER BY ts DESC, id DESC", (user_id,))
        levels = {r["system_id"]: r["level"] for r in _rows(
            conn, "SELECT system_id, level FROM self_level WHERE user_id = %s", (user_id,))}
        ids = sorted({c for lg in logs for c in lg["citations"] or []})
        ents = _rows(conn, "SELECT id, kind, name, parent_id FROM entity WHERE kind = 'system' OR parent_id IS NOT NULL ORDER BY id")
        notes = {r["id"]: r for r in _rows(
            conn, "SELECT h.id, h.system_id, h.owner_id, p.name AS owner_name FROM heuristic h "
                  "JOIN person p ON p.id = h.owner_id WHERE h.id = ANY(%s)", (ids,))}
        docs = {r["id"]: r["system_id"] for r in _rows(conn, "SELECT id, system_id FROM doc_chunk WHERE id = ANY(%s)", (ids,))}
        edges = _rows(conn, "SELECT src, dst FROM edge WHERE rel = 'about' AND src = ANY(%s)", (ids,))
    return {**shape_map(user_id, logs, ents, notes, docs, edges), "self_levels": levels}
