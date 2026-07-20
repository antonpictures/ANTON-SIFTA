#!/usr/bin/env python3
"""swarm_sie_embedding_bridge.py — r1622-01: Superlinked SIE probe (honest).

Dirt: github.com/superlinked/sie — encode / score / extract on :8080.
This module never pretends the container is installed. Probe only; wire later
when probe returns ok.

Truth label: SIE_EMBEDDING_BRIDGE_V1
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "sie_embedding_probe.jsonl"

TRUTH_LABEL = "SIE_EMBEDDING_BRIDGE_V1"
DEFAULT_BASE = "http://127.0.0.1:8080"
GITHUB = "https://github.com/superlinked/sie"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / _LEDGER
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def probe_sie(
    *,
    base_url: str = DEFAULT_BASE,
    timeout_s: float = 1.5,
    state_dir: Optional[Path | str] = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """HTTP probe. ok=False is the honest default when Docker/SIE is not up."""
    base = str(base_url or DEFAULT_BASE).rstrip("/")
    row: dict[str, Any] = {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "base_url": base,
        "github": GITHUB,
        "ok": False,
        "status_code": None,
        "error": "",
        "note": "SIE not claimed installed — probe only",
    }
    try:
        req = urllib.request.Request(base + "/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = (resp.read() or b"")[:500]
            row["status_code"] = int(getattr(resp, "status", 200) or 200)
            row["ok"] = 200 <= row["status_code"] < 300
            row["body_preview"] = body.decode("utf-8", errors="replace")[:200]
    except urllib.error.HTTPError as exc:
        # Some builds have no /health — try root.
        row["status_code"] = int(exc.code)
        row["error"] = f"HTTPError:{exc.code}"
        try:
            req2 = urllib.request.Request(base + "/", method="GET")
            with urllib.request.urlopen(req2, timeout=timeout_s) as resp2:
                row["status_code"] = int(getattr(resp2, "status", 200) or 200)
                row["ok"] = 200 <= row["status_code"] < 300
                row["error"] = ""
                row["note"] = "root reachable; /health missing"
        except Exception as exc2:
            row["error"] = f"{row['error']}; root:{type(exc2).__name__}"
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["ok"] = False
    if write_receipt:
        try:
            _append(row, state_dir=state_dir)
        except Exception:
            pass
    return row


def sie_status_block(*, state_dir: Optional[Path | str] = None) -> str:
    """Short owner/cortex note — never claims live SIE without probe ok."""
    p = probe_sie(state_dir=state_dir, write_receipt=False, timeout_s=0.6)
    if p.get("ok"):
        return (
            f"SIE local bridge: REACHABLE at {p.get('base_url')} "
            f"(encode/score/extract). github={GITHUB}"
        )
    return (
        f"SIE local bridge: NOT RUNNING ({p.get('error') or 'no response'}). "
        f"Install later via Docker from {GITHUB}. "
        "Memory still uses ledgers + human anchors; do not invent vector recall."
    )


def encode_texts(texts: list[str], **_kwargs: Any) -> dict[str, Any]:
    """Placeholder until SIE is up — honest refuse."""
    return {
        "ok": False,
        "reason": "sie_not_connected",
        "n": len(texts or []),
        "hint": "Run Docker SIE then re-probe; do not fake embeddings.",
    }


__all__ = [
    "TRUTH_LABEL",
    "DEFAULT_BASE",
    "GITHUB",
    "probe_sie",
    "sie_status_block",
    "encode_texts",
]
