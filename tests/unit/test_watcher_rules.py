"""Early-warning detectors (backend/watcher/rules.py): veteran pattern rules, metric trend projection. No DB."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.watcher import rules
from backend.watcher.engine import parse_event

T0 = datetime(2026, 10, 17, 2, 0, tzinfo=timezone.utc)
MARIA = {"type": "count", "event": "evt:TMF-185", "count": 2, "window_min": 30,
         "metric": "met:audit-capacity-pct", "above": 60, "rising": True, "lead_min": 40}


def ev(minute, entity, value=None, node="node:PROD"):
    return {"ts": T0 + timedelta(minutes=minute), "node": node, "tool": "t", "kind": "metric" if value is not None else "event",
            "entity": entity, "value": value, "text": ""}


def audit(minutes, start=58.0, step=0.6, node="node:PROD"):
    return [ev(m, "met:audit-capacity-pct", round(start + step * m, 1), node) for m in minutes]


def test_maria_pattern_fires_on_second_185_while_audit_rising():
    evs = audit(range(0, 26)) + [ev(10, "evt:TMF-185"), ev(25, "evt:TMF-185")]
    evidence = rules.check_rule(MARIA, evs, "node:PROD", T0 + timedelta(minutes=25))
    assert evidence[0] == {"event": "evt:TMF-185", "count": 2}
    assert evidence[1]["metric"] == "met:audit-capacity-pct" and evidence[1]["trend"] == "rising"


def test_maria_pattern_needs_two_within_window():
    evs = audit(range(0, 50)) + [ev(5, "evt:TMF-185"), ev(45, "evt:TMF-185")]  # 40 min apart
    assert rules.check_rule(MARIA, evs, "node:PROD", T0 + timedelta(minutes=45)) is None


def test_maria_pattern_needs_audit_above_60_and_rising():
    flat = [ev(m, "met:audit-capacity-pct", 70.0) for m in range(0, 26)] + [ev(10, "evt:TMF-185"), ev(25, "evt:TMF-185")]
    low = audit(range(0, 26), start=30) + [ev(10, "evt:TMF-185"), ev(25, "evt:TMF-185")]
    assert rules.check_rule(MARIA, flat, "node:PROD", T0 + timedelta(minutes=25)) is None
    assert rules.check_rule(MARIA, low, "node:PROD", T0 + timedelta(minutes=25)) is None


def test_pattern_never_uses_another_nodes_events():
    evs = audit(range(0, 26), node="node:DR") + [ev(10, "evt:TMF-185", node="node:DR"), ev(25, "evt:TMF-185", node="node:DR")]
    assert rules.check_rule(MARIA, evs, "node:PROD", T0 + timedelta(minutes=25)) is None


def test_stalled_revive():
    rule = {"type": "stalled", "metric": "met:revive-current-sector", "minutes": 10}
    climbing = [ev(m, "met:revive-current-sector", 1000 + 400 * m) for m in range(0, 6)]
    stuck = [ev(m, "met:revive-current-sector", 3000) for m in range(6, 17)]
    assert rules.check_rule(rule, climbing + stuck[:5], "node:PROD", T0) is None  # stuck 4 min
    out = rules.check_rule(rule, climbing + stuck, "node:PROD", T0)
    assert out[0]["value"] == 3000 and "unchanged for" in out[0]["trend"]


def test_trend_eta_straight_line():
    pts = [(T0 + timedelta(minutes=m), 40 + 1.0 * m) for m in range(10)]  # 49 at the end, +1/min
    assert rules.trend_eta(pts, 100) == pytest.approx(51)
    assert rules.trend_eta([(T0 + timedelta(minutes=m), 50.0) for m in range(10)], 100) is None  # flat
    assert rules.trend_eta(pts[:3], 100) is None  # too few points


def test_check_trend_warns_only_inside_an_hour():
    assert rules.check_trend(audit(range(0, 6), start=30), "met:audit-capacity-pct", "node:PROD") is None  # ~110 min away
    evidence, eta = rules.check_trend(audit(range(0, 12)), "met:audit-capacity-pct", "node:PROD")
    assert 50 < eta < 60 and evidence[0]["trend"] == "rising"


def test_rule_shape_and_event_parsing():
    rules.check_rule_shape(MARIA)
    with pytest.raises(ValueError):
        rules.check_rule_shape({"type": "count", "event": "evt:TMF-185"})
    with pytest.raises(ValueError):
        rules.check_rule_shape({"type": "guess"})
    e = parse_event({"node": "node:PROD", "kind": "event", "entity": "evt:TMF-185", "ts": "2026-10-17T02:00:00Z"})
    assert e["ts"] == T0 and e["tool"] == "unknown"
    with pytest.raises(ValueError):
        parse_event({"node": "node:PROD", "kind": "metric", "entity": "met:x"})  # metric without a value


def test_label_reads_the_plain_name():
    from backend.watcher.engine import label
    assert label("audit-capacity-pct (audit trail capacity used)") == "Audit trail capacity used"
    assert label("TMF 185 - audit file pinned") == "TMF 185 - audit file pinned"
