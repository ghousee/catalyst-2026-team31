"""Retrieval. Only the context filter exists so far; graph/vector search comes later.

Every query against doc_chunk or heuristic MUST include context_where() so nothing
outside the resolved system/version/site can be retrieved (CLAUDE.md rule 2).
"""


def context_where(table="", paramstyle="pyformat"):
    """SQL predicate restricting rows to the resolved context.

    NULL version_id/site_id means the row explicitly applies to all versions/sites
    (schema CHECKs tie NULL to all_versions/all_sites). system_id is never optional.
    paramstyle: "pyformat" for psycopg (%(name)s), "named" for sqlite (:name).
    """
    p = (lambda n: f"%({n})s") if paramstyle == "pyformat" else (lambda n: f":{n}")
    c = f"{table}." if table else ""
    return (f"{c}system_id = {p('system')}"
            f" AND ({c}version_id = {p('version')} OR {c}version_id IS NULL)"
            f" AND ({c}site_id = {p('site')} OR {c}site_id IS NULL)")


def context_params(ctx):
    """Params for context_where(). Refuses to run without a resolved system.

    An unresolved version/site stays None, which matches only all-versions/all-sites rows.
    """
    if not ctx or not ctx.get("system"):
        raise ValueError("context has no resolved system; clarify before retrieving")
    return {"system": ctx["system"], "version": ctx.get("version"), "site": ctx.get("site")}


# ---------------------------------------------------------------------------
# Search over doc_chunk: vector, keyword (Postgres full text), hybrid (RRF).
# ctx is a dict {system, version, site}; pass ctx=None ONLY from the eval harness to measure
# contamination without a filter. Production callers must always pass a context.
# ---------------------------------------------------------------------------
import math
import re

FTS_CONFIG = "english"  # must match the GIN index created by backend.ingest.loader.ensure_indexes
_STOP = set("a an and are as at be by can do does for from how i if in is it me my of on or the to "
            "what when which with you your we our this that there their should would could not no "
            "get got use used using need want show see".split())
_TOKEN = re.compile(r"[A-Za-z0-9_#$%]+")


def query_terms(q):
    """Alphanumeric query tokens minus stop words (de-duplicated, order kept). Pure; unit-tested."""
    seen, out = set(), []
    for t in _TOKEN.findall(q):
        k = t.lower()
        if len(k) < 2 or k in _STOP or k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def or_tsquery_text(q):
    """Text for websearch_to_tsquery that ORs every term (natural-language questions rarely contain all)."""
    return " or ".join(query_terms(q))


def rrf_fuse(ranked_lists, k=60, top=None):
    """Reciprocal rank fusion over lists of ids (best first). Returns [(id, score)] best first."""
    score = {}
    for lst in ranked_lists:
        for rank, i in enumerate(lst, start=1):
            score[i] = score.get(i, 0.0) + 1.0 / (k + rank)
    fused = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    return fused[:top] if top else fused


# a chunk removed by a document re-upload has valid_to = that day (exclusive end): never retrievable
CURRENT = "(valid_to IS NULL OR valid_to > CURRENT_DATE)"


def _scope(ctx, table=""):
    if ctx is None:
        return CURRENT, {}
    return f"{context_where(table)} AND {CURRENT}", context_params(ctx)


def vector_search(conn, qvec, ctx, k=5):
    """Cosine nearest chunks inside the context. Returns [{id, section, text, system_id, score}]."""
    where, params = _scope(ctx)
    params.update(q=qvec, k=k)
    sql = f"""SELECT id, section, text, system_id, 1 - (embedding <=> %(q)s::vector) AS score
              FROM doc_chunk WHERE {where} ORDER BY embedding <=> %(q)s::vector LIMIT %(k)s"""
    return _rows(conn, sql, params)


_df_cache = {}


def _idf(conn, term):
    """BM25-style idf of a (stemmed by Postgres) term over doc_chunk; 0.0 if the term is a stop word/absent."""
    if term not in _df_cache:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM doc_chunk WHERE to_tsvector('{FTS_CONFIG}', text) "
                        f"@@ plainto_tsquery('{FTS_CONFIG}', %s) AND plainto_tsquery('{FTS_CONFIG}', %s)::text <> ''",
                        (term, term))
            df = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM doc_chunk")
            n = cur.fetchone()[0]
        _df_cache[term] = math.log(1 + (n - df + 0.5) / (df + 0.5)) if df else 0.0
    return _df_cache[term]


def keyword_search(conn, query, ctx, k=5):
    """Postgres full-text search inside the context. Candidates = chunks matching ANY query term (GIN index);
    score = sum of idf of matched terms (BM25 without tf saturation) + 0.1 * ts_rank_cd as tie-break.
    Plain ts_rank has no idf, so a common word like STATUS drowned the rare command/message token."""
    terms = [t for t in query_terms(query) if _idf(conn, t) > 0]
    if not terms:
        return []
    where, params = _scope(ctx)
    cfg = FTS_CONFIG
    parts = []
    for i, t in enumerate(terms):
        params[f"t{i}"] = t
        parts.append(f"{_idf(conn, t):.4f} * (v @@ plainto_tsquery('{cfg}', %(t{i})s))::int")
    params.update(any=" or ".join(terms), k=k)
    sql = f"""WITH cand AS (
                SELECT id, section, text, system_id, to_tsvector('{cfg}', text) AS v FROM doc_chunk
                WHERE {where} AND to_tsvector('{cfg}', text) @@ websearch_to_tsquery('{cfg}', %(any)s))
              SELECT id, section, text, system_id,
                     {' + '.join(parts)} + 0.1 * ts_rank_cd(v, websearch_to_tsquery('{cfg}', %(any)s), 32) AS score
              FROM cand ORDER BY score DESC, id LIMIT %(k)s"""
    return _rows(conn, sql, params)


def hybrid_search(conn, query, qvec, ctx, k=5, pool=30, rrf_k=60):
    """RRF of vector and keyword rankings (each cut to `pool`), filtered by ctx. Returns top-k rows."""
    v = vector_search(conn, qvec, ctx, pool)
    w = keyword_search(conn, query, ctx, pool)
    rows = {r["id"]: r for r in v + w}
    out = []
    for i, s in rrf_fuse([[r["id"] for r in v], [r["id"] for r in w]], k=rrf_k, top=k):
        r = dict(rows[i])
        r["score"] = s
        out.append(r)
    return out


def _rows(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
