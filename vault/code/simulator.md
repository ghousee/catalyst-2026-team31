# simulator

Deterministic, in-memory NonStop-shaped demo data. It does not connect to HPE NonStop.

## Entry points
- `backend/simulator/service.py:37` holds scenario, command-run, and metric state.
- `start_scenario()` validates one of four design scenarios and a bounded replay speed.
- `preview()` and `execute()` return explicitly synthetic output; completed runs become `live` source cards.
- `metrics()` returns bounded 1m-24h series for the health panel; the audit-fill scenario raises only `\\PROD` audit capacity.
- API: `POST /simulator/scenario`, `GET /metrics`, and live lookup through `GET /sources/{run_id}`.

## Gotchas
- State is process-local and intentionally resets on API restart.
- Timestamps are real UTC; values and platform output are fictional demo fixtures.
