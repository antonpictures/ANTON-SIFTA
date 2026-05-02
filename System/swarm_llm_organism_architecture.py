#!/usr/bin/env python3
"""
System/swarm_llm_organism_architecture.py
══════════════════════════════════════════════════════════════════════════════
Event 110 — LLM-bearing organism substrate definition

Doctrine:
  SIFTA is not a new pretrained base LLM. It is a receipt-conditioned,
  body-regulated nervous system that *bears* LLMs as cortices among other
  organs. Boundaries are explicit; claims are ledger-backed.

Truth label (manifest): OBSERVED_ARCHITECTURE_NOT_BASE_MODEL

Persistence:
  Append-only `.sifta_state/llm_organism_state.jsonl` (flocked writes).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
ORGANISM_LEDGER = _STATE_DIR / "llm_organism_state.jsonl"
REGIME_FILE = _STATE_DIR / "regime_state.json"
CRYSTALLIZED_SKILLS = _STATE_DIR / "crystallized_skills.json"
IDE_TRACE = _STATE_DIR / "ide_stigmergic_trace.jsonl"

SCHEMA_VERSION = "llm_organism_architecture.event110.v1"
TRUTH_LABEL = "OBSERVED_ARCHITECTURE_NOT_BASE_MODEL"

# Organs with dedicated stigmergic / sensory ledgers or hot modules (not exhaustive).
SENSORY_ORGANS_SHIPPED: List[str] = [
    "visual_phenotype",
    "pheromone_field",
    "stigmergic_cochlea",
    "owl_spatial_hearing",
    "superior_colliculus",
    "intrinsic_drive",
    "homeostatic_stabilizer",
    "allostatic_load",
    "motor_policy",
    "stigmergic_observability",
]


def _state_dir(state_dir: Optional[Path]) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE_DIR


def get_organism_manifest() -> Dict[str, Any]:
    """Static architectural claim — safe to serialize every deposit."""
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "SIFTA_LLM_BEARING_ORGANISM",
        "version": "event110.v1",
        "truth_label": TRUTH_LABEL,
        "truth_note": (
            "Not a new pretrained base model; cortices (GPT/Claude/Gemini/local) "
            "plug into organs with append-only receipts."
        ),
        "core_principles": [
            "Append-only stigmergic memory (ide_stigmergic_trace.jsonl)",
            "Body-brain loop with metabolic, homeostatic, allostatic, and phase gates",
            "Crystallized skills feeding motor policy (temporal identity compression)",
            "Multi-sensory receipts (phenotype, cochlea, colliculus, pheromone, etc.)",
            "Multiple IDE Doctors via shared substrate (no single vendor chat thread)",
            "Truth labels + observability / crypto receipts for audit lanes",
        ],
        "llm_role": "One cortex among many organs — not the organism whole",
        "future_leap_note": (
            "Receipts + crystallized skills auto-selecting or composing adapters "
            "(LoRA / routers) is not shipped as autonomous training in Event 110."
        ),
        "forbidden_claim": "SIFTA is a new pretrained LLM (false without weights + training receipts)",
        "manifest_ts": time.time(),
    }


def deposit_organism_state(
    update: Dict[str, Any],
    *,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one organism-level manifest row merged with caller update."""
    base = get_organism_manifest()
    row = {**base, **update, "deposit_time": time.time()}
    path = _state_dir(state_dir) / ORGANISM_LEDGER.name
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    return row


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _crystallized_skill_count(state_dir: Path) -> int:
    data = _read_json(state_dir / CRYSTALLIZED_SKILLS.name)
    if not isinstance(data, dict):
        return 0
    return len(data)


def _tail_trace_rows(state_dir: Path, max_lines: int = 80) -> List[Dict[str, Any]]:
    p = state_dir / IDE_TRACE.name
    if not p.exists():
        return []
    try:
        body = read_text_locked(p, encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in body.splitlines()[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def get_current_regime_summary(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Best-effort dashboard hook: reads regime_state.json + skill DB + trace tail.
    Missing files → explicit nulls / zeros (no fake certainty).
    """
    root = _state_dir(state_dir)
    regime_data = _read_json(root / REGIME_FILE.name) or {}
    regime = regime_data.get("regime") or regime_data.get("state") or "UNKNOWN"
    density = regime_data.get("stigmergic_density")
    if density is None:
        density = 0.0
    try:
        density = float(density)
    except (TypeError, ValueError):
        density = 0.0

    n_skills = _crystallized_skill_count(root)
    trace_rows = _tail_trace_rows(root)

    auditability_score: Optional[float] = None
    audit_note = "no_trace_sample"
    if trace_rows:
        try:
            from System.swarm_stigmergic_observability import audit_trace_health

            h = audit_trace_health(trace_rows)
            auditability_score = float(h.get("attribution_confidence", 0.0))
            audit_note = str(h.get("truth_note", ""))
        except Exception:
            audit_note = "audit_import_failed"

    return {
        "truth_label": "OBSERVED_SUBSTRATE_SUMMARY",
        "regime": regime,
        "stigmergic_density": round(density, 4),
        "crystallized_skills_count": n_skills,
        "sensory_organs_manifest": list(SENSORY_ORGANS_SHIPPED),
        "ide_trace_tail_rows": len(trace_rows),
        "auditability_score": auditability_score,
        "audit_note": audit_note,
    }


__all__ = [
    "CRYSTALLIZED_SKILLS",
    "IDE_TRACE",
    "ORGANISM_LEDGER",
    "REGIME_FILE",
    "SCHEMA_VERSION",
    "SENSORY_ORGANS_SHIPPED",
    "TRUTH_LABEL",
    "deposit_organism_state",
    "get_current_regime_summary",
    "get_organism_manifest",
]
