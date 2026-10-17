# todo

- [ ] **Team review of [[system design]]** — then rewrite PLAN/EVAL/API examples from pumps to NonStop.
- [ ] Pick the creative angle (design §12; recommended: Drill mode + lead-time scoreboard).
- [x] UI on mocks merged (`frontend/`, [[frontend]]); wire to real API next.
- [x] Port clash fixed: PG_PORT/OLLAMA_PORT in `.env` (5433/11435 on Ghouse's laptop); own GPU Ollama service.
- [x] HPE manuals are in `data/raw/hpe/` (gitignored) and ingested ([[ingest]]).
- [ ] Real-Postgres integration test for [[retrieve]] (marked, not run by the [[stop hook]]).
- [x] Knowledge graph: migration 002, seed (10 notes, TMF hero), loader, `resolve`/`lookup`, graph view ([[graph]], [[ADR-005 manual editions apply to all series]]).
- [ ] Retrieve: ACL; embed-search over `heuristic.embedding` (embeddings are loaded, no search function yet); wire `lookup` into the ask pipeline (backend agent).
- [ ] Ingest the EMS Operator Messages manual so event numbers (TMF 185/187...) can be cited and `verified: true`; add a Pathway TS/MP manual (STATUS SERVER).
- [ ] Veteran review of the seed notes (domain plausibility, esp. `raj:h8` DR note and abort-threshold numbers).
- [ ] New modules per design §14: simulator + commands are implemented ([[simulator]], [[commands]]); watcher remains.
- [ ] RAG spike follow-ups ([[rag spike]]): one chunk per message number; stored tsvector; series strategy for
      multi-series manuals (exact `version_id` match cost 0.18 recall@5); larger independent eval set with real
      operator phrasing; near-miss sufficiency-gate cases; subtle MiniCheck negatives; wire `context.py`/`answer.py`.
- [x] Decided: keep `qwen3.5:4b` (works, 100% GPU) - no need for the phi4-mini fallback.

## Watcher (2026-10-17, built)
backend/watcher/rules.py (pure detectors: pattern rule, stalled, trend) + engine.py (buffer, alerts, card, replay).
Replays in data/replay/*.jsonl, started by the Training Simulator buttons. Next: Prognosis REST poller + MOMI export
folder reader posting to the same `ingest`; Teach to capture `rule` fields; incident history for `backtest`.
Graph audit: 6 curated nodes have no links (rvu:J, rvu:H, obj:TCP, obj:CPUs, met:cpu-qtime, met:request-qtime);
2,645 of 3,777 manual sections are not linked to any node (titles name no command/message) - still searchable.
