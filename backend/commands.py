"""Command cards from the graph's command catalog (entity kind 'command'): propose, dry run, approve, execute.

Risk class is data (`props.risk`), never LLM output. Execution is SIMULATED: canned text, nothing runs anywhere.
A command id is `<template_id>@<NODE>` (e.g. `tmfcom.status_tmf@PROD`): stateless, so a proposal can be re-derived
from the catalog at approve/execute time. Approvals and runs are in-memory (demo). Routes: bottom of the file.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api import state
from backend.graph.query import lookup, resolve
from backend.pipeline.answer import _rows, connect

APPROVAL = {"read_only": "one_click", "state_changing": "type_node", "critical": "second_approver"}
MAX_PROPOSALS = 3

# canned outputs for the demo; any other template gets GENERIC. {node} is filled with the target node.
SIM = {
    "tmfcom.status_audittrail_detail": (
        "TMF Status AUDITTRAIL, DETAIL  {node}  (simulated)\n"
        "Active audit trail capacity used: 71%\n"
        "First pinned file: $AUDIT.ZTMFAT.AA000412  pinned by transaction {node}(2,118).4471 (oldest, 3 h 12 min)\n"
        "Audit files on disk: 14"),
    "tmfcom.status_transaction": (
        "TMF Status TRANSACTION  {node}  (simulated)\n"
        "Transaction        State    Process       Age\n"
        "{node}(2,118).4471 ACTIVE   $SETTLE-SC    3 h 12 min\n"
        "{node}(1,090).9921 ACTIVE   $WEB01        0 h 00 min"),
    "tmfcom.status_tmf": "TMF Status TMF  {node}  (simulated)\nTMF state: STARTED   BEGINTRANS: ENABLED\nAudit trail capacity used: 71%",
    "scf.status_disk_detail": (
        "SCF STATUS DISK  {node}  (simulated)\n"
        "Primary: STARTED   Mirror: STARTED   Paths: PRIMARY-A UP, PRIMARY-B DOWN, MIRROR-A UP, MIRROR-B UP"),
    "pathcom.status_tcp": "PATHCOM STATUS TCP  {node}  (simulated)\nTCP $TCP1  RUNNING   terminals: 38 active",
}
GENERIC = "Simulated: {command} would run on {node}. No real command was executed."

APPROVED = {}   # command id -> user who approved (single use)
RUNS = {}       # run id -> {"command", "node", "ts"}


# ---------------------------------------------------------------- pure helpers
def cmd_id(template_id, node):
    return f"{template_id}@{node.split(':', 1)[1]}"


def parse_id(cid):
    """'tmfcom.status_tmf@PROD' -> ('tmfcom.status_tmf', 'node:PROD'); ValueError if malformed."""
    template, sep, node = cid.rpartition("@")
    if not (sep and template and node):
        raise ValueError(f"bad command id {cid!r}")
    return template, f"node:{node}"


def fill(command, node):
    """Fill the obvious slot (the node); other placeholders ($volume, cpu, seq.num) stay for the operator."""
    return command.replace("\\node", state.node_display(node))


def approval_for(risk):
    return {"required": APPROVAL.get(risk, "second_approver")}  # unknown risk class -> strictest tier


def _bare(node_text):
    return (node_text or "").strip().lstrip("\\").upper()


def check_approval(risk, target_node, session_node, user_id, typed_node=None, second_approver=None, known_people=None):
    """-> (status, reason). Enforces the tier: one_click | type_node (typed text must be the session node)
    | second_approver (a different, existing person). The node guard is always checked first."""
    if target_node != session_node:
        return "rejected", (f"Node guard: command targets {state.node_display(target_node)} but the session is on "
                            f"{state.node_display(session_node)}.")
    tier = approval_for(risk)["required"]
    if tier == "type_node" and _bare(typed_node) != _bare(state.node_display(session_node)):
        return "rejected", f"Type the node name {state.node_display(session_node)} to approve."
    if tier == "second_approver":
        if not second_approver:
            return "needs_second_approver", "Critical command: a second approver (a different person) must confirm."
        if second_approver == user_id:
            return "rejected", "The second approver must be a different person."
        if known_people is not None and second_approver not in known_people:
            return "rejected", f"Unknown approver {second_approver!r}."
    return "approved", ""


def sim_output(template_id, command, node):
    return SIM.get(template_id, GENERIC).format(node=state.node_display(node), command=command)


# ---------------------------------------------------------------- catalog access
def _catalog(conn, template_id):
    rows = _rows(conn, "SELECT props FROM entity WHERE id = %s AND kind = 'command'", (f"cmd:{template_id}",))
    return rows[0]["props"] if rows else None


def propose(conn, question, ctx):
    """Catalog commands for the entities the question resolves to, in the context's subsystem. -> (proposals, no_template)."""
    r = resolve(conn, question, {"version": ctx.get("version"), "site": ctx.get("site")})
    system = ctx.get("system") or r["subsystem"]
    if not system or not r["entities"]:
        return [], True
    try:
        cmds = lookup(conn, [e["id"] for e in r["entities"]],
                      {"system": system, "version": ctx.get("version"), "site": ctx.get("site")})["commands"]
    except ValueError:
        return [], True
    cmds = cmds[:MAX_PROPOSALS]
    node = ctx.get("site") or state.SESSION["node"]
    pinned = {}  # template -> series entities it is restricted to (applies_to edges; none today = all series)
    for e in _rows(conn, "SELECT src, dst FROM edge WHERE rel = 'applies_to' AND src LIKE 'cmd:%' AND dst LIKE 'rvu:%'"):
        pinned.setdefault(e["src"][4:], set()).add(e["dst"])
    out = [{"id": cmd_id(c["template_id"], node), "template_id": c["template_id"], "command": fill(c["command"], node),
            "node": state.node_display(node), "risk": c["risk"], "explanation": c["explanation"],
            "source_id": c["source_id"],
            "guards": {"node_match": node == state.SESSION["node"],
                       "rvu_ok": not pinned.get(c["template_id"]) or ctx.get("version") in pinned[c["template_id"]]},
            "approval": approval_for(c["risk"])} for c in cmds]
    return out, not out


