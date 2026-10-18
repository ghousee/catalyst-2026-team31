"""The watcher: takes normalised events, runs the three detectors in rules.py, stores alerts, and builds the alert card
(why, what to do, manual sections, next commands, who to call) from the knowledge graph. In-memory event buffer;
alerts live in the `alert` table. Sources: POST /events (Prognosis poller / MOMI export reader later) and replay files."""
import json
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import settings
from backend.pipeline.answer import _rows, clean_title, connect
from backend.pipeline.assistant import experts_for
from backend.integrations import mapping
from backend.watcher import rules

BUFFER_HOURS = 3
REPLAYS = settings.ROOT / "data" / "replay"
SCENARIO_REPLAY = {"audit_trail_fill": "quarter_end_audit", "disk_revive_stall": "revive_stall",
                   "pathway_no_server": "pathway_no_server", "cpu_down": "cpu_down"}  # simulator page buttons
TOOL_NAMES = {"prognosis": "IR Prognosis", "momi": "BlackWood MOMI"}
NODE_DISPLAY = {"node:PROD": "\\PROD", "node:DR": "\\DR"}


def parse_event(raw, ts=None):
    """dict from JSON -> internal event (ts as datetime). Raises ValueError on a bad event."""
    if raw.get("kind") not in ("event", "metric") or not raw.get("entity") or not raw.get("node"):
        raise ValueError("event needs kind (event|metric), entity and node")
    if raw["kind"] == "metric" and raw.get("value") is None:
        raise ValueError("a metric event needs a value")
    when = ts or (datetime.fromisoformat(raw["ts"].replace("Z", "+00:00")) if raw.get("ts") else datetime.now(timezone.utc))
    return {"ts": when, "node": raw["node"], "tool": raw.get("tool", "unknown"), "kind": raw["kind"],
            "entity": raw["entity"], "value": raw.get("value"), "text": raw.get("text", "")}


