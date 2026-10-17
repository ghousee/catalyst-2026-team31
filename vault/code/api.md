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
- MiniCheck checks a claim against its source only, so a claim that misreads a veteran note ("the manual recommends X" when the note says not to) can pass. Seen on `maria:h11`.
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
