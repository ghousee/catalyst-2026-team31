"""IR Prognosis connector: poll its REST API for open problems and hand new ones to the watcher.

Prognosis exposes admin-defined PQL datasets as JSON over HTTPS (`GET /Prognosis/Rest/v1/data/<dataset>`, basic auth),
and IR's own guide exposes open problems (PROBSUM) this way for ticketing tools. The exact column names depend on the
dataset the customer's admin defines, so they are configurable (FIELDS). Until we have a customer's dataset, the demo
points PROGNOSIS_URL at a local stand-in (/demo/prognosis/...) that returns the same shape.

    PROGNOSIS_URL=https://prognosis.example/Prognosis/Rest/v1/data/OpenProblems
    PROGNOSIS_USER=... PROGNOSIS_PASSWORD=... PROGNOSIS_EVERY=15
"""
import os
import threading
import time
from datetime import datetime, timezone

import httpx

# dataset column -> our field (edit to match the customer's RestApiDataSets.xml)
FIELDS = {"id": "ProblemId", "node": "NodeName", "category": "Category", "text": "Description",
          "severity": "Severity", "ts": "TimeRaised"}
SEVERITY = {"critical": "critical", "major": "critical", "minor": "warning", "warning": "warning", "info": "info"}


def parse_rows(rows, fields=FIELDS):
    """Prognosis dataset rows -> [raw alarm dicts] (node text, category, text, severity, ext_id, ts). Rows without
    a description are skipped. Pure."""
    out = []
    for r in rows if isinstance(rows, list) else rows.get("data") or rows.get("rows") or []:
        text = str(r.get(fields["text"]) or "").strip()
        if not text:
            continue
        out.append({"tool": "prognosis", "ext_id": str(r.get(fields["id"]) or text), "node_text": r.get(fields["node"]),
                    "category": r.get(fields["category"]), "text": text,
                    "severity": SEVERITY.get(str(r.get(fields["severity"]) or "").lower(), "warning"),
                    "ts": r.get(fields["ts"])})
    return out


class Poller:
    def __init__(self, deliver):
        self.deliver = deliver  # callable(raw alarm) -> list of alert ids
        self.url = os.getenv("PROGNOSIS_URL", "http://127.0.0.1:8000/demo/prognosis/Prognosis/Rest/v1/data/OpenProblems")
        auth = (os.getenv("PROGNOSIS_USER"), os.getenv("PROGNOSIS_PASSWORD"))
        self.auth = auth if all(auth) else None
        self.every = float(os.getenv("PROGNOSIS_EVERY", "10"))
        self.seen = set()
        self.status = {"tool": "IR Prognosis", "mode": "REST API poll", "target": self.url, "every_s": self.every,
                       "last_poll": None, "received": 0, "last_error": None, "running": False}

    def poll_once(self):
        try:
            r = httpx.get(self.url, auth=self.auth, timeout=10, verify=os.getenv("PROGNOSIS_VERIFY_TLS", "1") == "1")
            r.raise_for_status()
            new = [a for a in parse_rows(r.json()) if a["ext_id"] not in self.seen]
            for a in new:
                self.seen.add(a["ext_id"])
                self.deliver(a)
            self.status.update(last_poll=datetime.now(timezone.utc).isoformat(timespec="seconds"), last_error=None)
            self.status["received"] += len(new)
        except Exception as e:  # keep polling; show the error on the Alerts page
            self.status["last_error"] = str(e)[:200]

    def start(self):
        self.status["running"] = True

        def loop():
            time.sleep(5)  # let the API finish starting (the demo stand-in is served by this same process)
            while True:
                self.poll_once()
                time.sleep(self.every)

        threading.Thread(target=loop, daemon=True, name="prognosis-poller").start()
