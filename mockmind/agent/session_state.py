import json
import os
import time
from typing import Optional

import redis.asyncio as redis

from backend.models.interview_plan import InterviewPlan, SessionState


class AgentSessionState:
    def __init__(self, session_id: str, plan: InterviewPlan):
        self.session_id = session_id
        self.plan = plan
        self.current_question_index = 0
        self.asked_question_ids: list[str] = []
        self.follow_up_count_this_question = 0
        self.transcript: list[dict] = []
        self.started_at = time.time()
        self.ended_at: Optional[float] = None

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

    def add_transcript_entry(self, speaker: str, text: str):
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "timestamp": time.time(),
            "question_index": self.current_question_index,
        })

    def increment_follow_up_count(self):
        self.follow_up_count_this_question += 1

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
