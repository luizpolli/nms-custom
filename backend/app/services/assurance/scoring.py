"""Deterministic scoring helpers for assurance summaries."""

SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 40,
    "major": 25,
    "minor": 15,
    "warning": 8,
    "info": 3,
    "clear": 0,
}


def severity_penalty(severity: str, occurrences: int = 1) -> int:
    """Return bounded score penalty for a severity and repeat count."""
    weight = SEVERITY_WEIGHTS.get((severity or "info").lower(), 3)
    return weight * max(1, min(int(occurrences or 1), 5))


def clamp_score(value: float) -> int:
    """Clamp health score to the 0..100 integer range."""
    return max(0, min(100, round(value)))
