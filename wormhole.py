# wormhole.py
import json
import hashlib
from pathlib import Path

LEDGER_DIR = Path(".sifta_state/ledger")
REMOTE_CACHE = Path(".sifta_state/wormhole_cache")

REMOTE_CACHE.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# 🔗 CHAIN HASHING (STRUCTURAL TRUTH)
# ─────────────────────────────────────────────
def chain_hash(scars: list[dict]) -> str:
    """
    Hash entire life-chain deterministically.
    """
    payload = json.dumps(scars, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def load_chain(agent_id: str) -> list:
    path = LEDGER_DIR / f"{agent_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_chain(agent_id: str, chain: list):
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    path = LEDGER_DIR / f"{agent_id}.json"
    path.write_text(json.dumps(chain, indent=2))


# ─────────────────────────────────────────────
# 🌐 WORMHOLE EXCHANGE
# ─────────────────────────────────────────────
def export_agent(agent_id: str) -> dict:
    """
    Serialize agent for wormhole transfer.
    """
    chain = load_chain(agent_id)
    return {
        "agent_id": agent_id,
        "chain": chain,
        "chain_hash": chain_hash(chain),
        "length": len(chain)
    }


def import_agent(payload: dict):
    """
    Merge remote agent into local ledger safely.
    """
    agent_id = payload["agent_id"]
    incoming_chain = payload["chain"]
    incoming_hash = payload["chain_hash"]

    local_chain = load_chain(agent_id)

    # ─────────────────────────────
    # 🧠 RULE 1: VERIFY INTEGRITY
    # ─────────────────────────────
    if chain_hash(incoming_chain) != incoming_hash:
        raise RuntimeError("[WORMHOLE] Payload corrupted")

    # ─────────────────────────────
    # 🧠 RULE 2: IDENTICAL → IGNORE
    # ─────────────────────────────
    if chain_hash(local_chain) == incoming_hash:
        return "SYNCED"

    # ─────────────────────────────
    # 🧠 RULE 3: LONGEST VALID CHAIN WINS
    # ─────────────────────────────
    if len(incoming_chain) > len(local_chain):
        save_chain(agent_id, incoming_chain)
        return "UPDATED_FROM_REMOTE"

    if len(incoming_chain) < len(local_chain):
        return "REJECTED_STALE"

    # ─────────────────────────────
    # 🧠 RULE 4: SAME LENGTH → FORK DETECTED
    # ─────────────────────────────
    raise RuntimeError(f"[FORK DETECTED] {agent_id} divergent chains")
