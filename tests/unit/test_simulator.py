import pytest

from backend.simulator.service import Simulator


def test_scenario_changes_synthetic_audit_metric():
    now = [10.0]
    sim = Simulator(clock=lambda: now[0])
    sim.start_scenario("audit_trail_fill", speed=10)
    before = sim.metrics("node:PROD", "5m")["series"][0]["points"][-1][1]
    now[0] += 10
    after = sim.metrics("node:PROD", "5m")["series"][0]["points"][-1][1]
    assert after > before


def test_dr_metrics_stay_low_during_prod_demo():
    now = [10.0]
    sim = Simulator(clock=lambda: now[0])
    sim.start_scenario("audit_trail_fill", speed=100)
    now[0] += 100
    value = sim.metrics("node:DR", "5m")["series"][0]["points"][-1][1]
    assert value < 25


@pytest.mark.parametrize("scenario", ["missing", "AUDIT_TRAIL_FILL"])
def test_unknown_scenario_is_rejected(scenario):
    with pytest.raises(ValueError, match="unknown scenario"):
        Simulator().start_scenario(scenario, 1)


@pytest.mark.parametrize("speed", [0, -1, 101])
def test_unsafe_speed_is_rejected(speed):
    with pytest.raises(ValueError, match="speed"):
        Simulator().start_scenario("audit_trail_fill", speed)


def test_invalid_node_and_window_are_rejected():
    sim = Simulator()
    with pytest.raises(ValueError, match="unknown node"):
        sim.metrics("node:UNKNOWN")
    with pytest.raises(ValueError, match="window"):
        sim.metrics("node:PROD", "forever")
