import asyncio
import json
import logging
import time

from livekit.agents import Agent, RunContext, function_tool

from agent.prompts import build_interviewer_system_prompt
from agent.session_state import AgentSessionState, generate_and_store_report

logger = logging.getLogger(__name__)


class InterviewerAgent(Agent):
    def __init__(self, state: AgentSessionState):
        self._state = state

        system_prompt = build_interviewer_system_prompt(
            state.plan.model_dump_json(indent=2)
        )
        super().__init__(instructions=system_prompt)

    async def on_enter(self) -> None:
        """Speaks the opening message and asks the first question."""
        try:
            opening = self._state.plan.opening_message
            first_q = (
                self._state.plan.questions[0].question
                if self._state.plan.questions
                else "Tell me about yourself."
            )
            opening_text = f"{opening} {first_q}"
            self._state.add_transcript_entry("interviewer", opening_text)
            logger.info("on_enter: speaking opening message via session.say()")
            await self.session.say(opening_text, allow_interruptions=False)
            logger.info("on_enter: opening message spoken successfully")
        except Exception:
            logger.exception("on_enter: error while speaking opening message")

    @function_tool()
    async def move_to_next_question(self, context: RunContext) -> str:
        """
        Call this when you are ready to move to the next interview question.
        Call this AFTER finishing the current question and any follow-ups.
        Returns the next question to ask.
        """
        state: AgentSessionState = context.userdata

        state.advance_question()
        await state.save()

        if state.is_complete:
            return json.dumps({
                "status": "interview_complete",
                "message": "All questions have been asked. Call end_interview now.",
            })

        q = state.current_question
        return json.dumps({
            "status": "next_question",
            "question_number": state.current_question_index + 1,
            "total_questions": len(state.plan.questions),
            "question": q.question,
            "category": q.category,
            "intent": q.intent,
            "follow_ups": [
                {"trigger": fu.trigger, "question": fu.question}
                for fu in q.follow_ups
            ],
            "follow_ups_used_this_question": state.follow_up_count_this_question,
            "max_follow_ups": 2,
        })

    @function_tool()
    async def end_interview(self, context: RunContext) -> str:
        """
        Call this to formally end the interview session.
        This triggers report generation. Call it:
        - After all questions are asked, OR
        - If the candidate requests to end early.
        Before calling, say a proper closing statement to the candidate.
        """
        state: AgentSessionState = context.userdata
        state.ended_at = time.time()

        asyncio.create_task(generate_and_store_report(state))

        return json.dumps({
            "status": "session_ended",
            "questions_asked": len(state.asked_question_ids),
            "duration_minutes": round((state.ended_at - state.started_at) / 60, 1),
            "message": "Session ended. Report is being generated. Disconnect from the room.",
        })

    @function_tool()
    async def get_current_question_context(self, context: RunContext) -> str:
        """
        Returns the current question details including available follow-up options.
        Call this if you need to remind yourself of the current question.
        """
        state: AgentSessionState = context.userdata
        q = state.current_question

        if not q:
            return json.dumps({"status": "no_current_question", "interview_complete": True})

        return json.dumps({
            "question_number": state.current_question_index + 1,
            "total_questions": len(state.plan.questions),
            "current_question": q.question,
            "category": q.category,
            "intent": q.intent,
            "follow_ups_available": [
                {"trigger": fu.trigger, "question": fu.question}
                for fu in q.follow_ups
            ],
            "follow_ups_used_this_question": state.follow_up_count_this_question,
            "max_follow_ups": 2,
        })
