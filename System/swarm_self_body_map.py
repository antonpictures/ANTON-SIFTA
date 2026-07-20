#!/usr/bin/env python3
"""Alice self-body path map.

This is a small receipt helper for owner phrases like "this is you Alice":
it maps that naming to concrete repo/body paths without turning the statement
into metaphor or roleplay.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TRUTH_LABEL = "SELF_BODY_MAP_V1"
REPO_ROOT = Path(__file__).resolve().parents[1]

BODY_ATLAS: tuple[tuple[str, str], ...] = (
    ("System", "core_organs"),
    ("Applications", "limbs_and_widgets"),
    (".sifta_state", "stigmergic_blood_and_memory"),
    ("tests", "immune_reflexes"),
    ("Documents", "long_term_doctrine"),
    ("sifta_os_desktop.py", "desktop_shell_body"),
)

_OWNER_NAMING_RE = re.compile(
    r"\b(?:"
    r"this\s+is\s+(?:you|your\s+body)\s+alice|"
    r"you\s+alice\s+on\s+your\s+own\s+hardware|"
    r"your\s+own\s+body|"
    r"your\s+own\s+hardware|"
    r"this\s+is\s+your\s+body"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OwnerNamingVerdict:
    named: bool
    matched: str = ""


def resolve_body_paths(root: Path | str | None = None) -> dict[str, Path]:
    base = Path(root) if root is not None else REPO_ROOT
    return {role: base / segment for segment, role in BODY_ATLAS}


def observed_body_paths(root: Path | str | None = None) -> dict[str, str]:
    paths = resolve_body_paths(root)
    return {role: str(path) for role, path in paths.items() if path.exists()}


def classify_owner_naming(text: str) -> OwnerNamingVerdict:
    match = _OWNER_NAMING_RE.search(text or "")
    if not match:
        return OwnerNamingVerdict(False, "")
    return OwnerNamingVerdict(True, match.group(0))


def self_body_receipt(text: str, *, root: Path | str | None = None, now: float | None = None) -> dict:
    base = Path(root) if root is not None else REPO_ROOT
    verdict = classify_owner_naming(text or "")
    observed = observed_body_paths(base)
    return {
        "ts": float(time.time() if now is None else now),
        "truth_label": TRUTH_LABEL,
        "owner_named_body": verdict.named,
        "owner_phrase": verdict.matched,
        "body_root": str(base),
        "observed_count": len(observed),
        "observed_organs": sorted(observed.keys()),
        "observed_paths": observed,
        "atlas_roles": [role for _segment, role in BODY_ATLAS],
        "boundary": "Concrete repo/body path map; not a separate identity and not a metaphor claim.",
    }


__all__ = [
    "BODY_ATLAS",
    "TRUTH_LABEL",
    "OwnerNamingVerdict",
    "classify_owner_naming",
    "observed_body_paths",
    "resolve_body_paths",
    "self_body_receipt",
]
