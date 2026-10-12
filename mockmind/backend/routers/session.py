import asyncio
import json
import logging
import os
from datetime import timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from livekit.api import (
    AccessToken,
    VideoGrants,
    RoomAgentDispatch,
    RoomConfiguration,
)

from backend.models.interview_plan import SessionState
from backend.services import report_store
from backend.services.redis_client import redis_client
from backend.services.report_pipeline import run_report_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenRequest(BaseModel):
    session_id: str
    participant_name: str = "Candidate"


@router.post("/api/token")
async def get_token(req: TokenRequest):
    """
    Generate a LiveKit access token for the candidate.
    The token embeds an agent dispatch directive so the interviewer agent
    joins automatically when the candidate enters the room.
    """
    plan_json = await redis_client.get(f"interview_plan:{req.session_id}")
    if not plan_json:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please run /api/prepare first.",
        )

    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]
    livekit_url = os.environ["LIVEKIT_URL"]

    room_name = f"interview_{req.session_id}"
    identity = f"candidate_{req.session_id[:8]}"

    token = (
        AccessToken(api_key=api_key, api_secret=api_secret)
        .with_identity(identity)
        .with_name(req.participant_name)
        .with_ttl(timedelta(hours=2))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            RoomConfiguration(
                agents=[
                    RoomAgentDispatch(
                        agent_name="mockmind-interviewer",
                        metadata=json.dumps({"session_id": req.session_id}),
                    )
                ]
            )
        )
        .to_jwt()
    )

    return {
        "token": token,
        "ws_url": livekit_url,
        "room_name": room_name,
        "identity": identity,
        "session_id": req.session_id,
    }


@router.get("/api/report/{session_id}")
async def get_report(session_id: str):
    """
    Returns the post-interview evaluation report.
    Report is generated asynchronously after the interview ends.
    Poll this endpoint every few seconds after the session ends.

    200 -> report; 404 -> not ready yet (keep polling);
    502 {"status": "failed"} -> generation failed, POST /retry to try again.
    """
    report_json = await redis_client.get(f"interview_report:{session_id}")
    if report_json:
        return json.loads(report_json)
    if await report_store.get_status(session_id) == "failed":
        raise HTTPException(
            status_code=502,
            detail={"status": "failed", "message": "Report generation failed."},
        )
    raise HTTPException(status_code=404, detail="Report not ready yet.")


# Strong refs so fire-and-forget retry tasks aren't garbage-collected mid-run.
_retry_tasks: set[asyncio.Task] = set()


@router.post("/api/report/{session_id}/retry", status_code=202)
async def retry_report(session_id: str):
    """Regenerates a failed report from the transcript persisted in Redis."""
    status = await report_store.get_status(session_id)
    if status == "pending":
        return {"status": "pending"}
    if await redis_client.get(f"interview_report:{session_id}"):
        return {"status": "ready"}

    state_json = await redis_client.get(f"session_state:{session_id}")
    if not state_json:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    state = SessionState.model_validate_json(state_json)
    if not state.transcript:
        raise HTTPException(status_code=409, detail="No interview transcript to evaluate.")

    await report_store.set_status(session_id, "pending")
    task = asyncio.create_task(
        run_report_pipeline(
            session_id,
            state.plan.model_dump(),
            state.transcript,
            state.plan.candidate_email,
        )
    )
    _retry_tasks.add(task)
    task.add_done_callback(_retry_tasks.discard)
    return {"status": "pending"}