# ---------------------------------------------------------------- routes
router = APIRouter(prefix="/commands")


class ProposeIn(BaseModel):
    question: str
    context: dict


class ApproveIn(BaseModel):
    user_id: str = "newhire1"
    typed_node: str | None = None
    second_approver: str | None = None


def _load(cid):
    try:
        template, node = parse_id(cid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    with connect() as conn:
        props = _catalog(conn, template)
    if props is None:
        raise HTTPException(404, f"unknown command template {template}")
    return template, node, props


@router.post("/propose")
def propose_route(body: ProposeIn):
    with connect() as conn:
        proposals, none = propose(conn, body.question, body.context)
    return {"proposals": proposals, "no_template": none}


@router.post("/{cid}/dryrun")
def dryrun(cid: str):
    template, node, p = _load(cid)
    cmd = fill(p["command"], node)
    risky = p["risk"] != "read_only"
    return {"id": cid, "expected_output": sim_output(template, cmd, node),
            "blast_radius": [{"entity": p["subsystem"].split(":", 1)[1], "effect": p["explanation"]}] if risky else [],
            "warnings": ["Critical: cannot be undone."] if p["risk"] == "critical" else []}


@router.post("/{cid}/approve")
def approve(cid: str, body: ApproveIn):
    template, node, p = _load(cid)
    with connect() as conn:
        people = {r["id"] for r in _rows(conn, "SELECT id FROM person")}
    status, reason = check_approval(p["risk"], node, state.SESSION["node"], body.user_id, body.typed_node,
                                    body.second_approver, people)
    if status == "approved":
        APPROVED[cid] = body.user_id
    return {"status": status, "reason": reason}


@router.post("/{cid}/execute")
def execute(cid: str):
    template, node, p = _load(cid)
    if cid not in APPROVED:
        raise HTTPException(409, "Command has not been approved")
    if node != state.SESSION["node"]:
        APPROVED.pop(cid, None)
        raise HTTPException(409, "Session node changed since approval")
    APPROVED.pop(cid)  # approval is single-use
    run_id = f"run:c{len(RUNS) + 1}"
    cmd = fill(p["command"], node)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    RUNS[run_id] = {"command": cmd, "node": node, "ts": ts}
    return {"run_id": run_id, "output": sim_output(template, cmd, node), "ts": ts, "source_id": run_id}
