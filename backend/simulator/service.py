"""Small, deterministic simulator for command output and health metrics.

This module never connects to a NonStop system.  Every response is synthetic and
exists only to exercise the approval workflow described in the system design.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


SCENARIOS = {"audit_trail_fill", "disk_revive_stall", "pathway_no_server", "cpu_down"}
NODES = {"node:PROD": "\\PROD", "node:DR": "\\DR"}


@dataclass(frozen=True)
class Run:
    run_id: str
    template_id: str
    command: str
    node_id: str
    ts: str
    output: str


class Simulator:
    """Thread-safe, in-memory state for one local demonstration."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.RLock()
        self._scenario: str | None = None
        self._scenario_started = 0.0
        self._speed = 1.0
        self._run_counter = 42
        self._runs: dict[str, Run] = {}

    def reset(self) -> None:
        with self._lock:
            self._scenario = None
            self._scenario_started = 0.0
            self._speed = 1.0
            self._run_counter = 42
            self._runs.clear()

    def start_scenario(self, scenario: str, speed: float) -> dict:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario}")
        if not 0 < speed <= 100:
            raise ValueError("speed must be greater than 0 and at most 100")
        with self._lock:
            self._scenario = scenario
            self._scenario_started = self._clock()
            self._speed = speed
        return {"status": "running"}

    def preview(self, template_id: str, command: str, node_id: str) -> dict:
        node = self._node(node_id)
        if template_id == "tmfcom.abort_transaction":
            transid = self._transid(node)
            return {
                "expected_output": f"Transaction {transid} would be aborted.\nBackout of approximately 1 settlement batch.",
                "blast_radius": [
                    {"entity": "Pathway SETTLE-SC", "effect": "will retry 1 simulated batch"},
                    {"entity": "Audit trail $AUDIT", "effect": "pinned files release after simulated backout"},
                ],
                "warnings": [
                    "Critical: aborting a transaction cannot be undone.",
                    "Second approver required.",
                    "Simulator only: no production command will run.",
                ],
            }
        if template_id == "tmfcom.status_audittrail_detail":
            expected = "Active audit trail capacity used: nn%\nFirst pinned file: <file>\nReason: <pin reason>"
        elif template_id == "tmfcom.status_transaction":
            expected = "Transid                 State    Age      Process\n<transid>               ACTIVE   hh:mm    <owner>"
        elif template_id == "scf.status_disk_detail":
            expected = f"STORAGE - Detailed Status DISK {node}.$DATA01\nState, primary/mirror path and revive status"
        elif template_id == "peek.cpu":
            expected = "CPU 2 busy percentage, ready queue length and memory used"
        else:
            expected = f"Synthetic read-only output for: {command}"
        return {"expected_output": expected, "blast_radius": [], "warnings": ["Simulator only: no production command will run."]}

    def execute(self, template_id: str, command: str, node_id: str) -> dict:
        node = self._node(node_id)
        output = self._output(template_id, command, node)
        with self._lock:
            run_id = f"run:c{self._run_counter}"
            self._run_counter += 1
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            run = Run(run_id, template_id, command, node_id, ts, output)
            self._runs[run_id] = run
        return {"run_id": run_id, "output": output, "ts": ts, "source_id": run_id}

    def source_card(self, run_id: str) -> dict | None:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            return None
        excerpt = next((line.strip() for line in run.output.splitlines()[1:] if line.strip()), run.output[:160])
        return {
            "id": run.run_id,
            "kind": "live",
            "command": run.command,
            "node": self._node(run.node_id),
            "ts": run.ts,
            "excerpt": excerpt,
        }

    def last_template(self, node_id: str) -> str | None:
        with self._lock:
            runs = [run for run in self._runs.values() if run.node_id == node_id]
        return runs[-1].template_id if runs else None

    def metrics(self, node_id: str, window: str = "60m") -> dict:
        self._node(node_id)
        match = re.fullmatch(r"(\d+)(m|h)", window)
        if not match:
            raise ValueError("window must look like 60m or 2h")
        amount = int(match.group(1)) * (60 if match.group(2) == "h" else 1)
        if not 1 <= amount <= 24 * 60:
            raise ValueError("window must be between 1 minute and 24 hours")

        points = min(amount, 120)
        end = datetime.now(timezone.utc).replace(microsecond=0)
        prod = node_id == "node:PROD"
        audit_now = self._audit_capacity() if prod else 22.0

        def series(metric: str, value: Callable[[int], float]) -> dict:
            data = []
            for i in range(points):
                ts = end - timedelta(minutes=points - 1 - i)
                data.append([ts.isoformat().replace("+00:00", "Z"), round(value(i), 1)])
            return {"metric": metric, "points": data}

        denominator = max(1, points - 1)
        wobble = lambda i, phase: math.sin(i * 1.7 + phase)
        return {
            "series": [
                series(
                    "audit-capacity-pct",
                    lambda i: (41 + (audit_now - 41) * i / denominator + wobble(i, 1) * 0.5) if prod else 22 + wobble(i, 1) * 0.3,
                ),
                series("cpu-busy-time", lambda i: (52 + 12 * i / denominator + wobble(i, 2) * 3) if prod else 18 + wobble(i, 2)),
                series("request-qtime", lambda i: (12 + 16 * (i / denominator) ** 2 + wobble(i, 3)) if prod else 6 + wobble(i, 3) * 0.4),
            ]
        }

    def _audit_capacity(self) -> float:
        with self._lock:
            if self._scenario != "audit_trail_fill":
                return 62.0
            elapsed = max(0.0, self._clock() - self._scenario_started) * self._speed
        return min(99.0, 62.0 + elapsed * 0.15)

    @staticmethod
    def _node(node_id: str) -> str:
        try:
            return NODES[node_id]
        except KeyError as exc:
            raise ValueError(f"unknown node {node_id}") from exc

    @staticmethod
    def _transid(node: str) -> str:
        return f"{node}(1).3.45678"

    def _output(self, template_id: str, command: str, node: str) -> str:
        header = f"SYNTHETIC NONSTOP SIMULATOR  SYSTEM {node}\n"
        transid = self._transid(node)
        outputs = {
            "tmfcom.status_audittrail_detail": (
                "AUDITTRAIL STATUS\n"
                f"  Active audit trail capacity used: {self._audit_capacity():.0f}%\n"
                "  First pinned file:    $AUDIT.ZTMFAT.AA000409\n"
                "  Pinned reason:        long-running transaction\n"
                f"  Oldest active transid: {transid}\n"
            ),
            "tmfcom.status_transaction": (
                "TRANSACTION STATUS   (3 active)\n"
                "  Transid                 State    Age     Owner\n"
                f"  {transid}    ACTIVE   03:27   {node}.$SETL1  (SETTLE-SC batch)\n"
            ),
            "tmfcom.abort_transaction": (
                f"Transaction {transid} aborted in simulator.\n"
                "Backout complete. Audit trail capacity used: 38%\n"
            ),
            "tmfcom.status_tmf": "TMF State........ STARTED\nBEGINTRANS....... ENABLED\nActive transactions: 3\n",
            "scf.status_disk_detail": (
                f"STORAGE - Detailed Status DISK {node}.$DATA01\n"
                "  State................ STARTED\n"
                "  Primary Path......... UP     Mirror Path........ UP\n"
                "  Revive............... NONE\n"
            ),
            "peek.cpu": "CPU 2   Busy: 58%   Ready queue: 3   Memory used: 71%\n",
            "pathcom.status_tcp": "TCP        State      Waiting\n$ZTC0      RUNNING    0\n",
            "pathcom.status_term": "TERM       State      Server\n$TERM01    RUNNING    SETTLE-SC\n",
            "tacl.status_term": "$Z0A1   TERM $TERM01   RUNNING\n$Z0B2   TERM $TERM02   RUNNING\n",
            "fup.listopens": f"{node}.$DATA01.DEMO opened by {node}.$SETL1\n",
        }
        return header + outputs.get(template_id, f"Synthetic result for {command}\n")


simulator = Simulator()
