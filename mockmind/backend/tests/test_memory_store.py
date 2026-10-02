"""Run: cd mockmind && backend/.venv/bin/python -m backend.tests.test_memory_store
Requires a real Redis on REDIS_URL (default redis://localhost:6379)."""
import asyncio
import time

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from backend.models.candidate_memory import CandidateMemory
from backend.services.memory_store import get_memory, save_memory, delete_memory

TEST_EMAIL = "memory-store-test@example.com"


async def main():
    # Clean slate in case a previous run left this key behind.
    await delete_memory(TEST_EMAIL)

    assert await get_memory(TEST_EMAIL) is None
    print("get_memory on missing key returns None: PASS")

    memory = CandidateMemory(email=TEST_EMAIL, weak_categories=["technical"], updated_at=time.time())
    await save_memory(memory)

    fetched = await get_memory(TEST_EMAIL)
    assert fetched is not None
    assert fetched.email == TEST_EMAIL
    assert fetched.weak_categories == ["technical"]
    print("save_memory then get_memory round-trips: PASS")

    await delete_memory(TEST_EMAIL)
    assert await get_memory(TEST_EMAIL) is None
    print("delete_memory removes the record: PASS")

    # Deleting an email that was never stored must not raise (Review Focus #5).
    await delete_memory("never-stored@example.com")
    print("delete_memory on a non-existent email does not raise: PASS")


if __name__ == "__main__":
    asyncio.run(main())
