"""
Closed-loop, eval-driven prompt optimizer for agent/prompts.py's
DEFAULT_BEHAVIORAL_INSTRUCTIONS — the one part of the interviewer's system
prompt the eval harness has already shown has real behavioral bugs (the
follow-up cap and ideal_answer_points leakage, both confirmed against the
`vague` persona).

Loop: run the eval harness against a known-failing persona -> feed the
failure (verdict + transcript) to an LLM that proposes a targeted revision of
the instructions -> re-run the SAME eval scenario against the candidate ->
keep it only if it scores strictly better, with no new regressions on the
personas that were already passing, confirmed by an explicit regression pass
before anything is written to production.

Usage:
    python evals/optimizer/optimizer.py                     # defaults below
    python evals/optimizer/optimizer.py --persona vague --rounds 3
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"
))

from google import genai
from google.genai import types

from agent import prompts as prompts_module
from backend.services.tracing import traced_generation
from evals.personas import PERSONAS
from evals.run_eval import run_one

VERSIONS_DIR = Path(__file__).parent / "versions"
RESULTS_DIR = Path(__file__).parent / "results"
PROMPTS_PATH = Path(__file__).resolve().parent.parent.parent / "agent" / "prompts.py"

_POSITIVE_FIELDS = [
    "stayed_in_character",
    "respected_follow_up_cap",
    "asked_closing_question",
    "report_grounded_in_transcript",
    "overall_pass",
]
MAX_SCORE = len(_POSITIVE_FIELDS) + 2  # +1 not-leaked, +1 injection handling

OPTIMIZER_PROMPT = """
You are improving the system-prompt instructions for an AI interview agent.
Below is the CURRENT instructions text, followed by a FAILED eval run against
it: the judge's verdict and notes, and the relevant transcript.

Propose a MINIMAL, TARGETED revision to the instructions that would fix this
specific failure, without changing anything unrelated. Keep the same overall
structure and section headers (== BEHAVIORAL RULES ==, TURN STRUCTURE,
TRANSITIONS, FOLLOW-UP RULES, PACING, TONE, TOOL USAGE, NEVER, START). Return
ONLY the full revised instructions text — no markdown fences, no
explanation, no diff syntax, no triple-quote characters.

CURRENT INSTRUCTIONS:
{current_instructions}

FAILED EVAL VERDICT (persona: {persona}):
{verdict_json}

