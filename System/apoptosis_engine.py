#!/usr/bin/env python3
"""
apoptosis_engine.py — Vector 15: metabolic failure → controlled salvage (policy)
══════════════════════════════════════════════════════════════════════════════

**Not** a second memory API. Swimmers/orchestrators call these helpers when a
wallet is depleted under pressure: decide viability, then **optionally**
persist high-signal fragments through the **existing**
`StigmergicMemoryBus.remember(text, app_context, decay_modifier=...)`.

Important economics (ground truth):
  `remember()` still runs normal STGM minting inside the bus — salvage is not
  “free energy.” If you need zero-mint salvage, that is a **separate** signed
  ledger design, not this module.

Rejected patterns (do not reintroduce):
  - `get_memory_bus()` — does not exist.
  - `remember(memory_id=..., tags=[...])` — not the public bus API.

See: `System/stgm_metabolic.py`, `System/adaptive_constraint_memory_field.py`,
     `System/stigmergic_memory_bus.py`
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stgm_metabolic import (  # noqa: E402
    calculate_dynamic_store_fee,
    metabolic_regime_label,
)
from System.stigmergic_memory_bus import StigmergicMemoryBus  # noqa: E402


def metabolic_survival_threshold(
    lambda_norm: float,
    *,
    margin: float = 1.25,
) -> float:
    """
    Minimum STGM balance (same units as your wallet) before a caller should
    treat the swimmer as metabolically insolvent at this pressure.

    Uses dynamic store stress as the floor scale — bounded by V14 curve.
    """
    fee = calculate_dynamic_store_fee(lambda_norm)
    return max(1e-9, fee * float(margin))


def is_metabolically_viable(
    stgm_balance: float,
    lambda_norm: float,
    *,
    margin: float = 1.25,
) -> bool:
    return float(stgm_balance) >= metabolic_survival_threshold(lambda_norm, margin=margin)


def salvage_through_memory_bus(
    bus: StigmergicMemoryBus,
    swimmer_id: str,
    entries: List[Dict[str, Any]],
    *,
    lambda_norm: float = 0.0,
    fitness_floor: float = 1.15,
    decay_modifier: float = 0.35,
    max_items: int = 8,
    allow_unkeyed: bool = False,
) -> int:
    """
    Append salvaged text to the **append-only** ledger via `remember()`.

    Each `entries` item may contain:
      - `text` (required): payload to store (truncated internally by caller if needed)
      - `trace_id` (optional): if set, ACMF fitness must be >= `fitness_floor`
        to be written; if absent, the row is skipped unless `allow_unkeyed=True`.

    Returns count of successful `remember()` calls.
    """
    from System.adaptive_constraint_memory_field import (  # noqa: PLC0415
        AdaptiveConstraintMemoryField,
    )

    acmf = AdaptiveConstraintMemoryField()
    app_ctx = f"apoptosis_{swimmer_id}"
    written = 0
    regime = metabolic_regime_label(lambda_norm)

    for row in entries[: max_items * 4]:
        if written >= max_items:
            break
        text = str(row.get("text", "")).strip()
        if len(text) < 12:
            continue
        tid = row.get("trace_id")
        if tid is not None:
            if acmf.get_fitness(str(tid)) < float(fitness_floor):
                continue
        elif not allow_unkeyed:
            continue

        payload = (
            f"[APOPTOSIS | regime={regime} | λ_norm={float(lambda_norm):.2f} | "
            f"swimmer={swimmer_id} | trace_hint={tid!s}]\n{text}"
        )
        try:
            bus.remember(payload[:4000], app_context=app_ctx, decay_modifier=float(decay_modifier))
            written += 1
        except Exception:
            continue

    return written


class ApoptosisEngine:
    """
    Thin façade so orchestrators can hold one object; all methods delegate to
    module functions (easy to mock in tests).
    """

    def __init__(self, bus: StigmergicMemoryBus):
        self._bus = bus

    def check_metabolic_viability(
        self,
        swimmer_id: str,
        stgm_balance: float,
        lambda_norm: float,
        *,
        margin: float = 1.25,
    ) -> bool:
        _ = swimmer_id
        return is_metabolically_viable(stgm_balance, lambda_norm, margin=margin)

    def execute_apoptosis(
        self,
        swimmer_id: str,
        local_entries: List[Dict[str, Any]],
        lambda_norm: float,
        *,
        fitness_floor: float = 1.15,
        decay_modifier: float = 0.35,
    ) -> int:
        """Salvage then return number of ledger lines written."""
        return salvage_through_memory_bus(
            self._bus,
            swimmer_id,
            local_entries,
            lambda_norm=lambda_norm,
            fitness_floor=fitness_floor,
            decay_modifier=decay_modifier,
        )


if __name__ == "__main__":
    for lam in (0.0, 0.5, 0.95):
        print(f"λ={lam:.2f}  thresh={metabolic_survival_threshold(lam):.4f}  viable@0.04={is_metabolically_viable(0.04, lam)}")
