"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_candidate_memory_model"""
import time

from backend.models.candidate_memory import CandidateMemory, QuestionHistoryEntry


def test_defaults():
    memory = CandidateMemory(email="a@example.com", updated_at=time.time())
    assert memory.sessions == []
    assert memory.category_scores_history == {}
    assert memory.weak_categories == []
    assert memory.asked_questions == []
    assert memory.interviewer_notes == ""


def test_roundtrip_json():
    entry = QuestionHistoryEntry(
        session_id="s1", question="What is LiveKit?", category="technical", asked_at=time.time()
    )
    memory = CandidateMemory(
        email="a@example.com",
        sessions=["s1"],
        category_scores_history={"technical": [4.0, 5.5]},
        weak_categories=["technical"],
        asked_questions=[entry],
        interviewer_notes="Struggles with system design.",
        updated_at=time.time(),
    )
    restored = CandidateMemory.model_validate_json(memory.model_dump_json())
    assert restored == memory


if __name__ == "__main__":
    test_defaults()
    print("test_defaults PASS")
    test_roundtrip_json()
    print("test_roundtrip_json PASS")
