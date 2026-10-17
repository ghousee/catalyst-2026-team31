# graph

Knowledge graph + veteran knowledge: seed data (`kg/seed/*.yaml`), loader, deterministic queries.
Content is **fictional/illustrative** (see `kg/seed/README.md`); every edge cites a real manual chunk or a note.

## Entry points
- `backend/graph/query.py:129` `resolve(conn, text, ctx)` — alias/name/event-number match (`match_entities` :86, `tokens` :45). No LLM.
  `subsystem` comes from the matched entities only (never copied from ctx); two subsystems tied -> `None` (caller clarifies).
- `backend/graph/query.py:206` `lookup(conn, entity_ids, ctx, k)` — 2-hop `walk` (:162) then context-filtered notes, docs, commands, experts, path.
- `backend/graph/load.py:144` `python -m backend.graph.load [--no-embed]` — upsert + validation (`validate` :48) + embeddings for notes.
- `backend/graph/migrate.py` applies `sql/migrations/*.sql`. `scripts/graph_smoke.py` (DB check, \PROD vs \DR), `scripts/export_graph.py` -> `docs/knowledge_graph.html`.
- Seed: `entities.yaml` (events, objects, metrics, 17 command templates, aliases), `heuristics.yaml` (10 notes), `edges.yaml`, `persons.yaml`.

## Model
Entity ids: `sub:` subsystem, `evt:` event, `obj:`, `met:`, `cmd:` (props hold template/risk/source_id), `node:`, `rvu:`. Rels: see [[schema]].
Walk is undirected over about/symptom_of/fixed_by/precedes/depends_on/diagnosed_by/mentions; `sub:/node:/rvu:` are reached, never expanded.

## Invariants
- Notes go through `retrieve.context_where('h')` + `status='approved'`: a `node:PROD` note is never returned for `node:DR`,
  and an unresolved node/series returns only all-nodes/all-series rows. Drafts are never returned.
- Path edges justified by an out-of-context note are dropped (`expert_in` keeps the edge, loses the citation). Tested in `test_graph_query.py`.
- Doc chunks are all-series ([[ADR-005 manual editions apply to all series]]); each result carries `edition`.
- Commands are returned only for the context subsystem; risk class is data (`props.risk`), never LLM output.
- `lookup` with no `ctx.system` infers it if the entities imply exactly one, else `ValueError`.

## Gotchas
- Event numbers (TMF 185/187/109, DISK 5032, Pathway 1034...) come from the demo scenario; the EMS Operator Messages manual is NOT ingested,
  so they are `verified: false`. Edges cite the chunks that document the *object/command*.
- Frontend mock chunk ids (`doc:TMF-Reference:ch121.185`, `doc:Pathway-Ref:...`) do not exist in the DB; real ids look like
  `doc:TMF-Reference:status-audittrail`. `PATHCOM STATUS SERVER *` is not in the ingested Pathway/iTS manual, so the catalog has STATUS TCP/TERM and THAW SERVER instead.
- Merged message chunks carry the id of the first message (`msg-3209` holds 3209 and 3210).
- Loader deletes and re-inserts all `created_by = 'seed'` edges each run; edit the YAML, not the table.
- `query.py` also runs on SQLite (tests): SQL stays portable (`%(x)s` params, IN lists built by `_in`), JSON columns parsed by `_j`.
