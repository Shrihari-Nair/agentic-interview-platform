"""Aggregation across repeated eval runs — one LLM-judged run is a noisy
sample, so the harness reports a pass *rate* per persona."""


def run_passed(result: dict) -> bool:
    """A run passes only if it completed, the LLM judge passed it, and every
    deterministic check passed."""
    if result.get("error"):
        return False
    if not result.get("verdict", {}).get("overall_pass"):
        return False
    return all(result.get("checks", {}).values())


def summarize(results: list[dict]) -> dict:
    by_persona: dict[str, dict] = {}
    for r in results:
        s = by_persona.setdefault(r["persona"], {"runs": 0, "passed": 0, "errors": 0, "failed_checks": {}})
        s["runs"] += 1
        s["errors"] += 1 if r.get("error") else 0
        s["passed"] += 1 if run_passed(r) else 0
        for name, ok in (r.get("checks") or {}).items():
            if not ok:
                s["failed_checks"][name] = s["failed_checks"].get(name, 0) + 1
    for s in by_persona.values():
        s["pass_rate"] = round(s["passed"] / s["runs"], 3) if s["runs"] else 0.0
    return by_persona


def below_threshold(summary: dict, min_pass_rate: float) -> list[str]:
    return [p for p, s in summary.items() if s["pass_rate"] < min_pass_rate]
