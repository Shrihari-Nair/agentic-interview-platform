import os

import aiohttp


async def check_piston() -> None:
    """Coding evals really execute code. Fail fast with a clear fix instead of
    every run erroring deep inside the pipeline."""
    url = os.getenv("PISTON_URL", "http://localhost:2000")
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(f"{url}/api/v2/runtimes") as resp:
                resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"Piston sandbox not reachable at {url} ({e!r}). Coding personas need it: "
            "run `docker compose up -d piston` (or set PISTON_URL)."
        ) from e
