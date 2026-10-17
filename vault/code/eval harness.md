# eval harness

File: `eval/run_eval.py`. Docs: `docs/EVAL.md`. Template: `eval/golden_template.jsonl`.
Run: `python eval/run_eval.py --config N` (1 plain RAG … 4 full). Output CSV → `eval/results/` (gitignored).

| Function | Line | Notes |
|---|---|---|
| call | 21 | POST /chat with `ablation` |
| lookup_source_systems | 32 | `{source_id: system_id}` from doc_chunk ∪ heuristic via `DATABASE_URL` |
| contaminated | 46 | answer cites any source whose system ≠ gold; unknown id = contaminated; None if DB down |
| score | 56 | per-item row |
| rate | 83 | "n/a (0 items)" on empty subsets |
| main | 97 | collects all responses, one DB lookup, then scores |

## Invariants
- Contamination comes from the DB, not the API's self-report ([[ADR-002 eval trusts DB not API]]).
- `context_ok` is None for clarify items (no gold context).
- Headline metric = contamination on `context_trap` items.

## Tested by
[[tests]] → `test_eval_scoring.py` (imports the script via importlib; `eval/` isn't a package).
