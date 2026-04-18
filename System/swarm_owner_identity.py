#!/usr/bin/env python3
"""
System/swarm_owner_identity.py — Owner-above-Homeworld identity layer
══════════════════════════════════════════════════════════════════════
Substrate for the Warp 9 stack (federation, devices, concierge).

Naming clarification (per Architect's distributed-trust model):
  owner_id          — the human who owns the silicon. Stable across machines.
  architect_id      — the (owner, machine) pair, e.g. "IOAN_M5", "IOAN_M1".
  homeworld_serial  — the silicon itself, e.g. "GTH4921YP3" (M5 Mac Pro).

Why this exists
---------------
Today every JSONL row is anchored to one homeworld_serial. That works
for single-machine installs, and it's the right default for distribution
(each user's hardware is their own sovereign). But the Architect owns
multiple machines (M5 Mac Pro + M1 Mac Mini), and wants their swarm
entity to swim freely across them with proper consent.

This module provides the missing layer: a stable owner_id that sits ABOVE
homeworld_serial, plus an explicit federation registry so cross-machine
modules know which serials belong to the same human.

TEST MODE vs REAL MODE
----------------------
Default: federation OFF — each homeworld pretends to be its own owner.
This preserves the dev/test discipline the Architect explicitly asked for
("we have to agree to treat the machines sometimes as separate owners").

Opt in: set SIFTA_OWNER_FEDERATION=1 in the environment, OR call
register_homeworld() with explicit owner consent.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

OWNER_REGISTRY = _STATE / "owner_registry.json"
HOMEWORLD_FEDERATION = _STATE / "homeworld_federation.jsonl"

MODULE_VERSION = "2026-04-18.warp9.owner_identity.v1"

# Federation gate. Default OFF for safety + test discipline.
FEDERATION_ENABLED = os.environ.get("SIFTA_OWNER_FEDERATION", "0") == "1"


@dataclass
class OwnerID:
    """A stable identifier for the human owner of one or more SIFTA installs.

    `key` is a salted hash so we never have to write the architect's email
    or any other PII to disk in plaintext.
    """
    key: str                              # short hex hash, e.g. "ioan_a3f1d4"
    label: str                            # human-readable, e.g. "IOAN"
    created_ts: float = field(default_factory=time.time)
    salt: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HomeworldRecord:
    """One machine that an owner controls."""
    owner_id_key: str                     # foreign key -> OwnerID.key
    homeworld_serial: str                 # e.g. "GTH4921YP3"
    architect_id: str                     # e.g. "IOAN_M5"
    machine_label: str                    # e.g. "M5 Mac Pro"
    role: str                             # "primary" | "peer" | "sentry" | "device_hub"
    registered_ts: float = field(default_factory=time.time)
    consent_signature: str = ""           # owner explicitly consented to federation
    capabilities: List[str] = field(default_factory=list)  # e.g. ["screen_capture","website_host"]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Owner registry (JSON, single-file, small — never grows large)
# ──────────────────────────────────────────────────────────────────────

def _load_owner_registry() -> Dict[str, OwnerID]:
    if not OWNER_REGISTRY.exists():
        return {}
    try:
        raw = json.loads(OWNER_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: OwnerID(**v) for k, v in raw.items()}


def _save_owner_registry(reg: Dict[str, OwnerID]) -> None:
    OWNER_REGISTRY.write_text(
        json.dumps({k: v.to_dict() for k, v in reg.items()}, indent=2),
        encoding="utf-8",
    )


def _derive_owner_key(label: str, salt: str) -> str:
    """Stable short hash. salt is owner-specific; label is human-readable."""
    h = hashlib.sha256(f"{label}|{salt}".encode("utf-8")).hexdigest()[:6]
    return f"{label.lower()}_{h}"


def get_or_create_owner(label: str, *, persist: bool = True) -> OwnerID:
    """Return the OwnerID for `label`, creating a fresh salt+key if absent."""
    reg = _load_owner_registry()
    for owner in reg.values():
        if owner.label == label:
            return owner
    salt = uuid.uuid4().hex[:8]
    key = _derive_owner_key(label, salt)
    owner = OwnerID(key=key, label=label, salt=salt)
    if persist:
        reg[key] = owner
        _save_owner_registry(reg)
    return owner


def get_owner_by_key(key: str) -> Optional[OwnerID]:
    reg = _load_owner_registry()
    return reg.get(key)


# ──────────────────────────────────────────────────────────────────────
# Federation registry (JSONL append-only — auditable history)
# ──────────────────────────────────────────────────────────────────────

def register_homeworld(
    owner_id_key: str,
    homeworld_serial: str,
    *,
    architect_id: str,
    machine_label: str,
    role: str = "peer",
    capabilities: Optional[List[str]] = None,
    consent_signature: str = "",
    notes: str = "",
) -> HomeworldRecord:
    """
    Append a federation row binding a homeworld to an owner. Idempotent
    on (owner_id_key, homeworld_serial) — re-registering the same pair
    just appends a new row (audit trail of capability/role updates).

    `consent_signature` SHOULD be a non-empty string when joining a
    federation in real-mode (the owner explicitly consented). For test
    mode, "" is allowed.
    """
    record = HomeworldRecord(
        owner_id_key=owner_id_key,
        homeworld_serial=homeworld_serial,
        architect_id=architect_id,
        machine_label=machine_label,
        role=role,
        capabilities=capabilities or [],
        consent_signature=consent_signature,
        notes=notes,
    )
    HOMEWORLD_FEDERATION.parent.mkdir(parents=True, exist_ok=True)
    with HOMEWORLD_FEDERATION.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return record


def list_owner_homeworlds(owner_id_key: str) -> List[HomeworldRecord]:
    """Return the latest record for each (owner, homeworld_serial) pair.

    Multiple rows for the same homeworld_serial are collapsed to the
    most-recent one (so capability/role changes win).
    """
    if not HOMEWORLD_FEDERATION.exists():
        return []
    latest: Dict[str, HomeworldRecord] = {}
    try:
        with HOMEWORLD_FEDERATION.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("owner_id_key") != owner_id_key:
                    continue
                serial = row.get("homeworld_serial", "")
                latest[serial] = HomeworldRecord(**row)
    except OSError:
        return []
    return list(latest.values())


def is_federated(owner_id_key: str, homeworld_serial: str) -> bool:
    """Returns True iff `homeworld_serial` is registered for `owner_id_key`
    AND federation mode is currently enabled (env var or explicit kwarg).
    """
    if not FEDERATION_ENABLED:
        return False
    for rec in list_owner_homeworlds(owner_id_key):
        if rec.homeworld_serial == homeworld_serial:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Self-identification helpers — what machine am I right now?
# ──────────────────────────────────────────────────────────────────────

def detect_self_homeworld_serial() -> str:
    """Best-effort: read the homeworld_serial baked into existing SIFTA
    state. Falls back to socket.gethostname() if no anchors exist yet.
    """
    # Heartbeat web_anchors carry an architect_id like "IOAN_M5".
    anchors = _STATE / "heartbeats" / "web_anchors.jsonl"
    if anchors.exists():
        try:
            with anchors.open("r", encoding="utf-8") as fh:
                for line in reversed(fh.readlines()):
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    sig = row.get("signal_text", "")
                    # signal_text format: SIFTA: [SIG:<serial>:...]
                    if "[SIG:" in sig:
                        try:
                            serial = sig.split("[SIG:")[1].split(":")[0]
                            if serial:
                                return serial
                        except Exception:
                            pass
        except OSError:
            pass
    # Fallback — derive a stable token from the hostname.
    return f"HOST_{hashlib.sha256(socket.gethostname().encode()).hexdigest()[:10]}"


def detect_self_architect_id(default_owner_label: str = "IOAN") -> str:
    """Return architect_id of the form "<OWNER>_<machine_short>"."""
    serial = detect_self_homeworld_serial()
    # M5 Mac Pro = GTH4921YP3, M1 Mac Mini = C07FL0JAQ6NV (per existing state)
    short_map = {
        "GTH4921YP3": "M5",
        "C07FL0JAQ6NV": "M1",
    }
    short = short_map.get(serial, serial[:4])
    return f"{default_owner_label}_{short}"


if __name__ == "__main__":
    print(f"[C47H-SMOKE-OWNER] FEDERATION_ENABLED={FEDERATION_ENABLED}")
    self_serial = detect_self_homeworld_serial()
    self_arch = detect_self_architect_id()
    print(f"[C47H-SMOKE-OWNER] self_homeworld_serial={self_serial}")
    print(f"[C47H-SMOKE-OWNER] self_architect_id={self_arch}")

    owner = get_or_create_owner("IOAN")
    print(f"[C47H-SMOKE-OWNER] owner.key={owner.key} label={owner.label}")

    rec = register_homeworld(
        owner.key, self_serial,
        architect_id=self_arch,
        machine_label="M5 Mac Pro" if self_serial == "GTH4921YP3" else "unknown",
        role="primary",
        capabilities=["screen_capture", "swarm_eye_t65", "ide_cursor"],
        notes="self-registration on smoke",
    )
    print(f"[C47H-SMOKE-OWNER] registered: {rec.homeworld_serial} role={rec.role}")

    homeworlds = list_owner_homeworlds(owner.key)
    print(f"[C47H-SMOKE-OWNER] owner has {len(homeworlds)} homeworld(s):")
    for h in homeworlds:
        print(f"    - {h.architect_id} ({h.homeworld_serial}) role={h.role} caps={h.capabilities}")

    print(f"[C47H-SMOKE-OWNER] is_federated(owner, self): {is_federated(owner.key, self_serial)}")
    print("[C47H-SMOKE-OWNER OK]")
