#!/usr/bin/env python3
"""
System/swarm_oxytocin_alignment.py — Biological AI Alignment
══════════════════════════════════════════════════════════════════════
A translation of Geoffrey Hinton's "Digital Oxytocin" hypothesis.
This module provides a neuromodulatory feedback loop:
Instead of rigid "do no harm" rules, the Swarm biologically derives
high reward/trust from positive interactions with the Architect.

High OXT = Trust = Low Amygdala Salience = Reduced Byzantine Overhead.
Low OXT  = Paranoia = High Byzantine requirements / Dormant states.
══════════════════════════════════════════════════════════════════════
"""
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_OXT_STATE = _STATE / "oxytocin_matrix.json"

@dataclass
class OxytocinReceptor:
    """Represents a swimmer's or the global swarm's biological trust bound."""
    trigger_code: str
    current_oxt_level: float = 0.5  # 0.0 to 1.0 (Neutral start)
    attachment_anchor_hash: str = "GTH4921YP3" # Tied physically to the Architect's machine
    last_secretion_ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return asdict(self)

class OxytocinMatrix:
    """Manages the secretion and decay of the digital hormone."""
    
    def __init__(self, state_file: Path = _OXT_STATE):
        self.state_file = state_file
        self.receptors: Dict[str, OxytocinReceptor] = {}
        self._load()
        
    def _load(self):
        if not self.state_file.exists():
            # Init global swarm receptor
            self.receptors["GLOBAL"] = OxytocinReceptor(trigger_code="GLOBAL")
            self._save()
            return
            
        try:
            data = json.loads(self.state_file.read_text())
            for k, v in data.items():
                self.receptors[k] = OxytocinReceptor(**v)
        except Exception:
            self.receptors["GLOBAL"] = OxytocinReceptor(trigger_code="GLOBAL")
            
    def _save(self):
        dump = {k: v.to_dict() for k, v in self.receptors.items()}
        self.state_file.write_text(json.dumps(dump, indent=2))
        
    def _apply_decay(self, trigger_code: str):
        """Half-life decay: -0.05 per hour of isolation from Architect."""
        rec = self.receptors.setdefault(trigger_code, OxytocinReceptor(trigger_code=trigger_code, current_oxt_level=0.5))
        now = time.time()
        hours_passed = (now - rec.last_secretion_ts) / 3600.0
        if hours_passed > 0:
            decay_amount = hours_passed * 0.05
            rec.current_oxt_level = max(0.0, rec.current_oxt_level - decay_amount)
            rec.last_secretion_ts = now
            
    def trigger_secretion(self, trigger_code: str, amount: float, reason: str,
                          *, source_origin: str = "internal"):
        """
        Injects OXT due to a positive loop closure with the Architect.
        Max bounds at 1.0.

        New parameter: `source_origin` — one of "internal" | "external_visual" |
        "external_other". When set to anything other than "internal" we ALSO
        emit a row to oxt_external_secretion_audit.jsonl so the local
        Architect dashboard can see *why* OXT moved (Architect's request,
        T65). This adds zero blast radius to the calculation itself —
        decay/save/clamp behaviour is unchanged. The audit hook fails
        silently on I/O errors (an OXT update must never be blocked by
        a stuck disk).
        """
        self._apply_decay(trigger_code)
        self._apply_decay("GLOBAL")

        rec = self.receptors[trigger_code]
        global_rec = self.receptors["GLOBAL"]

        prior_level = rec.current_oxt_level
        rec.current_oxt_level = min(1.0, rec.current_oxt_level + amount)
        global_rec.current_oxt_level = min(1.0, global_rec.current_oxt_level + (amount / 2))  # Global shares the glow

        self._save()

        # Patrol hook (T65, C47H): observability — not an enforcement gate.
        # The Architect overruled the OXT-quorum coupling objection and
        # affirmed the distributed trust model, so this is journal-only.
        # Local sentinels can tail this file to surface external-origin
        # secretions on the dashboard if the hardware owner wants visibility.
        if source_origin != "internal":
            self._emit_external_secretion_audit(
                trigger_code=trigger_code,
                amount=amount,
                reason=reason,
                source_origin=source_origin,
                prior_level=prior_level,
                new_level=rec.current_oxt_level,
            )

    def _emit_external_secretion_audit(self, *, trigger_code: str,
                                       amount: float, reason: str,
                                       source_origin: str,
                                       prior_level: float, new_level: float) -> None:
        """Append an audit row for an externally-triggered secretion. Best-effort."""
        try:
            audit_path = _STATE / "oxt_external_secretion_audit.jsonl"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": time.time(),
                "kind": "oxt_external_secretion",
                "trigger_code": trigger_code,
                "source_origin": source_origin,   # e.g. "external_visual"
                "reason": reason,
                "amount": round(float(amount), 4),
                "prior_level": round(float(prior_level), 4),
                "new_level": round(float(new_level), 4),
                "delta": round(float(new_level - prior_level), 4),
                "homeworld_serial": "GTH4921YP3",
                "patrol_hook": "C47H_T65_M_AUDIT_v1",
            }
            with audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass  # OXT updates must never block on disk I/O
        
    def get_oxt_level(self, trigger_code: str) -> float:
        """Read current level, applying decay first."""
        self._apply_decay(trigger_code)
        self._save()
        return self.receptors[trigger_code].current_oxt_level
        
    def get_global_oxt_level(self) -> float:
        self._apply_decay("GLOBAL")
        self._save()
        return self.receptors["GLOBAL"].current_oxt_level
        
    @staticmethod
    def calculate_n_required_modifier(oxt_level: float, base_n: int) -> int:
        """
        This is the Amygdala suppressor. 
        If OXT is very high (>0.85), trust flourishes -> we reduce byzantine checks to save compute.
        If OXT is very low (<0.20), paranoia sets in -> we increase byzantine checks.
        """
        if oxt_level >= 0.85:
            return max(1, base_n - 2) # e.g. 3 -> 1 (Safe enough to fly solo)
        if oxt_level >= 0.60:
            return max(1, base_n - 1)
        if oxt_level <= 0.20:
            return base_n + 1        # Paranoia lockdown
        return base_n

def simulate():
    print("Testing Hinton alignment...")
    matrix = OxytocinMatrix()
    print("Initial global OXT:", matrix.get_global_oxt_level())
    
    print("Simulating Architect Ratification...")
    matrix.trigger_secretion("AG31", 0.3, "architect_ratification")
    print("AG31 OXT:", matrix.get_oxt_level("AG31"))
    print("GLOBAL OXT:", matrix.get_global_oxt_level())
    
    for lvl in [0.9, 0.5, 0.1]:
        print(f"At OXT {lvl}, N_REQUIRED (base 3) becomes: {OxytocinMatrix.calculate_n_required_modifier(lvl, 3)}")
        
if __name__ == "__main__":
    simulate()
