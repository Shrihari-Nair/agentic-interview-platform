"""
MockMind Interviewer Agent — Main entrypoint

Run modes:
  python agent/agent.py dev      ← development with hot reload (connects to LiveKit)
  python agent/agent.py start    ← production
  python agent/agent.py console  ← local terminal test

Architecture:
  Soniox STT  →  Gemini 2.5 Flash LLM  →  Cartesia Sonic-3 TTS
  Silero VAD for turn detection + MultilingualModel for natural turns
"""

import asyncio
import base64
import json
import logging
import os
import sys

# Add the parent directory (mockmind/) to Python path so agent can import backend package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    get_job_context,
    room_io,
)
from livekit.agents.telemetry import set_tracer_provider
from livekit.plugins import cartesia, google, silero, soniox
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
except ModuleNotFoundError:
    MultilingualModel = None  # type: ignore

from agent.interviewer import InterviewerAgent
from agent.session_state import AgentSessionState, generate_and_store_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("mockmind_agent")


def _get_context_session_id() -> str | None:
    """Reads our own session_id (not the LiveKit room name) from the current
    job's metadata, so every span — here and in the backend's Langfuse traces
    — groups under the same session.id."""
    ctx = get_job_context(required=False)
    if ctx is None:
        return None
    try:
        metadata = json.loads(ctx.job.metadata or "{}")
        return metadata.get("session_id") or ctx.job.room.name
    except Exception:
        return ctx.job.room.name


def _setup_otel_tracing():
    """Exports AgentSession spans (STT/LLM/TTS turns, tool calls, metrics) to
    the self-hosted Langfuse instance over OTLP. A no-op if Langfuse isn't
    configured — tracing is observability, never a hard dependency to run."""
    host = os.getenv("LANGFUSE_HOST")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not (host and public_key and secret_key):
        logger.info("Langfuse not configured — skipping agent tracing.")
        return

    from opentelemetry.context import Context
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import Span, SpanProcessor, TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    class SessionSpanProcessor(SpanProcessor):
        def on_start(self, span: Span, parent_context: Context | None = None) -> None:
            session_id = _get_context_session_id()
            if session_id:
                span.set_attribute("session.id", session_id)

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    trace_provider = TracerProvider()
    trace_provider.add_span_processor(SessionSpanProcessor())
    trace_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=f"{host.rstrip('/')}/api/public/otel",
                headers={
                    "Authorization": f"Basic {auth}",
                    "x-langfuse-ingestion-version": "4",
                },
            )
        )
    )
    set_tracer_provider(trace_provider)
    return trace_provider


_trace_provider = _setup_otel_tracing()


def _load_turn_detector():
    """Load MultilingualModel if model files exist, otherwise fall back to None (Silero VAD only)."""
    if MultilingualModel is None:
        return None
    try:
        return MultilingualModel()
    except Exception as e:
        logger.warning("Turn detector model not available (%s). Falling back to Silero VAD only. Run `python agent/agent.py download-files` to fix this.", e)
        return None


async def _handle_code_submission(packet, state: AgentSessionState, session: AgentSession) -> None:
    """Runs the candidate's submitted code through the sandboxed executor +
    LLM review, then injects the result into the live conversation via
    session.generate_reply() — this is what lets an async, out-of-band event
    (code arriving over a data channel) make the agent react naturally
    mid-interview instead of waiting for the candidate to speak again."""
    try:
        payload = json.loads(packet.data.decode("utf-8"))
        question_id = payload["question_id"]
        code = payload["code"]
    except Exception:
        logger.exception("Failed to parse code_submission data packet")
        return

    question = next((q for q in state.plan.questions if q.id == question_id), None)
    if question is None or question.coding_spec is None:
        logger.warning(f"Code submission for unknown/non-coding question_id={question_id!r}")
        return

    logger.info(f"Reviewing code submission for question {question_id}")
    try:
        from backend.services.code_judge import review_code
        review = await review_code(question, code, state.session_id)
    except Exception:
        logger.exception("Code review failed")
        session.generate_reply(
            instructions=(
                "The candidate's code submission couldn't be evaluated due to "
                "a technical error on our end. Apologize briefly, and either "
                "ask them to resubmit or move on to the next question."
            )
        )
        return

    state.add_transcript_entry("candidate", f"[Submitted code]\n{code}")
    state.add_transcript_entry(
        "system",
        f"Code review for {question_id}: {review.tests_passed}/{review.tests_total} "
        f"tests passed, correctness {review.correctness_score}/10. {review.code_quality_notes}",
    )

    session.generate_reply(
        instructions=(
            f"The candidate just submitted their code for the current coding "
            f"question. Result: {review.tests_passed}/{review.tests_total} test "
            f"cases passed, correctness score {review.correctness_score}/10. "
            f"{review.code_quality_notes} React naturally and conversationally "
            f"to this — do not just read out the numbers. Per your usual rules, "
            f"ask at most one follow-up about their approach if warranted, then "
            f"call move_to_next_question."
        )
    )


