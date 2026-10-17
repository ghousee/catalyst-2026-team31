# commands

Allowlisted command workflow for the simulator; no production connector or generic executor exists.

## Entry points
- `backend/commands/service.py:52` loads command entities from `kg/seed/entities.yaml`; risk and source citation are mandatory.
- `CommandService.propose()` selects within the locked subsystem, renders demo slots, and records node/RVU guards.
- `dryrun()` delegates to the simulator without creating a run. `approve()` enforces node, typed-node, and distinct-second-approver rules. `execute()` requires a single-use approval.
- `backend/api/main.py` exposes `/commands/propose`, `/commands/{id}/dryrun`, `/approve`, and `/execute`.

## Invariants
- Unknown intent returns `no_template: true`; operator text is never emitted as a command.
- Risk comes from the catalog, never the LLM or question.
- All execution is synthetic and in-memory. Changing the session node invalidates execution.
