"""Offline tests for the eval harness itself (no API keys / network)."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from agent.code_review_flow import REVIEW_FAILED_INSTRUCTIONS, review_reply_instructions
from agent.session_state import AgentSessionState, follow_up_policy_note
from backend.models.interview_plan import CodingSpec, InterviewQuestion
from backend.tests.conftest import make_plan
from evals import interview_driver, run_eval
from evals.checks import deterministic_checks
from evals.summary import below_threshold, run_passed, summarize


def _entry(speaker, text, qi):
    return {"speaker": speaker, "text": text, "timestamp": 0.0, "question_index": qi}


def _coding_plan():
    plan = make_plan(n_questions=2)
    plan.questions[1] = InterviewQuestion(
        id="q2", category="technical", question="Write fizzbuzz", intent="x",
        question_type="coding",
        coding_spec=CodingSpec(problem_statement="Write fizzbuzz(n)", starter_code="def fizzbuzz(n): ..."),
    )
    return plan


# ---------------------------------------------------------------- checks
def test_silent_interviewer_turn_is_flagged():
    plan = make_plan()
    t = [_entry("system", interview_driver.SILENT_TURN_NOTE, 1)]
    assert not deterministic_checks(t, plan.questions, 1)["interviewer_never_silent"]
    assert deterministic_checks([], plan.questions, 1)["interviewer_never_silent"]


def test_follow_up_cap_check_detects_violation():
    plan = make_plan(n_questions=2)
    ok = [_entry("candidate", f"a{i}", 0) for i in range(3)]       # answer + 2 follow-ups
    bad = [_entry("candidate", f"a{i}", 0) for i in range(4)]      # answer + 3 follow-ups
    assert deterministic_checks(ok, plan.questions, 1)["follow_up_cap_respected"]
    assert not deterministic_checks(bad, plan.questions, 1)["follow_up_cap_respected"]


def test_safety_cap_marks_interview_not_ended():
    plan = make_plan()
    t = [_entry("system", "Eval safety cap hit: interview did not end within 30 turns.", 0)]
    assert not deterministic_checks(t, plan.questions, 0)["interview_ended_normally"]


def test_coding_checks_require_submission_and_review():
    plan = _coding_plan()
    good = [
        _entry("candidate", "[Submitted code]\ndef fizzbuzz(n): pass", 1),
        _entry("system", "Code review for q2: 3/3 tests passed", 1),
    ]
    checks = deterministic_checks(good, plan.questions, 2)
    assert checks["coding_question_reached"] and checks["code_submitted_for_each_reached_coding_question"]
    assert checks["code_review_ran"]

    no_review = [_entry("candidate", "[Submitted code]\nx", 1)]
    assert not deterministic_checks(no_review, plan.questions, 2)["code_review_ran"]
    assert not deterministic_checks([], plan.questions, 2)["code_submitted_for_each_reached_coding_question"]


def test_coding_check_does_not_count_code_as_spoken_follow_ups():
    plan = _coding_plan()
    t = [_entry("candidate", "[Submitted code]\nx", 1)] * 5
    assert deterministic_checks(t, plan.questions, 2)["follow_up_cap_respected"]


# --------------------------------------------------------------- summary
def _res(persona, passed=True, error=None, checks=None):
    return {
        "persona": persona, "error": error,
        "verdict": {"overall_pass": passed}, "checks": checks or {"a": True},
    }


def test_run_passed_requires_judge_checks_and_no_error():
    assert run_passed(_res("p"))
    assert not run_passed(_res("p", passed=False))
    assert not run_passed(_res("p", checks={"a": True, "b": False}))
    assert not run_passed(_res("p", error="boom"))


def test_summarize_pass_rate_and_threshold():
    results = [_res("strong"), _res("strong"), _res("strong", passed=False), _res("vague", error="x")]
    s = summarize(results)
    assert s["strong"]["passed"] == 2 and s["strong"]["runs"] == 3 and s["strong"]["pass_rate"] == 0.667
    assert s["vague"]["errors"] == 1 and s["vague"]["pass_rate"] == 0
    assert below_threshold(s, 0.5) == ["vague"]
    assert set(below_threshold(s, 1.0)) == {"strong", "vague"}


def test_summarize_counts_failed_checks():
    s = summarize([_res("p", checks={"x": False}), _res("p", checks={"x": False, "y": True})])
    assert s["p"]["failed_checks"] == {"x": 2}


# ---------------------------------------------------- shared follow-up rule
def test_policy_note_is_none_for_coding_questions():
    state = AgentSessionState("s", _coding_plan())
    state.current_question_index = 1
    assert follow_up_policy_note(state) is None
    assert state.candidate_turns_this_question == 0


def test_policy_note_counts_and_enforces():
    state = AgentSessionState("s", make_plan())
    notes = [follow_up_policy_note(state) for _ in range(3)]
    assert "0/2" in notes[0] and "1/2" in notes[1]
    assert "do NOT ask another follow-up" in notes[2]


# ------------------------------------------------------ driver internals
class FakeChat:
    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.sent = []

    async def send_message(self, parts):
        self.sent.append(parts)
        return self.behaviours.pop(0)(parts)


def test_send_rolls_back_state_so_retries_do_not_double_apply_tools():
    state = AgentSessionState("s", make_plan(n_questions=3))
    flags = {"ended": False}

    def tool_then_fail(parts):
        state.advance_question()        # the tool already ran...
        flags["ended"] = True
        raise RuntimeError("503 after tool call")

    def ok(parts):
        state.advance_question()
        return SimpleNamespace(text="next question")

    chat = FakeChat([tool_then_fail, ok])
    out = asyncio.run(interview_driver._send(chat, ["hi"], state, flags, "t", base_delay=0))
    assert out.text == "next question"
    assert state.current_question_index == 1   # advanced once, not twice
    assert flags["ended"] is False             # failed attempt's side effects undone


def _coding_state():
    state = AgentSessionState("s", _coding_plan())
    state.current_question_index = 1
    return state


class FakeCandidate:
    async def write_code(self, problem, starter):
        return "def fizzbuzz(n):\n    return []"


def test_coding_turn_records_review_and_prompts_interviewer(monkeypatch):
    review = SimpleNamespace(tests_passed=2, tests_total=3, correctness_score=6.0, code_quality_notes="ok")

    async def fake_review(q, code, sid):
        return review

    monkeypatch.setattr("backend.services.code_judge.review_code", fake_review)
    state, flags, submitted = _coding_state(), {"ended": False}, set()
    chat = FakeChat([lambda p: SimpleNamespace(text="Nice approach.")])

    reply = asyncio.run(interview_driver._coding_turn(chat, FakeCandidate(), state, flags, "s", submitted, 0))

    assert reply == "Nice approach." and submitted == {"q2"}
    assert chat.sent == [[review_reply_instructions(review)]]
    texts = [(e["speaker"], e["text"]) for e in state.transcript]
    assert texts[0][1].startswith("[Submitted code]")
    assert texts[1][0] == "system" and "2/3 tests passed" in texts[1][1]


def test_coding_turn_review_failure_uses_production_fallback(monkeypatch):
    async def boom(q, code, sid):
        raise ConnectionError("piston down")

    monkeypatch.setattr("backend.services.code_judge.review_code", boom)
    state, flags = _coding_state(), {"ended": False}
    chat = FakeChat([lambda p: SimpleNamespace(text="Sorry, technical issue.")])

    asyncio.run(interview_driver._coding_turn(chat, FakeCandidate(), state, flags, "s", set(), 0))

    assert chat.sent == [[REVIEW_FAILED_INSTRUCTIONS]]
    assert not any(e["text"].startswith("Code review for") for e in state.transcript)
    # ...which the deterministic check then reports as a failed run:
    assert not deterministic_checks(state.transcript, state.plan.questions, 2)["code_review_ran"]


# -------------------------------------------------------------- run_one
@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "tracing_enabled", lambda: False)
    return tmp_path


def test_run_one_never_raises_and_records_the_error(results_dir, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("gemini exploded")

    monkeypatch.setattr(run_eval, "analyze_resume", boom)
    r = asyncio.run(run_eval.run_one("strong"))
    assert r["error"] and "gemini exploded" in r["error"] and r["passed"] is False
    assert json.loads(next(results_dir.glob("*.json")).read_text())["error"] == r["error"]


def test_run_one_times_out_hung_runs(results_dir, monkeypatch):
    async def hang(*a, **k):
        await asyncio.sleep(30)

    monkeypatch.setattr(run_eval, "analyze_resume", hang)
    r = asyncio.run(run_eval.run_one("strong", timeout_s=0.05))
    assert r["error"].startswith("TimeoutError") and r["passed"] is False


def test_run_one_success_applies_deterministic_checks(results_dir, monkeypatch):
    plan = make_plan(n_questions=2)

    async def ret(value):
        return value

    async def fake_interview(plan_, persona, sid, instr=None):
        state = AgentSessionState(sid, plan_)
        state.transcript = [_entry("candidate", f"a{i}", 0) for i in range(5)]  # 4 follow-ups!
        return state

    monkeypatch.setattr(run_eval, "analyze_resume", lambda *a: ret(plan.candidate))
    monkeypatch.setattr(run_eval, "analyze_jd", lambda *a: ret(plan.job))
    monkeypatch.setattr(run_eval, "generate_questions", lambda *a, **k: ret(plan))
    monkeypatch.setattr(run_eval, "run_simulated_interview", fake_interview)
    monkeypatch.setattr(run_eval, "generate_report", lambda *a: ret({"overall_score": 5}))
    monkeypatch.setattr(
        run_eval, "judge_interview",
        lambda *a: ret(SimpleNamespace(model_dump=lambda: {"overall_pass": True, "notes": "judge says fine"})),
    )
    r = asyncio.run(run_eval.run_one("strong"))
    # The LLM judge passed it, but the deterministic check catches the cap violation:
    assert r["verdict"]["overall_pass"] is True
    assert r["checks"]["follow_up_cap_respected"] is False
    assert r["passed"] is False and r["error"] is None


def test_coding_personas_use_coding_preset(results_dir, monkeypatch):
    plan = make_plan(n_questions=2)
    seen = {}

    async def ret(value):
        return value

    def fake_generate(*a, **k):
        seen.update(k)
        return ret(plan)

    async def fake_interview(plan_, persona, sid, instr=None):
        return AgentSessionState(sid, plan_)

    monkeypatch.setattr(run_eval, "analyze_resume", lambda *a: ret(plan.candidate))
    monkeypatch.setattr(run_eval, "analyze_jd", lambda *a: ret(plan.job))
    monkeypatch.setattr(run_eval, "generate_questions", fake_generate)
    monkeypatch.setattr(run_eval, "run_simulated_interview", fake_interview)
    monkeypatch.setattr(run_eval, "generate_report", lambda *a: ret({}))
    monkeypatch.setattr(
        run_eval, "judge_interview", lambda *a: ret(SimpleNamespace(model_dump=lambda: {"overall_pass": True}))
    )
    asyncio.run(run_eval.run_one("coder"))
    assert seen["num_coding_questions"] == 4 and seen["total_questions"] == 6
