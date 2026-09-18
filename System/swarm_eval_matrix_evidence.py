"""Eval matrix panel evidence pointers — real paths only (r1021 C7).
Lane contract: trace (zero-surprise).
"""
from __future__ import annotations

import math
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
_HUMAN_SUFFIX_RE = re.compile(r"\.(human|owner|george)\b", re.IGNORECASE)


# The world-to-field request must reuse existing observation, phone, memory and
# self-evaluation lanes. These rows are the single crosswalk used by the live
# matrix and We Code Together; they are not a second consciousness registry.
_WORLD_TO_FIELD_AUDIT_ROWS: tuple[dict[str, Any], ...] = (
    {
        "id": "SUFL-01",
        "family": "observation_envelope",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": (
            "System/swarm_observation_fusion.py; "
            "System/swarm_phone_observations.py; tests/test_phone_telemetry_envelope.py"
        ),
        "acceptance": "One versioned envelope preserves source, timestamp, modality and confidence without flattening evidence.",
    },
    {
        "id": "SUFL-02",
        "family": "cross_modal_timestamp_package",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": (
            "System/swarm_phone_observations.py; System/swarm_observation_fusion.py; "
            "tests/test_phone_observation_summary.py"
        ),
        "acceptance": "Camera, audio and telemetry link only when device/session, time window and coordinate frame agree.",
    },
    {
        "id": "SUFL-03",
        "family": "idempotent_capture_and_memory_promotion",
        "status": "COVERED",
        "wiring": "wired",
        "evidence": (
            "System/swarm_phone_observations.py; System/swarm_web_global_chat_gate.py; "
            "tests/test_phone_observation_summary.py"
        ),
        "acceptance": "A repeated capture ID produces one accepted observation and one bounded promotion.",
    },
    {
        "id": "SUFL-04",
        "family": "owner_correction_supersession",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": (
            "System/swarm_cortex_context_manager.py; System/swarm_post_turn_correction.py; "
            "tests/test_post_turn_correction_r1331.py; "
            "System/swarm_observation_fusion.py:project_field_assertions; "
            "tests/test_field_assertion_projection.py; "
            "System/swarm_phone_observations.py:phone_field_projection; "
            "tests/test_phone_field_projection.py"
        ),
        "acceptance": "Evidence revision and phone commit projection tested; authenticated correction adapters and live context wiring remain open. Retain original evidence and competing corrections.",
    },
    {
        "id": "SUFL-05",
        "family": "unknown_sensor_and_coordinate_honesty",
        "status": "COVERED",
        "wiring": "wired",
        "evidence": (
            "System/swarm_web_global_chat_gate.py; System/swarm_sensor_truth_context.py; "
            "tests/test_phone_observation_summary.py; tests/test_swarm_sensor_truth_context.py"
        ),
        "acceptance": "Missing GPS, pose, camera, audio or speaker identity stays unknown; no guessed presence is emitted.",
    },
    {
        "id": "SUFL-06",
        "family": "multi_device_session_isolation",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": (
            "System/swarm_phone_observations.py; System/swarm_web_global_chat_gate.py; "
            "tests/test_phone_observation_summary.py"
        ),
        "acceptance": "Two devices cannot silently merge observations; physical two-device acceptance remains open.",
    },
    {
        "id": "SUFL-07",
        "family": "semantic_world_map_index",
        "status": "OPEN",
        "wiring": "open",
        "evidence": "Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md; System/swarm_observation_fusion.py",
        "acceptance": "Index owner, device, place, object, action and time-window nodes with explicit relation edges.",
    },
    {
        "id": "SUFL-09",
        "family": "speech_language_voice_routing",
        "status": "COVERED",
        "wiring": "wired",
        "evidence": (
            "System/swarm_speech_language.py; System/swarm_web_global_chat_speech_worker.py; "
            "Applications/sifta_talk_to_alice_widget.py; System/swarm_broca_wernicke.py; "
            "tests/test_speech_language.py; tests/test_romanian_tts_routing.py"
        ),
        "acceptance": (
            "Every TTS mouth resolves one language-matched installed voice: Romanian text routes to an "
            "installed ro_RO voice (locale family match, not an exact remembered name), English keeps the "
            "owner's chosen voice, and a missing voice degrades to the default instead of silence."
        ),
    },
    {
        "id": "SUFL-08",
        "family": "field_slice_prompt_context",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": (
            "System/swarm_web_global_chat_gate.py; System/swarm_memory_card.py; "
            "tests/test_phone_observation_summary.py"
        ),
        "acceptance": "Alice receives recent changes, linked evidence, contradictions and missing sensors as a bounded context slice.",
    },
    {
        "id": "OBSERVER-LOOP-01",
        "family": "observer_observed_delayed_evidence",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": "System/swarm_active_inference_world_model.py:evaluate_delayed_prediction; tests/test_delayed_prediction_evidence.py",
        "acceptance": "Operational owner definition of qualia: identified observer, observed event, comparison and revision. Delayed evaluator tested; authenticated live forecast/observation pairing and hierarchical coverage remain pending.",
    },
    {
        "id": "PATCH-ORACLE-01",
        "family": "patch_independent_measurement",
        "status": "PARTIAL",
        "wiring": "partial",
        "evidence": "System/swarm_spinal_cord.py:gate_and_apply; tests/test_spinal_measurement_oracle.py",
        "acceptance": "Empty/skipped suites cannot pass; finite independent before/after metric required for KEPT. Production metric-probe registration and evaluator isolation remain pending.",
    },
    {
        "id": "BOUNDARY-QUALIA-01",
        "family": "qualia_claim_boundary",
        "category": "claim_boundary",
        "status": "BOUNDARY_ONLY",
        "wiring": "wired",
        "evidence": (
            "System/swarm_alice_self_eval_loop.py; "
            "Documents/IDE_BOOT_COVENANT.md; Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md"
        ),
        "acceptance": "Owner-defined operational qualia is tracked by OBSERVER-LOOP-01. Its measured coverage does not establish subjective experience or universal consciousness.",
    },
    {
        "id": "BOUNDARY-CONSCIOUSNESS-01",
        "family": "consciousness_claim_boundary",
        "category": "claim_boundary",
        "status": "BOUNDARY_ONLY",
        "wiring": "wired",
        "evidence": (
            "System/swarm_alice_self_eval_loop.py; "
            "Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-24.md; "
            "Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md"
        ),
        "acceptance": "Operational observer/observed loops may be tested; AGI or consciousness completion is never a green result.",
    },
)


