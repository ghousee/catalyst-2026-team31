# todo

- [ ] Domain switch: starter kit uses placeholder pumps (P-201, Ravi). Real target is **HPE NonStop**
      operations for CAIL. Rewrite PLAN/EVAL/API examples after [[system design]] is agreed.
- [ ] Postgres port clash on the dev laptop: another project (`frr-postgres`) holds 5432. Make the
      compose host port configurable (`PG_PORT`, default 5432) — awaiting Ghouse's OK.
- [ ] Real-Postgres integration test for [[retrieve]] (marked, not run by the [[stop hook]]).
- [ ] Build the rest of retrieve (graph query → filtered vector search → ACL).
- [ ] UI (after system design).
