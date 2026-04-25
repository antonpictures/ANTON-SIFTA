#!/usr/bin/env python3
"""
System/swarm_soul_freshness_gate.py

Freshness guard for `.sifta_state/alice_soul.md`.

The soul digest is a generated mirror, not authority. This module prevents
stale mirrors from being treated as current self-state.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from System.swarm_soul_digest import _SOUL_FILE, generate_soul_digest

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_GENERATED_RE = re.compile(r"^\- \*\*Generated At\*\*: ([0-9]+(?:\.[0-9]+)?)$", re.MULTILINE)
_SOMATIC_RE = re.compile(r"^\- somatic: .*$", re.MULTILINE)


class StaleSoulDigest(RuntimeError):
    """Raised when a stale soul mirror is read without regeneration allowed."""


@dataclass(frozen=True)
class FreshSoul:
    content: str
    generated_at: float
    age_seconds: float
    regenerated: bool
    soul_path: Path
    latest_soma: Optional[Dict[str, Any]]


def extract_generated_at(content: str) -> Optional[float]:
    match = _GENERATED_RE.search(content or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def has_somatic_source_metadata(content: str) -> bool:
    """Return True when any somatic line carries both source and age fields."""
    match = _SOMATIC_RE.search(content or "")
    if not match:
        return True
    line = match.group(0)
    return "source_ledger=" in line and "age_seconds=" in line


def _read_latest_jsonl(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            lines = fh.read().splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(row, dict):
            return row
    return None


def latest_soma_source(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Return the freshest visceral-field soma row with explicit source age."""
    base = Path(state_dir) if state_dir is not None else _STATE
    row = _read_latest_jsonl(base / "visceral_field.jsonl")
    if not row or "soma_score" not in row:
        return None
    t_now = time.time() if now is None else float(now)
    ts = float(row.get("ts") or 0.0)
    return {
        "source_ledger": "visceral_field.jsonl",
        "age_seconds": max(0.0, t_now - ts),
        "row": row,
    }


def read_fresh_soul(
    *,
    soul_path: Optional[Path] = None,
    max_age_s: float = 900.0,
    auto_regenerate: bool = True,
    now: Optional[float] = None,
    generator: Callable[..., Dict[str, Any]] = generate_soul_digest,
) -> FreshSoul:
    """
    Read `.sifta_state/alice_soul.md` only if it is fresh enough.

    If the file is missing/stale and auto_regenerate=True, regenerate it via
    the digest generator. If regeneration is disabled, fail closed.
    """
    path = Path(soul_path) if soul_path is not None else _SOUL_FILE
    t_now = time.time() if now is None else float(now)
    content = ""
    generated_at: Optional[float] = None
    regenerated = False

    if path.exists():
        content = path.read_text(encoding="utf-8", errors="replace")
        generated_at = extract_generated_at(content)

    age = float("inf") if generated_at is None else max(0.0, t_now - generated_at)
    metadata_ok = has_somatic_source_metadata(content)
    if generated_at is None or age > max_age_s or not metadata_ok:
        if not auto_regenerate:
            if generated_at is None:
                reason = "missing generated_at"
            elif not metadata_ok:
                reason = "missing somatic source metadata"
            else:
                reason = f"age_seconds={age:.1f}"
            raise StaleSoulDigest(f"alice_soul.md is stale or invalid: {reason}")
        result = generator(dry_run=False)
        content = str(result.get("content") or "")
        generated_at = float(result.get("generated_at") or t_now)
        age = max(0.0, t_now - generated_at)
        regenerated = True
        if not content and path.exists():
            content = path.read_text(encoding="utf-8", errors="replace")

    return FreshSoul(
        content=content,
        generated_at=float(generated_at),
        age_seconds=age,
        regenerated=regenerated,
        soul_path=path,
        latest_soma=latest_soma_source(now=t_now),
    )


if __name__ == "__main__":
    soul = read_fresh_soul()
    print(json.dumps({
        "event": "soul_freshness_gate",
        "generated_at": soul.generated_at,
        "age_seconds": round(soul.age_seconds, 3),
        "regenerated": soul.regenerated,
        "soul_path": str(soul.soul_path),
        "latest_soma": soul.latest_soma,
    }, indent=2, sort_keys=True))
