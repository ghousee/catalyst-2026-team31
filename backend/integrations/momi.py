"""BlackWood MOMI connector: read alarm exports dropped in a folder and hand them to the watcher.

MOMI has no API. Its documented outputs are alarm email/EMS messages (custom templates with <%Alarm-Text%> etc.) and
scheduled log/history exports (`MOMI.EXE script-log=<name>`, TAB-delimited). We accept both shapes in an inbox folder:
  1. our recommended alarm template, one alarm per block of key=value lines (tool, node, state, date, time, alarm,
     action, entity, text), blank line between alarms;
  2. a log export line: date <TAB> time <TAB> node <TAB> alarm text.
Numeric fields in MOMI exports can carry a leading hard space (ASCII 160); it is stripped.

    MOMI_INBOX=data/inbox/momi   (each new file is read once, then moved to MOMI_INBOX/done)
"""
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from backend import settings

ACTION_SEVERITY = {"ACT-CRITICAL": "critical", "ACT-WARN": "warning", "ACT-INFO": "info"}


def parse_export(text):
    """MOMI export file text -> [raw alarm dicts]. Cleared alarms (state=CLEARED) are skipped. Pure."""
    text = (text or "").replace("\xa0", " ")
    out = []
    if "=" in text.split("\n", 1)[0]:  # key=value alarm blocks
        for block in text.replace("\r", "").split("\n\n"):
            kv = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
            kv = {k.strip().lower(): v.strip() for k, v in kv.items()}
            if not kv.get("text") or kv.get("state", "SET").upper() == "CLEARED":
                continue
            out.append({"tool": "momi", "ext_id": f"{kv.get('date')} {kv.get('time')} {kv.get('alarm')} {kv.get('entity')}",
                        "node_text": kv.get("node"), "category": None, "text": kv["text"],
                        "severity": ACTION_SEVERITY.get(kv.get("action", "").upper(), "warning"),
                        "ts": f"{kv['date']}T{kv['time']}Z" if kv.get("date") and kv.get("time") else None})
        return out
    for line in text.splitlines():  # TAB-delimited log export
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 4 or not parts[3]:
            continue
        out.append({"tool": "momi", "ext_id": line.strip(), "node_text": parts[2], "category": None, "text": parts[3],
                    "severity": "warning", "ts": f"{parts[0]}T{parts[1]}Z"})
    return out


class InboxReader:
    def __init__(self, deliver):
        self.deliver = deliver
        self.inbox = Path(os.getenv("MOMI_INBOX", settings.ROOT / "data" / "inbox" / "momi"))
        self.every = float(os.getenv("MOMI_EVERY", "5"))
        self.status = {"tool": "BlackWood MOMI", "mode": "alarm export folder", "target": str(self.inbox),
                       "every_s": self.every, "last_poll": None, "received": 0, "last_error": None, "running": False}

    def read_once(self):
        try:
            (self.inbox / "done").mkdir(parents=True, exist_ok=True)
            for f in sorted(self.inbox.glob("*.txt")):
                alarms = parse_export(f.read_text(encoding="utf-8", errors="replace"))
                for a in alarms:
                    self.deliver(a)
                self.status["received"] += len(alarms)
                f.replace(self.inbox / "done" / f.name)
            self.status.update(last_poll=datetime.now(timezone.utc).isoformat(timespec="seconds"), last_error=None)
        except Exception as e:
            self.status["last_error"] = str(e)[:200]

    def start(self):
        self.status["running"] = True

        def loop():
            while True:
                self.read_once()
                time.sleep(self.every)

        threading.Thread(target=loop, daemon=True, name="momi-inbox").start()
