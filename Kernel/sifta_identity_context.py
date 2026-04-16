# ─────────────────────────────────────────────
# GEN4 — SWARM IDENTITY PROPAGATION LAYER
# "Identity is useless unless it flows everywhere."
# ─────────────────────────────────────────────

# Drop-in module: sifta_identity_context.py
# Purpose:
#   - Inject swarm_id into ALL system outputs
#   - Bind identity to scars, proposals, audit logs
#   - Make every action provable

import json
import time
from pathlib import Path
from datetime import datetime

from sifta_swarm_identity import get_identity

IDENTITY_CACHE = None


# ─────────────────────────────────────────────
# LOAD IDENTITY (cached)
# ─────────────────────────────────────────────
def _load_identity():
    global IDENTITY_CACHE
    if IDENTITY_CACHE is None:
        IDENTITY_CACHE = get_identity()
    return IDENTITY_CACHE


# ─────────────────────────────────────────────
# CONTEXT INJECTION
# ─────────────────────────────────────────────
def inject_identity(payload: dict) -> dict:
    ident = _load_identity()

    # Ensure payload is a dictionary, otherwise return as is
    if not isinstance(payload, dict):
        return payload

    payload["_swarm"] = {
        "swarm_id": ident["swarm_id"],
        "genesis": ident["genesis"],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    return payload


# ─────────────────────────────────────────────
# SCAR WRAPPER
# ─────────────────────────────────────────────
def write_scar(path: Path, scar_data: dict):
    scar_data = inject_identity(scar_data)

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(scar_data, f, indent=2)


# ─────────────────────────────────────────────
# AUDIT WRAPPER
# ─────────────────────────────────────────────
def audit_log(db_conn, event_type: str, payload: dict):
    payload = inject_identity(payload)

    db_conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, component, details) VALUES (?, ?, ?, ?)",
        (time.time(), event_type.upper(), payload.get("component", "UNKNOWN"), json.dumps(payload))
    )
    db_conn.commit()


# ─────────────────────────────────────────────
# PROPOSAL WRAPPER
# ─────────────────────────────────────────────
def write_proposal(path: Path, proposal_data: dict):
    proposal_data = inject_identity(proposal_data)

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(proposal_data, f, indent=2)


# ─────────────────────────────────────────────
# VERIFY ORIGIN (future cross-swarm security)
# ─────────────────────────────────────────────
def verify_same_swarm(payload: dict):
    ident = _load_identity()

    incoming = payload.get("_swarm", {}).get("swarm_id")

    if incoming != ident["swarm_id"]:
        raise PermissionError(
            f"[X] FOREIGN SWARM DETECTED: {incoming}"
        )

    return True


# ─────────────────────────────────────────────
# OPTIONAL: GLOBAL PATCH HOOK (one-line integration)
# ─────────────────────────────────────────────
def bind_global_context():
    """
    Monkey-patch helpers for fast integration.
    Call once in server.py boot.
    """
    import builtins

    builtins.SIFTA_INJECT_IDENTITY = inject_identity
