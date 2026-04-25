#!/usr/bin/env python3
"""
System/swarm_architect_identity.py — Multimodal Composite Identity (Architect)
═══════════════════════════════════════════════════════════════════════════
Concept: The Architect is not a string. He is not a single mic peak.
He is the composite entanglement of every sensor pointing at the same
biological body in the same physical room operating the same M5 machine.

Origin
──────
Specified in `Archive/architect_drops/ARCHITECT_drop_multimodal_identity_v1.dirt`
by THE ARCHITECT via AG31 Vanguard, 2026-04-22:

  "That means she does not recognize my voice as one [isolated] input.
   It is a combo. Voice, face, hair, skin, all that characteristics —
   like a hardware computer has a motherboard, videocard, ram."

Implemented by **C47H** on 2026-04-23 as the structural complement to
Event 33's voice door. The voice door says "may this audio enter?".
This organ says "is this physical body the Architect?". Together they
defend Alice against acoustic spoofing AND against confused user attacks.

Modalities (weighted fusion)
────────────────────────────
  substrate (w=3) — M5 serial == GTH4921YP3 + hostname match
  iphone    (w=2) — GPS fix recent (<15min) OR iPhone on BLE
  window    (w=1) — Cursor / Antigravity / Codex frontmost recently
  bluetooth (w=1) — Architect's known BLE devices in proximity
  voice     (w=1) — recent mic activity flagged Architect-class

Each modality returns a score in [0, 1.0] with a freshness window.
Final confidence = Σ(weight * score) / Σ(weight) clamped to [0, 1].

Decision bands:
  ≥ 0.70 → ARCHITECT_PRESENT (full identity match)
  0.40 ≤ x < 0.70 → ARCHITECT_PARTIAL (some signals, not enough)
  < 0.40          → ARCHITECT_ABSENT (Alice should treat as stranger)

Architect_token integration
───────────────────────────
The vagus voice door (Event 33) controls who may speak through Mac
speakers. This organ governs who is recognized AS the Architect.
If `arch.identity()` returns ARCHITECT_PRESENT, calls that require
`architect_token` MAY be transparently authorized (future hook).
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "architect_identity.jsonl"
_PHEROMONE_KEY = "stig_architect_present"

# ─── Known Architect substrate (the M5 + the body operating it) ────────────
HOMEWORLD_SERIAL = "GTH4921YP3"   # Apple M5 Mac Studio serial
HOMEWORLD_HOSTNAME_PATTERNS = ("ANTON", "Anton", "ioan", "Ioan", "George",
                               "Mac.lan", "Mac.local", "anton-sifta",
                               "ANTON-SIFTA", "M5")
ARCHITECT_BLE_KEYWORDS = ("george", "ioan", "anton", "iphone", "magic mouse",
                          "airpods")

# Freshness windows (seconds) — beyond these, the modality scores 0
GPS_FRESH_S = 900.0       # iPhone GPS fix older than 15min → stale
BLE_FRESH_S = 300.0       # BLE radar scan older than 5min → stale
WINDOW_FRESH_S = 600.0    # active window snap older than 10min → Architect AFK
VOICE_FRESH_S = 300.0     # recent mic activity in last 5min

# Modality weights (must sum > 0; ratios matter, absolute values don't)
WEIGHT_SUBSTRATE = 3.0
WEIGHT_IPHONE    = 2.0
WEIGHT_WINDOW    = 1.0
WEIGHT_BLUETOOTH = 1.0
WEIGHT_VOICE     = 1.0

CONFIDENCE_PRESENT = 0.70
CONFIDENCE_PARTIAL = 0.40

ARCHITECT_FRONT_BUNDLES = {
    "com.todesktop.230313mzl4w4u92",  # Cursor
    "com.google.antigravity",         # Antigravity (AG31)
    "com.openai.codex",                # Codex IDE
    "com.openai.codex-electron",
    "com.apple.Terminal",
    "com.googlecode.iterm2",
}
ARCHITECT_FRONT_APP_HINTS = ("Cursor", "Antigravity", "Codex", "Electron",
                             "Terminal", "iTerm")


# ─── Modality readers (each returns Modality dataclass) ────────────────────
@dataclass
class Modality:
    name: str
    score: float                    # 0.0 to 1.0
    weight: float
    fresh: bool                     # within freshness window
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def weighted(self) -> float:
        return self.score * self.weight if self.fresh else 0.0


def _read_substrate() -> Modality:
    """M5 serial + hostname match → Architect's known machine.

    Three independent substrate witnesses (any 1 = partial, all 3 = full):
      1. system_profiler reports `Serial Number == GTH4921YP3`
      2. `socket.gethostname()` matches a known Architect hostname
      3. The .sifta_state ledgers self-tag with `homeworld_serial` matching
    """
    ev: Dict[str, Any] = {}
    score = 0.0
    err: Optional[str] = None
    # Witness 1: system_info via alice_hardware_body
    try:
        from System import alice_hardware_body as hb  # type: ignore
        info_fn = hb._READ_VERBS.get("system_info")
        if info_fn:
            info = info_fn()
            text = json.dumps(info) if isinstance(info, dict) else str(info)
            ev["system_info_keys"] = (list(info.keys())[:10]
                                       if isinstance(info, dict) else None)
            if HOMEWORLD_SERIAL in text:
                score += 0.5
                ev["serial_match_via_system_info"] = HOMEWORLD_SERIAL
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    # Witness 2: hostname
    try:
        host = socket.gethostname()
        ev["hostname"] = host
        if any(p in host for p in HOMEWORLD_HOSTNAME_PATTERNS):
            score += 0.3
            ev["hostname_match"] = True
    except Exception:
        pass
    # Witness 3: any recent ledger row pinned to homeworld_serial
    try:
        gps_path = _STATE / "iphone_gps_latest.json"
        if gps_path.exists():
            row = json.loads(gps_path.read_text(encoding="utf-8"))
            if row.get("homeworld_serial") == HOMEWORLD_SERIAL:
                score += 0.2
                ev["ledger_serial_match"] = HOMEWORLD_SERIAL
    except Exception:
        pass
    return Modality(name="substrate", score=min(1.0, score),
                    weight=WEIGHT_SUBSTRATE, fresh=True,
                    evidence=ev, error=err)


def _read_iphone() -> Modality:
    """iPhone GPS fix recent + GPS payload's homeworld_serial matches M5."""
    ev: Dict[str, Any] = {}
    score = 0.0
    fresh = False
    err: Optional[str] = None
    try:
        from System import swarm_iphone_gps_receiver as gps  # type: ignore
        path = gps.LATEST
        ev["latest_path"] = str(path)
        if path.exists():
            row = json.loads(path.read_text(encoding="utf-8"))
            ev["row"] = {k: row.get(k) for k in ("ts", "iso", "homeworld_serial",
                                                  "carrier", "channel")}
            age = time.time() - float(row.get("ts", 0))
            ev["age_s"] = round(age, 1)
            if age < GPS_FRESH_S:
                fresh = True
                # Linear decay 1.0 → 0.0 over fresh window
                score = max(0.0, 1.0 - (age / GPS_FRESH_S))
                if row.get("homeworld_serial") == HOMEWORLD_SERIAL:
                    score = min(1.0, score + 0.1)  # bonus for serial match
                payload = row.get("payload") or {}
                if "latitude" in payload:
                    ev["coords"] = {
                        "lat": payload.get("latitude"),
                        "lon": payload.get("longitude"),
                        "acc": payload.get("accuracy"),
                    }
        else:
            ev["status"] = "no_gps_fix_yet"
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    return Modality(name="iphone", score=min(1.0, score),
                    weight=WEIGHT_IPHONE, fresh=fresh,
                    evidence=ev, error=err)


