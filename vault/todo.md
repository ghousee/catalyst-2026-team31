# todo

- [ ] **Team review of [[system design]]** — then rewrite PLAN/EVAL/API examples from pumps to NonStop.
- [ ] Pick the creative angle (design §12; recommended: Drill mode + lead-time scoreboard).
- [ ] UI (after design sign-off).
- [ ] Postgres port clash on the dev laptop: another project (`frr-postgres`) holds 5432. Make the
      compose host port configurable (`PG_PORT`, default 5432) — awaiting Ghouse's OK.
- [ ] HPE manuals downloaded during research sit in Claude's scratchpad (temporary) → copy to
      `data/raw/` (gitignored) for ingestion.
- [ ] Real-Postgres integration test for [[retrieve]] (marked, not run by the [[stop hook]]).
- [ ] Build the rest of retrieve (graph query → filtered vector search → ACL).
- [ ] New modules per design §14: simulator, commands (catalog/parser/risk/guards), watcher.
