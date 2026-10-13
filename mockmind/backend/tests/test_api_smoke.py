"""API-level end-to-end smoke test: prepare -> token -> (simulated agent) ->
report -> retry -> candidate memory, against a REAL Redis with the LLM calls
stubbed. Covers the glue the eval harness cannot: the FastAPI endpoints, the SSE
stream, Redis keys/TTLs, the agent<->backend hand-off through Redis, and the
report status/retry flow.

Skipped automatically when Redis isn't reachable (set REDIS_URL, or run
`docker compose up -d redis`). CI provides a Redis service container."""
import asyncio
import json
import os
import sys
import uuid

import httpx
import jwt
import pytest
import redis.asyncio as aioredis

from backend.tests.conftest import make_plan

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
GOOD_REPORT = {
    "overall_score": 7.5,
    "hiring_recommendation": "yes",
    "category_scores": {"technical": 5.0, "communication": 8.0},
    "summary": "ok",
    "strengths": ["a"],
    "improvements": ["b"],
    "question_feedback": [],
}


def _redis_up() -> bool:
    async def ping():
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            return await asyncio.wait_for(r.ping(), 2)
        finally:
            await r.aclose()

    try:
        return bool(asyncio.run(ping()))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _redis_up(), reason=f"Redis not reachable at {REDIS_URL}")


@pytest.fixture
def stack(monkeypatch):
    """A fresh Redis client per test (clients are bound to the event loop that
    created them), patched into every module that holds one."""
    monkeypatch.setenv("REDIS_URL", REDIS_URL)
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "x" * 40)
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")

    import backend.main  # noqa: F401  (imports every router)

    holder = {}

    def install(client):
        holder["client"] = client
        for name in (
            "backend.services.redis_client", "backend.services.report_store",
            "backend.services.report_pipeline", "backend.services.memory_store",
            "backend.routers.session", "backend.routers.prepare",
        ):
            monkeypatch.setattr(sys.modules[name], "redis_client", client)

    holder["install"] = install
    return holder


def _sse(resp: httpx.Response) -> list[dict]:
    return [json.loads(l[6:]) for l in resp.text.splitlines() if l.startswith("data: ")]


def test_full_flow_with_real_redis(stack, monkeypatch):
    from agent.session_state import AgentSessionState, generate_and_store_report
    from backend.main import app
    from backend.routers import prepare, session
    from backend.services import memory_store, report_pipeline

    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    created: list[str] = []

    async def fake_resume(text, sid):
        return make_plan(sid).candidate

    async def fake_jd(text, sid):
        return make_plan(sid).job

    async def fake_questions(candidate, job, sid, **kw):
        return make_plan(sid, email=kw.get("candidate_email"), n_questions=4)

    async def fake_notes(*a, **k):
        return "notes"

    monkeypatch.setattr(prepare, "analyze_resume", fake_resume)
    monkeypatch.setattr(prepare, "analyze_jd", fake_jd)
    monkeypatch.setattr(prepare, "generate_questions", fake_questions)
    monkeypatch.setattr("backend.services.memory_updater._regenerate_notes", fake_notes)

    async def main():
        r = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        stack["install"](r)
        transport = httpx.ASGITransport(app=app)
        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                async def prepare_session(with_memory):
                    data = {"job_description": "x" * 80}
                    if with_memory:
                        data.update(use_memory="true", candidate_email=email)
                    resp = await c.post(
                        "/api/prepare", data=data,
                        files={"resume": ("cv.txt", b"Jane Doe, Python engineer", "text/plain")},
                    )
                    events = _sse(resp)
                    assert events[-1]["stage"] == "complete", events
                    sid = events[-1]["session_id"]
                    created.append(sid)
                    return sid

                # ---- prepare: SSE stream completes, plan + state land in Redis with a TTL
                sid = await prepare_session(with_memory=True)
                assert await r.get(f"interview_plan:{sid}")
                assert await r.get(f"session_state:{sid}")
                assert 0 < await r.ttl(f"interview_plan:{sid}") <= 14400

                # ---- token: room + agent dispatch carry the session
                tok = await c.post("/api/token", json={"session_id": sid})
                assert tok.status_code == 200
                claims = jwt.decode(
                    tok.json()["token"], "x" * 40, algorithms=["HS256"], options={"verify_aud": False}
                )
                blob = json.dumps(claims)
                assert f"interview_{sid}" in blob and "mockmind-interviewer" in blob and sid in blob
                assert (await c.post("/api/token", json={"session_id": "unknown"})).status_code == 404

                # ---- report not ready yet
                assert (await c.get(f"/api/report/{sid}")).status_code == 404

                # ---- the agent side: loads the plan from Redis, interviews, generates the report
                state = await AgentSessionState.load(sid)
                state.add_transcript_entry("interviewer", "Question 1?")
                state.add_transcript_entry("candidate", "My answer.")
                async def good_report(**kw):
                    return dict(GOOD_REPORT)

                monkeypatch.setattr(report_pipeline, "generate_report", good_report)
                await generate_and_store_report(state)

                rep = await c.get(f"/api/report/{sid}")
                assert rep.status_code == 200 and rep.json()["overall_score"] == 7.5

                # ---- memory write path (opted in)
                mem = await memory_store.get_memory(email)
                assert mem is not None and mem.sessions == [sid]
                assert mem.weak_categories == ["technical"]

                # ---- failure + retry path: report generation dies, then is retried from Redis
                sid2 = await prepare_session(with_memory=False)
                state2 = await AgentSessionState.load(sid2)
                state2.add_transcript_entry("candidate", "Answer for the retry test.")

                async def broken_report(**kw):
                    raise RuntimeError("gemini down")

                monkeypatch.setattr(report_pipeline, "generate_report", broken_report)
                await generate_and_store_report(state2)
                failed = await c.get(f"/api/report/{sid2}")
                assert failed.status_code == 502 and failed.json()["detail"]["status"] == "failed"

                monkeypatch.setattr(report_pipeline, "generate_report", good_report)
                retry = await c.post(f"/api/report/{sid2}/retry")
                assert retry.status_code == 202
                await asyncio.gather(*list(session._retry_tasks))
                assert (await c.get(f"/api/report/{sid2}")).status_code == 200
        finally:
            for sid_ in created:
                keys = await r.keys(f"*{sid_}*")
                if keys:
                    await r.delete(*keys)
            await memory_store.delete_memory(email)
            await r.aclose()

    asyncio.run(main())
