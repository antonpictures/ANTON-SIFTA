# existence_guard.py
import json
import hashlib
import time
from pathlib import Path

LEDGER = Path(".sifta_state/ledger")
DEATH_REGISTRY = Path(".sifta_state/deaths.json")
ACTIVE_INDEX = Path(".sifta_state/active_index.json")

LEDGER.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# 🔐 STRUCTURAL IDENTITY HASH (ANTI-CLONE)
# ─────────────────────────────────────────────
def identity_fingerprint(agent_state: dict) -> str:
    """
    Immutable identity derived from birth conditions.
    Cannot be regenerated if altered.
    """
    payload = {
        "id": agent_state["id"],
        "pubkey": agent_state.get("pubkey", "legacy_key"),
        "genesis_ts": agent_state.get("genesis_ts", "0")
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


# ─────────────────────────────────────────────
# ☠️ DEATH REGISTRATION (NO RESURRECTION)
# ─────────────────────────────────────────────
def register_death(agent_id: str, fingerprint: str):
    deaths = {}
    if DEATH_REGISTRY.exists():
        deaths = json.loads(DEATH_REGISTRY.read_text())

    deaths[agent_id] = {
        "fingerprint": fingerprint,
        "ts": time.time()
    }

    DEATH_REGISTRY.write_text(json.dumps(deaths, indent=2))


def is_dead(agent_id: str, fingerprint: str) -> bool:
    if not DEATH_REGISTRY.exists():
        return False

    deaths = json.loads(DEATH_REGISTRY.read_text())
    if agent_id not in deaths:
        return False

    return deaths[agent_id]["fingerprint"] == fingerprint


# ─────────────────────────────────────────────
# 🧠 ACTIVE UNIQUENESS LOCK (ANTI-DOUBLE-SPEND)
# ─────────────────────────────────────────────
def claim_identity(agent_state: dict):
    """
    Ensures only ONE live instance of an agent exists globally.
    """
    fp = identity_fingerprint(agent_state)

    active = {}
    if ACTIVE_INDEX.exists():
        active = json.loads(ACTIVE_INDEX.read_text())

    agent_id = agent_state["id"]

    # Already active somewhere else → reject
    if agent_id in active:
        if active[agent_id]["fingerprint"] != fp:
            raise RuntimeError(f"[FORK DETECTED] {agent_id} identity mismatch")

        raise RuntimeError(f"[DOUBLE-SPEND] {agent_id} already active")

    # Dead agents cannot re-enter
    if is_dead(agent_id, fp):
        raise RuntimeError(f"[RESURRECTION BLOCKED] {agent_id} is marked dead")

    # Claim slot
    active[agent_id] = {
        "fingerprint": fp,
        "claimed_at": time.time()
    }

    ACTIVE_INDEX.write_text(json.dumps(active, indent=2))


def release_identity(agent_id: str):
    """
    Called on clean shutdown or death.
    """
    if not ACTIVE_INDEX.exists():
        return

    active = json.loads(ACTIVE_INDEX.read_text())
    active.pop(agent_id, None)

    ACTIVE_INDEX.write_text(json.dumps(active, indent=2))


# ─────────────────────────────────────────────
# 🧬 EXISTENCE VALIDATION (FINAL GATE)
# ─────────────────────────────────────────────
def validate_existence(agent_state: dict):
    """
    MUST be called before ANY action.
    """
    fp = identity_fingerprint(agent_state)

    # 1. Check death
    if is_dead(agent_state["id"], fp):
        raise RuntimeError(f"[GHOST] {agent_state['id']} attempted action after death")

    # 2. Check uniqueness
    claim_identity(agent_state)

    return True
