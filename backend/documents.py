"""Add or update a manual without a developer: POST /documents (.pdf or .txt) -> chunk, embed, diff against what is loaded.

Same key (the title, non-alphanumerics -> '-') = same document: unchanged chunks keep their id, changed ones are replaced in
place, vanished ones get valid_to = today (retrieval excludes valid_to <= today). Approved notes linked to a changed or
removed chunk get needs_review = TRUE (answers still show them, flagged). New chunks get `mentions` edges to the entities
whose names/aliases they contain. A subsystem name the graph does not know creates a 'system' entity.
"""
import hashlib
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend import settings
from backend.graph.query import _entities, tokens
from backend.ingest import embedder
from backend.ingest.chunker import MAX_TOKENS, TARGET_TOKENS, Chunk, chunk_manual, est_tokens, slugify
from backend.pipeline import retrieve
from backend.pipeline.answer import _rows, connect

UPLOADS = settings.ROOT / "data" / "raw" / "uploads"
MIN_COVERAGE = 0.6  # the HPE-layout chunker is trusted only if its chunks cover this share of the text


# ---------------------------------------------------------------- pure parts (unit-tested)
def doc_key(title):
    return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def diff_chunks(old, new):
    """old / new = {chunk id: content hash} (old = currently valid chunks of the document). Unchanged ids keep their row."""
    return {"added": sorted(set(new) - set(old)),
            "changed": sorted(i for i in new if i in old and new[i] != old[i]),
            "unchanged": sorted(i for i in new if i in old and new[i] == old[i]),
            "removed": sorted(set(old) - set(new))}


def _is_heading(p):
    return "\n" not in p and len(p) <= 70 and not p.endswith((".", ",", ";", ":"))


def generic_chunks(text, key):
    """Layout-free chunker for non-HPE text: a short single line without final punctuation starts a section; sections
    over MAX_TOKENS are split on paragraph boundaries. Ids are doc:<key>:<heading slug> (stable across re-uploads)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\f", "\n\n")) if p.strip()]
    sections, title, body = [], None, []

    def flush():
        if body:
            sections.append((title or "Introduction", list(body)))
        body.clear()
    for p in paras:
        if _is_heading(p):
            flush()
            title = p
        else:
            body.append(p)
    flush()
    out, used = [], {}
    for sec, ps in sections:
        parts, cur = [], []
        for p in ps:
            if cur and est_tokens("\n\n".join(cur + [p])) > TARGET_TOKENS and est_tokens("\n\n".join(cur)) >= MAX_TOKENS // 4:
                parts.append(cur)
                cur = []
            cur.append(p)
        parts.append(cur)
        for k, part in enumerate(parts):
            name = sec if k == 0 else f"{sec} (part {k + 1})"
            slug = slugify(name)
            used[slug] = used.get(slug, 0) + 1
            if used[slug] > 1:
                slug = f"{slug}-{used[slug]}"
            body_text = f"{sec}\n\n" + "\n\n".join(part)
            out.append(Chunk(f"doc:{key}:{slug}", key, name, body_text, 0, est_tokens(body_text)))
    return out


def chunk_text(text, key):
    """The HPE-manual chunker when it understands the layout (covers most of the text), else the generic one."""
    try:
        hpe = chunk_manual(text, key)
    except Exception:  # an arbitrary document can break the manual heuristics; fall back instead of failing
        hpe = []
    if hpe and sum(len(c.text) for c in hpe) >= MIN_COVERAGE * len(text.strip()):
        return hpe
    return generic_chunks(text, key)


def alias_tokens(entities, system_id):
    """[(entity id, token tuple)] for every name/alias of the entities a chunk may mention: not nodes/series, and a
    subsystem entity only for the document's own subsystem."""
    out = []
    for e in entities:
        if e["kind"] in ("site", "version") or (e["kind"] == "system" and e["id"] != system_id):
            continue
        for a in [e["name"], *e["aliases"]]:
            t = tuple(tokens(a))
            if t:
                out.append((e["id"], t))
    return out


def mentioned(alias_toks, text):
    """Entity ids whose name/alias occurs in the text (same tokenisation as graph.resolve)."""
    toks = tokens(text)
    grams = {}
    found = []
    for eid, a in alias_toks:
        n = len(a)
        if n not in grams:
            grams[n] = {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}
        if a in grams[n] and eid not in found:
            found.append(eid)
    return found


# ---------------------------------------------------------------- db
def resolve_subsystem(conn, value):
    """(subsystem entity id, created?) for a typed id / name / alias; an unknown name creates a 'system' entity."""
    v = value.strip()
    if not v:
        raise HTTPException(422, "subsystem is required")
    rows = _rows(conn, "SELECT id FROM entity WHERE kind = 'system' AND (id = %s OR lower(name) = lower(%s) OR EXISTS "
                       "(SELECT 1 FROM unnest(aliases) a WHERE lower(a) = lower(%s))) ORDER BY id", (v, v, v))
    if rows:
        return rows[0]["id"], False
    sid = "sub:" + re.sub(r"[^A-Za-z0-9]+", "-", v).strip("-").upper()
    conn.execute("INSERT INTO entity (id, kind, name, aliases) VALUES (%s, 'system', %s, %s) ON CONFLICT DO NOTHING",
                 (sid, v, [v]))
    return sid, True


def _vec(v):
    return "[" + ",".join(map(str, v)) + "]"


