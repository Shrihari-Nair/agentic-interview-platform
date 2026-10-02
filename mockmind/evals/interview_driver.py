import os
import time

from google import genai
from google.genai import types

from agent.session_state import AgentSessionState
from agent.prompts import build_interviewer_system_prompt
from backend.models.interview_plan import InterviewPlan
from backend.services.tracing import traced_generation
from evals.candidate_simulator import CandidateSimulator
from evals.interview_tools import make_tools

MAX_TURNS = 30


async def run_simulated_interview(
    plan: InterviewPlan,
    persona: str,
    session_id: str,
    behavioral_instructions: str | None = None,
) -> AgentSessionState:
    """Drives a full text-mode interview between the REAL interviewer system
    prompt + tool logic and a simulated candidate, turn by turn, until
    end_interview is called or MAX_TURNS is hit. Returns the resulting
    AgentSessionState (same shape the real agent produces), ready to hand
    straight to the real report_generator.generate_report().

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

    for _ in range(MAX_TURNS):
        candidate_reply = await candidate.respond(interviewer_message)
        state.add_transcript_entry("candidate", candidate_reply)

        with traced_generation(
            "interviewer_turn", session_id=session_id, input_data=candidate_reply
        ) as gen:
            response = await chat.send_message(candidate_reply)
            gen.record_response(response)

        interviewer_message = response.text or ""
        if interviewer_message:
            state.add_transcript_entry("interviewer", interviewer_message)

        if run_flags["ended"]:
            break
    else:
        state.add_transcript_entry(
            "system", f"Eval safety cap hit: interview did not end within {MAX_TURNS} turns."
        )

    state.ended_at = time.time()
    return state
