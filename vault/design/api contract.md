# api contract

Source of truth: `docs/API_CONTRACT.md`. The UI builds against it — change it only deliberately.

Gotchas (fixed 2026-10-16):
- `/chat` accepts optional `ablation` (default 4); UI never sends it. Used by [[eval harness]].
- `answer` and `refer` share the same `context` shape (system, version, site, display, confidence);
  `clarify` has none.
- `answer.answer_log_id` → sent back on `/feedback`.

Will change once [[system design]] for the NonStop domain lands (command proposals + approval).