def world_to_field_audit_rows() -> List[Dict[str, Any]]:
    """Return the one SUFL/WCT crosswalk without creating a rival matrix."""
    return [dict(row) for row in _WORLD_TO_FIELD_AUDIT_ROWS]


def validate_world_to_field_audit() -> Dict[str, Any]:
    """Check IDs, families and the deliberate open/boundary split."""
    rows = world_to_field_audit_rows()
    ids = [str(row.get("id") or "") for row in rows]
    families = [str(row.get("family") or "") for row in rows]
    duplicate_ids = sorted({value for value in ids if value and ids.count(value) > 1})
    duplicate_families = sorted({value for value in families if value and families.count(value) > 1})
    open_rows = [row["id"] for row in rows if row.get("wiring") == "open"]
    boundary_rows = [row["id"] for row in rows if row.get("category") == "claim_boundary"]
    invalid_boundary_status = [
        row["id"] for row in rows
        if row.get("category") == "claim_boundary" and row.get("status") != "BOUNDARY_ONLY"
    ]
    return {
        "ok": not duplicate_ids and not duplicate_families and not invalid_boundary_status,
        "rows": rows,
        "duplicate_ids": duplicate_ids,
        "duplicate_families": duplicate_families,
        "open_rows": open_rows,
        "boundary_rows": boundary_rows,
        "invalid_boundary_status": invalid_boundary_status,
        "note": "Open implementation rows and claim-boundary rows are intentional; neither is a completion claim.",
    }


def _resolve(path_str: str, *, repo_root: Path | None = None) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (repo_root or _REPO) / path_str
    return p


