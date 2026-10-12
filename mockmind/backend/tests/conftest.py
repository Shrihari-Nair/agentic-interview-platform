import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeRedis:
    """Just enough of redis.asyncio.Redis for the report/session code paths."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def set(self, key, value, *a, **k):
        self.store[key] = value

    async def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    async def ping(self):
        return True

    async def aclose(self):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    r = FakeRedis()
    for mod in (
        "backend.services.redis_client",
        "backend.services.report_store",
        "backend.services.report_pipeline",
        "backend.routers.session",
    ):
        __import__(mod)
        if hasattr(sys.modules[mod], "redis_client"):
            monkeypatch.setattr(sys.modules[mod], "redis_client", r)
    return r


def make_plan(session_id="s1", email=None, n_questions=3):
    from backend.models.interview_plan import (
        CandidateProfile, InterviewPlan, InterviewQuestion, JobProfile,
    )

    return InterviewPlan(
        session_id=session_id,
        candidate=CandidateProfile(name="Test Candidate"),
        job=JobProfile(title="Backend Engineer"),
        questions=[
            InterviewQuestion(id=f"q{i + 1}", category="technical", question=f"Question {i + 1}?", intent="x")
            for i in range(n_questions)
        ],
        opening_message="Hi!",
        created_at=0.0,
        candidate_email=email,
    )
