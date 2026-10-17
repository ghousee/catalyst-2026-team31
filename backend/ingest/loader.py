"""Load chunked manuals into Postgres (entities + doc_chunk) with embeddings.

    python -m backend.ingest.loader [--manual TMF-Reference ...] [--no-embed] [--cpu]

Idempotent per manual: deletes that manual's doc_chunk rows (id prefix 'doc:<manual>:') then re-inserts.
Docs are tagged all_sites = true (site_id NULL), version_id per manuals.py, all_versions = false.
"""
import argparse
import time

import psycopg
from pgvector.psycopg import register_vector

from backend import settings
from backend.ingest import embedder
from backend.ingest.chunker import chunk_manual
from backend.ingest.manuals import BY_KEY, MANUALS, SITE_ENTITIES, VERSION_ENTITIES


def read_text(manual_key):
    p = settings.RAW_HPE_DIR / f"{manual_key}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    pdf = p.with_suffix(".pdf")  # fallback: extract with pypdf (pages joined by form feed)
    from pypdf import PdfReader
    return "\f".join((pg.extract_text() or "") for pg in PdfReader(str(pdf)).pages)


def ensure_entities(conn):
    with conn.cursor() as cur:
        for m in MANUALS:
            cur.execute("INSERT INTO entity (id, kind, name) VALUES (%s,'system',%s) ON CONFLICT DO NOTHING",
                        (m.system_id, m.system_name))
        for eid, name in VERSION_ENTITIES:
            cur.execute("INSERT INTO entity (id, kind, name) VALUES (%s,'version',%s) ON CONFLICT DO NOTHING",
                        (eid, name))
        for eid, name in SITE_ENTITIES:
            cur.execute("INSERT INTO entity (id, kind, name) VALUES (%s,'site',%s) ON CONFLICT DO NOTHING",
                        (eid, name))


def ensure_indexes(conn):
    """Indexes built after loading (see sql/schema.sql footer). FTS config must match retrieve.keyword_search."""
    with conn.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS doc_chunk_fts_en ON doc_chunk USING gin (to_tsvector('english', text))")
        cur.execute("CREATE INDEX IF NOT EXISTS doc_chunk_emb_hnsw ON doc_chunk USING hnsw (embedding vector_cosine_ops)")


def load_manual(conn, key, embed=True, cpu=False):
    m = BY_KEY[key]
    chunks = chunk_manual(read_text(key), key)
    t0 = time.time()
    vecs, toks = ([None] * len(chunks), 0)
    if embed:
        vecs, toks = embedder.embed([embedder.doc_text(c.section, c.text) for c in chunks], cpu=cpu)
    t_embed = time.time() - t0
    with conn.cursor() as cur:
        cur.execute("DELETE FROM doc_chunk WHERE id LIKE %s", (f"doc:{key}:%",))
        for c, v in zip(chunks, vecs):
            cur.execute(
                """INSERT INTO doc_chunk (id, source_file, section, text, system_id, version_id, site_id,
                                          all_versions, all_sites, valid_from, embedding)
                   VALUES (%s,%s,%s,%s,%s,%s,NULL,FALSE,TRUE,%s,%s)""",
                (c.id, f"data/raw/hpe/{key}.txt", c.section, c.text, m.system_id, m.version_id, m.published, v))
    return {"manual": key, "chunks": len(chunks), "est_tokens": sum(c.est_tokens for c in chunks),
            "embed_prompt_tokens": toks, "embed_seconds": round(t_embed, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", action="append", help="manual key (default: all)")
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--cpu", action="store_true", help="embed on CPU instead of GPU")
    a = ap.parse_args(argv)
    keys = a.manual or [m.key for m in MANUALS]
    with psycopg.connect(settings.DATABASE_URL, autocommit=False) as conn:
        register_vector(conn)
        ensure_entities(conn)
        stats = []
        for k in keys:
            s = load_manual(conn, k, embed=not a.no_embed, cpu=a.cpu)
            conn.commit()
            print(s, flush=True)
            stats.append(s)
        ensure_indexes(conn)
        conn.commit()
    print("total chunks", sum(s["chunks"] for s in stats), "embed seconds", round(sum(s["embed_seconds"] for s in stats), 1))


if __name__ == "__main__":
    main()
