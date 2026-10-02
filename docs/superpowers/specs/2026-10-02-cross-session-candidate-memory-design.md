# Cross-Session Candidate Memory — Design

**Status**: Approved in chat, pending written-spec review.
**Author**: Claude (session with Shrihari), 2026-10-02.

## Motivation

Today every MockMind interview is fully stateless: a fresh UUID session, a fresh resume upload, a fresh question bank, with zero awareness of any prior attempt by the same person. For a tool whose natural usage pattern is "practice again," that's a real gap — a candidate who bombed system-design questions last week gets no more system-design practice this week than anyone else.

This adds an opt-in memory layer: candidates who choose to be identified by email get a question bank that's informed by their own history (recurring weak areas get more attention, previously-asked questions aren't repeated verbatim), and that history visibly carries no cost to anyone who doesn't opt in.

## Goals

- Returning candidates (identified by email, no password) get question generation biased toward their historically weak areas.
- Memory updates automatically after each opted-in interview — no manual data entry.
- Fully opt-in, off by default, with a one-step way to delete stored history.
- Zero behavior change, zero new failure modes, for anyone who doesn't use it.

## Non-goals (explicitly out of scope for this pass)

- Real authentication (passwords, OTP, sessions) — email is a lookup key, not a credential. This is an accepted, explicit tradeoff already agreed in brainstorming: anyone who knows/guesses an email can see memory-influenced behavior for it, or delete it.
- The interviewer *speaking about* a candidate's history out loud — memory only biases which questions get generated, never gets quoted into the live system prompt. (Deliberately avoids adding another prompt-injection-shaped surface on top of the ones the earlier audit already found.)
- Any admin/analytics view across candidates.
- Changes to the frontend's report page, LiveKit/agent voice pipeline internals, or the eval harness (noted as a gap below).

## Data model

New file: `backend/models/candidate_memory.py`

```python
from pydantic import BaseModel

class QuestionHistoryEntry(BaseModel):
    session_id: str
    question: str
    category: str       # QuestionCategory value, as a plain string
    asked_at: float

class CandidateMemory(BaseModel):
    email: str
    sessions: list[str] = []                         # session_ids, newest last
    category_scores_history: dict[str, list[float]] = {}  # report category name -> scores over time
    weak_categories: list[str] = []                   # derived each update, see below
    asked_questions: list[QuestionHistoryEntry] = []
    interviewer_notes: str = ""                        # free-form, LLM-maintained, overwritten each update
    updated_at: float
```

**Important mapping note**: `report_generator.py`'s `category_scores` uses a fixed 5-key set (`behavioral`, `technical`, `situational`, `resume_deep_dive`, `communication`) that does **not** line up 1:1 with `QuestionCategory` (which also has `culture_fit` and `closing`, and has no `communication`). `communication` is a holistic quality assessed across the whole interview, not a specific question topic. Consequence for the read path: only `behavioral` / `technical` / `situational` / `resume_deep_dive` weak-scores feed the question-category bias; a weak `communication` score instead becomes qualitative guidance in the prompt (e.g. "favor follow-ups that push for specific, structured answers"), not a category quota, since there's no "communication-category question" to ask more of.

## Storage

New file: `backend/services/memory_store.py`, built on the existing `redis_client` (no new infrastructure):

```python
KEY_PREFIX = "candidate_memory:"
TTL_SECONDS = 60 * 60 * 24 * 365  # 1 year — a deliberate expiry, not forever

def _key(email: str) -> str:
    return KEY_PREFIX + hashlib.sha256(email.strip().lower().encode()).hexdigest()

async def get_memory(email: str) -> CandidateMemory | None: ...
async def save_memory(memory: CandidateMemory) -> None: ...
async def delete_memory(email: str) -> None: ...
```

Hashing the email in the key means a Redis `KEYS`/`SCAN` doesn't trivially enumerate raw email addresses; the email itself is still stored inside the value (needed to answer "whose record is this"), but isn't exposed just by listing keys.

## Write path

Triggered from the same place report generation already happens: `generate_and_store_report()` in `agent/session_state.py`, right after the report is produced. This requires `InterviewPlan` to carry the opted-in state through from setup to the live agent:

- `InterviewPlan` gains `candidate_email: str | None = None` (already has `level_weights` added in a prior pass as a precedent for this kind of traceability field).
- If `plan.candidate_email` is set:
  1. Fetch existing `CandidateMemory` (or start a fresh one).
  2. Merge this session's `report["category_scores"]` into `category_scores_history` (append each category's score to its list).
  3. Recompute `weak_categories`: filter to categories whose **average** score (across all history, this session included) is below `6.0`; if more than 3 qualify, keep only the 3 lowest-scoring — keeps the prompt injection compact and avoids a long tail of noise from one bad day.
  4. Append this session's asked questions (`plan.questions` -> `QuestionHistoryEntry`), then truncate to the most recent 50 entries to bound growth.
  5. One Gemini call (same `traced_generation` tracing pattern as every other LLM call in this codebase) to regenerate `interviewer_notes` — a 2-3 sentence rolling summary, given the old notes + this session's transcript/report, explicitly instructed to describe *trends* ("has improved at providing concrete metrics, still tends to give vague system-design answers") rather than re-describing a single session.
  6. Save.
