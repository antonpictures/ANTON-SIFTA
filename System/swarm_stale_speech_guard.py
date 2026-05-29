#!/usr/bin/env python3
"""Tiny wording guard for stale measurements.

Receipts are still evidence when they are old. The guard only prevents Alice
from speaking old values as if they were live current body state.
"""
from __future__ import annotations


def is_stale(age_s: float | None, *, threshold_s: int = 86400) -> bool:
    if age_s is None:
        return False
    try:
        return float(age_s) > float(threshold_s)
    except (TypeError, ValueError):
        return False


def stale_phrase(age_s: float | None, *, threshold_s: int = 86400) -> str:
    if not is_stale(age_s, threshold_s=threshold_s):
        return ""
    try:
        hours = int(float(age_s) / 3600.0)
    except (TypeError, ValueError):
        return ""
    return f"last snapshot {hours} hours ago"


def wrap_value_if_stale(
    label: str,
    value: object,
    age_s,
    *,
    threshold_s: int = 86400,
) -> str:
    phrase = stale_phrase(age_s, threshold_s=threshold_s)
    if not phrase:
        return f"{label}={value}"
    return f"{label}=<{phrase}, was {value}>"


__all__ = ["is_stale", "stale_phrase", "wrap_value_if_stale"]
