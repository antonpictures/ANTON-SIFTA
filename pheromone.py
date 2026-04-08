import json
import os
import time
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

SCARS_MD_MAX = 200  # Maximum scar entries shown in SCARS.md

def compute_territory_hash(file_path: str, bite_range: tuple[int, int] | None = None) -> str:
    """Computes SHA-256 hash of the actual physical territory touched."""
    try:
        with open(file_path, "rb") as f:
            content = f.read()
    except Exception:
        # If file doesn't exist or is unreadable, treat as empty
        content = b""

    if bite_range:
        start, end = bite_range
        context_radius = 20

        lines = content.splitlines(keepends=True)
        slice_start = max(0, start - context_radius)
        slice_end = min(len(lines), end + context_radius)

        scoped = b"".join(lines[slice_start:slice_end])
        return hashlib.sha256(scoped).hexdigest()

    return hashlib.sha256(content).hexdigest()

def resolve_territory_hashes(action_type: str, file_path: str = None, bite_range=None) -> tuple[str, str]:
    # Lazy import to avoid circular dependency
    from body_state import NULL_TERRITORY
    
    if action_type in ["FIX", "BITE", "SCOUT"]:
        if not file_path:
            return NULL_TERRITORY, NULL_TERRITORY
            
        pre_hash = compute_territory_hash(file_path, bite_range)
        
        if action_type == "SCOUT":
            post_hash = pre_hash
        else:
            post_hash = compute_territory_hash(file_path, bite_range)
            
    else:
        pre_hash = NULL_TERRITORY
        post_hash = NULL_TERRITORY
        
    return pre_hash, post_hash

def calculate_potency(timestamp_str: str) -> float:
    """Returns a score between 0.0 and 1.0 based on how fresh the scent is.
    Physics: exponential decay, half-life = 24h. e^(-kt), k = ln(2)/24 ≈ 0.02888
    """
    try:
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta_hours = (now - ts).total_seconds() / 3600.0
        potency = max(0.01, min(1.0, 2.71828 ** (-0.02888 * delta_hours)))
        return round(potency, 4)
    except Exception:
        return 0.1  # Very weak if parsing fails


