"""Map a monitoring tool's alarm onto Synapse: which node, and which graph entity (so the steps are already linked).

Tools quote EMS subsystem + message number in their alarm text ("TMF 185", "PATHWAY 1034", "DISK 5032"). Curated
events (evt:TMF-185) carry veteran notes, commands and manual sections; every other message number found in the
manuals has an auto-extracted entity ("TMFCOM message 185") linked to its manual section.
`node_id`, `message_refs` are pure (unit-tested); `entity_for` looks the refs up in the graph.
"""
import re

from backend.pipeline.answer import _rows

# word in alarm text -> (curated event prefix, auto-extracted name prefixes)
SUBSYSTEMS = {
    "TMF": ("TMF", ("TMFCOM", "TMF")), "TMFCOM": ("TMF", ("TMFCOM", "TMF")),
    "PATHWAY": ("PATHWAY", ("PATHCOM", "PATHWAY")), "PATHCOM": ("PATHWAY", ("PATHCOM", "PATHWAY")),
    "DISK": ("DISK", ("SCF",)), "SCF": ("DISK", ("SCF",)), "STORAGE": ("DISK", ("SCF",)),
    "CPU": ("CPU", ()), "MEASCOM": (None, ("MEASCOM",)), "MEASURE": (None, ("MEASCOM",)), "TACL": (None, ("TACL",)),
}
REF = re.compile(r"\b(" + "|".join(SUBSYSTEMS) + r")[\s:#-]*(\d{1,5})\b", re.I)
# metric-style alarms (no message number), e.g. MOMI "File $x is 81% full", Prognosis "audit trail capacity"
METRIC_HINTS = [(re.compile(r"audit\s*trail.*(capacity|full)|audit.capacity", re.I), "met:audit-capacity-pct"),
                (re.compile(r"cpu.*busy|busy.*cpu", re.I), "met:cpu-busy-time"),
                (re.compile(r"revive", re.I), "met:revive-current-sector")]
CATEGORY = {"TMF": "sub:TMF", "PATHWAY": "sub:PATHWAY", "DISK": "sub:SCF-STORAGE", "STORAGE": "sub:SCF-STORAGE",
            "SCF": "sub:SCF-STORAGE", "CPU": "sub:PEEK", "PROCESS": "sub:PEEK", "TACL": "sub:TACL", "FUP": "sub:FUP",
            "MEASURE": "sub:MEASURE"}


def node_id(text):
    """'\\PROD', 'PROD1', 'prod' -> 'node:PROD'; '\\DR' -> 'node:DR'; anything else -> None."""
    s = (text or "").strip().lstrip("\\").upper()
    return "node:DR" if s.startswith("DR") else "node:PROD" if s.startswith("PROD") else None


def message_refs(text):
    """[(WORD, number)] quoted in an alarm text, in order, e.g. 'TMF 185 ... PATHWAY 1034' -> [('TMF', 185), ('PATHWAY', 1034)]."""
    return [(m.group(1).upper(), int(m.group(2))) for m in REF.finditer(text or "")]


def entity_for(conn, text, category=None):
    """The best graph entity for an alarm: curated event, else auto-extracted message, else a metric, else its subsystem."""
    for word, n in message_refs(text):
        curated, auto_prefixes = SUBSYSTEMS[word]
        if curated and _rows(conn, "SELECT 1 FROM entity WHERE id = %s", (f"evt:{curated}-{n}",)):
            return f"evt:{curated}-{n}"
        for prefix in auto_prefixes:
            r = _rows(conn, "SELECT id FROM entity WHERE kind = 'event' AND name ~* %s LIMIT 1", (rf"^{prefix} message 0*{n}$",))
            if r:
                return r[0]["id"]
    for pattern, metric in METRIC_HINTS:
        if pattern.search(text or ""):
            return metric
    return CATEGORY.get((category or "").upper())