def load_document(conn, title, system_id, edition, text, source_file, embed=None):
    """Chunk, diff and load one document; returns the diff summary. Caller commits."""
    key, today = doc_key(title), date.today()
    chunks = chunk_text(text, key)
    if not chunks:
        raise HTTPException(422, "no text could be extracted from the document")
    new = {c.id: content_hash(c.text) for c in chunks}
    old = dict(conn.execute("SELECT id, content_hash FROM doc_chunk WHERE id LIKE %s "
                            "AND (valid_to IS NULL OR valid_to > CURRENT_DATE)", (f"doc:{key}:%",)).fetchall())
    d = diff_chunks(old, new)
    todo = [c for c in chunks if c.id in set(d["added"] + d["changed"])]
    vecs = (embed or (lambda t: embedder.embed(t, cpu=True)[0]))([embedder.doc_text(c.section, c.text) for c in todo]) if todo else []
    label = f"{title}, edition {edition}"
    for c, v in zip(todo, vecs):
        conn.execute(
            """INSERT INTO doc_chunk (id, source_file, section, text, system_id, version_id, site_id, all_versions, all_sites,
                                      valid_from, valid_to, embedding, edition, doc_version, content_hash, loaded_at)
               VALUES (%s,%s,%s,%s,%s,NULL,NULL,TRUE,TRUE,%s,NULL,%s::vector,%s,%s,%s, now())
               ON CONFLICT (id) DO UPDATE SET source_file = EXCLUDED.source_file, section = EXCLUDED.section,
                 text = EXCLUDED.text, system_id = EXCLUDED.system_id, valid_from = EXCLUDED.valid_from, valid_to = NULL,
                 embedding = EXCLUDED.embedding, edition = EXCLUDED.edition, doc_version = EXCLUDED.doc_version,
                 content_hash = EXCLUDED.content_hash, loaded_at = EXCLUDED.loaded_at""",
            (c.id, source_file, c.section, c.text, system_id, today, _vec(v), label, edition, new[c.id]))
    if d["removed"]:
        conn.execute("UPDATE doc_chunk SET valid_to = %s WHERE id = ANY(%s::text[])", (today, d["removed"]))
    redo = d["added"] + d["changed"] + d["removed"]
    conn.execute("DELETE FROM edge WHERE src = ANY(%s::text[]) AND rel = 'mentions' AND created_by = 'auto'", (redo,))
    aliases = alias_tokens(_entities(conn), system_id)
    for c in todo:
        for eid in mentioned(aliases, c.text):
            conn.execute("INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,'mentions',%s,1,%s,'auto') "
                         "ON CONFLICT (src, rel, dst) DO NOTHING", (c.id, eid, c.id))
    flagged = flag_notes(conn, d["changed"] + d["removed"])
    retrieve._df_cache.clear()  # keyword idf cache would otherwise ignore terms that only the new text contains
    return {"key": key, "title": title, "edition": edition, "subsystem": system_id,
            "added": len(d["added"]), "changed": len(d["changed"]), "unchanged": len(d["unchanged"]),
            "removed": len(d["removed"]), "changed_ids": d["changed"], "removed_ids": d["removed"], "notes_flagged": flagged}


def flag_notes(conn, chunk_ids):
    """needs_review = TRUE on approved notes linked to these chunks (edge src, dst or source_id). Returns the note ids."""
    if not chunk_ids:
        return []
    ids = set()
    for e in _rows(conn, "SELECT src, dst, source_id FROM edge WHERE src = ANY(%s::text[]) OR dst = ANY(%s::text[]) OR source_id = ANY(%s::text[])",
                   (chunk_ids, chunk_ids, chunk_ids)):
        ids.update(x for x in (e["src"], e["dst"], e["source_id"]) if x)
    if not ids:
        return []
    return sorted(r[0] for r in conn.execute(
        "UPDATE heuristic SET needs_review = TRUE WHERE id = ANY(%s::text[]) AND status = 'approved' RETURNING id", (list(ids),)))


def extract_text(path, ext):
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\f".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- routes
router = APIRouter()


@router.post("/documents")
def upload(file: UploadFile = File(...), title: str = Form(...), subsystem: str = Form(...), edition: str = Form("")):
    ext = ("." + (file.filename or "").rsplit(".", 1)[-1].lower()) if "." in (file.filename or "") else ""
    if ext not in (".pdf", ".txt"):
        raise HTTPException(422, "only .pdf and .txt files are accepted")
    key = doc_key(title)
    if not key:
        raise HTTPException(422, "title is required")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    path = UPLOADS / f"{key}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}{ext}"
    path.write_bytes(file.file.read())
    try:
        text = extract_text(path, ext)
    except Exception as e:
        raise HTTPException(422, f"could not read the file: {e}")
    if not text.strip():
        raise HTTPException(422, "the file has no extractable text")
    with connect() as conn:
        system_id, created = resolve_subsystem(conn, subsystem)
        out = load_document(conn, title.strip(), system_id, edition.strip() or f"uploaded {date.today()}", text,
                            str(path.relative_to(settings.ROOT)).replace("\\", "/"))
        conn.commit()
    return {**out, "subsystem_created": created}


@router.get("/documents")
def documents():
    with connect() as conn:
        rows = _rows(conn, """
            SELECT split_part(id, ':', 2) AS key, max(split_part(edition, ',', 1)) AS title, max(doc_version) AS edition,
                   max(system_id) AS subsystem,
                   count(*) FILTER (WHERE valid_to IS NULL OR valid_to > CURRENT_DATE) AS chunks,
                   count(*) FILTER (WHERE valid_to IS NOT NULL AND valid_to <= CURRENT_DATE) AS removed,
                   coalesce(max(loaded_at)::text, max(valid_from)::text) AS last_loaded
            FROM doc_chunk GROUP BY 1 ORDER BY 1""")
    return rows
