import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    label: str = "llm_call",
) -> T:
    """Runs fn() up to `attempts` times with exponential backoff (1s, 2s, ...).

    Used around "call the LLM and parse its JSON" so a transient 429/5xx or one
    malformed response doesn't fail the whole run. Re-raises the last error."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001 - any LLM/parse failure is retryable
            last = e
            if i < attempts - 1:
                delay = base_delay * (2 ** i)
                logger.warning("%s failed (attempt %d/%d): %s — retrying in %.1fs", label, i + 1, attempts, e, delay)
                await asyncio.sleep(delay)
    logger.error("%s failed after %d attempts: %s", label, attempts, last)
    assert last is not None
    raise last
