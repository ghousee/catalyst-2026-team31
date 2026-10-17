# stop hook

File: `.claude/hooks/stop_tests.py` (main at line 15). Wired in `.claude/settings.json` as
`python .claude/hooks/stop_tests.py`.

- Reads hook JSON from stdin; `stop_hook_active: true` → exit 0 (prevents infinite loop).
- No `tests/unit/test_*.py` → exit 0.
- Runs `pytest tests/unit -q` with `.venv` python if present (else current interpreter) from repo root; failure → exit 2 + last 25 lines on stderr.
- ASCII only in messages (Windows console mangles `—`).

Needs the venv active when Claude Code starts, else `python` may lack pytest.
See [[ADR-003 python stop hook]].
