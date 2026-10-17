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

from backend import documents, knowledge, learning, settings
from backend.graph import view as graph_view
from backend.commands.service import command_service
from backend.pipeline import answer as pipeline
from backend.pipeline import assistant
from backend.pipeline import verify
from backend.simulator.service import simulator

NODES = [{"id": "node:PROD", "display": "\\PROD"}, {"id": "node:DR", "display": "\\DR"}]
SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "OPS.NEWHIRE"}  # in-memory, single demo user


@asynccontextmanager
async def lifespan(app):
    pipeline.warm()  # MiniCheck loads once, here, not on the first question
    if ANSWER_MODE == "assistant":
        assistant.warm()
    yield


# "assistant" = standard RAG (rerank + one cited answer, docs/ARCHITECTURE_V2.md); "classic" = claims pipeline
ANSWER_MODE = os.getenv("ANSWER_MODE", "assistant")


app = FastAPI(title="NonStop Copilot", lifespan=lifespan)
for r in (knowledge.router, documents.router, graph_view.router, learning.router):  # /persons /knowledge* /documents /graph /learning*
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
        return simulator.start_scenario(body.scenario, body.speed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/metrics")
def get_metrics(node: str, window: str = "60m"):
    try:
        return simulator.metrics(node, window)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
