import asyncio
import json
import logging
import traceback
import uuid
from fastapi import APIRouter, UploadFile, File, Form

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse

from backend.services.resume_parser import extract_resume_text
from backend.agents.resume_analyzer import analyze_resume
from backend.agents.jd_analyzer import analyze_jd
from backend.agents.question_generator import generate_questions
from backend.services.redis_client import redis_client
from backend.models.interview_plan import SessionState

router = APIRouter()


@router.post("/api/prepare")
async def prepare_interview(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
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
            file_bytes = await resume.read()
            resume_text = extract_resume_text(file_bytes, resume.filename or "resume.pdf")
            if not resume_text:
                yield _sse({"stage": "error", "message": "Could not extract text from resume. Please try a PDF or DOCX file.", "progress": 0, "session_id": session_id})
                return
            yield _sse({"stage": "parsing", "message": "Resume parsed successfully.", "progress": 15, "session_id": session_id})

            # Stage 2: Analyze resume (Sub-Agent 1)
            yield _sse({"stage": "resume_analysis", "message": "Analyzing your background and experience...", "progress": 20, "session_id": session_id})
            candidate_profile = await analyze_resume(resume_text)
            yield _sse({
                "stage": "resume_analysis",
                "message": f"Profile built: {candidate_profile.years_of_experience} years experience, {len(candidate_profile.skills)} skills identified.",
                "progress": 45,
                "session_id": session_id,
                "data": {"candidate_name": candidate_profile.name},
            })

            # Stage 3: Analyze JD (Sub-Agent 2)
            yield _sse({"stage": "jd_analysis", "message": "Analyzing the job requirements...", "progress": 50, "session_id": session_id})
            job_profile = await analyze_jd(job_description)
            yield _sse({
                "stage": "jd_analysis",
                "message": f"Job analyzed: {job_profile.title} ({job_profile.seniority_level}). Found {len(job_profile.red_flags_to_probe)} areas to probe.",
                "progress": 65,
                "session_id": session_id,
            })

            # Stage 4: Generate questions (Sub-Agent 3)
            yield _sse({"stage": "question_gen", "message": "Crafting personalized interview questions...", "progress": 70, "session_id": session_id})
            plan = await generate_questions(candidate_profile, job_profile, session_id)
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

        except Exception as e:
            logger.error("Preparation failed:\n%s", traceback.format_exc())
            yield _sse({
                "stage": "error",
                "message": f"Preparation failed: {str(e)}",
                "progress": 0,
                "session_id": session_id,
            })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