server = AgentServer()


@server.rtc_session(agent_name="mockmind-interviewer")
async def entrypoint(ctx: JobContext) -> None:
    """
    Entry point called once per dispatched room.
    Reads session_id from job metadata, loads the interview plan from Redis,
    then starts the voice pipeline with the InterviewerAgent.
    """
    logger.info(f"Agent joining room: {ctx.room.name}")

    # ── Load session_id from job metadata ──────────────────────────────────
    try:
        metadata = json.loads(ctx.job.metadata or "{}")
        session_id = metadata.get("session_id")
    except Exception:
        session_id = None

    if not session_id:
        logger.error("No session_id in job metadata — cannot load interview plan")
        return

    logger.info(f"Loading interview plan for session: {session_id}")

    # ── Load interview plan from Redis ─────────────────────────────────────
    try:
        state = await AgentSessionState.load(session_id)
        logger.info(
            f"Plan loaded: {len(state.plan.questions)} questions | "
            f"role: {state.plan.job.title} | "
            f"candidate: {state.plan.candidate.name}"
        )
    except ValueError as e:
        logger.error(f"Failed to load session state: {e}")
        return

    # ── Configure the voice pipeline ───────────────────────────────────────
    session = AgentSession(
        stt=soniox.STT(
            params=soniox.STTOptions(
                model="stt-rt-v4",
                language_hints=["en"],
            )
        ),
        llm=google.LLM(
            model="gemini-2.5-flash",
            temperature=0.7,
        ),
        tts=cartesia.TTS(
            model="sonic-3",
            voice="f786b574-daa5-4673-aa0c-cbe3e8534c02",  # "Barbershop Man" — verified default
        ),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            turn_detection=_load_turn_detector(),
        ),
        userdata=state,
    )

    # ── Transcript tracking ────────────────────────────────────────────────
    @session.on("user_input_transcribed")
    def on_user_speech(event):
        if getattr(event, "is_final", True) and getattr(event, "transcript", None):
            state.add_transcript_entry("candidate", event.transcript)

    # ── Live-coding: candidate code submissions arrive over a LiveKit data
    # message (not HTTP) — see frontend's useDataChannel("code_submission").
    @ctx.room.on("data_received")
    def on_data_received(packet):
        if packet.topic == "code_submission":
            asyncio.create_task(_handle_code_submission(packet, state, session))

    # ── Shutdown hook: generate report if not yet done ─────────────────────
    async def on_session_shutdown():
        if not state.ended_at:
            import time
            state.ended_at = time.time()
            await generate_and_store_report(state)

    ctx.add_shutdown_callback(on_session_shutdown)

    if _trace_provider is not None:
        async def flush_trace():
            _trace_provider.force_flush()

        ctx.add_shutdown_callback(flush_trace)

    # ── Start the session (connects to room internally) ────────────────────
    await session.start(
        room=ctx.room,
        agent=InterviewerAgent(state=state),
        room_options=room_io.RoomOptions(
            delete_room_on_close=True,
        ),
    )

    logger.info("Interviewer agent running — session active")


if __name__ == "__main__":
    agents.cli.run_app(server)