def smell_territory(directory: Path) -> List[Dict[str, Any]]:
    """Reads ALL .scar files in the .sifta folder and returns them sorted by urgency.
    V2: multi-scar-aware. Each file is a distinct, immutable event.
    """
    sifta_dir = directory / ".sifta"
    if not sifta_dir.exists() or not sifta_dir.is_dir():
        return []

    scars = []
    for scar_file in sifta_dir.glob("*.scar"):
        try:
            with open(scar_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Recalculate runtime potency against the real system clock
                if "scent" in data and "last_visited" in data["scent"]:
                    data["scent"]["potency"] = calculate_potency(data["scent"]["last_visited"])
                scars.append(data)
        except Exception:
            continue

    # Weight logic: compound potency × bleeding multiplier
    def smell_score(scar):
        is_bleeding = 2 if scar.get("stigmergy", {}).get("status") == "BLEEDING" else 1
        potency = scar.get("scent", {}).get("potency", 0.0)
        return potency * is_bleeding

    return sorted(scars, key=smell_score, reverse=True)


def aggregate_territory(scars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes the compound field intensity of a territory from all its scars.
    This is the consensus reading — not just the loudest voice.
    """
    bleeding_count = 0
    total_potency = 0.0
    max_potency = 0.0
    agents = set()

    for s in scars:
        potency = s.get("scent", {}).get("potency", 0.0)
        status = s.get("stigmergy", {}).get("status")
        total_potency += potency
        max_potency = max(max_potency, potency)
        if status == "BLEEDING":
            bleeding_count += 1
        agents.add(s.get("agent_id", "UNKNOWN"))

    danger_score = round(bleeding_count * total_potency, 3)
    overall_status = "BLEEDING" if bleeding_count > 0 else "CLEAN"

    return {
        "status": overall_status,
        "bleeding_count": bleeding_count,
        "total_potency": round(total_potency, 3),
        "max_potency": round(max_potency, 4),
        "danger_score": danger_score,
        "agents": sorted(list(agents))
    }


def drop_scar(
    directory: Path,
    agent_state: Dict[str, Any],
    action: str,
    found: str,
    status: str,
    mark_text: str,
    parent_hash: str = None,
    action_hash: str = None,
    unresolved_line: int = -1,
    reason: Dict[str, Any] = None,
    pre_territory_hash: str = None,
    post_territory_hash: str = None
):
    """Drops a pheromone mark in the directory using atomic, distinct per-action writes.
    V2: Each call = a new immutable .scar file. No overwrites. No collisions.
    """
    sifta_dir = directory / ".sifta"
    sifta_dir.mkdir(parents=True, exist_ok=True)

    agent_id = agent_state.get("id", "UNKNOWN")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Unique filename: agent + millisecond timestamp + 6-char uuid entropy
    ts_ms = int(time.time() * 1000)
    entropy = uuid.uuid4().hex[:6]
    scar_path = sifta_dir / f"{agent_id}_{ts_ms}_{entropy}.scar"

    # Danger level is driven by structured reason, not string matching
    danger_level = "SAFE"
    if status == "BLEEDING":
        danger_level = "HIGH"
    elif reason and reason.get("type") in ("Hallucination", "ValidationFail"):
        danger_level = "WARNING"

    # Parse face from raw body string if available
    raw = agent_state.get("raw", "")
    if "<///" in raw:
        try:
            face = raw.split("<///")[1].split("///::")[0]
        except Exception:
            face = "[?]"
    else:
        face = agent_state.get("face", "[?]")

    body_hash = raw[-64:] if len(raw) >= 64 else raw

    data = {
        "agent_id": agent_id,
        "body_hash": body_hash,
        "face": face,
        "action": action,
        "mark": mark_text,
        "pre_territory_hash": pre_territory_hash,
        "post_territory_hash": post_territory_hash,
        "scent": {
            "last_visited": now_iso,
            "potency": 1.0,
            "danger_level": danger_level
        },
        "stigmergy": {
            "status": status,
            "unresolved_fault_line": unresolved_line,
            "reason": reason  # structured — machine readable
        },
        "history": [{
            "ts": now_iso,
            "action": action,
            "found": found,
            "reason": reason,
            "parent_hash": parent_hash,
            "action_hash": action_hash
        }]
    }

    # Atomic write — POSIX os.replace is atomic
    tmp_path = scar_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, scar_path)

    _rebuild_scars_md(sifta_dir)


def _rebuild_scars_md(sifta_dir: Path):
    """Regenerates the human-readable Markdown Chronicle.
    V2: Chronological append-only. Oldest at top, newest at bottom.
    Capped at SCARS_MD_MAX entries for performance.
    """
    scars = []
    for p in sifta_dir.glob("*.scar"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                scars.append(json.load(f))
        except Exception:
            pass

    # Chronological — oldest first (bottom is most recent)
    scars.sort(key=lambda x: x.get("scent", {}).get("last_visited", ""))

    # Cap to avoid O(n²)
    if len(scars) > SCARS_MD_MAX:
        scars = scars[-SCARS_MD_MAX:]

    md = [
        "# ANTON-SIFTA TERRITORY CHRONICLE",
        "> Chronological record of agent presence. Oldest event at top, newest at bottom.",
        f"> Total marks: {len(scars)} (cap: {SCARS_MD_MAX})",
        ""
    ]

    for s in scars:
        scent = s.get("scent", {})
        ts = scent.get("last_visited", "Unknown")[:19].replace("T", " ")
        potency = scent.get("potency", 0.0)
        danger = scent.get("danger_level", "SAFE")
        status = s.get("stigmergy", {}).get("status", "UNKNOWN")
        face = s.get("face", "[x]")
        agent = s.get("agent_id", "ANON")
        mark = s.get("mark", "")
        action = s.get("action", "?")
        reason = s.get("stigmergy", {}).get("reason")

        status_icon = "🩸" if status == "BLEEDING" else ("✅" if status in ("RESOLVED", "CLEAN") else "💨")
        md.append(f"### {ts} | {status_icon} {face} {agent}")
        md.append(f"**Action:** `{action}` | **Status:** `{status}` | **Danger:** `{danger}` | **Potency:** `{potency}`")

        if status == "BLEEDING":
            line = s.get("stigmergy", {}).get("unresolved_fault_line", -1)
            if line > 0:
                md.append(f"⚠️ **Bleeding wound at line {line}**")

        if reason:
            md.append(f"🔬 **Machine Cause:** `{reason.get('type', '?')}` — {reason.get('message', '')[:120]}")

        md.append(f"> {mark}")
        md.append("")

    (sifta_dir / "SCARS.md").write_text("\n".join(md), encoding="utf-8")


def scan_all_territories(root_path: Path) -> List[Dict[str, Any]]:
    """Recursively scans for all .sifta folders and returns aggregate territory status.
    V2: Uses aggregate_territory() for compound field intensity, not just max scar.
    """
    territories = []

    for sifta_dir in root_path.rglob(".sifta"):
        if not sifta_dir.is_dir():
            continue

        rel_path = str(sifta_dir.parent.relative_to(root_path))
        if rel_path == ".":
            rel_path = "Root"

        scars = smell_territory(sifta_dir.parent)
        if not scars:
            continue

        agg = aggregate_territory(scars)

        territories.append({
            "path": rel_path,
            "full_path": str(sifta_dir.parent.absolute()),
            "status": agg["status"],
            "bleeding_count": agg["bleeding_count"],
            "danger_score": agg["danger_score"],
            "max_potency": agg["max_potency"],
            "total_potency": agg["total_potency"],
            "agents": agg["agents"],
            "last_visited": max(
                (s.get("scent", {}).get("last_visited", "") for s in scars),
                default=""
            )
        })

    # Sort: danger_score descending (most wounded territory first)
    territories.sort(key=lambda x: x["danger_score"], reverse=True)
    return territories
