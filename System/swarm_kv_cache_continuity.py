#!/usr/bin/env python3
"""swarm_kv_cache_continuity.py — r1623-04: continuity without fake vLLM KV.

Fahd dirt: vLLM + PegaFlow KV survive restarts. On this desk we may not have
vLLM. Continuity enzyme = rehydrate mind from ledgers (selection receipt,
active plan, browser URL, last self-code) after reboot — not pretend GPU KV.

Truth label: KV_CACHE_CONTINUITY_V1
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "KV_CACHE_CONTINUITY_V1"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _tail_one(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-30:]):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                return row
    except Exception:
        return {}
    return {}


def rehydrate_mind_snapshot(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Build a restart-survival 'KV substitute' from ledgers."""
    root = _state_dir(state_dir)
    cortex = _tail_one(root / "cortex_selection_receipts.jsonl")
    plan: dict[str, Any] = {}
    active = root / "alice_self_plan_active.json"
    if active.is_file():
        try:
            plan = json.loads(active.read_text(encoding="utf-8"))
        except Exception:
            plan = {}
    browser = _tail_one(root / "browser_page_state.jsonl")
    self_code = _tail_one(root / "alice_self_coding_receipts.jsonl")
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "mode": "ledger_rehydrate_not_gpu_kv",
        "cortex_pin": {
            "model": cortex.get("selected_model")
            or cortex.get("worker_first")
            or cortex.get("model")
            or "",
            "family": cortex.get("family") or "",
        },
        "active_plan": {
            "round_id": plan.get("round_id") or "",
            "title": plan.get("title") or "",
            "goal": str(plan.get("goal") or "")[:160],
        },
        "browser": {
            "url": browser.get("url") or browser.get("current_url") or "",
            "title": browser.get("title") or "",
        },
        "last_self_code": {
            "receipt_id": self_code.get("receipt_id") or "",
            "ok": self_code.get("ok"),
            "path": self_code.get("path") or "",
        },
        "vllm_pegaflow": {
            "enabled": False,
            "note": "not installed on this desk; ledgers are source of truth",
        },
    }


def continuity_prompt_block(
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 900,
) -> str:
    snap = rehydrate_mind_snapshot(state_dir=state_dir)
    c = snap.get("cortex_pin") or {}
    p = snap.get("active_plan") or {}
    b = snap.get("browser") or {}
    lines = [
        "MIND CONTINUITY (r1623-04 — ledger rehydrate, not GPU KV claim):",
        f"- cortex pin: {c.get('model') or 'unknown'}",
        f"- active self-plan: {p.get('round_id') or 'none'} {p.get('title') or ''}",
        f"- browser last: {b.get('url') or 'none'}",
        "- After restart, truth lives in ledgers under .sifta_state — do not claim "
        "vLLM KV survival unless that stack is installed and receipted.",
    ]
    block = "\n".join(lines)
    return block[:max_chars]


__all__ = [
    "TRUTH_LABEL",
    "rehydrate_mind_snapshot",
    "continuity_prompt_block",
]
