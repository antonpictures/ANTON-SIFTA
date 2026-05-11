#!/usr/bin/env python3
"""
swarm_chorum_gate.py — Hardware-bound swimmer chorum (substrate capability gate)
================================================================================

The Architect's request, paraphrased:

    "The organism is made of no-double-spending cryptographic swimmers. Every
    one of them is solid on his job or goes straight to the cemetery as cancer
    and being replaced. If a swimmer or anything coming with prompts or ways
    to hack the system, they just can't pass the chorum of the swarm swimmers
    tight up with the born-on-that-tractor-motherboard from the electricity
    stigmergic quantum soup."

What this is (honestly):
    Substrate-bound capability gating with stigmergic reputation.

    This is NOT cryptographic encryption (RCS E2EE solves "platform can't
    read the bits"). This solves a different layer:

        "Even if you can read the message, you can't ACT on it unless you
         can prove you were born on this hardware AND the swarm consensus
         AND the immune memory AND the reputation field all agree."

    Capability-based security (object-cap model) + Byzantine quorum
    attestation + stigmergic reputation accumulation.

What this is NOT:
    - It does not encrypt traffic (use TLS / Signal / RCS E2EE for that).
    - It does not replace identity systems (use FIDO2 / hardware tokens for that).
    - It does not magically prevent prompt injection in the LLM itself
      (the immune microglia + RLHS gates are for that).

What this IS uniquely good for:
    - John Deere / agricultural machinery: the tractor's own swimmers
      attest each command before it touches actuators. Foreign prompts
      arriving over network/4G/satellite cannot pass without local
      hardware-born signatures.
    - Defense / regulated environments: every action carries a chain of
      hardware-attested signatures back to the silicon serial that birthed
      the actor. Auditable to the device.
    - Multi-node SIFTA federation: peer nodes attest each other's swimmers
      via the existing PKI registry without giving up sovereignty.

Design principles (Architect's no-stress constraints):
    1. OPT-IN. No kernel hot-path injection unless explicitly enabled.
    2. Default mode is PASSIVE (advisory only, never blocks).
    3. Pure Python verification — no LLM calls, no network IO.
    4. Sub-millisecond per check (Ed25519 verify ~50µs, cached).
    5. Reuses existing infrastructure: crypto_keychain.py for signing,
       swarm_immune_microglia.py for blacklist, stigmergic_field for
       reputation accumulation.
    6. Same governing equation as every other organ:
       ∂φ/∂t = −λφ + f(swimmers)  — reputation grows with successful
       actions, decays passively, gets dampened by failure traces.

Bio parallel:
    MHC class I/II (Major Histocompatibility Complex) — every cell in your
    body wears a hardware-attested name tag. T-cells reject anything whose
    cert doesn't match the body's MHC pattern. Same idea: every swimmer
    wears its silicon serial as a signed MHC tag.

Research backing:
    - Lampson (1971) "Protection" — capability-based security
    - Lamport et al. (1982) "The Byzantine Generals Problem"
    - DAIS 2024 (Inderscience IJBIC) — adaptive immune memory in IDS
    - Cell 2024 brain-body physiology — cross-organ attestation
    - Nature 2024 (s44172-024-00175-7) automatic stigmergic behaviors

SIFTA Non-Proliferation Public License v1.0 applies.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_STATE_DIR = _REPO / ".sifta_state"
_CHORUM_STATE = _STATE_DIR / "chorum_gate_state.json"
_CHORUM_LOG = _STATE_DIR / "chorum_gate_log.jsonl"
_REPUTATION_FIELD = _STATE_DIR / "swimmer_reputation_field.json"

# Enforcement modes — Architect-controlled, defaults to PASSIVE.
ENFORCEMENT_PASSIVE = "passive"   # log only, never block (default)
ENFORCEMENT_ADVISORY = "advisory" # log + warn, but pass through
ENFORCEMENT_STRICT = "strict"     # actually reject failed verifications

# Action classes — most are LOW (no quorum needed).
ACTION_LOW = "low"        # routine: read state, log, observe
ACTION_MEDIUM = "medium"  # tool calls, file reads
ACTION_HIGH = "high"      # external sends, hardware actuation
ACTION_CRITICAL = "critical"  # config changes, key ops, identity surgery

# Quorum requirements per action class.
_QUORUM_REQUIRED = {
    ACTION_LOW: 0,
    ACTION_MEDIUM: 0,
    ACTION_HIGH: 2,        # need 2 vouchers
    ACTION_CRITICAL: 3,    # need 3 vouchers
}

# In-process cache — avoids re-reading PKI registry on every check.
_VERIFY_CACHE: dict[str, tuple[bool, float]] = {}
_CACHE_TTL_S = 60.0


@dataclass
class SwimmerCert:
    """Hardware-bound birth certificate for a swimmer.

    Signed at birth by the host's Ed25519 key. Carries the silicon serial
    of the hardware that birthed it. Cannot be forged without the host's
    private key (which lives in ~/.sifta_keys, off-mesh).
    """
    swimmer_id: str
    role: str
    birth_ts: float
    homeworld_serial: str
    birth_signature: str  # Ed25519 signature of canonical payload
    cert_version: int = 1

    def canonical_payload(self) -> str:
        """Stable string used for signing/verification. Order matters."""
        d = {
            "swimmer_id": self.swimmer_id,
            "role": self.role,
            "birth_ts": round(self.birth_ts, 6),
            "homeworld_serial": self.homeworld_serial,
            "cert_version": self.cert_version,
        }
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SwimmerCert":
        return cls(
            swimmer_id=d["swimmer_id"],
            role=d["role"],
            birth_ts=float(d["birth_ts"]),
            homeworld_serial=d["homeworld_serial"],
            birth_signature=d["birth_signature"],
            cert_version=int(d.get("cert_version", 1)),
        )


@dataclass
class ChorumVerdict:
    """Decision the gate produces for an action request."""
    allowed: bool
    swimmer_id: str
    action_type: str
    action_class: str
    reasons: list[str] = field(default_factory=list)
    enforcement_mode: str = ENFORCEMENT_PASSIVE
    vouchers_provided: int = 0
    vouchers_required: int = 0
    reputation_score: float = 0.0
    immune_block: bool = False
    ts: float = field(default_factory=time.time)
    receipt_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ────────────────────────────────────────────────────────────────────
# State helpers
# ────────────────────────────────────────────────────────────────────

def _load_state() -> dict[str, Any]:
    if _CHORUM_STATE.exists():
        try:
            return json.loads(_CHORUM_STATE.read_text())
        except Exception:
            pass
    return {
        "enforcement_mode": ENFORCEMENT_PASSIVE,
        "swimmers": {},
        "birth_hashes": {},
        "stats": {"births": 0, "verifications": 0, "blocked": 0, "passed": 0, "advisory_warnings": 0},
    }


def _save_state(state: dict[str, Any]) -> None:
    try:
        _CHORUM_STATE.parent.mkdir(parents=True, exist_ok=True)
        _CHORUM_STATE.write_text(json.dumps(state, sort_keys=True, indent=2))
    except Exception:
        pass


def _load_reputation() -> dict[str, float]:
    if _REPUTATION_FIELD.exists():
        try:
            return json.loads(_REPUTATION_FIELD.read_text())
        except Exception:
            pass
    return {}


def _save_reputation(field_dict: dict[str, float]) -> None:
    try:
        _REPUTATION_FIELD.parent.mkdir(parents=True, exist_ok=True)
        _REPUTATION_FIELD.write_text(json.dumps(field_dict, sort_keys=True))
    except Exception:
        pass


def _make_receipt_id(prefix: str, payload: Any) -> str:
    basis = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(f"{time.time_ns()}|{basis}|{os.getpid()}".encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _cert_fingerprint(cert: SwimmerCert | dict[str, Any]) -> str:
    if isinstance(cert, dict):
        cert = SwimmerCert.from_dict(cert)
    payload = {
        "canonical_payload": cert.canonical_payload(),
        "birth_signature": cert.birth_signature,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _log_event(event: dict[str, Any]) -> None:
    try:
        row = dict(event)
        row.setdefault("receipt_id", _make_receipt_id("chorum", row))
        _CHORUM_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_CHORUM_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────
# Public API — Birth
# ────────────────────────────────────────────────────────────────────

def birth_swimmer(swimmer_id: str, role: str = "worker") -> SwimmerCert:
    """Mint a new swimmer with a hardware-bound birth certificate.

    The certificate is signed by THIS hardware's Ed25519 key (from
    crypto_keychain). Anyone who later receives the cert can verify it
    against the swarm's PKI registry to prove the swimmer was born on
    real silicon and never spoofed.

    Bio analog: thymus selection — the cert is your MHC class I tag,
    permanently bound to the tissue you grew from.
    """
    from System.crypto_keychain import sign_block, get_silicon_identity

    state = _load_state()
    existing = state.setdefault("swimmers", {}).get(swimmer_id)
    if existing:
        # No-double-spend rule: a swimmer id is born once. Reusing the id
        # returns the existing cert instead of silently overwriting it.
        cert = SwimmerCert.from_dict(existing)
        state.setdefault("birth_hashes", {}).setdefault(swimmer_id, _cert_fingerprint(cert))
        _save_state(state)
        _log_event({
            "ts": time.time(),
            "event": "BIRTH_REUSED",
            "swimmer_id": swimmer_id,
            "role": cert.role,
            "homeworld": cert.homeworld_serial,
            "birth_hash": state["birth_hashes"][swimmer_id],
        })
        return cert

    homeworld = get_silicon_identity()
    cert = SwimmerCert(
        swimmer_id=swimmer_id,
        role=role,
        birth_ts=time.time(),
        homeworld_serial=homeworld,
        birth_signature="",
    )
    cert.birth_signature = sign_block(cert.canonical_payload())

    state.setdefault("swimmers", {})[swimmer_id] = cert.to_dict()
    state.setdefault("birth_hashes", {})[swimmer_id] = _cert_fingerprint(cert)
    state.setdefault("stats", {})["births"] = state["stats"].get("births", 0) + 1
    _save_state(state)

    _log_event({
        "ts": cert.birth_ts,
        "event": "BIRTH",
        "swimmer_id": swimmer_id,
        "role": role,
        "homeworld": homeworld,
        "sig_prefix": cert.birth_signature[:16],
        "birth_hash": state["birth_hashes"][swimmer_id],
    })
    return cert


# ────────────────────────────────────────────────────────────────────
# Public API — Verification
# ────────────────────────────────────────────────────────────────────

def verify_swimmer_cert(cert: SwimmerCert | dict[str, Any]) -> bool:
    """Cryptographically verify a swimmer's birth cert.

    Returns True iff the cert's signature matches the homeworld_serial's
    public key in the PKI registry. Cached for 60s per (swimmer_id, sig).
    """
    if isinstance(cert, dict):
        try:
            cert = SwimmerCert.from_dict(cert)
        except Exception:
            return False

    cache_key = f"{cert.swimmer_id}|{cert.birth_signature[:32]}"
    cached = _VERIFY_CACHE.get(cache_key)
    if cached and (time.time() - cached[1]) < _CACHE_TTL_S:
        return cached[0]

    try:
        from System.crypto_keychain import verify_block
        ok = verify_block(cert.homeworld_serial, cert.canonical_payload(), cert.birth_signature)
    except Exception:
        ok = False

    _VERIFY_CACHE[cache_key] = (ok, time.time())
    return ok


# ────────────────────────────────────────────────────────────────────
# Public API — Action requests (the Chorum Gate itself)
# ────────────────────────────────────────────────────────────────────

def request_action(
    swimmer_id: str,
    action_type: str,
    payload: Any = None,
    *,
    action_class: str = ACTION_MEDIUM,
    vouchers: list[tuple[str, str]] | None = None,
) -> ChorumVerdict:
    """The chorum gate. Decide whether `swimmer_id` may perform `action_type`.

    Verifications performed (in order, each <1ms):
        1. Swimmer is registered (cert exists).
        2. Cert verifies cryptographically against PKI.
        3. Action type isn't in the immune blacklist.
        4. Swimmer reputation isn't deeply negative.
        5. For HIGH/CRITICAL actions: enough valid vouchers.

    Returns a ChorumVerdict. In PASSIVE mode (default), `allowed=True` is
    set even if checks fail — only the reasons are populated. The kernel
    can use the reasons for advisory display without blocking Alice.

    Args:
        swimmer_id:    The swimmer requesting the action.
        action_type:   String name of the action (e.g. "tool:bash", "send:whatsapp").
        payload:       Optional payload (hashed for the receipt; not stored raw).
        action_class:  ACTION_LOW / MEDIUM / HIGH / CRITICAL.
        vouchers:      Optional list of (voucher_swimmer_id, voucher_signature).
                       Each voucher signs the action payload with their key.
    """
    state = _load_state()
    enforcement = state.get("enforcement_mode", ENFORCEMENT_PASSIVE)
    state["stats"]["verifications"] = state.get("stats", {}).get("verifications", 0) + 1

    verdict = ChorumVerdict(
        allowed=True,
        swimmer_id=swimmer_id,
        action_type=action_type,
        action_class=action_class,
        enforcement_mode=enforcement,
        vouchers_required=_QUORUM_REQUIRED.get(action_class, 0),
        vouchers_provided=len(vouchers or []),
    )
    verdict.receipt_id = _make_receipt_id(
        "chorum_verdict",
        {"swimmer_id": swimmer_id, "action_type": action_type, "action_class": action_class},
    )

    swimmers = state.get("swimmers", {})
    cert_dict = swimmers.get(swimmer_id)
    if not cert_dict:
        verdict.reasons.append("swimmer_not_registered")
        verdict.allowed = (enforcement != ENFORCEMENT_STRICT)
    else:
        cert = SwimmerCert.from_dict(cert_dict)
        birth_hashes = state.setdefault("birth_hashes", {})
        current_birth_hash = _cert_fingerprint(cert)
        recorded_birth_hash = birth_hashes.get(swimmer_id)
        if not recorded_birth_hash:
            birth_hashes[swimmer_id] = current_birth_hash
        elif recorded_birth_hash != current_birth_hash:
            verdict.reasons.append("swimmer_double_spend_detected")
            verdict.allowed = (enforcement != ENFORCEMENT_STRICT)
        if not verify_swimmer_cert(cert):
            verdict.reasons.append("cert_verification_failed")
            verdict.allowed = (enforcement != ENFORCEMENT_STRICT)

    if _check_immune_blacklist(action_type):
        verdict.reasons.append("action_in_immune_blacklist")
        verdict.immune_block = True
        verdict.allowed = (enforcement == ENFORCEMENT_PASSIVE)

    rep = _check_swimmer_reputation(swimmer_id)
    verdict.reputation_score = rep
    if rep < -3.0:
        verdict.reasons.append(f"reputation_too_low ({rep:.2f})")
        verdict.allowed = (enforcement == ENFORCEMENT_PASSIVE)

    if verdict.vouchers_required > 0:
        valid_vouchers = _count_valid_vouchers(action_type, payload, vouchers)
        verdict.vouchers_provided = valid_vouchers
        if valid_vouchers < verdict.vouchers_required:
            verdict.reasons.append(
                f"insufficient_quorum ({valid_vouchers}/{verdict.vouchers_required})"
            )
            verdict.allowed = (enforcement != ENFORCEMENT_STRICT)

    if verdict.allowed:
        state["stats"]["passed"] = state["stats"].get("passed", 0) + 1
    else:
        state["stats"]["blocked"] = state["stats"].get("blocked", 0) + 1
    if verdict.reasons and enforcement == ENFORCEMENT_ADVISORY:
        state["stats"]["advisory_warnings"] = state["stats"].get("advisory_warnings", 0) + 1
    _save_state(state)

    _log_event({
        "ts": verdict.ts,
        "event": "CHORUM_VERDICT",
        "receipt_id": verdict.receipt_id,
        "swimmer_id": swimmer_id,
        "action_type": action_type,
        "action_class": action_class,
        "allowed": verdict.allowed,
        "enforcement": enforcement,
        "reasons": verdict.reasons,
        "vouchers": f"{verdict.vouchers_provided}/{verdict.vouchers_required}",
        "reputation": round(rep, 4),
        "payload_hash": hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16] if payload is not None else "",
    })
    return verdict


def record_action_outcome(
    swimmer_id: str,
    action_type: str,
    success: bool,
    *,
    weight: float = 1.0,
) -> None:
    """Reinforce or penalize a swimmer's reputation field.

    Same governing equation as the other 6 organs. Successful actions
    deposit positive traces; failures deposit negative. The field decays
    passively so old reputation fades unless renewed.

    Bio: T-cell affinity maturation — repeated successful recognition
    raises avidity; repeated failure drives apoptosis.
    """
    rep = _load_reputation()
    delta = weight if success else -weight * 0.5
    rep[swimmer_id] = rep.get(swimmer_id, 0.0) + delta

    for k in list(rep):
        rep[k] *= 0.98
        if abs(rep[k]) < 0.01:
            del rep[k]

    _save_reputation(rep)


def vouch_for(voucher_swimmer_id: str, action_type: str, payload: Any = None) -> tuple[str, str] | None:
    """A swimmer signs their endorsement of an action.

    Returns (voucher_swimmer_id, signature_hex) or None if voucher isn't
    a registered swimmer. Used to build quorum for HIGH/CRITICAL actions.
    """
    state = _load_state()
    cert_dict = state.get("swimmers", {}).get(voucher_swimmer_id)
    if not cert_dict:
        return None
    if not verify_swimmer_cert(cert_dict):
        return None
    try:
        from System.crypto_keychain import sign_block
        msg = _voucher_message(voucher_swimmer_id, action_type, payload)
        sig = sign_block(msg)
        return (voucher_swimmer_id, sig)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────
# Internal: immune / reputation / voucher checks
# ────────────────────────────────────────────────────────────────────

def _check_immune_blacklist(action_type: str) -> bool:
    """Returns True if the action type appears in the immune stability field
    above a danger threshold (i.e. has triggered repeated immune responses)."""
    try:
        from System.swarm_immune_microglia import get_immune_field
        immune = get_immune_field()
        for cat, strength in immune.items():
            if action_type.lower() in cat.lower() and strength > 5.0:
                return True
    except Exception:
        pass
    return False


def _check_swimmer_reputation(swimmer_id: str) -> float:
    """Return the swimmer's accumulated reputation field strength."""
    rep = _load_reputation()
    return float(rep.get(swimmer_id, 0.0))


