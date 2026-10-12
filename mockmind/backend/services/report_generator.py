import json
import os
from google import genai
from google.genai import types
from backend.services.llm_retry import retry_async
from backend.services.tracing import traced_generation

VALID_RECOMMENDATIONS = {"strong_yes", "yes", "maybe", "no"}
_REQUIRED_KEYS = ("overall_score", "hiring_recommendation", "category_scores")


def validate_report(report: dict) -> dict:
    """The frontend indexes straight into these fields, so a malformed report
    must fail here (and be retried) rather than crash the report page."""
    if not isinstance(report, dict):
        raise ValueError("report is not a JSON object")
    missing = [k for k in _REQUIRED_KEYS if k not in report]
    if missing:
        raise ValueError(f"report missing keys: {missing}")
    if report["hiring_recommendation"] not in VALID_RECOMMENDATIONS:
        raise ValueError(f"invalid hiring_recommendation: {report['hiring_recommendation']!r}")
    if not isinstance(report["category_scores"], dict):
        raise ValueError("category_scores must be an object")
    report["overall_score"] = float(report["overall_score"])
    report.setdefault("summary", "")
    report.setdefault("strengths", [])
    report.setdefault("improvements", [])
    report.setdefault("question_feedback", [])
    return report

REPORT_PROMPT = """
You are an expert interview evaluator. Analyze this mock interview session thoroughly.

INTERVIEW PLAN:
{plan_json}

FULL TRANSCRIPT:
{transcript_json}

Generate a comprehensive evaluation report as a JSON object:
{{
  "overall_score": <0.0-10.0 float>,
  "hiring_recommendation": "strong_yes|yes|maybe|no",
  "summary": "2-3 sentence overall assessment of the candidate",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "improvements": ["area to improve 1", "area 2", "area 3"],
  "category_scores": {{
    "behavioral": <0-10>,
    "technical": <0-10>,
    "situational": <0-10>,
    "resume_deep_dive": <0-10>,
    "communication": <0-10>
  }},
  "question_feedback": [
    {{
      "question_id": "q1",
      "question": "question text",
      "candidate_answer": "candidate answer from transcript (or 'Not answered' if skipped)",
      "score": <0-10>,
      "feedback": "specific constructive feedback on this answer",
      "missed_points": ["what they should have mentioned but did not"]
    }}
  ]
}}

Be specific, honest, and constructive. Reference actual things the candidate said.
If the transcript is short or the interview was cut short, note this in the summary.
Return ONLY the JSON object — no markdown fences, no explanation.
"""


async def generate_report(session_id: str, plan: dict, transcript: list) -> dict:
    return await retry_async(
        lambda: _generate_report_once(session_id, plan, transcript),
        attempts=3,
        label="report_generation",
    )


async def _generate_report_once(session_id: str, plan: dict, transcript: list) -> dict:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    prompt = REPORT_PROMPT.format(
        plan_json=json.dumps(plan, indent=2),
        transcript_json=json.dumps(transcript, indent=2),
    )

    with traced_generation("report_generation", session_id=session_id, input_data=prompt) as gen:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=16384,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        gen.record_response(response)

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        return validate_report(json.loads(raw))
