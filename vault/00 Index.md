# Index

Map of the codebase for humans (Obsidian) and Claude (cheap lookup before reading code).
Open `vault/` as an Obsidian vault. Notes use `[[wikilinks]]`.

## How to use
- **Claude:** read this note, then only the notes for the area you're touching. Open code at the
  `file:line` the note gives instead of scanning folders.
- **Everyone:** when you change code, update its note **in the same commit**. A stale note is worse
  than no note. Keep notes short: purpose, entry points (file:line), invariants, gotchas.

## Code
- [[schema]] — Postgres tables, context fingerprint, constraints
- [[retrieve]] — context filter (`context_where`), vector/keyword/hybrid search, generate/gate/verify stages
- [[ingest]] — manual chunker, embedder, loader (HPE manuals -> doc_chunk)
- [[eval harness]] — golden set scoring, contamination, ablation
- [[stop hook]] — blocks Claude while unit tests fail
- [[tests]] — what each unit test proves
- [[frontend]] — Next.js operator console, mocks, contract gaps

## Design
- [[core requirements]] — non-negotiables from Ghouse + CAIL (read before designing)
- [[system design]] — NonStop copilot architecture (docs/SYSTEM_DESIGN.md, draft)
- [[api contract]] — pointer to `docs/API_CONTRACT.md` + gotchas

## Decisions
- [[ADR-001 explicit all-versions]]
- [[ADR-002 eval trusts DB not API]]
- [[ADR-003 python stop hook]]
- [[ADR-004 context dimensions]] (proposed)
- [[ADR-005 manual editions apply to all series]]

## Research
- [[rag spike]] — RAG feasibility on the HPE manuals: numbers and decisions (docs/RAG_SPIKE.md)

## Domain
- [[glossary]] — NonStop / project terms (to be filled)

## Status
- [[todo]] — open problems and next steps
