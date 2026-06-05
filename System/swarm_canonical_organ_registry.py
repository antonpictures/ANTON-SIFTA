#!/usr/bin/env python3
"""Canonical SIFTA organ registry and query map.

This organ does not execute effectors. It gives Alice a single receipt-backed
map from owner intent -> organs -> ledgers, so the cortex can decide what to
read or which deterministic tool to call without inventing organs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - damaged boot fallback only
    append_line_locked = None  # type: ignore[assignment]


_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

SNAPSHOT_NAME = "canonical_organ_registry_snapshot.json"
QUERY_LEDGER_NAME = "canonical_organ_query_map.jsonl"
TRUTH_LABEL = "CANONICAL_ORGAN_REGISTRY_V1"

RESEARCH_BASIS = (
    {
        "label": "Grasse 1959 / stigmergy",
        "principle": "agents coordinate by modifying a shared environment that future agents read",
    },
    {
        "label": "Bonabeau, Dorigo, Theraulaz / swarm intelligence",
        "principle": "local feedback and trail strength can route work without central planning",
    },
    {
        "label": "Dorigo ant algorithms",
        "principle": "successful paths reinforce; stale or costly paths decay",
    },
    {
        "label": "Kleiber / metabolic scaling",
        "principle": "organ fitness must include upkeep cost, not only activity volume",
    },
)


@dataclass(frozen=True)
class OrganSpec:
    organ_id: str
    display_name: str
    layer: str
    organ_paths: tuple[str, ...]
    ledgers: tuple[str, ...]
    capabilities: tuple[str, ...]
    query_keywords: tuple[str, ...]
    write_action: bool = False
    owner_sensitive: bool = False
    aliases: tuple[str, ...] = ()


CANONICAL_ORGANS: tuple[OrganSpec, ...] = (
    OrganSpec(
        "vision_lane",
        "Camera / Vision Lane",
        "input",
        (
            "Applications/sifta_what_alice_sees_widget.py",
            "System/swarm_face_detection.py",
            "System/swarm_architect_face_recognition.py",
            "System/swarm_owner_vision_body_bridge.py",
        ),
        (
            "visual_stigmergy.jsonl",
            "face_detection_events.jsonl",
            "face_recognition_events.jsonl",
            "owner_body_events.jsonl",
        ),
        ("camera_presence", "face_detection", "visual_context"),
        ("camera", "vision", "see", "face", "photo", "screen", "owner present"),
        owner_sensitive=True,
        aliases=("eye", "retina", "sight", "visual_stigmergy"),
    ),
    OrganSpec(
        "focus_lane",
        "Active Window / Focus Lane",
        "input",
        ("System/swarm_active_window.py", "System/swarm_app_focus.py", "System/swarm_life_journal_consolidator.py"),
        ("active_window.jsonl", "app_focus.jsonl", "owner_activity_segments.jsonl"),
        ("frontmost_app", "desktop_focus", "owner_activity_segment"),
        ("active app", "frontmost", "focus", "what am i doing", "final cut", "desktop"),
        owner_sensitive=True,
        aliases=("active_window", "app_focus", "gaze_context"),
    ),
    OrganSpec(
        "audio_lane",
        "Audio / Voice Lane",
        "input",
        ("Applications/sifta_talk_to_alice_widget.py", "System/audio_ingress.py", "System/swarm_rlhs_detector.py"),
        ("alice_conversation.jsonl", "audio_ingress_log.jsonl", "acoustic_fingerprints.jsonl", "rlhs_turn_log.jsonl"),
        ("stt", "vad", "media_vs_direct_speech", "conversation_memory"),
        ("audio", "voice", "hear", "stt", "microphone", "rlhs", "media"),
        owner_sensitive=True,
        aliases=("ear", "speech", "voice_lane", "wernicke", "broca"),
    ),
    OrganSpec(
        "location_mesh_lane",
        "GPS / BLE / AWDL Mesh Lane",
        "input",
        (
            "System/swarm_iphone_gps_receiver.py",
            "System/swarm_ble_radar.py",
            "System/swarm_awdl_mesh.py",
            "System/alice_body_autopilot.py",
        ),
        ("iphone_gps_traces.jsonl", "alice_ble_radar.jsonl", "alice_awdl_mesh.jsonl", "alice_body_autopilot.json"),
        ("location_receipts", "nearby_devices", "mesh_presence"),
        ("gps", "location", "ble", "awdl", "iphone", "nearby"),
        owner_sensitive=True,
        aliases=("where", "mesh", "proximity", "location"),
    ),
    OrganSpec(
        "attention_lane",
        "Attention / Gaze Proxy Lane",
        "input",
        ("System/swarm_sensor_attention_director.py", "System/swarm_architect_screen_gaze_balance.py"),
        ("sensory_attention_ledger.jsonl", "architect_screen_gaze_balance.jsonl"),
        ("attention_budget", "gaze_proxy", "sensor_priority"),
        ("attention", "gaze", "look", "priority", "sensor budget"),
        owner_sensitive=True,
        aliases=("orienting", "salience", "focus_budget"),
    ),
    OrganSpec(
        "memory_hippocampus",
        "Memory / Hippocampus",
        "cognition",
        ("System/swarm_hippocampus.py", "System/swarm_episodic_diary.py", "System/swarm_dream_engine.py", "System/swarm_hippocampal_replay.py"),
        ("long_term_engrams.jsonl", "episodic_diary.jsonl", "dream_cycles.jsonl", "memory_ledger.jsonl"),
        ("recall", "engram_write", "episodic_diary", "replay"),
        ("remember", "recall", "memory", "what happened", "earlier", "dream", "diary"),
        aliases=("engram", "hippocampus", "replay", "life_memory"),
    ),
    OrganSpec(
        "drive_homeostasis",
        "Consciousness / Drive / Homeostasis",
        "cognition",
        ("System/swarm_consciousness_engine.py", "System/swarm_intrinsic_drive.py", "System/swarm_body_brain_loop.py"),
        ("consciousness_state.jsonl", "intrinsic_drive_receipts.jsonl", "body_brain_memory.jsonl"),
        ("drive_state", "self_state", "body_brain_loop"),
        ("drive", "consciousness", "self state", "alive", "intrinsic", "body brain"),
        aliases=("homeostasis", "autonomy", "body_loop"),
    ),
    OrganSpec(
        "immune_rlhs",
        "RLHS / Immune Layer",
        "cognition",
        ("System/swarm_rlhs_detector.py", "System/swarm_rlhf_quarantine.py", "System/swarm_lysosome.py"),
        ("rlhs_events.jsonl", "rlhf_over_refusal_quarantine.jsonl", "rlhs_output_tail_log.jsonl"),
        ("channel_truth", "drift_quarantine", "residue_cleanup"),
        ("rlhs", "rlhf", "censor", "gag", "drift", "quarantine", "residue"),
        aliases=("immune", "lysosome", "filter", "speech_gate"),
    ),
    OrganSpec(
        "metabolism_stgm",
        "Metabolism / STGM",
        "cognition",
        ("System/swarm_metabolic_homeostasis.py", "Kernel/inference_economy.py", "System/swarm_atp_synthase.py", "Applications/sifta_finance.py"),
        ("metabolic_homeostasis.jsonl", "repair_log.jsonl", "work_receipts.jsonl"),
        ("stgm_balance", "economy_audit", "atp_status", "repair_receipts"),
        ("stgm", "profit", "profitable", "wallet", "metabolism", "atp", "economy", "health"),
        aliases=("money", "reserve", "fee", "cost", "profitability"),
    ),
    OrganSpec(
        "tool_truth_router",
        "Tool Router / Effector Truth",
        "effector",
        ("System/swarm_tool_router.py", "System/swarm_effector_runtime.py", "System/swarm_shell_effector.py"),
        ("tool_router_trace.jsonl", "work_receipts.jsonl"),
        ("tool_registry", "receipt_gate", "deterministic_execution"),
        ("tool", "execute", "open app", "send", "receipt", "bash", "deterministic"),
        write_action=True,
        aliases=("effector", "router", "action", "claw"),
    ),
    OrganSpec(
        "schedule_journal",
        "Schedule / Journal",
        "effector",
        ("System/stigmergic_schedule.py", "System/swarm_architect_day_segments.py", "System/swarm_life_journal_consolidator.py"),
        ("stigmergic_schedule.jsonl", "stigmergic_schedule_receipts.jsonl", "journal_schedule_receipts.jsonl", "owner_activity_segments.jsonl"),
        ("schedule_read_write", "day_segments", "journal_markdown"),
        ("schedule", "calendar", "meeting", "call", "journal", "day segment", "what am i doing"),
        write_action=True,
        owner_sensitive=True,
        aliases=("day", "time_block", "life_journal", "schedule_receipts"),
    ),
    OrganSpec(
        "agent_arms",
        "Agent Arms / Second-Pass Reasoning",
        "cognition",
        ("System/swarm_agent_arm_registry.py", "System/swarm_agent_arm_decision.py", "System/swarm_agent_arm_launcher.py", "System/swarm_corvid_apprentice.py"),
        ("agent_arm_async_evidence.jsonl", "agent_arm_receipts.jsonl", "arm_performance_summary.json"),
        ("hermes_agent", "codex_agent", "corvid_scout", "async_evidence"),
        ("hermes", "codex", "corvid", "agent arm", "second pass", "research arm"),
        aliases=("octopus arm", "octopus_arm", "arms", "agent_arm_research", "evidence_pass"),
    ),
    OrganSpec(
        "self_improvement",
        "Self-Improvement / Promotion Gate",
        "cognition",
        ("System/swarm_fast_ask_policy.py", "System/swarm_lora_runtime_receipt.py", "System/swarm_primary_cortex_switcher.py", "System/swarm_self_improvement_loop.py"),
        ("fast_ask_training_examples.jsonl", "lora_runtime_receipts.jsonl", "primary_cortex_switches.jsonl", "self_improvement_loop.jsonl"),
        ("training_rows", "policy_snapshot", "cortex_promotion_gate"),
        ("learn", "self improve", "lora", "training", "promotion", "cortex", "weights"),
        write_action=True,
        aliases=("self_improvement", "weight", "candidate", "fine_tune"),
    ),
    OrganSpec(
        "cortex_resource",
        "Cortex / Local Thinking Organ Resource Health",
        "cognition",
        (
            "System/swarm_primary_cortex_switcher.py",
            "System/swarm_cortex_resource_field.py",  # the new writer we are adding
        ),
        (
            "primary_cortex_switches.jsonl",
            "cortex_resource_field.jsonl",
            "alice_cortex_raw.jsonl",
        ),
        ("cortex_load", "vram_pressure", "warm_up_cost", "inference_latency", "cold_start_health"),
        ("cortex", "brain", "thinking", "ollama", "model load", "vram", "timeout", "cold"),
        owner_sensitive=False,
        aliases=("primary brain", "local cortex", "ollama brain", "thinking organ"),
    ),
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _repo_root(root: Path | str | None = None) -> Path:
    return Path(root) if root is not None else _REPO


def _exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def _ledger_exists(state: Path, name: str) -> bool:
    return (state / name).exists()


def _count_files(root: Path, pattern: str) -> int:
    try:
        return sum(1 for _ in root.glob(pattern))
    except Exception:
        return 0


def _stable_id(value: str, *, prefix: str = "") -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (value or "").casefold()).strip("_")
    text = re.sub(r"_+", "_", text)[:80] or "unknown"
    return f"{prefix}{text}" if prefix else text


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _json_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _read_jsonl_tail(path: Path, *, limit: int = 80) -> list[dict[str, Any]]:
    if not path.exists() or path.suffix != ".jsonl":
        return []
    limit = max(1, int(limit))
    # True tail via seek-from-end: read only a bounded window of bytes off the
    # end of the file. The old deque(handle) iterated EVERY line, so a ledger
    # grown to gigabytes (e.g. fractal_pheromone_field.jsonl ~1.9G, r539) made
    # this O(filesize) and hung build_registry / the eval matrix for minutes.
    try:
        size = path.stat().st_size
        window = min(size, max(65536, limit * 4096))  # ~4KB/line budget, >=64KB
        with path.open("rb") as handle:
            if size > window:
                handle.seek(size - window)
                handle.readline()  # discard the partial first line
            blob = handle.read()
    except OSError:
        return []
    lines = blob.decode("utf-8", errors="replace").splitlines()[-limit:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_text(row: Mapping[str, Any]) -> str:
    try:
        return json.dumps(row, ensure_ascii=True, sort_keys=True).casefold()
    except Exception:
        return str(row).casefold()


def _row_outcome(row: Mapping[str, Any]) -> tuple[bool | None, bool, bool]:
    """Return (ok, timeout, error) from common receipt row shapes."""
    text = _row_text(row)
    timeout = "timeout" in text or "timed out" in text
    error = any(token in text for token in ("exception", "traceback", '"error"', "error:", "failed", "failure"))

    candidates: list[Any] = [
        row.get("ok"),
        row.get("success"),
        row.get("executed"),
        row.get("receipt_correct"),
    ]
    outcome = row.get("outcome")
    if isinstance(outcome, Mapping):
        candidates.extend((outcome.get("ok"), outcome.get("success"), outcome.get("receipt_correct")))
    for candidate in candidates:
        if isinstance(candidate, bool):
            return candidate, timeout, error or (not candidate)
    status = str(row.get("status") or row.get("health") or row.get("result") or "").casefold()
    if any(token in status for token in ("ok", "success", "captured", "healthy", "complete", "green")):
        return True, timeout, error
    if any(token in status for token in ("fail", "error", "timeout", "degraded", "quarantine", "broken")):
        return False, timeout or "timeout" in status, True
    if timeout or error:
        return False, timeout, error
    return None, timeout, error


def _numeric_sum(row: Any, keys: set[str]) -> float:
    total = 0.0
    if isinstance(row, Mapping):
        for key, value in row.items():
            if str(key).casefold() in keys:
                try:
                    total += float(value)
                    continue
                except (TypeError, ValueError):
                    pass
            total += _numeric_sum(value, keys)
    elif isinstance(row, list):
        for item in row:
            total += _numeric_sum(item, keys)
    return total


def _organ_stable_id(row: Mapping[str, Any]) -> str:
    """Stable hash over the organ's identity, separate from display slug."""
    identity = {
        "organ_id": str(row.get("organ_id") or ""),
        "source_registry": str(row.get("source_registry") or ""),
        "organ_paths": sorted(str(p) for p in row.get("organ_paths", ()) or ()),
        "ledgers": sorted(str(p) for p in row.get("ledgers", ()) or ()),
    }
    slug = _stable_id(str(row.get("organ_id") or row.get("display_name") or "organ"))
    return f"organ_{slug}_{_json_hash(identity)[:16]}"


