import asyncio
import json
import logging
import traceback
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse

from backend.services.resume_parser import extract_resume_text
from backend.agents.resume_analyzer import analyze_resume
from backend.agents.jd_analyzer import analyze_jd
from backend.agents.question_generator import DEFAULT_TOTAL_QUESTIONS, generate_questions
from backend.services.redis_client import redis_client
from backend.models.interview_plan import SessionState

router = APIRouter()

# Fixed presets, not raw sliders — the setup page exposes this as a simple
# "standard vs coding" toggle, not more knobs than that.
# "coding" is deliberately short (6 questions, not 16): the point is to
# reach code quickly, not bury it among a full conversational interview.
INTERVIEW_TYPE_PRESETS = {
    "standard": {"num_coding_questions": 0, "total_questions": DEFAULT_TOTAL_QUESTIONS},
    "coding": {"num_coding_questions": 4, "total_questions": 6},
}


def _resolve_interview_type(interview_type: str) -> dict:
    return INTERVIEW_TYPE_PRESETS.get(interview_type, INTERVIEW_TYPE_PRESETS["standard"])


# Setup-page knobs. Fixed presets (not raw numbers) so the UI stays simple and
# the server never trusts arbitrary client-supplied weights/counts.
DIFFICULTY_PRESETS = {
    "easier": {"basic": 0.6, "intermediate": 0.3, "advanced": 0.1},
    "balanced": None,  # question_generator's default mix
    "harder": {"basic": 0.15, "intermediate": 0.35, "advanced": 0.5},
}
LENGTH_PRESETS = {"quick": 8, "standard": DEFAULT_TOTAL_QUESTIONS}


def resolve_plan_options(interview_type: str, difficulty: str, length: str) -> dict:
    """kwargs for generate_questions(). Unknown values fall back to defaults.
    The coding preset fixes its own length, so `length` only applies to standard."""
    preset = dict(_resolve_interview_type(interview_type))
    if interview_type != "coding":
        preset["total_questions"] = LENGTH_PRESETS.get(length, DEFAULT_TOTAL_QUESTIONS)
    preset["level_weights"] = DIFFICULTY_PRESETS.get(difficulty)
    return preset


# Upload / input limits — a resume goes straight into an LLM prompt.
MAX_RESUME_BYTES = 5 * 1024 * 1024
ALLOWED_RESUME_EXTS = {".pdf", ".docx", ".doc", ".txt"}
MAX_RESUME_CHARS = 30_000
MAX_JD_CHARS = 15_000
GENERIC_PREP_ERROR = (
    "Something went wrong while preparing your interview. Please try again in a moment."
)


class PreparationError(Exception):
    """An error whose message is safe and useful to show the user."""


def validate_resume_upload(filename: str, size: int) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_RESUME_EXTS:
        raise PreparationError("Unsupported file type. Please upload a PDF, DOCX or TXT resume.")
    if size == 0:
        raise PreparationError("The uploaded resume is empty.")
    if size > MAX_RESUME_BYTES:
        raise PreparationError(
            f"Resume is too large (max {MAX_RESUME_BYTES // (1024 * 1024)} MB)."
        )


async def _maybe_fetch_memory(use_memory: bool, candidate_email: str):
    """Returns (memory_or_None, normalized_email_or_None). Never raises — a
    memory-store problem must not block interview preparation."""
    email = (candidate_email or "").strip()
    if not use_memory or not email:
        return None, None
    try:
        from backend.services.memory_store import get_memory
        memory = await get_memory(email)
        return memory, email
    except Exception:
        logger.exception("Failed to fetch candidate memory for %s", email)
        return None, email


