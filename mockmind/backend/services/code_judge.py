"""
Reviews a candidate's submitted code for a live-coding interview question.

Grounds the LLM's judgment in REAL execution results (runs the code against
every test case via the Piston sandbox first) rather than asking the model
to evaluate correctness by eyeballing the code alone — the model still makes
the final qualitative call (code quality, approach, edge-case handling), but
whether each test case actually passed is a fact, not an opinion.
"""

import json
import logging
import os
import re

from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.models.interview_plan import InterviewQuestion
from backend.services.code_executor import execute_code
from backend.services.tracing import traced_generation

logger = logging.getLogger(__name__)

CODE_REVIEW_PROMPT = """
You are a technical interviewer reviewing a candidate's code submission.

PROBLEM STATEMENT:
{problem_statement}

CANDIDATE'S CODE:
```{language}
{code}
```

TEST RESULTS (ground truth — these actually ran):
{test_results_json}

Based on the code AND the real test results above, return a JSON object:
{{
  "tests_passed": <int, count from the test results above>,
  "tests_total": <int, count from the test results above>,
  "correctness_score": <0.0-10.0 float, weighted toward test results but informed by the code itself>,
  "code_quality_notes": "1-2 sentences on readability, approach, efficiency, edge-case handling",
  "feedback": "2-3 sentences of spoken, conversational feedback the interviewer could say next — do not just restate the test results, react to the approach"
}}

Be honest — do not inflate the score if tests failed. Return ONLY the JSON object.
"""


class CodeReviewResult(BaseModel):
    tests_passed: int
    tests_total: int
    correctness_score: float
    code_quality_notes: str
    feedback: str


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()
    match = re.search(r'(\{.*\})', raw, re.DOTALL)
    return match.group(1) if match else raw


async def review_code(question: InterviewQuestion, submitted_code: str, session_id: str) -> CodeReviewResult:
    spec = question.coding_spec
    if spec is None:
        raise ValueError(f"Question {question.id} has no coding_spec — not a coding question")

    test_results = []
    for tc in spec.test_cases:
        try:
            # tc.input is a snippet that CALLS the candidate's function and
            # prints the result — it's appended after their code and run,
            # not passed as stdin (most interview-style problems are
            # "write a function", not "read a program's stdin").
            full_program = f"{submitted_code}\n\n{tc.input}"
            run = await execute_code(full_program, language=spec.language)
            actual = (run["stdout"] or "").strip()
            expected = tc.expected_output.strip()
            test_results.append({
                "description": tc.description,
                "input": tc.input,
                "expected_output": expected,
                "actual_output": actual,
                "passed": actual == expected and run["exit_code"] == 0,
                "stderr": run["stderr"],
                "signal": run["signal"],
            })
        except Exception as e:
            test_results.append({
                "description": tc.description,
                "input": tc.input,
                "expected_output": tc.expected_output,
                "actual_output": None,
                "passed": False,
                "stderr": f"execution error: {e}",
                "signal": None,
            })

    prompt = CODE_REVIEW_PROMPT.format(
        problem_statement=spec.problem_statement,
        language=spec.language,
        code=submitted_code,
        test_results_json=json.dumps(test_results, indent=2),
    )

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    with traced_generation("code_review", session_id=session_id, input_data=prompt) as gen:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        gen.record_response(response)
        try:
            data = json.loads(_clean_json(response.text))
        except json.JSONDecodeError:
            logger.error("code_judge JSON parse failed. Raw response:\n%s", response.text)
            raise

    # Ground truth always wins over whatever the model reported for these two.
    data["tests_passed"] = sum(1 for t in test_results if t["passed"])
    data["tests_total"] = len(test_results)

    return CodeReviewResult(**data)