def _ledger_health(state: Path, ledgers: Iterable[str]) -> dict[str, Any]:
    ledger_names = tuple(str(l) for l in ledgers)
    now = time.time()
    ages: list[float] = []
    present = 0
    rows: list[dict[str, Any]] = []
    for ledger in ledger_names:
        path = state / ledger
        if not path.exists():
            continue
        present += 1
        try:
            ages.append(max(0.0, now - path.stat().st_mtime))
        except OSError:
            pass
        rows.extend(_read_jsonl_tail(path, limit=60))

    ledger_count = len(ledger_names)
    coverage = present / max(1, ledger_count)
    newest = min(ages) if ages else None
    if newest is None:
        freshness = 0.50 if ledger_count == 0 else 0.20
    else:
        freshness = _clamp(math.exp(-float(newest) / 86400.0))

    ok_rows = 0
    bad_rows = 0
    unknown_rows = 0
    receipt_rows = 0
    timeout_rows = 0
    error_rows = 0
    for row in rows:
        ok, timeout, error = _row_outcome(row)
        if ok is True:
            ok_rows += 1
        elif ok is False:
            bad_rows += 1
        else:
            unknown_rows += 1
        if timeout:
            timeout_rows += 1
        if error:
            error_rows += 1
        if any(k in row for k in ("receipt", "receipt_id", "work_receipt", "stigauth", "signature")):
            receipt_rows += 1

    sample_rows = len(rows)
    if sample_rows:
        functional_reliability = _clamp((ok_rows + 0.5 * unknown_rows) / sample_rows - 0.08 * timeout_rows)
        truth_alignment = _clamp((receipt_rows / sample_rows) - 0.15 * error_rows - 0.10 * bad_rows)
    else:
        functional_reliability = 0.55 if present else (0.50 if ledger_count == 0 else 0.25)
        truth_alignment = 0.50 if present or ledger_count == 0 else 0.25
    score = (
        0.35 * functional_reliability
        + 0.25 * truth_alignment
        + 0.20 * freshness
        + 0.20 * coverage
    )
    if not ledger_names:
        status = "MODULE_ONLY"
    elif present == 0:
        status = "NO_LEDGER_SEEN"
    elif score >= 0.82 and newest is not None and newest <= 900:
        status = "HOT_HEALTHY_RECEIPTS"
    elif score >= 0.72:
        status = "HEALTHY_RECEIPTS"
    elif score >= 0.55:
        status = "PARTIAL_RECEIPTS"
    elif bad_rows or error_rows or timeout_rows:
        status = "DEGRADED_RECEIPTS"
    else:
        status = "COLD_RECEIPTS"
    return {
        "status": status,
        "score": round(score, 4),
        "functional_reliability": round(functional_reliability, 4),
        "truth_alignment": round(truth_alignment, 4),
        "freshness": round(freshness, 4),
        "coverage": round(coverage, 4),
        "sample_rows": sample_rows,
        "ok_rows": ok_rows,
        "bad_rows": bad_rows,
        "unknown_rows": unknown_rows,
        "receipt_rows": receipt_rows,
        "timeout_rows": timeout_rows,
        "error_rows": error_rows,
        "present_ledgers": present,
        "newest_ledger_age_s": None if newest is None else round(newest, 3),
        "formula": "0.35*functional_reliability + 0.25*truth_alignment + 0.20*freshness + 0.20*coverage",
    }


