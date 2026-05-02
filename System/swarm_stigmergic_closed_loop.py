#!/usr/bin/env python3
"""Event 98c: receipt-backed stigmergic closed-loop heal conductor.

This module composes already-shipped organs into one explicit proof cycle:

body_brain_tick -> visual phenotype ledger -> synthetic audiogram PCM ->
feature-only cochlea -> acoustic overlay -> superior colliculus salience ->
body_brain_memory.jsonl.

It does not open microphones, cameras, sockets, or GPU contexts. The acoustic
buffer is generated from the phenotype ledger and is never stored as raw audio;
only bounded cochlea features are appended.

Truth label: STIGMERGIC_CLOSED_LOOP_HEAL. This is a synthetic phenotype feedback
receipt, not a claim of biological hearing or conscious experience.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked
from System.swarm_stigmergic_audiogram import ledger_tail_pcm
from System.swarm_stigmergic_cochlea import TRUTH_SYNTHETIC, analyze_and_write
from System.swarm_stigmergic_cochlea_integrator import (
    TRUTH_OVERLAY,
    body_brain_memory_path,
    cochlea_ledger_path,
    integrate_acoustic_features,
    validate_body_brain_tick,
)
from System.swarm_superior_colliculus_integrator import (
    TRUTH_MULTISENSORY,
    append_integrated_tick,
    integrate_to_body_brain,
    phenotype_ledger_path,
)
from System.swarm_visual_phenotype_bridge import build_visual_phenotype_uniforms


_REPO = Path(__file__).resolve().parent.parent

TRUTH_LABEL = "STIGMERGIC_CLOSED_LOOP_HEAL"
EVENT_NAME = "stigmergic_closed_loop_heal"
STATUS_HEALED = "HEALED"
STATUS_SKIPPED = "SKIPPED"


def _state_root() -> Path:
    try:
        import System.swarm_body_brain_loop as _bbl

        root = getattr(_bbl, "_STATE_DIR", None)
        if root is not None:
            return Path(root).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def closed_loop_receipt_path(state_root: Optional[Path] = None) -> Path:
    return (state_root or _state_root()) / "stigmergic_closed_loop_heal.jsonl"


def _read_latest_jsonl_object(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for line in reversed([ln.strip() for ln in lines if ln.strip()]):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _validate_closed_loop_tick(mem_row: Dict[str, Any]) -> None:
    validate_body_brain_tick(mem_row)
    if "td_value" not in mem_row:
        raise ValueError("closed-loop heal requires td_value for a receipt-backed phenotype")


def heal_closed_loop(
    mem_row: Dict[str, Any],
    *,
    state_root: Optional[Path] = None,
    phenotype_path: Optional[Path] = None,
    cochlea_ledger: Optional[Path] = None,
    memory_path: Optional[Path] = None,
    receipt_path: Optional[Path] = None,
    sample_rate: int = 16_000,
    duration_s: float = 0.06,
    phase0: float = 0.0,
    append_memory: bool = True,
) -> Dict[str, Any]:
    """Run one closed-loop heal pass over a validated body-brain tick.

    Returns a dict with ``row`` (final body-brain row), ``receipt`` (audit row),
    ``uniforms`` (visual phenotype row), and ``cochlea`` (feature-only row).
    """
    _validate_closed_loop_tick(mem_row)
    root = Path(state_root).resolve() if state_root is not None else _state_root()
    phen_path = Path(phenotype_path) if phenotype_path is not None else phenotype_ledger_path(root)
    coch_path = Path(cochlea_ledger) if cochlea_ledger is not None else cochlea_ledger_path(root)
    mem_path = Path(memory_path) if memory_path is not None else body_brain_memory_path(root)
    rec_path = Path(receipt_path) if receipt_path is not None else closed_loop_receipt_path(root)

    base_row = dict(mem_row)
    base_td = _finite_float(base_row.get("td_value"), 0.0)

    uniforms = build_visual_phenotype_uniforms(base_row)
    _append_jsonl(phen_path, uniforms)

    pcm, frame = ledger_tail_pcm(
        phen_path,
        sample_rate=sample_rate,
        duration_s=duration_s,
        phase0=phase0,
    )
    cochlea_row = analyze_and_write(
        pcm,
        sample_rate=sample_rate,
        tick_id=str(base_row.get("tick_id") or ""),
        source="phenotype_ledger_tail_pcm",
        truth_label=TRUTH_SYNTHETIC,
        ledger_path=coch_path,
    )

    acoustic_row = integrate_acoustic_features(
        base_row,
        cochlea_ledger=coch_path,
        state_root=root,
    )
    final_row = integrate_to_body_brain(
        acoustic_row,
        phenotype_path=phen_path,
        cochlea_ledger=coch_path,
        state_root=root,
    )
    final_td = _finite_float(final_row.get("td_value"), base_td)

    final_row["closed_loop_heal_applied"] = bool(final_row.get("multisensory_integrated"))
    final_row["closed_loop_truth_label"] = TRUTH_LABEL
    final_row["truth_label"] = TRUTH_LABEL
    final_row["colliculus_truth_label"] = TRUTH_MULTISENSORY
    final_row["acoustic_truth_label"] = TRUTH_OVERLAY
    final_row["phenotype_truth_label"] = str(frame.truth_label)
    final_row["closed_loop_td_delta"] = round(final_td - base_td, 6)
    final_row["closed_loop_source"] = "phenotype_ledger_tail_pcm"
    final_row["raw_audio_logged"] = False

    status = STATUS_HEALED if final_row["closed_loop_heal_applied"] else STATUS_SKIPPED
    receipt = {
        "event": EVENT_NAME,
        "truth_label": TRUTH_LABEL,
        "status": status,
        "ts": time.time(),
        "tick_id": str(base_row.get("tick_id") or ""),
        "visual_tick_id": str(frame.tick_id or ""),
        "cochlea_tick_id": str(cochlea_row.get("tick_id") or ""),
        "base_td_value": round(base_td, 6),
        "final_td_value": round(final_td, 6),
        "td_delta": round(final_td - base_td, 6),
        "visual_receipt_backed": bool(frame.receipt_backed and final_row.get("visual_receipt_backed")),
        "cochlea_receipt_backed": bool(final_row.get("cochlea_receipt_backed")),
        "multisensory_integrated": bool(final_row.get("multisensory_integrated")),
        "collicular_salience": _finite_float(final_row.get("collicular_salience"), 0.0),
        "cochlea_acoustic_stress": _finite_float(cochlea_row.get("acoustic_stress"), 0.0),
        "sample_rate": int(sample_rate),
        "duration_s": round(float(duration_s), 6),
        "n_samples": int(getattr(pcm, "shape", [0])[0]),
        "phenotype_path": str(phen_path),
        "cochlea_path": str(coch_path),
        "memory_path": str(mem_path),
        "raw_audio_logged": False,
    }

    if append_memory:
        append_integrated_tick(final_row, memory_path=mem_path, state_root=root)
    _append_jsonl(rec_path, receipt)

    return {
        "row": final_row,
        "receipt": receipt,
        "uniforms": uniforms,
        "cochlea": cochlea_row,
    }


def heal_latest_closed_loop(
    *,
    state_root: Optional[Path] = None,
    memory_path: Optional[Path] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Read the latest body-brain tick and run ``heal_closed_loop`` on it."""
    root = Path(state_root).resolve() if state_root is not None else _state_root()
    mem_path = Path(memory_path) if memory_path is not None else body_brain_memory_path(root)
    latest = _read_latest_jsonl_object(mem_path)
    if not latest:
        raise ValueError(f"no body-brain tick found at {mem_path}")
    return heal_closed_loop(latest, state_root=root, memory_path=mem_path, **kwargs)


class StigmergicClosedLoopHealer:
    heal_closed_loop = staticmethod(heal_closed_loop)
    heal_latest_closed_loop = staticmethod(heal_latest_closed_loop)
    closed_loop_receipt_path = staticmethod(closed_loop_receipt_path)


__all__ = [
    "EVENT_NAME",
    "STATUS_HEALED",
    "STATUS_SKIPPED",
    "TRUTH_LABEL",
    "StigmergicClosedLoopHealer",
    "closed_loop_receipt_path",
    "heal_closed_loop",
    "heal_latest_closed_loop",
]
