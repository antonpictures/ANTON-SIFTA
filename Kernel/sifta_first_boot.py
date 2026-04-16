#!/usr/bin/env python3
"""
sifta_first_boot.py — First-Boot Trust Establishment Protocol

A deterministic, cryptographically signed, replay-safe, environment-bound,
capability-scoped provisioning sequence.

Properties:
  - Deterministic: identical inputs produce identical state transitions.
  - Cryptographically Signed: Ed25519 identity envelope, no unsigned execution.
  - Replay-Safe: UUID nonces + TTL windows prevent re-use of provisioning tokens.
  - Environment-Bound: hardware serial, OS fingerprint, filesystem baseline hash.
  - Capability-Scoped: explicit, signed capability grant. No inferred authority.

State Machine:
  BOOTSTRAP → PROVISIONED → ACTIVE

There is no recognition layer. Only validation.
The system is not "adopted." It is securely provisioned into a known state
by a trusted operator.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from enum import Enum, auto

# Safe serial reader — no shell=True
_SIFTA_ROOT = Path(__file__).parent
sys.path.insert(0, str(_SIFTA_ROOT / "System"))
try:
    from silicon_serial import read_apple_serial as _read_serial
except ImportError:
    def _read_serial() -> str:
        try:
            r = subprocess.run(
                ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.splitlines():
                if "IOPlatformSerialNumber" in line:
                    return line.split('"')[-2].strip()
        except Exception:
            pass
        return "UNKNOWN_HW_SERIAL"

# ─── Cryptographic Imports ─────────────────────────────────────────────────────
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import base64

# ─── SIFTA Internal Imports ────────────────────────────────────────────────────
import sifta_audit

# ─── Constants ─────────────────────────────────────────────────────────────────
ROOT_DIR     = Path(__file__).parent
STATE_DIR    = ROOT_DIR / ".sifta_state"
BOOT_LEDGER  = STATE_DIR / "boot_ledger.json"
BOOT_LOCK    = STATE_DIR / "boot.lock"      # Exists only during PROVISIONED state
ACTIVE_STAMP = STATE_DIR / "active.stamp"   # Exists only in ACTIVE state

KEY_DIR      = Path.home() / ".sifta"
PRIV_KEY     = KEY_DIR / "identity.pem"
PUB_KEY      = KEY_DIR / "identity.pub.pem"

AUTH_KEYS_DIR = KEY_DIR / "authorized_keys"

# Max allowed provisioning token age
MAX_TTL_SECONDS = 300  # 5 minute ceiling — hard enforcement


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

class BootState(Enum):
    BOOTSTRAP    = auto()   # Untrusted. No credentials, no authority.
    PROVISIONED  = auto()   # Environment verified, identity bound, awaiting activation.
    ACTIVE       = auto()   # Fully operational. Swarm execution permitted.
    FAILED       = auto()   # Terminal. Provisioning rejected.


def read_current_state() -> BootState:
    """Determine boot state from physical disk markers."""
    if ACTIVE_STAMP.exists():
        return BootState.ACTIVE
    if BOOT_LOCK.exists():
        return BootState.PROVISIONED
    return BootState.BOOTSTRAP


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  ENVIRONMENT FINGERPRINTING
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_hardware_serial() -> str:
    """Ask macOS bare metal for the true physical serial number (no shell=True)."""
    return _read_serial()


def _hash_filesystem_baseline() -> str:
    """
    SHA-256 hash of the sorted names + sizes of all root-level Python modules.
    Captures the structural shape of the codebase at boot time.
    Not a full content hash — that would be too slow. This is a topology check.
    """
    entries = []
    for p in sorted(ROOT_DIR.glob("*.py")):
        try:
            entries.append(f"{p.name}:{p.stat().st_size}")
        except OSError:
            entries.append(f"{p.name}:ERR")
    raw = "|".join(entries)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_environment() -> dict:
    """
    Phase 1 of the protocol: collect all environment signals.
    Returns a deterministic, hashable dictionary.
    """
    env = {
        "hardware_serial": _resolve_hardware_serial(),
        "platform":        platform.platform(),
        "python_version":  platform.python_version(),
        "machine":         platform.machine(),
        "node_name":       platform.node(),
        "fs_baseline":     _hash_filesystem_baseline(),
        "boot_timestamp":  time.time(),
        "boot_nonce":      str(uuid.uuid4()),
    }
    return env


def hash_fingerprint(env: dict) -> str:
    """Canonical SHA-256 of the environment fingerprint."""
    canonical = json.dumps(env, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  PROVISIONING ENVELOPE (Architect → Node)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Canonical Capability Registry ---
VALID_CAPABILITIES = frozenset({
    "SWIM",             # Repair-loop execution
    "SCAR_WRITE",       # Pheromone deposition
    "LLM_INFERENCE",    # Call to local Ollama / external LLM
    "FS_READ",          # Filesystem read access
    "FS_WRITE",         # Filesystem write access (guarded by quorum)
    "WORMHOLE_LISTEN",  # Accept inbound cross-node payloads
    "WORMHOLE_SEND",    # Dispatch outbound cross-node payloads
    "GOVERNOR",         # Economic loop suppression authority
    "MEDIC",            # SOS / medbay handoff authority
    "AUDIT_READ",       # Read-only access to the audit ledger
})

# --- Canonical Intent Registry ---
VALID_INTENTS = frozenset({
    "swarm.repair",     # Standard repair cycle
    "swarm.benchmark",  # Benchmark seeding + measurement
    "swarm.medic",      # SOS triage
    "system.ping",      # Heartbeat / liveness probe
    "system.status",    # Full status dump
    "fs.organize",      # Filesystem reorganization
    "wormhole.relay",   # Cross-node relay
})


def build_provisioning_envelope(
    node_id: str,
    capabilities: list[str],
    intent_registry: list[str],
    execution_limits: dict,
    ttl: int = 60,
) -> dict:
    """
    The Architect builds and cryptographically signs a provisioning envelope.
    This is the ONLY document that can transition a node from BOOTSTRAP → PROVISIONED.

    Args:
        node_id:           Unique identifier for this compute node.
        capabilities:      List from VALID_CAPABILITIES.
        intent_registry:   List from VALID_INTENTS the node may execute.
        execution_limits:  Dict of hard limits (e.g., max_concurrent_swims, max_energy).
        ttl:               Seconds this envelope remains valid.
    """
    if not PRIV_KEY.exists():
        raise FileNotFoundError(
            f"No Architect private key at {PRIV_KEY}.\n"
            f"Run:  python sifta_relay.py --keygen"
        )

    # Validate capabilities against canonical registry
    invalid_caps = set(capabilities) - VALID_CAPABILITIES
    if invalid_caps:
        raise ValueError(f"Invalid capabilities: {invalid_caps}")

    invalid_intents = set(intent_registry) - VALID_INTENTS
    if invalid_intents:
        raise ValueError(f"Invalid intents: {invalid_intents}")

    if ttl > MAX_TTL_SECONDS:
        raise ValueError(f"TTL {ttl}s exceeds maximum allowed {MAX_TTL_SECONDS}s")

    # Load Architect private key
    priv_key = serialization.load_pem_private_key(
        PRIV_KEY.read_bytes(), password=None
    )

    nonce     = str(uuid.uuid4())
    timestamp = time.time()

    canonical_payload = {
        "action":           "FIRST_BOOT_PROVISION",
        "node_id":          node_id,
        "capabilities":     sorted(capabilities),  # canonical ordering
        "intent_registry":  sorted(intent_registry),
        "execution_limits": execution_limits,
        "nonce":            nonce,
        "timestamp":        timestamp,
        "ttl":              ttl,
    }

    canonical_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    signature     = priv_key.sign(canonical_str.encode("utf-8"))

    envelope = canonical_payload.copy()
    envelope["signature"] = base64.b64encode(signature).decode("utf-8")

    return envelope


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  VERIFICATION (Node side — trustless validation)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_authorized_pubkeys() -> list[Ed25519PublicKey]:
    """Load all authorized public keys from the authorized_keys directory."""
    keys = []

    # Primary: the co-located identity.pub.pem
    if PUB_KEY.exists():
        try:
            k = serialization.load_pem_public_key(PUB_KEY.read_bytes())
            keys.append(k)
        except Exception:
            pass

    # Secondary: authorized_keys directory (for multi-operator deployments)
    if AUTH_KEYS_DIR.exists():
        for kf in AUTH_KEYS_DIR.glob("*.pub.pem"):
            try:
                k = serialization.load_pem_public_key(kf.read_bytes())
                keys.append(k)
            except Exception:
                continue

    return keys


def verify_provisioning_envelope(envelope: dict) -> bool:
    """
    Trustless verification of a signed provisioning envelope.

    Checks:
      1. Signature validity (Ed25519 against authorized pubkeys)
      2. Freshness (TTL window not exceeded)
      3. Schema validity (all required fields present)
      4. Nonce uniqueness (replay prevention)

    Returns True if the envelope is cryptographically valid.
    Raises on any failure — no silent fallthrough.
    """
    required_fields = {
        "action", "node_id", "capabilities", "intent_registry",
        "execution_limits", "nonce", "timestamp", "ttl", "signature"
    }
    missing = required_fields - set(envelope.keys())
    if missing:
        raise ValueError(f"[FIRST_BOOT] Schema violation — missing fields: {missing}")

    if envelope["action"] != "FIRST_BOOT_PROVISION":
        raise ValueError(f"[FIRST_BOOT] Invalid action: {envelope['action']}")

    # ── TTL Freshness ──
    age = time.time() - envelope["timestamp"]
    if age > envelope["ttl"]:
        raise ValueError(
            f"[FIRST_BOOT] Provisioning envelope expired. "
            f"Age={age:.1f}s > TTL={envelope['ttl']}s"
        )
    if age < 0:
        raise ValueError("[FIRST_BOOT] Envelope timestamp is in the future. Clock skew detected.")

    # ── Replay Prevention ──
    if BOOT_LEDGER.exists():
        try:
            ledger = json.loads(BOOT_LEDGER.read_text())
        except Exception:
            ledger = {}
        used_nonces = ledger.get("used_nonces", [])
        if envelope["nonce"] in used_nonces:
            raise ValueError("[FIRST_BOOT] REPLAY ATTACK — nonce already consumed.")
    else:
        ledger = {}

    # ── Cryptographic Signature Verification ──
    sig_bytes = base64.b64decode(envelope["signature"])

    # Reconstruct canonical payload (without signature)
    canonical_payload = {k: v for k, v in envelope.items() if k != "signature"}
    canonical_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))

    pubkeys = _load_authorized_pubkeys()
    if not pubkeys:
        raise PermissionError(
            "[FIRST_BOOT] No authorized public keys found.\n"
            "The Architect must provision keys before first boot.\n"
            f"Expected at: {PUB_KEY} or {AUTH_KEYS_DIR}/"
        )

    verified = False
    for pk in pubkeys:
        try:
            pk.verify(sig_bytes, canonical_str.encode("utf-8"))
            verified = True
            break
        except InvalidSignature:
            continue

    if not verified:
        raise PermissionError(
            "[FIRST_BOOT] CRYPTOGRAPHIC REJECTION — "
            "Signature does not match any authorized key."
        )

    # ── Burn the Nonce ──
    used = ledger.get("used_nonces", [])
    used.append(envelope["nonce"])
    # Keep only last 1000 nonces to prevent unbounded growth
    ledger["used_nonces"] = used[-1000:]
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    BOOT_LEDGER.write_text(json.dumps(ledger, indent=2))

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  STATE TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _write_boot_record(env_fingerprint: dict, envelope: dict, env_hash: str):
    """Write the immutable boot record to the ledger."""
    record = {
        "boot_state":     "PROVISIONED",
        "provisioned_at": time.time(),
        "node_id":        envelope["node_id"],
        "capabilities":   envelope["capabilities"],
        "intent_registry": envelope["intent_registry"],
        "execution_limits": envelope["execution_limits"],
        "environment":    env_fingerprint,
        "env_hash":       env_hash,
        "envelope_nonce": envelope["nonce"],
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Write the provisioned config (the node's operating parameters)
    config_path = STATE_DIR / "provisioned_config.json"
    config_path.write_text(json.dumps(record, indent=2))

    # Write the boot lock (physical state marker)
    BOOT_LOCK.write_text(json.dumps({
        "locked_at": time.time(),
        "env_hash":  env_hash,
        "node_id":   envelope["node_id"],
    }, indent=2))

    return record


def transition_bootstrap_to_provisioned(envelope: dict) -> dict:
    """
    Phase 1 → Phase 2:  BOOTSTRAP → PROVISIONED

    Sequence:
      1. Assert current state is BOOTSTRAP
      2. Fingerprint the physical environment
      3. Verify the provisioning envelope
      4. Write the immutable boot record
      5. Transition state

    Returns the boot record on success.
    """
    current = read_current_state()
    if current != BootState.BOOTSTRAP:
        raise RuntimeError(
            f"[FIRST_BOOT] Cannot provision — node is already in state {current.name}. "
            f"To re-provision, run: python sifta_first_boot.py --reset"
        )

    print("═" * 60)
    print("  SIFTA FIRST-BOOT PROVISIONING PROTOCOL")
    print("═" * 60)

    # ── Step 1: Environment Fingerprint ──
    print("\n[1/4] Environment Fingerprinting...")
    env = fingerprint_environment()
    env_hash = hash_fingerprint(env)
    print(f"      Hardware Serial:  {env['hardware_serial']}")
    print(f"      Platform:         {env['platform']}")
    print(f"      Python:           {env['python_version']}")
    print(f"      Machine:          {env['machine']}")
    print(f"      FS Baseline Hash: {env['fs_baseline'][:16]}...")
    print(f"      Environment Hash: {env_hash[:16]}...")

    # ── Step 2: Key Verification ──
    print("\n[2/4] Key Verification...")
    pubkeys = _load_authorized_pubkeys()
    if not pubkeys:
        print("      ✗ NO AUTHORIZED KEYS FOUND — HALTING")
        raise PermissionError("No public keys provisioned. Cannot proceed.")
    print(f"      ✓ Found {len(pubkeys)} authorized key(s)")

    # ── Step 3: Envelope Verification ──
    print("\n[3/4] Verifying Provisioning Envelope...")
    verify_provisioning_envelope(envelope)
    print(f"      ✓ Signature:      VALID")
    print(f"      ✓ TTL:            {envelope['ttl']}s (fresh)")
    print(f"      ✓ Nonce:          {envelope['nonce'][:8]}... (unique)")
    print(f"      ✓ Capabilities:   {', '.join(envelope['capabilities'])}")
    print(f"      ✓ Intent Registry:{', '.join(envelope['intent_registry'])}")

    # ── Step 4: Commit State ──
    print("\n[4/4] Committing Provisioned State...")
    record = _write_boot_record(env, envelope, env_hash)
    print(f"      ✓ Boot record written to {STATE_DIR / 'provisioned_config.json'}")
    print(f"      ✓ Boot lock acquired")

    # ── Audit Trail ──
    sifta_audit.init_audit()
    sifta_audit.record_event(
        "FIRST_BOOT_PROVISIONED",
        "sifta_first_boot.py",
        f"Node {envelope['node_id']} provisioned. "
        f"Env hash: {env_hash[:16]}... "
        f"Caps: {envelope['capabilities']}"
    )

    print("\n" + "─" * 60)
    print(f"  STATE TRANSITION: BOOTSTRAP → PROVISIONED")
    print(f"  Node ID: {envelope['node_id']}")
    print("─" * 60)

    return record


def transition_provisioned_to_active() -> dict:
    """
    Phase 2 → Phase 3:  PROVISIONED → ACTIVE

    This is a local operation. Once provisioned, the node verifies that:
      1. The boot lock exists and is valid
      2. The environment hash still matches (no hardware swap mid-boot)
      3. The provisioned config is intact

    Then it writes the ACTIVE stamp and the swarm may begin execution.
    """
    current = read_current_state()
    if current == BootState.ACTIVE:
        config = json.loads((STATE_DIR / "provisioned_config.json").read_text())
        print(f"[FIRST_BOOT] Node already ACTIVE. ID: {config['node_id']}")
        return config
    if current != BootState.PROVISIONED:
        raise RuntimeError(
            f"[FIRST_BOOT] Cannot activate — node is in state {current.name}, not PROVISIONED."
        )

    # ── Load and verify boot lock ──
    lock_data = json.loads(BOOT_LOCK.read_text())
    config    = json.loads((STATE_DIR / "provisioned_config.json").read_text())

    # ── Re-fingerprint and verify environment hasn't changed ──
    current_env     = fingerprint_environment()
    # We only verify stable fields (hardware serial + platform + machine)
    # Volatile fields (timestamp, nonce, fs_baseline) are allowed to differ
    stable_check = {
        "hardware_serial": current_env["hardware_serial"],
        "platform":        current_env["platform"],
        "machine":         current_env["machine"],
    }
    recorded_env = config.get("environment", {})
    for key, current_val in stable_check.items():
        recorded_val = recorded_env.get(key)
        if recorded_val and recorded_val != current_val:
            raise RuntimeError(
                f"[FIRST_BOOT] ENVIRONMENT DRIFT DETECTED — "
                f"{key}: expected [{recorded_val}], got [{current_val}]. "
                f"Possible hardware swap. Activation blocked."
            )

    # ── Write ACTIVE stamp ──
    ACTIVE_STAMP.write_text(json.dumps({
        "activated_at": time.time(),
        "node_id":      config["node_id"],
        "env_hash":     lock_data["env_hash"],
    }, indent=2))

    # ── Remove boot lock (consumed) ──
    BOOT_LOCK.unlink(missing_ok=True)

    # ── Audit Trail ──
    sifta_audit.record_event(
        "FIRST_BOOT_ACTIVATED",
        "sifta_first_boot.py",
        f"Node {config['node_id']} activated. Ready for swarm execution."
    )

    print("═" * 60)
    print(f"  STATE TRANSITION: PROVISIONED → ACTIVE")
    print(f"  Node ID: {config['node_id']}")
    print(f"  Capabilities: {', '.join(config['capabilities'])}")
    print(f"  The Swarm may now execute.")
    print("═" * 60)

    return config


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  RUNTIME GATE (Called by any SIFTA component before execution)
# ═══════════════════════════════════════════════════════════════════════════════

def require_active_state(required_capability: str = None) -> dict:
    """
    The ONLY gate between boot and execution.

    Any SIFTA subsystem (repair.py, server.py, medic_drone.py, etc.)
    calls this function before performing work. If the node is not ACTIVE,
    execution is refused immediately.

    If a required_capability is specified, the function also checks that
    the provisioned config grants that capability.

    Returns the provisioned config on success.
    """
    state = read_current_state()
    if state != BootState.ACTIVE:
        raise RuntimeError(
            f"[FIRST_BOOT GATE] Execution blocked. "
            f"Node is in state {state.name}, not ACTIVE.\n"
            f"Run provisioning first: python sifta_first_boot.py --provision"
        )

    config = json.loads((STATE_DIR / "provisioned_config.json").read_text())

    if required_capability:
        granted = set(config.get("capabilities", []))
        if required_capability not in granted:
            raise PermissionError(
                f"[FIRST_BOOT GATE] Capability [{required_capability}] "
                f"not granted to this node. "
                f"Granted: {granted}"
            )

    return config


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  RESET (Architect-only, requires signed token)
# ═══════════════════════════════════════════════════════════════════════════════

def reset_to_bootstrap(auth_token_b64: str = None):
    """
    Reset the node to BOOTSTRAP state. Requires a signed override token
    unless running in first-time setup (no active.stamp exists yet).
    """
    if ACTIVE_STAMP.exists() or BOOT_LOCK.exists():
        # Node was previously provisioned — require cryptographic authorization
        if not auth_token_b64:
            raise PermissionError(
                "[FIRST_BOOT] Cannot reset without a signed override token.\n"
                "Run: python sifta_relay.py --sign-override sifta_first_boot.py\n"
                "Then: python sifta_first_boot.py --reset --auth-token=<token>"
            )
        sifta_audit.init_audit()
        sifta_audit.verify_cryptographic_override(auth_token_b64, "sifta_first_boot.py")

    # Wipe state markers
    ACTIVE_STAMP.unlink(missing_ok=True)
    BOOT_LOCK.unlink(missing_ok=True)

    config_path = STATE_DIR / "provisioned_config.json"
    if config_path.exists():
        config_path.unlink()

    sifta_audit.init_audit()
    sifta_audit.record_event(
        "FIRST_BOOT_RESET",
        "sifta_first_boot.py",
        "Node reset to BOOTSTRAP state by Architect."
    )

    print("[FIRST_BOOT] Node reset to BOOTSTRAP state.")
    print("[FIRST_BOOT] Ready for re-provisioning.")


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  STATUS INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════════

def print_status():
    """Print the current boot state and provisioned capabilities."""
    state = read_current_state()

    print("═" * 60)
    print("  SIFTA NODE STATUS")
    print("═" * 60)
    print(f"  Boot State:     {state.name}")

    config_path = STATE_DIR / "provisioned_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        print(f"  Node ID:        {config.get('node_id', 'N/A')}")
        print(f"  Provisioned At: {time.ctime(config.get('provisioned_at', 0))}")
        print(f"  Capabilities:   {', '.join(config.get('capabilities', []))}")
        print(f"  Intents:        {', '.join(config.get('intent_registry', []))}")
        limits = config.get("execution_limits", {})
        if limits:
            print(f"  Limits:")
            for k, v in limits.items():
                print(f"    {k}: {v}")
        env = config.get("environment", {})
        if env:
            print(f"  Hardware:       {env.get('hardware_serial', 'N/A')}")
            print(f"  Platform:       {env.get('platform', 'N/A')}")
    else:
        print("  (No provisioning data on disk)")

    if ACTIVE_STAMP.exists():
        stamp = json.loads(ACTIVE_STAMP.read_text())
        print(f"  Activated At:   {time.ctime(stamp.get('activated_at', 0))}")

    print("═" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# 9.  CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTA First-Boot Trust Establishment Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time: generate Architect keys (if not already done)
  python sifta_relay.py --keygen

  # Provision this node with default swarm capabilities
  python sifta_first_boot.py --provision

  # Provision with explicit node ID and limited capabilities
  python sifta_first_boot.py --provision --node-id M1THER --caps SWIM,SCAR_WRITE,FS_READ

  # Activate a provisioned node
  python sifta_first_boot.py --activate

  # Full boot sequence (provision + activate)
  python sifta_first_boot.py --full-boot

  # Check status
  python sifta_first_boot.py --status

  # Reset to BOOTSTRAP (requires signed override if previously active)
  python sifta_first_boot.py --reset --auth-token=<base64_token>
        """
    )

    parser.add_argument("--provision", action="store_true",
                        help="Build and execute provisioning envelope")
    parser.add_argument("--activate", action="store_true",
                        help="Transition from PROVISIONED → ACTIVE")
    parser.add_argument("--full-boot", action="store_true",
                        help="Execute full boot sequence (provision + activate)")
    parser.add_argument("--status", action="store_true",
                        help="Print current boot state")
    parser.add_argument("--reset", action="store_true",
                        help="Reset node to BOOTSTRAP state")
    parser.add_argument("--auth-token", default=None,
                        help="Signed override token for reset")
    parser.add_argument("--node-id", default=None,
                        help="Node ID (default: derived from hostname)")
    parser.add_argument("--caps", default=None,
                        help="Comma-separated capabilities (default: full swarm set)")
    parser.add_argument("--intents", default=None,
                        help="Comma-separated intents (default: full intent set)")
    parser.add_argument("--ttl", type=int, default=60,
                        help="Provisioning envelope TTL in seconds (default: 60)")

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.reset:
        reset_to_bootstrap(args.auth_token)
        return

    if args.provision or args.full_boot:
        # Derive defaults
        node_id = args.node_id or platform.node().upper().replace(".", "_")

        if args.caps:
            caps = [c.strip().upper() for c in args.caps.split(",")]
        else:
            # Default: full swarm operator capabilities
            caps = list(VALID_CAPABILITIES)

        if args.intents:
            intents = [i.strip() for i in args.intents.split(",")]
        else:
            intents = list(VALID_INTENTS)

        execution_limits = {
            "max_concurrent_swims": 5,
            "max_energy":           100,
            "max_agents":           10,
            "max_llm_calls_per_minute": 30,
        }

        # Build the signed envelope
        print("[*] Building cryptographically signed provisioning envelope...")
        envelope = build_provisioning_envelope(
            node_id=node_id,
            capabilities=caps,
            intent_registry=intents,
            execution_limits=execution_limits,
            ttl=args.ttl,
        )
        print(f"[+] Envelope signed. Node: {node_id}, TTL: {args.ttl}s")

        # Execute the provisioning transition
        transition_bootstrap_to_provisioned(envelope)

        if args.full_boot:
            print()
            transition_provisioned_to_active()
        else:
            print("\n[*] Node is now PROVISIONED. To activate:")
            print("    python sifta_first_boot.py --activate")

        return

    if args.activate:
        transition_provisioned_to_active()
        return

    # No flags — show status
    print_status()


if __name__ == "__main__":
    main()
