import json
import logging
import os
import re
from google import genai
from google.genai import types
from backend.models.interview_plan import JobProfile

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

JD_ANALYSIS_PROMPT = """
You are an expert technical recruiter analyzing a job description.
Extract structured information from the job description provided at the end of this message.

Extract and return a JSON object with EXACTLY this structure:
{{
  "title": "job title",
  "company": "company name or null",
  "required_skills": ["non-negotiable technical and soft skills explicitly listed"],
  "nice_to_have_skills": ["preferred but optional skills"],
  "responsibilities": ["key responsibilities, 5-10 bullet points"],
  "seniority_level": "junior|mid|senior|lead|staff|principal",
  "red_flags_to_probe": ["skills or experiences the JD requires that a typical candidate might lack — things an interviewer would specifically test for"]
}}

For seniority_level: infer from years required, title, and responsibility scope.
Return ONLY the JSON object — no markdown fences, no explanation.
"""


async def analyze_jd(jd_text: str) -> JobProfile:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    prompt = JD_ANALYSIS_PROMPT + "\n\nJOB DESCRIPTION:\n" + jd_text

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
        logger.error("jd_analyzer JSON parse failed. Raw response (first 500 chars):\n%s", raw[:500])
        raise
    return JobProfile(**data)
