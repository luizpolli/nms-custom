"""Assurance scoring and correlation helpers."""

from .scoring import SEVERITY_WEIGHTS, clamp_score, severity_penalty

__all__ = ["SEVERITY_WEIGHTS", "clamp_score", "severity_penalty"]
