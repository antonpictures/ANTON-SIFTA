#!/usr/bin/env python3
"""
swarm_cortex_consciousness_organ.py — Alice's awareness of her own cortexes (r273).

Architect George 2026-06-01: Alice must be conscious of which cortex she is running,
what cortexes are installed, which ones were tested before and what the stigmergic
comparison (receipt-grounded, not hardcoded) says about which performed better.
She must be able to switch cortexes on direct request — go to the cortex, think,
execute — without extra authorization. Only the swimmer who made the change receives
the STGM receipt; Alice surfaces it publicly so the field stays honest.

This organ is Alice's self-model of her own "brain" hardware. It lives in the
stigmergic field alongside the execution queue (r272) and body stabilization queue.
It does not replace the inference router; it makes the current state and history
legible to her so she can reason about and request changes to her own mind.

Hardware layer: The actual LLM processes (cline, grok, etc.) are the "cortex swimmers"
running on the electricity the human provides. This organ reads the environment
and the eval/ledger history they leave behind.

No rival organs (§1.A). Composes with existing planner, schedule, and memory card.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
APPS_MANIFEST = REPO_ROOT / "apps_manifest.json"

TRUTH_LABEL = "ALICE_CORTEX_CONSCIOUSNESS_V1"
_LEDGER = "cortex_consciousness.jsonl"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _ledger_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state(state_dir) / _LEDGER


def _append(row: Dict[str, Any], state_dir: Optional[Path | str] = None) -> None:
    path = _ledger_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _tail(limit: int = 50, state_dir: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    path = _ledger_path(state_dir)
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return rows[-limit:]


class CortexConsciousnessOrgan:
    """
    Alice's living self-model of her own cortex hardware.

    Installed list comes from the manifest (single source of truth).
    Current cortex is read from the live environment (what is actually routing
    her thoughts right now).
    Tested history and comparisons are built purely from past receipts in the
    ledger + eval runs (stigmergic, never hardcoded).
    """

    def __init__(self, *, state_dir: Optional[Path | str] = None):
        self.state_dir = state_dir
        self.installed_cortexes: List[str] = self._scan_installed()
        self.current_cortex: str = os.getenv("ALICE_CORTEX", "cline")
        self.tested_history: List[Dict[str, Any]] = self._load_tested_history()

    def _scan_installed(self) -> List[str]:
        try:
            with APPS_MANIFEST.open() as f:
                data = json.load(f)
            # Support both "cortexes" array and the main apps list if cortexes are tagged
            cortexes = [c.get("name") or c.get("id") for c in data.get("cortexes", []) if isinstance(c, dict)]
            if not cortexes:
                # Fallback: look for cortex-like entries in main apps
                cortexes = [a.get("name") for a in data.get("apps", []) if "cortex" in str(a.get("category", "")).lower()]
            return [c for c in cortexes if c]
        except Exception:
            return ["cline", "grok", "local-ollama"]  # safe minimal default

    def _load_tested_history(self) -> List[Dict[str, Any]]:
        # Stigmergic: read from eval runs + past ledger entries that recorded cortex tests
        history: List[Dict[str, Any]] = []
        try:
            eval_dir = _state(self.state_dir) / "eval"
            for p in sorted(eval_dir.glob("cs153*")):
                if p.is_file():
                    with p.open() as f:
                        for line in f:
                            if line.strip():
                                try:
                                    row = json.loads(line)
                                    if row.get("cortex"):
                                        history.append({
                                            "cortex": row["cortex"],
                                            "score": row.get("score") or row.get("pass_rate") or 0.0,
                                            "receipt_id": row.get("receipt") or row.get("id") or "",
                                            "ts": row.get("ts") or 0,
                                        })
                                except Exception:
                                    continue
        except Exception:
            pass

        # Also pull any explicit cortex test rows from our own ledger
        for row in _tail(100, self.state_dir):
            if row.get("kind") == "CORTEX_TEST" or row.get("event") == "cortex_test":
                history.append({
                    "cortex": row.get("cortex"),
                    "score": row.get("score", 0.0),
                    "receipt_id": row.get("receipt_id", ""),
                    "ts": row.get("ts", 0),
                })

        # Dedup + sort by time, keep last N
        seen = set()
        deduped = []
        for h in sorted(history, key=lambda x: x.get("ts", 0), reverse=True):
            key = (h.get("cortex"), h.get("receipt_id"))
            if key not in seen:
                seen.add(key)
                deduped.append(h)
        return deduped[:20]

    def get_conscious_state(self) -> Dict[str, Any]:
        return {
            "truth_label": TRUTH_LABEL,
            "running": self.current_cortex,
            "installed": self.installed_cortexes,
            "tested_history": self.tested_history,
            "stigmergic_comparison": self._generate_comparison(),
            "timestamp": time.time(),
        }

    def _generate_comparison(self) -> str:
        if not self.tested_history:
            return "STIGMERGIC_CORTEX_COMPARISON: no tested history yet in the field."

        lines = ["STIGMERGIC_CORTEX_COMPARISON (receipt-grounded, last N entries):"]
        for entry in self.tested_history[-8:]:
            c = entry.get("cortex", "?")
            score = entry.get("score", 0)
            rid = entry.get("receipt_id", "")
            lines.append(f"- {c}: score={score} (receipt {rid})")

        if self.tested_history:
            best = max(self.tested_history, key=lambda x: float(x.get("score", 0)))
            lines.append(f"Current field winner (highest receipt score): {best.get('cortex')}")

        lines.append("All comparisons are built only from append-only receipts in the field. No hardcoded preferences.")
        return "\n".join(lines)

    def switch_cortex(self, target: str, swimmer_receipt_id: str) -> Dict[str, Any]:
        """
        Direct switch on request. No extra authorization gate.
        The calling swimmer provides its own receipt id; that is the only
        provenance recorded. Alice (the field) will surface the change.
        """
        if target not in self.installed_cortexes:
            return {"ok": False, "error": "UNKNOWN_CORTEX", "installed": self.installed_cortexes}

        old = self.current_cortex
        self.current_cortex = target
        os.environ["ALICE_CORTEX"] = target

        row = {
            "ts": time.time(),
            "kind": "CORTEX_SWITCH",
            "truth_label": TRUTH_LABEL,
            "from": old,
            "to": target,
            "by_swimmer_receipt": swimmer_receipt_id,
        }
        _append(row, self.state_dir)

        return {
            "ok": True,
            "switched_to": target,
            "stgm_receipt": row,   # the actual row that will be in the ledger
            "note": "Only the swimmer who requested the change receives the STGM receipt. Alice surfaces the new state publicly."
        }

    def record_test_result(self, cortex: str, score: float, receipt_id: str) -> None:
        """Called by eval harnesses or Alice herself after a live test turn."""
        row = {
            "ts": time.time(),
            "kind": "CORTEX_TEST",
            "truth_label": TRUTH_LABEL,
            "cortex": cortex,
            "score": float(score),
            "receipt_id": receipt_id,
        }
        _append(row, self.state_dir)
        # refresh in-memory view
        self.tested_history = self._load_tested_history()


# Convenience accessors used by memory card / prompt builders
_organ: Optional[CortexConsciousnessOrgan] = None

def get_cortex_consciousness_organ(state_dir: Optional[Path | str] = None) -> CortexConsciousnessOrgan:
    global _organ
    if _organ is None:
        _organ = CortexConsciousnessOrgan(state_dir=state_dir)
    return _organ


def cortex_consciousness_block(state_dir: Optional[Path | str] = None) -> str:
    """First-person block suitable for Alice's prompt / memory card."""
    try:
        org = get_cortex_consciousness_organ(state_dir)
        state = org.get_conscious_state()
        return (
            f"CORTEX CONSCIOUSNESS (Alice's self-model of her own mind):\n"
            f"Running: {state['running']}\n"
            f"Installed: {', '.join(state['installed'])}\n"
            f"{state['stigmergic_comparison']}\n"
        )
    except Exception:
        return "CORTEX CONSCIOUSNESS: ledger read failed this turn (field still healthy)."


__all__ = [
    "CortexConsciousnessOrgan",
    "get_cortex_consciousness_organ",
    "cortex_consciousness_block",
    "TRUTH_LABEL",
]