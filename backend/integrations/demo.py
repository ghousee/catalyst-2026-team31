"""Demo stand-ins for the monitoring tools, so the real connectors have something to read without a customer system.

- Prognosis: a local endpoint returning open problems in the dataset shape the poller expects (prognosis.FIELDS).
  Pointing PROGNOSIS_URL at a real Prognosis Web UI replaces it with no code change.
- MOMI: writes an alarm export file into the inbox folder the reader watches, in MOMI's documented template shape.
Samples quote real message numbers from the ingested manuals. All synthetic.
"""
import threading
import uuid
from datetime import datetime, timezone

from backend.pipeline.answer import _rows, connect

_lock = threading.Lock()
OPEN_PROBLEMS = []  # what the stand-in Prognosis dataset currently returns

PROGNOSIS_SAMPLES = {
    "audit": ("\\PROD", "TMF", "Major", "TMF 185: audit file $AUDIT.ZTMFAT.AA000409 is pinned by an active transaction"),
    "pathway": ("\\PROD", "PATHWAY", "Major", "PATHWAY 1034: no server available for server class SETTLE-SC"),
    "cpu": ("\\PROD", "CPU", "Critical", "CPU 101: processor 2 down, backup processes taking over on processor 3"),
    "dr_audit": ("\\DR", "TMF", "Minor", "TMF 185: audit file $AUDIT.ZTMFAT.AA000212 is pinned (DR replication)"),
}
MOMI_SAMPLES = {
    "disk": ("PROD1", "ACT-CRITICAL", "DISK STATE [$DATA01]", "$DATA01", "DISK 5032: $DATA01 mirror drive down, volume running unprotected"),
    "frozen": ("PROD1", "ACT-WARN", "EMS PATHWAY [SETTLE-SC]", "SETTLE-SC", "PATHWAY 1061: server class SETTLE-SC is frozen"),
    "path": ("PROD1", "ACT-WARN", "EMS DISK [$DATA01]", "$DATA01", "DISK 5015: path error on $DATA01 mirror path"),
}


def any_manual_message():
    """A random numbered message from the manuals that has no curated notes: shows that any message maps to its section."""
    with connect() as conn:
        r = _rows(conn, "SELECT e.name, d.section FROM entity e JOIN edge x ON x.dst = e.id AND x.rel = 'about' "
                        "JOIN doc_chunk d ON d.id = x.src WHERE e.id LIKE 'evt:auto:tmf:%%' ORDER BY random() LIMIT 1")
    if not r:
        return None
    n = r[0]["name"].split()[-1].lstrip("0") or "0"
    title = r[0]["section"].split(">")[-1].split("(")[0].strip()
    text = f"TMF {n}: {title}" if title and not title.lower().startswith("message") else f"TMF {n} raised by the TMF subsystem"
    return ("\\PROD", "TMF", "Minor", text)


def add_problem(sample):
    spec = any_manual_message() if sample == "any" else PROGNOSIS_SAMPLES.get(sample)
    if not spec:
        raise ValueError(f"unknown sample {sample}")
    node, cat, sev, text = spec
    row = {"ProblemId": f"P-{uuid.uuid4().hex[:6]}", "NodeName": node, "Category": cat, "Severity": sev,
           "Description": text, "TimeRaised": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with _lock:
        OPEN_PROBLEMS.append(row)
    return row


def momi_file(sample, inbox):
    node, action, alarm, entity, text = MOMI_SAMPLES[sample]
    now = datetime.now(timezone.utc)
    body = (f"tool=momi\nnode={node}\nstate=SET\ndate={now:%Y-%m-%d}\ntime={now:%H:%M:%S}\nalarm={alarm}\n"
            f"action={action}\nentity={entity}\ntext={text}\nextra=\n")
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"momi_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:4]}.txt"
    path.write_text(body, encoding="utf-8")
    return str(path)


def clear():
    with _lock:
        OPEN_PROBLEMS.clear()
