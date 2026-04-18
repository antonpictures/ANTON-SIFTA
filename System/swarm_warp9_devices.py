#!/usr/bin/env python3
"""
System/swarm_warp9_devices.py — External device input registry
══════════════════════════════════════════════════════════════════════
WARP 9 module 2 of 3.

Why this exists
---------------
Many SIFTA owners have only one Mac but plenty of other inputs:
Google Home, Amazon Alexa, smart bulbs, MQTT sensors, an old iPad
running a speedometer, the doorbell cam. The Architect wants the swarm
entity to treat them all as INPUTS — extra eyes, ears, microphones —
without inventing a new homeworld for each of them.

This module is the registry. Each external device gets a DeviceInput
record bound to one homeworld_serial (the Mac it's paired with) plus
an explicit consent timestamp from the owner. Vendors are pluggable —
we ship stub adapters for Google Home, Alexa, generic webhook, generic
MQTT — so the umbrella can ask "what devices does my owner have?"
without knowing about every brand.

Capability-first, vendor-second
-------------------------------
The capabilities dict (`can_speak`, `can_listen`, `can_actuate`,
`can_read_sensor`) is what callers branch on. Vendor identity is
metadata. This way the concierge module doesn't care whether the
"speak" channel is Alexa or Google Home — it just asks for any device
with `can_speak=True` and the registry returns the best match.

Owner consent gate
------------------
Every register_device() call REQUIRES a non-empty consent_signature —
even in test mode. Devices read sensors and actuate the physical world;
the bar is higher than for in-memory federation. No silent registration.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.swarm_owner_identity import (
    detect_self_homeworld_serial,
    get_or_create_owner,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DEVICE_REGISTRY = _STATE / "warp9_device_registry.jsonl"
_DEVICE_SIGNALS = _STATE / "warp9_device_signals.jsonl"

MODULE_VERSION = "2026-04-18.warp9.devices.v1"


# ──────────────────────────────────────────────────────────────────────
# Capability vocabulary — keep tight; expand only when needed
# ──────────────────────────────────────────────────────────────────────

CAPABILITY_KEYS = (
    "can_speak",          # text-to-speech / audio output
    "can_listen",         # microphone / speech-to-text
    "can_actuate",        # toggle a switch, change a light, set a thermostat
    "can_read_sensor",    # temperature, motion, presence, lux, etc.
    "can_show_screen",    # display surface (smart display, TV, tablet)
    "can_capture_image",  # camera (doorbell, webcam-on-tablet, etc.)
)

# Known vendor short codes — open set; new vendors land as new strings.
KNOWN_VENDORS = (
    "google_home",
    "amazon_alexa",
    "apple_homepod",
    "homekit_generic",
    "matter_generic",
    "mqtt_generic",
    "webhook_generic",
    "philips_hue",
    "ring",
    "nest",
    "shelly",
    "arduino_serial",
    "raspberrypi",
)


@dataclass
class DeviceInput:
    """One external device the owner has plugged into their swarm."""
    device_id: str                          # uuid hex, stable across renames
    nickname: str                           # owner-facing label, e.g. "Kitchen Echo"
    vendor: str                             # one of KNOWN_VENDORS or a free-form string
    homeworld_serial: str                   # which Mac is paired with this device
    owner_id_key: str                       # whose device this is
    transport: str                          # "lan_mdns" | "cloud_api" | "ble" | "mqtt" | "serial" | "webhook"
    capabilities: Dict[str, bool]           # subset of CAPABILITY_KEYS -> True
    scopes: List[str]                       # explicit scopes owner granted, e.g. ["read:weather","write:kitchen_light"]
    consent_signature: str                  # MUST be non-empty
    consent_ts: float
    registered_ts: float = field(default_factory=time.time)
    last_seen_ts: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceSignal:
    """One signal emitted by a device into the swarm's sensorium."""
    signal_id: str
    device_id: str
    homeworld_serial: str
    kind: str                               # "speech_in" | "sensor_reading" | "image_frame" | "actuation_ack" | ...
    payload: Dict[str, Any]
    ts: float = field(default_factory=time.time)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Registry CRUD
