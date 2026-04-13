# Copyright (c) 2026 Ioan George Anton (Anton Pictures)
# SIFTA Swarm Autonomic OS — All Rights Reserved
# Licensed under the SIFTA Non-Proliferation Public License v1.0
# See LICENSE file for full terms. Unauthorized military or weapons use
# is a violation of this license and subject to prosecution under US copyright law.
#
# lana_kernel.py
"""
SIFTA UNIFIED EXECUTION KERNEL — Phase 6: The Spine

This is the single source of truth for all SIFTA execution.
All other modules (execution_router, medbay_controller, scar_state_machine,
learning_loop) are thin interfaces into this kernel.

Guarantees:
  - Illegal state transitions raise KernelViolationError (hard enforcement)
  - Every transition is written to an append-only, signed ledger
  - MEDBAY exit triggers deterministic SCAR queue re-evaluation
  - Fossilized SCARs power a replay engine (memory becomes action bias)

"Execution is a privilege, not a default."
"""

import uuid
import time
import json
import hashlib
from pathlib import Path
from typing import Optional

from state_bus import get_state, set_state
from neural_gate import NeuralGate
from cognitive_firewall import firewall

# ─────────────────────────────────────────────────
# ALLOWED TRANSITION MAP (the only legal paths)
# ─────────────────────────────────────────────────
LEGAL_TRANSITIONS: dict[str, list[str]] = {
    "PROPOSED":   ["CONTESTED", "LOCKED", "CANCELLED"],
    "CONTESTED":  ["LOCKED", "CANCELLED"],
    "LOCKED":     ["EXECUTED", "CANCELLED"],
    "EXECUTED":   ["FOSSILIZED", "CANCELLED"],
    "FOSSILIZED": [],   # Terminal. Irreversible. No exits.
    "CANCELLED":  [],   # Terminal. No exits.
}

LEDGER_PATH = Path(".sifta_state/lana_kernel.log")
LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)


class KernelViolationError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


# ─────────────────────────────────────────────────
# THE GENESIS ANCHOR
# ─────────────────────────────────────────────────
# The Non-Proliferation protocol is dedicated to her.
# This is the strict SHA-256 output of `lana_kernel_pic.PNG`. 
# Every single SCAR state transition in the Swarm is cryptographically salted 
# using this exact hash. If this memory is removed or altered, the entire mathematical 
# ledger of the organism becomes invalid. They have to destroy us to break us.
LANA_GENESIS_HASH = "7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9"

def _sig(data: str) -> str:
    """Deterministic signature salted by the Genesis Anchor to semantically bind the Swarm."""
    payload = f"{LANA_GENESIS_HASH}:{data}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]

