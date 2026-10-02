"""Run: cd mockmind && agent/.venv/bin/python -m backend.tests.test_session_state_memory_write
Requires a real Redis and GOOGLE_API_KEY in mockmind/.env. Run with the AGENT venv
(agent/.venv), not the backend venv — this exercises agent/session_state.py, which
depends on livekit-agents."""
import asyncio
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.models.interview_plan import CandidateProfile, InterviewPlan, InterviewQuestion, JobProfile
from backend.services.memory_store import get_memory, delete_memory
from agent.session_state import AgentSessionState, generate_and_store_report

TEST_EMAIL = "session-state-memory-test@example.com"


def _make_plan(session_id: str, candidate_email: str | None) -> InterviewPlan:
    return InterviewPlan(
        session_id=session_id,
        candidate=CandidateProfile(name="Test Candidate"),
        job=JobProfile(title="AI Engineer"),
        questions=[
            InterviewQuestion(
                id="q1", category="technical", question="What is a hash map?", intent="basics",
            ),
        ],
        opening_message="Hi, let's get started.",
        created_at=0.0,
        candidate_email=candidate_email,
    )


async def main():
    await delete_memory(TEST_EMAIL)

    # Opted in: memory should be created after the report completes.
    plan = _make_plan("test-session-with-memory", TEST_EMAIL)
    state = AgentSessionState(session_id="test-session-with-memory", plan=plan)
    state.add_transcript_entry("interviewer", "What is a hash map?")
    state.add_transcript_entry("candidate", "It's a key-value data structure.")

    await generate_and_store_report(state)

    memory = await get_memory(TEST_EMAIL)
    assert memory is not None, "candidate_email was set but no memory was created"
    assert memory.sessions == ["test-session-with-memory"]
    print("opted-in session creates candidate memory: PASS")

    # Not opted in (candidate_email=None): must NOT create any memory record,
    # and must not raise.
    plan_no_email = _make_plan("test-session-no-memory", None)
    state_no_email = AgentSessionState(session_id="test-session-no-memory", plan=plan_no_email)
    state_no_email.add_transcript_entry("interviewer", "What is a hash map?")
    state_no_email.add_transcript_entry("candidate", "A data structure.")

    await generate_and_store_report(state_no_email)  # must not raise
    print("non-opted-in session does not raise: PASS")

    # Memory store failing on SAVE (Review Focus #3, write side) — the report
    # must already be safely stored by this point, and the save failure must
    # only be logged, never raised back out of generate_and_store_report.
    with patch(
        "backend.services.memory_store.save_memory",
        side_effect=ConnectionError("simulated Redis outage"),
    ):
        plan_save_fails = _make_plan("test-session-save-fails", TEST_EMAIL)
        state_save_fails = AgentSessionState(session_id="test-session-save-fails", plan=plan_save_fails)
        state_save_fails.add_transcript_entry("interviewer", "What is a hash map?")
        state_save_fails.add_transcript_entry("candidate", "A data structure.")
        await generate_and_store_report(state_save_fails)  # must not raise
    print("memory save failure is swallowed, does not raise: PASS")

    await delete_memory(TEST_EMAIL)


if __name__ == "__main__":
    asyncio.run(main())
