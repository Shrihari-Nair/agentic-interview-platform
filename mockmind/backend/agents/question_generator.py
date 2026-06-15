import json
import logging
import os
import re
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()
    match = re.search(r'(\{.*\})', raw, re.DOTALL)
    if match:
        return match.group(1)
    return raw
from backend.models.interview_plan import (
    InterviewQuestion,
    InterviewPlan,
    QuestionCategory,
    FollowUp,
    CandidateProfile,
    JobProfile,
)

QUESTION_GENERATION_PROMPT = """
You are a world-class technical interviewer preparing for an interview.
The candidate profile and job profile are provided at the end of this message.

Generate a tailored interview question bank of 15-20 questions.

REQUIREMENTS:
1. Questions must be SPECIFIC to this candidate and role — not generic
2. Include questions that probe the candidate's ACTUAL projects and experience
3. Include questions that test for skills the JD requires but the resume lacks (red flags)
4. Mix categories: behavioral (30%), technical (30%), situational (20%), resume_deep_dive (15%), closing (5%)
5. Order questions naturally: start easy/warm-up, build to harder, end with closing
6. Each question must have 2-3 contextual follow-ups based on expected answer patterns
7. Behavioral questions must use STAR format probing

Return a JSON object with EXACTLY this structure:
{{
  "opening_message": "The interviewer's first spoken message to open the session naturally. Friendly, professional. Introduce yourself as Alex, the AI interviewer. Mention candidate name if available. 2 sentences max.",
  "interview_style": "conversational",
  "total_duration_minutes": 30,
  "questions": [
    {{
      "id": "q1",
      "category": "behavioral|technical|situational|resume_deep_dive|culture_fit|closing",
      "question": "The exact question text as the interviewer would say it",
      "intent": "What this question is testing (1 sentence)",
      "ideal_answer_points": [
        "Point 1 a strong answer should cover",
        "Point 2",
        "Point 3"
      ],
      "follow_ups": [
        {{
          "trigger": "If the candidate gives a vague answer",
          "question": "Can you walk me through a specific example?"
        }},
        {{
          "trigger": "If the candidate mentions a metric or result",
          "question": "How did you measure that improvement?"
        }}
      ],
      "difficulty": 1,
      "source": "behavioral_standard|resume_gap|jd_requirement|project_deep_dive"
    }}
  ]
}}

IMPORTANT RULES:
- questions[0] must be a warm-up resume question (difficulty: 1)
- questions[-1] must be "Do you have any questions for me?" (category: closing)
- Technical questions must reference the tech stack from BOTH resume and JD
- Resume deep-dive questions must reference SPECIFIC projects from the resume by name
- If there are career gaps, include one tactful question about the gap
- Return ONLY the JSON object — no markdown fences, no explanation
"""


async def generate_questions(
    candidate: CandidateProfile,
    job: JobProfile,
    session_id: str,
) -> InterviewPlan:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    prompt = (
        QUESTION_GENERATION_PROMPT
        + "\n\nCANDIDATE PROFILE (JSON):\n"
        + candidate.model_dump_json(indent=2)
        + "\n\nJOB PROFILE (JSON):\n"
        + job.model_dump_json(indent=2)
    )

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=8192,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    raw = response.text
    try:
        data = json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        logger.error("question_generator JSON parse failed. Raw response (first 800 chars):\n%s", raw[:800])
        raise

    questions = []
    for q_data in data["questions"]:
        follow_ups = [
            FollowUp(
                trigger=f.get("trigger", ""),
                question=f.get("question", ""),
            )
            for f in q_data.get("follow_ups", [])
        ]
        questions.append(
            InterviewQuestion(
                id=q_data.get("id", f"q{len(questions) + 1}"),
                category=QuestionCategory(q_data["category"]),
                question=q_data["question"],
                intent=q_data.get("intent", ""),
                ideal_answer_points=q_data.get("ideal_answer_points", []),
                follow_ups=follow_ups,
                difficulty=q_data.get("difficulty", 2),
                source=q_data.get("source", "general"),
            )
        )

    return InterviewPlan(
        session_id=session_id,
        candidate=candidate,
        job=job,
        questions=questions,
        opening_message=data["opening_message"],
        interview_style=data.get("interview_style", "conversational"),
        total_duration_minutes=data.get("total_duration_minutes", 30),
        created_at=time.time(),
    )