@router.post("/api/prepare")
async def prepare_interview(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    use_memory: bool = Form(False),
    candidate_email: str = Form(""),
    interview_type: str = Form("standard"),
    difficulty: str = Form("balanced"),
    length: str = Form("standard"),
    focus_weak_areas: bool = Form(False),
):
    """
    SSE endpoint — streams preparation progress while running 3 sub-agents.

    SSE data format:
        {"stage": "...", "message": "...", "progress": 0-100, "session_id": "..."}

    Stages: parsing → resume_analysis → jd_analysis → question_gen → complete | error
    """
    session_id = str(uuid.uuid4())

    async def event_stream():
        try:
            # Stage 1: Parse resume
            yield _sse({"stage": "parsing", "message": "Reading your resume...", "progress": 5, "session_id": session_id})
            if len(job_description) > MAX_JD_CHARS:
                raise PreparationError(
                    f"Job description is too long (max {MAX_JD_CHARS:,} characters)."
                )
            # Read one byte past the cap so oversize is detected without
            # buffering an arbitrarily large upload.
            file_bytes = await resume.read(MAX_RESUME_BYTES + 1)
            validate_resume_upload(resume.filename or "", len(file_bytes))
            resume_text = extract_resume_text(file_bytes, resume.filename or "resume.pdf")
            if not resume_text:
                raise PreparationError(
                    "Could not extract text from resume. Please try a PDF or DOCX file."
                )
            resume_text = resume_text[:MAX_RESUME_CHARS]
            yield _sse({"stage": "parsing", "message": "Resume parsed successfully.", "progress": 15, "session_id": session_id})

            # Stage 2: Analyze resume (Sub-Agent 1)
            yield _sse({"stage": "resume_analysis", "message": "Analyzing your background and experience...", "progress": 20, "session_id": session_id})
            candidate_profile = await analyze_resume(resume_text, session_id)
            yield _sse({
                "stage": "resume_analysis",
                "message": f"Profile built: {candidate_profile.years_of_experience} years experience, {len(candidate_profile.skills)} skills identified.",
                "progress": 45,
                "session_id": session_id,
                "data": {"candidate_name": candidate_profile.name},
            })

            # Stage 3: Analyze JD (Sub-Agent 2)
            yield _sse({"stage": "jd_analysis", "message": "Analyzing the job requirements...", "progress": 50, "session_id": session_id})
            job_profile = await analyze_jd(job_description, session_id)
            yield _sse({
                "stage": "jd_analysis",
                "message": f"Job analyzed: {job_profile.title} ({job_profile.seniority_level}). Found {len(job_profile.red_flags_to_probe)} areas to probe.",
                "progress": 65,
                "session_id": session_id,
            })

            # Stage 4: Generate questions (Sub-Agent 3)
            yield _sse({"stage": "question_gen", "message": "Crafting personalized interview questions...", "progress": 70, "session_id": session_id})
            memory, normalized_email = await _maybe_fetch_memory(use_memory, candidate_email)
            preset = resolve_plan_options(interview_type, difficulty, length)
            weak_focus = bool(focus_weak_areas and memory and memory.weak_categories)
            if focus_weak_areas and not weak_focus:
                yield _sse({
                    "stage": "question_gen",
                    "message": "No weak areas on record yet — running a balanced interview. Future sessions will adapt.",
                    "progress": 72,
                    "session_id": session_id,
                })
            plan = await generate_questions(
                candidate_profile, job_profile, session_id,
                candidate_memory=memory, candidate_email=normalized_email,
                num_coding_questions=preset["num_coding_questions"],
                total_questions=preset["total_questions"],
                level_weights=preset["level_weights"],
                weak_focus=weak_focus,
            )
            yield _sse({
                "stage": "question_gen",
                "message": f"Generated {len(plan.questions)} tailored questions across {len(set(q.category for q in plan.questions))} categories.",
                "progress": 90,
                "session_id": session_id,
            })

            # Store plan in Redis (TTL: 4 hours)
            await redis_client.setex(
                f"interview_plan:{session_id}",
                14400,
                plan.model_dump_json(),
            )

            # Store empty session state
            state = SessionState(session_id=session_id, plan=plan)
            await redis_client.setex(
                f"session_state:{session_id}",
                14400,
                state.model_dump_json(),
            )

            yield _sse({
                "stage": "complete",
                "message": "Your interview is ready. Click 'Start Interview' when you're ready.",
                "progress": 100,
                "session_id": session_id,
                "data": {
                    "total_questions": len(plan.questions),
                    "duration_minutes": plan.total_duration_minutes,
                    "job_title": job_profile.title,
                    "candidate_name": candidate_profile.name,
                },
            })

        except PreparationError as e:
            yield _sse({"stage": "error", "message": str(e), "progress": 0, "session_id": session_id})
        except Exception:
            # Full detail goes to the log; the user gets a safe, generic message.
            logger.error("Preparation failed:\n%s", traceback.format_exc())
            yield _sse({
                "stage": "error",
                "message": GENERIC_PREP_ERROR,
                "progress": 0,
                "session_id": session_id,
            })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
