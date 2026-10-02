"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_question_generator_memory
Makes real Gemini calls — needs GOOGLE_API_KEY in mockmind/.env. Takes ~30-60s."""
import asyncio
import time

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.agents.question_generator import generate_questions
from backend.models.candidate_memory import CandidateMemory, QuestionHistoryEntry
from backend.models.interview_plan import CandidateProfile, JobProfile

CANDIDATE = CandidateProfile(
    name="Priya Sharma", current_role="Backend Engineer", years_of_experience=4,
    skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
    notable_projects=["Resume-parsing microservice using Gemini pipelines"],
)
JOB = JobProfile(
    title="AI Engineer", required_skills=["Python", "LLMs", "Docker", "Kubernetes"],
)


async def main():
    # No memory at all — must behave exactly as before (Review Focus #1).
    plan_no_memory = await generate_questions(CANDIDATE, JOB, "test-qg-memory-baseline")
    assert plan_no_memory.candidate_email is None
    print(f"no-memory baseline: {len(plan_no_memory.questions)} questions, candidate_email=None: PASS")

    # A returning candidate, weak at 'technical', with a prior question to avoid repeating.
    memory = CandidateMemory(
        email="returning-candidate@example.com",
        weak_categories=["technical"],
        asked_questions=[
            QuestionHistoryEntry(
                session_id="prior-session", question="What is a hash map?",
                category="technical", asked_at=time.time(),
            )
        ],
        interviewer_notes="Tends to give vague answers on data structure trade-offs.",
        updated_at=time.time(),
    )
    plan_with_memory = await generate_questions(
        CANDIDATE, JOB, "test-qg-memory-returning",
        candidate_memory=memory, candidate_email="returning-candidate@example.com",
    )
    assert plan_with_memory.candidate_email == "returning-candidate@example.com"
    question_texts = [q.question for q in plan_with_memory.questions]
    assert "What is a hash map?" not in question_texts, (
        "exact verbatim repeat of a seeded prior question — memory context wasn't respected"
    )
    technical_count = sum(1 for q in plan_with_memory.questions if q.category == "technical")
    print(f"returning-candidate plan: {len(plan_with_memory.questions)} questions, "
          f"{technical_count} technical, no verbatim repeat: PASS")

    # A candidate with memory but no weak categories yet (Review Focus #4) — must not crash.
    empty_weak_memory = CandidateMemory(email="no-weak-areas@example.com", updated_at=time.time())
    plan_empty_weak = await generate_questions(
        CANDIDATE, JOB, "test-qg-memory-no-weak",
        candidate_memory=empty_weak_memory, candidate_email="no-weak-areas@example.com",
    )
    assert len(plan_empty_weak.questions) > 0
    print("candidate_memory with no weak_categories does not crash: PASS")


if __name__ == "__main__":
    asyncio.run(main())
