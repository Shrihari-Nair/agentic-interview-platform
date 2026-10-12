import asyncio

import pytest

from backend.tests.conftest import make_plan

pytest.importorskip("livekit.agents")  # needs the agent deps (CI installs livekit-agents)

from agent.interviewer import InterviewerAgent  # noqa: E402
from agent.session_state import MAX_FOLLOW_UPS, AgentSessionState  # noqa: E402


class FakeTurnCtx:
    def __init__(self):
        self.messages = []

    def add_message(self, *, role, content):
        self.messages.append((role, content))


def _turn(agent):
    ctx = FakeTurnCtx()
    asyncio.run(agent.on_user_turn_completed(ctx, None))
    return ctx.messages[0][1]


def test_first_turn_is_the_answer_not_a_follow_up():
    state = AgentSessionState("s1", make_plan())
    assert state.record_candidate_turn() == 0
    assert not state.follow_up_cap_reached


def test_cap_reached_after_max_follow_ups():
    state = AgentSessionState("s1", make_plan())
    counts = [state.record_candidate_turn() for _ in range(MAX_FOLLOW_UPS + 1)]
    assert counts == [0, 1, 2]
    assert state.follow_up_cap_reached


def test_advancing_question_resets_counter():
    state = AgentSessionState("s1", make_plan())
    for _ in range(3):
        state.record_candidate_turn()
    state.advance_question()
    assert state.follow_up_count_this_question == 0 and not state.follow_up_cap_reached


def test_hook_tells_llm_to_move_on_once_cap_is_hit():
    agent = InterviewerAgent(AgentSessionState("s1", make_plan()))
    notes = [_turn(agent) for _ in range(MAX_FOLLOW_UPS + 1)]
    assert "do NOT ask another follow-up" not in notes[0]
    assert "do NOT ask another follow-up" not in notes[1]
    assert "do NOT ask another follow-up" in notes[2]
    assert "move_to_next_question" in notes[2]


def test_transcript_autosave_coalesces_writes(monkeypatch):
    from agent import session_state

    monkeypatch.setattr(session_state, "_AUTOSAVE_DELAY_S", 0.01)
    saves = []

    async def run():
        state = AgentSessionState("s1", make_plan())

        async def fake_save():
            saves.append(len(state.transcript))

        state.save = fake_save
        for i in range(5):
            state.add_transcript_entry("candidate", f"line {i}")
        await asyncio.sleep(0.1)

    asyncio.run(run())
    assert saves == [5]  # five entries, one write containing all of them
