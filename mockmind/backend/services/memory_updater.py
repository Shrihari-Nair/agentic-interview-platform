import json
import os
import time

from google import genai
from google.genai import types

from backend.models.candidate_memory import CandidateMemory, QuestionHistoryEntry
from backend.services.tracing import traced_generation

WEAK_THRESHOLD = 6.0
MAX_WEAK_CATEGORIES = 3
MAX_ASKED_QUESTIONS = 50

NOTES_PROMPT = """
You maintain a short rolling summary of a candidate's performance across
multiple mock interview sessions.

PREVIOUS NOTES:
{previous_notes}

THIS SESSION'S REPORT SUMMARY:
{report_summary}

THIS SESSION'S CATEGORY SCORES:
{category_scores_json}

Update the notes in 2-3 sentences, describing TRENDS across sessions (e.g.
"has improved at providing concrete metrics, still tends to give vague
system-design answers") rather than just restating this one session. If
there are no previous notes, write an initial 2-3 sentence summary based on
this session alone. Return ONLY the updated notes text — no JSON, no
markdown, no preamble.
"""


def _recompute_weak_categories(category_scores_history: dict[str, list[float]]) -> list[str]:
    averages = {
        category: sum(scores) / len(scores)
        for category, scores in category_scores_history.items()
        if scores
    }
    weak = sorted(
        (cat for cat, avg in averages.items() if avg < WEAK_THRESHOLD),
        key=lambda cat: averages[cat],
    )
    return weak[:MAX_WEAK_CATEGORIES]


async def _regenerate_notes(previous_notes: str, report: dict, category_scores: dict, session_id: str) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = NOTES_PROMPT.format(
        previous_notes=previous_notes or "(none yet — this is their first session)",
        report_summary=report.get("summary", ""),
        category_scores_json=json.dumps(category_scores, indent=2),
    )
    with traced_generation("memory_notes_update", session_id=session_id, input_data=prompt) as gen:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1024,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        gen.record_response(response)
        return response.text.strip()


async def update_memory_from_report(
    existing: CandidateMemory | None,
    email: str,
    session_id: str,
    plan: dict,
    report: dict,
) -> CandidateMemory:
    """Pure merge logic — no Redis I/O, so it's testable without a live store."""
    memory = existing or CandidateMemory(email=email, updated_at=time.time())

    memory.sessions = [*memory.sessions, session_id]

    category_scores = report.get("category_scores", {})
    for category, score in category_scores.items():
        memory.category_scores_history.setdefault(category, []).append(score)

    memory.weak_categories = _recompute_weak_categories(memory.category_scores_history)

    new_entries = [
        QuestionHistoryEntry(
            session_id=session_id,
            question=q["question"],
            category=q["category"],
            asked_at=plan.get("created_at", time.time()),
        )
        for q in plan.get("questions", [])
    ]
    memory.asked_questions = (memory.asked_questions + new_entries)[-MAX_ASKED_QUESTIONS:]

    memory.interviewer_notes = await _regenerate_notes(
        memory.interviewer_notes, report, category_scores, session_id
    )
    memory.updated_at = time.time()
    return memory
