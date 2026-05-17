#!/usr/bin/env python3
"""
System/swarm_skill_ingest.py
============================
Remote skill ingestion + Hermes format conversion + marketplace + life-context scoring.

Thin layer that uses the mature swarm_skill_library.py for the heavy lifting.
All actions are fully receipted.

Exposes the high-level functions Codex implemented for the router and UI.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import swarm_skill_library as lib

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_RECEIPTS = _STATE / "skill_ingest.jsonl"


def _log_receipt(row: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    row["ts"] = time.time()
    with _RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def fetch_skill_from_url(url: str, **kwargs) -> Dict[str, Any]:
    """HTTPS-only fetch with size cap and receipt."""
    result = lib.fetch_and_convert_skill_from_url(url, **kwargs)
    _log_receipt({
        "action": "fetch_skill_from_url",
        "url": url,
        "result": result.get("status"),
    })
    return result


def evaluate_skill_with_alice(skill_content: str, life_context: Optional[str] = None) -> Dict[str, Any]:
    """LLM-driven LIKE/SKIP evaluation using current life context."""
    if life_context is None:
        life_context = lib.current_life_context()
    fit = lib.skill_life_fit(skill_content, life_context=life_context)
    return {
        "score": fit.get("score", 0.0),
        "overlap": fit.get("overlap", []),
        "recommendation": "LIKE" if fit.get("score", 0) > 0.4 else "SKIP",
        "life_context_used": life_context[:500],
    }


def install_skill(source: str | Path, **kwargs) -> Dict[str, Any]:
    result = lib.install_skill(source, **kwargs)
    _log_receipt({"action": "install_skill", "source": str(source), "result": result})
    return result


def ingest_skill(**params) -> Dict[str, Any]:
    """Main high-level entry point for remote/marketplace ingestion."""
    url = params.get("url")
    if url:
        return fetch_skill_from_url(url, auto_install=params.get("auto_install", False))
    # fallback to local path or manifest
    return {"status": "NOT_IMPLEMENTED_YET", "params": params}
