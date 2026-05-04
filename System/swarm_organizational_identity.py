"""
Organizational Persistence & Identity Layer (Priority #1)

An auditable organizational identity substrate that maintains continuity across power cycles,
long gaps, genome updates, and component turnover. Implements the identity ledger and
rehydration semantics.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kw: Any) -> str:
        return path.read_text(**kw) if path.exists() else ""

    def append_line_locked(path: Path, line: str, **kw: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root: Optional[Path] = None) -> Path:
        return Path(root) if root else Path(".sifta_state")

from System.swarm_hardware_identity_anchor import compute_identity_anchor as compute_hardware_anchor
from System.swarm_regulatory_genome import load_regulatory_parameters

LOG_NAME = "identity_continuity.jsonl"
LONG_GAP_THRESHOLD_TICKS = 86400  # assuming ~1 tick per sec, 1 day


def get_identity_ledger_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def compute_identity_anchor(root: Optional[Path] = None) -> str:
    """
    Returns a stable cryptographic identity anchor.
    Reuses hardware_identity_anchor.py for physical + self-model lineage.
    """
    # Fetch from the hardware anchor logic
    hw_anchor_data = compute_hardware_anchor(root=root, write_ledger=False)
    anchor = hw_anchor_data.get("identity_anchor", "unknown_anchor")
    return anchor


def ensure_identity_anchor_logged(root: Optional[Path] = None, *, current_tick: Optional[int] = None) -> str:
    path = get_identity_ledger_path(root)
    anchor = compute_identity_anchor(root)
    has_anchor = False
    if path.exists():
        for line in read_text_locked(path, encoding="utf-8").splitlines():
            if not line.strip(): continue
            try:
                row = json.loads(line)
                if row.get("kind") == "IDENTITY_ANCHOR":
                    has_anchor = True
                    break
            except Exception:
                pass
    
    if not has_anchor:
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "IDENTITY_ANCHOR",
            "kind": "IDENTITY_ANCHOR",
            "identity_anchor": anchor,
            "personality_vector": snapshot_personality(root),
            "continuity": {
                "last_seen_tick": current_tick,
            },
            "event": {
                "type": "INITIALIZATION",
                "details": {"message": "Identity anchor established for hardware lineage."}
            }
        }
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
        
    return anchor


def _last_identity_row(root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = get_identity_ledger_path(root)
    if not path.exists():
        return None
    for line in reversed(read_text_locked(path, encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _all_identity_rows(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = get_identity_ledger_path(root)
    if not path.exists():
        return []
    rows = []
    for line in read_text_locked(path, encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def snapshot_personality(root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Captures the current active regulatory parameters + recent regime history.
    """
    params = load_regulatory_parameters(root)

    from System.swarm_regulatory_genome import get_latest_genome_hash
    genome_row_hash = get_latest_genome_hash(root)

    recent_regimes = []
    chronic_dam2_streak = 0
    try:
        mc_path = state_dir(root) / "metacognitive_state.jsonl"
        if mc_path.exists():
            mc_lines = read_text_locked(mc_path, encoding="utf-8").splitlines()
            for line in reversed(mc_lines[-30:]):
                if not line.strip(): continue
                try:
                    r = json.loads(line)
                    recent_regimes.append(r.get("metacog_regime", "UNKNOWN"))
                    if int(r.get("dam_stage", 0)) >= 2:
                        chronic_dam2_streak += 1
                except Exception:
                    continue
    except Exception:
        pass

    return {
        "genome_row_hash": genome_row_hash,
        "metacog_evidence_threshold": params.get("metacog_evidence_threshold", 0.5),
        "arbiter_risk_weight": params.get("arbiter_risk_weight", 1.0),
        "arbiter_exploration_temperature": params.get("arbiter_exploration_temperature", 1.0),
        "causal_prober_uncertainty_threshold": params.get("causal_prober_uncertainty_threshold", 0.5),
        "microglia_priming_half_life_hours": params.get("microglia_priming_half_life_hours", 48.0),
        "recent_regimes": recent_regimes[:5],
        "chronic_dam2_streak": chronic_dam2_streak
    }


