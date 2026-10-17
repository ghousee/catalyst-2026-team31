# eval harness

File: `eval/run_eval.py`. Docs: `docs/EVAL.md`, `eval/README.md` (categories, independence note).
Golden sets: `eval/golden.jsonl` (60 items, independent of the pipeline), `eval/golden_template.jsonl` (schema example).
Run: `python eval/run_eval.py --golden eval/golden.jsonl --config N` (1 plain RAG ... 4 full). Output CSV -> `eval/results/` (gitignored).
Exits with a clear message if the API is down (`api_up`); `EVAL_API_BASE` overrides `http://localhost:8000`.

| Function | Line | Notes |
|---|---|---|
| call | 28 | POST /chat with `ablation` |
| set_node | 35 | POST /session `{node}` before an item so the session node is honoured |
| api_up | 43 | False only if unreachable (HTTP errors count as up) |
| lookup_source_systems | 58 | `{source_id: system_id}` from doc_chunk + heuristic via `DATABASE_URL` |
| wilson | 72 | 95% Wilson interval, (None, None) for n=0 |
| includes_all / includes_any | 91 / 97 | case-insensitive phrase match; must_include groups are any-of lists |
| forbidden_hits | 102 | cited ids matching forbidden ids/fnmatch globs |
| both_sides_ok | 107 | each any-of id group has a citation |
| contaminated | 112 | answer cites any source whose system != gold; unknown id = contaminated; None if DB down |
| score | 122 | per-item row |
| rate | 163 | `k/n (pct) 95% CI [lo-hi%] n=N`; "n/a (0 items)" on empty subsets |
| main | 179 | loads items, API preflight, sets node per item, one DB lookup, scores |

## Golden item fields
`id, category, q, node, system, version, gold_nodes, expect, expert, must_include, must_not_include,
forbidden_sources, both_sides, notes`. Categories: doc, veteran, context_trap, conflict, negation, must_refer, must_clarify.
`node` (`node:PROD`/`node:DR`) is sent to the API session. Older template fields keep working; new fields are optional.

## Metrics (each with n and 95% Wilson CI)
behaviour acc, context acc (system, version, and site == item node if the API returns site), retrieval hit,
contamination (traps = headline, and all), correct/false refusals, expert routing, plus
- `must_include_ok`: all key-fact groups present in claim text (answer items only; a refusal fails it)
- `must_not_ok`: no banned phrase in claim text
- `forbidden_clean`: no forbidden source cited (e.g. maria:* on \DR)
- `both_sides_ok`: conflict items cite both sides
- behaviour per category

## Invariants
- Contamination comes from the DB, not the API's self-report ([[ADR-002 eval trusts DB not API]]).
- `context_ok` is None for clarify items (no gold context).
- Headline metric = contamination on `context_trap` items.
- The golden set was written without reading the pipeline; do not tune questions to pipeline behaviour.

## Tested by
[[tests]] -> `test_eval_scoring.py` (contamination) and `test_eval_metrics.py` (Wilson, must_include, forbidden, both-sides, golden schema, API-down exit). Both import the script via importlib; `eval/` isn't a package.
