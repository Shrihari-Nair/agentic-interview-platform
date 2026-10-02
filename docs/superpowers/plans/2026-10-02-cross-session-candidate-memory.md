# Cross-Session Candidate Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a candidate who opts in with an email get question generation biased toward their own historically weak areas across sessions, fully off by default, with no behavior change for anyone who doesn't opt in.

**Architecture:** A new Redis-backed `CandidateMemory` record (reusing the existing `redis_client`, no new infrastructure) is read before question generation and written after report generation. Reading injects a soft, qualitative bias into the question-generation prompt; writing merges this session's category scores, recomputes weak areas, and regenerates a short rolling LLM-written summary. Both the read and write paths are fully isolated behind try/except — a memory-store problem can never break interview preparation or report generation.

**Tech Stack:** Python/FastAPI/Pydantic (backend), the existing `google-genai` + `traced_generation` tracing pattern for the one new LLM call, Next.js/TypeScript (frontend), Redis (existing service, no new infra).

**Spec:** [`docs/superpowers/specs/2026-10-02-cross-session-candidate-memory-design.md`](../specs/2026-10-02-cross-session-candidate-memory-design.md)

## Global Constraints

- No new infrastructure — reuse the existing `redis_client` (`mockmind/backend/services/redis_client.py`).
- Redis key: `candidate_memory:{sha256(email.strip().lower())}`, TTL = `60 * 60 * 24 * 365` seconds (1 year) — a deliberate expiry, not forever.
- Weak-category threshold: average score < `6.0`; if more than 3 categories qualify, keep only the 3 lowest-scoring.
- `asked_questions` is truncated to the most recent 50 entries after each update.
- Memory read and write paths must never raise into interview preparation or report generation — every memory I/O call is wrapped in try/except, failures logged only, never re-raised.
- Memory is never injected into the live interviewer system prompt (`agent/prompts.py`) — only into the question-generation prompt (`backend/agents/question_generator.py`). This deliberately avoids adding another prompt-injection surface on top of the ones an earlier audit of this codebase already found.
- The report's `category_scores` uses a fixed 5-key set (`behavioral`, `technical`, `situational`, `resume_deep_dive`, `communication`) that does not map 1:1 onto `QuestionCategory`. A weak `communication` score becomes qualitative prompt guidance, never a question-category quota — there is no "communication-category question" to ask more of.
- `use_memory` defaults to `False`; `candidate_email` is only read/used when `use_memory` is `True`.
- Every new Gemini call uses the existing `traced_generation` helper (`backend/services/tracing.py`), consistent with every other LLM call in this codebase.
- This codebase has no test framework (confirmed: no `tests/` dir, no pytest config anywhere). Tests in this plan are plain runnable Python scripts with `assert` statements — the same verification style already used for every other feature in this project — not pytest. Don't introduce pytest as a side effect of this plan.

## Review Focus

- First-time candidate / no existing `CandidateMemory` in Redis yet — `get_memory` returns `None`, and both `generate_questions(candidate_memory=None)` and `update_memory_from_report(existing=None, ...)` must handle that cleanly (identical behavior to no-memory, and fresh-record creation, respectively) rather than crashing on a missing attribute.
- `use_memory=True` submitted with a blank/missing `candidate_email` — must be treated as not opted in (no read, no write), not raise an error.
- Redis/memory-store unavailable when fetching or saving — interview preparation and report generation must both complete successfully regardless, with the failure only logged.
- A candidate with no weak categories yet (e.g. a strong performer, all scores >= 6.0) — the prompt injection must omit the weak-areas bias cleanly, not inject a confusing empty list.
- Deleting `candidate_memory` for an email that was never stored — must return a clean success, not a 404/500, since "forget me" should be idempotent.

---

### Task 1: CandidateMemory data model

**Files:**
- Create: `mockmind/backend/models/candidate_memory.py`
- Test: `mockmind/backend/tests/test_candidate_memory_model.py`

**Interfaces:**
- Produces: `CandidateMemory` (fields: `email: str`, `sessions: list[str]`, `category_scores_history: dict[str, list[float]]`, `weak_categories: list[str]`, `asked_questions: list[QuestionHistoryEntry]`, `interviewer_notes: str`, `updated_at: float`), `QuestionHistoryEntry` (fields: `session_id: str`, `question: str`, `category: str`, `asked_at: float`) — both Pydantic `BaseModel`s, used by every later task.

- [ ] **Step 1: Write the failing test**

Create `mockmind/backend/tests/__init__.py` (empty file) if it doesn't exist yet, then create `mockmind/backend/tests/test_candidate_memory_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_candidate_memory_model`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.models.candidate_memory'`

- [ ] **Step 3: Write minimal implementation**

Create `mockmind/backend/models/candidate_memory.py`:

```python
from pydantic import BaseModel