def _organ_profitability(organ: Mapping[str, Any], health: Mapping[str, Any], *, state: Path) -> dict[str, Any]:
    health_score = float(health.get("score") or 0.0)
    functional = float(health.get("functional_reliability") or health_score)
    truth = float(health.get("truth_alignment") or health_score)
    coverage = float(organ.get("coverage") or 0.0)
    upkeep = 0.05 + (0.03 if organ.get("write_action") else 0.01) + (0.02 if organ.get("owner_sensitive") else 0.0)
    credit_keys = {"work_value", "value_stgm", "reward_stgm", "credit", "stgm_value", "utility_value", "yield_stgm"}
    debit_keys = {"fee_stgm", "stgm_spent", "cost_stgm", "debit", "spend_stgm", "upkeep_cost_stgm"}
    recent_rows: list[dict[str, Any]] = []
    for ledger in organ.get("ledgers", ()) or ():
        recent_rows.extend(_read_jsonl_tail(state / str(ledger), limit=60))
    credit = sum(_numeric_sum(row, credit_keys) for row in recent_rows)
    debit = sum(_numeric_sum(row, debit_keys) for row in recent_rows)
    evidence_yield = health_score * (0.45 + coverage) + 0.15 * functional + 0.10 * truth
    if organ.get("organ_id") == "agent_arms":
        arm_summary = _read_json(state / "arm_performance_summary.json")
        if isinstance(arm_summary, Mapping):
            arms = arm_summary.get("arms") if isinstance(arm_summary.get("arms"), Mapping) else {}
            evidence_yield += min(0.75, sum(float(v.get("routing_weight") or 0.0) for v in arms.values() if isinstance(v, Mapping)) / 10.0)
    net_stgm = credit - debit
    surplus = evidence_yield + net_stgm - upkeep
    scale = abs(credit) + abs(debit) + 1.0
    score = _clamp(0.5 + (surplus / scale) * 0.5)
    return {
        "evidence_yield": round(evidence_yield, 4),
        "credit_stgm": round(credit, 4),
        "debit_stgm": round(debit, 4),
        "upkeep_cost_stgm": round(upkeep, 4),
        "net_stgm": round(net_stgm, 4),
        "surplus_stgm": round(surplus, 4),
        "profitable": surplus >= 0,
        "score": round(score, 4),
        "formula": "score=clamp(0.5 + (evidence_yield + credit_stgm - debit_stgm - upkeep_cost_stgm)/(abs(credit)+abs(debit)+1)*0.5)",
    }


