"""Knowledge check (backend/knowledge_check.py): question wording, which notes are asked, grade clamping. No DB, no LLM."""
from backend.knowledge_check import clamp_grade, pick_notes, question_for

NOTES = [{"id": f"maria:h{i}", "trigger_text": f"trigger {i}."} for i in range(1, 6)]


def test_question_is_the_trigger_plus_the_ask():
    q = question_for({"trigger_text": "TMF 185 fires twice in 30 minutes."})
    assert q == "TMF 185 fires twice in 30 minutes. What would you do, and what would you check first?"


def test_unpassed_notes_come_first_and_at_most_three():
    picked = pick_notes(NOTES, passed_ids={"maria:h1", "maria:h2"})
    assert [x["id"] for x in picked] == ["maria:h3", "maria:h4", "maria:h5"]
    assert [x["id"] for x in pick_notes(NOTES[:2], passed_ids={"maria:h1"})] == ["maria:h2", "maria:h1"]


def test_grade_is_clamped_and_short_answers_score_zero():
    assert clamp_grade({"score": 2, "feedback": "Good."}, "check status transaction first") == (2, "Good.")
    assert clamp_grade({"score": 7}, "check status transaction first")[0] == 2
    assert clamp_grade({"score": "x"}, "check status transaction first")[0] == 0
    assert clamp_grade({"score": 2}, "idk")[0] == 0
