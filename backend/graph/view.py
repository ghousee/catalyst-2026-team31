"""GET /graph: a read-only snapshot of the live knowledge graph for the UI's "Knowledge graph" page.
`shape_graph` is pure (unit-tested); the route only runs the queries."""
from fastapi import APIRouter

from backend.pipeline.answer import _rows, connect

LINK_CAP = 500
NOTE_CAP = 200
RECENT_N = 20


def _count(items):
    out = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items()))


def recent_changes(notes, links, docs, n=RECENT_N):
    """Newest first. Edges have no timestamp, so auto/human links are shown through the note that justified them."""
    ev = []
    by_id = {x["id"]: x for x in notes}
    for x in notes:
        if x["status"] == "approved" and x["signed_at"]:
            ev.append({"ts": x["signed_at"], "type": "note_signed", "text": f"{x['owner_name']} signed {x['id']}"})
        elif x["status"] == "draft" and x["captured_at"]:
            ev.append({"ts": x["captured_at"], "type": "note_drafted", "text": f"{x['owner_name']} drafted {x['id']} (awaiting sign-off)"})
    per_note = {}
    for e in links:
        if e["created_by"] in ("auto", "human") and e["source_id"] in by_id:
            per_note.setdefault((e["source_id"], e["created_by"]), []).append(e["rel"])
    for (nid, who), rels in per_note.items():
        n_ = by_id[nid]
        ev.append({"ts": n_["signed_at"] or n_["captured_at"], "type": f"links_{who}",
                   "text": f"{len(rels)} {who} link(s) for {nid}: {', '.join(sorted(set(rels)))}"})
    for d in docs:
        if d["last_loaded"]:
            ev.append({"ts": d["last_loaded"], "type": "document_loaded", "text": f"{d['title']}: {d['chunks']} section(s)"})
    ev.sort(key=lambda e: e["ts"], reverse=True)
    return ev[:n]


def shape_graph(entities, edges, notes, persons, docs, link_cap=LINK_CAP):
    """entities [{id,kind,name,aliases}], edges [{src,rel,dst,source_id,created_by}], notes [{id,owner_name,kind,
    scope,status,needs_review,signed_at,captured_at,call_text}], persons = int, docs [{title,chunks,last_loaded}]."""
    touch = {}
    for e in edges:
        for end in (e["src"], e["dst"]):
            touch[end] = touch.get(end, 0) + 1
    ents = [{"id": x["id"], "kind": x["kind"], "name": x["name"], "aliases": list(x["aliases"] or []),
             "links": touch.get(x["id"], 0)} for x in entities]
    ordered = sorted(edges, key=lambda e: e["created_by"] == "seed")  # auto/human (the growing part) first; stable
    links = [{k: e[k] for k in ("src", "rel", "dst", "source_id", "created_by")} for e in ordered[:link_cap]]
    return {
        "counts": {
            "entities": _count(x["kind"] for x in entities),
            "links": _count(e["rel"] for e in edges),
            "persons": persons,
            "notes": {**{s: 0 for s in ("approved", "draft", "retired")}, **_count(x["status"] for x in notes),
                      "needs_review": sum(1 for x in notes if x["needs_review"])},
            "doc_sections": sum(d["chunks"] for d in docs),
            "documents": len(docs),
        },
        "entities": ents,
        "links": links,
        "links_total": len(edges),
        "notes": [{k: x[k] for k in ("id", "owner_name", "kind", "scope", "status", "needs_review", "signed_at", "call_text")}
                  for x in notes[:NOTE_CAP]],
        "recent": recent_changes(notes, edges, docs),
    }


router = APIRouter()


@router.get("/graph")
def graph():
    with connect() as conn:
        ents = _rows(conn, "SELECT id, kind, name, aliases FROM entity ORDER BY kind, id")
        edges = _rows(conn, "SELECT src, rel, dst, source_id, created_by FROM edge")
        persons = _rows(conn, "SELECT count(*) AS n FROM person")[0]["n"]
        raw = _rows(conn, "SELECT h.id, p.name AS owner_name, h.kind, h.system_id, h.site_id, h.status, h.needs_review, "
                          "h.signed_at, h.captured_at, h.call_text FROM heuristic h JOIN person p ON p.id = h.owner_id "
                          "ORDER BY h.signed_at DESC NULLS LAST, h.captured_at DESC NULLS LAST, h.id")
        docs = _rows(conn, """
            SELECT max(split_part(edition, ',', 1)) AS title,
                   count(*) FILTER (WHERE valid_to IS NULL OR valid_to > CURRENT_DATE) AS chunks,
                   coalesce(max(loaded_at)::text, max(valid_from)::text) AS last_loaded
            FROM doc_chunk GROUP BY split_part(id, ':', 2)""")
    notes = [{"id": r["id"], "owner_name": r["owner_name"], "kind": r["kind"],
              "scope": f"{r['system_id'].replace('sub:', '')} / {r['site_id'].replace('node:', '') if r['site_id'] else 'all nodes'}",
              "status": r["status"], "needs_review": bool(r["needs_review"]), "signed_at": str(r["signed_at"] or ""),
              "captured_at": str(r["captured_at"] or ""), "call_text": r["call_text"]} for r in raw]
    return shape_graph(ents, edges, notes, persons, docs)
