#!/usr/bin/env python3
"""Post-turn self-correction — lightweight mistake detection after each Talk turn.

r1331: Closes the gap between "Alice made a mistake" and "spinal cord picks up the signal."
Fires after each complete turn (brain done + TTS done). Writes body signals to the
spinal cord's input ledger so the next spinal_cord_cycle() picks them up automatically.

Does NOT dispatch MiMo directly — that's the spinal cord's job. This organ only
detects and records. Fast, lightweight, no network calls.

Truth label: POST_TURN_CORRECTION_V1
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "POST_TURN_CORRECTION_V1"
SCHEMA = "POST_TURN_CORRECTION_SIGNAL_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SIGNALS_LEDGER = "self_eval_swimmer_dispatch.jsonl"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append_signal(
    *,
    source: str,
    severity: str,
    summary: str,
    target_files: Optional[list[str]] = None,
    suggested_fix: str = "",
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Write a body signal to the spinal cord's input ledger."""
    sd = state_dir or _state_dir()
    signal = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "signal_id": str(uuid.uuid4()),
        "ts": time.time(),
        "source": source,
        "severity": severity,
        "summary": summary[:500],
        "target_files": target_files or [],
        "suggested_fix": suggested_fix,
    }
    path = sd / _SIGNALS_LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(signal, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return signal


def check_provider_mismatch(
    *,
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Check if the last search had a provider mismatch (owner said Google, opened DDG)."""
    sd = _state_dir(state_dir)
    ledger = sd / "search_provider_reality.jsonl"
    if not ledger.exists():
        return None
    try:
        lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("provider_mismatch"):
                age_s = time.time() - float(row.get("ts", 0))
                if age_s < 300:
                    return _append_signal(
                        source="post_turn_provider_mismatch",
                        severity="yellow",
                        summary=(
                            f"Provider mismatch: owner said {row.get('requested_brand_or_verb')}, "
                            f"Alice opened {row.get('execution_provider')}. "
                            f"URL: {row.get('execution_url', '')[:200]}"
                        ),
                        target_files=[
                            "Applications/sifta_talk_to_alice_widget.py",
                            "System/swarm_search_provider_reality.py",
                        ],
                        suggested_fix="Honest provider reply already wired; verify cortex uses it.",
                        state_dir=sd,
                    )
            break
    except Exception:
        pass
    return None


def check_action_prediction_mistake(
    *,
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Check if the last action prediction was a MISTAKE."""
    sd = _state_dir(state_dir)
    ledger = sd / "action_prediction.jsonl"
    if not ledger.exists():
        return None
    try:
        lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("outcome") == "MISTAKE":
                age_s = time.time() - float(row.get("ts", 0))
                if age_s < 300:
                    return _append_signal(
                        source="post_turn_action_mistake",
                        severity="yellow",
                        summary=(
                            f"Action prediction MISTAKE: predicted {row.get('expected', '')[:200]}, "
                            f"actual {row.get('actual', '')[:200]}"
                        ),
                        target_files=[
                            "Applications/sifta_talk_to_alice_widget.py",
                            "System/swarm_action_prediction.py",
                        ],
                        suggested_fix="Review the predict→observe path for this action type.",
                        state_dir=sd,
                    )
            break
    except Exception:
        pass
    return None


def check_owner_correction(
    *,
    state_dir: Optional[Path | str] = None,
    owner_text: str = "",
) -> Optional[dict[str, Any]]:
    """Detect owner correction keywords in the latest turn."""
    sd = _state_dir(state_dir)
    text = (owner_text or "").lower()
    correction_keywords = ("wrong", "fix this", "bug", "broken", "incorrect", "that's not right", "try again")
    if not any(kw in text for kw in correction_keywords):
        return None
    return _append_signal(
        source="post_turn_owner_correction",
        severity="yellow",
        summary=f"Owner correction detected: {owner_text[:300]}",
        target_files=[],
        suggested_fix="Route through spinal_cord_cycle for MiMo patch.",
        state_dir=sd,
    )


def run_post_turn_correction(
    *,
    owner_text: str = "",
    assistant_text: str = "",
    state_dir: Optional[Path | str] = None,
    turn_source: str = "talk_post_turn",
    tts_ok: Optional[bool] = None,
    tts_error: str = "",
) -> dict[str, Any]:
    """Run all post-turn checks and write body signals. Lightweight — no network calls.

    Returns a summary of signals written.
    """
    sd = _state_dir(state_dir)
    signals_written: list[dict[str, Any]] = []
    body_execution: Optional[dict[str, Any]] = None

    try:
        from System.swarm_body_turn_execution import record_body_turn_execution

        body_execution = record_body_turn_execution(
            owner_text=owner_text,
            assistant_text=assistant_text,
            state_dir=sd,
            turn_source=turn_source,
            tts_ok=tts_ok,
            tts_error=tts_error,
        )
    except Exception:
        body_execution = None

    s = check_provider_mismatch(state_dir=sd)
    if s:
        signals_written.append(s)

    s = check_action_prediction_mistake(state_dir=sd)
    if s:
        signals_written.append(s)

    s = check_owner_correction(state_dir=sd, owner_text=owner_text)
    if s:
        signals_written.append(s)

    return {
        "schema": TRUTH_LABEL,
        "ts": time.time(),
        "body_execution_written": bool(body_execution),
        "body_execution": body_execution,
        "signals_written": len(signals_written),
        "signals": signals_written,
    }


__all__ = [
    "TRUTH_LABEL",
    "run_post_turn_correction",
    "check_provider_mismatch",
    "check_action_prediction_mistake",
    "check_owner_correction",
]
