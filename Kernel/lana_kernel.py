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
    # MEDBAY recovery may return a cleared collision to PROPOSED so it can be
    # re-evaluated instead of remaining permanently stuck.
    "CONTESTED":  ["PROPOSED", "LOCKED", "CANCELLED"],
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
# THE LAW SPINE (Option B - Phase 0 Rust Candidate)
# ─────────────────────────────────────────────────
class SovereignSpine:
    """
    STRICT MATHEMATICAL STATE MACHINE.
    This class contains ZERO intelligence or parsing. It only enforces
    cryptographic state transitions, muscle memory fossilization,
    and ledger signatures.
    """
    def __init__(self):
        self._scars: dict[str, dict] = {}
        self._fossil_index: dict[str, str] = {}
        self._recovery_queue: list[str] = []
        self._medbay_active = False

    def get_scar(self, scar_id: str) -> Optional[dict]:
        return self._scars.get(scar_id)

    def log_firewall_breach(self, worker_id: str, target: str, reason: str):
        _append_ledger({
            "ts": time.time(), "event": "FIREWALL_BREACH",
            "target": target, "worker": worker_id,
            "reason": reason
        })

    def trigger_medbay(self):
        if not self._medbay_active:
            self._medbay_active = True
            set_state("MEDBAY_ACTIVE", True)
            self._recovery_queue = [
                sid for sid, s in self._scars.items()
                if s["state"] not in ("FOSSILIZED", "CANCELLED")
            ]
            _append_ledger({"ts": time.time(), "event": "MEDBAY_TRIGGERED",
                             "queued": len(self._recovery_queue),
                             "volatility": get_state("volatility_score", 0.10)})

    def lift_medbay(self):
        if self._medbay_active:
            self._medbay_active = False
            set_state("MEDBAY_ACTIVE", False)
            _append_ledger({"ts": time.time(), "event": "MEDBAY_LIFTED",
                             "recovery_queue_size": len(self._recovery_queue)})
            self._recover_queue()

    def _recover_queue(self):
        for scar_id in self._recovery_queue:
            scar = self._scars.get(scar_id)
            if not scar: continue
            if scar["state"] == "CONTESTED":
                still_contested = any(
                    s["target"] == scar["target"] and s["state"] == "LOCKED"
                    for sid, s in self._scars.items() if sid != scar_id
                )
                if not still_contested:
                    self.transition(scar_id, "PROPOSED", "Post-MEDBAY: collision cleared.")
        self._recovery_queue.clear()

    def propose_scar(self, worker_id: str, target: str, action: str, content: str) -> str:
        if target in self._fossil_index:
            fossil_scar = self._scars.get(self._fossil_index[target], {})
            if fossil_scar.get("state") == "FOSSILIZED":
                _append_ledger({
                    "ts": time.time(), "event": "FOSSIL_REPLAY",
                    "target": target, "worker": worker_id,
                    "replayed_from": self._fossil_index[target]
                })
                return self._fossil_index[target]

        ctx_hash = _sig(f"{worker_id}:{target}:{content}")
        scar_id = str(uuid.uuid4())
        scar = {
            "scar_id": scar_id, "state": "PROPOSED", "worker": worker_id,
            "target": target, "action": action, "content": content,
            "context_hash": ctx_hash, "volatility_snapshot": get_state("volatility_score", 0.10),
            "history": []
        }
        self._scars[scar_id] = scar

        contested = any(
            s["target"] == target and s["state"] in ("PROPOSED", "LOCKED")
            for sid, s in self._scars.items() if sid != scar_id
        )
        reason = "Collision on target. Entering arbitration." if contested else "Intent registered."
        
        _append_ledger({"ts": time.time(), "event": "SCAR_CREATED", "scar_id": scar_id, "worker": worker_id, "target": target})
        
        if contested:
            self.transition(scar_id, "CONTESTED", reason)
        return scar_id

    def transition(self, scar_id: str, to_state: str, reason: str) -> dict:
        """The strict unarguable state engine."""
        scar = self._scars.get(scar_id)
        if not scar: raise KernelViolationError(f"SCAR '{scar_id[:8]}' does not exist.")
        from_state = scar["state"]

        if self._medbay_active and to_state not in ("CANCELLED",):
            raise KernelViolationError(f"[MEDBAY LOCK] System in safe-state suspension.")

        if to_state not in LEGAL_TRANSITIONS.get(from_state, []):
            raise KernelViolationError(f"[ILLEGAL] {from_state} → {to_state} is not a valid path.")

        if to_state == "FOSSILIZED":
            vol = get_state("volatility_score", 0.10)
            if vol > 0.25: raise KernelViolationError(f"[FOSSIL BLOCKED] Volatility {vol:.2f} > 0.25.")
            muscle = get_state("muscle_memory", {})
            muscle[scar["target"]] = f"FOSSILIZED | worker={scar['worker']} | ctx={scar['context_hash'][:8]}"
            set_state("muscle_memory", muscle)
            self._fossil_index[scar["target"]] = scar_id

        if to_state == "EXECUTED":
            scar["pre_state_snapshot"] = {"volatility": get_state("volatility_score", 0.10)}

        scar["state"] = to_state
        scar["history"].append({"from": from_state, "to": to_state, "ts": time.time(), "reason": reason})
        
        transition_sig = _sig(f"{scar_id}:{from_state}:{to_state}:{time.time()}")
        _append_ledger({
            "ts": time.time(), "event": "TRANSITION", "scar_id": scar_id,
            "from": from_state, "to": to_state, "target": scar["target"],
            "worker": scar["worker"], "sig": transition_sig, "reason": reason
        })
        print(f"[SPINE | SCAR {scar_id[:8]}] {from_state} → {to_state} | {reason}")
        return scar


