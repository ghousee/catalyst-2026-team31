# schema

File: `sql/schema.sql`. Loaded by Docker on **first** start of an empty volume only
(`docker compose down -v` to reload — wipes data).

| Table | Line | Purpose |
|---|---|---|
| entity | 6 | backbone nodes: system, version, component, symptom, alarm, site, procedure |
| person | 14 | veterans / doc owners |
| doc_chunk | 29 | doc overlay; context fingerprint + embedding(768) |
| heuristic | 49 | person overlay: trigger/call/why, provenance, status |
| edge | 71 | graph: about, symptom_of, fixed_by, precedes, extends/contradicts/supersedes, disagrees_with, expert_in |
| answer_log | 88 | audit of every /chat response; `id` = `answer_log_id` in API |
| referral | 101 | /refer loop |
| feedback | 116 | /feedback endorse/wrong/outdated |
| alert | 126 | watcher alerts |

## Invariants
- `system_id NOT NULL` on doc_chunk + heuristic.
- `CHECK ((version_id IS NULL) = all_versions)` and same for site (lines 44-45, 66-67).
  See [[ADR-001 explicit all-versions]].
- Every query on doc_chunk/heuristic goes through [[retrieve]] `context_where()`.

## Gotchas
- IDE shows T-SQL errors on the CHECKs — false positive, it's valid Postgres.
- Vector dim 768 = embeddinggemma; **verified** against the pulled model (2026-10-17, [[rag spike]]).
- Indexes created after load by `backend/ingest/loader.py:42` (GIN FTS on `to_tsvector('english', text)`, HNSW cosine); also listed in the schema.sql footer.
- Verified loading in pgvector/pg16 on 2026-10-16 (all 9 tables, constraints reject bad rows).
