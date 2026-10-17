# api

Backend for the UI. One pipeline function, a thin FastAPI shell, a CLI. Contract: [[api contract]] (v2 authoritative).

## Entry points
- `backend/pipeline/answer.py:118` `answer(question, session, override)` -> exactly one of `answer` / `clarify` / `refer`.
  Order: `resolve` -> node-mismatch/subsystem checks (`clarify`) -> `lookup` + `hybrid_search` (docs unfiltered by version/node, filtered by subsystem)
  -> gate -> `generate` -> `verify.support_prob` per claim vs its own source -> cards + `answer_log` row.
- `answer.py:49` `source_card(conn, id)` doc / heuristic card (same fields in answers and `GET /sources/{id}`). `:37` `warm()` loads MiniCheck.
- `backend/api/main.py` exposes `/health`, `/session`, `/chat`, `/sources/{id}`, the [[commands]] proposal/review routes, and [[simulator]] scenario/metrics routes. CORS: localhost:3000.
- `/sources/{id}` checks synthetic command runs before querying Postgres, so simulator output can become a `live` citation.
- `scripts/ask.py "question" [--node PROD|DR]` calls `answer()` directly and prints entities, path, sources, gate, claims + scores, experts, timings.

## Rules implemented
- Context = session node + series, subsystem from graph `resolve()`; `context_override` wins. No LLM for context.
- Node named in the question != session node (and no site override) -> `clarify` with the nodes. Entities matched but subsystem tied -> `clarify` with subsystems.
- **No entity matched at all** -> `refer` (everyone, active first; `context.system` is `""`). Gate says no, or no claim survives MiniCheck -> `refer` with graph experts.
- Lane comes from the cited source (veteran note ids -> `veteran`). Uncited or unsupported claims are dropped and counted in `dropped_claims`.
- Extra keys the UI ignores: `quality` (answer + refer: counts, support avg/min, gate, lanes, latency, per-stage ms) and `debug` (entities, path, retrieved, dropped claims with scores).

## Run
`uvicorn backend.api.main:app --port 8000` (needs Docker db + Ollama, `python -m backend.graph.load` done). Startup loads MiniCheck (~30 s).

## Gotchas
- Latency (RTX 4050, CPU MiniCheck): about 6-15 s warm; verify is CPU and scales with claims x source length, generate/gate on GPU 2-6 s. Embedding the query runs on CPU (~0.5 s).
- Qwen sometimes writes the node as `\PROD` or a stray Cyrillic letter before PROD; `_clean` repairs it before verification.
- Context `confidence` is not a model output: 0.9 when the subsystem came from the graph, 1.0 with an override.
- `/sources/{id}` does not apply session context (it is a card lookup by id).
- MiniCheck checks a claim against its source only, so a paraphrase that inverts a note can pass (seen on `maria:h11`); veteran claims are now verbatim, see the last section.
- A vague question that resolves to one subsystem ("the disk is acting up" -> Storage) is not clarified; the gate refers it.
- Tests: `tests/unit/test_answer.py` fakes every stage.

## Tuning (2026-10-17, after first real test)
- Vague questions (only a whole subsystem matched, e.g. "the disk is acting up") -> clarify asking for the symptom
  with examples from the graph; picking the area (override) proceeds without a second clarify.
- LLM sufficiency gate is skipped when the graph matched a specific event/object/command/metric with linked knowledge
  (saves ~2.7 s); still runs for subsystem-only matches.
- Sources interleaved doc/veteran (max 6 docs, 3 notes), labelled MANUAL/VETERAN for Qwen, with a "balanced
  answer" rule (`generate.LANE_RULES`). Notes-first -> only veteran claims; docs-first -> only manual claims.
- Max 4 claims; MiniCheck batched (`verify.support_probs`) against the same 1,800 chars Qwen saw.
- `misattributed()` drops claims where a veteran note is quoted as "the manual says/recommends" (or a doc as a
  named veteran). MiniCheck scored such an inverted claim 0.97. "Don't rely on the manual's X" stays allowed.
- Ollama `keep_alive: 60m` + `warm()` loads Qwen and the embedder at startup (cold reload cost ~20 s).
- Measured warm, 5 questions: 8-12.5 s per answer; all 5 cite both a manual section and a veteran.

## Verbatim veterans, note search, conflicts (2026-10-17)
- Veteran-lane claims are never Qwen's wording. Each veteran note Qwen cites (relevance signal) becomes ONE claim =
  the note's `call_text` verbatim (`answer.verbatim`, cut to 2 sentences above 300 chars), `verified: true`, `score: 1.0`,
  `verbatim: true`. Qwen's claims about that note are discarded (MiniCheck passed an inverted paraphrase at 0.97).
  Veteran claims come first, then the verified doc claims. `dropped_claims` now counts dropped Qwen claims only.
- Negation guard on doc claims (`verify.negation_mismatch`, why `negation` in `debug.dropped`): drop a claim that negates
  something the source does not negate nearby, or that mentions the 2 words right after a source "not" without negating
  them. Same-sentence windows. Real run: 1 borderline drop in 5 questions; if it drops good claims, loosen it.
