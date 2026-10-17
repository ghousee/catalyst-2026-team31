"""Knowledge capture: a veteran adds a note, signs it, and the graph connects itself.

draft (POST /knowledge) -> owner signs (POST /knowledge/{id}/approve) -> approved = usable by /chat immediately.
On approve the code (never the LLM) auto-links: `about` edges to the graph entities the note's text names (same
subsystem only), `applies_to` the node(s), and +1 on the owner's `expert_in` weight for the subsystem. The veteran
then confirms which manual sections the note extends/contradicts (POST /knowledge/{id}/link, created_by = 'human').
"""
import re
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.graph.query import resolve
from backend.ingest import embedder
from backend.pipeline.answer import _rows, clean_title, connect
from backend.pipeline.retrieve import hybrid_search

LINKABLE = {"event", "object", "metric", "command", "component", "symptom", "alarm", "procedure"}
NODE_ID = {"PROD": "node:PROD", "DR": "node:DR", "ALL": None}
STATUSES = ("draft", "approved", "retired")


# ---------------------------------------------------------------- pure parts (unit-tested)
def next_note_id(owner, existing_ids):
    """'<owner>:hN' with N one above the owner's highest existing number."""
    nums = [int(m.group(1)) for i in existing_ids if (m := re.fullmatch(re.escape(owner) + r":h(\d+)", i))]
    return f"{owner}:h{max(nums, default=0) + 1}"


def captured_via(entered_by, owner):
    """The owner typed it themselves = interview; a colleague entered it for them = referral."""
    return "interview" if entered_by == owner else "referral"


def check_signer(owner, signed_by):
    """Only the owner may sign their note (nothing goes live unsigned, and nobody signs for someone else)."""
    if signed_by != owner:
        raise PermissionError(f"only {owner} can sign this note, not {signed_by}")


def autolink_edges(note_id, subsystem, node_ids, entities):
    """Edges (src, rel, dst) created when a note is approved. entities = graph entities named in the note's text:
    [{id, kind, parent_id}]. Only entities of the note's own subsystem are linked (a manual-wide alias like 'disk'
    in an SCF note must not link a TMF object). node_ids = the nodes the note applies to (all nodes -> both)."""
    out = [(note_id, "about", subsystem)]
    for e in entities:
        if e["kind"] in LINKABLE and e.get("parent_id") == subsystem:
            out.append((note_id, "about", e["id"]))
    out += [(note_id, "applies_to", n) for n in node_ids]
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- db helpers
def _note_row(conn, nid):
    rows = _rows(conn, "SELECT h.*, p.name AS owner_name FROM heuristic h JOIN person p ON p.id = h.owner_id "
                       "WHERE h.id = %s", (nid,))
    if not rows:
        raise HTTPException(404, f"unknown note {nid}")
    return rows[0]


def _view(h, links):
    node = "ALL" if h["site_id"] is None else h["site_id"].split(":", 1)[1]
    return {"id": h["id"], "owner_id": h["owner_id"], "owner_name": h["owner_name"], "entered_by": h["entered_by"],
            "kind": h["kind"], "trigger_text": h["trigger_text"], "call_text": h["call_text"],
            "why_text": h["why_text"] or "", "not_when_text": h["not_when_text"] or "", "node": node,
            "subsystem": h["system_id"], "status": h["status"], "captured_via": h["captured_via"],
            "captured_at": str(h["captured_at"] or ""), "signed_by": h["signed_by"],
            "signed_at": str(h["signed_at"] or ""), "needs_review": bool(h["needs_review"]), "links": links}


def _links(conn, ids):
    out = {i: [] for i in ids}
    if ids:
        for e in _rows(conn, "SELECT src, rel, dst, created_by FROM edge WHERE src = ANY(%s::text[]) "
                             "AND rel IN ('about', 'applies_to', 'extends', 'contradicts')", (list(ids),)):
            out[e["src"]].append({"rel": e["rel"], "dst": e["dst"], "created_by": e["created_by"]})
    return out


def approve_note(conn, nid, signed_by):
    """Sign a draft and wire it into the graph. Returns {note, auto_links, suggested_sections}."""
    h = _note_row(conn, nid)
    try:
        check_signer(h["owner_id"], signed_by)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    if h["status"] != "draft":
        raise HTTPException(409, f"note is {h['status']}, only a draft can be approved")
    body = f"{h['trigger_text']} {h['call_text']} {h['why_text'] or ''}"
    vec = embedder.embed([embedder.doc_text(h["trigger_text"][:80], body)], cpu=True)[0][0]
    today = date.today()
    conn.execute("UPDATE heuristic SET status = 'approved', signed_by = %s, signed_at = %s, last_validated = %s, "
                 "needs_review = FALSE, embedding = %s::vector WHERE id = %s",
                 (signed_by, today, today, "[" + ",".join(map(str, vec)) + "]", nid))
    sub = h["system_id"]
    named = resolve(conn, f"{h['trigger_text']} {h['call_text']}", {"system": sub})["entities"]
    ents = _rows(conn, "SELECT id, kind, parent_id FROM entity WHERE id = ANY(%s::text[])", ([e["id"] for e in named],))
    nodes = [h["site_id"]] if h["site_id"] else [r["id"] for r in _rows(conn, "SELECT id FROM entity WHERE kind = 'site'")]
    edges = autolink_edges(nid, sub, nodes, ents)
    for src, rel, dst in edges:
        conn.execute("INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,%s,%s,1,%s,'auto') "
                     "ON CONFLICT (src, rel, dst) DO NOTHING", (src, rel, dst, nid))
    conn.execute("INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,'expert_in',%s,1,%s,'auto') "
                 "ON CONFLICT (src, rel, dst) DO UPDATE SET weight = edge.weight + 1", (h["owner_id"], sub, nid))
    qtext = f"{h['trigger_text']} {h['call_text']}"
    hits = hybrid_search(conn, qtext, embedder.embed_query(qtext), {"system": sub, "version": None, "site": None}, k=3)
    conn.commit()
    return {"note": _view(_note_row(conn, nid), _links(conn, [nid])[nid]),
            "auto_links": [{"rel": rel, "dst": dst} for _, rel, dst in edges] +
                          [{"rel": "expert_in", "dst": sub, "src": h["owner_id"]}],
            "suggested_sections": [{"id": r["id"], "section": clean_title(r["section"]), "snippet": r["text"][:200]}
                                   for r in hits]}


