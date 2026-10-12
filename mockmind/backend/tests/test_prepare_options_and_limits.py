import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import prepare
from backend.routers.prepare import (
    GENERIC_PREP_ERROR, MAX_RESUME_BYTES, PreparationError, resolve_plan_options, validate_resume_upload,
)


def test_standard_defaults():
    o = resolve_plan_options("standard", "balanced", "standard")
    assert o["total_questions"] == 16 and o["num_coding_questions"] == 0 and o["level_weights"] is None


def test_quick_and_harder():
    o = resolve_plan_options("standard", "harder", "quick")
    assert o["total_questions"] == 8
    assert o["level_weights"]["advanced"] > o["level_weights"]["basic"]


def test_coding_ignores_length_choice():
    o = resolve_plan_options("coding", "balanced", "quick")
    assert o["total_questions"] == 6 and o["num_coding_questions"] == 4


def test_unknown_values_fall_back_to_defaults():
    o = resolve_plan_options("bogus", "nonsense", "huge")
    assert o["total_questions"] == 16 and o["level_weights"] is None and o["num_coding_questions"] == 0


@pytest.mark.parametrize("name,size", [("cv.exe", 10), ("cv", 10), ("cv.pdf", 0), ("cv.pdf", MAX_RESUME_BYTES + 1)])
def test_bad_uploads_rejected(name, size):
    with pytest.raises(PreparationError):
        validate_resume_upload(name, size)


@pytest.mark.parametrize("name", ["cv.pdf", "cv.DOCX", "cv.txt"])
def test_good_uploads_accepted(name):
    validate_resume_upload(name, 1000)


def _events(resp):
    return [json.loads(l[6:]) for l in resp.text.splitlines() if l.startswith("data: ")]


def _post(client, filename="cv.txt", content=b"Jane Doe, Python engineer", jd="x" * 100):
    return client.post(
        "/api/prepare",
        files={"resume": (filename, content, "text/plain")},
        data={"job_description": jd},
    )


def _client():
    app = FastAPI()
    app.include_router(prepare.router)
    return TestClient(app)


def test_prepare_rejects_bad_file_type_with_friendly_message():
    events = _events(_post(_client(), filename="cv.exe"))
    assert events[-1]["stage"] == "error" and "Unsupported file type" in events[-1]["message"]


def test_prepare_rejects_oversized_resume():
    events = _events(_post(_client(), content=b"a" * (MAX_RESUME_BYTES + 10)))
    assert events[-1]["stage"] == "error" and "too large" in events[-1]["message"]


def test_prepare_rejects_overlong_job_description():
    events = _events(_post(_client(), jd="x" * (prepare.MAX_JD_CHARS + 1)))
    assert events[-1]["stage"] == "error" and "too long" in events[-1]["message"]


def test_unexpected_errors_hide_internal_detail(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("internal API key sk-secret leaked in traceback")

    monkeypatch.setattr(prepare, "analyze_resume", boom)
    events = _events(_post(_client()))
    assert events[-1]["stage"] == "error"
    assert events[-1]["message"] == GENERIC_PREP_ERROR
    assert "sk-secret" not in json.dumps(events)
