# graph

Knowledge graph + veteran knowledge: seed data (`kg/seed/*.yaml`), loader, deterministic queries.
Content is **fictional/illustrative** (see `kg/seed/README.md`); every edge cites a real manual chunk or a note.

## Entry points
- `backend/graph/query.py:129` `resolve(conn, text, ctx)` — alias/name/event-number match (`match_entities` :86, `tokens` :45). No LLM.
  `subsystem` comes from the matched entities only (never copied from ctx); two subsystems tied -> `None` (caller clarifies).
- `backend/graph/query.py:206` `lookup(conn, entity_ids, ctx, k)` — 2-hop `walk` (:162) then context-filtered notes, docs, commands, experts, path.
- `query.py` `note_search` (vector search over approved notes, context-scoped), `fetch_notes` (notes by id, same filter), `note_dict` (one note's shape; `disagrees_with` = in-context partners only).
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

## Auto-built from the manuals (2026-10-17) — `backend/graph/from_docs.py`
`python -m backend.graph.from_docs [--subsystem sub:TMF] [--dry-run] [--rebuild]` — deterministic (no LLM), idempotent. Titles of `doc_chunk` sections give:
- **commands** `cmd:auto:<sub>:<slug>` (kind `command`, parent = subsystem, name `<TOOL> <COMMAND>` e.g. `SCF ADD DISK`, `FUP CONFIG[URE]`, `PEEK PAGING`).
  Per-manual rule in `PROFILES` (`command_heads`): TMF/FUP = bare uppercase heading under the commands chapter; SCF/Pathway/TACL = `<X> Command`;
  PEEK = `<X> Option`; MEASURE (flat titles) = heading whose first word is a MEASCOM verb. Ranges (`A .. B`) name both ends, `A - note` ignores the note.
  Not extracted: guidelines/examples/listing formats, summary chapters, TACL built-in functions, API procedures, glossary.
- **messages** `evt:auto:<sub>:<number>` (kind `event`, name `<TOOL> message <n>`): `Message n` / `MEAS n` titles plus the bare number lines inside merged sections (`message_numbers`).
  `props.number` is a **string** on purpose: `match_entities` compares int `props.number` (curated EMS events) with bare numbers in a question. FUP has none (`UNNUMBERED`).
- props `{auto: true, risk, source_id}`; `risk` = `read_only` only when the first word is STATUS/INFO/LISTOPENS/DISPLAY/SHOW/HELP, else `unknown`. No `template_id`/`subsystem`
  on purpose: `lookup` lists a command only if it has `template_id` (catalog), so auto commands are never proposed or executed.
- aliases: lowercase, **never a single word** (`add`, `status`, `info` stay out): `<tool> <command>` plus the bare command when it is >= 2 words; bracket forms expand
  (`fup configure`, `fup config`); an alias any other entity already uses is dropped.
- edges (`created_by='auto-docs'`, `source_id` = defining section = lowest page): section -about-> entity, entity -about-> subsystem.
- **dedupe**: `norm_key` (tool prefix, case, plural, `[optional]` parts and arguments dropped: `FUP LISTOPENS file`, `... STATUS AUDITTRAIL, DETAIL`) equal to a curated command's key (or the curated one = auto + arguments, auto >= 2 words)
  -> reuse the curated id, add only the section -about-> curated edge. Curated rows are never edited.
- `sync(conn, sub)` = extract + upsert + prune (auto-docs edges whose section is gone/renamed; auto entities left without a section, unless a human/curated edge uses them). `POST /documents` calls it for the
  document's subsystem and returns `graph` counts. `--rebuild` deletes only `props.auto` entities, `created_by='auto-docs'` edges and auto `mentions` of those, then re-extracts.
- `GET /graph`: links are capped at 500 with curated/human first and auto-docs last, so the thousands of auto links never push out the curated ones; `entities` lists every entity.

## Knowledge capture (2026-10-17) — `backend/knowledge.py`
- draft (`POST /knowledge`) -> owner signs (`/approve`, 403 for anyone else) -> approved. Embedding = same text as the seed loader (`doc_text(trigger[:80], trigger+call+why)`, CPU).
- Auto-link on approve (`autolink_edges`, pure): `about` subsystem + entities named in trigger+call (via `resolve`, same subsystem only), `applies_to` node(s)
  (all nodes -> both), owner `expert_in` +1 (`created_by='auto'`; the seed loader re-inserts seed edges and would reset a seed expert_in weight). Human links via `/link` (`created_by='human'`).
- Suggested manual sections = `hybrid_search` top 3 in the subsystem. Scope of a new note: all series, one node or all.
- Removed doc chunks (`valid_to <= today`) are excluded: `retrieve.CURRENT`, `query.DOC_CURRENT`.
