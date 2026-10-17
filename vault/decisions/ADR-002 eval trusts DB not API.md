# ADR-002 eval trusts DB not API

**Date:** 2026-10-16 · **Status:** accepted

**Decision:** contamination is computed by looking up each cited `source_id`'s `system_id` in Postgres,
not from fields the API returns. The system under test shouldn't grade itself. Unknown source ids
count as contaminated (fail closed). If the DB is unreachable, contamination is reported n/a, not 0.

Code: [[eval harness]].