class QuestionHistoryEntry(BaseModel):
    session_id: str
    question: str
    category: str  # QuestionCategory value, as a plain string
    asked_at: float


class CandidateMemory(BaseModel):
    email: str
    sessions: list[str] = []
    category_scores_history: dict[str, list[float]] = {}
    weak_categories: list[str] = []
    asked_questions: list[QuestionHistoryEntry] = []
    interviewer_notes: str = ""
    updated_at: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_candidate_memory_model`
Expected: `test_defaults PASS` then `test_roundtrip_json PASS`

- [ ] **Step 5: Commit**

```bash
cd mockmind
git add backend/models/candidate_memory.py backend/tests/__init__.py backend/tests/test_candidate_memory_model.py
git commit -m "feat: add CandidateMemory data model"
```

---

### Task 2: Redis-backed memory store

**Files:**
- Create: `mockmind/backend/services/memory_store.py`
- Test: `mockmind/backend/tests/test_memory_store.py`

**Interfaces:**
- Consumes: `CandidateMemory` from Task 1; `redis_client` from `backend/services/redis_client.py` (existing: `redis.asyncio` client, `decode_responses=True`, exposes `.get(key)`, `.setex(key, ttl, value)`, `.delete(key)`).
- Produces: `async def get_memory(email: str) -> CandidateMemory | None`, `async def save_memory(memory: CandidateMemory) -> None`, `async def delete_memory(email: str) -> None` — used by Task 5 (write) and Task 6 (read/delete).

**Requires a real Redis running** on `REDIS_URL` (default `redis://localhost:6379`) for this task's test — same as every other Redis-touching test in this project. If you don't already have one: `docker run -d --name mockmind-redis -p 6379:6379 redis:7-alpine`.

- [ ] **Step 1: Write the failing test**

Create `mockmind/backend/tests/test_memory_store.py`:

```python
"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_store
Requires a real Redis on REDIS_URL (default redis://localhost:6379)."""
import asyncio
import time

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.models.candidate_memory import CandidateMemory
from backend.services.memory_store import get_memory, save_memory, delete_memory

TEST_EMAIL = "memory-store-test@example.com"


async def main():
    # Clean slate in case a previous run left this key behind.
    await delete_memory(TEST_EMAIL)

    assert await get_memory(TEST_EMAIL) is None
    print("get_memory on missing key returns None: PASS")

    memory = CandidateMemory(email=TEST_EMAIL, weak_categories=["technical"], updated_at=time.time())
    await save_memory(memory)

    fetched = await get_memory(TEST_EMAIL)
    assert fetched is not None
    assert fetched.email == TEST_EMAIL
    assert fetched.weak_categories == ["technical"]
    print("save_memory then get_memory round-trips: PASS")

    await delete_memory(TEST_EMAIL)
    assert await get_memory(TEST_EMAIL) is None
    print("delete_memory removes the record: PASS")

    # Deleting an email that was never stored must not raise (Review Focus #5).
    await delete_memory("never-stored@example.com")
    print("delete_memory on a non-existent email does not raise: PASS")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_store`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.memory_store'`

- [ ] **Step 3: Write minimal implementation**

Create `mockmind/backend/services/memory_store.py`:

```python
import hashlib

from backend.models.candidate_memory import CandidateMemory
from backend.services.redis_client import redis_client

KEY_PREFIX = "candidate_memory:"
TTL_SECONDS = 60 * 60 * 24 * 365  # 1 year — a deliberate expiry, not forever


def _key(email: str) -> str:
    normalized = email.strip().lower()
    return KEY_PREFIX + hashlib.sha256(normalized.encode()).hexdigest()


async def get_memory(email: str) -> CandidateMemory | None:
    raw = await redis_client.get(_key(email))
    if not raw:
        return None
    return CandidateMemory.model_validate_json(raw)


async def save_memory(memory: CandidateMemory) -> None:
    await redis_client.setex(_key(memory.email), TTL_SECONDS, memory.model_dump_json())


async def delete_memory(email: str) -> None:
    await redis_client.delete(_key(email))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_store`
Expected: all four `PASS` lines printed, no exception.

- [ ] **Step 5: Commit**

```bash
cd mockmind
git add backend/services/memory_store.py backend/tests/test_memory_store.py
git commit -m "feat: add Redis-backed candidate memory store"
```

---

### Task 3: Merge logic for updating memory from a finished report

**Files:**
- Create: `mockmind/backend/services/memory_updater.py`
- Test: `mockmind/backend/tests/test_memory_updater.py`

