"""Knowledge capture: a veteran adds a note, signs it, and the graph connects itself.

draft (POST /knowledge) -> owner signs (POST /knowledge/{id}/approve) -> approved = usable by /chat immediately.
On approve the code (never the LLM) auto-links: `about` edges to the graph entities the note's text names (same
subsystem only), `applies_to` the node(s), and +1 on the owner's `expert_in` weight for the subsystem. The veteran
then confirms which manual sections the note extends/contradicts (POST /knowledge/{id}/link, created_by = 'human').
"""
import json
import re
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.graph.query import resolve
from backend.ingest import embedder
from backend.pipeline import llm
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


# ---------------------------------------------------------------- teach chat (a veteran talks, the assistant drafts)
MAX_FOLLOWUPS = 3
FIELDS = ("trigger_text", "call_text", "why_text", "not_when_text")
TEACH_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["ask", "draft"]},
        "question": {"type": "string"},
        "trigger_text": {"type": "string"}, "call_text": {"type": "string"},
        "why_text": {"type": "string"}, "not_when_text": {"type": "string"},
        "node": {"type": "string", "enum": ["PROD", "DR", "ALL", "unknown"]},
        "subsystem": {"type": "string"},
        "kind": {"type": "string", "enum": ["note", "warning_pattern"]},
    },
    "required": ["action", "question", "trigger_text", "call_text", "why_text", "not_when_text", "node", "subsystem", "kind"],
}
TEACH_PROMPT = """You help a senior HPE NonStop operator write down what they know as a short knowledge note.
Fields: trigger_text (when it happens), call_text (what to do), why_text (why), not_when_text (when it does NOT apply),
node (PROD, DR, ALL or unknown), subsystem (one id from the list), kind (warning_pattern if it warns of a coming failure, else note).
Rules:
- Use ONLY what the operator said, in their own words. Never invent or guess a fact. Leave a field "" if they did not say it.
- If trigger_text, call_text, node or subsystem is still missing, or something important is unclear, answer action "ask" with ONE short
  question about the single most important gap (when it happens / what to do / why / when it does NOT apply / which node).
- IMPORTANT: while why_text or not_when_text is still empty and the Assistant has not yet asked about it in the conversation,
  action MUST be "ask" (ask about why first, then about when it does NOT apply). If the operator already answered or said there is
  nothing to add, do not ask again.
- Otherwise answer action "draft" and fill the fields. why_text and not_when_text may stay "" if never mentioned.
- Questions are plain words for the operator (never ids). Pick the subsystem yourself from the commands/objects they name; ask only if unsure.
- Do not ask about something the operator already answered.
Subsystems:
{subs}"""
_STOP = {"the", "and", "for", "that", "this", "with", "you", "are", "was", "not", "but", "its", "has", "have", "when",
         "then", "than", "from", "into", "will", "can", "all", "any", "does", "doesn"}


def teach_schema(sub_ids):
    """TEACH_SCHEMA with the subsystem limited to real ids (constrained decoding), or 'unknown'."""
    props = {**TEACH_SCHEMA["properties"], "subsystem": {"type": "string", "enum": [*sorted(sub_ids), "unknown"]}}
    return {**TEACH_SCHEMA, "properties": props}


def _words(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in _STOP}


def grounded(text, said):
    """True when most of the text's words were actually said by the veteran (the LLM may rephrase, not invent)."""
    w = _words(text)
    return not w or len(w & _words(said)) / len(w) >= 0.6


def shape_turn(raw, said, subs, followups, node_hint=None, subsystem_hint=None):
    """Turn one raw LLM answer into {"type": "question"|"draft", ...}. All safety lives here: every text field must be
    grounded in what the veteran said (else emptied), the subsystem must be a known id, and after MAX_FOLLOWUPS questions
    we draft with what we have (a missing subsystem/node is then left for the editable form)."""
    can_ask = followups < MAX_FOLLOWUPS
    d = {f: (raw.get(f) or "").strip() if grounded(raw.get(f) or "", said) else "" for f in FIELDS}
    sub = raw.get("subsystem") if raw.get("subsystem") in subs else subsystem_hint if subsystem_hint in subs else ""
    node = raw.get("node") if raw.get("node") in NODE_ID else node_hint if node_hint in NODE_ID else ""
    missing = [m for m, ok in (("when it happens", d["trigger_text"]), ("what to do", d["call_text"]),
                               ("which node", node), ("which subsystem", sub)) if not ok]
    if can_ask and (raw.get("action") == "ask" or missing):
        q = (raw.get("question") or "").strip()
        return {"type": "question", "text": q if raw.get("action") == "ask" and q else f"Can you tell me {missing[0]}?"}
    if not d["trigger_text"] or not d["call_text"]:  # nothing usable to save: keep asking
        return {"type": "question", "text": "Can you tell me when it happens and what to do?"}
    kind = raw.get("kind") if raw.get("kind") in ("note", "warning_pattern") else "note"
    return {"type": "draft", "draft": {**d, "node": node or "ALL", "subsystem": sub, "kind": kind}}


class TeachMsg(BaseModel):
    role: str
    text: str


class TeachIn(BaseModel):
    owner_id: str
    messages: list[TeachMsg]
    node_hint: str | None = None
    subsystem_hint: str | None = None


@router.post("/knowledge/teach")
def teach(body: TeachIn):
    said = " ".join(m.text for m in body.messages if m.role == "veteran")
    if not said.strip():
        raise HTTPException(422, "say something first")
    followups = sum(m.role == "assistant" for m in body.messages)
    with connect() as conn:
        if not _rows(conn, "SELECT 1 FROM person WHERE id = %s", (body.owner_id,)):
            raise HTTPException(404, f"unknown person {body.owner_id}")
        subs = _rows(conn, "SELECT id, name FROM entity WHERE kind = 'system' ORDER BY id")
    ids = {s["id"] for s in subs}
    convo = "\n".join(f"{'Operator' if m.role == 'veteran' else 'Assistant'}: {m.text}" for m in body.messages)
    hints = "".join(f"\nHint: {k} = {v}" for k, v in (("node", body.node_hint), ("subsystem", body.subsystem_hint)) if v)
    forced = '\nYou have asked enough questions: answer action "draft".' if followups >= MAX_FOLLOWUPS else ""
    sys_prompt = TEACH_PROMPT.format(subs="\n".join(f"{s['id']} ({s['name']})" for s in subs))
    r = llm.chat([{"role": "system", "content": sys_prompt}, {"role": "user", "content": convo + hints + forced}],
                 schema=teach_schema(ids), max_tokens=500)
    try:
        raw = json.loads(r["content"])
    except ValueError:
        raise HTTPException(502, "the model returned something unreadable, try again")
    return shape_turn(raw, said, ids, followups, body.node_hint, body.subsystem_hint)