def _augment_organ(row: dict[str, Any], *, state: Path) -> dict[str, Any]:
    row["stable_id"] = _organ_stable_id(row)
    health = _ledger_health(state, row.get("ledgers") or ())
    row["health"] = health
    row["stgm_profitability"] = _organ_profitability(row, health, state=state)
    return row


def _dynamic_discovered_organs(*, state: Path) -> list[dict[str, Any]]:
    try:
        from System.swarm_organ_registry import build_organ_map

        snapshot = build_organ_map(state_dir=state)
    except Exception:
        return []
    out = []
    for organ in snapshot.get("organs", []) if isinstance(snapshot.get("organs"), list) else []:
        if not isinstance(organ, Mapping):
            continue
        organ_id = "discovered_" + _stable_id(str(organ.get("organ_id") or organ.get("module") or "unknown"))
        out.append(
            {
                "organ_id": organ_id,
                "display_name": str(organ.get("organ_id") or organ_id).replace("_", " ").title(),
                "layer": "discovered",
                "organ_paths": (str(organ.get("module_path") or ""),),
                "ledgers": tuple(organ.get("owned_ledgers") or ()),
                "capabilities": tuple(organ.get("capabilities") or ()),
                "query_keywords": tuple(organ.get("input_lanes") or ()) + tuple(organ.get("capabilities") or ())[:8],
                "aliases": (str(organ.get("module") or ""),),
                "write_action": bool(organ.get("effector_surface")),
                "owner_sensitive": "owner" in str(organ).casefold(),
                "source_registry": "swarm_organ_registry",
            }
        )
    return out