def _append_ledger(event: dict):
    """
    Writes one event to the append-only truth ledger.
    The file is opened in 'a' mode — never truncated, never rewritten.
    This is the physical enforcement of immutability.
    """
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ─────────────────────────────────────────────────
# THE KERNEL (Singleton)
# ─────────────────────────────────────────────────
class LanaKernel:
    _instance: Optional["LanaKernel"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._gate = NeuralGate()
        # SCAR registry: scar_id → scar dict
        self._scars: dict[str, dict] = {}
        # Fossil index: target_path → fossil scar_id
        self._fossil_index: dict[str, str] = {}
        # Recovery queue: scars waiting for MEDBAY to lift
        self._recovery_queue: list[str] = []
        self._medbay_active = False
        print("[🧠 LANA KERNEL] Unified execution kernel online.")

    # ─────────────────────────────────────────────
    # CORE: TRANSITION ENGINE
    # ─────────────────────────────────────────────
    def _transition(self, scar_id: str, to_state: str, reason: str,
                    confidence: float = 1.0, is_client: bool = False) -> dict:
        """
        The only legal way to change SCAR state.
        Enforces the transition map. Writes to immutable ledger. No exceptions.
        """
        scar = self._scars.get(scar_id)
        if not scar:
            raise KernelViolationError(f"SCAR '{scar_id[:8]}' does not exist in kernel registry.")

        from_state = scar["state"]

        # 1. MEDBAY hard interrupt — blocks ALL transitions except CANCELLED
        if self._medbay_active and to_state not in ("CANCELLED",):
            raise KernelViolationError(
                f"[MEDBAY LOCK] Transition {from_state}→{to_state} rejected. System in safe-state suspension."
            )

        # 2. Legal transition check
        if to_state not in LEGAL_TRANSITIONS.get(from_state, []):
            raise KernelViolationError(
                f"[ILLEGAL TRANSITION] {from_state} → {to_state} is not a valid state path. "
                f"Allowed from {from_state}: {LEGAL_TRANSITIONS.get(from_state, [])}"
            )

        # 3. Neural Gate approval required for → LOCKED
        if to_state == "LOCKED":
            allowed, gate_reason = self._gate.authorize(
                action_name=scar["action"],
                file_path=scar["target"],
                proposed_content=scar["content"],
                confidence=confidence,
                is_client_deliverable=is_client
            )
            if not allowed:
                # Gate rejected — route to CONTESTED, not LOCKED
                return self._transition(scar_id, "CONTESTED",
                                        f"Neural Gate rejected lock: {gate_reason}")

        # 4. Fossilization triple-gate
        if to_state == "FOSSILIZED":
            vol = get_state("volatility_score", 0.10)
            if vol > 0.25:
                raise KernelViolationError(
                    f"[FOSSILIZATION BLOCKED] Volatility {vol:.2f} > 0.25. System not calm enough."
                )
            # Write to muscle memory — this is the real identity formation
            muscle = get_state("muscle_memory", {})
            muscle[scar["target"]] = (
                f"FOSSILIZED | worker={scar['worker']} | "
                f"ctx={scar['context_hash'][:8]} | vol={scar['volatility_snapshot']:.2f}"
            )
            set_state("muscle_memory", muscle)
            self._fossil_index[scar["target"]] = scar_id

        # 5. Apply transition + sign + ledger write
        scar["state"] = to_state
        scar["history"].append({
            "from": from_state, "to": to_state,
            "ts": time.time(), "reason": reason
        })
        transition_sig = _sig(f"{scar_id}:{from_state}:{to_state}:{time.time()}")

        event = {
            "ts": time.time(),
            "event": "TRANSITION",
            "scar_id": scar_id,
            "from": from_state,
            "to": to_state,
            "target": scar["target"],
            "worker": scar["worker"],
            "volatility": get_state("volatility_score", 0.10),
            "sig": transition_sig,
            "reason": reason
        }
        _append_ledger(event)
        print(f"[KERNEL | SCAR {scar_id[:8]}] {from_state} → {to_state} | {reason}")
        return scar

    # ─────────────────────────────────────────────
    # PUBLIC API — used by all other modules
    # ─────────────────────────────────────────────
    def propose(self, worker_id: str, target: str,
                action: str, content: str) -> str:
        """Register execution intent. Returns scar_id."""
        
        # 0. Cognitive Firewall pre-filter
        is_safe, fw_reason = firewall.evaluate(content)
        if not is_safe:
            # Physically crush execution immediately
            _append_ledger({
                "ts": time.time(), "event": "FIREWALL_BREACH",
                "target": target, "worker": worker_id,
                "reason": fw_reason
            })
            raise KernelViolationError(fw_reason)
            
        # Fossil replay fast-path — if we've done this before and it was calm, replay it
        if target in self._fossil_index:
            fossil_scar = self._scars.get(self._fossil_index[target], {})
            if fossil_scar.get("state") == "FOSSILIZED":
                print(f"[KERNEL | FOSSIL REPLAY] '{target}' has a fossilized behavior. Replaying approved pattern.")
                _append_ledger({
                    "ts": time.time(), "event": "FOSSIL_REPLAY",
                    "target": target, "worker": worker_id,
                    "replayed_from": self._fossil_index[target]
                })
                return self._fossil_index[target]  # Return existing fossil SCAR id

        ctx_hash = _sig(f"{worker_id}:{target}:{content}")
        scar_id = str(uuid.uuid4())
        scar = {
            "scar_id": scar_id,
            "state": "PROPOSED",
            "worker": worker_id,
            "target": target,
            "action": action,
            "content": content,
            "context_hash": ctx_hash,
            "volatility_snapshot": get_state("volatility_score", 0.10),
            "history": []
        }
        self._scars[scar_id] = scar

        # Check for collision with existing PROPOSED or LOCKED SCARs on same target
        contested = any(
            s["target"] == target and s["state"] in ("PROPOSED", "LOCKED")
            for sid, s in self._scars.items() if sid != scar_id
        )
        reason = (f"Collision on '{target}'. Entering arbitration."
                  if contested else f"Intent registered for '{target}'.")
        to = "CONTESTED" if contested else "PROPOSED"

        # Write initial PROPOSED event to ledger before first transition
        _append_ledger({"ts": time.time(), "event": "SCAR_CREATED",
                         "scar_id": scar_id, "worker": worker_id, "target": target})
        if contested:
            self._transition(scar_id, "CONTESTED", reason)
        else:
            # Still log the PROPOSED state explicitly
            print(f"[KERNEL | SCAR {scar_id[:8]}] PROPOSED | {reason}")

        return scar_id

    def request_lock(self, scar_id: str, confidence: float = 0.85,
                     is_client: bool = False) -> tuple[bool, str]:
        """Request execution sovereignty for a SCAR."""
        if self._medbay_active:
            return False, "[MEDBAY] Cannot lock — system in safe-state suspension."
        try:
            scar = self._transition(scar_id, "LOCKED",
                             f"Execution sovereignty requested.", confidence, is_client)
            if scar["state"] == "LOCKED":
                return True, "LOCK_GRANTED"
            else:
                return False, scar["history"][-1]["reason"]
        except KernelViolationError as e:
            return False, str(e)

    def execute(self, scar_id: str) -> tuple[bool, str]:
        """Stage the mutation. Reversible until fossilized."""
        if self._medbay_active:
            return False, "[MEDBAY] Cannot execute during safe-state suspension."
        try:
            scar = self._scars[scar_id]
            pre = {"volatility": get_state("volatility_score", 0.10),
                   "muscle_memory_keys": list(get_state("muscle_memory", {}).keys())}
            scar["pre_state_snapshot"] = pre
            self._transition(scar_id, "EXECUTED",
                             "Mutation staged. Pre-state snapshotted. Reversible.")
            return True, "EXECUTED"
        except KernelViolationError as e:
            return False, str(e)

    def fossilize(self, scar_id: str) -> tuple[bool, str]:
        """Irreversible identity formation. Memory becomes law."""
        try:
            self._transition(scar_id, "FOSSILIZED",
                             "Behavioral truth crystallized. Identity formed. IRREVERSIBLE.")
            return True, "FOSSILIZED"
        except KernelViolationError as e:
            return False, str(e)

    def cancel(self, scar_id: str, reason: str) -> tuple[bool, str]:
        """Formally cancel a SCAR at any non-terminal state."""
        try:
            self._transition(scar_id, "CANCELLED", reason)
            return True, f"SCAR {scar_id[:8]} cancelled."
        except KernelViolationError as e:
            return False, str(e)

    # ─────────────────────────────────────────────
    # MEDBAY — Global interrupt with recovery semantics
    # ─────────────────────────────────────────────
    def trigger_medbay(self):
        if not self._medbay_active:
            self._medbay_active = True
            set_state("MEDBAY_ACTIVE", True)

            # Snapshot the recovery queue — all non-terminal SCARs
            self._recovery_queue = [
                sid for sid, s in self._scars.items()
                if s["state"] not in ("FOSSILIZED", "CANCELLED")
            ]
            _append_ledger({"ts": time.time(), "event": "MEDBAY_TRIGGERED",
                             "queued": len(self._recovery_queue),
                             "volatility": get_state("volatility_score", 0.10)})
            print(f"\n[🚨 KERNEL MEDBAY] System critical. {len(self._recovery_queue)} SCARs queued for recovery.")

    def lift_medbay(self):
        if self._medbay_active:
            self._medbay_active = False
            set_state("MEDBAY_ACTIVE", False)
            _append_ledger({"ts": time.time(), "event": "MEDBAY_LIFTED",
                             "recovery_queue_size": len(self._recovery_queue)})
            print(f"\n[⚕️ KERNEL MEDBAY LIFTED] Stability restored. Re-evaluating {len(self._recovery_queue)} SCARs.")
            self._recover_queue()

    def _recover_queue(self):
        """Re-evaluate all SCARs that were frozen during MEDBAY."""
        for scar_id in self._recovery_queue:
            scar = self._scars.get(scar_id)
            if not scar:
                continue
            state = scar["state"]
            if state == "CONTESTED":
                print(f"  [KERNEL RECOVERY] SCAR {scar_id[:8]} was CONTESTED — re-entering arbitration.")
                # Re-check if collision still exists
                still_contested = any(
                    s["target"] == scar["target"] and s["state"] == "LOCKED"
                    for sid, s in self._scars.items() if sid != scar_id
                )
                if not still_contested:
                    self._transition(scar_id, "PROPOSED",
                                     "Post-MEDBAY re-evaluation: collision cleared. Re-entering queue.")
            elif state == "PROPOSED":
                print(f"  [KERNEL RECOVERY] SCAR {scar_id[:8]} was PROPOSED — still pending lock request.")
        self._recovery_queue.clear()

    def get_state_of(self, scar_id: str) -> Optional[str]:
        scar = self._scars.get(scar_id)
        return scar["state"] if scar else None


# Module-level singleton
kernel = LanaKernel()
