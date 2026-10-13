"""The pure (no LiveKit) pieces of reacting to a live-coding submission, shared
by the live agent (agent.py) and the text-mode eval driver so both record and
prompt identically."""

from agent.session_state import AgentSessionState

REVIEW_FAILED_INSTRUCTIONS = (
    "The candidate's code submission couldn't be evaluated due to "
    "a technical error on our end. Apologize briefly, and either "
    "ask them to resubmit or move on to the next question."
)


def record_review(state: AgentSessionState, question_id: str, code: str, review) -> None:
    state.add_transcript_entry("candidate", f"[Submitted code]\n{code}")
    state.add_transcript_entry(
        "system",
        f"Code review for {question_id}: {review.tests_passed}/{review.tests_total} "
        f"tests passed, correctness {review.correctness_score}/10. {review.code_quality_notes}",
    )


def review_reply_instructions(review) -> str:
    return (
        f"The candidate just submitted their code for the current coding "
        f"question. Result: {review.tests_passed}/{review.tests_total} test "
        f"cases passed, correctness score {review.correctness_score}/10. "
        f"{review.code_quality_notes} React naturally and conversationally "
        f"to this — do not just read out the numbers. Per your usual rules, "
        f"ask at most one follow-up about their approach if warranted, then "
        f"call move_to_next_question."
    )
