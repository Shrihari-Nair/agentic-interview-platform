import json
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

from backend.services.redis_client import redis_client
from backend.services.report_generator import generate_report

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
    """
    report_json = await redis_client.get(f"interview_report:{session_id}")
    if not report_json:
        raise HTTPException(status_code=404, detail="Report not ready yet.")
    return json.loads(report_json)
