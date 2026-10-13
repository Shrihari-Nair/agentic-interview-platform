import asyncio
import logging
import os
import time
from typing import Optional

import redis.asyncio as redis

from backend.models.interview_plan import InterviewPlan, SessionState

logger = logging.getLogger("mockmind_agent")

MAX_FOLLOW_UPS = 2
# Transcript autosave: coalesce bursts of entries into one Redis write.
_AUTOSAVE_DELAY_S = 1.0


class AgentSessionState:
    def __init__(self, session_id: str, plan: InterviewPlan):
        self.session_id = session_id
        self.plan = plan
        self.current_question_index = 0
        self.asked_question_ids: list[str] = []
        self.follow_up_count_this_question = 0
        self.candidate_turns_this_question = 0
        self.transcript: list[dict] = []
        self.started_at = time.time()
        self.ended_at: Optional[float] = None
        self._autosave_task: Optional[asyncio.Task] = None

    @classmethod
    async def load(cls, session_id: str) -> "AgentSessionState":
        r = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            plan_json = await r.get(f"interview_plan:{session_id}")
            if not plan_json:
                raise ValueError(f"No interview plan found for session {session_id}")
            plan = InterviewPlan.model_validate_json(plan_json)
            return cls(session_id=session_id, plan=plan)
        finally:
            await r.aclose()

    @property
    def current_question(self):
        if self.current_question_index < len(self.plan.questions):
            return self.plan.questions[self.current_question_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_question_index >= len(self.plan.questions)

    @property
    def questions_remaining(self) -> int:
        return len(self.plan.questions) - self.current_question_index

    def advance_question(self):
        q = self.current_question
        if q:
            self.asked_question_ids.append(q.id)
        self.current_question_index += 1
        self.follow_up_count_this_question = 0
        self.candidate_turns_this_question = 0

    def add_transcript_entry(self, speaker: str, text: str):
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "timestamp": time.time(),
            "question_index": self.current_question_index,
        })
        self._schedule_autosave()

    def increment_follow_up_count(self):
        self.follow_up_count_this_question += 1

    def record_candidate_turn(self) -> int:
        """Called once per completed candidate turn. The first turn on a
        question answers it; every later turn answers a follow-up. Counting
        this in code (not trusting the LLM to count) is what enforces the cap."""
        self.candidate_turns_this_question += 1
        self.follow_up_count_this_question = max(0, self.candidate_turns_this_question - 1)
        return self.follow_up_count_this_question

    @property
    def follow_up_cap_reached(self) -> bool:
        return self.follow_up_count_this_question >= MAX_FOLLOW_UPS

    def _schedule_autosave(self):
        """Persist the transcript to Redis shortly after it changes, so an
        agent crash mid-interview no longer loses the whole interview (the
        report can then still be generated/retried from Redis)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no event loop (e.g. sync unit tests) — shutdown hook still saves
        if self._autosave_task and not self._autosave_task.done():
            return
        self._autosave_task = loop.create_task(self._autosave())

    async def _autosave(self):
        await asyncio.sleep(_AUTOSAVE_DELAY_S)
        try:
            await self.save()
        except Exception:
            logger.exception("Transcript autosave failed for session %s", self.session_id)

    async def save(self):
        r = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            state = SessionState(
                session_id=self.session_id,
                plan=self.plan,
                current_question_index=self.current_question_index,
                asked_questions=self.asked_question_ids,
                transcript=self.transcript,
                started_at=self.started_at,
                ended_at=self.ended_at,
            )
            await r.setex(
                f"session_state:{self.session_id}",
                14400,
                state.model_dump_json(),
            )
        finally:
            await r.aclose()


def follow_up_policy_note(state: AgentSessionState) -> str | None:
    """The per-turn follow-up policy, shared by the live agent
    (InterviewerAgent.on_user_turn_completed) and the text-mode eval driver so
    the eval exercises the exact rule production enforces.

    Call once per completed candidate turn: it counts the turn and returns the
    note to show the LLM (None for coding questions, which are driven by code
    submissions rather than spoken follow-ups)."""
    q = state.current_question
    if q is None or q.question_type == "coding":
        return None
    used = state.record_candidate_turn()
    if state.follow_up_cap_reached:
        return (
            f"[system note] Follow-ups used on this question: {used}/{MAX_FOLLOW_UPS}. "
            "The limit is reached: do NOT ask another follow-up. Briefly acknowledge "
            "the candidate's answer, then call move_to_next_question."
        )
    return f"[system note] Follow-ups used on this question: {used}/{MAX_FOLLOW_UPS}."


async def generate_and_store_report(state: AgentSessionState):
    """
    Generate the post-interview report and store it in Redis (with a
    pending/ready/failed status). Called by the end_interview tool or the
    session shutdown callback. Never raises — see run_report_pipeline.
    """
    from backend.services.report_pipeline import run_report_pipeline

    # Persist the final transcript first so POST /api/report/{id}/retry can
    # regenerate the report even if generation below fails.
    try:
        await state.save()
    except Exception:
        logger.exception("Final state save failed for session %s", state.session_id)

    await run_report_pipeline(
        state.session_id,
        state.plan.model_dump(),
        state.transcript,
        state.plan.candidate_email,
    )
