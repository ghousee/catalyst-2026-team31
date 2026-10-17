# retrieve

File: `backend/pipeline/retrieve.py`. Context filter + doc_chunk search (vector, keyword, hybrid).
Later pipeline stages built in the spike: `generate.py`, `gate.py`, `verify.py`, `llm.py` (see below).

## Entry points
- `context_where(table="", paramstyle="pyformat")` — line 8. Returns
  `system_id = :system AND (version_id = :version OR version_id IS NULL) AND (site_id = :site OR site_id IS NULL)`.
  `paramstyle="named"` for sqlite (tests), default `pyformat` for psycopg.
- `context_params(ctx)` — line 22. Raises `ValueError` if no resolved system -> caller must clarify.
- `vector_search(conn, qvec, ctx, k)` — :80, pgvector cosine.
- `keyword_search(conn, query, ctx, k)` — :106, Postgres FTS, OR terms, score = sum idf of matched terms (+0.1 ts_rank_cd). `_idf` :92.
- `hybrid_search(conn, query, qvec, ctx, k, pool=30)` — :129, RRF (`rrf_fuse` :64) of the two.
- `query_terms` :47 / `or_tsquery_text` :59 — pure helpers.
- `ctx=None` disables the filter: **only for eval baselines** (contamination measurement).

## Pipeline stages added by the spike (all in `backend/pipeline/`)
- `llm.py:9` `chat()` Ollama client with `format` schema, timings; `:31` `loaded_models()` (/api/ps).
- `generate.py:66` `generate()` -> `[{claim, source_id}]`; sources aliased S1..Sn (`unalias` :39), `keep_cited` :59 drops uncited claims.
- `gate.py:31` `sufficient()` prompt-based gate. `verify.py:31` `support_prob()` MiniCheck-Flan-T5-Large on CPU.

## Invariants
- Filter is applied **before** vector search (inside the same SQL), never after (CLAUDE.md rule 2).
- Unresolved version/site (None) matches only all-versions/all-sites rows — safe by default.
- NULL only means "all" because [[schema]] CHECKs forbid accidental NULLs ([[ADR-001 explicit all-versions]]).
- FTS config (`english`) must match the GIN index from `ingest/loader.py:42`.

## Gotchas (measured, see [[rag spike]])
- Plain `ts_rank` (no idf) was useless for message numbers; keep the idf score.
- Exact-match `version_id` is dangerous: forcing `rvu:J` on a TMF (H-only) question set cut hybrid recall@5 0.81 -> 0.63.
- Keyword step is ~270 ms filtered (tsvector computed on the fly); add a stored tsvector if it matters.
- Always label sources S1..Sn for the LLM; raw ids led to invented ids and a dropped correct claim.

## Tested by
[[tests]] -> `test_context_filter.py`, `test_retrieve_search.py`, `test_generate_gate_verify.py`.
DB/Ollama-dependent checks live in `scripts/rag_spike.py`.

## Next
Graph query first, ACL, per-message chunks. See [[todo]].
