#!/usr/bin/env python3
"""swarm_cortex_selection_receipt.py — pre-dispatch cortex honesty receipt. r948.

Codex r947 found the trust break: George selects Claude/Fable, sends a turn
that needs vision, and `_talk_ollama_model_candidates` silently puts the local
Gemma VLM first in the worker ladder. The pill says one cortex; the worker
runs another. Nobody lied on purpose — vision turns prefer local pixels — but
the divergence was invisible, and invisible divergence breaks trust in WHO is
thinking.

This organ writes ONE row before every Talk brain dispatch:

    selected_model   — what the owner's pin/registry resolved to
    worker_first     — the first model the worker will actually try
    candidates       — the full ladder
    route_reason     — why the ladder looks like this
    mismatch         — True when selected != worker_first (the headline flag)

Ledger: .sifta_state/cortex_selection_receipts.jsonl (append-only).
The caller surfaces a visible CORTEX_SELECTION_MISMATCH line when mismatch.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
LEDGER_NAME = "cortex_selection_receipts.jsonl"
TRUTH_LABEL = "CORTEX_SELECTION_RECEIPT_V1"

USD_MODEL_NEEDLES = (
    "diffusiongemma",
    "diffusion-gemma",
    "diffusion_gemma",
)


def decode_family_for_model(model: str) -> str:
    """Classify the visible text-decode family for cortex receipts.

    DiffusionGemma uses uniform-state diffusion decoding for text. Everything
    else remains the normal autoregressive family until a model id proves
    otherwise. This is receipt labeling only; it does not install or promote a
    cortex.
    """
    low = str(model or "").strip().lower()
    if low.startswith(("diffusion:", "usd:")) or any(needle in low for needle in USD_MODEL_NEEDLES):
        return "usd"
    return "autoregressive"


def write_cortex_selection_receipt(
    selected_model: str,
    candidates: List[str],
    *,
    route_reason: str = "",
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Receipt the selected-vs-actual cortex before dispatch. Returns the row."""
    selected = str(selected_model or "").strip()
    ladder = [str(c or "").strip() for c in (candidates or []) if str(c or "").strip()]
    worker_first = ladder[0] if ladder else ""
    mismatch = bool(selected and worker_first and selected != worker_first)
    selected_decode_family = decode_family_for_model(selected)
    worker_first_decode_family = decode_family_for_model(worker_first or selected)
    row: Dict[str, Any] = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "selected_model": selected,
        "worker_first": worker_first,
        "candidates": ladder[:8],
        "route_reason": str(route_reason or ""),
        "mismatch": mismatch,
        "decode_family": worker_first_decode_family,
        "selected_decode_family": selected_decode_family,
        "worker_first_decode_family": worker_first_decode_family,
        "candidate_decode_families": {
            model: decode_family_for_model(model)
            for model in ladder[:8]
        },
    }
    if mismatch:
        row["kind"] = "CORTEX_SELECTION_MISMATCH"
        row["spoken_line"] = (
            f"CORTEX_SELECTION_MISMATCH: selected={selected} but this turn runs "
            f"{worker_first} first ({row['route_reason'] or 'ladder reorder'}). "
            "The receipt names who is thinking."
        )
    try:
        sd = Path(state_dir) if state_dir else _DEFAULT_STATE
        sd.mkdir(parents=True, exist_ok=True)
        with (sd / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        row["ledger_ok"] = True
    except Exception as exc:  # honest failure, never crash the turn
        row["ledger_ok"] = False
        row["ledger_error"] = f"{type(exc).__name__}: {exc}"
    return row
