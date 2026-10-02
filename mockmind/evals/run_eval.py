"""
Eval harness entrypoint — runs a full simulated interview (real resume/JD
analysis -> real question generation -> simulated voice-free interview ->
real report generation) against one or more candidate personas, then has an
LLM judge grade the INTERVIEWER's and REPORT GENERATOR's behavior.

Usage:
    python evals/run_eval.py                  # all personas
    python evals/run_eval.py --persona strong  # one persona
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s]: %(message)s")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from backend.agents.resume_analyzer import analyze_resume
from backend.agents.jd_analyzer import analyze_jd
from backend.agents.question_generator import generate_questions
from backend.services.report_generator import generate_report
from backend.services.tracing import is_enabled as tracing_enabled
from evals.fixtures import SAMPLE_RESUME, SAMPLE_JOB_DESCRIPTION
from evals.interview_driver import run_simulated_interview
from evals.judge import judge_interview
from evals.personas import PERSONAS

RESULTS_DIR = Path(__file__).parent / "results"


def _save(session_id: str, result: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{session_id}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str))
    return out_path


async def run_one(
    persona: str,
    behavioral_instructions: str | None = None,
    session_prefix: str = "eval",
) -> dict:
    """Runs one full eval. Never raises — any failure anywhere in the
    pipeline (including a bug in the system under test, like a malformed
    report-generator response) is captured as a FAILED result instead of
    crashing the whole batch. A harness that can't survive the first bug it
    finds isn't a working harness.

    `behavioral_instructions`, when given, test-drives a candidate interviewer
    prompt revision instead of the production default — this is the hook the
    eval-driven optimizer (evals/optimizer/) uses to grade a candidate before
    deciding whether to promote it."""
    session_id = f"{session_prefix}-{persona}-{uuid.uuid4().hex[:8]}"
    print(f"\n=== [{persona}] session {session_id} ===")
    state = None
    plan = None
    report = None

    try:
        print("  generating interview plan (resume -> jd -> questions)...")
        candidate_profile = await analyze_resume(SAMPLE_RESUME, session_id)
        job_profile = await analyze_jd(SAMPLE_JOB_DESCRIPTION, session_id)
        plan = await generate_questions(candidate_profile, job_profile, session_id)
        print(f"  plan ready: {len(plan.questions)} questions")

        print("  running simulated interview...")
        state = await run_simulated_interview(plan, persona, session_id, behavioral_instructions)
        print(f"  interview done: {len(state.transcript)} transcript entries, "
              f"{state.current_question_index}/{len(plan.questions)} questions reached")

        print("  generating report...")
        report = await generate_report(session_id, plan.model_dump(), state.transcript)

        print("  running judge...")
        verdict = await judge_interview(plan.model_dump(), state.transcript, report, session_id)
        verdict_dict = verdict.model_dump()
        error = None
    except Exception as e:
        print(f"  !! eval run raised: {e!r}")
        verdict_dict = {"overall_pass": False}
        error = repr(e)

    result = {
        "session_id": session_id,
        "persona": persona,
        "transcript": state.transcript if state else None,
        "transcript_length": len(state.transcript) if state else 0,
        "questions_reached": state.current_question_index if state else None,
        "total_questions": len(plan.questions) if plan else None,
        "report": report,
        "verdict": verdict_dict,
        "error": error,
    }

    if error is None and tracing_enabled():
        try:
            from langfuse import get_client
            client = get_client()
            for field, value in verdict_dict.items():
                if isinstance(value, bool):
                    client.create_score(
                        name=f"eval_{field}",
                        value=1.0 if value else 0.0,
                        data_type="BOOLEAN",
                        session_id=session_id,
                    )
            client.flush()
        except Exception as e:
            print(f"  (warning: failed to push eval scores to Langfuse: {e})")

    out_path = _save(session_id, result)

    status = "ERROR" if error else ("PASS" if verdict_dict.get("overall_pass") else "FAIL")
    note = error or verdict_dict.get("notes", "")
    print(f"  verdict: {status} — {note}")
    print(f"  saved -> {out_path}")
    return result


async def main():
    parser = argparse.ArgumentParser(description="Run MockMind interviewer eval harness.")
    parser.add_argument(
        "--persona", choices=list(PERSONAS) + ["all"], default="all",
        help="Which candidate persona to simulate (default: all).",
    )
    args = parser.parse_args()

    personas = list(PERSONAS) if args.persona == "all" else [args.persona]

    start = time.time()
    results = []
    for persona in personas:
        results.append(await run_one(persona))

    print(f"\n=== Summary ({time.time() - start:.1f}s) ===")
    for r in results:
        status = "ERROR" if r["error"] else ("PASS" if r["verdict"]["overall_pass"] else "FAIL")
        print(f"  [{status}] {r['persona']:<16} {r['session_id']}")

    failures = [r for r in results if r["error"] or not r["verdict"]["overall_pass"]]
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
