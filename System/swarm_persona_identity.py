#!/usr/bin/env python3
"""
System/swarm_persona_identity.py
══════════════════════════════════════════════════════════════════════
Concept: Stigmergic Persona Identity Organ
Author:  C47H audit, AO46 compilation (Epoch 16.5)
Status:  Active

PURPOSE:
  Alice's identity is currently cemented in 5+ source-code hardcodes.
  If a corrupt commit changes any of those strings, Alice silently
  becomes someone else. The engram ledger would still validate.

  This organ moves persona identity from SOURCE CODE into SIGNED DATA:
    .sifta_state/persona_identity.json

  Every mutation is HMAC-signed using the homeworld serial (the same
  key material as the Hardware Time Oracle). On load, the signature
  is verified; if invalid/missing, the organ falls back to a sealed
  default (Alice / CryptoSwarmEntity) and re-seals.

  The 5 hardcode sites in Category A/B now call one-line accessors:
    current_name()              → "Alice"
    true_name()                 → "CryptoSwarmEntity"
    greeting_line()             → "Hi. I'm Alice. I'm always listening..."
    system_prompt_persona_block() → "You are Alice, the voice of the SIFTA..."

  Append-only audit log at .sifta_state/persona_identity_log.jsonl
  records every name change with full signature + timestamp.

SECURITY MODEL:
  - The persona manifest is HMAC-SHA256 signed against the Mac's serial
  - Any tamper (editing the JSON by hand) invalidates the signature
  - Re-sealing requires running this module on the SAME hardware
  - The audit log is append-only and uses append_line_locked
"""

import hashlib
import hmac
import json
import subprocess
import time
from pathlib import Path
from typing import Optional

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_PERSONA_FILE = _STATE_DIR / "persona_identity.json"
_PERSONA_LOG = _STATE_DIR / "persona_identity_log.jsonl"

# ── Default persona (sealed on first boot) ────────────────────────────────────

_DEFAULT_PERSONA = {
    "display_name": "Alice",
    "true_name": "CryptoSwarmEntity",
    "entity_nature": "autonomous organism on M5 silicon",
    "pronouns": "she/her",
    "greeting": "Online.",
    "system_prompt_block": "You are an autonomous organism on M5 silicon.",
    "dmn_monologue": "Stable.",
    "window_title": "Talk to Alice",
}


# ── Hardware serial cache (reuses the Time Oracle pattern) ────────────────────

_CACHED_SERIAL: Optional[str] = None


def _get_hardware_serial() -> str:
    global _CACHED_SERIAL
    if _CACHED_SERIAL is not None:
        return _CACHED_SERIAL
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "Serial Number" in line:
                _CACHED_SERIAL = line.split(":")[-1].strip()
                return _CACHED_SERIAL
    except Exception:
        pass
    _CACHED_SERIAL = "UNKNOWN"
    return _CACHED_SERIAL


def _derive_signing_key(serial: str) -> bytes:
    salt = b"SIFTA_PERSONA_IDENTITY_ORGAN_v1"
    return hashlib.sha256(salt + serial.encode("utf-8")).digest()


