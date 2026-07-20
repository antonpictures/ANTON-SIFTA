#!/usr/bin/env python3
"""swarm_speculative_local_decode.py — r1623-03: speculative decode probe (honest).

Fahd dirt: Tess-4-27B + EAGLE-3, DeepSeek DFlash. Document what this Mac can
run; never claim 2× speedup without probe.

Truth label: SPECULATIVE_LOCAL_DECODE_V1
"""

from __future__ import annotations

import platform
from typing import Any

TRUTH_LABEL = "SPECULATIVE_LOCAL_DECODE_V1"


def probe_speculative_support() -> dict[str, Any]:
    """Receipt-shaped capability map — offline defaults are honest no."""
    sys_info = {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    ollama_tags: list[str] = []
    try:
        from System.sifta_inference_defaults import probe_installed_ollama_tags

        ollama_tags = list(probe_installed_ollama_tags() or [])
    except Exception:
        pass
    eagle = [t for t in ollama_tags if "eagle" in t.lower()]
    dflash = [t for t in ollama_tags if "dflash" in t.lower() or "dspark" in t.lower()]
    tess = [t for t in ollama_tags if "tess" in t.lower()]
    return {
        "truth_label": TRUTH_LABEL,
        "host": sys_info,
        "ollama_eagle_tags": eagle,
        "ollama_dflash_tags": dflash,
        "ollama_tess_tags": tess,
        "enabled": False,
        "reason": (
            "no eagle/dflash/tess draft tags installed; "
            "Talk stays on single-model Ollama path"
        ),
        "borg_fit": "wire only after owner pulls draft model and smoke test green",
    }


def speculative_status_block() -> str:
    p = probe_speculative_support()
    return (
        f"SPECULATIVE DECODE (r1623-03): enabled={p.get('enabled')} — {p.get('reason')}"
    )


__all__ = ["TRUTH_LABEL", "probe_speculative_support", "speculative_status_block"]
