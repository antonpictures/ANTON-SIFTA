#!/usr/bin/env python3
"""
cp2f_layer.py — Concrete CP2F interface (Composer 2 Fast lane on Cursor).
══════════════════════════════════════════════════════════════════════════════

SwarmGPT (external tab) asked for a pinned definition: is CP2F a buffer, a
protocol, a curriculum, a meta-controller? **In this repo, CP2F is:**

    A thin orchestration facade for the *fast, local* substrate:
        • stigmergy deposits (`ide_stigmergic_bridge`)
        • optional SLLI fingerprints (`stigmergic_llm_identifier`)
        • metabolic accounting (`metabolic_budget`)
        • pointers to SwarmRL upstream (`Library/swarmrl/swarmrl/`)

It does **not** replace C47H (deep refactors) or AG31 (Antigravity). It does
**not** run inside ChatGPT — external models cannot flock JSONL; this class
only runs where Python + repo access exist.

Upstream SwarmRL tasks remain in `Library/swarmrl/swarmrl/tasks/`:
`searching/`, `object_movement/`, `multi_tasking.py` — future meta-controller
can import those once wired; this module is the seam.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_SWARMRL_TASKS = _REPO / "Archive" / "swarmrl_upstream" / "swarmrl" / "tasks"

MODULE_VERSION = "2026-04-18.v1"


@dataclass
class CP2FConfig:
    trigger_code: str = "CP2F"
    homeworld_serial: str = "GTH4921YP3"


class CP2FLayer:
    """
    Single entry point for Composer-class work: DYOR, traces, stigmergy,
    metabolism — all optional calls, fail-soft on missing deps.
    """

    def __init__(self, cfg: Optional[CP2FConfig] = None) -> None:
        self.cfg = cfg or CP2FConfig()

    def deposit_stigmergy(self, payload: str, *, kind: str = "cp2f") -> Dict[str, Any]:
        from System.ide_stigmergic_bridge import deposit

        return deposit(
            "cursor_m5",
            payload,
            kind=kind,
            meta={"trigger": self.cfg.trigger_code},
            homeworld_serial=self.cfg.homeworld_serial,
        )

    def record_probe(
        self,
        model_label: str,
        response_text: str,
    ) -> Dict[str, Any]:
        from System.stigmergic_llm_identifier import record_probe_response

        return record_probe_response(
            self.cfg.trigger_code,
            model_label,
            response_text,
        )

    def log_local_work(self, note: str = "") -> Dict[str, Any]:
        from System.metabolic_budget import SpendKind, spend

        return spend(
            SpendKind.LOCAL_IDE,
            note=note or "cp2f_layer",
            trigger=self.cfg.trigger_code,
        )

    def log_external_tab(self, note: str = "") -> Dict[str, Any]:
        """Architect pasted text from centralized ChatGPT — higher abstract cost."""
        from System.metabolic_budget import SpendKind, spend

        return spend(
            SpendKind.EXTERNAL_API,
            units=0.1,
            note=note or "external_chatgpt_tab",
            trigger=self.cfg.trigger_code,
        )

    @staticmethod
    def swarmrl_tasks_path() -> Path:
        return _SWARMRL_TASKS


__all__ = ["CP2FLayer", "CP2FConfig", "MODULE_VERSION"]
