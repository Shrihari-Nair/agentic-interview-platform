"""
Runs candidate-submitted code against a self-hosted Piston instance
(https://github.com/engineer-man/piston) — chosen specifically because it's
built to run untrusted/possibly-malicious code safely, free, and
self-hostable alongside everything else in docker-compose.yml.
"""

import os

import aiohttp

PISTON_URL = os.getenv("PISTON_URL", "http://localhost:2000")

_version_cache: dict[str, str] = {}


async def _ensure_language_version(session: aiohttp.ClientSession, language: str) -> str:
    if language in _version_cache:
        return _version_cache[language]

    async with session.get(f"{PISTON_URL}/api/v2/runtimes") as resp:
        resp.raise_for_status()
        runtimes = await resp.json()
    for rt in runtimes:
        if rt["language"] == language:
            _version_cache[language] = rt["version"]
            return rt["version"]

    # Not installed yet — install the latest available version for it.
    async with session.get(f"{PISTON_URL}/api/v2/packages") as resp:
        resp.raise_for_status()
        packages = await resp.json()
    candidates = [p for p in packages if p["language"] == language]
    if not candidates:
        raise ValueError(f"No Piston package available for language {language!r}")
    target = max(candidates, key=lambda p: p["language_version"])

    async with session.post(
        f"{PISTON_URL}/api/v2/packages",
        json={"language": language, "version": target["language_version"]},
    ) as resp:
        resp.raise_for_status()
        installed = await resp.json()

    _version_cache[language] = installed["version"]
    return installed["version"]


async def execute_code(
    code: str, language: str = "python", stdin: str = "", run_timeout_ms: int = 3000
) -> dict:
    """run_timeout_ms default matches Piston's own default server-side cap
    (requests above its configured limit are rejected with 400) — raise it
    only if the self-hosted instance's PISTON_RUN_LIMIT is reconfigured
    higher."""
    """Returns {"stdout", "stderr", "exit_code", "signal", "compile"}."""
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        version = await _ensure_language_version(session, language)
        payload = {
            "language": language,
            "version": version,
            "files": [{"name": "main.py" if language == "python" else "main", "content": code}],
            "stdin": stdin,
            "run_timeout": run_timeout_ms,
        }
        async with session.post(f"{PISTON_URL}/api/v2/execute", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()

    run = data.get("run", {})
    return {
        "stdout": run.get("stdout", ""),
        "stderr": run.get("stderr", ""),
        "exit_code": run.get("code"),
        "signal": run.get("signal"),
        "compile": data.get("compile"),
    }
