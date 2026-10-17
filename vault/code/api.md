# api

Backend for the UI. One pipeline function, a thin FastAPI shell, a CLI. Contract: [[api contract]] (v2 authoritative).

## Entry points
- `backend/pipeline/answer.py:119` `answer(question, session, override)` -> exactly one of `answer` / `clarify` / `refer`.
  Order: `resolve` -> node-mismatch/subsystem checks (`clarify`) -> `lookup` + `hybrid_search` (docs unfiltered by version/node, filtered by subsystem)
  -> gate -> `generate` -> `verify.support_prob` per claim vs its own source -> cards + `answer_log` row.
- `answer.py:50` `source_card(conn, id)` doc / heuristic card (same fields in answers and `GET /sources/{id}`). `:38` `warm()` loads MiniCheck.
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
- MiniCheck checks a claim against its source only, so a claim that misreads a veteran note ("the manual recommends X" when the note says not to) can pass. Seen on `maria:h11`.
- A vague question that resolves to one subsystem ("the disk is acting up" -> Storage) is not clarified; the gate refers it.
- Tests: `tests/unit/test_answer.py` fakes every stage.
