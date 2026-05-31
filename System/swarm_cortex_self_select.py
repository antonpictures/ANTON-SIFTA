#!/usr/bin/env python3
"""System/swarm_cortex_self_select.py — Alice's cortex self-awareness + on-demand switch.

George's ask (r213): "she should be aware of installed cortexes and switch them on
HER demand needs, like now." The trigger was concrete — a dropped image only became
readable after the cortex was switched to a vision-capable brain. Alice should not
wait for the owner to swap her brain; she should know her options and switch herself.

This is the awareness primitive that makes that possible. It builds on what already
exists — swarm_primary_cortex_switcher.set_primary_cortex (the switch) and
installed_ollama_models / resolve_ollama_model (the current + installed set) — and
adds the missing piece: each cortex's CAPABILITIES (vision / tools / thinking),
probed from `ollama show` for local cortexes and a known map for the cloud teachers.

Honest boundaries:
  • Capability probing + the switch run on the owner's Mac (Ollama). Off-Mac this
    degrades to the known cloud-capability map and returns honest "cannot probe" notes.
  • The hard switch (set_primary_cortex) only targets cortexes INSTALLED in Ollama.
    If the only brain with a needed capability is a cloud cortex, this RECOMMENDS it
    rather than forcing a switch through the wrong path — no faked switch.
"""

from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional

# Known capabilities of the selectable cloud teacher cortexes (vision-capable noted).
_CLOUD_CAPS: Dict[str, List[str]] = {
    "codex": ["completion", "tools", "thinking", "vision"],
    "gpt-5.5": ["completion", "tools", "thinking", "vision"],
    "claude": ["completion", "tools", "thinking", "vision"],
    "grok": ["completion", "tools", "thinking", "vision"],
    "qwen": ["completion", "tools"],
}


def _ollama_caps(model_id: str) -> List[str]:
    """Parse `ollama show <model_id>` for its Capabilities block. [] if unprobeable."""
    try:
        proc = subprocess.run(["ollama", "show", model_id], capture_output=True, text=True, timeout=8)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    caps: List[str] = []
    in_caps = False
    for line in (proc.stdout or "").splitlines():
        low = line.strip().lower()
        if low.startswith("capabilities"):
            in_caps = True
            continue
        if in_caps:
            if not line.strip() or line[:1] not in (" ", "\t"):
                break
            tok = low.split()[0] if low.split() else ""
            if tok:
                caps.append(tok)
    return caps


def _cloud_caps_for(model_id: str) -> List[str]:
    low = (model_id or "").lower()
    for key, caps in _CLOUD_CAPS.items():
        if key in low:
            return caps
    return []


def active_cortex() -> str:
    try:
        from System.sifta_inference_defaults import resolve_ollama_model
        return resolve_ollama_model(app_context="talk_to_alice")
    except Exception:
        try:
            from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK
            return CANONICAL_OLLAMA_FALLBACK
        except Exception:
            return ""


def _installed_models() -> List[str]:
    try:
        from System.swarm_primary_cortex_switcher import installed_ollama_models
        return [str(r.get("name", "")) for r in installed_ollama_models() if r.get("name")]
    except Exception:
        return []


def list_cortexes_with_capabilities() -> List[Dict[str, Any]]:
    """Every cortex Alice can reach, with its capabilities and which is active."""
    active = active_cortex()
    out: List[Dict[str, Any]] = []
    for m in _installed_models():
        out.append({"model_id": m, "provider": "ollama_local",
                    "capabilities": _ollama_caps(m), "active": (m == active)})
    for tag in ("codex", "claude", "grok", "qwen"):
        out.append({"model_id": tag, "provider": "cloud_teacher",
                    "capabilities": _CLOUD_CAPS.get(tag, []), "active": (tag in (active or "").lower())})
    return out


def _has_capability(model_id: str, capability: str) -> bool:
    caps = _ollama_caps(model_id) or _cloud_caps_for(model_id)
    return capability.lower() in [c.lower() for c in caps]


def recommend_cortex_for(capability: str) -> Optional[Dict[str, Any]]:
    """Best cortex that has `capability` — prefer a local Ollama brain, else cloud."""
    cands = list_cortexes_with_capabilities()
    local = [c for c in cands if c["provider"] == "ollama_local"
             and capability.lower() in [x.lower() for x in c["capabilities"]]]
    if local:
        return local[0]
    cloud = [c for c in cands if c["provider"] == "cloud_teacher"
             and capability.lower() in [x.lower() for x in c["capabilities"]]]
    return cloud[0] if cloud else None


def self_select_for_capability(capability: str) -> Dict[str, Any]:
    """Alice's on-demand move: ensure the active cortex has `capability`; switch if not.

    Returns a dict describing the decision. Hard-switches only to an installed Ollama
    cortex; if only a cloud cortex qualifies, recommends it (the cloud switch path is
    the Talk picker, not set_primary_cortex) — never fakes a switch.
    """
    active = active_cortex()
    if active and _has_capability(active, capability):
        return {"ok": True, "switched": False, "active": active,
                "note": f"active cortex already has '{capability}'"}
    rec = recommend_cortex_for(capability)
    if not rec:
        return {"ok": False, "switched": False, "active": active,
                "note": f"no reachable cortex advertises '{capability}'"}
    if rec["provider"] == "ollama_local":
        try:
            from System.swarm_primary_cortex_switcher import set_primary_cortex
            res = set_primary_cortex(rec["model_id"], source="alice_self_select")
            return {"ok": True, "switched": True, "to": rec["model_id"],
                    "capability": capability, "switch_receipt": res}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "switched": False, "error": f"{type(exc).__name__}: {exc}",
                    "recommend": rec}
    return {"ok": True, "switched": False, "recommend": rec,
            "note": f"only a cloud cortex ({rec['model_id']}) has '{capability}'; "
                    f"select it from the Talk cortex picker"}


if __name__ == "__main__":
    print("active cortex:", active_cortex())
    for c in list_cortexes_with_capabilities():
        print(f"  {c['provider']:14} {c['model_id']:42} caps={c['capabilities']} active={c['active']}")
    print("self_select_for_capability('vision'):", self_select_for_capability("vision"))
