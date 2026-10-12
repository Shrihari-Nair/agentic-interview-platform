import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.interview_plan import SessionState
from backend.tests.conftest import make_plan

GOOD_REPORT = {
    "overall_score": 8.0,
    "hiring_recommendation": "yes",
    "category_scores": {"technical": 8},
    "summary": "",
    "strengths": [],
    "improvements": [],
    "question_feedback": [],
}


def _client():
    from backend.routers import session

    app = FastAPI()
    app.include_router(session.router)
    return TestClient(app)


def test_pipeline_success_stores_report_and_marks_ready(fake_redis, monkeypatch):
    from backend.services import report_pipeline, report_store

    async def fake_generate(**kw):
        return GOOD_REPORT

    monkeypatch.setattr(report_pipeline, "generate_report", fake_generate)
    ok = asyncio.run(report_pipeline.run_report_pipeline("s1", make_plan().model_dump(), [{"speaker": "candidate", "text": "hi"}]))
    assert ok is True
    assert json.loads(fake_redis.store["interview_report:s1"])["overall_score"] == 8.0
    assert asyncio.run(report_store.get_status("s1")) == "ready"


def test_pipeline_failure_marks_failed_and_never_raises(fake_redis, monkeypatch):
    from backend.services import report_pipeline, report_store

    async def boom(**kw):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(report_pipeline, "generate_report", boom)
    ok = asyncio.run(report_pipeline.run_report_pipeline("s1", make_plan().model_dump(), []))
    assert ok is False
    assert "interview_report:s1" not in fake_redis.store
    assert asyncio.run(report_store.get_status("s1")) == "failed"


def test_get_report_states(fake_redis):
    c = _client()
    assert c.get("/api/report/s1").status_code == 404  # still generating / unknown

    fake_redis.store["interview_report_status:s1"] = "failed"
    r = c.get("/api/report/s1")
    assert r.status_code == 502 and r.json()["detail"]["status"] == "failed"

    fake_redis.store["interview_report:s1"] = json.dumps(GOOD_REPORT)
    assert c.get("/api/report/s1").status_code == 200


def test_retry_unknown_session_404(fake_redis):
    assert _client().post("/api/report/nope/retry").status_code == 404


def test_retry_without_transcript_409(fake_redis):
    state = SessionState(session_id="s1", plan=make_plan())
    fake_redis.store["session_state:s1"] = state.model_dump_json()
    assert _client().post("/api/report/s1/retry").status_code == 409


def test_retry_regenerates_from_persisted_transcript(fake_redis, monkeypatch):
    from backend.routers import session

    seen = {}

    async def fake_pipeline(session_id, plan, transcript, email):
        seen.update(session_id=session_id, transcript=transcript)
        return True

    monkeypatch.setattr(session, "run_report_pipeline", fake_pipeline)
    state = SessionState(session_id="s1", plan=make_plan(), transcript=[{"speaker": "candidate", "text": "hello"}])
    fake_redis.store["session_state:s1"] = state.model_dump_json()
    fake_redis.store["interview_report_status:s1"] = "failed"

    async def run():
        out = await session.retry_report("s1")
        await asyncio.gather(*list(session._retry_tasks))  # the fire-and-forget regeneration
        return out

    assert asyncio.run(run()) == {"status": "pending"}
    assert fake_redis.store["interview_report_status:s1"] == "pending"
    assert seen == {"session_id": "s1", "transcript": [{"speaker": "candidate", "text": "hello"}]}


def test_retry_is_a_noop_while_already_pending(fake_redis):
    fake_redis.store["interview_report_status:s1"] = "pending"
    assert _client().post("/api/report/s1/retry").json() == {"status": "pending"}