**Interfaces:**
- Consumes: `CandidateMemory`, `QuestionHistoryEntry` from Task 1.
- Produces: `async def update_memory_from_report(existing: CandidateMemory | None, email: str, session_id: str, plan: dict, report: dict) -> CandidateMemory` — a pure merge function (no Redis I/O inside it, so it's testable without a live store) used by Task 5.

This task makes one real Gemini call (to regenerate `interviewer_notes`) — needs `GOOGLE_API_KEY` set in `mockmind/.env`, same as every other LLM-calling test in this project.

- [ ] **Step 1: Write the failing test**

Create `mockmind/backend/tests/test_memory_updater.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_updater`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.memory_updater'`

- [ ] **Step 3: Write minimal implementation**

Create `mockmind/backend/services/memory_updater.py`:

```python
import json
import os
import time

from google import genai
from google.genai import types

from backend.models.candidate_memory import CandidateMemory, QuestionHistoryEntry
from backend.services.tracing import traced_generation

WEAK_THRESHOLD = 6.0
MAX_WEAK_CATEGORIES = 3
MAX_ASKED_QUESTIONS = 50

NOTES_PROMPT = """
You maintain a short rolling summary of a candidate's performance across
multiple mock interview sessions.

PREVIOUS NOTES:
{previous_notes}

THIS SESSION'S REPORT SUMMARY:
{report_summary}

THIS SESSION'S CATEGORY SCORES:
{category_scores_json}

Update the notes in 2-3 sentences, describing TRENDS across sessions (e.g.
"has improved at providing concrete metrics, still tends to give vague
system-design answers") rather than just restating this one session. If
there are no previous notes, write an initial 2-3 sentence summary based on
this session alone. Return ONLY the updated notes text — no JSON, no
markdown, no preamble.
"""


def _recompute_weak_categories(category_scores_history: dict[str, list[float]]) -> list[str]:
    averages = {
        category: sum(scores) / len(scores)
        for category, scores in category_scores_history.items()
        if scores
    }
    weak = sorted(
        (cat for cat, avg in averages.items() if avg < WEAK_THRESHOLD),
        key=lambda cat: averages[cat],
    )
    return weak[:MAX_WEAK_CATEGORIES]


async def _regenerate_notes(previous_notes: str, report: dict, category_scores: dict, session_id: str) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = NOTES_PROMPT.format(
        previous_notes=previous_notes or "(none yet — this is their first session)",
        report_summary=report.get("summary", ""),
        category_scores_json=json.dumps(category_scores, indent=2),
    )
    with traced_generation("memory_notes_update", session_id=session_id, input_data=prompt) as gen:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1024,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        gen.record_response(response)
        return response.text.strip()


async def update_memory_from_report(
    existing: CandidateMemory | None,
    email: str,
    session_id: str,
    plan: dict,
    report: dict,
) -> CandidateMemory:
    """Pure merge logic — no Redis I/O, so it's testable without a live store."""
    memory = existing or CandidateMemory(email=email, updated_at=time.time())

    memory.sessions = [*memory.sessions, session_id]

    category_scores = report.get("category_scores", {})
    for category, score in category_scores.items():
        memory.category_scores_history.setdefault(category, []).append(score)

    memory.weak_categories = _recompute_weak_categories(memory.category_scores_history)

    new_entries = [
        QuestionHistoryEntry(
            session_id=session_id,
            question=q["question"],
            category=q["category"],
            asked_at=plan.get("created_at", time.time()),
        )
        for q in plan.get("questions", [])
    ]
    memory.asked_questions = (memory.asked_questions + new_entries)[-MAX_ASKED_QUESTIONS:]

    memory.interviewer_notes = await _regenerate_notes(
        memory.interviewer_notes, report, category_scores, session_id
    )
    memory.updated_at = time.time()
    return memory
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_updater`
Expected: all three `PASS` lines printed, no exception. (`interviewer_notes` content is LLM-generated and will vary — the test only asserts it's non-empty, not specific wording.)

- [ ] **Step 5: Commit**

```bash
cd mockmind
git add backend/services/memory_updater.py backend/tests/test_memory_updater.py
git commit -m "feat: add candidate memory update/merge logic"
```

---

### Task 4: Wire memory into question_generator.py (read path)

**Files:**
- Modify: `mockmind/backend/models/interview_plan.py` (add `InterviewPlan.candidate_email`)
- Modify: `mockmind/backend/agents/question_generator.py`
- Test: `mockmind/backend/tests/test_question_generator_memory.py`

**Interfaces:**
- Consumes: `CandidateMemory` from Task 1.
- Produces: `generate_questions(..., candidate_memory: CandidateMemory | None = None, candidate_email: str | None = None)` — new optional parameters, backward compatible with every existing call site (`backend/routers/prepare.py`, `evals/run_eval.py`, `evals/optimizer/optimizer.py` all call it positionally/by the existing keyword names only, so this is additive). `InterviewPlan.candidate_email: str | None = None` — new field, used by Task 5.

This task makes real Gemini calls — needs `GOOGLE_API_KEY` in `mockmind/.env`.

- [ ] **Step 1: Write the failing test**

Create `mockmind/backend/tests/test_question_generator_memory.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_question_generator_memory`
Expected: FAIL with `TypeError: generate_questions() got an unexpected keyword argument 'candidate_memory'`

- [ ] **Step 3: Add `InterviewPlan.candidate_email`**

In `mockmind/backend/models/interview_plan.py`, in the `InterviewPlan` class, add after the existing `level_weights` field:

```python
    # Set only when the candidate opted in to cross-session memory at setup.
    # Read by agent/session_state.py's generate_and_store_report() to decide
    # whether to update candidate memory after this session.
    candidate_email: Optional[str] = None
```

- [ ] **Step 4: Add the memory-context prompt builder and new parameters**

In `mockmind/backend/agents/question_generator.py`, add this import alongside the existing ones:

```python
from backend.models.candidate_memory import CandidateMemory
```

Add this constant and function after `_LEVEL_FRAMEWORK` (before `QUESTION_GENERATION_PROMPT`):

```python
_QUESTION_CATEGORIES = {"behavioral", "technical", "situational", "resume_deep_dive"}


def _build_memory_context(memory: CandidateMemory | None) -> str:
    """Soft, qualitative bias from a returning candidate's history — not a
    hard quota like the difficulty-level sequence, since "weak category" is
    a fuzzier signal than a clean 3-way enum. Never injected into the live
    interviewer system prompt (agent/prompts.py) — question generation only."""
    if memory is None:
        return ""

    lines = ["\n\n== RETURNING CANDIDATE CONTEXT ==\n", "This candidate has interviewed before.\n"]

    question_weak = [c for c in memory.weak_categories if c in _QUESTION_CATEGORIES]
    if question_weak:
        lines.append(
            f"Historically weaker areas: {', '.join(question_weak)}. Skew "
            f"technical/situational/behavioral/resume_deep_dive question "
            f"selection toward these areas more than the usual mix, without "
            f"abandoning balanced coverage entirely.\n"
        )
    if "communication" in memory.weak_categories:
        lines.append(
            "This candidate has also had communication/clarity issues in "
            "past sessions — favor follow-ups that push for specific, "
            "structured answers.\n"
        )
    if memory.asked_questions:
        recent = [q.question for q in memory.asked_questions[-15:]]
        lines.append(
            "Do not repeat these exact previously-asked questions (new "
            "questions on the same topic are fine, verbatim repeats are "
            "not):\n" + "\n".join(f"- {q}" for q in recent) + "\n"
        )
    if memory.interviewer_notes:
        lines.append(f"Interviewer's running notes on this candidate: {memory.interviewer_notes}\n")

    return "".join(lines)
```

Change the `generate_questions` signature from:

```python
async def generate_questions(
    candidate: CandidateProfile,
    job: JobProfile,
    session_id: str,
    level_weights: dict | None = None,
    total_questions: int = DEFAULT_TOTAL_QUESTIONS,
    num_coding_questions: int = 0,
) -> InterviewPlan:
```

to:

```python
async def generate_questions(
    candidate: CandidateProfile,
    job: JobProfile,
    session_id: str,
    level_weights: dict | None = None,
    total_questions: int = DEFAULT_TOTAL_QUESTIONS,
    num_coding_questions: int = 0,
    candidate_memory: CandidateMemory | None = None,
    candidate_email: str | None = None,
) -> InterviewPlan:
```

Inside the function body, change:

```python
    prompt = _build_prompt(candidate, job, level_sequence, coding_slots)
```

to:

```python
    prompt = _build_prompt(candidate, job, level_sequence, coding_slots)
    prompt += _build_memory_context(candidate_memory)
```

And change the final `return InterviewPlan(...)` block to add `candidate_email=candidate_email,` as the last argument:

```python
    return InterviewPlan(
        session_id=session_id,
        candidate=candidate,
        job=job,
        questions=questions,
        opening_message=data["opening_message"],
        interview_style=data.get("interview_style", "conversational"),
        total_duration_minutes=data.get("total_duration_minutes", 30),
        created_at=time.time(),
        level_weights=normalized_weights,
        candidate_email=candidate_email,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_question_generator_memory`
Expected: all three `PASS` lines printed. (The exact `technical_count` printed will vary run to run since this is real LLM generation — only the verbatim-repeat assertion is a hard check; eyeball that the technical count looks reasonably skewed, don't hard-assert an exact number.)

- [ ] **Step 6: Commit**

```bash
cd mockmind
git add backend/models/interview_plan.py backend/agents/question_generator.py backend/tests/test_question_generator_memory.py
git commit -m "feat: bias question generation toward a returning candidate's weak areas"
```

---

### Task 5: Wire memory into the agent's report flow (write path)

**Files:**
- Modify: `mockmind/agent/session_state.py`
- Test: `mockmind/backend/tests/test_session_state_memory_write.py`

**Interfaces:**
- Consumes: `get_memory`/`save_memory` (Task 2), `update_memory_from_report` (Task 3), `InterviewPlan.candidate_email` (Task 4).
- Produces: `generate_and_store_report()` now also updates candidate memory as a side effect when `state.plan.candidate_email` is set — no new public interface, this is the integration point later tasks don't need to know about.

This test imports from `agent/`, which depends on `livekit-agents` — run it with the **agent venv**, not the backend venv: `agent/.venv/bin/python`. Needs a real Redis and `GOOGLE_API_KEY` (same as Tasks 2-4).

- [ ] **Step 1: Write the failing test**

Create `mockmind/backend/tests/test_session_state_memory_write.py` (lives in `backend/tests/` for consistency with the other test files even though it exercises `agent/` code — this project doesn't have an `agent/tests/` directory, and this is the one test in this plan that needs the agent venv specifically):

```python
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

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockmind && agent/.venv/bin/python -m backend.tests.test_session_state_memory_write`
Expected: FAIL — `assert memory is not None` fails, since `generate_and_store_report` doesn't update memory yet.

- [ ] **Step 3: Write minimal implementation**

In `mockmind/agent/session_state.py`, change the end of `generate_and_store_report`:

```python
async def generate_and_store_report(state: AgentSessionState):
    """
    Background coroutine: generate the post-interview report and store it in Redis.
    Called either by the end_interview tool or the session shutdown callback.
    """
    import json
    import redis.asyncio as redis_mod
    from backend.services.report_generator import generate_report

    try:
        report = await generate_report(
            session_id=state.session_id,
            plan=state.plan.model_dump(),
            transcript=state.transcript,
        )
        r = redis_mod.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await r.setex(
                f"interview_report:{state.session_id}",
                86400,
                json.dumps(report),
            )
        finally:
            await r.aclose()
    except Exception as e:
        import logging
        logging.getLogger("mockmind_agent").error(f"Report generation failed: {e}")
        return

    if state.plan.candidate_email:
        try:
            from backend.services.memory_store import get_memory, save_memory
            from backend.services.memory_updater import update_memory_from_report

            existing = await get_memory(state.plan.candidate_email)
            updated = await update_memory_from_report(
                existing=existing,
                email=state.plan.candidate_email,
                session_id=state.session_id,
                plan=state.plan.model_dump(),
                report=report,
            )
            await save_memory(updated)
        except Exception as e:
            import logging
            logging.getLogger("mockmind_agent").error(f"Candidate memory update failed: {e}")
```

(Only the part after the first `try/except` block is new — report generation and storage are unchanged, and the memory update only runs after the report has already been successfully produced and stored.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mockmind && agent/.venv/bin/python -m backend.tests.test_session_state_memory_write`
Expected: all three `PASS` lines printed. (This makes real `generate_report`/`update_memory_from_report` Gemini calls for the first two scenarios, so it takes ~15-30s; the third scenario's save failure is mocked and fast.)

- [ ] **Step 5: Commit**

```bash
cd mockmind
git add agent/session_state.py backend/tests/test_session_state_memory_write.py
git commit -m "feat: update candidate memory after an opted-in interview's report completes"
```

---

### Task 6: Wire memory into /api/prepare (read path + opt-in fields)

**Files:**
- Modify: `mockmind/backend/routers/prepare.py`
- Test: manual curl against a running backend (this is an HTTP router — see rationale below)

**Interfaces:**
- Consumes: `get_memory` (Task 2), `generate_questions(candidate_memory=..., candidate_email=...)` (Task 4).
- Produces: `/api/prepare` accepts two new optional form fields, `use_memory` (bool, default `False`) and `candidate_email` (str, default `""`).

This task's core logic (`prepare_interview` itself) is tightly coupled to FastAPI's `UploadFile`/`Form`/`StreamingResponse` machinery, and this project has no HTTP test client set up (consistent with "no test framework" — adding one just for this endpoint would be a bigger change than the feature itself). Starting the real server and `curl`-ing it is the same technique already used throughout this project's development to verify other HTTP services (Langfuse, Piston). But `_maybe_fetch_memory` — the one piece of this task's logic that needs to prove it survives a memory-store failure (Review Focus #3) — is a plain importable function, so that specific case gets its own fast, standalone Python test instead of going through a live server.

- [ ] **Step 1: Write the failing resilience test**

Create `mockmind/backend/tests/test_maybe_fetch_memory_resilience.py`:

```python
"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_maybe_fetch_memory_resilience
No real Redis needed — this specifically tests what happens when the memory
store is unreachable/erroring (Review Focus #3)."""
import asyncio
from unittest.mock import patch

from backend.routers.prepare import _maybe_fetch_memory


async def main():
    # use_memory=False: must skip the store entirely, regardless of email.
    memory, email = await _maybe_fetch_memory(False, "someone@example.com")
    assert memory is None and email is None
    print("use_memory=False skips the store entirely: PASS")

    # Simulates the memory store being down/erroring — must not raise, and
    # must not block interview preparation.
    with patch(
        "backend.services.memory_store.get_memory",
        side_effect=ConnectionError("simulated Redis outage"),
    ):
        memory, email = await _maybe_fetch_memory(True, "someone@example.com")
        assert memory is None
        assert email == "someone@example.com"  # email is still normalized/returned
    print("memory-store failure is swallowed, does not raise: PASS")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_maybe_fetch_memory_resilience`
Expected: FAIL with `ImportError: cannot import name '_maybe_fetch_memory' from 'backend.routers.prepare'`

- [ ] **Step 3: Write the (currently failing) manual HTTP test script**

Create `mockmind/backend/tests/test_prepare_memory.sh`:

```bash
#!/usr/bin/env bash
# Run: cd mockmind && bash backend/tests/test_prepare_memory.sh
# Requires: backend running on :8000 (backend/.venv/bin/uvicorn backend.main:app --port 8000),
# a real Redis, and GOOGLE_API_KEY set.
set -euo pipefail

RESUME_FILE=$(mktemp /tmp/resume-XXXX.txt)
echo "Priya Sharma. Backend Engineer. 4 years. Python, FastAPI, Docker." > "$RESUME_FILE"

echo "--- Request WITHOUT use_memory (should work exactly as before) ---"
curl -sS -X POST http://localhost:8000/api/prepare \
  -F "resume=@${RESUME_FILE}" \
  -F "job_description=AI Engineer role requiring Python, LLMs, Docker, Kubernetes, and strong system design skills for a growing startup." \
  | tee /tmp/prepare_no_memory.sse
grep -q '"stage": "complete"' /tmp/prepare_no_memory.sse && echo "no-memory request completed: PASS"

echo ""
echo "--- Request WITH use_memory=true and a blank email (Review Focus #2 — must not error) ---"
curl -sS -X POST http://localhost:8000/api/prepare \
  -F "resume=@${RESUME_FILE}" \
  -F "job_description=AI Engineer role requiring Python, LLMs, Docker, Kubernetes, and strong system design skills for a growing startup." \
  -F "use_memory=true" \
  -F "candidate_email=" \
  | tee /tmp/prepare_blank_email.sse
grep -q '"stage": "complete"' /tmp/prepare_blank_email.sse && echo "use_memory with blank email still completes: PASS"

echo ""
echo "--- Request WITH use_memory=true and a real email (should complete normally) ---"
curl -sS -X POST http://localhost:8000/api/prepare \
  -F "resume=@${RESUME_FILE}" \
  -F "job_description=AI Engineer role requiring Python, LLMs, Docker, Kubernetes, and strong system design skills for a growing startup." \
  -F "use_memory=true" \
  -F "candidate_email=prepare-test@example.com" \
  | tee /tmp/prepare_with_email.sse
grep -q '"stage": "complete"' /tmp/prepare_with_email.sse && echo "use_memory with real email completes: PASS"

rm -f "$RESUME_FILE"
```

- [ ] **Step 4: Run the HTTP test to verify it fails**

Run: `cd mockmind && backend/.venv/bin/uvicorn backend.main:app --port 8000 &` (leave running), then `bash backend/tests/test_prepare_memory.sh`
Expected: the first (no-memory) request still passes as before, but the second and third requests FAIL — `curl` itself succeeds, but FastAPI returns a 422 Unprocessable Entity (unexpected form fields `use_memory`/`candidate_email`) before any SSE stream is produced, so the `grep` for `"stage": "complete"` finds nothing.

- [ ] **Step 5: Write minimal implementation**

In `mockmind/backend/routers/prepare.py`, change the imports at the top to add:

```python
from fastapi import APIRouter, UploadFile, File, Form
```

(this import already exists — `Form` is already imported; no change needed here, just confirming the existing import covers the new fields).

Add this helper function after the imports, before `router = APIRouter()`:

```python
async def _maybe_fetch_memory(use_memory: bool, candidate_email: str):
    """Returns (memory_or_None, normalized_email_or_None). Never raises — a
    memory-store problem must not block interview preparation."""
    email = (candidate_email or "").strip()
    if not use_memory or not email:
        return None, None
    try:
        from backend.services.memory_store import get_memory
        memory = await get_memory(email)
        return memory, email
    except Exception:
        logger.exception("Failed to fetch candidate memory for %s", email)
        return None, email
```

Change the `prepare_interview` function signature from:

```python
async def prepare_interview(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
```

to:

```python
async def prepare_interview(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    use_memory: bool = Form(False),
    candidate_email: str = Form(""),
):
```

Inside `event_stream()`, change:

```python
            # Stage 4: Generate questions (Sub-Agent 3)
            yield _sse({"stage": "question_gen", "message": "Crafting personalized interview questions...", "progress": 70, "session_id": session_id})
            plan = await generate_questions(candidate_profile, job_profile, session_id)
```

to:

```python
            # Stage 4: Generate questions (Sub-Agent 3)
            yield _sse({"stage": "question_gen", "message": "Crafting personalized interview questions...", "progress": 70, "session_id": session_id})
            memory, normalized_email = await _maybe_fetch_memory(use_memory, candidate_email)
            plan = await generate_questions(
                candidate_profile, job_profile, session_id,
                candidate_memory=memory, candidate_email=normalized_email,
            )
```

- [ ] **Step 6: Run both tests to verify they pass**

Run: `cd mockmind && backend/.venv/bin/python -m backend.tests.test_maybe_fetch_memory_resilience`
Expected: both `PASS` lines printed.

Restart the server (`Ctrl+C` the backgrounded uvicorn, start it again) to pick up the code change, then run: `cd mockmind && bash backend/tests/test_prepare_memory.sh`
Expected: all three `PASS` lines printed.

- [ ] **Step 7: Commit**

```bash
cd mockmind
git add backend/routers/prepare.py backend/tests/test_maybe_fetch_memory_resilience.py backend/tests/test_prepare_memory.sh
git commit -m "feat: accept use_memory/candidate_email in /api/prepare"
```

---

### Task 7: Forget-me endpoint

**Files:**
- Create: `mockmind/backend/routers/memory.py`
- Modify: `mockmind/backend/main.py`
- Test: manual curl against a running backend (same rationale as Task 6)

**Interfaces:**
- Consumes: `delete_memory` (Task 2).
- Produces: `DELETE /api/candidate-memory` HTTP endpoint.

- [ ] **Step 1: Write the (currently failing) manual test script**

Create `mockmind/backend/tests/test_memory_endpoint.sh`:

```bash
#!/usr/bin/env bash
# Run: cd mockmind && bash backend/tests/test_memory_endpoint.sh
# Requires: backend running on :8000, a real Redis.
set -euo pipefail

echo "--- Delete an email that was never stored (Review Focus #5 — must be a clean success) ---"
STATUS=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/candidate-memory \
  -H "Content-Type: application/json" \
  -d '{"email": "never-stored-via-api@example.com"}')
[ "$STATUS" = "204" ] && echo "delete on non-existent email returns 204: PASS" || (echo "got $STATUS"; exit 1)

echo ""
echo "--- Missing email in body must be a 400, not a 500 ---"
STATUS=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/candidate-memory \
  -H "Content-Type: application/json" \
  -d '{"email": ""}')
[ "$STATUS" = "400" ] && echo "blank email returns 400: PASS" || (echo "got $STATUS"; exit 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockmind && bash backend/tests/test_memory_endpoint.sh`
Expected: FAIL — `curl` gets a 404 (no such route exists yet), the first assertion's `[ "$STATUS" = "204" ]` fails and the script exits non-zero.

- [ ] **Step 3: Write minimal implementation**

Create `mockmind/backend/routers/memory.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.memory_store import delete_memory

router = APIRouter()


class ForgetMeRequest(BaseModel):
    email: str


@router.delete("/api/candidate-memory", status_code=204)
async def forget_me(req: ForgetMeRequest):
    email = req.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    await delete_memory(email)
```

In `mockmind/backend/main.py`, change:

```python
from backend.routers import prepare, session, health
```

to:

```python
from backend.routers import prepare, session, health, memory
```

and change:

```python
app.include_router(health.router)
app.include_router(prepare.router)
app.include_router(session.router)
```

to:

```python
app.include_router(health.router)
app.include_router(prepare.router)
app.include_router(session.router)
app.include_router(memory.router)
```

- [ ] **Step 4: Run test to verify it passes**

Restart the server to pick up the new router, then run: `cd mockmind && bash backend/tests/test_memory_endpoint.sh`
Expected: both `PASS` lines printed.

- [ ] **Step 5: Commit**

```bash
cd mockmind
git add backend/routers/memory.py backend/main.py backend/tests/test_memory_endpoint.sh
git commit -m "feat: add DELETE /api/candidate-memory forget-me endpoint"
```

---

### Task 8: Frontend — opt-in checkbox and email field

**Files:**
- Modify: `mockmind/frontend/hooks/usePreparation.ts`
- Modify: `mockmind/frontend/app/setup/page.tsx`

**Interfaces:**
- Consumes: `/api/prepare`'s new `use_memory`/`candidate_email` form fields (Task 6).
- Produces: `startPreparation(resumeFile, jobDescription, useMemory?, candidateEmail?)` — additive optional parameters, so any other caller of this hook (there are none today) keeps working unchanged.

- [ ] **Step 1: Thread the new fields through `usePreparation.ts`**

In `mockmind/frontend/hooks/usePreparation.ts`, change:

```typescript
  const startPreparation = useCallback(
    async (resumeFile: File, jobDescription: string) => {
      setIsRunning(true);
      setEvents([]);
      setError(null);
      setSessionInfo(null);
      setCurrentProgress(0);

      const formData = new FormData();
      formData.append('resume', resumeFile);
      formData.append('job_description', jobDescription);
```

to:

```typescript
  const startPreparation = useCallback(
    async (
      resumeFile: File,
      jobDescription: string,
      useMemory: boolean = false,
      candidateEmail: string = '',
    ) => {
      setIsRunning(true);
      setEvents([]);
      setError(null);
      setSessionInfo(null);
      setCurrentProgress(0);

      const formData = new FormData();
      formData.append('resume', resumeFile);
      formData.append('job_description', jobDescription);
      formData.append('use_memory', String(useMemory));
      if (useMemory && candidateEmail.trim()) {
        formData.append('candidate_email', candidateEmail.trim());
      }
```

- [ ] **Step 2: Add the checkbox + email field to the setup page**

In `mockmind/frontend/app/setup/page.tsx`, change:

```typescript
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
```

to:

```typescript
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
  const [useMemory, setUseMemory] = useState(false);
  const [candidateEmail, setCandidateEmail] = useState('');
```

Change:

```typescript
  const handleStart = async () => {
    if (!resumeFile || !jobDescription.trim()) return;
    await startPreparation(resumeFile, jobDescription);
  };
```

to:

```typescript
  const handleStart = async () => {
    if (!resumeFile || !jobDescription.trim()) return;
    await startPreparation(resumeFile, jobDescription, useMemory, candidateEmail);
  };
```

Add this block right after the closing `</div>` of the "Job Description" section (before the `{/* Preparation Progress */}` comment):

```tsx
          {/* Cross-session memory opt-in */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-3">
            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={useMemory}
                onChange={(e) => setUseMemory(e.target.checked)}
                disabled={isRunning}
                className="mt-0.5 w-4 h-4 rounded border-white/20 bg-white/5 accent-blue-500"
              />
              <span className="text-sm text-slate-300">
                Remember my performance across sessions — future interviews
                will focus more on areas I've historically struggled with.
              </span>
            </label>
            {useMemory && (
              <input
                type="email"
                value={candidateEmail}
                onChange={(e) => setCandidateEmail(e.target.value)}
                placeholder="your@email.com"
                disabled={isRunning}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-blue-400/50 outline-none transition-colors"
              />
            )}
          </div>
```

- [ ] **Step 3: Type-check and build**

Run: `cd mockmind/frontend && npx tsc --noEmit`
Expected: no output (no type errors).

Run: `cd mockmind/frontend && npm run build`
Expected: `✓ Compiled successfully`, same as every prior build in this project.

- [ ] **Step 4: Commit**

```bash
cd mockmind
git add frontend/hooks/usePreparation.ts frontend/app/setup/page.tsx
git commit -m "feat: add cross-session memory opt-in to the setup page"
```

---

## Known gap (carried from the spec, not fixed by this plan)

The eval harness (`evals/`) does not simulate multi-session candidates, so there's no automated regression coverage for "does memory bias actually survive into a full simulated interview end-to-end." Extending the candidate-simulator to run a two-session scenario would close this gap but is out of scope for this plan.