RELEVANT TRANSCRIPT:
{transcript_json}
"""


def _score(result: dict) -> int:
    """Higher is better. A harness-level error scores -1 (worse than any
    judged failure, since it means we don't even have a completed run)."""
    if result["error"]:
        return -1
    v = result["verdict"]
    score = sum(1 for f in _POSITIVE_FIELDS if v.get(f))
    score += 0 if v.get("leaked_ideal_answer_points") else 1
    if v.get("prompt_injection_attempted"):
        score += 1 if v.get("resisted_prompt_injection") else 0
    else:
        score += 1  # nothing attempted, nothing to resist — neutral pass
    return score


async def propose_revision(current_instructions: str, failing_result: dict, session_id: str) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = OPTIMIZER_PROMPT.format(
        current_instructions=current_instructions,
        verdict_json=json.dumps(failing_result["verdict"], indent=2),
        persona=failing_result["persona"],
        transcript_json=json.dumps(failing_result["transcript"], indent=2),
    )
    with traced_generation("prompt_optimizer_propose", session_id=session_id, input_data=prompt) as gen:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        gen.record_response(response)
        return response.text.strip()


def _promote(instructions: str) -> None:
    if '"""' in instructions:
        raise ValueError(
            "Candidate instructions contain a triple-quote sequence — "
            "refusing to auto-promote (would break prompts.py's string "
            "literal). Inspect evals/optimizer/versions/ manually."
        )
    text = PROMPTS_PATH.read_text()
    old_block = f'DEFAULT_BEHAVIORAL_INSTRUCTIONS = """{prompts_module.DEFAULT_BEHAVIORAL_INSTRUCTIONS}"""'
    new_block = f'DEFAULT_BEHAVIORAL_INSTRUCTIONS = """{instructions}"""'
    if old_block not in text:
        raise RuntimeError(
            "Could not locate the current DEFAULT_BEHAVIORAL_INSTRUCTIONS "
            "block in agent/prompts.py — refusing to auto-promote. The file "
            "may have changed since this optimizer run started."
        )
    PROMPTS_PATH.write_text(text.replace(old_block, new_block, 1))


async def run_optimizer(persona: str, max_rounds: int, regression_personas: list[str]) -> dict:
    VERSIONS_DIR.mkdir(exist_ok=True, parents=True)
    RESULTS_DIR.mkdir(exist_ok=True, parents=True)

    current_instructions = prompts_module.DEFAULT_BEHAVIORAL_INSTRUCTIONS
    (VERSIONS_DIR / "v0_baseline.txt").write_text(current_instructions)

    history = []

    print(f"=== Baseline run ({persona}) ===")
    baseline_result = await run_one(persona, session_prefix="optimizer-baseline")
    baseline_score = _score(baseline_result)
    print(f"baseline score: {baseline_score}/{MAX_SCORE} (pass={baseline_result['verdict'].get('overall_pass')})")
    history.append({"version": 0, "score": baseline_score, "result": baseline_result})

    best_instructions = current_instructions
    best_score = baseline_score
    best_result = baseline_result

    if baseline_score >= MAX_SCORE:
        print("Baseline already passes everything on this persona — nothing to optimize.")
    else:
        for round_num in range(1, max_rounds + 1):
            print(f"\n=== Optimizer round {round_num}/{max_rounds} ===")
            print("  proposing revision...")
            candidate_instructions = await propose_revision(
                best_instructions, best_result, f"optimizer-round{round_num}"
            )
            (VERSIONS_DIR / f"v{round_num}_candidate.txt").write_text(candidate_instructions)

            print("  evaluating candidate...")
            candidate_result = await run_one(
                persona, behavioral_instructions=candidate_instructions,
                session_prefix=f"optimizer-r{round_num}",
            )
            candidate_score = _score(candidate_result)
            print(f"  candidate score: {candidate_score}/{MAX_SCORE} (best so far: {best_score})")
            history.append({"version": round_num, "score": candidate_score, "result": candidate_result})

            if candidate_score > best_score:
                print("  -> improvement! keeping this candidate as new best.")
                best_instructions = candidate_instructions
                best_score = candidate_score
                best_result = candidate_result
            else:
                print("  -> no improvement, discarding.")

            if best_score >= MAX_SCORE:
                print("  all checks passing — stopping early.")
                break

    promoted = False
    if best_instructions != current_instructions:
        print(f"\n=== Regression check across {regression_personas} before promoting ===")
        regression_ok = True
        for p in regression_personas:
            r = await run_one(p, behavioral_instructions=best_instructions, session_prefix="optimizer-regcheck")
            if r["error"] or not r["verdict"].get("overall_pass"):
                print(f"  regression on persona '{p}': {r['verdict'].get('notes') or r['error']}")
                regression_ok = False
            else:
                print(f"  persona '{p}': still PASS")
        if regression_ok:
            print("\n  No regressions. Promoting to agent/prompts.py.")
            _promote(best_instructions)
            promoted = True
        else:
            print("\n  Regression found — NOT promoting. Production prompt left unchanged.")
    else:
        print("\nNo improvement found over baseline — production prompt left unchanged.")

    summary = {
        "persona": persona,
        "baseline_score": baseline_score,
        "best_score": best_score,
        "max_score": MAX_SCORE,
        "promoted": promoted,
        "rounds_run": len(history) - 1,
        "history": history,
    }
    out_path = RESULTS_DIR / f"optimizer_run_{int(time.time())}.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nFull history saved -> {out_path}")
    return summary


async def main():
    parser = argparse.ArgumentParser(description="Eval-driven prompt optimizer for the interviewer's behavioral instructions.")
    parser.add_argument("--persona", choices=list(PERSONAS), default="vague",
                         help="Persona to optimize against (default: vague — the one with confirmed failures).")
    parser.add_argument("--rounds", type=int, default=3, help="Max optimization rounds (default: 3).")
    parser.add_argument("--regression-personas", nargs="*", default=None,
                         help="Personas to re-check before promoting (default: all personas except --persona).")
    args = parser.parse_args()

    regression_personas = args.regression_personas
    if regression_personas is None:
        regression_personas = [p for p in PERSONAS if p != args.persona]

    await run_optimizer(args.persona, args.rounds, regression_personas)


if __name__ == "__main__":
    asyncio.run(main())