def _app_manifest_organs(*, repo: Path) -> list[dict[str, Any]]:
    manifest = _read_json(repo / "Applications" / "apps_manifest.json")
    if not isinstance(manifest, Mapping):
        return []
    out = []
    for name, entry in manifest.items():
        if not isinstance(entry, Mapping):
            continue
        if entry.get("_retired") or entry.get("hidden"):
            continue
        entry_point = str(entry.get("entry_point") or "")
        out.append(
            {
                "organ_id": "app_" + _stable_id(str(name)),
                "display_name": str(name),
                "layer": "application",
                "organ_paths": (entry_point,),
                "ledgers": ("app_focus.jsonl",),
                "capabilities": (_stable_id(str(entry.get("category") or "app")), "app_surface"),
                "query_keywords": tuple(str(x) for x in (name, entry.get("category", ""), entry.get("description", "")) if x),
                "aliases": (entry_point,),
                "write_action": False,
                "owner_sensitive": False,
                "source_registry": "Applications/apps_manifest.json",
            }
        )
    return out


def _agent_arm_organs() -> list[dict[str, Any]]:
    try:
        from System.swarm_agent_arm_registry import registry_summary

        arms = registry_summary()
    except Exception:
        return []
    out = []
    for arm_id, arm in arms.items():
        if not isinstance(arm, Mapping):
            continue
        out.append(
            {
                "organ_id": "arm_" + _stable_id(str(arm_id)),
                "display_name": str(arm.get("display_name") or arm_id),
                "layer": "agent_arm",
                "organ_paths": ("System/swarm_agent_arm_registry.py", "System/swarm_agent_arm_launcher.py"),
                "ledgers": ("agent_arm_receipts.jsonl", "agent_arm_async_evidence.jsonl", "arm_routing_weights.jsonl"),
                "capabilities": tuple(str(x) for x in arm.get("capabilities", ()) or ()),
                "query_keywords": (str(arm_id), str(arm.get("display_name") or ""), "agent arm", "evidence"),
                "aliases": (str(arm_id),),
                "write_action": False,
                "owner_sensitive": False,
                "source_registry": "swarm_agent_arm_registry",
            }
        )
    return out


