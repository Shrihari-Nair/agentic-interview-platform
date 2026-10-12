"""Report lifecycle in Redis: pending -> ready | failed.

The frontend polls GET /api/report/{id}; without a status key it could not tell
"still generating" from "generation died", and polled blindly until it gave up."""

from backend.services.redis_client import redis_client

STATUS_TTL = 86400
REPORT_TTL = 86400


def _status_key(session_id: str) -> str:
    return f"interview_report_status:{session_id}"


async def set_status(session_id: str, status: str) -> None:
    await redis_client.setex(_status_key(session_id), STATUS_TTL, status)


async def get_status(session_id: str) -> str | None:
    return await redis_client.get(_status_key(session_id))