- **Failure handling**: this entire write path is wrapped in try/except and only logged on failure — a memory-store problem must never fail report generation or the interview itself. Same principle already applied to Langfuse tracing elsewhere in this codebase (observability/memory is additive, never a hard dependency).

## Read path

In `backend/agents/question_generator.py`, `generate_questions()` gains an optional `candidate_memory: CandidateMemory | None = None` parameter. When present, a new prompt block is injected (modeled on the existing `_LEVEL_FRAMEWORK` injection pattern):

```
== RETURNING CANDIDATE CONTEXT ==
This candidate has interviewed before. Their historically weaker areas: {weak_categories}.
Skew technical/situational/behavioral/resume_deep_dive question selection toward these areas
more than the usual mix, without abandoning balanced coverage entirely.
{if "communication" is weak}: Favor follow-ups that push for specific, structured answers.
Do not repeat these exact previously-asked questions (new questions on the same topic are fine,
verbatim repeats are not): {asked_questions titles, most recent ~15}
Interviewer's running notes on this candidate: {interviewer_notes}
```

This is a soft, qualitative instruction — not a hard Python-enforced quota like the difficulty-level slot assignment — because "weak category" is fuzzier than a clean 3-way enum and forcing an exact count would be over-engineering a signal this soft.

`backend/routers/prepare.py` fetches the `CandidateMemory` (if `use_memory` and `candidate_email` were submitted) before calling `generate_questions()`, and passes `candidate_email` through to the constructed `InterviewPlan` either way (even reads can't fail the interview — a memory-store outage here just means no personalization this time, logged, not raised).

## API / frontend surface

- `POST /api/prepare`: two new optional form fields, `use_memory: bool = False` and `candidate_email: str | None = None`. Validated together: `candidate_email` is only read/used when `use_memory` is true.
- New `backend/routers/memory.py`: `DELETE /api/candidate-memory` with `{"email": "..."}` body → calls `delete_memory()`, returns 204. No confirmation flow beyond the request itself (consistent with the no-auth tradeoff already agreed).
- Frontend (`app/setup/page.tsx`): one new checkbox, unchecked by default — "Remember my performance across sessions" — which reveals an email input when checked. Both are sent as additional `FormData` fields alongside the existing resume/JD fields in `usePreparation.ts`'s `startPreparation()`.

## Testing plan

- Unit-level: `memory_store.py`'s get/save/delete against a real Redis (same pattern as everything else in this codebase — no mocks, per this project's own established practice of testing against real dependencies).
- `question_generator.py`: a standalone real-call test (same style used for the difficulty-levels and coding-questions features) — generate a plan with a synthetic `CandidateMemory` showing weak `technical` scores, confirm the resulting question mix is visibly skewed technical and doesn't repeat the seeded prior questions.
- End-to-end write path: run two synthetic report-generation calls back to back for the same email, confirm `category_scores_history` accumulates and `weak_categories`/`interviewer_notes` update sensibly.
- **Known gap**: the eval harness (`evals/`) does not currently simulate multi-session candidates, so there's no automated regression coverage for "does memory bias actually survive into a full simulated interview." Extending the candidate-simulator to run a two-session scenario would close this gap but is out of scope for this pass — flagged here rather than silently skipped.

## Files touched

| File | Change |
|---|---|
| `backend/models/candidate_memory.py` | new — `CandidateMemory`, `QuestionHistoryEntry` |
| `backend/services/memory_store.py` | new — Redis get/save/delete |
| `backend/models/interview_plan.py` | add `InterviewPlan.candidate_email: str \| None` |
| `backend/agents/question_generator.py` | add `candidate_memory` param + prompt injection |
| `backend/routers/prepare.py` | accept `use_memory`/`candidate_email`, fetch memory before generation |
| `backend/routers/memory.py` | new — `DELETE /api/candidate-memory` |
| `agent/session_state.py` | `generate_and_store_report()` writes memory when `plan.candidate_email` is set |
| `backend/main.py` | register the new memory router |
| `frontend/app/setup/page.tsx` | checkbox + email field |
| `frontend/hooks/usePreparation.ts` | pass new fields through to `/api/prepare` |
| `frontend/types/interview.ts` | no change needed (memory fields aren't surfaced to the UI beyond the input) |

## Privacy / limitations (restated plainly)

Identity here is an unverified email string. Anyone who knows or guesses a candidate's email can see memory-influenced behavior under it, or delete its history via the forget-me endpoint. This was an explicit, agreed tradeoff of skipping real authentication for this pass — not an oversight. If this is ever deployed somewhere a stranger might plausibly guess another person's email and care about their interview-practice history, revisit this before relying on it.
