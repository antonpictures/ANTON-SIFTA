# sifta_swarm_identity.py
# GEN3 HARDENING PATCH
# "Trust is enforced at runtime, not assumed at boot."
# ─────────────────────────────────────────────

import os
import json
import time
import uuid
import hashlib
import platform
from pathlib import Path

STATE_DIR = Path(".sifta_state")
IDENTITY_FILE = STATE_DIR / "swarm.id"
PUBKEY_PATH = Path.home() / ".sifta" / "identity.pub.pem"


# ─────────────────────────────────────────────
# HARDWARE SALT (stronger + less spoofable)
# ─────────────────────────────────────────────
def _get_hardware_salt() -> str:
    machine_uuid = str(uuid.getnode())
    try:
        if platform.system() == "Darwin":
            import subprocess
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], 
                stderr=subprocess.DEVNULL
            ).decode("utf-8")
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    machine_uuid = line.split("=")[-1].strip().strip('"')
                    break
    except Exception:
        pass

    parts = [
        platform.system(),
        platform.machine(),
        platform.release(),
        machine_uuid,
        platform.processor(),  # added entropy
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


# ─────────────────────────────────────────────
# PUBLIC KEY FINGERPRINT
# ─────────────────────────────────────────────
def _get_pubkey_fingerprint() -> str:
    if not PUBKEY_PATH.exists():
        raise FileNotFoundError("[X] Missing identity.pub.pem")
    return hashlib.sha256(PUBKEY_PATH.read_bytes()).hexdigest()


# ─────────────────────────────────────────────
# SWARM ID GENERATION
# ─────────────────────────────────────────────
def _generate_swarm_id(pub_fp: str, hw_salt: str, genesis: float) -> str:
    payload = f"{pub_fp}:{hw_salt}:{genesis}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


# ─────────────────────────────────────────────
# ATOMIC WRITE (prevents partial corruption)
# ─────────────────────────────────────────────
def _atomic_write(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ─────────────────────────────────────────────
# INIT (idempotent + safe)
# ─────────────────────────────────────────────
def init_identity():
    STATE_DIR.mkdir(exist_ok=True)

    if IDENTITY_FILE.exists():
        print("[!] Identity already exists. Refusing overwrite.")
        return

    pub_fp = _get_pubkey_fingerprint()
    hw_salt = _get_hardware_salt()
    genesis = time.time()

    swarm_id = _generate_swarm_id(pub_fp, hw_salt, genesis)

    record = {
        # NEW CANONICAL FIELDS
        "swarm_id": swarm_id,
        "genesis": genesis,
        "pub_fp": pub_fp,
        "hw_salt": hw_salt,

        # LEGACY COMPATIBILITY
        "genesis_ts": genesis,
        "root_fingerprint": pub_fp,
        "machine_salt": hw_salt,
    }

    _atomic_write(IDENTITY_FILE, record)

    print(f"[+] Swarm Identity established: {swarm_id}")


# ─────────────────────────────────────────────
# VERIFY (RUNTIME ENFORCEMENT)
# ─────────────────────────────────────────────
def verify_identity(caller: str = "UNKNOWN"):
    if not IDENTITY_FILE.exists():
        raise PermissionError("[X] No swarm identity found")

    with open(IDENTITY_FILE) as f:
        data = json.load(f)

    current_pub = _get_pubkey_fingerprint()
    current_hw = _get_hardware_salt()

    # HARD FAIL CONDITIONS
    if current_pub != data["pub_fp"]:
        raise PermissionError(
            f"[!] IDENTITY VIOLATION ({caller}): Public key mismatch"
        )

    if current_hw != data["hw_salt"]:
        raise PermissionError(
            f"[!] IDENTITY VIOLATION ({caller}): Hardware mismatch (clone detected)"
        )

    return True


# ─────────────────────────────────────────────
# CONTINUOUS INTEGRITY WATCHDOG (NEW 🔥)
# runs in background thread if imported
# ─────────────────────────────────────────────
def start_identity_watchdog(interval: float = 5.0):
    import threading

    def _loop():
        while True:
            try:
                verify_identity("watchdog")
            except Exception as e:
                print(f"[🔥] CRITICAL IDENTITY BREACH: {e}")
                os._exit(1)  # hard kill — no recovery
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


# ─────────────────────────────────────────────
# WHOAMI
# ─────────────────────────────────────────────
def whoami():
    if not IDENTITY_FILE.exists():
        print("[X] No identity initialized")
        return

    with open(IDENTITY_FILE) as f:
        data = json.load(f)

    try:
        verify_identity("whoami")
        integrity = "✅ VALID (Hardware Bound)"
    except Exception as e:
        integrity = f"❌ INVALID — {str(e)}"

    print("══════════════════════════════════════════════════")
    print(" 🧬 SWARM IDENTITY")
    print("══════════════════════════════════════════════════")
    print(f" Swarm ID:    {data['swarm_id']}")
    print(f" Genesis:     {data['genesis']}")
    print(f" Integrity:   {integrity}")
    print("══════════════════════════════════════════════════")


# ─────────────────────────────────────────────
# BACKWARDS COMPATIBILITY (your patch respected)
# ─────────────────────────────────────────────
def get_identity():
    if not IDENTITY_FILE.exists():
        raise FileNotFoundError("Swarm Identity not yet established.")
    with open(IDENTITY_FILE, "r") as f:
        return json.load(f)


def enforce_identity(caller: str = "UNKNOWN"):
    return verify_identity(caller)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if "--init" in sys.argv:
        init_identity()
    elif "--whoami" in sys.argv:
        whoami()
    else:
        print("Usage: --init | --whoami")


