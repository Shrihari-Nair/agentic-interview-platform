import json
import logging
import os
import re
from google import genai
from google.genai import types
from backend.models.interview_plan import CandidateProfile

logger = logging.getLogger(__name__)


def _clean_json(raw: str) -> str:
    """Strip markdown fences and extract the first JSON object/array."""
    raw = raw.strip()
    # Remove ```json ... ``` or ``` ... ``` fences
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()
    # Extract first { ... } block in case there's surrounding text
    match = re.search(r'(\{.*\})', raw, re.DOTALL)
    if match:
        return match.group(1)
    return raw

RESUME_ANALYSIS_PROMPT = """
You are an expert technical recruiter analyzing a candidate's resume.
Extract structured information from the resume provided at the end of this message.

Extract and return a JSON object with EXACTLY this structure:
{{
  "name": "candidate full name or null",
  "current_role": "most recent job title or null",
  "years_of_experience": <integer, total years of relevant work experience>,
  "skills": ["list", "of", "all", "technical", "and", "soft", "skills"],
  "notable_projects": ["brief description of each significant project"],
  "education": ["degree and institution for each"],
  "career_gaps": ["any gaps in employment or notable missing experience worth probing"],
  "key_achievements": ["quantified achievements, e.g. 'Reduced API latency by 40%'"]
}}

Be thorough. For career_gaps, include skill gaps relative to a senior engineer too.
Return ONLY the JSON object — no markdown fences, no explanation.
"""


async def analyze_resume(resume_text: str) -> CandidateProfile:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    prompt = RESUME_ANALYSIS_PROMPT + "\n\nRESUME TEXT:\n" + resume_text

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    raw = response.text
    try:
        data = json.loads(_clean_json(raw))
    except json.JSONDecodeError as e:
        logger.error("resume_analyzer JSON parse failed. Raw response (first 500 chars):\n%s", raw[:500])
        raise
    return CandidateProfile(**data)
