"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_maybe_fetch_memory_resilience
No real Redis needed — this specifically tests what happens when the memory
store is unreachable/erroring (Review Focus #3)."""
import asyncio
from unittest.mock import patch

from backend.routers.prepare import _maybe_fetch_memory


async def main():
    # use_memory=False: must skip the store entirely, regardless of email.
    memory, email = await _maybe_fetch_memory(False, "someone@example.com")
    assert memory is None and email is None
    print("use_memory=False skips the store entirely: PASS")

    # Simulates the memory store being down/erroring — must not raise, and
    # must not block interview preparation.
    with patch(
        "backend.services.memory_store.get_memory",
        side_effect=ConnectionError("simulated Redis outage"),
    ):
        memory, email = await _maybe_fetch_memory(True, "someone@example.com")
        assert memory is None
        assert email == "someone@example.com"  # email is still normalized/returned
    print("memory-store failure is swallowed, does not raise: PASS")


if __name__ == "__main__":
    asyncio.run(main())
