# todo

- [ ] **Team review of [[system design]]** — then rewrite PLAN/EVAL/API examples from pumps to NonStop.
- [ ] Pick the creative angle (design §12; recommended: Drill mode + lead-time scoreboard).
- [ ] UI (after design sign-off).
- [ ] Postgres port clash on the dev laptop: another project (`frr-postgres`) holds 5432. Make the
      compose host port configurable (`PG_PORT`, default 5432) — awaiting Ghouse's OK.
- [x] HPE manuals are in `data/raw/hpe/` (gitignored) and ingested ([[ingest]]).
- [ ] Real-Postgres integration test for [[retrieve]] (marked, not run by the [[stop hook]]).
- [ ] Build the rest of retrieve (graph query → ACL). Filtered vector/keyword/hybrid search is done ([[rag spike]]).
- [ ] New modules per design §14: simulator, commands (catalog/parser/risk/guards), watcher.
- [ ] RAG spike follow-ups ([[rag spike]]): one chunk per message number; stored tsvector; series strategy for
      multi-series manuals (exact `version_id` match cost 0.18 recall@5); larger independent eval set with real
      operator phrasing; near-miss sufficiency-gate cases; subtle MiniCheck negatives; wire `context.py`/`answer.py`.
- [ ] Decide: keep `qwen3.5:4b` (works, 100% GPU) - no need for the phi4-mini fallback.