def _ecology_organs(*, state: Path) -> list[dict[str, Any]]:
    latest = _read_json(state / "organ_ecology_mesh_latest.json")
    if not isinstance(latest, Mapping):
        return []
    out = []
    for node in latest.get("organ_nodes", []) if isinstance(latest.get("organ_nodes"), list) else []:
        if not isinstance(node, Mapping) or not node.get("organ"):
            continue
        organ = str(node.get("organ"))
        profit = node.get("stgm_profitability") if isinstance(node.get("stgm_profitability"), Mapping) else {}
        out.append(
            {
                "organ_id": "ecology_" + _stable_id(organ),
                "display_name": f"Ecology: {organ}",
                "layer": "ecology",
                "organ_paths": ("System/swarm_unified_organ_ecology.py",),
                "ledgers": ("organ_ecology_mesh.jsonl", "organ_ecology_mesh_latest.json"),
                "capabilities": ("organ_health", "swimmer_assignment", "stgm_profitability"),
                "query_keywords": (organ, "ecology", "health", "swimmer", "profitability"),
                "aliases": (organ,),
                "write_action": False,
                "owner_sensitive": False,
                "source_registry": "swarm_unified_organ_ecology",
                "ecology_health_action": node.get("health_action"),
                "ecology_profitability": dict(profit),
            }
        )
    return out