class Watcher:
    def __init__(self):
        self.lock = threading.RLock()
        self.events = deque()
        self.proposals = {}  # alert id -> proposals (made once, so approval ids stay stable across polls)
        self.replay_thread = None

    # ------------------------------------------------------------ detection
    def ingest(self, ev):
        with self.lock:
            self.events.append(ev)
            while self.events and self.events[0]["ts"] < ev["ts"] - timedelta(hours=BUFFER_HOURS):
                self.events.popleft()
            evs = list(self.events)
        made = []
        with connect() as conn:
            open_keys = {(r["kind"], r["key"]) for r in _rows(
                conn, "SELECT kind, coalesce(pattern_id, entity_id) AS key FROM alert WHERE node_id = %s AND NOT acknowledged",
                (ev["node"],))}
            # an open veteran-pattern card already covers its event and metric: no separate chain/trend card for them
            for r in _rows(conn, "SELECT h.rule FROM alert a JOIN heuristic h ON h.id = a.pattern_id "
                                 "WHERE a.node_id = %s AND NOT a.acknowledged", (ev["node"],)):
                open_keys |= {(k, x) for x in (r["rule"].get("event"), r["rule"].get("metric")) if x for k in ("chain", "trend")}
            # 1. veteran patterns on this node
            for p in _rows(conn, "SELECT id, rule, system_id FROM heuristic WHERE status = 'approved' AND rule IS NOT NULL "
                                 "AND (site_id = %s OR site_id IS NULL)", (ev["node"],)):
                if ("pattern", p["id"]) in open_keys:
                    continue
                evidence = rules.check_rule(p["rule"], evs, ev["node"], ev["ts"])
                if evidence:
                    entity = p["rule"].get("event") or p["rule"]["metric"]
                    made.append(self._store(conn, "pattern", ev["node"], entity, p["id"], evidence,
                                            p["rule"].get("lead_min"), "warning"))
                    open_keys.add(("pattern", p["id"]))
                    # the veteran's card says it better: close the chain/trend cards about the same event or metric
                    covered = [x for x in (p["rule"].get("event"), p["rule"].get("metric")) if x]
                    conn.execute("UPDATE alert SET acknowledged = TRUE WHERE node_id = %s AND kind IN ('chain', 'trend') "
                                 "AND entity_id = ANY(%s) AND NOT acknowledged", (ev["node"], covered))
                    open_keys |= {("chain", x) for x in covered} | {("trend", x) for x in covered}
            # 2. graph chain: this event usually comes before something worse
            if ev["kind"] == "event" and ("chain", ev["entity"]) not in open_keys:
                nxt = _rows(conn, "SELECT dst FROM edge WHERE src = %s AND rel = 'precedes'", (ev["entity"],))
                # a veteran pattern already covering this event says more than the bare chain: don't double up
                # (and a monitoring tool's own card for it already says what usually follows)
                pattern_on_it = _rows(conn, "SELECT 1 FROM alert WHERE node_id = %s AND NOT acknowledged AND entity_id = %s "
                                            "AND kind IN ('pattern', 'tool')", (ev["node"], ev["entity"]))
                if nxt and not pattern_on_it:
                    made.append(self._store(conn, "chain", ev["node"], ev["entity"], None,
                                            [{"event": ev["entity"], "count": 1}], None, "info"))
            # 3. metric trend toward a hard limit
            if ev["kind"] == "metric" and ev["entity"] in rules.TREND_LIMITS:
                hit = rules.check_trend(evs, ev["entity"], ev["node"])
                if hit:
                    evidence, eta = hit
                    sev = "critical" if eta <= rules.TREND_CRITICAL_MIN else "warning"
                    if ("trend", ev["entity"]) in open_keys:  # keep the countdown current
                        conn.execute("UPDATE alert SET lead_min = %s, severity = %s, signal = %s WHERE node_id = %s AND kind = 'trend' "
                                     "AND entity_id = %s AND NOT acknowledged", (round(eta), sev, json.dumps(evidence), ev["node"], ev["entity"]))
                    else:
                        made.append(self._store(conn, "trend", ev["node"], ev["entity"], None, evidence, round(eta), sev))
            conn.commit()
        return made

    def ingest_alarm(self, raw):
        """A monitoring tool's own alarm (backend/integrations): show it as a card right away, mapped onto Synapse so
        its steps are already linked, and feed it on as an event so veteran patterns and graph chains see it too.
        An alarm whose node cannot be read is dropped, never guessed (context safety)."""
        node = mapping.node_id(raw.get("node_text"))
        if not node:
            return []
        with connect() as conn:
            entity = mapping.entity_for(conn, raw["text"], raw.get("category")) or node
            made = []
            if not _rows(conn, "SELECT 1 FROM alert WHERE node_id = %s AND kind = 'tool' AND entity_id = %s AND message = %s "
                               "AND NOT acknowledged", (node, entity, raw["text"])):
                made.append(self._store(conn, "tool", node, entity, None, [{"event": entity, "count": 1, "source": raw["tool"]}],
                                        None, raw.get("severity") or "warning", message=raw["text"]))
            conn.commit()
        if entity.startswith("evt:"):
            made += self.ingest(parse_event({"node": node, "kind": "event", "entity": entity, "tool": raw["tool"], "text": raw["text"]}))
        return made

    @staticmethod
    def _store(conn, kind, node, entity, pattern_id, evidence, lead_min, severity, message=""):
        aid = f"al-{uuid.uuid4().hex[:6]}"
        conn.execute("INSERT INTO alert (id, entity_id, pattern_id, probability, message, signal, node_id, kind, severity, lead_min) "
                     "VALUES (%s,%s,%s,1.0,%s,%s,%s,%s,%s,%s)",
                     (aid, entity, pattern_id, message, json.dumps(evidence), node, kind, severity, lead_min))
        return aid

    def reset(self):
        with self.lock:
            self.events.clear()
            self.proposals.clear()
        with connect() as conn:
            conn.execute("DELETE FROM alert")
            conn.commit()

    # ------------------------------------------------------------ replay (the demo feed; same path as a live source)
    def start_replay(self, name, speed=30.0):
        path = REPLAYS / f"{name}.jsonl"
        if not path.exists():
            raise ValueError(f"no replay {name}")
        lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
        self.reset()

        def run():
            base, wall0 = datetime.now(timezone.utc), time.monotonic()
            for raw in lines:  # t = seconds into the incident; played `speed` times faster
                delay = raw["t"] / speed - (time.monotonic() - wall0)
                if delay > 0:
                    time.sleep(delay)
                self.ingest(parse_event(raw, ts=base + timedelta(seconds=raw["t"])))

        self.replay_thread = threading.Thread(target=run, daemon=True, name=f"replay-{name}")
        self.replay_thread.start()
        return {"status": "running", "replay": name, "events": len(lines), "speed": speed}

    # ------------------------------------------------------------ the alert card
    def alerts(self, node, propose):
        """Open alerts for a node, newest first, in the UI's Alert shape. `propose(entity_id, node)` -> proposal or None."""
        with connect() as conn:
            rows = _rows(conn, "SELECT * FROM alert WHERE (node_id = %s OR %s = 'all') AND NOT acknowledged ORDER BY ts DESC",
                         (node, node))
            cards = [self._card(conn, r, propose) for r in rows]  # newest first ...
        rank = {"High": 0, "Medium": 1, "Low": 2}
        return sorted(cards, key=lambda c: rank[c["priority"]])  # ... within High, then Medium, then Low (stable sort)

    def _card(self, conn, a, propose):
        ent = {r["id"]: r for r in _rows(conn, "SELECT id, name, parent_id FROM entity WHERE id = %s", (a["entity_id"],))}.get(
            a["entity_id"], {"name": a["entity_id"], "parent_id": None})
        sub = ent["parent_id"] or ""
        node_ok = "(h.site_id = %s OR h.site_id IS NULL) AND h.status = 'approved'"
        owner, notes = None, []
        if a["pattern_id"]:
            notes = _rows(conn, f"SELECT h.*, p.name AS owner_name FROM heuristic h JOIN person p ON p.id = h.owner_id "
                                f"WHERE h.id = %s AND {node_ok}", (a["pattern_id"], a["node_id"]))
            owner = notes[0] if notes else None
            sub = owner["system_id"] if owner else sub
        else:  # chain/trend: the veteran notes the graph links to this event or metric, or to what usually comes next
            ids = [a["entity_id"]] + [r["dst"] for r in _rows(
                conn, "SELECT dst FROM edge WHERE src = %s AND rel = 'precedes'", (a["entity_id"],))]
            notes = _rows(conn, f"SELECT DISTINCT h.*, p.name AS owner_name FROM edge e JOIN heuristic h ON h.id IN (e.src, e.dst) "
                                f"JOIN person p ON p.id = h.owner_id WHERE ((e.dst = ANY(%s) AND e.rel = 'about') OR "
                                f"(e.src = ANY(%s) AND e.rel = 'fixed_by')) AND {node_ok} ORDER BY h.kind DESC, h.id LIMIT 2",
                          (ids, ids, a["node_id"]))
        claims = []
        for n in notes:
            claims.append({"text": n["call_text"], "lane": "veteran", "source_id": n["id"], "verified": True, "score": 1.0, "verbatim": True})
            if n["why_text"]:
                claims.append({"text": f"Why: {n['why_text']}", "lane": "veteran", "source_id": n["id"], "verified": True, "score": 1.0, "verbatim": True})
            if n["not_when_text"]:
                claims.append({"text": f"Not when: {n['not_when_text']}", "lane": "veteran", "source_id": n["id"], "verified": True, "score": 1.0, "verbatim": True})
        note_ids = [n["id"] for n in notes]
        # manual sections: how to fix / diagnose it, the ones the notes extend, and the section the message comes from
        docs = _rows(conn, "SELECT d.id, d.section FROM doc_chunk d WHERE d.id IN ("
                           "SELECT dst FROM edge WHERE src = %s AND rel IN ('fixed_by', 'diagnosed_by') "
                           "UNION SELECT dst FROM edge WHERE src = ANY(%s) AND rel = 'extends' "
                           "UNION SELECT src FROM edge WHERE dst = %s AND rel = 'about' AND src LIKE 'doc:%%') "
                           "ORDER BY d.id LIMIT 3", (a["entity_id"], note_ids, a["entity_id"]))
        claims += [{"text": f"Manual: {clean_title(d['section'])}", "lane": "doc", "source_id": d["id"], "verified": True, "score": 1.0}
                   for d in docs]

        with self.lock:
            if a["id"] not in self.proposals:
                cmds = _rows(conn, "SELECT dst FROM edge WHERE src = %s AND rel = 'diagnosed_by' AND dst LIKE 'cmd:%%' ORDER BY dst LIMIT 2",
                             (a["entity_id"],))
                self.proposals[a["id"]] = [p for p in (propose(c["dst"], a["node_id"]) for c in cmds) if p]
            next_commands = self.proposals[a["id"]]

        exclude = owner["owner_id"] if owner else None
        ok = lambda e: e["id"] != exclude and e["availability"] != "retired"
        # an expert in this subsystem, else anyone available (the pattern's owner may be the only expert)
        backups = [e for e in experts_for(conn, [sub] if sub else [], set()) if ok(e)] or \
                  [e for e in experts_for(conn, [], set()) if ok(e)]
        evidence = a["signal"] or []
        source = evidence[0].get("source") if evidence else None
        what = label(ent["name"])
        if a["kind"] == "pattern" and owner:
            first = owner["owner_name"].split(" ")[0]
            lead = f" (about {a['lead_min']} min before failure in {first}'s experience)" if a["lead_min"] else ""
            message = f"{first}'s warning pattern matched: {owner['trigger_text'].split('.')[0]}{lead}"
        elif a["kind"] == "tool":
            nxt = _rows(conn, "SELECT x.name FROM edge e JOIN entity x ON x.id = e.dst WHERE e.src = %s AND e.rel = 'precedes'", (a["entity_id"],))
            follows = f" Usually comes before {', '.join(r['name'] for r in nxt)}." if nxt else ""
            message = f"{TOOL_NAMES.get(source, source)}: {a['message']}.{follows}"
        elif a["kind"] == "chain":
            nxt = _rows(conn, "SELECT x.name FROM edge e JOIN entity x ON x.id = e.dst WHERE e.src = %s AND e.rel = 'precedes'", (a["entity_id"],))
            message = f"{what} seen. In the knowledge graph it usually comes before {', '.join(r['name'] for r in nxt)}."
        else:
            message = f"{what} is at {evidence[0]['value'] if evidence else '?'} and rising: at this rate it reaches the limit in about {a['lead_min']} min."
        leads_to = [r["dst"] for r in _rows(conn, "SELECT dst FROM edge WHERE src = %s AND rel = 'precedes'", (a["entity_id"],))]
        if owner and owner.get("rule"):
            leads_to += [x for x in (owner["rule"].get("event"),) if x]
            leads_to += [r["dst"] for r in _rows(conn, "SELECT dst FROM edge WHERE src = %s AND rel = 'about' AND dst LIKE 'evt:%%'",
                                                 (owner["id"],))]
        level, reasons = rules.priority(a["kind"], a["node_id"], a["entity_id"], leads_to, a["lead_min"], a["severity"])
        return {
            "id": a["id"], "ts": a["ts"].isoformat().replace("+00:00", "Z"), "node": NODE_DISPLAY.get(a["node_id"], a["node_id"]),
            "priority": level, "priority_reasons": reasons,
            "subsystem": sub.replace("sub:", "") or "-", "kind": a["kind"], "pattern_id": a["pattern_id"],
            "source_tool": TOOL_NAMES.get(source, source) if source else None,
            "owner": owner["owner_id"] if owner else None, "owner_name": owner["owner_name"] if owner else None,
            "severity": {"High": "critical", "Medium": "warning", "Low": "info"}[level],
            "lead_time_min": a["lead_min"], "message": message,
            "evidence": [{**{k: v for k, v in e.items() if k != "source"}, **({"event": _name(conn, e["event"])} if e.get("event") else {}),
                          **({"metric": e["metric"].replace("met:", "")} if e.get("metric") else {})} for e in evidence],
            "fix_claims": claims, "next_commands": next_commands, "backtest": None,
            "backup_expert": backups[0] if backups else None,
        }


def label(name):
    """'audit-capacity-pct (audit trail capacity used)' -> 'Audit trail capacity used'; other names unchanged."""
    if "(" in name and name.endswith(")"):
        inner = name[name.index("(") + 1:-1]
        return inner[:1].upper() + inner[1:]
    return name


def series(node, metric, n=120):
    """Recent [(iso ts, value)] for a metric from the watcher buffer (what the replay or a live source has sent)."""
    with watcher.lock:
        pts = [(e["ts"], e["value"]) for e in watcher.events
               if e["kind"] == "metric" and e["entity"] == metric and e["node"] == node]
    return [[ts.isoformat().replace("+00:00", "Z"), v] for ts, v in pts[-n:]]


def _name(conn, entity_id):
    r = _rows(conn, "SELECT name FROM entity WHERE id = %s", (entity_id,))
    return r[0]["name"].split(" - ")[0] if r else entity_id


def replays():
    return sorted(p.stem for p in Path(REPLAYS).glob("*.jsonl"))


watcher = Watcher()