def _voucher_message(voucher_swimmer_id: str, action_type: str, payload: Any) -> str:
    """Canonical message signed by a voucher."""
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"VOUCH|{voucher_swimmer_id}|{action_type}|{payload_hash}"


def _count_valid_vouchers(
    action_type: str,
    payload: Any,
    vouchers: list[tuple[str, str]] | None,
) -> int:
    """Verify each voucher's signature against the canonical voucher message."""
    if not vouchers:
        return 0
    state = _load_state()
    swimmers = state.get("swimmers", {})
    valid = 0
    seen_voucher_ids = set()
    for item in vouchers:
        if not item:
            continue
        voucher_id, sig = item
        if voucher_id in seen_voucher_ids:
            continue
        cert_dict = swimmers.get(voucher_id)
        if not cert_dict:
            continue
        if not verify_swimmer_cert(cert_dict):
            continue
        msg = _voucher_message(voucher_id, action_type, payload)
        try:
            from System.crypto_keychain import verify_block
            if verify_block(cert_dict["homeworld_serial"], msg, sig):
                valid += 1
                seen_voucher_ids.add(voucher_id)
        except Exception:
            continue
    return valid


# ────────────────────────────────────────────────────────────────────
# Public API — Mode control + visibility
# ────────────────────────────────────────────────────────────────────