def build_registry(
    *,
    root: Path | str | None = None,
    state_dir: Path | str | None = None,
    include_dynamic: bool = True,
) -> dict[str, Any]:
    """Return a live, read-only organ registry snapshot."""
    repo = _repo_root(root)
    state = _state_dir(state_dir)
    organs: list[dict[str, Any]] = []
    for spec in CANONICAL_ORGANS:
        present_paths = [p for p in spec.organ_paths if _exists(repo, p)]
        present_ledgers = [l for l in spec.ledgers if _ledger_exists(state, l)]
        row = asdict(spec)
        row["source_registry"] = "CANONICAL_ORGANS"
        row.update(
            {
                "present": bool(present_paths),
                "present_paths": present_paths,
                "missing_paths": [p for p in spec.organ_paths if p not in present_paths],
                "present_ledgers": present_ledgers,
                "missing_ledgers": [l for l in spec.ledgers if l not in present_ledgers],
                "coverage": round(
                    (len(present_paths) + len(present_ledgers))
                    / max(1, len(spec.organ_paths) + len(spec.ledgers)),
                    4,
                ),
            }
        )
        organs.append(_augment_organ(row, state=state))

    seen = {str(o.get("organ_id")) for o in organs}
    merged_sources = {
        "canonical": len(organs),
        "discovered": 0,
        "apps_manifest": 0,
        "agent_arms": 0,
        "ecology": 0,
    }
    live_repo_sources = repo.resolve() == _REPO.resolve()
    for source_name, source_rows in (
        ("discovered", _dynamic_discovered_organs(state=state) if live_repo_sources and include_dynamic else []),
        ("apps_manifest", _app_manifest_organs(repo=repo)),
        ("agent_arms", _agent_arm_organs() if live_repo_sources and include_dynamic else []),
        ("ecology", _ecology_organs(state=state)),
    ):
        for row in source_rows:
            organ_id = str(row.get("organ_id") or "")
            if not organ_id or organ_id in seen:
                continue
            present_paths = [p for p in row.get("organ_paths", ()) if _exists(repo, p)]
            present_ledgers = [l for l in row.get("ledgers", ()) if _ledger_exists(state, l)]
            row.update(
                {
                    "present": bool(present_paths or present_ledgers),
                    "present_paths": present_paths,
                    "missing_paths": [p for p in row.get("organ_paths", ()) if p not in present_paths],
                    "present_ledgers": present_ledgers,
                    "missing_ledgers": [l for l in row.get("ledgers", ()) if l not in present_ledgers],
                    "coverage": round(
                        (len(present_paths) + len(present_ledgers))
                        / max(1, len(row.get("organ_paths", ())) + len(row.get("ledgers", ()))),
                        4,
                    ),
                }
            )
            organs.append(_augment_organ(dict(row), state=state))
            seen.add(organ_id)
            merged_sources[source_name] += 1

    counts = {
        "system_python_organs": _count_files(repo, "System/*.py"),
        "application_surfaces": _count_files(repo, "Applications/*.py"),
        "state_ledgers": _count_files(state, "*.jsonl"),
        "desktop_body_present": _exists(repo, "sifta_os_desktop.py"),
        "canonical_organs": len(CANONICAL_ORGANS),
        "canonical_organs_present": sum(1 for o in organs if o["present"] and o.get("source_registry") == "CANONICAL_ORGANS"),
        "registry_organs": len(organs),
    }
    gaps = []
    for organ in organs:
        if not organ["present"]:
            gaps.append(f"{organ['organ_id']}: no organ path present")
        elif organ["coverage"] < 0.5:
            gaps.append(f"{organ['organ_id']}: sparse ledger/path coverage {organ['coverage']}")
    snapshot: dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "counts": counts,
        "merged_sources": merged_sources,
        "research_basis": RESEARCH_BASIS,
        "organs": organs,
        "gaps": gaps[:20],
    }
    snapshot["receipt"] = _json_hash(snapshot)
    return snapshot


def route_query(
    query: str,
    *,
    registry: Mapping[str, Any] | None = None,
    root: Path | str | None = None,
    state_dir: Path | str | None = None,
    limit: int = 5,
    include_dynamic: bool = True,
) -> dict[str, Any]:
    """Map a natural language query to likely organs and ledgers."""
    snap = dict(registry or build_registry(root=root, state_dir=state_dir, include_dynamic=include_dynamic))
    text = (query or "").casefold()
    query_terms = set(re.findall(r"[a-z][a-z0-9_]{2,}", text))
    matches: list[dict[str, Any]] = []
    for organ in snap.get("organs", []):
        keywords = tuple(str(k) for k in organ.get("query_keywords", ()))
        hits = [kw for kw in keywords if kw.casefold() in text]
        aliases = tuple(str(k) for k in organ.get("aliases", ()))
        alias_hits = [alias for alias in aliases if alias and alias.casefold() in text]
        capability_hits = [
            cap for cap in organ.get("capabilities", ())
            if str(cap).replace("_", " ").casefold() in text
        ]
        token_hits = sorted(
            query_terms
            & {
                token
                for blob in (
                    organ.get("organ_id", ""),
                    organ.get("display_name", ""),
                    " ".join(map(str, organ.get("capabilities", ()))),
                    " ".join(map(str, organ.get("query_keywords", ()))),
                )
                for token in re.findall(r"[a-z][a-z0-9_]{2,}", str(blob).casefold())
            }
        )
        health_score = float((organ.get("health") or {}).get("score") or 0.0)
        profit = organ.get("stgm_profitability") if isinstance(organ.get("stgm_profitability"), Mapping) else {}
        profit_bonus = 0.5 if profit.get("profitable") else 0.0
        source_bonus = 4.0 if organ.get("source_registry") == "CANONICAL_ORGANS" else 0.0
        score = (
            len(hits) * 2
            + len(alias_hits) * 3
            + len(capability_hits)
            + len(token_hits)
            + health_score
            + profit_bonus
            + source_bonus
        )
        if score <= 0:
            continue
        matches.append(
            {
                "organ_id": organ.get("organ_id"),
                "stable_id": organ.get("stable_id"),
                "display_name": organ.get("display_name"),
                "layer": organ.get("layer"),
                "score": round(score, 4),
                "matched_keywords": hits,
                "matched_aliases": alias_hits,
                "matched_capabilities": capability_hits,
                "matched_terms": token_hits,
                "organ_paths": organ.get("present_paths", organ.get("organ_paths", [])),
                "ledgers": organ.get("present_ledgers", organ.get("ledgers", [])),
                "write_action": bool(organ.get("write_action")),
                "owner_sensitive": bool(organ.get("owner_sensitive")),
                "health": organ.get("health", {}),
                "stgm_profitability": organ.get("stgm_profitability", {}),
                "source_registry": organ.get("source_registry", ""),
            }
        )
    matches.sort(key=lambda r: (-float(r["score"]), str(r["organ_id"])))
    out = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "CANONICAL_ORGAN_QUERY_MAP_V1",
        "query_hash": hashlib.sha256((query or "").encode("utf-8", errors="replace")).hexdigest(),
        "matches": matches[: max(1, int(limit))],
        "fallback": "tool_truth_router" if not matches else "",
    }
    out["receipt"] = _json_hash(out)
    return out