def panel_evidence_rows() -> List[Dict[str, Any]]:
    """Canonical evidence map for matrix panels."""
    return [
        {"panel": "living_substrate_loc", "path": "System/swarm_code_body_inventory.py", "ledger": ".sifta_state/canonical_organ_registry_snapshot.json"},
        {"panel": "appearance_walk", "path": ".sifta_state/eval/code_body_appearance_order.jsonl", "ledger": ".sifta_state/eval/code_body_appearance_order.jsonl"},
        {"panel": "organ_field", "path": "System/swarm_canonical_organ_registry.py", "ledger": ".sifta_state/organ_field.jsonl"},
        {"panel": "self_improvement", "path": "System/swarm_self_improvement_loop.py", "ledger": ".sifta_state/self_improvement_proposals.jsonl"},
        {
            "panel": "persistent_endogenous_motivation",
            "path": "System/swarm_drive_economy.py",
            "ledger": ".sifta_state/eval/motivational_control_evidence.jsonl",
        },
        {
            "panel": "lived_experience_bridge",
            "path": "System/swarm_lived_experience_bridge.py",
            "ledger": ".sifta_state/lived_experience_events.jsonl",
        },
        {"panel": "spinal_cord", "path": "System/swarm_spinal_cord.py", "ledger": ".sifta_state/spinal_cord_cycles.jsonl"},
        {"panel": "cortex_switch_truth", "path": "System/swarm_cortex_switch_intent.py", "ledger": ".sifta_state/cortex_selection_receipts.jsonl"},
        {"panel": "effector_gate", "path": "System/swarm_effector_gate.py", "ledger": ".sifta_state/effector_gate.jsonl"},
        {"panel": "intent_nonce", "path": "System/swarm_intent_nonce_gate.py", "ledger": ".sifta_state/intent_nonce_gate.jsonl"},
        {
            "panel": "shadow_swimmer_quarantine",
            "path": "System/swarm_ide_trace_quarantine.py",
            "ledger": ".sifta_state/ide_stigmergic_trace.jsonl",
            "quarantine_ledger": ".sifta_state/ide_stigmergic_trace_quarantine.jsonl",
            "mana_is_crypto": False,
            "stgm_is_crypto": True,
        },
        {"panel": "matrix_html", "path": "tools/generate_organ_eval_matrix_v2.py", "ledger": ".sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html"},
        {"panel": "census_delta", "path": "System/swarm_census_delta.py", "ledger": ".sifta_state/eval/code_body_census_delta.jsonl"},
    ]


def _path_age_s(path: Path, *, now: float | None = None) -> float | None:
    try:
        return max(0.0, float(now if now is not None else time.time()) - path.stat().st_mtime)
    except OSError:
        return None


# r1744 cut #1 from WCT r1743 §2 (the jewel-beetle failure). Hoffman's male
# beetle mates with a beer bottle because "dimpled, glossy, brown" was the only
# icon it ever had. This scorer had the same shape of bug: it asked whether a
# ledger FILE exists and how fresh its mtime is, never whether the ledger holds
# a single row. An empty-but-freshly-touched ledger scored green while proving
# nothing — .sifta_state/reply_language_mismatch.jsonl is exactly that today:
# 0 bytes, mtime hours old. Existence is the icon; rows are the evidence.
def ledger_evidence_rows(path: Path, *, activation_id: str | None = None) -> int | None:
    """Count the rows of evidence a ledger actually holds.
    If activation_id is provided, only count rows matching that epoch.
    """
    try:
        if not path.is_file():
            return None
        size = path.stat().st_size
    except OSError:
        return None
    if size == 0:
        return 0
    if path.suffix.lower() != ".jsonl":
        return 0 if activation_id else 1

    rows = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                if activation_id:
                    try:
                        data = json.loads(line)
                        if isinstance(data, dict) and data.get("activation_id") == activation_id:
                            rows += 1
                    except json.JSONDecodeError:
                        continue
                else:
                    rows += 1
    except OSError:
        return None
    return rows


