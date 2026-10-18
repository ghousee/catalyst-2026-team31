"""FastAPI app: uvicorn backend.api.main:app --port 8000.
Endpoints: /health /session /chat /sources/{id}; command/simulator demo (/commands/*, /simulator/scenario,
/metrics, backend/commands + backend/simulator); routers backend/knowledge.py (/persons, /knowledge*) and
backend/documents.py (/documents)."""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import documents, knowledge, knowledge_check, learning, settings, training
from backend.graph import view as graph_view
from backend.commands.service import command_service
from backend.pipeline import answer as pipeline
from backend.pipeline import assistant
from backend.pipeline import verify
from backend.simulator.service import simulator
from backend.watcher.engine import SCENARIO_REPLAY, parse_event, replays, watcher
from backend.watcher.engine import series as watcher_series
from backend.integrations import demo as tool_demo
from backend.integrations.momi import InboxReader
from backend.integrations.prognosis import Poller

NODES = [{"id": "node:PROD", "display": "\\PROD"}, {"id": "node:DR", "display": "\\DR"}]
SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "OPS.NEWHIRE"}  # in-memory, single demo user


@asynccontextmanager
async def lifespan(app):
    pipeline.warm()  # MiniCheck loads once, here, not on the first question
    if ANSWER_MODE == "assistant":
        assistant.warm()
    if os.getenv("CONNECTORS", "on") != "off":  # monitoring-tool connectors -> watcher
        PROGNOSIS.start()
        MOMI.start()
    yield


# "assistant" = standard RAG (rerank + one cited answer, docs/ARCHITECTURE_V2.md); "classic" = claims pipeline
ANSWER_MODE = os.getenv("ANSWER_MODE", "assistant")


app = FastAPI(title="NonStop Copilot", lifespan=lifespan)
for r in (knowledge.router, documents.router, graph_view.router, knowledge_check.router, learning.router, training.router):  # /persons /knowledge* /documents /graph /learning*
    app.include_router(r)
# any local UI port (Next.js moves to 3001+ when 3000 is busy); still local-only
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])


def session_view():
    disp = next(n["display"] for n in NODES if n["id"] == SESSION["node"])
    return {**SESSION, "node_display": disp, "nodes_available": NODES}


class SessionIn(BaseModel):
    node: str


class ChatIn(BaseModel):
    user_id: str = "newhire1"
    question: str
    context_override: dict | None = None
    ablation: int | None = None  # accepted, ignored (eval-only flag in the contract)
    history: list[dict] | None = None  # last turns [{question, reply}] for follow-ups (assistant mode)


class CommandContext(BaseModel):
    system: str
    site: str
    version: str


class ProposeIn(BaseModel):
    question: str
    context: CommandContext


class ApproveIn(BaseModel):
    user_id: str
    typed_node: str | None = None
    second_approver: str | None = None


class ScenarioIn(BaseModel):
    scenario: str
    speed: float = 1


@app.get("/health")
def health():
    out = {"db": False, "ollama": False, "minicheck_loaded": verify._model is not None}
    try:
        with pipeline.connect() as conn:
            conn.execute("SELECT 1")
        out["db"] = True
    except Exception:
        pass
    try:
        out["ollama"] = httpx.get(f"{settings.OLLAMA_URL}/api/tags", timeout=3).status_code == 200
    except httpx.HTTPError:
        pass
    return out


@app.get("/session")
def get_session():
    return session_view()


@app.post("/session")
def set_session(body: SessionIn):
    if body.node not in {n["id"] for n in NODES}:
        raise HTTPException(400, f"unknown node {body.node}")
    SESSION["node"] = body.node
    return session_view()


@app.post("/chat")
def chat(body: ChatIn):
    # sync def: FastAPI runs it in a worker thread, so the event loop is not blocked by Ollama/MiniCheck
    session = {**SESSION, "user": body.user_id}
    if ANSWER_MODE == "assistant":
        return assistant.answer(body.question, session, body.context_override, body.history or [])
    return pipeline.answer(body.question, session, body.context_override)


@app.get("/sources/{source_id:path}")
def get_source(source_id: str):
    live = simulator.source_card(source_id)
    if live is not None:
        return live
    with pipeline.connect() as conn:
        card = pipeline.source_card(conn, source_id)
    if card is None:
        raise HTTPException(404, f"unknown source {source_id}")
    return card


@app.post("/commands/propose")
def propose_command(body: ProposeIn):
    try:
        return command_service.propose(body.question, body.context.model_dump(), SESSION["node"])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/commands/{proposal_id}/dryrun")
def dryrun_command(proposal_id: str):
    try:
        return command_service.dryrun(proposal_id)
    except KeyError as exc:
        raise HTTPException(404, f"unknown proposal {proposal_id}") from exc


