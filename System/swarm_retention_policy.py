#!/usr/bin/env python3
"""Retention classes for SIFTA ledgers.

This is an archival hygiene layer, not cognition. It prevents high-volume
field telemetry from being treated like legal/financial/identity receipts, and
prevents protected receipts from being silently evicted by future compaction.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

RETENTION_EPHEMERAL = "ephemeral"
RETENTION_OPERATIONAL = "operational"
RETENTION_COMPLIANCE = "compliance"

RETENTION_CLASSES = (
    RETENTION_EPHEMERAL,
    RETENTION_OPERATIONAL,
    RETENTION_COMPLIANCE,
)

COMPLIANCE_LEDGER_PATTERNS = (
    "stgm",
    "financial",
    "billing",
    "payment",
    "identity",
    "identity_label",
    "genesis",
    "work_receipts",
    "ide_stigmergic_trace",
    "owner_body_events",
)

EPHEMERAL_LEDGER_PATTERNS = (
    "raw_frame",
    "frame_cache",
    "visual_stigmergy",
    "pheromone",
    "snapshot_png",
)

OPERATIONAL_LEDGER_PATTERNS = (
    "organ_field_vector",
    "truth_continuity",
    "td_receipts",
    "td_q_table",
    "dopamine",
    "basal_ganglia",
    "field_homeostasis",
    "motor_pulses",
    "field_motor_effector",
    "unified_field_slo",
    "hippocampus",
    "sensor_gate",
    "motor_bus",
    "cuttlefish",
    "electric_field",
    "waggle_quorum",
)


def retention_class_for_ledger(name: str) -> str:
    """Classify a ledger path/name for future archival and compaction policy."""
    text = str(name or "").lower()
    if any(pattern in text for pattern in COMPLIANCE_LEDGER_PATTERNS):
        return RETENTION_COMPLIANCE
    if any(pattern in text for pattern in EPHEMERAL_LEDGER_PATTERNS):
        return RETENTION_EPHEMERAL
    if any(pattern in text for pattern in OPERATIONAL_LEDGER_PATTERNS):
        return RETENTION_OPERATIONAL
    return RETENTION_OPERATIONAL


def apply_retention_class(row: Mapping[str, Any], ledger_name: str) -> Dict[str, Any]:
    """Return a copy of row with an explicit retention_class if absent."""
    out = dict(row)
    value = str(out.get("retention_class") or "").strip().lower()
    if value in RETENTION_CLASSES:
        return out
    out["retention_class"] = retention_class_for_ledger(ledger_name)
    return out


def compaction_allowed(ledger_name: str) -> bool:
    """Compliance ledgers are never eligible for automatic eviction."""
    return retention_class_for_ledger(ledger_name) != RETENTION_COMPLIANCE


def policy_summary() -> Dict[str, Any]:
    return {
        "schema": "SWARM_RETENTION_POLICY_V1",
        "classes": list(RETENTION_CLASSES),
        "rule": (
            "ephemeral may be downsampled; operational may be summarized after "
            "retention windows; compliance is protected from automatic eviction"
        ),
        "compliance_patterns": list(COMPLIANCE_LEDGER_PATTERNS),
        "operational_patterns": list(OPERATIONAL_LEDGER_PATTERNS),
        "ephemeral_patterns": list(EPHEMERAL_LEDGER_PATTERNS),
    }


__all__ = [
    "RETENTION_EPHEMERAL",
    "RETENTION_OPERATIONAL",
    "RETENTION_COMPLIANCE",
    "RETENTION_CLASSES",
    "retention_class_for_ledger",
    "apply_retention_class",
    "compaction_allowed",
    "policy_summary",
]
