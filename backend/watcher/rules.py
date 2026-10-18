"""Early-warning checks. Pure functions (unit-tested); backend/watcher/engine.py feeds them events and stores alerts.

An event is the one normalised shape every source is turned into (replay file, Prognosis REST poller, MOMI export):
    {"ts": datetime, "node": "node:PROD", "tool": "prognosis", "kind": "event"|"metric",
     "entity": "evt:TMF-185" | "met:audit-capacity-pct", "value": float|None, "text": str}
Three detectors, all explainable and cited:
  pattern  a veteran's warning-pattern note with a rule (heuristic.rule), e.g. "TMF 185 twice in 30 min while audit rising"
  chain    the graph says this event usually comes before another one ('precedes' edges)
  trend    a metric heading for its limit: straight-line projection of the recent points
"""
from datetime import timedelta

TREND_LIMITS = {"met:audit-capacity-pct": 100.0}  # metrics with a hard ceiling worth projecting
TREND_WARN_MIN = 60        # warn when the projected time to the limit is under this
TREND_CRITICAL_MIN = 20
TREND_MIN_POINTS = 5


def _metric_points(events, metric, node, since=None):
    return [(e["ts"], e["value"]) for e in events
            if e["kind"] == "metric" and e["entity"] == metric and e["node"] == node and e["value"] is not None
            and (since is None or e["ts"] >= since)]


def check_rule(rule, events, node, now):
    """A veteran pattern's rule against the recent events on one node. Returns the evidence list, or None if no match."""
    if rule["type"] == "count":
        since = now - timedelta(minutes=rule["window_min"])
        hits = [e for e in events if e["kind"] == "event" and e["entity"] == rule["event"] and e["node"] == node
                and e["ts"] >= since]
        if len(hits) < rule["count"]:
            return None
        evidence = [{"event": rule["event"], "count": len(hits)}]
        if rule.get("metric"):
            pts = _metric_points(events, rule["metric"], node, since)
            if not pts or pts[-1][1] <= rule.get("above", float("-inf")):
                return None
            if rule.get("rising") and not (len(pts) >= 2 and pts[-1][1] > pts[0][1]):
                return None
            evidence.append({"metric": rule["metric"], "value": pts[-1][1], "trend": "rising" if rule.get("rising") else None})
        return evidence
    if rule["type"] == "stalled":
        pts = _metric_points(events, rule["metric"], node)
        if len(pts) < 2:
            return None
        last_ts, last_v = pts[-1]
        unchanged_since = last_ts
        for ts, v in reversed(pts):
            if v != last_v:
                break
            unchanged_since = ts
        stalled_min = (last_ts - unchanged_since).total_seconds() / 60
        if stalled_min < rule["minutes"]:
            return None
        return [{"metric": rule["metric"], "value": last_v, "trend": f"unchanged for {int(stalled_min)} min"}]
    raise ValueError(f"unknown rule type {rule['type']}")


# events that stop or block transactions: reaching one of these is the failure the warnings are about
IMPACT = {"evt:TMF-187": "audit trail critically full", "evt:TMF-109": "BEGINTRANS disabled (no new transactions)",
          "evt:PATHWAY-1034": "no server available (requests fail)", "evt:DISK-5032": "mirror drive down",
          "evt:CPU-101": "a processor is down"}


def priority(kind, node, entity, leads_to, lead_min, tool_severity):
    """High / Medium / Low with the reasons, from what the graph knows. Pure. Points:
    +2 production node, +2 the entity is (or usually leads to) a transaction-stopping event, +1 a veteran's pattern
    matched, +1 failure expected within 30 min, +1 the monitoring tool itself says critical. High >= 4, Medium 2-3."""
    pts, why = 0, []
    if node == "node:PROD":
        pts += 2
        why.append("on production (\\PROD)")
    hit = entity if entity in IMPACT else next((x for x in leads_to if x in IMPACT), None)
    if hit:
        pts += 2
        why.append(IMPACT[hit] if hit == entity else f"usually leads to {IMPACT[hit]}")
    if kind == "pattern":
        pts += 1
        why.append("a veteran has seen this go wrong before")
    if lead_min is not None and lead_min <= 30:
        pts += 1
        why.append(f"failure expected in about {lead_min} min")
    if tool_severity == "critical":
        pts += 1
        why.append("the monitoring tool marks it critical")
    level = "High" if pts >= 4 else "Medium" if pts >= 2 else "Low"
    return level, why


def check_rule_shape(rule):
    """Validate a rule before it is stored (POST /knowledge). Raises ValueError."""
    need = {"count": ("event", "count", "window_min"), "stalled": ("metric", "minutes")}
    if not isinstance(rule, dict) or rule.get("type") not in need:
        raise ValueError("rule.type must be count or stalled")
    missing = [k for k in need[rule["type"]] if k not in rule]
    if missing:
        raise ValueError(f"rule is missing {', '.join(missing)}")


def trend_eta(points, limit):
    """Minutes until a straight-line fit of [(ts, value)] reaches `limit`; None if flat, falling or too few points."""
    if len(points) < TREND_MIN_POINTS:
        return None
    t0 = points[0][0]
    xs = [(ts - t0).total_seconds() / 60 for ts, _ in points]
    ys = [v for _, v in points]
    n, mx, my = len(xs), sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var  # units per minute
    if slope <= 0:
        return None
    return max(0.0, (limit - ys[-1]) / slope)


def check_trend(events, metric, node):
    """(evidence, eta_min) when the metric is projected to hit its limit within TREND_WARN_MIN, else None."""
    pts = _metric_points(events, metric, node)[-30:]
    eta = trend_eta(pts, TREND_LIMITS[metric])
    if eta is None or eta > TREND_WARN_MIN:
        return None
    return [{"metric": metric, "value": pts[-1][1], "trend": "rising"}], eta