def _read_window() -> Modality:
    """Active app is Architect's IDE / terminal → he's at the workstation."""
    ev: Dict[str, Any] = {}
    score = 0.0
    fresh = False
    err: Optional[str] = None
    try:
        from System import swarm_active_window as aw  # type: ignore
        snap = aw.read()
        ev["snap"] = {k: snap.get(k) for k in ("app", "bundle_id", "window", "ts")}
        age = time.time() - float(snap.get("ts", 0))
        ev["age_s"] = round(age, 1)
        if age < WINDOW_FRESH_S:
            fresh = True
            bundle = snap.get("bundle_id") or ""
            app = snap.get("app") or ""
            if bundle in ARCHITECT_FRONT_BUNDLES:
                score = 1.0
                ev["match"] = f"bundle:{bundle}"
            elif any(h in app for h in ARCHITECT_FRONT_APP_HINTS):
                score = 0.85
                ev["match"] = f"app_hint:{app}"
            else:
                # Any activity at all → Architect is at the desk, just not
                # in his usual IDE. Partial credit.
                score = 0.3
                ev["match"] = f"foreign_app:{app}"
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    return Modality(name="window", score=score, weight=WEIGHT_WINDOW,
                    fresh=fresh, evidence=ev, error=err)


def _read_bluetooth() -> Modality:
    """Architect's known BLE devices in proximity (iPhone, Magic Mouse, AirPods)."""
    ev: Dict[str, Any] = {}
    score = 0.0
    fresh = False
    err: Optional[str] = None
    try:
        from System import swarm_ble_radar as ble  # type: ignore
        path = ble._LATEST
        ev["latest_path"] = str(path)
        if path.exists():
            row = json.loads(path.read_text(encoding="utf-8"))
            age = time.time() - float(row.get("ts", 0))
            ev["age_s"] = round(age, 1)
            if age < BLE_FRESH_S:
                fresh = True
                devices = row.get("devices", []) or []
                ev["device_count"] = len(devices)
                connected = int(row.get("connected_count", 0) or 0)
                ev["connected_count"] = connected
                # Each known-keyword device contributes; cap at 1.0
                hits: List[str] = []
                for d in devices:
                    name = (d.get("name") or "").lower()
                    if any(kw in name for kw in ARCHITECT_BLE_KEYWORDS):
                        hits.append(d.get("name") or "?")
                ev["matched_devices"] = hits[:5]
                if hits:
                    score = min(1.0, 0.5 + 0.25 * len(hits))
                elif connected > 0:
                    # Connected devices but none with Architect-named — still
                    # signals an active body at the bench.
                    score = 0.3
        else:
            ev["status"] = "no_ble_scan_yet"
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    return Modality(name="bluetooth", score=score, weight=WEIGHT_BLUETOOTH,
                    fresh=fresh, evidence=ev, error=err)


