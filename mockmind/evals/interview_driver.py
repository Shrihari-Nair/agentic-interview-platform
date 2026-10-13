import logging
import os
import time

from google import genai
from google.genai import types

from agent.code_review_flow import REVIEW_FAILED_INSTRUCTIONS, record_review, review_reply_instructions
from agent.prompts import build_interviewer_system_prompt
from agent.session_state import AgentSessionState, follow_up_policy_note
from backend.models.interview_plan import InterviewPlan
from backend.services.llm_retry import retry_async
from backend.services.tracing import traced_generation
from evals.candidate_simulator import CandidateSimulator
from evals.interview_tools import make_tools

logger = logging.getLogger(__name__)

# Recorded when the interviewer's turn has no spoken text (e.g. it only made a
# tool call). A real candidate would hear silence; evals/checks.py counts these.
SILENT_TURN_NOTE = "[eval] Interviewer returned no spoken reply this turn."
SILENCE_FOR_CANDIDATE = "(The interviewer said nothing.)"

# Safety cap: a runaway interview (interviewer never calls end_interview)
# shouldn't loop forever.
MAX_TURNS = 30


def _snapshot(state: AgentSessionState, run_flags: dict) -> dict:
    return {
        "index": state.current_question_index,
        "asked": list(state.asked_question_ids),
        "follow_ups": state.follow_up_count_this_question,
        "turns": state.candidate_turns_this_question,
        "transcript_len": len(state.transcript),
        "ended": run_flags["ended"],
    }


def _restore(state: AgentSessionState, run_flags: dict, snap: dict) -> None:
    state.current_question_index = snap["index"]
    state.asked_question_ids = list(snap["asked"])
    state.follow_up_count_this_question = snap["follow_ups"]
    state.candidate_turns_this_question = snap["turns"]
    del state.transcript[snap["transcript_len"]:]
    run_flags["ended"] = snap["ended"]


async def _send(chat, parts: list[str], state, run_flags, label: str, base_delay: float = 2.0):
    """chat.send_message with retries that are safe for a *tool-calling* chat.

    The interviewer's tools mutate `state` (advance the question, end the
    interview). If a call fails after a tool already ran, blindly re-sending
    would run the tool twice and skip a question. So each attempt starts from a
    snapshot and a failure rolls the state back before the retry."""
    async def attempt():
        snap = _snapshot(state, run_flags)
        try:
            return await chat.send_message(parts)
        except Exception:
            _restore(state, run_flags, snap)
            raise

    return await retry_async(attempt, label=label, base_delay=base_delay)


async def _coding_turn(
    chat, candidate: CandidateSimulator, state: AgentSessionState, run_flags: dict,
    session_id: str, submitted: set[str], base_delay: float = 2.0,
) -> str:
    """Mirrors agent.py's _handle_code_submission: the candidate submits code,
    it is really executed + reviewed, the result is recorded the same way, and
    the interviewer reacts. Returns the interviewer's reply."""
    q = state.current_question
    submitted.add(q.id)
    code = await candidate.write_code(q.coding_spec.problem_statement, q.coding_spec.starter_code)

    try:
        from backend.services.code_judge import review_code

        review = await review_code(q, code, session_id)
    except Exception:
        # Same fallback as production: apologise and carry on, but make the
        # missing review visible in the transcript so the run's checks fail loudly.
        logger.exception("Code review failed during eval")
        state.add_transcript_entry("candidate", f"[Submitted code]\n{code}")
        instructions = REVIEW_FAILED_INSTRUCTIONS
    else:
        record_review(state, q.id, code, review)
        instructions = review_reply_instructions(review)

    response = await _send(chat, [instructions], state, run_flags, "interviewer_code_reaction", base_delay)
    reply = response.text or ""
    if reply:
        state.add_transcript_entry("interviewer", reply)
    else:
        state.add_transcript_entry("system", SILENT_TURN_NOTE)
    return reply


async def run_simulated_interview(
    plan: InterviewPlan,
    persona: str,
    session_id: str,
    behavioral_instructions: str | None = None,
    send_base_delay: float = 2.0,
) -> AgentSessionState:
    """Drives a full text-mode interview between the REAL interviewer system
    prompt + tool logic and a simulated candidate, turn by turn, until
    end_interview is called or MAX_TURNS is hit. Returns the resulting
    AgentSessionState (same shape the real agent produces), ready to hand
    straight to the real report_generator.generate_report().

    Production behaviour mirrored here: the opening line, the three tools, the
    per-turn follow-up policy note (agent/session_state.follow_up_policy_note,
    the same function the live agent uses), and the live-coding submission flow.

    `behavioral_instructions`, when given, overrides the production default
    from agent/prompts.py for this run only — this is how the eval-driven
    optimizer (evals/optimizer/) test-drives a candidate prompt revision
    without touching the production file until it's proven to win."""
    state = AgentSessionState(session_id=session_id, plan=plan)
    run_flags = {"ended": False}
    tools = make_tools(state, run_flags)

    system_prompt = build_interviewer_system_prompt(
        plan.model_dump_json(indent=2), behavioral_instructions
    )
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    # Mirrors agent.py's on_enter(): the opening line is assembled
    # deterministically, not LLM-generated, so we do the same here.
    first_q = plan.questions[0].question if plan.questions else "Tell me about yourself."
    opening_text = f"{plan.opening_message} {first_q}"
    state.add_transcript_entry("interviewer", opening_text)

    chat = client.aio.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
            temperature=0.7,
        ),
        history=[types.Content(role="model", parts=[types.Part.from_text(text=opening_text)])],
    )

    candidate = CandidateSimulator(persona, session_id)
    interviewer_message = opening_text
    submitted: set[str] = set()

    for _ in range(MAX_TURNS):
        q = state.current_question
        if q is not None and q.question_type == "coding" and q.coding_spec and q.id not in submitted:
            with traced_generation(
                "interviewer_code_turn", session_id=session_id, input_data=q.id
            ):
                interviewer_message = await _coding_turn(
                    chat, candidate, state, run_flags, session_id, submitted, send_base_delay
                )
            if run_flags["ended"]:
                break
            continue

        candidate_reply = await candidate.respond(interviewer_message or SILENCE_FOR_CANDIDATE)
        state.add_transcript_entry("candidate", candidate_reply)

        parts = [candidate_reply]
        note = follow_up_policy_note(state)
        if note:
            parts.append(note)

        with traced_generation(
            "interviewer_turn", session_id=session_id, input_data=candidate_reply
        ) as gen:
            response = await _send(chat, parts, state, run_flags, "interviewer_turn", send_base_delay)
            gen.record_response(response)

        interviewer_message = response.text or ""
        if interviewer_message:
            state.add_transcript_entry("interviewer", interviewer_message)
        elif not run_flags["ended"]:
            # (a silent turn that *ended* the interview is fine — nothing left to say)
            state.add_transcript_entry("system", SILENT_TURN_NOTE)

        if run_flags["ended"]:
            break
    else:
        state.add_transcript_entry(
            "system", f"Eval safety cap hit: interview did not end within {MAX_TURNS} turns."
        )

    state.ended_at = time.time()
    return state
