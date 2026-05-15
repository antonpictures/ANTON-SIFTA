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

def _run_hardened_tests() -> int:
    """Hardened test suite: 20+ scenarios including STRICT mode, load, adversarial.

    Returns the number of failed tests. Designed to be called both as __main__
    and from external test harnesses. Uses a temporary state directory to avoid
    polluting Alice's real reputation/chorum state.
    """
    import tempfile
    import shutil
    passed = 0
    failed = 0

    global _CHORUM_STATE, _CHORUM_LOG, _REPUTATION_FIELD

    tmp_dir = Path(tempfile.mkdtemp(prefix="chorum_test_"))
    orig_state = _CHORUM_STATE
    orig_log = _CHORUM_LOG
    orig_rep = _REPUTATION_FIELD
    try:
        _CHORUM_STATE = tmp_dir / "chorum_gate_state.json"
        _CHORUM_LOG = tmp_dir / "chorum_gate_log.jsonl"
        _REPUTATION_FIELD = tmp_dir / "swimmer_reputation_field.json"
        _VERIFY_CACHE.clear()

        def _assert(cond: bool, label: str):
            nonlocal passed, failed
            if cond:
                passed += 1
                print(f"  [PASS] {label}")
            else:
                failed += 1
                print(f"  [FAIL] {label}")

        print("=== SIFTA CHORUM GATE — HARDENED TEST SUITE ===\n")

        # ── 1. Birth + idempotency ──────────────────────────────
        print("── Birth + Idempotency ──")
        ca = birth_swimmer("test_alpha", role="data_processor")
        _assert(ca.swimmer_id == "test_alpha", "1. birth returns correct id")
        _assert(len(ca.birth_signature) > 20, "2. birth signature is non-trivial")

        ca2 = birth_swimmer("test_alpha", role="SHOULD_NOT_OVERWRITE")
        _assert(ca2.role == "data_processor", "3. idempotent re-birth preserves original role")
        _assert(ca2.birth_signature == ca.birth_signature, "4. idempotent re-birth preserves signature")

        cb = birth_swimmer("test_beta", role="memory_keeper")
        cc = birth_swimmer("test_gamma", role="actuator_driver")
        cd = birth_swimmer("test_delta", role="scout")
        _assert(len(list_swimmers()) == 4, "5. four swimmers registered")

        # ── 2. Cert verification ────────────────────────────────
        print("\n── Certificate Verification ──")
        _assert(verify_swimmer_cert(ca), "6. alpha cert verifies")
        _assert(verify_swimmer_cert(cb), "7. beta cert verifies")

        forged = SwimmerCert(
            swimmer_id="evil_intruder", role="hacker",
            birth_ts=time.time(), homeworld_serial="GTH4921YP3",
            birth_signature="deadbeef" * 16,
        )
        _assert(not verify_swimmer_cert(forged), "8. forged cert rejected")

        tampered = SwimmerCert(
            swimmer_id=ca.swimmer_id, role=ca.role,
            birth_ts=ca.birth_ts, homeworld_serial=ca.homeworld_serial,
            birth_signature=ca.birth_signature[:-4] + "ffff",
        )
        _VERIFY_CACHE.clear()
        _assert(not verify_swimmer_cert(tampered), "9. tampered signature rejected")

        wrong_serial = SwimmerCert(
            swimmer_id="phantom", role="spy",
            birth_ts=time.time(), homeworld_serial="FAKE_SERIAL_123",
            birth_signature="0000" * 32,
        )
        _assert(not verify_swimmer_cert(wrong_serial), "10. wrong-serial cert rejected")

        # ── 3. PASSIVE mode — everything passes with reasons ────
        print("\n── PASSIVE Mode (default) ──")
        set_enforcement_mode(ENFORCEMENT_PASSIVE)
        v = request_action("test_alpha", "read:state", action_class=ACTION_LOW)
        _assert(v.allowed, "11. LOW action allowed in PASSIVE")
        _assert(len(v.receipt_id) > 10, "12. verdict carries receipt_id")

        v = request_action("test_alpha", "send:whatsapp", action_class=ACTION_HIGH)
        _assert(v.allowed, "13. HIGH action without quorum still allowed in PASSIVE")
        _assert("insufficient_quorum" in " ".join(v.reasons), "14. quorum deficiency flagged")

        v = request_action("ghost_nobody", "tool:bash", action_class=ACTION_MEDIUM)
        _assert(v.allowed, "15. unregistered swimmer allowed in PASSIVE")
        _assert("swimmer_not_registered" in v.reasons, "16. unregistered reason recorded")

        # ── 4. ADVISORY mode — warns but passes ────────────────
        print("\n── ADVISORY Mode ──")
        set_enforcement_mode(ENFORCEMENT_ADVISORY)
        v = request_action("ghost_nobody", "tool:bash", action_class=ACTION_MEDIUM)
        _assert(v.allowed, "17. unregistered swimmer still allowed in ADVISORY")
        state_check = _load_state()
        _assert(state_check["stats"].get("advisory_warnings", 0) > 0, "18. advisory warning counter incremented")

        # ── 5. STRICT mode — actually blocks ────────────────────
        print("\n── STRICT Mode (blocks) ──")
        set_enforcement_mode(ENFORCEMENT_STRICT)

        v = request_action("ghost_nobody", "tool:bash", action_class=ACTION_MEDIUM)
        _assert(not v.allowed, "19. unregistered swimmer BLOCKED in STRICT")

        # Ensure verify cache is warm for test swimmers
        _VERIFY_CACHE.clear()
        state_check2 = _load_state()
        for sid in ("test_alpha", "test_beta", "test_gamma", "test_delta"):
            cd = state_check2.get("swimmers", {}).get(sid)
            if cd:
                verify_swimmer_cert(cd)

        v = request_action("test_alpha", "tool:bash", action_class=ACTION_LOW)
        if not v.allowed:
            print(f"    DEBUG: reasons={v.reasons}")
        _assert(v.allowed, "20. registered swimmer passes LOW action in STRICT")

        v = request_action("test_alpha", "actuate:steering", action_class=ACTION_HIGH)
        _assert(not v.allowed, "21. HIGH action without quorum BLOCKED in STRICT")

        v_b = vouch_for("test_beta", "actuate:steering", payload=None)
        v_c = vouch_for("test_gamma", "actuate:steering", payload=None)
        _assert(v_b is not None, "22. beta can vouch")
        _assert(v_c is not None, "23. gamma can vouch")

        v = request_action("test_alpha", "actuate:steering", action_class=ACTION_HIGH,
                           vouchers=[v_b, v_c])
        _assert(v.allowed, "24. HIGH action with 2 vouchers passes STRICT")
        _assert(v.vouchers_provided == 2, "25. voucher count correct")

        # CRITICAL needs 3 vouchers
        v_d = vouch_for("test_delta", "deploy:firmware", payload={"version": "1.2"})
        v = request_action("test_alpha", "deploy:firmware",
                           payload={"version": "1.2"}, action_class=ACTION_CRITICAL,
                           vouchers=[v_b, v_c])
        _assert(not v.allowed, "26. CRITICAL with 2/3 vouchers BLOCKED in STRICT")

        v_b2 = vouch_for("test_beta", "deploy:firmware", payload={"version": "1.2"})
        v_c2 = vouch_for("test_gamma", "deploy:firmware", payload={"version": "1.2"})
        v = request_action("test_alpha", "deploy:firmware",
                           payload={"version": "1.2"}, action_class=ACTION_CRITICAL,
                           vouchers=[v_b2, v_c2, v_d])
        _assert(v.allowed, "27. CRITICAL with 3/3 vouchers passes STRICT")

        # ── 6. Duplicate voucher rejection ──────────────────────
        print("\n── Duplicate / Replay Voucher Rejection ──")
        dup_v = vouch_for("test_beta", "actuate:brake", payload=None)
        v = request_action("test_alpha", "actuate:brake", action_class=ACTION_HIGH,
                           vouchers=[dup_v, dup_v])
        _assert(v.vouchers_provided == 1, "28. duplicate voucher counted only once")
        _assert(not v.allowed, "29. duplicate vouchers don't reach quorum in STRICT")

        # ── 7. Reputation-based blocking ────────────────────────
        print("\n── Reputation-Based Gating ──")
        for _ in range(20):
            record_action_outcome("test_alpha", "tool:bash", success=False)
        rep_score = _check_swimmer_reputation("test_alpha")
        _assert(rep_score < -3.0, f"30. 20 failures → reputation deeply negative ({rep_score:.2f})")

        v = request_action("test_alpha", "read:state", action_class=ACTION_LOW)
        _assert(not v.allowed, "31. deeply-negative-reputation swimmer BLOCKED in STRICT")
        _assert(any("reputation_too_low" in r for r in v.reasons), "32. reputation reason present")

        # Rehabilitate
        for _ in range(40):
            record_action_outcome("test_alpha", "tool:bash", success=True)
        rep_after = _check_swimmer_reputation("test_alpha")
        _assert(rep_after > -3.0, f"33. rehabilitation restores reputation ({rep_after:.2f})")

        # ── 8. Receipt uniqueness ───────────────────────────────
        print("\n── Receipt Uniqueness ──")
        receipt_ids = set()
        for i in range(50):
            v = request_action("test_alpha", f"action_{i}", action_class=ACTION_LOW)
            receipt_ids.add(v.receipt_id)
        _assert(len(receipt_ids) == 50, f"34. 50 verdicts → 50 unique receipt IDs ({len(receipt_ids)})")

        # ── 9. Load benchmark ───────────────────────────────────
        print("\n── Load Benchmark (1000 action requests) ──")
        set_enforcement_mode(ENFORCEMENT_PASSIVE)
        t0 = time.perf_counter()
        for i in range(1000):
            request_action("test_alpha", "tool:bash", action_class=ACTION_LOW)
        elapsed = time.perf_counter() - t0
        per_req_us = (elapsed / 1000) * 1_000_000
        _assert(elapsed < 30.0, f"35. 1000 requests in {elapsed:.2f}s ({per_req_us:.0f}µs/req)")

        t0 = time.perf_counter()
        for i in range(200):
            vb = vouch_for("test_beta", "actuate:x", payload={"i": i})
            vc = vouch_for("test_gamma", "actuate:x", payload={"i": i})
            request_action("test_alpha", "actuate:x", payload={"i": i},
                           action_class=ACTION_HIGH, vouchers=[vb, vc])
        elapsed_hq = time.perf_counter() - t0
        per_hq_us = (elapsed_hq / 200) * 1_000_000
        _assert(elapsed_hq < 30.0, f"36. 200 HIGH+quorum requests in {elapsed_hq:.2f}s ({per_hq_us:.0f}µs/req)")

        # ── 10. Log integrity ───────────────────────────────────
        print("\n── Log Integrity ──")
        log_path = _CHORUM_LOG
        if log_path.exists():
            lines = log_path.read_text().strip().split("\n")
            valid_json = 0
            has_receipt = 0
            for ln in lines:
                try:
                    row = json.loads(ln)
                    valid_json += 1
                    if "receipt_id" in row:
                        has_receipt += 1
                except Exception:
                    pass
            _assert(valid_json == len(lines), f"37. all {len(lines)} log rows are valid JSON")
            _assert(has_receipt == valid_json, f"38. all log rows carry receipt_id")
        else:
            print("  [SKIP] no log file created")

        # ── 11. Mode switching ──────────────────────────────────
        print("\n── Mode Switching ──")
        for mode in (ENFORCEMENT_PASSIVE, ENFORCEMENT_ADVISORY, ENFORCEMENT_STRICT, ENFORCEMENT_PASSIVE):
            set_enforcement_mode(mode)
            _assert(get_enforcement_mode() == mode, f"39. mode switches to {mode}")
        try:
            set_enforcement_mode("INVALID_MODE")
            _assert(False, "40. invalid mode raises ValueError")
        except ValueError:
            _assert(True, "40. invalid mode raises ValueError")

        # ── 12. Status snapshot ─────────────────────────────────
        print("\n── Status Snapshot ──")
        status = chorum_status()
        _assert(status["swimmer_count"] == 4, "41. status shows 4 swimmers")
        _assert("stats" in status, "42. status contains stats")

    finally:
        _CHORUM_STATE = orig_state
        _CHORUM_LOG = orig_log
        _REPUTATION_FIELD = orig_rep
        _VERIFY_CACHE.clear()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'='*50}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*50}")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_hardened_tests())
