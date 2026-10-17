# api

Backend for the UI. One pipeline function, a thin FastAPI shell, a CLI. Contract: [[api contract]] (v2 authoritative).

## Entry points
- `backend/pipeline/answer.py:118` `answer(question, session, override)` -> exactly one of `answer` / `clarify` / `refer`.
  Order: `resolve` -> node-mismatch/subsystem checks (`clarify`) -> `lookup` + `hybrid_search` (docs unfiltered by version/node, filtered by subsystem)
  -> gate -> `generate` -> `verify.support_prob` per claim vs its own source -> cards + `answer_log` row.
- `answer.py:49` `source_card(conn, id)` doc / heuristic card (same fields in answers and `GET /sources/{id}`). `:37` `warm()` loads MiniCheck.
- `backend/api/main.py:43` `/health`, `:59` `/session` (GET, POST `:64`, in-memory, nodes `node:PROD`/`node:DR`), `:72` `/chat`, `:78` `/sources/{id}`. CORS: localhost:3000.
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
