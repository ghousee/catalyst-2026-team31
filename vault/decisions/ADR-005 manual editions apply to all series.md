# ADR-005 manual editions apply to all series

**Date:** 2026-10-17 · **Status:** accepted

**Context:** every ingested manual is a J/H-era edition (TMF: H06.03+ only), but `\PROD` is L-series
(NonStop X). `doc_chunk.version_id` held one exact series (`rvu:J` / `rvu:H`), so `context_where` with
`version = rvu:L` returned **no manual rows at all**; forcing `rvu:J` for everything already cost 0.18
recall@5 on the TMF (H-only) questions ([[rag spike]], item 8).

**Decision:** manual chunks are explicitly **all-series**: `version_id = NULL`, `all_versions = TRUE`
(the explicit flag required by [[ADR-001 explicit all-versions]]). The honest provenance moves to new
columns: `edition` ("TMF Reference Manual, H-series edition (540138-001, July 2005)"), `doc_version`
(part number), `content_hash` (re-ingest diffing). Citations render it, e.g.
"J/H-series edition; L-series behaviour not verified". Veteran **heuristics stay node/series-scoped**
(`maria:h7` is `\PROD` + `rvu:L`), so the context trap still works where it matters.

**Why not the alternatives:** duplicating rows per series triples the index for no new information;
a version *set* filter changes `context_where` for every caller; guessing "L is close to J" hides the gap.

**Consequence:** the series filter no longer narrows documents; the node/subsystem filter and the
`edition` label carry the safety message. Ingest ([[ingest]]) writes the flags and edition on every chunk.
If an L-series edition is ever ingested it gets its own `version_id = rvu:L` and `supersedes` edges.
Code: `backend/ingest/manuals.py`, `sql/migrations/002_knowledge_graph.sql`.
