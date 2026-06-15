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
    room_io,
)
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


def _load_turn_detector():
    """Load MultilingualModel if model files exist, otherwise fall back to None (Silero VAD only)."""
    if MultilingualModel is None:
        return None
    try:
        return MultilingualModel()
    except Exception as e:
        logger.warning("Turn detector model not available (%s). Falling back to Silero VAD only. Run `python agent/agent.py download-files` to fix this.", e)
        return None


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

    # ── Shutdown hook: generate report if not yet done ─────────────────────
    async def on_session_shutdown():
        if not state.ended_at:
            import time
            state.ended_at = time.time()
            await generate_and_store_report(state)

    ctx.add_shutdown_callback(on_session_shutdown)

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