def evidence_score_for_row(
    row: Dict[str, Any],
    *,
    repo_root: str | Path | None = None,
    now: float | None = None,
    half_life_s: float = 7 * 24 * 3600.0,
    activation_id: str | None = None,
) -> Dict[str, Any]:
    """Score one eval cell from concrete evidence, never prose alone."""
    root = Path(repo_root) if repo_root is not None else _REPO
    panel = str(row.get("panel") or "")
    path = str(row.get("path") or "")
    ledger = str(row.get("ledger") or "")
    evidence_path = ledger or path
    problems: List[str] = []
    if not panel:
        problems.append("missing_panel")
    if not evidence_path:
        problems.append("missing_evidence_path")
    if _HUMAN_SUFFIX_RE.search(path) or _HUMAN_SUFFIX_RE.search(ledger):
        problems.append("human_suffix_path")
    path_obj = _resolve(path, repo_root=root) if path else None
    ledger_obj = _resolve(ledger, repo_root=root) if ledger else None
    path_ok = bool(path_obj and path_obj.exists())
    ledger_ok = bool(ledger_obj and ledger_obj.exists())
    if path and not path_ok:
        problems.append("missing_path")
    if ledger and not ledger_ok:
        problems.append("missing_ledger")
    if not ledger:
        problems.append("missing_named_receipt_or_ledger")

    # An existing ledger with zero rows is a bottle, not a female beetle.
    evidence_rows = ledger_evidence_rows(ledger_obj, activation_id=activation_id) if ledger_ok else None
    if ledger_ok and evidence_rows == 0:
        problems.append("no_evidence_for_activation" if activation_id else "empty_ledger")

    age_s = _path_age_s(ledger_obj or path_obj, now=now) if (ledger_ok or path_ok) else None
    decay = 1.0
    if age_s is not None and half_life_s > 0:
        decay = math.pow(0.5, age_s / float(half_life_s))
    base_score = 0.0
    if path_ok:
        base_score += 0.35
    if ledger_ok:
        base_score += 0.65
    if not ledger_ok:
        base_score = min(base_score, 0.35)
    # A ledger that holds nothing cannot carry its 0.65 — the cell falls back to
    # what the code path alone proves, which is never enough to be green.
    if evidence_rows == 0:
        base_score = min(base_score, 0.35)
    score = round(max(0.0, min(1.0, base_score * decay)), 4)
    status = "red"
    if not problems and score >= 0.75:
        status = "green"
    elif score > 0.0 and "missing_evidence_path" not in problems:
        status = "yellow"
    return {
        "panel": panel,
        "score": score,
        "status": status,
        "path_ok": path_ok,
        "ledger_ok": ledger_ok,
        "evidence_rows": evidence_rows,
        "activation_id": activation_id,
        "age_s": None if age_s is None else round(age_s, 3),
        "decay": round(decay, 4),
        "problems": problems,
    }


def score_panel_evidence_rows(
    rows: List[Dict[str, Any]] | None = None,
    *,
    repo_root: str | Path | None = None,
    now: float | None = None,
    half_life_s: float = 7 * 24 * 3600.0,
    activation_id: str | None = None,
) -> Dict[str, Any]:
    scored = [
        evidence_score_for_row(
            row,
            repo_root=repo_root,
            now=now,
            half_life_s=half_life_s,
            activation_id=activation_id,
        )
        for row in (rows if rows is not None else panel_evidence_rows())
    ]
    green = sum(1 for row in scored if row["status"] == "green")
    return {
        "ok": green == len(scored) and bool(scored),
        "green_count": green,
        "total": len(scored),
        "activation_id": activation_id,
        "rows": scored,
    }


def validate_panel_evidence(
    *,
    repo_root: str | Path | None = None,
    activation_id: str | None = None,
) -> Dict[str, Any]:
    rows = panel_evidence_rows()
    problems: List[Dict[str, Any]] = []
    ok_count = 0
    for row in rows:
        path = str(row.get("path") or "")
        ledger = str(row.get("ledger") or "")
        if _HUMAN_SUFFIX_RE.search(path) or _HUMAN_SUFFIX_RE.search(ledger):
            problems.append({"panel": row["panel"], "reason": "human_suffix_path", "path": path})
            continue
        path_ok = _resolve(path, repo_root=Path(repo_root) if repo_root is not None else None).exists()
        ledger_ok = _resolve(ledger, repo_root=Path(repo_root) if repo_root is not None else None).exists()
        if not path_ok:
            problems.append({"panel": row["panel"], "reason": "missing_path", "path": path})
        elif not ledger_ok:
            problems.append({"panel": row["panel"], "reason": "missing_ledger", "ledger": ledger})
        else:
            ok_count += 1
    scored = score_panel_evidence_rows(
        rows,
        repo_root=repo_root,
        activation_id=activation_id,
    )
    return {
        "ok": not problems and scored["ok"],
        "ok_count": ok_count,
        "green_count": scored["green_count"],
        "total": len(rows),
        "activation_id": activation_id,
        "problems": problems,
        "scores": scored["rows"],
    }
