# ADR-001 explicit all-versions

**Date:** 2026-10-16 · **Status:** accepted

**Context:** Filter `version_id = :v OR version_id IS NULL` lets "applies to all versions" rows through.
If ingest leaves version NULL by accident, that row leaks into every version's answers.

**Decision:** `all_versions`/`all_sites` booleans + `CHECK ((version_id IS NULL) = all_versions)`.
NULL is only possible when someone set the flag on purpose. `system_id` is NOT NULL.

**Consequence:** ingest must tag every chunk explicitly; untagged chunks fail to insert (good).
Code: [[schema]], [[retrieve]].
