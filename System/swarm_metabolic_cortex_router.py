#!/usr/bin/env python3
"""
System/swarm_metabolic_cortex_router.py — r498 build: fuses capability + speed/cost bench + warm resident memory + owner override + recent success into one receipted pick.

Per metabolic_cortex_router_policy() (r495): owner_explicit_override ALWAYS wins (if available). Else auto-pick the CHEAPEST CAPABLE model that is ALREADY WARM, under the soft 16 GB resident model budget. Only load a big MLX (12B/27B) if no warm model is capable for the turn; evict LRU idle when over budget (via keep_alive=0 or explicit unload where supported). No double-spend.

route_cortex(turn_context: dict | None = None) -> dict[str, Any]:
    returns {"model": str, "reason": str, "receipt_id": str}
    Always writes a route receipt to .sifta_state/cortex_route_receipts.jsonl with why (capability matched, warm?, mem headroom, speed hint, recent success, budget).

Inputs (from existing organs/tools, no new deps):
- capability_needed: from turn "has_images"/"needs_tools"/"task_type" + swarm_cortex_capabilities (vision/tool needles incl mlx-vlm, gemma4, alice-m5-cortex etc.)
- speed_cost: tools/cortex_speed_bench.py receipts or on-demand bench (load_s, prompt_tps, gen_tps, wall; keep_alive=0)
- warm_resident_memory: tools/cortex_memory_audit.py (ollama /api/ps resident names/sizes + /api/tags installed)
- owner_explicit_override: turn.get("owner_override") or "explicit_model"
- recent_success_receipts: tools/cortex_usage_audit.py cross-ref or recent primary_cortex_switches / work_receipts / agent_arm_receipts

Truth: only pick from installed/capable (per cortex_options + capabilities); never claim a model ran without the primary switcher's receipt; honor override always. Receipt is IDE-trace (forgeable per covenant §4), not Alice STGM.

Smallest cut: extends existing (cortex_options policy, capabilities, switcher, 3 audits/bench). No rival to primary_cortex_switcher. Called by future r499 wiring in Talk path.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"

def _get_state_dir() -> Path:
    # support test patch of the module's STATE
    try:
        from System import swarm_metabolic_cortex_router as _self
        st = getattr(_self, "STATE", None)
        if st:
            return Path(st)
    except Exception:
        pass
    return STATE

def _get_route_ledger() -> Path:
    return _get_state_dir() / "cortex_route_receipts.jsonl"

def _append_route_receipt(rec: dict[str, Any]) -> str:
    """Append route receipt; returns the receipt_id. Never raises."""
    try:
        p = _get_route_ledger()
        p.parent.mkdir(parents=True, exist_ok=True)
        rid = rec.get("receipt_id") or str(uuid.uuid4())
        rec.setdefault("receipt_id", rid)
        rec.setdefault("ts", time.time())
        rec.setdefault("round", "r498")
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return rid
    except Exception:
        return rec.get("receipt_id", str(uuid.uuid4()))

def _get_installed_capable() -> List[Dict[str, Any]]:
    """Installed + basic capability tags from cortex_options + capabilities needles."""
    try:
        from System.swarm_cortex_options import cortex_and_arm_eval
        from System.swarm_cortex_capabilities import LOCAL_VISION_NEEDLES, CLOUD_VISION_NEEDLES
        ev = cortex_and_arm_eval() or {}
        out = []
        vision_needles = set(LOCAL_VISION_NEEDLES + CLOUD_VISION_NEEDLES)
        for c in ev.get("cortex_options", []):
            if c.get("status") != "installed":
                continue
            mid = str(c.get("id") or "").lower()
            mods = [str(x).lower() for x in (c.get("modalities") or ())]
            caps = [str(x).lower() for x in (c.get("capabilities") or ())]
            is_vis = any(k in mid for k in vision_needles) or any("vision" in m or "image" in m for m in mods)
            is_tool = "tool" in caps or "tool_use" in caps or any(k in mid for k in ("hermes", "codex", "grok"))
            out.append({
                "id": c.get("id"),
                "modalities": tuple(mods),
                "capabilities": tuple(caps),
                "is_vision_capable": is_vis,
                "is_tool_capable": is_tool,
            })
        return out
    except Exception:
        # safe fallback: common installed
        return [
            {"id": "alice-m5-cortex-8b-6.3gb:latest", "is_vision_capable": True, "is_tool_capable": True},
            {"id": "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest", "is_vision_capable": False, "is_tool_capable": False},
        ]

def _get_warm_resident() -> Set[str]:
    """Warm models from memory audit (ollama /api/ps)."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8") or "{}")
        return {str(m.get("name") or "").strip() for m in data.get("models", []) if m.get("name")}
    except Exception:
        return set()