@app.post("/commands/{proposal_id}/approve")
def approve_command(proposal_id: str, body: ApproveIn):
    # only veterans approve; emerging veterans (and any non-person user) can ask, dry-run and learn, not approve
    with pipeline.connect() as conn:
        veterans = {r[0] for r in conn.execute("SELECT id FROM person WHERE level = 'veteran' AND active").fetchall()}
    if body.user_id not in veterans:
        return {"status": "rejected", "reason": "Emerging Veterans can't approve commands. Ask a veteran to approve this one."}
    if body.second_approver and body.second_approver not in veterans:
        return {"status": "rejected", "reason": "The second approver must be a veteran."}
    try:
        return command_service.approve(
            proposal_id,
            body.user_id,
            body.typed_node,
            body.second_approver,
            SESSION["node"],
        )
    except KeyError as exc:
        raise HTTPException(404, f"unknown proposal {proposal_id}") from exc


@app.post("/commands/{proposal_id}/execute")
def execute_command(proposal_id: str):
    try:
        return command_service.execute(proposal_id, SESSION["node"])
    except KeyError as exc:
        raise HTTPException(404, f"unknown proposal {proposal_id}") from exc
    except PermissionError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/simulator/scenario")
def run_scenario(body: ScenarioIn):
    try:
        out = simulator.start_scenario(body.scenario, body.speed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if body.scenario in SCENARIO_REPLAY:  # the same Start button also plays the recorded feed into the watcher
        out["replay"] = watcher.start_replay(SCENARIO_REPLAY[body.scenario], speed=REPLAY_SPEED)
    return out


# ---------------------------------------------------------------- watcher: early warnings (backend/watcher)
REPLAY_SPEED = 30.0  # a 40-minute incident plays in ~80 s


class EventIn(BaseModel):
    node: str
    kind: str
    entity: str
    value: float | None = None
    tool: str = "unknown"
    text: str = ""
    ts: str | None = None


class ReplayIn(BaseModel):
    name: str
    speed: float = REPLAY_SPEED


@app.post("/events")
def post_event(body: EventIn):
    """One normalised event from any source (Prognosis REST poller, MOMI export reader, a script). Returns new alert ids."""
    try:
        return {"alerts": watcher.ingest(parse_event(body.model_dump()))}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/alerts")
def get_alerts(node: str | None = None):
    """Open alerts for a node (default: the session node; `all` = every node), as alert cards with fix steps and
    next commands. Each card carries its node, and its commands keep their node guard."""
    return watcher.alerts(node or SESSION["node"], command_service.propose_entity)


@app.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: str):
    with pipeline.connect() as conn:
        n = conn.execute("UPDATE alert SET acknowledged = TRUE WHERE id = %s", (alert_id,)).rowcount
        conn.commit()
    if not n:
        raise HTTPException(404, f"unknown alert {alert_id}")
    return {"id": alert_id, "acknowledged": True}


@app.get("/watcher/replays")
def list_replays():
    return replays()


@app.post("/watcher/replay")
def start_replay(body: ReplayIn):
    if not 0 < body.speed <= 600:
        raise HTTPException(422, "speed must be between 0 and 600")
    try:
        return watcher.start_replay(body.name, body.speed)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/metrics")
def get_metrics(node: str, window: str = "60m"):
    try:
        out = simulator.metrics(node, window)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # a metric the watcher has received (replay or live source) wins over the simulator's curve, so charts and alerts agree
    for s in out["series"]:
        pts = watcher_series(node, f"met:{s['metric']}")
        if len(pts) >= 2:
            s["points"] = pts
    return out


# ---------------------------------------------------------------- monitoring-tool connectors (backend/integrations)
PROGNOSIS = Poller(watcher.ingest_alarm)
MOMI = InboxReader(watcher.ingest_alarm)


class SampleIn(BaseModel):
    sample: str


@app.get("/integrations")
def integrations():
    """Connector status for the Alerts page: what each tool feeds, how, when it was last read, how many alarms."""
    return [PROGNOSIS.status, MOMI.status]


@app.get("/demo/prognosis/Prognosis/Rest/v1/data/OpenProblems")
def demo_prognosis_dataset():
    """Stand-in for a Prognosis REST dataset of open problems (same shape the poller reads from a real one)."""
    return tool_demo.OPEN_PROBLEMS


@app.post("/demo/prognosis/problem")
def demo_prognosis_problem(body: SampleIn):
    """Raise a sample problem in the stand-in Prognosis; the poller picks it up on its next poll."""
    try:
        return tool_demo.add_problem(body.sample)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/demo/momi/alarm")
def demo_momi_alarm(body: SampleIn):
    """Drop a sample MOMI alarm export into the inbox; the reader picks it up within seconds."""
    if body.sample not in tool_demo.MOMI_SAMPLES:
        raise HTTPException(404, f"unknown sample {body.sample}")
    return {"file": tool_demo.momi_file(body.sample, MOMI.inbox)}
