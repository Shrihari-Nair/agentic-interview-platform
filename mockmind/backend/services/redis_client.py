import os
import redis.asyncio as redis

redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    encoding="utf-8",
    decode_responses=True,
)
