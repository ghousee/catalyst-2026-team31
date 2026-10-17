# tests

Run: `pytest` (config in `pytest.ini`: `pythonpath = .`, `testpaths = tests`). All unit tests are
Docker-free so the [[stop hook]] stays fast.

| File | Proves |
|---|---|
| `tests/unit/test_context_filter.py` | P-305 context never returns P-201 doc chunks/heuristics (incl. unresolved version/site, mismatched version); all-versions rows included; NULL without flag rejected; no system → ValueError. In-memory SQLite mirror of the fingerprint columns. |
| `tests/unit/test_eval_scoring.py` | contamination via source→system map; unknown source = contaminated; refer/clarify unscored; DB down → None; empty/missing golden file. |
| `tests/unit/test_smoke.py` | placeholder |

Note: SQLite mirror ≠ real Postgres. A real-Postgres check was run by hand on 2026-10-16
(not in CI). See [[todo]] for an integration test.