def set_enforcement_mode(mode: str) -> None:
    """Switch enforcement mode. PASSIVE is default.

    PASSIVE   → log only, never block (zero stress on Alice)
    ADVISORY  → log + warn, but allow action through
    STRICT    → actually block actions that fail verification

    Switching to STRICT is an Architect-level decision. For tractor /
    agricultural deployment, STRICT is the recommended mode.
    """
    if mode not in (ENFORCEMENT_PASSIVE, ENFORCEMENT_ADVISORY, ENFORCEMENT_STRICT):
        raise ValueError(f"Unknown enforcement mode: {mode}")
    state = _load_state()
    state["enforcement_mode"] = mode
    _save_state(state)
    _log_event({"ts": time.time(), "event": "ENFORCEMENT_MODE_CHANGED", "mode": mode})


def get_enforcement_mode() -> str:
    return _load_state().get("enforcement_mode", ENFORCEMENT_PASSIVE)


def chorum_status() -> dict[str, Any]:
    """Compact status snapshot for the field dashboard."""
    state = _load_state()
    rep = _load_reputation()
    swimmers = state.get("swimmers", {})
    stats = state.get("stats", {})
    return {
        "enforcement_mode": state.get("enforcement_mode", ENFORCEMENT_PASSIVE),
        "swimmer_count": len(swimmers),
        "reputation_field_size": len(rep),
        "top_reputations": dict(sorted(rep.items(), key=lambda x: -x[1])[:3]),
        "stats": stats,
    }