def detect_genome_drift(previous: Dict[str, Any], current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Detects if the personality vector has shifted significantly.
    Significant drift creates a CONTINUITY_EVENT.
    """
    deltas = {}
    total_delta = 0.0
    keys_to_check = [
        "metacog_evidence_threshold", "arbiter_risk_weight", 
        "arbiter_exploration_temperature", "causal_prober_uncertainty_threshold",
        "microglia_priming_half_life_hours"
    ]
    for k in keys_to_check:
        prev_val = float(previous.get(k, 0.0))
        cur_val = float(current.get(k, 0.0))
        if k == "microglia_priming_half_life_hours":
            delta = abs(cur_val - prev_val) / 48.0
        else:
            delta = abs(cur_val - prev_val)
        deltas[k] = delta
        total_delta += delta

    if total_delta > 0.4:
        return {
            "type": "GENOME_DRIFT",
            "details": {
                "total_delta": total_delta,
                "deltas": deltas,
                "previous_hash": previous.get("genome_row_hash"),
                "current_hash": current.get("genome_row_hash")
            }
        }
    return None


def build_current_internal_state_vector(root: Optional[Path] = None) -> Dict[str, float]:
    """Collects the 8 fields from relevant organs / ledgers."""
    vec: Dict[str, float] = {
        "avg_prediction_error_50": 0.5,
        "dam_stage": 0.0,
        "chronic_dam2_streak": 0.0,
        "genome_drift_magnitude": 0.0,
        "na_level": 0.5,
        "valence": 0.0,
        "pruning_pressure": 0.0,
        "ledger_pressure": 0.0
    }
    try:
        mc_path = state_dir(root) / "metacognitive_state.jsonl"
        if mc_path.exists():
            lines = read_text_locked(mc_path, encoding="utf-8").splitlines()
            valid_rows = []
            for l in reversed(lines[-50:]):
                if l.strip():
                    try:
                        valid_rows.append(json.loads(l))
                    except Exception:
                        pass
            if valid_rows:
                recent = valid_rows[0]
                vec["dam_stage"] = float(recent.get("dam_stage", 0))
                vec["na_level"] = float(recent.get("na_level", 0.5))
                vec["valence"] = float(recent.get("valence", 0.0))
                
                streak = 0
                for r in valid_rows:
                    if int(r.get("dam_stage", 0)) >= 2:
                        streak += 1
                    else:
                        break
                vec["chronic_dam2_streak"] = float(streak)
    except Exception:
        pass
        
    try:
        from System.swarm_regulatory_genome import load_regulatory_parameters, default_regulatory_parameters
        params = load_regulatory_parameters(root)
        defaults = default_regulatory_parameters()
        total_drift = 0.0
        keys = ["metacog_evidence_threshold", "arbiter_risk_weight"]
        for k in keys:
            total_drift += abs(params.get(k, defaults[k]) - defaults[k])
        vec["genome_drift_magnitude"] = min(1.0, total_drift)
    except Exception:
        pass
        
    try:
        log_size = (state_dir(root) / "metacognitive_state.jsonl").stat().st_size
        vec["ledger_pressure"] = min(1.0, log_size / (10 * 1024 * 1024))
    except Exception:
        pass

    return vec


def snapshot_proto_self(root: Optional[Path] = None, tick_id: Optional[int] = None) -> None:
    """Builds vector + writes PROTO_SELF_SNAPSHOT row."""
    vec = build_current_internal_state_vector(root)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "PROTO_SELF_SNAPSHOT",
        "kind": "PROTO_SELF_SNAPSHOT",
        "tick_id": tick_id,
        "internal_state_vector": vec,
        "source": "body_brain_tick",
        "version": 1
    }
    append_line_locked(
        get_identity_ledger_path(root),
        json.dumps(row, sort_keys=True) + "\n",
        encoding="utf-8"
    )


def load_latest_proto_self_vector(root: Optional[Path] = None) -> Optional[Dict[str, float]]:
    """Returns the internal_state_vector from the most recent PROTO_SELF_SNAPSHOT."""
    for row in reversed(_all_identity_rows(root)):
        if row.get("kind") == "PROTO_SELF_SNAPSHOT":
            return row.get("internal_state_vector")
    return None


def _cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Simple cosine similarity over the shared keys of two state vectors."""
    keys = set(v1.keys()) & set(v2.keys())
    if not keys:
        return 0.5
    dot = sum(v1[k] * v2[k] for k in keys)
    norm1 = math.sqrt(sum(v1[k]**2 for k in keys))
    norm2 = math.sqrt(sum(v2[k]**2 for k in keys))
    if norm1 == 0 or norm2 == 0:
        return 0.5
    return dot / (norm1 * norm2)


def compute_revival_score(
    last_seen_tick: int, 
    current_tick: int,
    personality_delta: float,
    recent_boots: int,
    current_internal_state: Optional[Dict[str, float]] = None,
    last_proto_self_vector: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate scalar [0,1] indicating how 'alive / continuous' the organism feels on boot.
    revival_score = clamp(0.0, 1.0, base_continuity - gap_penalty - personality_penalty + boot_bonus - proto_self_penalty)
    """
    gap_ticks = max(0, current_tick - last_seen_tick)
    base_continuity = 1.0
    gap_penalty = (gap_ticks / LONG_GAP_THRESHOLD_TICKS) * 0.4
    personality_penalty = abs(personality_delta) * 0.3
    boot_bonus = recent_boots * 0.1

    if current_internal_state and last_proto_self_vector:
        proto_self_alignment = _cosine_similarity(current_internal_state, last_proto_self_vector)
    else:
        proto_self_alignment = 0.75
        
    proto_self_penalty = (1.0 - proto_self_alignment) * 0.22

    score = base_continuity - gap_penalty - personality_penalty + boot_bonus - proto_self_penalty
    return max(0.10, min(0.98, score))


def record_continuity_event(
    event_type: str, 
    details: Dict[str, Any], 
    root: Optional[Path] = None,
    *,
    current_tick: Optional[int] = None
) -> None:
    anchor = ensure_identity_anchor_logged(root, current_tick=current_tick)
    personality = snapshot_personality(root)
    
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": f"IDENTITY_{event_type}",
        "kind": "CONTINUITY_EVENT",
        "identity_anchor": anchor,
        "personality_vector": personality,
        "continuity": {
            "last_seen_tick": current_tick,
        },
        "event": {
            "type": event_type,
            "details": details
        }
    }
    append_line_locked(
        get_identity_ledger_path(root),
        json.dumps(row, sort_keys=True) + "\n",
        encoding="utf-8"
    )


def rehydrate_identity(
    root: Optional[Path] = None, 
    *, 
    current_tick: Optional[int] = None
) -> Dict[str, Any]:
    """
    Called early in body_brain_tick / boot sequence.
    """
    current_tick = current_tick or int(time.time())
    anchor = ensure_identity_anchor_logged(root, current_tick=current_tick)
    current_personality = snapshot_personality(root)
    
    last_row = _last_identity_row(root)
    last_seen_tick = current_tick
    last_ts = time.time()
    
    recent_boots = 0
    all_rows = _all_identity_rows(root)
    for r in all_rows[-50:]:
        if r.get("event", {}).get("type") == "BOOT":
            recent_boots += 1

    personality_delta = 0.0
    if last_row:
        prev_personality = last_row.get("personality_vector", {})
        drift = detect_genome_drift(prev_personality, current_personality)
        if drift:
            personality_delta = drift["details"]["total_delta"]
            record_continuity_event("GENOME_DRIFT", drift["details"], root, current_tick=current_tick)
            
        cont = last_row.get("continuity", {})
        last_seen_tick = cont.get("last_seen_tick") or int(last_row.get("ts", time.time()))
        last_ts = last_row.get("ts", time.time())

    gap_ticks = max(0, current_tick - last_seen_tick)
    gap_seconds = max(0.0, time.time() - last_ts)

    current_internal_state = build_current_internal_state_vector(root)
    last_proto_self_vector = load_latest_proto_self_vector(root)

    revival_score = compute_revival_score(
        last_seen_tick, 
        current_tick, 
        personality_delta, 
        recent_boots,
        current_internal_state=current_internal_state,
        last_proto_self_vector=last_proto_self_vector
    )
    conservative_mode = revival_score < 0.6
    
    recommended_genome_blend = max(0.2, min(1.0, revival_score + 0.1))

    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "IDENTITY_REVIVAL_ASSESSMENT",
        "kind": "REVIVAL_ASSESSMENT",
        "identity_anchor": anchor,
        "personality_vector": current_personality,
        "continuity": {
            "last_seen_tick": last_seen_tick,
            "gap_duration_ticks": gap_ticks,
            "gap_duration_seconds": gap_seconds,
            "revival_score": round(revival_score, 4)
        },
        "event": {
            "type": "BOOT",
            "details": {
                "conservative_mode": conservative_mode,
                "recommended_genome_blend": round(recommended_genome_blend, 4)
            }
        }
    }

    append_line_locked(
        get_identity_ledger_path(root),
        json.dumps(row, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    return {
        "identity_anchor": anchor,
        "revival_score": round(revival_score, 4),
        "personality_vector": current_personality,
        "conservative_mode": conservative_mode,
        "recommended_genome_blend": round(recommended_genome_blend, 4)
    }


def _latest_revival_assessment(root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    for row in reversed(_all_identity_rows(root)):
        if row.get("kind") == "REVIVAL_ASSESSMENT":
            return row
    return None


def summary_for_prompt(root: Optional[Path] = None) -> str:
    """
    Compact live-context summary for Alice.

    This is intentionally read-only: prompt construction must not append boot rows
    on every inference. body_brain_tick/boot paths own rehydration writes.
    """
    row = _latest_revival_assessment(root)
    if not row:
        return ""

    continuity = row.get("continuity") or {}
    event_details = (row.get("event") or {}).get("details") or {}
    personality = row.get("personality_vector") or {}
    anchor = str(row.get("identity_anchor", "unknown_anchor"))
    anchor_short = anchor[:12] if anchor else "unknown"
    revival_score = float(continuity.get("revival_score", 0.0) or 0.0)
    conservative_mode = bool(event_details.get("conservative_mode", False))
    blend = float(event_details.get("recommended_genome_blend", 1.0) or 1.0)
    gap_ticks = int(float(continuity.get("gap_duration_ticks", 0) or 0))

    lines = [
        "ORGANIZATIONAL IDENTITY CONTINUITY:",
        f"- identity_anchor: {anchor_short}... | revival_score={revival_score:.3f} | conservative_mode={conservative_mode}",
        f"- gap_ticks={gap_ticks} | recommended_genome_blend={blend:.3f}",
    ]
    genome_hash = personality.get("genome_row_hash")
    if genome_hash:
        lines.append(f"- current_genome_hash: {str(genome_hash)[:12]}...")
    if personality.get("recent_regimes"):
        regimes = ", ".join(str(x) for x in personality.get("recent_regimes", [])[:5])
        lines.append(f"- recent_metacog_regimes: {regimes}")
    if conservative_mode:
        lines.append("- boot policy: speak and act cautiously until continuity recalibrates.")
    return "\n".join(lines)

__all__ = [
    "compute_identity_anchor",
    "snapshot_personality",
    "detect_genome_drift",
    "compute_revival_score",
    "record_continuity_event",
    "rehydrate_identity",
    "summary_for_prompt",
    "build_current_internal_state_vector",
    "snapshot_proto_self",
    "load_latest_proto_self_vector",
]