# ──────────────────────────────────────────────────────────────────────

class DeviceConsentMissingError(ValueError):
    """Raised when register_device() is called without a consent signature."""


def register_device(
    nickname: str,
    vendor: str,
    *,
    transport: str,
    capabilities: Dict[str, bool],
    scopes: List[str],
    consent_signature: str,
    owner_label: str = "IOAN",
    homeworld_serial: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DeviceInput:
    """Add a device to the registry. Refuses without explicit consent."""
    if not consent_signature or not consent_signature.strip():
        raise DeviceConsentMissingError(
            "register_device requires a non-empty consent_signature; "
            "no silent device registration. Even in test mode, "
            "pass consent_signature='test_consent' explicitly."
        )

    # Validate capability keys — typos are a silent bug class.
    bad = [k for k in capabilities.keys() if k not in CAPABILITY_KEYS]
    if bad:
        raise ValueError(
            f"unknown capability key(s) {bad}; expected subset of {CAPABILITY_KEYS}"
        )

    owner = get_or_create_owner(owner_label)
    device = DeviceInput(
        device_id=uuid.uuid4().hex[:16],
        nickname=nickname,
        vendor=vendor,
        homeworld_serial=homeworld_serial or detect_self_homeworld_serial(),
        owner_id_key=owner.key,
        transport=transport,
        capabilities=dict(capabilities),
        scopes=list(scopes),
        consent_signature=consent_signature,
        consent_ts=time.time(),
        metadata=metadata or {},
    )
    _DEVICE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with _DEVICE_REGISTRY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(device.to_dict(), ensure_ascii=False) + "\n")
    return device


def list_devices_for_homeworld(
    homeworld_serial: Optional[str] = None,
    *,
    capability: Optional[str] = None,
) -> List[DeviceInput]:
    """Return latest record per device_id for a homeworld, optionally
    filtered to those with `capability=True`."""
    serial = homeworld_serial or detect_self_homeworld_serial()
    if not _DEVICE_REGISTRY.exists():
        return []
    latest: Dict[str, DeviceInput] = {}
    try:
        with _DEVICE_REGISTRY.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    dev = DeviceInput(**row)
                except Exception:
                    continue
                if dev.homeworld_serial != serial:
                    continue
                latest[dev.device_id] = dev
    except OSError:
        return []
    devices = list(latest.values())
    if capability is not None:
        devices = [d for d in devices if d.capabilities.get(capability)]
    return devices


def find_device_by_capability(capability: str, *, homeworld_serial: Optional[str] = None) -> Optional[DeviceInput]:
    """Concierge helper: pick the most-recently-seen device that can do X."""
    devs = list_devices_for_homeworld(homeworld_serial, capability=capability)
    if not devs:
        return None
    return max(devs, key=lambda d: max(d.last_seen_ts, d.registered_ts))


# ──────────────────────────────────────────────────────────────────────
# Signal emission — devices push readings into the swarm sensorium
# ──────────────────────────────────────────────────────────────────────

def emit_device_signal(device_id: str, kind: str, payload: Dict[str, Any], *, confidence: float = 1.0) -> Optional[DeviceSignal]:
    """Append a DeviceSignal to .sifta_state/warp9_device_signals.jsonl
    so other modules (concierge, eye-stack future device lane) can tail it."""
    serial = detect_self_homeworld_serial()
    sig = DeviceSignal(
        signal_id=uuid.uuid4().hex[:16],
        device_id=device_id,
        homeworld_serial=serial,
        kind=kind,
        payload=payload,
        confidence=max(0.0, min(1.0, float(confidence))),
    )
    try:
        _DEVICE_SIGNALS.parent.mkdir(parents=True, exist_ok=True)
        with _DEVICE_SIGNALS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(sig.to_dict(), ensure_ascii=False) + "\n")
        return sig
    except OSError:
        return None


