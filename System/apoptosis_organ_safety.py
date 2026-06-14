"""Organ-level apoptosis safety — census tags must not kill live imports (r1018)."""
from __future__ import annotations

from typing import Iterable, Set


def should_refuse_organ_apoptosis(
    *,
    tagged_apoptosis_candidate: bool,
    is_imported_live: bool,
) -> bool:
    """Census may tag orphans; a module still imported by live tissue stays alive."""
    return bool(tagged_apoptosis_candidate and is_imported_live)


def refuse_apoptosis_targets(
    candidates: Iterable[str],
    live_imports: Set[str],
) -> Set[str]:
    """Return module paths that may proceed to apoptosis (not refused)."""
    live = {str(m).replace("\\", "/") for m in live_imports}
    refused: Set[str] = set()
    allowed: Set[str] = set()
    for raw in candidates:
        norm = str(raw).replace("\\", "/")
        if should_refuse_organ_apoptosis(
            tagged_apoptosis_candidate=True,
            is_imported_live=norm in live,
        ):
            refused.add(norm)
        else:
            allowed.add(norm)
    return allowed