"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_question_generator_coding_slot_compliance
Regression test for a real, reproducible bug found while adding the
"coding interview" preset (4 coding questions out of 6 total): with
thinking disabled (thinking_budget=0), the model reliably under-produced
coding-tagged questions — e.g. one real run returned question_type="coding"
for only 1 of the 4 slots tagged [CODING] in the prompt, another run got
2/4, another 3/4. Root cause: thinking_budget=0 left the model unable to
reliably track the combination of per-slot category + difficulty + a hard
binary "this slot must be coding" tag across a whole generation. Fix:
enable dynamic thinking (thinking_budget=-1) specifically when coding
slots are requested — measured at 13/13 perfect trials after the fix,
versus roughly 1-in-4 slots dropped before it.

Makes real Gemini calls — needs GOOGLE_API_KEY in mockmind/.env."""
import asyncio

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.agents.question_generator import generate_questions
from backend.models.interview_plan import CandidateProfile, JobProfile

CANDIDATE = CandidateProfile(
    name="Priya Sharma", current_role="Backend Engineer", years_of_experience=4,
    skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
)
JOB = JobProfile(title="AI Engineer", required_skills=["Python", "LLMs", "Docker", "Kubernetes"])


async def _regression_check(n: int):
    for i in range(n):
        plan = await generate_questions(
            CANDIDATE, JOB, f"test-coding-slot-compliance-{i}",
            num_coding_questions=4, total_questions=6,
        )
        assert len(plan.questions) == 6
        coding = [q for q in plan.questions if q.question_type == "coding"]
        assert len(coding) == 4, (
            f"run {i}: expected 4 coding questions, got {len(coding)} "
            f"(question_types={[q.question_type for q in plan.questions]})"
        )


if __name__ == "__main__":
    asyncio.run(_regression_check(3))
    print("3 repeated real generate_questions() calls with num_coding_questions=4/6, "
          "all slots honored: PASS")
