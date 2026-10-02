import hashlib

from backend.models.candidate_memory import CandidateMemory
from backend.services.redis_client import redis_client

KEY_PREFIX = "candidate_memory:"
TTL_SECONDS = 60 * 60 * 24 * 365  # 1 year — a deliberate expiry, not forever


def _key(email: str) -> str:
    normalized = email.strip().lower()
    return KEY_PREFIX + hashlib.sha256(normalized.encode()).hexdigest()


async def get_memory(email: str) -> CandidateMemory | None:
    raw = await redis_client.get(_key(email))
    if not raw:
        return None
    return CandidateMemory.model_validate_json(raw)


async def save_memory(memory: CandidateMemory) -> None:
    await redis_client.setex(_key(memory.email), TTL_SECONDS, memory.model_dump_json())


async def delete_memory(email: str) -> None:
    await redis_client.delete(_key(email))
