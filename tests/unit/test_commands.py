import pytest

from backend.commands.service import CommandService, load_catalog
from backend.simulator.service import Simulator


@pytest.fixture
def services():
    sim = Simulator(clock=lambda: 10.0)
    return CommandService(sim=sim, catalog=load_catalog()), sim


def context(system="sub:TMF", site="node:PROD", version="rvu:L"):
    return {"system": system, "site": site, "version": version}


def test_catalog_is_allowlisted_and_cited():
    entries = load_catalog()
    assert len(entries) >= 10
    assert all(entry.template_id and entry.source_id.startswith("doc:") for entry in entries)
    assert {entry.risk for entry in entries} <= {"read_only", "state_changing", "critical"}


def test_propose_returns_scoped_read_only_template(services):
    commands, _ = services
    result = commands.propose("what is pinning the audit trail?", context(), "node:PROD")
    proposal = result["proposals"][0]
    assert proposal["template_id"] == "tmfcom.status_audittrail_detail"
    assert proposal["risk"] == "read_only"
    assert proposal["guards"] == {"node_match": True, "rvu_ok": True}
    assert proposal["approval"]["required"] == "one_click"


def test_unknown_intent_never_generates_free_text(services):
    commands, _ = services
    assert commands.propose("make everything better", context(), "node:PROD") == {
        "proposals": [],
        "no_template": True,
    }


def test_node_guard_rejects_cross_node_proposal(services):
    commands, _ = services
    proposal = commands.propose("status tmf", context(site="node:DR"), "node:PROD")["proposals"][0]
    result = commands.approve(proposal["id"], "newhire1", None, None, "node:PROD")
    assert result["status"] == "rejected"
    assert "Node guard" in result["reason"]


def test_critical_requires_distinct_second_approver_and_is_single_use(services):
    commands, sim = services
    proposal = commands.propose("abort transaction", context(), "node:PROD")["proposals"][0]
    assert proposal["command"] == r"TMFCOM ABORT TRANSACTION \PROD(1).3.45678"
    assert commands.approve(proposal["id"], "newhire1", None, None, "node:PROD")["status"] == "needs_second_approver"
    assert commands.approve(proposal["id"], "newhire1", None, "newhire1", "node:PROD")["status"] == "rejected"
    assert commands.approve(proposal["id"], "newhire1", None, "raj", "node:PROD")["status"] == "approved"
    run = commands.execute(proposal["id"], "node:PROD")
    assert run["source_id"].startswith("run:c")
    assert "simulator" in run["output"].lower()
    assert sim.source_card(run["run_id"])["kind"] == "live"
    with pytest.raises(PermissionError, match="not been approved"):
        commands.execute(proposal["id"], "node:PROD")


def test_dryrun_never_executes(services):
    commands, sim = services
    proposal = commands.propose("abort transaction", context(), "node:PROD")["proposals"][0]
    preview = commands.dryrun(proposal["id"])
    assert preview["blast_radius"]
    assert any("Simulator only" in warning for warning in preview["warnings"])
    assert sim.source_card("run:c42") is None


def test_next_step_uses_last_simulated_run(services):
    commands, _ = services
    first = commands.propose("audit trail status", context(), "node:PROD")["proposals"][0]
    commands.approve(first["id"], "newhire1", None, None, "node:PROD")
    commands.execute(first["id"], "node:PROD")
    next_one = commands.propose("what next?", context(), "node:PROD")["proposals"][0]
    assert next_one["template_id"] == "tmfcom.status_transaction"
