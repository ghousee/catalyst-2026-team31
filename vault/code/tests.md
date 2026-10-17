# tests

Run: `pytest` (config in `pytest.ini`: `pythonpath = .`, `testpaths = tests`). All unit tests are
Docker-free so the [[stop hook]] stays fast.

| File | Proves |
|---|---|
| `tests/unit/test_context_filter.py` | P-305 context never returns P-201 doc chunks/heuristics (incl. unresolved version/site, mismatched version); all-versions rows included; NULL without flag rejected; no system → ValueError. In-memory SQLite mirror of the fingerprint columns. |
| `tests/unit/test_eval_scoring.py` | contamination via source→system map; unknown source = contaminated; refer/clarify unscored; DB down → None; empty/missing golden file. |
| `tests/unit/test_chunker.py` | [[ingest]] chunker on synthetic text: TOC page dropped, TOC titles/message numbers (1-4 digits) become sections, page numbers vs message numbers, oversized split <= 800 est. tokens, tiny merge, generic headings qualified by parent. |
| `tests/unit/test_retrieve_search.py` | `query_terms` stop words/tokens (#FUNC, $DISK, 3123), OR query text, RRF fusion and tie order. |
| `tests/unit/test_generate_gate_verify.py` | claim JSON parsing, `keep_cited` drops uncited claims, S1..Sn alias round-trip, gate parse (truncated JSON = no verdict), MiniCheck windows. |
| `tests/unit/test_graph_query.py` | [[graph]]: alias/stem/event-number resolution, subsystem tie -> None, walk depth/hubs, `lookup` on a SQLite mirror: \PROD note never returned (or cited) for \DR, drafts hidden, unresolved node gets no node-scoped notes, manuals apply to all series, commands scoped to subsystem, seed files consistent. |
| `tests/unit/test_smoke.py` | placeholder |

Note: SQLite mirror ≠ real Postgres. A real-Postgres check was run by hand on 2026-10-16
(not in CI). See [[todo]] for an integration test.