# ---------------------------------------------------------------- routes
router = APIRouter()


class KnowledgeIn(BaseModel):
    owner_id: str
    entered_by: str
    kind: str = "note"
    trigger_text: str
    call_text: str
    why_text: str = ""
    not_when_text: str = ""
    node: str = "ALL"
    subsystem: str


class SignIn(BaseModel):
    signed_by: str


class LinkIn(BaseModel):
    doc_id: str
    rel: str


@router.get("/persons")
def persons():
    with connect() as conn:
        rows = _rows(conn, "SELECT id, name, role, team, years, expertise, availability, active FROM person ORDER BY name")
    return [{**r, "expertise": list(r["expertise"] or [])} for r in rows]


@router.get("/knowledge")
def list_knowledge(status: str | None = None):
    if status is not None and status not in STATUSES:
        raise HTTPException(400, f"status must be one of {', '.join(STATUSES)}")
    with connect() as conn:
        rows = _rows(conn, "SELECT h.*, p.name AS owner_name FROM heuristic h JOIN person p ON p.id = h.owner_id "
                           "WHERE (%s::text IS NULL OR h.status = %s) ORDER BY h.captured_at DESC NULLS LAST, h.id",
                     (status, status))
        links = _links(conn, [r["id"] for r in rows])
    return [_view(r, links[r["id"]]) for r in rows]


@router.post("/knowledge")
def create_knowledge(body: KnowledgeIn):
    if body.kind not in ("note", "warning_pattern"):
        raise HTTPException(422, "kind must be note or warning_pattern")
    if body.node not in NODE_ID:
        raise HTTPException(422, "node must be PROD, DR or ALL")
    if not body.trigger_text.strip() or not body.call_text.strip():
        raise HTTPException(422, "trigger_text and call_text are required")
    with connect() as conn:
        people = {r["id"] for r in _rows(conn, "SELECT id FROM person")}
        for who in (body.owner_id, body.entered_by):
            if who not in people:
                raise HTTPException(404, f"unknown person {who}")
        if not _rows(conn, "SELECT 1 FROM entity WHERE id = %s AND kind = 'system'", (body.subsystem,)):
            raise HTTPException(422, f"unknown subsystem {body.subsystem}")
        nid = next_note_id(body.owner_id, [r["id"] for r in _rows(
            conn, "SELECT id FROM heuristic WHERE owner_id = %s", (body.owner_id,))])
        via, today, site = captured_via(body.entered_by, body.owner_id), date.today(), NODE_ID[body.node]
        prov = f"{via}:{today}" if via == "interview" else f"referral:{body.entered_by}"
        conn.execute(
            "INSERT INTO heuristic (id, owner_id, trigger_text, call_text, why_text, not_when_text, system_id, version_id, "
            "site_id, all_versions, all_sites, provenance, status, kind, captured_via, captured_at, entered_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s,TRUE,%s,%s,'draft',%s,%s,%s,%s)",
            (nid, body.owner_id, body.trigger_text.strip(), body.call_text.strip(), body.why_text.strip(),
             body.not_when_text.strip(), body.subsystem, site, site is None, prov, body.kind, via, today, body.entered_by))
        conn.commit()
        return _view(_note_row(conn, nid), [])


@router.post("/knowledge/{nid}/approve")
def approve(nid: str, body: SignIn):
    with connect() as conn:
        return approve_note(conn, nid, body.signed_by)


@router.post("/knowledge/{nid}/link")
def link(nid: str, body: LinkIn):
    if body.rel not in ("extends", "contradicts"):
        raise HTTPException(422, "rel must be extends or contradicts")
    with connect() as conn:
        h = _note_row(conn, nid)
        if h["status"] != "approved":
            raise HTTPException(409, "only an approved note can be linked to the manual")
        if not _rows(conn, "SELECT 1 FROM doc_chunk WHERE id = %s", (body.doc_id,)):
            raise HTTPException(404, f"unknown manual section {body.doc_id}")
        conn.execute("INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,%s,%s,1,%s,'human') "
                     "ON CONFLICT (src, rel, dst) DO NOTHING", (nid, body.rel, body.doc_id, nid))
        conn.commit()
        return _view(h, _links(conn, [nid])[nid])


@router.post("/knowledge/{nid}/retire")
def retire(nid: str):
    with connect() as conn:
        h = _note_row(conn, nid)
        conn.execute("UPDATE heuristic SET status = 'retired' WHERE id = %s", (nid,))
        conn.commit()
        return _view({**h, "status": "retired"}, _links(conn, [nid])[nid])
