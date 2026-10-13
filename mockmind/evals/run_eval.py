"""
Eval harness entrypoint — runs a full simulated interview (real resume/JD
analysis -> real question generation -> simulated voice-free interview ->
real report generation) against one or more candidate personas, then has an
LLM judge grade the INTERVIEWER's and REPORT GENERATOR's behavior.

Usage:
    python evals/run_eval.py                            # all conversational personas
    python evals/run_eval.py --persona strong           # one persona
    python evals/run_eval.py --persona coding           # coding personas (needs Piston)
    python evals/run_eval.py --runs 5 --concurrency 3   # pass *rate* over repeated runs
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
from backend.routers.prepare import resolve_plan_options
from evals.checks import deterministic_checks
from evals.fixtures import SAMPLE_RESUME, SAMPLE_JOB_DESCRIPTION
from evals.interview_driver import run_simulated_interview
from evals.judge import judge_interview
from evals.personas import CODING_PERSONAS, PERSONAS
from evals.preflight import check_piston
from evals.summary import below_threshold, run_passed, summarize

RESULTS_DIR = Path(__file__).parent / "results"

# One run = 3 analysis calls + a ~30-turn interview + report + judge.
RUN_TIMEOUT_S = 900


def _save(session_id: str, result: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{session_id}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str))
    return out_path


async def run_one(
    persona: str,
    behavioral_instructions: str | None = None,
    session_prefix: str = "eval",
    timeout_s: float = RUN_TIMEOUT_S,
) -> dict:
    """Runs one full eval. Never raises — any failure anywhere in the
    pipeline (including a bug in the system under test, like a malformed
    report-generator response) is captured as a FAILED result instead of
    crashing the whole batch, and a hung run is cut off after `timeout_s`.
    A harness that can't survive the first bug it finds isn't a working harness.

    `behavioral_instructions`, when given, test-drives a candidate interviewer
    prompt revision instead of the production default — this is the hook the
    eval-driven optimizer (evals/optimizer/) uses to grade a candidate before
    deciding whether to promote it."""
    session_id = f"{session_prefix}-{persona}-{uuid.uuid4().hex[:8]}"
    print(f"\n=== [{persona}] session {session_id} ===")
    box: dict = {"state": None, "plan": None, "report": None}

    async def pipeline():
        print("  generating interview plan (resume -> jd -> questions)...")
        candidate_profile = await analyze_resume(SAMPLE_RESUME, session_id)
        job_profile = await analyze_jd(SAMPLE_JOB_DESCRIPTION, session_id)
        if persona in CODING_PERSONAS:
            opts = resolve_plan_options("coding", "balanced", "standard")
            plan = await generate_questions(candidate_profile, job_profile, session_id, **opts)
        else:
            plan = await generate_questions(candidate_profile, job_profile, session_id)
        box["plan"] = plan
        print(f"  plan ready: {len(plan.questions)} questions")

        print("  running simulated interview...")
        state = await run_simulated_interview(plan, persona, session_id, behavioral_instructions)
        box["state"] = state
        print(f"  interview done: {len(state.transcript)} transcript entries, "
              f"{state.current_question_index}/{len(plan.questions)} questions reached")

        print("  generating report...")
        box["report"] = await generate_report(session_id, plan.model_dump(), state.transcript)

        print("  running judge...")
        verdict = await judge_interview(plan.model_dump(), state.transcript, box["report"], session_id)
        return verdict.model_dump()

    try:
        verdict_dict = await asyncio.wait_for(pipeline(), timeout=timeout_s)
        error = None
    except asyncio.TimeoutError:
        print(f"  !! eval run timed out after {timeout_s:.0f}s")
        verdict_dict = {"overall_pass": False}
        error = f"TimeoutError: run exceeded {timeout_s:.0f}s"
    except Exception as e:
        print(f"  !! eval run raised: {e!r}")
        verdict_dict = {"overall_pass": False}
        error = repr(e)

    state, plan, report = box["state"], box["plan"], box["report"]
    checks = (
        deterministic_checks(state.transcript, plan.questions, state.current_question_index)
        if state and plan else {}
    )

    result = {
        "session_id": session_id,
        "persona": persona,
        "transcript": state.transcript if state else None,
        "transcript_length": len(state.transcript) if state else 0,
        "questions_reached": state.current_question_index if state else None,
        "total_questions": len(plan.questions) if plan else None,
        "report": report,
        "verdict": verdict_dict,
        "checks": checks,
        "error": error,
    }
    result["passed"] = run_passed(result)

    if error is None and tracing_enabled():
        try:
            from langfuse import get_client
            client = get_client()
            scores = {**{k: v for k, v in verdict_dict.items() if isinstance(v, bool)}, **checks}
            for field, value in scores.items():
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

    status = "ERROR" if error else ("PASS" if result["passed"] else "FAIL")
    failed_checks = [k for k, ok in checks.items() if not ok]
    note = error or verdict_dict.get("notes", "")
    if failed_checks:
        note = f"failed checks: {failed_checks}. {note}"
    print(f"  verdict: {status} — {note}")
    print(f"  saved -> {out_path}")
    return result


def _persona_list(choice: str) -> list[str]:
    if choice == "all":
        return [p for p in PERSONAS if p not in CODING_PERSONAS]
    if choice == "coding":
        return sorted(CODING_PERSONAS)
    return [choice]


async def main():
    parser = argparse.ArgumentParser(description="Run MockMind interviewer eval harness.")
    parser.add_argument(
        "--persona", choices=list(PERSONAS) + ["all", "coding"], default="all",
        help="Persona to simulate; 'all' = conversational personas, 'coding' = coding personas (default: all).",
    )
    parser.add_argument("--runs", type=int, default=1, help="Runs per persona (default 1).")
    parser.add_argument("--concurrency", type=int, default=1, help="Runs in parallel (default 1).")
    parser.add_argument(
        "--min-pass-rate", type=float, default=1.0,
        help="Exit non-zero if any persona's pass rate is below this (default 1.0).",
    )
    parser.add_argument("--timeout", type=float, default=RUN_TIMEOUT_S, help="Per-run timeout in seconds.")
    args = parser.parse_args()

    personas = _persona_list(args.persona)
    if any(p in CODING_PERSONAS for p in personas):
        try:
            await check_piston()
        except RuntimeError as e:
            print(f"Preflight failed: {e}")
            sys.exit(2)

    sem = asyncio.Semaphore(max(1, args.concurrency))

    async def guarded(persona: str) -> dict:
        async with sem:
            return await run_one(persona, timeout_s=args.timeout)

    start = time.time()
    jobs = [guarded(p) for p in personas for _ in range(max(1, args.runs))]
    results = await asyncio.gather(*jobs)

    summary = summarize(results)
    print(f"\n=== Summary ({time.time() - start:.1f}s) ===")
    for persona, s in summary.items():
        extra = f"  failed checks: {s['failed_checks']}" if s["failed_checks"] else ""
        print(f"  {persona:<16} {s['passed']}/{s['runs']} passed "
              f"(pass rate {s['pass_rate']:.0%}, {s['errors']} errors){extra}")

    RESULTS_DIR.mkdir(exist_ok=True)
    summary_path = RESULTS_DIR / f"summary-{int(start)}.json"
    summary_path.write_text(json.dumps(
        {"min_pass_rate": args.min_pass_rate, "personas": summary,
         "sessions": [r["session_id"] for r in results]}, indent=2))
    print(f"  summary -> {summary_path}")

    failing = below_threshold(summary, args.min_pass_rate)
    if failing:
        print(f"  BELOW THRESHOLD ({args.min_pass_rate:.0%}): {failing}")
    sys.exit(1 if failing else 0)


if __name__ == "__main__":
    asyncio.run(main())
