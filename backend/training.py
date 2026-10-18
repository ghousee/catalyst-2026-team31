"""Training sandbox: guided exercises on the Training Simulator page. Nothing here is recorded: no question log,
no learning map, no Synapse links, no alerts. Commands only return simulated output (no approval needed, because
nothing runs anywhere). The exercise steps live in the UI; the backend only runs checks and grades free-text answers.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.commands.service import command_service
from backend.knowledge_check import grade
from backend.pipeline.answer import _rows, connect
from backend.simulator.service import NODES, Simulator

router = APIRouter()
SANDBOX = Simulator()  # its own simulator: the exercise never sees (or changes) the live demo's state


class RunIn(BaseModel):
    template_id: str
    node: str = "node:PROD"


class GradeIn(BaseModel):
    note_ids: list[str]
    answer: str


@router.post("/training/run")
def run(body: RunIn):
    """Simulated output for a catalog command, for practice. Not logged, not approved, not a proposal."""
    entry = next((e for e in command_service.catalog if e.template_id == body.template_id), None)
    if entry is None or body.node not in NODES:
        raise HTTPException(404, "unknown command or node")
    command = command_service._render(entry, body.node)
    return {"command": command, "risk": entry.risk, "output": SANDBOX._output(entry.template_id, command, NODES[body.node]),
            "source_id": entry.source_id}


@router.post("/training/grade")
def grade_answer(body: GradeIn):
    """Grade a practice answer against the veterans' notes it is about. Stores nothing."""
    with connect() as conn:
        notes = _rows(conn, "SELECT h.*, p.name AS owner_name FROM heuristic h JOIN person p ON p.id = h.owner_id "
                            "WHERE h.id = ANY(%s) AND h.status = 'approved'", (body.note_ids,))
    if not notes:
        raise HTTPException(404, "unknown notes")
    score, feedback = grade(notes, body.answer)
    return {"score": score, "feedback": feedback,
            "veterans": [{"note_id": n["id"], "owner_name": n["owner_name"], "call_text": n["call_text"],
                          "why_text": n["why_text"] or "", "not_when_text": n["not_when_text"] or ""} for n in notes]}