- `graph.query.note_search(conn, qvec, ctx, k)`: brute-force cosine over approved, context-scoped `heuristic.embedding`
  (same `context_where`), merged with `lookup` notes (lookup's top 2, then search hits, then the rest; max `MAX_NOTES`).
- Conflicts: a used note's in-context `disagrees_with` partner is added as its own verbatim claim; both claims get
  `conflict_with: <other id>`. A note with relation `contradicts:doc:X` gets `contradicts: "doc:X"` on its claim.
- Source card for notes has `not_when`. The MANUAL header in the Qwen prompt carries the edition string.
- Gotcha: `disagrees_with` in note dicts only lists partners that are approved and in context (an unfiltered id leaked
  a \PROD note id on \DR; caught by `test_prod_only_note_never_returned_for_dr`).

## Veteran relevance, knowledge capture, documents (2026-10-17)
- A veteran note is offered to Qwen only if its cosine to the question is >= `NOTE_MIN_SIM` (0.5; `answer.relevant_notes`; calibrated: off-topic
  notes scored 0.31-0.49, on-topic 0.55-0.79). Unknown similarity = not offered. It is used only if Qwen cited it AND Qwen's claim about it passes
  MiniCheck against the note's plain text (trigger+call+why+not_when) >= `VERIFY_THRESHOLD`, OR cosine >= `NOTE_STRONG_SIM` (0.7): MiniCheck scores a
  faithful negation paraphrase ("do not start with X") at 0.02, so a close match overrides it (`answer.note_ok`). Then the claim is the verbatim call_text.
- `contradicts` is set on a veteran claim only if that manual section is in the answer's cited docs (`veteran_claims(doc_cited=...)`).
- `needs_review` notes still answer; the claim carries `needs_review: true`.
- `verify.negation_mismatch`: a source negation only counts for claim words the source never uses un-negated (it dropped a good TACL claim because
  of an unrelated "does not exist, TACL returns").
- `generate.SYSTEM`: keep conditions, exact command/option names, name option combinations together.
- Routers: `backend/knowledge.py` (`/persons`, `/knowledge*`), `backend/documents.py` (`/documents`) included in `main.py`. Contract: `docs/API_CONTRACT.md` v3.
- Expert card "author of N approved note(s) that apply here" = the owner's approved notes in the context (`graph.query.lookup`).
- `answer.clean_title` repairs the TACL kerning glitch ("Com m and(s)") in section titles shown on source cards.

## GET /graph (2026-10-17) — `backend/graph/view.py`
Read-only snapshot for the UI's Knowledge graph page. `shape_graph` is pure (tested in `test_knowledge_capture.py`).
`{counts{entities by kind, links by rel, persons, notes{approved,draft,retired,needs_review}, doc_sections, documents}, entities[{id,kind,name,aliases,parent_id,links}],
links[{src,rel,dst,source_id,created_by}] (cap 500, auto/human before seed), links_total, notes[{id,owner_name,kind,scope,status,needs_review,signed_at,call_text}] (cap 200),
recent[...20]}`. Edges have no timestamp, so `recent` = notes signed/drafted, plus auto/human links dated by their note, plus document loads, newest first.

## Answer modes (2026-10-17)
`ANSWER_MODE` env: `classic` (default) = `backend/pipeline/answer.py` (claims JSON, gate, MiniCheck);
`assistant` = `backend/pipeline/assistant.py` (hybrid search + node-scoped notes -> MiniLM rerank fused with search
rank -> one cited Qwen answer with history). See docs/ARCHITECTURE_V2.md. `/chat` accepts `history`
[{question, reply}]. Assistant responses carry `reply` + `reply_citations`, `claims` is empty; the UI's
`ReplyText` renders it. The eval treats an assistant answer with no citations as refer (or clarify if it ends in "?").

## Learning map (2026-10-17) — `backend/learning.py`
`GET /learning/users` (operators in `answer_log` with question counts; ids `eval conncheck check t test cli` excluded, `real_users`) and
`GET /learning/{user_id}` (404 for test ids / no questions). Pure `shape_map` (tested in `test_learning.py`): per `sub:*` entity the questions asked
(context.system), manual sections cited (`doc_chunk.system_id`), veteran notes cited (`heuristic.system_id`, owner), entities touched (`about` edges from
cited notes/chunks to entities whose `parent_id` is that subsystem), coverage = touched / entities in the subsystem, last seen.
"Touched" needs a cited source, so a question that cited nothing does not count. Gaps = untouched subsystems + events. It is encounter history, not a test of knowledge.
Gotcha: `/chat` with `context_override: {"site": "node:DR"}` and no `version` returns a 500; send both.

## Teach chat (2026-10-17)
- `POST /knowledge/teach` (`backend/knowledge.py`, `teach` / `shape_turn`): one `llm.chat` per turn with a JSON schema whose `subsystem` is an enum of the real `sub:*` ids.
  `shape_turn` (pure, unit-tested) decides question vs draft: model `ask` or a missing trigger/call/node/subsystem -> question (max `MAX_FOLLOWUPS`=3, then draft with what is known);
  every text field must be `grounded` in the veteran's words (>= 60% of its words said) or it is emptied. Nothing is saved here: the UI posts the draft to `POST /knowledge`, then the existing approve flow.
- Gotcha: Qwen 4B often drafts on turn 1 and leaves why / not-when empty rather than asking (prompt asks, it ignores); the editable form covers it. Free-text subsystem made it ask for ids: hence the enum schema.