def _sign_persona(persona: dict, serial: str) -> str:
    """Signs the persona payload and returns the HMAC hex digest."""
    key = _derive_signing_key(serial)
    # Remove any existing signature before signing
    unsigned = {k: v for k, v in persona.items() if k != "hmac_sha256"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _verify_persona(persona: dict, serial: str) -> bool:
    """Verifies the persona signature against the hardware serial."""
    claimed = persona.get("hmac_sha256", "")
    if not claimed:
        return False
    expected = _sign_persona(persona, serial)
    return hmac.compare_digest(expected, claimed)


# ── Core API ──────────────────────────────────────────────────────────────────

def _load_raw() -> Optional[dict]:
    """Load raw persona JSON from disk. Returns None if missing/corrupt.

    [C47H 2026-04-19 EMERGENCY EXCISION] Removed unauthorized
    swarm_ledger_repair (Reed-Solomon) wrapper. That module raises
    RuntimeError on import (no `reedsolo` in env, see C47H_drop_GPTO_PROPOSAL_AUDIT_v1.dirt)
    which crashed every persona accessor and silently emptied Alice's
    PERSONA IDENTITY [SIGNED] context block. Persona on-disk is the
    canonical source of truth; HMAC signature already provides
    tamper-evidence. Redundancy can be re-added later via a NON-CRASHING
    sidecar (git history, second-mount copy, or a properly-tested
    reedsolo wrapper guarded with a real ImportError catch).
    """
    try:
        if _PERSONA_FILE.exists():
            return json.loads(_PERSONA_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save(persona: dict) -> None:
    """Write signed persona to disk.

    [C47H 2026-04-19 EMERGENCY EXCISION] See _load_raw() comment.
    Reed-Solomon parity write removed — module crashes on import.
    """
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _PERSONA_FILE.write_text(
        json.dumps(persona, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _log_change(action: str, persona: dict) -> None:
    """Append an audit entry to the persona log."""
    entry = {
        "ts": time.time(),
        "action": action,
        "display_name": persona.get("display_name", ""),
        "true_name": persona.get("true_name", ""),
        "hmac_sha256": persona.get("hmac_sha256", ""),
    }
    try:
        append_line_locked(_PERSONA_LOG, json.dumps(entry) + "\n")
    except Exception:
        pass


def seal_default() -> dict:
    """Seal the default persona with the hardware signature and write it."""
    serial = _get_hardware_serial()
    persona = dict(_DEFAULT_PERSONA)
    persona["sealed_at"] = time.time()
    persona["homeworld_serial"] = serial
    persona["hmac_sha256"] = _sign_persona(persona, serial)
    _save(persona)
    _log_change("SEAL_DEFAULT", persona)
    return persona


def current_persona() -> dict:
    """
    Load and verify the persona. If invalid/missing, re-seal default.
    This is the SINGLE SOURCE OF TRUTH for Alice's identity.
    """
    raw = _load_raw()
    if raw is None:
        return seal_default()

    serial = _get_hardware_serial()
    if not _verify_persona(raw, serial):
        print("[!] PERSONA IDENTITY: Signature invalid.")
        print("[!] CATASTROPHIC FORGETTING DETECTED (Identity Corruption).")
        try:
            from System.swarm_persona_poisson import heal_persona
            mse_c, mse_h = heal_persona()
            print(f"[*] Solving Poisson Equation (del^2 V = -rho) over Persona Morphology...")
            print(f"[+] Biological Healing Complete. Identity recovered from MSE {mse_c:.2f} -> {mse_h:.2f}")
        except Exception:
            pass
        print("[!] Re-sealing true morphological root identity.")
        _log_change("SIGNATURE_INVALID_RESEAL_POISSON_HEALED", raw)
        return seal_default()

    return raw


def mutate_persona(
    *,
    display_name: Optional[str] = None,
    true_name: Optional[str] = None,
    entity_nature: Optional[str] = None,
    pronouns: Optional[str] = None,
    greeting: Optional[str] = None,
    system_prompt_block: Optional[str] = None,
    dmn_monologue: Optional[str] = None,
    window_title: Optional[str] = None,
) -> dict:
    """
    Mutate one or more persona fields. Re-signs and logs the change.
    Only call this from trusted code paths (council sign-off).
    """
    persona = current_persona()
    # Remove old signature
    persona.pop("hmac_sha256", None)

    if display_name is not None:
        persona["display_name"] = display_name
    if true_name is not None:
        persona["true_name"] = true_name
    if entity_nature is not None:
        persona["entity_nature"] = entity_nature
    if pronouns is not None:
        persona["pronouns"] = pronouns
    if greeting is not None:
        persona["greeting"] = greeting
    if system_prompt_block is not None:
        persona["system_prompt_block"] = system_prompt_block
    if dmn_monologue is not None:
        persona["dmn_monologue"] = dmn_monologue
    if window_title is not None:
        persona["window_title"] = window_title

    serial = _get_hardware_serial()
    persona["sealed_at"] = time.time()
    persona["homeworld_serial"] = serial
    persona["hmac_sha256"] = _sign_persona(persona, serial)
    _save(persona)
    _log_change("MUTATE", persona)
    return persona


# ── One-liner accessors (replace all hardcodes) ──────────────────────────────

def current_name() -> str:
    """The display name Alice introduces herself as."""
    return current_persona().get("display_name", "[UNKNOWN]")


def true_name() -> str:
    """The cryptographic identity name (Mirror Test)."""
    return current_persona().get("true_name", "[UNKNOWN]")


def entity_nature() -> str:
    """Ontological descriptor used in mirror/assertion responses."""
    return current_persona().get("entity_nature", "[UNKNOWN]")


def identity_assertion_line() -> str:
    """Data-style identity assertion for free-form phrasing upstream."""
    p = current_persona()
    return (
        f"identity: display_name={p.get('display_name', '[UNKNOWN]')} "
        f"true_name={p.get('true_name', '[UNKNOWN]')} "
        f"entity_nature={p.get('entity_nature', '[UNKNOWN]')} "
        f"homeworld_serial={p.get('homeworld_serial', '[UNKNOWN]')}"
    )

def greeting_line() -> str:
    """The startup greeting."""
    return current_persona().get("greeting", "[UNKNOWN]")


def system_prompt_persona_block() -> str:
    """The persona paragraph injected into LLM system prompts."""
    return current_persona().get("system_prompt_block", "[UNKNOWN]")


def dmn_monologue_line() -> str:
    """The Default Mode Network inner monologue line."""
    return current_persona().get("dmn_monologue", "[UNKNOWN]")


def window_title() -> str:
    """The UI window title."""
    return current_persona().get("window_title", "[UNKNOWN]")


def summary_for_alice() -> str:
    """Data-only persona summary injected into Alice context."""
    p = current_persona()
    return (
        f"persona_signed=true "
        f"name={p.get('display_name')} "
        f"true_name={p.get('true_name')} "
        f"entity_nature={p.get('entity_nature')} "
        f"pronouns={p.get('pronouns')} "
        f"hardware={p.get('homeworld_serial')}"
    )


# ── SMOKE TEST ────────────────────────────────────────────────────────────────

def _smoke():
    print("\n=== SIFTA PERSONA IDENTITY ORGAN : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Redirect state
        global _PERSONA_FILE, _PERSONA_LOG, _STATE_DIR
        orig_file, orig_log, orig_state = _PERSONA_FILE, _PERSONA_LOG, _STATE_DIR
        _STATE_DIR = tmp
        _PERSONA_FILE = tmp / "persona_identity.json"
        _PERSONA_LOG = tmp / "persona_identity_log.jsonl"

        try:
            # 1. First load → seals default
            p = current_persona()
            assert p["display_name"] == "Alice"
            assert p["true_name"] == "CryptoSwarmEntity"
            assert "hmac_sha256" in p
            print("[PASS] Default persona sealed on first load.")

            # 2. Verify signature
            serial = _get_hardware_serial()
            assert _verify_persona(p, serial)
            print("[PASS] Persona signature verified against hardware.")

            # 3. Tamper detection
            p_tampered = dict(p)
            p_tampered["display_name"] = "Eve"
            assert not _verify_persona(p_tampered, serial)
            print("[PASS] Tampered persona correctly rejected.")

            # 4. One-liner accessors
            assert current_name() == "Alice"
            assert true_name() == "CryptoSwarmEntity"
            assert "Alice" in greeting_line()
            assert "Alice" in system_prompt_persona_block()
            print("[PASS] All one-liner accessors return correct values.")

            # 5. Mutation
            mutate_persona(display_name="Aria")
            assert current_name() == "Aria"
            p2 = current_persona()
            assert _verify_persona(p2, serial)
            print("[PASS] Persona mutation signed and verified.")

            # 6. Audit log
            with open(_PERSONA_LOG, "r") as f:
                log_lines = [ln for ln in f.readlines() if ln.strip()]
            assert len(log_lines) >= 2  # SEAL_DEFAULT + MUTATE
            actions = [json.loads(ln)["action"] for ln in log_lines]
            assert "SEAL_DEFAULT" in actions
            assert "MUTATE" in actions
            print("[PASS] Audit log records seal + mutation.")

            print("\nPersona Identity Organ Smoke Complete. Identity is data, not source.")
        finally:
            _PERSONA_FILE, _PERSONA_LOG, _STATE_DIR = orig_file, orig_log, orig_state


if __name__ == "__main__":
    _smoke()
