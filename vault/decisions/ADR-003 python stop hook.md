# ADR-003 python stop hook

**Date:** 2026-10-16 · **Status:** accepted

**Context:** bash hook needed bash on PATH (Windows dev box) and re-blocked forever when Claude
couldn't fix a test.

**Decision:** Python hook; exit 0 when `stop_hook_active` is true, so it blocks at most once per stop.

Code: [[stop hook]].