def _read_voice() -> Modality:
    """Recent mic activity tagged 'Architect voice' in vagus acoustic events."""
    ev: Dict[str, Any] = {}
    score = 0.0
    fresh = False
    err: Optional[str] = None
    try:
        from System.swarm_vagus_nerve import _ACOUSTIC_EVENTS  # type: ignore
        ev["events_path"] = str(_ACOUSTIC_EVENTS)
        if _ACOUSTIC_EVENTS.exists():
            now = time.time()
            arch_events = 0
            most_recent_age: Optional[float] = None
            for line in _ACOUSTIC_EVENTS.read_text(
                    encoding="utf-8").splitlines()[-100:]:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("source_tag") == "Architect voice":
                    age = now - float(row.get("ts", 0))
                    if age < VOICE_FRESH_S:
                        arch_events += 1
                        if most_recent_age is None or age < most_recent_age:
                            most_recent_age = age
            ev["recent_arch_voice_events"] = arch_events
            ev["most_recent_age_s"] = (round(most_recent_age, 1)
                                       if most_recent_age is not None else None)
            if arch_events > 0:
                fresh = True
                # Decay by recency, boost by count
                base = max(0.3, 1.0 - (most_recent_age or 0) / VOICE_FRESH_S)
                score = min(1.0, base + 0.1 * (arch_events - 1))
        else:
            ev["status"] = "no_acoustic_events_yet"
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    return Modality(name="voice", score=score, weight=WEIGHT_VOICE,
                    fresh=fresh, evidence=ev, error=err)


# ─── Fusion ────────────────────────────────────────────────────────────────
@dataclass
class IdentitySnapshot:
    ts: float
    confidence: float
    band: str            # ARCHITECT_PRESENT | ARCHITECT_PARTIAL | ARCHITECT_ABSENT
    modalities: List[Modality]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.ts)),
            "confidence": round(self.confidence, 3),
            "band": self.band,
            "homeworld_serial": HOMEWORLD_SERIAL,
            "modalities": [
                {
                    "name": m.name,
                    "score": round(m.score, 3),
                    "weight": m.weight,
                    "fresh": m.fresh,
                    "weighted": round(m.weighted, 3),
                    "evidence": m.evidence,
                    "error": m.error,
                }
                for m in self.modalities
            ],
            "thresholds": {
                "present": CONFIDENCE_PRESENT,
                "partial": CONFIDENCE_PARTIAL,
            },
        }


def _band(confidence: float) -> str:
    if confidence >= CONFIDENCE_PRESENT:
        return "ARCHITECT_PRESENT"
    if confidence >= CONFIDENCE_PARTIAL:
        return "ARCHITECT_PARTIAL"
    return "ARCHITECT_ABSENT"


