import json
import logging

from backend.services import report_store
from backend.services.redis_client import redis_client
from backend.services.report_generator import generate_report

logger = logging.getLogger(__name__)


async def run_report_pipeline(
    session_id: str,
    plan: dict,
    transcript: list,
    candidate_email: str | None = None,
) -> bool:
    """Generate the report, store it, and mark status pending -> ready | failed.

    Shared by the voice agent (end of interview) and POST /api/report/{id}/retry.
    Returns True when a report was stored. Never raises: a failure is recorded
    as status "failed" so the frontend can show a Retry button instead of
    polling until it gives up."""
    try:
        await report_store.set_status(session_id, "pending")
        report = await generate_report(session_id=session_id, plan=plan, transcript=transcript)
        await redis_client.setex(
            f"interview_report:{session_id}", report_store.REPORT_TTL, json.dumps(report)
        )
        await report_store.set_status(session_id, "ready")
    except Exception:
        logger.exception("Report generation failed for session %s", session_id)
        try:
            await report_store.set_status(session_id, "failed")
        except Exception:
            logger.exception("Could not record failed status for session %s", session_id)
        return False

    if candidate_email:
        try:
            from backend.services.memory_store import get_memory, save_memory
            from backend.services.memory_updater import update_memory_from_report

            existing = await get_memory(candidate_email)
            updated = await update_memory_from_report(
                existing=existing,
                email=candidate_email,
                session_id=session_id,
                plan=plan,
                report=report,
            )
            await save_memory(updated)
        except Exception:
            logger.exception("Candidate memory update failed for session %s", session_id)
    return True
