"""Knowledge check: measures what an emerging veteran actually knows, not just what they have been shown.

A signed veteran note becomes a scenario question ("<trigger>. What would you do?"). The junior answers in their own
words; Qwen grades the answer against the veteran's do / why / not-when (0 missed, 1 partly, 2 got it) and the
veteran's answer is shown back (that is the teaching). A pass adds a `knows` edge user -> note, so Synapse shows it.
`pick_notes`, `question_for` and `clamp_grade` are pure (unit-tested).
"""
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.learning import TEST_USERS
from backend.pipeline import llm
from backend.pipeline.answer import _rows, connect

PER_CHECK = 3
PASS = 1  # partly right counts as demonstrated; 2 is "got it"

GRADE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer", "enum": [0, 1, 2]}, "feedback": {"type": "string"}},
    "required": ["score", "feedback"],
}
GRADER = """You grade a junior NonStop operator's answer against a senior veteran's captured advice.
Score 2 if the answer contains the veteran's key action (what to do or check first) and nothing the veteran warns against.
Score 1 if it is partly right: the right direction but missing the key check, or vague.
Score 0 if it is wrong, empty, unsafe, or does the thing the veteran says not to do.
Judge meaning, not wording or spelling. Feedback: one or two short sentences to the junior, plain English,
saying what they got right and the one thing to remember. Do not repeat the whole veteran answer."""


def question_for(note):
    """The scenario question for a note: its trigger, then the ask."""
    return f"{note['trigger_text'].rstrip('.')}. What would you do, and what would you check first?"


def pick_notes(notes, passed_ids, n=PER_CHECK):
    """Notes not yet passed first (newest signed first), then the rest; at most n."""
    fresh = [x for x in notes if x["id"] not in passed_ids]
    seen = [x for x in notes if x["id"] in passed_ids]
    return (fresh + seen)[:n]


def clamp_grade(raw, answer):
    """Model output -> (score 0..2, feedback). An empty or very short answer is always 0."""
    if len(answer.split()) < 3:
        return 0, "Write what you would actually do, even a short sentence."
    try:
        score = int(raw.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(2, score)), str(raw.get("feedback") or "").strip()[:400]


router = APIRouter()


class CheckAnswerIn(BaseModel):
    note_id: str
    answer: str


def _user(user_id):
    if not user_id.strip() or user_id.strip().lower() in TEST_USERS:
        raise HTTPException(404, "not an operator id")


@router.get("/learning/{user_id}/check")
def get_check(user_id: str, subsystem: str):
    """Up to 3 scenario questions from signed veteran notes in one subsystem."""
    _user(user_id)
    with connect() as conn:
        notes = _rows(conn, "SELECT h.id, h.trigger_text, h.site_id, h.system_id, p.name AS owner_name FROM heuristic h "
                            "JOIN person p ON p.id = h.owner_id WHERE h.status = 'approved' AND h.system_id = %s "
                            "ORDER BY h.signed_at DESC NULLS LAST, h.id", (subsystem,))
        passed = {r["note_id"] for r in _rows(conn, "SELECT note_id FROM check_result WHERE user_id = %s AND score >= %s",
                                               (user_id, PASS))}
    return {"subsystem": subsystem,
            "questions": [{"note_id": x["id"], "owner_name": x["owner_name"], "question": question_for(x),
                           "node": x["site_id"].split(":", 1)[1] if x["site_id"] else "ALL",
                           "passed_before": x["id"] in passed} for x in pick_notes(notes, passed)]}


@router.post("/learning/{user_id}/check")
def answer_check(user_id: str, body: CheckAnswerIn):
    """Grade one answer, store it, and on a pass link the user to the note in the graph."""
    _user(user_id)
    with connect() as conn:
        rows = _rows(conn, "SELECT h.*, p.name AS owner_name FROM heuristic h JOIN person p ON p.id = h.owner_id "
                           "WHERE h.id = %s AND h.status = 'approved'", (body.note_id,))
        if not rows:
            raise HTTPException(404, f"unknown note {body.note_id}")
        n = rows[0]
        veteran = (f"Situation: {n['trigger_text']}\nVeteran ({n['owner_name']}) says do: {n['call_text']}\n"
                   f"Why: {n['why_text'] or '-'}\nNot when: {n['not_when_text'] or '-'}")
        raw = {}
        if len(body.answer.split()) >= 3:
            r = llm.chat([{"role": "system", "content": GRADER},
                          {"role": "user", "content": f"{veteran}\n\nJunior's answer: {body.answer.strip()}"}],
                         schema=GRADE_SCHEMA, max_tokens=200)
            try:
                raw = json.loads(r["content"])
            except ValueError:
                raw = {}
        score, feedback = clamp_grade(raw, body.answer)
        conn.execute("INSERT INTO check_result (user_id, note_id, answer, score, feedback) VALUES (%s,%s,%s,%s,%s)",
                     (user_id, n["id"], body.answer.strip(), score, feedback))
        linked = score >= PASS
        if linked:
            conn.execute("INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,'knows',%s,%s,%s,'check') "
                         "ON CONFLICT (src, rel, dst) DO UPDATE SET weight = GREATEST(edge.weight, EXCLUDED.weight)",
                         (user_id, n["id"], score, n["id"]))
        conn.commit()
    return {"score": score, "feedback": feedback, "linked": linked,
            "veteran": {"owner_name": n["owner_name"], "call_text": n["call_text"], "why_text": n["why_text"] or "",
                        "not_when_text": n["not_when_text"] or "", "note_id": n["id"]}}


def checks_summary(conn, user_id):
    """{sub_id: {"tried": n, "passed": m}} and the total notes demonstrated (best score per note >= PASS)."""
    rows = _rows(conn, "SELECT h.system_id, c.note_id, max(c.score) AS best FROM check_result c "
                       "JOIN heuristic h ON h.id = c.note_id WHERE c.user_id = %s GROUP BY h.system_id, c.note_id", (user_id,))
    out = {}
    for r in rows:
        s = out.setdefault(r["system_id"], {"tried": 0, "passed": 0})
        s["tried"] += 1
        s["passed"] += r["best"] >= PASS
    return out, sum(s["passed"] for s in out.values())