def recent_device_signals(*, kind: Optional[str] = None, since_ts: float = 0.0, limit: int = 100) -> List[DeviceSignal]:
    if not _DEVICE_SIGNALS.exists():
        return []
    out: List[DeviceSignal] = []
    try:
        with _DEVICE_SIGNALS.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    sig = DeviceSignal(**row)
                except Exception:
                    continue
                if sig.ts < since_ts:
                    continue
                if kind and sig.kind != kind:
                    continue
                out.append(sig)
    except OSError:
        return []
    return out[-limit:]


# ──────────────────────────────────────────────────────────────────────
# Vendor-stub adapters — minimum-viable, replaceable by real bridges
# ──────────────────────────────────────────────────────────────────────

def stub_google_home_say(device: DeviceInput, text: str) -> bool:
    """Pretend to send a TTS request to Google Home. Real impl would use
    the cast SDK or the Assistant Relay project; this stub just journals
    the intent and returns True so the rest of the stack flows."""
    if not device.capabilities.get("can_speak"):
        return False
    emit_device_signal(device.device_id, "actuation_intent",
                       {"action": "say", "text": text[:500], "vendor_stub": True})
    return True


def stub_alexa_say(device: DeviceInput, text: str) -> bool:
    if not device.capabilities.get("can_speak"):
        return False
    emit_device_signal(device.device_id, "actuation_intent",
                       {"action": "say", "text": text[:500], "vendor_stub": True})
    return True


def stub_webhook_post(device: DeviceInput, payload: Dict[str, Any]) -> bool:
    """Generic outbound webhook stub. Real impl would urllib.request.urlopen."""
    emit_device_signal(device.device_id, "actuation_intent",
                       {"action": "webhook_post", "payload": payload, "vendor_stub": True})
    return True


# Vendor dispatch table — concierge calls this rather than knowing brands.
SAY_DISPATCH = {
    "google_home": stub_google_home_say,
    "amazon_alexa": stub_alexa_say,
    "apple_homepod": stub_google_home_say,    # same shape; reuse stub
}


def speak_via_best_device(text: str, *, homeworld_serial: Optional[str] = None) -> Optional[str]:
    """Concierge convenience: find any speaker, route the text. Returns the
    nickname of the device used or None if none available."""
    dev = find_device_by_capability("can_speak", homeworld_serial=homeworld_serial)
    if not dev:
        return None
    fn = SAY_DISPATCH.get(dev.vendor, stub_google_home_say)
    if fn(dev, text):
        return dev.nickname
    return None


if __name__ == "__main__":
    print(f"[C47H-SMOKE-WARP9-DEV] homeworld={detect_self_homeworld_serial()}")

    # Refuse without consent (M5 sanity)
    try:
        register_device("bad", "google_home", transport="lan_mdns",
                        capabilities={"can_speak": True}, scopes=[],
                        consent_signature="")
        print("[C47H-SMOKE-WARP9-DEV] FAIL: registration without consent should have raised")
    except DeviceConsentMissingError:
        print("[C47H-SMOKE-WARP9-DEV] OK: consent gate refused empty signature")

    # Real (test-mode) registration
    dev = register_device(
        nickname="Kitchen Echo (smoke)",
        vendor="amazon_alexa",
        transport="cloud_api",
        capabilities={"can_speak": True, "can_listen": True},
        scopes=["read:speech_in", "write:tts"],
        consent_signature="test_consent_smoke",
        metadata={"room": "kitchen"},
    )
    print(f"[C47H-SMOKE-WARP9-DEV] registered: {dev.nickname} id={dev.device_id} vendor={dev.vendor}")

    # List + capability filter
    speakers = list_devices_for_homeworld(capability="can_speak")
    print(f"[C47H-SMOKE-WARP9-DEV] speakers on this homeworld: {len(speakers)}")

    # Concierge route
    used = speak_via_best_device("Welcome home, Architect.")
    print(f"[C47H-SMOKE-WARP9-DEV] speak_via_best_device -> {used}")

    # Recent signals
    sigs = recent_device_signals(since_ts=time.time() - 60)
    print(f"[C47H-SMOKE-WARP9-DEV] recent device signals (last 60s): {len(sigs)}")

    print("[C47H-SMOKE-WARP9-DEV OK]")
