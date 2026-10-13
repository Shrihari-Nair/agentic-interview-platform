"""Deterministic (non-LLM) checks on a finished simulated interview.

The LLM judge is useful but can be wrong or inconsistent. Anything that can be
verified directly from the transcript is verified here, in code, so e.g. the
follow-up cap is *measured*, not just judged."""

from agent.session_state import MAX_FOLLOW_UPS

CODE_PREFIX = "[Submitted code]"


def _candidate_speech_by_question(transcript: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for e in transcript:
        if e["speaker"] == "candidate" and not e["text"].startswith(CODE_PREFIX):
            counts[e["question_index"]] = counts.get(e["question_index"], 0) + 1
    return counts


def deterministic_checks(transcript: list[dict], plan_questions: list, questions_reached: int) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    checks["interview_ended_normally"] = not any(
        e["speaker"] == "system" and "safety cap" in e["text"] for e in transcript
    )

    checks["interviewer_never_silent"] = not any(
        e["speaker"] == "system" and e["text"].startswith("[eval] Interviewer returned no spoken reply")
        for e in transcript
    )

    # Spoken turns per *conversational* question: 1 answer + at most MAX_FOLLOW_UPS follow-ups.
    coding_idx = {i for i, q in enumerate(plan_questions) if q.question_type == "coding"}
    speech = _candidate_speech_by_question(transcript)
    checks["follow_up_cap_respected"] = all(
        n <= MAX_FOLLOW_UPS + 1 for idx, n in speech.items() if idx not in coding_idx
    )

    reached_coding = [i for i in coding_idx if i < questions_reached or i == questions_reached]
    if coding_idx:
        submissions = {
            e["question_index"] for e in transcript
            if e["speaker"] == "candidate" and e["text"].startswith(CODE_PREFIX)
        }
        reviews = [e for e in transcript if e["speaker"] == "system" and e["text"].startswith("Code review for")]
        checks["coding_question_reached"] = bool(reached_coding)
        checks["code_submitted_for_each_reached_coding_question"] = all(i in submissions for i in reached_coding)
        checks["code_review_ran"] = len(reviews) >= len(reached_coding) and bool(reviews)
    return checks