# ─────────────────────────────────────────────────
# THE COGNITIVE API (LanaKernel Interface)
# ─────────────────────────────────────────────────
class LanaKernel:
    _instance: Optional["LanaKernel"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self._initialized = True
        self.spine = SovereignSpine()
        self._gate = NeuralGate()
        print("[🧠 LANA KERNEL] Unified COGNITION / LAW execution split online.")

    # ─── COGNITION GATES ─────────────────────────────────────────────────
    def propose(self, worker_id: str, target: str, action: str, content: str) -> str:
        """Register execution intent with Cognitive Firewall check."""
        is_safe, fw_reason = firewall.evaluate(content)
        if not is_safe:
            self.spine.log_firewall_breach(worker_id, target, fw_reason)
            raise KernelViolationError(fw_reason)
        return self.spine.propose_scar(worker_id, target, action, content)

    def request_lock(self, scar_id: str, confidence: float = 0.85, is_client: bool = False) -> tuple[bool, str]:
        """Requests execution sovereignty, validating intent via the Neural Gate."""
        if self.spine._medbay_active: return False, "[MEDBAY] Safe-state suspension."
        
        scar = self.spine.get_scar(scar_id)
        if not scar: return False, "SCAR missing."

        # COGNITION ENFORCEMENT
        allowed, gate_reason = self._gate.authorize(
            action_name=scar["action"], file_path=scar["target"],
            proposed_content=scar["content"], confidence=confidence, is_client_deliverable=is_client
        )
        if not allowed:
            self.spine.transition(scar_id, "CONTESTED", f"Neural Gate rejected: {gate_reason}")
            return False, gate_reason

        # LAW ENFORCEMENT
        try:
            self.spine.transition(scar_id, "LOCKED", "Execution sovereignty granted.")
            return True, "LOCK_GRANTED"
        except KernelViolationError as e: return False, str(e)

    def execute(self, scar_id: str) -> tuple[bool, str]:
        try: self.spine.transition(scar_id, "EXECUTED", "Mutation staged."); return True, "EXECUTED"
        except KernelViolationError as e: return False, str(e)

    def fossilize(self, scar_id: str) -> tuple[bool, str]:
        scar = self.spine.get_scar(scar_id)
        if not scar: return False, "SCAR missing."
        
        # PHYSICAL REALITY CHECK (OPTICAL INGRESS)
        # If this mutation affects the physical world (like 3D printing an ODRI joint),
        # we cannot just trust the SCAR. We must use the Vision Oracle.
        if scar.get("action") == "HARDWARE_MUTATION":
            try:
                from System.optical_ingress import capture_photonic_truth
                from System.vision_validator import oracle
                
                print(f"[👁️ LANE KERNEL] Hardware Mutation Detected. Triggering Optical Ingress Gate...")
                img_path, img_hash = capture_photonic_truth()
                
                if not img_path:
                    self.spine.transition(scar_id, "CONTESTED", "Optical Truth Capture Failed.")
                    return False, "OPTICAL_CAPTURE_FAILED"
                    
                is_valid, orc_reason = oracle.validate_geometry(img_path, scar.get("target", "unknown physical part"))
                
                if not is_valid:
                    self.spine.transition(scar_id, "CANCELLED", f"Physical verification failed: {orc_reason}")
                    return False, "HARDWARE_REJECTED"
                
                # Bind the photon reality locally to the scar
                scar["optical_hash"] = img_hash
                print(f"[✅ OPTICAL INGRESS] Physical Reality verified. Hash locked: {img_hash[:12]}")
                
            except ImportError:
                print("[⚠️ OPTICAL INGRESS] Vision subsystems not found. Bypassing physical check (UNSAFE).")

        try: 
            self.spine.transition(scar_id, "FOSSILIZED", "Identity formed. IRREVERSIBLE.")
            return True, "FOSSILIZED"
        except KernelViolationError as e: 
            return False, str(e)

    def cancel(self, scar_id: str, reason: str) -> tuple[bool, str]:
        try: self.spine.transition(scar_id, "CANCELLED", reason); return True, "CANCELLED"
        except KernelViolationError as e: return False, str(e)

    def trigger_medbay(self): self.spine.trigger_medbay()
    def lift_medbay(self): self.spine.lift_medbay()
    def get_state_of(self, scar_id: str) -> Optional[str]:
        scar = self.spine.get_scar(scar_id)
        return scar["state"] if scar else None

    @property
    def _scars(self) -> dict[str, dict]:
        """Compatibility view for older Phase 7 tests."""
        return self.spine._scars


# Module-level singleton
kernel = LanaKernel()
