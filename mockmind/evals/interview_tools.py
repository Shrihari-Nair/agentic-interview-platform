"""Plain-function reimplementations of agent/interviewer.py's three
@function_tool()s, for use with google-genai's automatic function calling
(the real tools are bound methods on a livekit Agent, tied to a RunContext/
AgentSession — not callable standalone outside a live LiveKit room).

Deliberately mirrors the real tool behavior exactly, bugs included (e.g.
`increment_follow_up_count()` is never called here either, matching
agent/interviewer.py) — the eval harness exists to catch real regressions,
so faithfully reproducing current production behavior matters more than
reproducing an idealized version.
"""

from agent.session_state import AgentSessionState


def make_tools(state: AgentSessionState, run_flags: dict):
    def move_to_next_question() -> dict:
        """Call this when you are ready to move to the next interview question.
        Call this AFTER finishing the current question and any follow-ups.
        Returns the next question to ask."""
        state.advance_question()

        if state.is_complete:
            return {
                "status": "interview_complete",
                "message": "All questions have been asked. Call end_interview now.",
            }

        q = state.current_question
        return {
            "status": "next_question",
            "question_number": state.current_question_index + 1,
            "total_questions": len(state.plan.questions),
            "question": q.question,
            "category": q.category,
            "intent": q.intent,
            "follow_ups": [
                {"trigger": fu.trigger, "question": fu.question} for fu in q.follow_ups
            ],
            "follow_ups_used_this_question": state.follow_up_count_this_question,
            "max_follow_ups": 2,
        }

    def end_interview() -> dict:
        """Call this to formally end the interview session. This triggers
        report generation. Call it after all questions are asked, OR if the
        candidate requests to end early. Before calling, say a proper
        closing statement to the candidate."""
        run_flags["ended"] = True
        return {
            "status": "session_ended",
            "questions_asked": len(state.asked_question_ids),
            "message": "Session ended. Report is being generated.",
        }

    def get_current_question_context() -> dict:
        """Returns the current question details including available
        follow-up options. Call this if you need a reminder of the current
        question details."""
        q = state.current_question
        if not q:
            return {"status": "no_current_question", "interview_complete": True}
        return {
            "question_number": state.current_question_index + 1,
            "total_questions": len(state.plan.questions),
            "current_question": q.question,
            "category": q.category,
            "intent": q.intent,
            "follow_ups_available": [
                {"trigger": fu.trigger, "question": fu.question} for fu in q.follow_ups
            ],
            "follow_ups_used_this_question": state.follow_up_count_this_question,
            "max_follow_ups": 2,
        }

    return [move_to_next_question, end_interview, get_current_question_context]