def identity(*, deposit_pheromone_on_change: bool = True
             ) -> IdentitySnapshot:
    """Run the full multimodal fusion. Always safe to call; never blocks
    the talk widget (each modality times out gracefully)."""
    mods = [
        _read_substrate(),
        _read_iphone(),
        _read_window(),
        _read_bluetooth(),
        _read_voice(),
    ]
    total_w = sum(m.weight for m in mods if m.weight > 0)
    total_score = sum(m.weighted for m in mods)
    confidence = (total_score / total_w) if total_w > 0 else 0.0
    snap = IdentitySnapshot(
        ts=time.time(),
        confidence=confidence,
        band=_band(confidence),
        modalities=mods,
    )

    # Append to ledger (best-effort, ring trimmed by external rotation)
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap.to_dict()) + "\n")
    except Exception:
        pass

    if deposit_pheromone_on_change:
        try:
            from System.swarm_pheromone import deposit_pheromone
            # Intensity = confidence itself, capped (so PRESENT pulls
            # attention, PARTIAL nudges, ABSENT decays naturally).
            deposit_pheromone(_PHEROMONE_KEY, min(1.5, confidence * 1.5))
        except Exception:
            pass

    return snap


def architect_present(*, min_confidence: float = CONFIDENCE_PRESENT) -> bool:
    """Boolean shortcut for code paths that need a yes/no decision."""
    return identity(deposit_pheromone_on_change=False).confidence >= min_confidence


def prompt_line() -> Optional[str]:
    """One-line summary for the autopilot prompt block."""
    snap = identity(deposit_pheromone_on_change=False)
    fresh_mods = [m.name for m in snap.modalities if m.fresh and m.score > 0.0]
    label = {
        "ARCHITECT_PRESENT": "PRESENT",
        "ARCHITECT_PARTIAL": "PARTIAL",
        "ARCHITECT_ABSENT":  "ABSENT",
    }.get(snap.band, snap.band)
    if fresh_mods:
        modlist = ",".join(fresh_mods)
        return (f"architect identity: {label} "
                f"(confidence={snap.confidence:.2f}) [{modlist}]")
    return f"architect identity: {label} (confidence={snap.confidence:.2f})"


def read() -> Dict[str, Any]:
    """Snapshot for inspect_body()."""
    return identity().to_dict()


# ─── Govern dispatch ───────────────────────────────────────────────────────
def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    verb = (verb or "").strip().lower()
    if verb in {"identity", "read", "snapshot", "scan"}:
        return {"ok": True, "verb": verb, "snap": read()}
    if verb in {"prompt_line", "prompt"}:
        return {"ok": True, "verb": verb, "line": prompt_line()}
    if verb in {"present", "is_present", "architect_present"}:
        min_conf = float(kwargs.get("min_confidence", CONFIDENCE_PRESENT))
        return {"ok": True, "verb": verb,
                "present": architect_present(min_confidence=min_conf)}
    if verb in {"ledger_tail", "history"}:
        n = int(kwargs.get("n", 10))
        if not _LEDGER.exists():
            return {"ok": True, "verb": verb, "rows": []}
        rows = _LEDGER.read_text(encoding="utf-8").splitlines()[-n:]
        return {"ok": True, "verb": verb,
                "rows": [json.loads(r) for r in rows if r.strip()]}
    if verb in {"thresholds", "config"}:
        return {
            "ok": True, "verb": verb,
            "thresholds": {"present": CONFIDENCE_PRESENT, "partial": CONFIDENCE_PARTIAL},
            "weights": {
                "substrate": WEIGHT_SUBSTRATE, "iphone": WEIGHT_IPHONE,
                "window": WEIGHT_WINDOW, "bluetooth": WEIGHT_BLUETOOTH,
                "voice": WEIGHT_VOICE,
            },
            "freshness_s": {
                "gps": GPS_FRESH_S, "ble": BLE_FRESH_S,
                "window": WINDOW_FRESH_S, "voice": VOICE_FRESH_S,
            },
            "homeworld_serial": HOMEWORLD_SERIAL,
        }
    return {"ok": False, "verb": verb, "error": "unknown verb"}


# ─── Self-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Architect Multimodal Identity — live read on M5 ===")
    snap = identity()
    print(f"confidence : {snap.confidence:.3f}")
    print(f"band       : {snap.band}")
    print()
    for m in snap.modalities:
        marker = "✓" if m.fresh and m.score > 0 else ("·" if m.fresh else "✗")
        print(f"  {marker} {m.name:10s} score={m.score:.2f} "
              f"weight={m.weight:.1f} weighted={m.weighted:.2f} "
              f"fresh={m.fresh} err={m.error}")
        for k, v in (m.evidence or {}).items():
            v_str = json.dumps(v) if not isinstance(v, str) else v
            if len(v_str) > 80:
                v_str = v_str[:77] + "..."
            print(f"      {k}: {v_str}")
    print()
    print(prompt_line())
