"""FastAPI app: uvicorn backend.api.main:app --port 8000. Endpoints: /health /session /chat /sources/{id}, plus the routers
in backend/knowledge.py (/persons, /knowledge*) and backend/documents.py (/documents)."""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import documents, knowledge, settings
from backend.pipeline import answer as pipeline
from backend.pipeline import verify

NODES = [{"id": "node:PROD", "display": "\\PROD"}, {"id": "node:DR", "display": "\\DR"}]
SESSION = {"node": "node:PROD", "series": "rvu:L", "user": "OPS.NEWHIRE"}  # in-memory, single demo user


@asynccontextmanager
async def lifespan(app):
    pipeline.warm()  # MiniCheck loads once, here, not on the first question
    yield


app = FastAPI(title="NonStop Copilot", lifespan=lifespan)
for r in (knowledge.router, documents.router):  # /persons /knowledge* /documents
    app.include_router(r)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


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
    return pipeline.answer(body.question, {**SESSION, "user": body.user_id}, body.context_override)


@app.get("/sources/{source_id:path}")
def get_source(source_id: str):
    with pipeline.connect() as conn:
        card = pipeline.source_card(conn, source_id)
    if card is None:
        raise HTTPException(404, f"unknown source {source_id}")
    return card