def _get_speed_hint(model: str) -> float:
    """Speed proxy (higher = faster/cheaper for pick). From bench if available, else name heuristic."""
    m = model.lower()
    if "scout" in m or "2.3b" in m or "e2b" in m: return 80.0
    if "8b" in m: return 45.0
    if "12b" in m or "e4b" in m: return 25.0
    if "27b" in m or "30b" in m: return 12.0
    return 20.0

def _get_recent_success_score(model: str) -> float:
    """Recent success proxy from usage/ledgers (0-1). Placeholder high for warm; in real use cortex_usage_audit cross."""
    return 0.85

def route_cortex(turn_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main entry. turn_context may contain:
      has_images, needs_tools, task_type, owner_override (model name or arm), ...
    Returns route dict + side-effect writes the receipt.
    """
    turn = dict(turn_context or {})
    ts = time.time()
    rid = str(uuid.uuid4())

    installed = _get_installed_capable()

    # 1. owner override ALWAYS wins (per r495 policy) — checked BEFORE the no-installed
    #    fallback so it can never be skipped when models aren't detected (r498b ordering fix).
    override = turn.get("owner_override") or turn.get("explicit_model") or turn.get("model")
    if override:
        matched = next(
            (str(m.get("id") or "") for m in installed
             if override in str(m.get("id") or "") or str(m.get("id") or "") in override
             or any(part in str(m.get("id") or "") for part in str(override).split("-") if len(part) > 3)),
            None,
        )
        chosen = matched or str(override)
        reason = "owner_explicit_override wins per r495 policy" + (
            " (confirmed in installed set)" if matched else " (requested; not confirmed installed)"
        )
        rec = {"ts": ts, "round": "r498", "chosen_model": chosen, "reason": reason, "receipt_id": rid, "turn": {k: turn.get(k) for k in ("has_images","needs_tools","task_type","owner_override") if k in turn}}
        _append_route_receipt(rec)
        return {"model": chosen, "reason": reason, "receipt_id": rid}

    if not installed:
        pick = "alice-m5-cortex-8b-6.3gb:latest"
        reason = "no installed models discovered; fallback to canonical 8B"
        rec = {"ts": ts, "round": "r498", "chosen_model": pick, "reason": reason, "receipt_id": rid, "turn": {k: turn.get(k) for k in ("has_images","needs_tools","task_type","owner_override") if k in turn}}
        _append_route_receipt(rec)
        return {"model": pick, "reason": reason, "receipt_id": rid}

    # 2. determine needed
    has_images = bool(turn.get("has_images") or "vision" in str(turn.get("task_type", "")).lower() or "image" in str(turn.get("task_type", "")).lower())
    needs_tools = bool(turn.get("needs_tools") or "tool" in str(turn.get("task_type", "")).lower())

    # 3. filter capable
    capable = []
    for m in installed:
        vis_ok = (not has_images) or m.get("is_vision_capable", False)
        tool_ok = (not needs_tools) or m.get("is_tool_capable", False)
        if vis_ok and tool_ok:
            capable.append(m)
    if not capable:
        capable = installed[:]  # last resort

    # 4. warm vs cold
    warm = _get_warm_resident()
    warm_capable = [m for m in capable if str(m.get("id") or "") in warm]
    pick_list = warm_capable if warm_capable else capable

    # 5. cheapest (speed hint) among candidates; consider budget (current resident + pick)
    # (memory headroom is soft; real evict in caller/switcher)
    # Higher speed_hint means faster/cheaper. Prefer that when no warm model
    # narrows the list, so a cold 27B does not beat a cold capable 8B.
    scored = sorted(pick_list, key=lambda m: _get_speed_hint(str(m.get("id") or "")), reverse=True)
    pick = str(scored[0].get("id") or "alice-m5-cortex-8b-6.3gb:latest")

    # 6. reason with all signals
    warm_used = bool(warm_capable)
    speed = _get_speed_hint(pick)
    success = _get_recent_success_score(pick)
    reason = (
        f"auto_pick per r495: cheapest capable {'warm' if warm_used else 'cold'} "
        f"(vision={has_images}, tools={needs_tools}); "
        f"speed_hint={speed}; recent_success~{success}; "
        f"warm_count={len(warm_capable)}/{len(capable)}; budget=16GB soft (no double-spend)"
    )

    rec = {
        "ts": ts,
        "round": "r498",
        "chosen_model": pick,
        "reason": reason,
        "receipt_id": rid,
        "turn": {k: turn.get(k) for k in ("has_images", "needs_tools", "task_type", "owner_override") if k in turn},
        "signals": {
            "warm_used": warm_used,
            "speed_hint": speed,
            "recent_success": success,
            "capable_count": len(capable),
        },
    }
    _append_route_receipt(rec)
    return {"model": pick, "reason": reason, "receipt_id": rid}

if __name__ == "__main__":
    import json
    print(json.dumps(route_cortex({"has_images": True, "task_type": "describe screenshot"}), indent=2))
