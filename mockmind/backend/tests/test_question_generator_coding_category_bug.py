"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_question_generator_coding_category_bug
Regression test for a real, reproducible bug hit repeatedly during manual
testing: with num_coding_questions=0 (the default), the model would
sometimes still emit "category": "coding" (not a valid QuestionCategory),
crashing generate_questions() with an uncaught ValueError. Root cause: the
prompt unconditionally explained the coding-question JSON format regardless
of whether any coding slots were requested, priming the model to confuse
"coding" (a question_type value) with "category" (which has no such value).
Fix: only include that explanation when coding slots are actually assigned,
plus an explicit "category is never 'coding'" rule shown unconditionally.

Makes real Gemini calls — needs GOOGLE_API_KEY in mockmind/.env."""
import asyncio

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.agents.question_generator import (
    _assign_coding_slots,
    _assign_level_sequence,
    _build_prompt,
    _normalize_level_weights,
    generate_questions,
)
from backend.models.interview_plan import CandidateProfile, JobProfile

CANDIDATE = CandidateProfile(
    name="Priya Sharma", current_role="Backend Engineer", years_of_experience=4,
    skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
)
JOB = JobProfile(title="AI Engineer", required_skills=["Python", "LLMs", "Docker", "Kubernetes"])


def test_prompt_omits_coding_format_when_no_coding_questions_requested():
    weights = _normalize_level_weights(None)
    seq = _assign_level_sequence(16, weights)

    no_coding_slots = _assign_coding_slots(seq, 0)
    prompt = _build_prompt(CANDIDATE, JOB, seq, no_coding_slots)
    assert "For slots marked CODING" not in prompt
    assert "problem_statement" not in prompt

    coding_slots = _assign_coding_slots(seq, 2)
    prompt_with_coding = _build_prompt(CANDIDATE, JOB, seq, coding_slots)
    assert "For slots marked CODING" in prompt_with_coding
    assert "problem_statement" in prompt_with_coding

    assert 'never "coding" or anything else' in prompt
    assert 'never "coding" or anything else' in prompt_with_coding


async def _regression_check(n: int):
    """Repeated real calls with the default (no coding questions) — this is
    exactly the configuration that was crashing. Not a 100% guarantee (LLM
    output is probabilistic) but a strong regression signal: this used to
    fail roughly every other call."""
    for i in range(n):
        plan = await generate_questions(CANDIDATE, JOB, f"test-coding-category-bug-{i}")
        assert len(plan.questions) > 0


if __name__ == "__main__":
    test_prompt_omits_coding_format_when_no_coding_questions_requested()
    print("prompt correctly omits/includes coding format block: PASS")

    asyncio.run(_regression_check(3))
    print("3 repeated real generate_questions() calls, no 'coding' category crash: PASS")
