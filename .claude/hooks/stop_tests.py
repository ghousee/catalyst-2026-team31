"""Stop hook: block Claude from finishing while unit tests fail.

Exit 2 = feed stderr back to Claude so it keeps working. If this Stop was already
triggered by a previous block (stop_hook_active), exit 0 so it can never loop.
Skips when there are no tests yet. Cross-platform (Windows/macOS/Linux).
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}
    if event.get("stop_hook_active"):
        return 0
    if not list((ROOT / "tests" / "unit").glob("test_*.py")):
        return 0

    venv = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    py = str(venv) if venv.exists() else sys.executable  # project deps live in .venv
    r = subprocess.run([py, "-m", "pytest", "tests/unit", "-q"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
        print("Unit tests failing - fix before finishing:\n" + tail, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
