# retrieve

File: `backend/pipeline/retrieve.py`. Only the context filter exists so far.

- `context_where(table="", paramstyle="pyformat")` — line 8. Returns
  `system_id = :system AND (version_id = :version OR version_id IS NULL) AND (site_id = :site OR site_id IS NULL)`.
  `paramstyle="named"` for sqlite (tests), default `pyformat` for psycopg.
- `context_params(ctx)` — line 22. Raises `ValueError` if no resolved system → caller must clarify.

## Invariants
- Filter is applied **before** vector search, never after (CLAUDE.md rule 2).
- Unresolved version/site (None) matches only all-versions/all-sites rows — safe by default.
- NULL only means "all" because [[schema]] CHECKs forbid accidental NULLs ([[ADR-001 explicit all-versions]]).

## Tested by
[[tests]] → `test_context_filter.py`.

## Next
Graph query first, then pgvector search inside the filter, plus ACL. See [[todo]].
