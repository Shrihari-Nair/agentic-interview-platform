import json
import os
from google import genai
from google.genai import types

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
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=REPORT_PROMPT.format(
            plan_json=json.dumps(plan, indent=2),
            transcript_json=json.dumps(transcript, indent=2),
        ),
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
