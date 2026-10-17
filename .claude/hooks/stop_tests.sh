#!/usr/bin/env bash
# Blocks Claude from finishing while unit tests fail (exit 2 = feed stderr back to Claude).
# Skips if there are no tests yet.
if ! ls tests/unit/test_*.py >/dev/null 2>&1; then exit 0; fi
out=$(python -m pytest tests/unit -q 2>&1)
if [ $? -ne 0 ]; then
  echo "Unit tests failing — fix before finishing:" >&2
  echo "$out" | tail -n 25 >&2
  exit 2
fi
exit 0
