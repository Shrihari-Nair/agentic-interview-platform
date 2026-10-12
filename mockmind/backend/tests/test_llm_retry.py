import asyncio

import pytest

from backend.services.llm_retry import retry_async


def test_succeeds_after_transient_failures():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429")
        return "ok"

    assert asyncio.run(retry_async(flaky, attempts=3, base_delay=0)) == "ok"
    assert calls["n"] == 3


def test_raises_last_error_after_exhausting_attempts():
    calls = {"n": 0}

    async def always_bad():
        calls["n"] += 1
        raise ValueError(f"bad json {calls['n']}")

    with pytest.raises(ValueError, match="bad json 3"):
        asyncio.run(retry_async(always_bad, attempts=3, base_delay=0))
    assert calls["n"] == 3


def test_no_retry_when_first_call_succeeds():
    calls = {"n": 0}

    async def ok():
        calls["n"] += 1
        return 1

    asyncio.run(retry_async(ok, base_delay=0))
    assert calls["n"] == 1