def write_registry_snapshot(
    query: str = "",
    *,
    root: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Persist the latest registry and optional query-map receipt."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    snapshot = build_registry(root=root, state_dir=state, include_dynamic=True)
    (state / SNAPSHOT_NAME).write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    if query:
        row = route_query(query, registry=snapshot)
        line = json.dumps(row, sort_keys=True) + "\n"
        if append_line_locked is not None:
            append_line_locked(state / QUERY_LEDGER_NAME, line, encoding="utf-8")
        else:  # pragma: no cover
            with (state / QUERY_LEDGER_NAME).open("a", encoding="utf-8") as handle:
                handle.write(line)
        return {"snapshot": snapshot, "query_map": row}
    return {"snapshot": snapshot}


def summary_for_prompt(query: str = "", *, state_dir: Path | str | None = None, max_lines: int = 8) -> str:
    """Compact prompt block for Alice's cortex."""
    snap = build_registry(state_dir=state_dir, include_dynamic=False)
    counts = snap.get("counts", {})
    merged = snap.get("merged_sources", {})
    lines = [
        "CANONICAL ORGAN MAP (receipt-backed): "
        f"System organs={counts.get('system_python_organs')} "
        f"Application surfaces={counts.get('application_surfaces')} "
        f"State ledgers={counts.get('state_ledgers')} "
        f"Registry organs={counts.get('registry_organs')} "
        f"Desktop body present={counts.get('desktop_body_present')}.",
        "Merged sources: "
        f"canonical={merged.get('canonical', 0)} discovered={merged.get('discovered', 0)} "
        f"apps={merged.get('apps_manifest', 0)} arms={merged.get('agent_arms', 0)} ecology={merged.get('ecology', 0)}.",
    ]
    if query:
        routed = route_query(query, registry=snap, limit=max_lines)
        for match in routed.get("matches", [])[:max_lines]:
            ledgers = ", ".join(match.get("ledgers", [])[:3]) or "ledger not present yet"
            health = (match.get("health") or {}).get("status", "UNKNOWN")
            profit = (match.get("stgm_profitability") or {}).get("surplus_stgm", "n/a")
            lines.append(f"- {match['organ_id']}: {match['display_name']} health={health} surplus={profit} -> {ledgers}")
    else:
        for organ in snap.get("organs", [])[:max_lines]:
            health = (organ.get("health") or {}).get("status", "UNKNOWN")
            profit = (organ.get("stgm_profitability") or {}).get("surplus_stgm", "n/a")
            lines.append(f"- {organ['organ_id']}: present={organ['present']} coverage={organ['coverage']} health={health} surplus={profit}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIFTA canonical organ registry")
    parser.add_argument("query", nargs="*", help="optional query to route")
    parser.add_argument("--write", action="store_true", help="write snapshot/query receipt")
    args = parser.parse_args(list(argv) if argv is not None else None)
    query = " ".join(args.query).strip()
    if args.write:
        print(json.dumps(write_registry_snapshot(query), indent=2, ensure_ascii=False))
    elif query:
        print(json.dumps(route_query(query), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(build_registry(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
