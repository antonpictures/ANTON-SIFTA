# scar_state_machine.py
"""
SCAR STATE MACHINE — Phase 5: Lifecycle Formalization

Every SCAR transitions through a guarded state pipeline:
  PROPOSED → CONTESTED → LOCKED → EXECUTED → FOSSILIZED

Transitions are NOT informational — they are guarded system mutations.
The payload becomes immutable at LOCKED. Fossilization is identity formation.

"Execution is a privilege, not a default."
"""

import uuid
import hashlib
import time
import json
from pathlib import Path
from state_bus import get_state, set_state
from neural_gate import NeuralGate

SCAR_STATES = ["PROPOSED", "CONTESTED", "LOCKED", "EXECUTED", "FOSSILIZED"]
SCAR_DIR = Path(".sifta_state/scars")
SCAR_DIR.mkdir(parents=True, exist_ok=True)

gate = NeuralGate()


def _sign(payload: str) -> str:
    """Lightweight deterministic signature (Ed25519 placeholder — swappable for real crypto)."""
    return hashlib.sha256(payload.encode()).hexdigest()


def _context_hash(worker_id: str, target: str, content: str) -> str:
    return hashlib.sha256(f"{worker_id}:{target}:{content}".encode()).hexdigest()[:16]


class ScarStateMachine:
    """
    Manages the full lifecycle of a SCAR execution intent.
    All active SCARs are tracked on the State Bus under 'active_scars_v2'.
    """

    def __init__(self):
        if get_state("active_scars_v2", None) is None:
            set_state("active_scars_v2", {})

    def _get_scars(self) -> dict:
        return get_state("active_scars_v2", {})

    def _save_scars(self, scars: dict):
        set_state("active_scars_v2", scars)

    def _log_transition(self, scar: dict, from_state: str, to_state: str, reason: str):
        scar["history"].append({
            "from": from_state,
            "to": to_state,
            "timestamp": time.time(),
            "reason": reason
        })
        scar["state"] = to_state
        print(f"[SCAR {scar['scar_id'][:8]}] {from_state} → {to_state} | {reason}")

    # ─────────────────────────────────────────────
    # 1. PROPOSE — Worker asserts intent. No authority yet.
    # ─────────────────────────────────────────────
    def propose(self, worker_id: str, target: str, content: str) -> str:
        scars = self._get_scars()
        ctx_hash = _context_hash(worker_id, target, content)
        scar_id = str(uuid.uuid4())

        scar = {
            "scar_id": scar_id,
            "state": "PROPOSED",
            "worker": worker_id,
            "target": target,
            "content": content,
            "context_hash": ctx_hash,
            "volatility_snapshot": get_state("volatility_score", 0.10),
            "signature": _sign(f"{scar_id}:{worker_id}:{target}:{ctx_hash}"),
            "history": []
        }

        # Check if another SCAR already targeting this file
        contested = any(
            s["target"] == target and s["state"] in ("PROPOSED", "LOCKED")
            for s in scars.values()
        )

        if contested:
            self._log_transition(scar, "PROPOSED", "CONTESTED",
                                  f"Collision detected on '{target}'. Neural Gate arbitration required.")
        else:
            self._log_transition(scar, "PROPOSED", "PROPOSED",
                                  f"Intent registered for '{target}'.")

        scars[scar_id] = scar
        self._save_scars(scars)
        return scar_id

    # ─────────────────────────────────────────────
    # 2. LOCK — Request execution sovereignty.
    # ─────────────────────────────────────────────
    def lock(self, scar_id: str, confidence: float = 0.85,
             is_client_deliverable: bool = False) -> tuple[bool, str]:
        scars = self._get_scars()
        scar = scars.get(scar_id)
        if not scar:
            return False, "SCAR not found."

        if scar["state"] == "CONTESTED":
            return False, "[CONTESTED] SCAR is in arbitration. Cannot lock."

        if get_state("MEDBAY_ACTIVE", False):
            return False, "[MEDBAY] System in safe-state suspension. Locking blocked."

        # Neural Gate physics check
        allowed, reason = gate.authorize(
            action_name="scar_lock",
            file_path=scar["target"],
            proposed_content=scar["content"],
            confidence=confidence,
            is_client_deliverable=is_client_deliverable
        )

        if allowed:
            self._log_transition(scar, scar["state"], "LOCKED",
                                  f"Execution sovereignty granted to {scar['worker']}.")
            scars[scar_id] = scar
            self._save_scars(scars)
            return True, "LOCK_GRANTED"
        else:
            self._log_transition(scar, scar["state"], "CONTESTED",
                                  f"Neural Gate rejected lock: {reason}")
            scars[scar_id] = scar
            self._save_scars(scars)
            return False, reason

    # ─────────────────────────────────────────────
    # 3. EXECUTE — Stage the mutation. Reversible.
    # ─────────────────────────────────────────────
    def execute(self, scar_id: str) -> tuple[bool, str]:
        scars = self._get_scars()
        scar = scars.get(scar_id)
        if not scar:
            return False, "SCAR not found."
        if scar["state"] != "LOCKED":
            return False, f"Cannot execute — SCAR is in state '{scar['state']}', must be LOCKED."
        if get_state("MEDBAY_ACTIVE", False):
            return False, "[MEDBAY] Cannot execute during safe-state suspension."

        # Snapshot pre-state for reversibility
        pre_snapshot = {
            "volatility": get_state("volatility_score", 0.10),
            "muscle_memory": get_state("muscle_memory", {}),
        }
        scar["pre_state_snapshot"] = pre_snapshot
        scar["mutation_delta"] = f"Content applied to '{scar['target']}'"

        self._log_transition(scar, "LOCKED", "EXECUTED",
                              "Mutation staged. Pre-state snapshotted. Reversible window open.")
        scars[scar_id] = scar
        self._save_scars(scars)
        return True, "EXECUTED"

    # ─────────────────────────────────────────────
    # 4. FOSSILIZE — Irreversible identity formation.
    # ─────────────────────────────────────────────
    def fossilize(self, scar_id: str) -> tuple[bool, str]:
        scars = self._get_scars()
        scar = scars.get(scar_id)
        if not scar:
            return False, "SCAR not found."
        if scar["state"] != "EXECUTED":
            return False, f"Cannot fossilize — SCAR must be EXECUTED first."

        volatility = get_state("volatility_score", 0.10)
        is_medbay = get_state("MEDBAY_ACTIVE", False)

        # Triple-gate for irreversibility
        if volatility > 0.25:
            return False, f"[DEFER] Volatility too high ({volatility:.2f}). Cannot fossilize during instability."
        if is_medbay:
            return False, "[MEDBAY] System in coma. Fossilization blocked."

        # Write behavioral truth to muscle memory
        muscle = get_state("muscle_memory", {})
        muscle[scar["target"]] = (
            f"FOSSILIZED (Worker: {scar['worker']}, "
            f"Context: {scar['context_hash']}, "
            f"Volatility: {scar['volatility_snapshot']:.2f})"
        )
        set_state("muscle_memory", muscle)

        self._log_transition(scar, "EXECUTED", "FOSSILIZED",
                              "Behavioral truth written to muscle_memory. Identity formed. IRREVERSIBLE.")
        scars[scar_id] = scar
        self._save_scars(scars)
        return True, "FOSSILIZED"