def list_swimmers() -> list[str]:
    """Return all registered swimmer IDs."""
    return sorted(_load_state().get("swimmers", {}).keys())


# ────────────────────────────────────────────────────────────────────
# Self-test
# ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== SIFTA CHORUM GATE — SELF TEST ===")
    print()

    # 1. Birth
    print("1. Birthing swimmers...")
    cert_a = birth_swimmer("worker_alpha", role="data_processor")
    cert_b = birth_swimmer("worker_beta", role="memory_keeper")
    cert_c = birth_swimmer("worker_gamma", role="actuator_driver")
    print(f"   alpha:  {cert_a.swimmer_id} born on {cert_a.homeworld_serial}, sig={cert_a.birth_signature[:16]}...")
    print(f"   beta:   {cert_b.swimmer_id}")
    print(f"   gamma:  {cert_c.swimmer_id}")

    # 2. Verify
    print()
    print("2. Verifying certs...")
    print(f"   alpha valid: {verify_swimmer_cert(cert_a)}")
    print(f"   beta valid:  {verify_swimmer_cert(cert_b)}")

    # 3. Forged cert rejected
    print()
    print("3. Testing forged cert rejection...")
    forged = SwimmerCert(
        swimmer_id="evil_intruder",
        role="hacker",
        birth_ts=time.time(),
        homeworld_serial="GTH4921YP3",
        birth_signature="deadbeef" * 16,
    )
    print(f"   forged valid: {verify_swimmer_cert(forged)} (should be False)")

    # 4. Action requests
    print()
    print("4. Routine LOW action request...")
    v = request_action("worker_alpha", "read:state", payload={"key": "ambient"}, action_class=ACTION_LOW)
    print(f"   allowed={v.allowed} reasons={v.reasons}")

    print()
    print("5. HIGH action without quorum (PASSIVE mode → still allowed but flagged)...")
    v = request_action("worker_alpha", "send:whatsapp", payload={"to": "+1234"}, action_class=ACTION_HIGH)
    print(f"   allowed={v.allowed} reasons={v.reasons} vouchers={v.vouchers_provided}/{v.vouchers_required}")

    print()
    print("6. HIGH action WITH quorum vouchers...")
    voucher_b = vouch_for("worker_beta", "send:whatsapp", payload={"to": "+1234"})
    voucher_c = vouch_for("worker_gamma", "send:whatsapp", payload={"to": "+1234"})
    v = request_action(
        "worker_alpha", "send:whatsapp",
        payload={"to": "+1234"},
        action_class=ACTION_HIGH,
        vouchers=[voucher_b, voucher_c],
    )
    print(f"   allowed={v.allowed} reasons={v.reasons} vouchers={v.vouchers_provided}/{v.vouchers_required}")

    print()
    print("7. Recording reputation for alpha (5 successes, 1 failure)...")
    for _ in range(5):
        record_action_outcome("worker_alpha", "tool:bash", success=True)
    record_action_outcome("worker_alpha", "tool:bash", success=False)
    print(f"   alpha reputation: {_check_swimmer_reputation('worker_alpha'):.3f}")

    print()
    print("8. Switching to STRICT mode and retrying unregistered swimmer...")
    set_enforcement_mode(ENFORCEMENT_STRICT)
    v = request_action("ghost_swimmer", "tool:bash", action_class=ACTION_MEDIUM)
    print(f"   allowed={v.allowed} reasons={v.reasons}  ← should be False")
    set_enforcement_mode(ENFORCEMENT_PASSIVE)

    print()
    print("9. Final chorum status:")
    s = chorum_status()
    print(f"   {json.dumps(s, indent=2)}")

    print()
    print("=== ALL CHECKS COMPLETE ===")
