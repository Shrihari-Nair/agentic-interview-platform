"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_updater
Makes a real Gemini call — needs GOOGLE_API_KEY in mockmind/.env."""
import asyncio

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.services.memory_updater import update_memory_from_report

PLAN = {
    "created_at": 1700000000.0,
    "questions": [
        {"id": "q1", "question": "What is a hash map?", "category": "technical"},
        {"id": "q2", "question": "Tell me about a conflict with a teammate.", "category": "behavioral"},
    ],
}

REPORT_SESSION_1 = {
    "summary": "Candidate gave vague answers on technical depth, solid on behavioral.",
    "category_scores": {"technical": 4.5, "behavioral": 8.0, "communication": 7.0},
}

REPORT_SESSION_2 = {
    "summary": "Still weak on technical depth, improved slightly.",
    "category_scores": {"technical": 5.0, "behavioral": 8.5, "communication": 7.5},
}


async def main():
    # First-ever update for this candidate — existing=None must not crash
    # (Review Focus #1).
    memory = await update_memory_from_report(
        existing=None, email="updater-test@example.com", session_id="s1",
        plan=PLAN, report=REPORT_SESSION_1,
    )
    assert memory.sessions == ["s1"]
    assert memory.category_scores_history["technical"] == [4.5]
    assert memory.weak_categories == ["technical"]  # 4.5 < 6.0 threshold; behavioral/communication are not
    assert len(memory.asked_questions) == 2
    assert memory.interviewer_notes.strip() != ""
    print("first update from existing=None: PASS")

    # Second session for the same candidate — history should accumulate.
    memory2 = await update_memory_from_report(
        existing=memory, email="updater-test@example.com", session_id="s2",
        plan=PLAN, report=REPORT_SESSION_2,
    )
    assert memory2.sessions == ["s1", "s2"]
    assert memory2.category_scores_history["technical"] == [4.5, 5.0]
    assert memory2.weak_categories == ["technical"]
    assert len(memory2.asked_questions) == 4
    print("second update accumulates history: PASS")

    # A candidate with no weak categories at all (Review Focus #4).
    strong_report = {
        "summary": "Excellent across the board.",
        "category_scores": {"technical": 9.0, "behavioral": 9.5, "communication": 9.0},
    }
    memory3 = await update_memory_from_report(
        existing=None, email="strong-candidate@example.com", session_id="s1",
        plan=PLAN, report=strong_report,
    )
    assert memory3.weak_categories == []
    print("strong candidate has no weak categories: PASS")


if __name__ == "__main__":
    asyncio.run(main())
