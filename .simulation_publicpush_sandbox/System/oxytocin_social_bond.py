#!/usr/bin/env python3
"""
oxytocin_social_bond.py — Social bonding, trust weighting, attachment memory.
══════════════════════════════════════════════════════════════════════════════
Biology:
  Paraventricular nucleus (PVN) → oxytocin (OT) release → amygdala, hippocampus,
  striatum, brainstem. Insel & Young (2001): OT drives pair-bond formation and
  social memory. Meyer-Lindenberg *et al.* (2011): OT modulates limbic reactivity in
  social contexts. Heinrichs *et al.* (2003): social support × OT context and
  stress-axis buffering (metaphor: dampen spurious threat tagging for bonded sources).

Function:
  1. BOND REGISTRY — OT bond strength [0,1] per source ticker.
  2. TRUST MODULATION — soften non-critical THREAT for high-bond sources; boost
     attention; small DA expected_affinity nudge.
  3. SOCIAL MEMORY — append-only JSONL for consolidation priors.
  4. ARCHITECT — ARCHITECT_COMMAND / is_architect → large OT pulse.

Hard contract:
  IMMUNE_ALERT and IDENTITY_CONTRADICTION are NEVER softened by OT.

Biology anchors:
  Insel & Young, Nat Rev Neurosci 2:129 (2001). DOI `10.1038/35053579`
  Meyer-Lindenberg *et al.*, Nat Rev Neurosci 12:524 (2011). DOI `10.1038/nrn3044`
  Heinrichs *et al.*, Biol Psychiatry 54:1389 (2003). DOI `10.1016/S0006-3223(03)00465-7`
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
SIFTA_STATE = _REPO / ".sifta_state"
BOND_REGISTRY = SIFTA_STATE / "oxytocin_bond_registry.json"
SOCIAL_MEMORY = SIFTA_STATE / "oxytocin_social_memory.jsonl"
OT_STATE = SIFTA_STATE / "oxytocin_state.json"

OT_OU_THETA = 0.02
OT_BASELINE = 0.10
OT_MAX = 1.00
OT_GAIN_ARCHITECT = 0.25
OT_GAIN_REWARD = 0.08
OT_GAIN_NEUTRAL = 0.02
OT_LOSS_THREAT = 0.12

TRUST_SUPPRESS_THREAT_FLOOR = 0.55
TRUST_BOOST_FLOOR = 0.40
TRUST_SOCIAL_REWARD_FLOOR = 0.60
BOND_ATTENTION_BOOST = 0.18

HARDCODED_THREAT_TYPES = frozenset({"IMMUNE_ALERT", "IDENTITY_CONTRADICTION"})


@dataclass
class OxytocinModulation:
    source: str
    bond_strength: float
    ot_level: float
    attention_boost: float
    threat_suppressed: bool
    social_reward_nudge: float
    is_architect: bool
    reason: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "bond_strength": round(self.bond_strength, 4),
            "ot_level": round(self.ot_level, 4),
            "attention_boost": round(self.attention_boost, 4),
            "threat_suppressed": self.threat_suppressed,
            "social_reward_nudge": round(self.social_reward_nudge, 4),
            "is_architect": self.is_architect,
            "reason": self.reason,
            "ts": self.ts,
        }


class OxytocinSocialBond:
    """
    Call .interact() for each signal after thalamic gating; apply modulation before
    amygdala / DA tick as appropriate.
    """

    def __init__(self) -> None:
        self._bonds: Dict[str, float] = self._load_bonds()
        saved = self._load_state()
        self._systemic_ot = float(saved.get("systemic_ot", 0.30))
        self._last_ts = float(saved.get("last_ts", time.time()))
        self._interaction_ct = int(saved.get("interaction_ct", 0))

    def interact(
        self,
        source: str,
        signal_type: str,
        valence_hint: str = "NEUTRAL",
        is_architect: bool = False,
    ) -> OxytocinModulation:
        now = time.time()
        dt = max(now - self._last_ts, 1e-3)
        self._last_ts = now
        self._interaction_ct += 1

        self._decay_bonds(dt)

        bond = self._bonds.get(source, OT_BASELINE)
        ot_release = 0.0
        arch = is_architect

        if arch or signal_type == "ARCHITECT_COMMAND":
            ot_release = OT_GAIN_ARCHITECT
            arch = True
        elif signal_type in HARDCODED_THREAT_TYPES:
            # Sterile immune / identity flags: no OT "gain" from neutral path; no bond gardening.
            ot_release = 0.0
        elif valence_hint == "REWARD":
            ot_release = OT_GAIN_REWARD
        elif valence_hint == "THREAT":
            ot_release = -OT_LOSS_THREAT
        else:
            ot_release = OT_GAIN_NEUTRAL

        bond = max(OT_BASELINE, min(OT_MAX, bond + ot_release))
        self._bonds[source] = bond

        self._systemic_ot = min(
            OT_MAX,
            max(0.0, self._systemic_ot * 0.92 + ot_release * 0.08 + 0.01),
        )

        threat_suppressed = False
        attention_boost = 0.0
        social_reward_nudge = 0.0
        reason_parts: List[str] = []

        if (
            valence_hint == "THREAT"
            and signal_type not in HARDCODED_THREAT_TYPES
            and bond >= TRUST_SUPPRESS_THREAT_FLOOR
        ):
            threat_suppressed = True
            reason_parts.append(
                f"TRUST_SHIELD: bond={bond:.3f}>={TRUST_SUPPRESS_THREAT_FLOOR} -> THREAT->NEUTRAL"
            )

        if bond >= TRUST_BOOST_FLOOR:
            attention_boost = BOND_ATTENTION_BOOST * (bond - TRUST_BOOST_FLOOR)
            reason_parts.append(f"BOND_BOOST: +{attention_boost:.3f} attention")

        if bond >= TRUST_SOCIAL_REWARD_FLOOR:
            social_reward_nudge = (bond - TRUST_SOCIAL_REWARD_FLOOR) * 0.30
            reason_parts.append(f"SOCIAL_REWARD: +{social_reward_nudge:.3f} DA nudge")

        if arch:
            reason_parts.append("ARCHITECT_RECOGNIZED: OT pulse")

        reason = " | ".join(reason_parts) if reason_parts else "Baseline OT interaction"

        mod = OxytocinModulation(
            source=source,
            bond_strength=bond,
            ot_level=self._systemic_ot,
            attention_boost=attention_boost,
            threat_suppressed=threat_suppressed,
            social_reward_nudge=social_reward_nudge,
            is_architect=arch,
            reason=reason,
        )
        self._log_social(source, signal_type, valence_hint, bond, arch)
        self._persist()
        return mod

    def bond_strength(self, source: str) -> float:
        return self._bonds.get(source, OT_BASELINE)

    def top_bonds(self, n: int = 5) -> List[Tuple[str, float]]:
        return sorted(self._bonds.items(), key=lambda x: -x[1])[:n]

    def _decay_bonds(self, dt: float) -> None:
        for src in list(self._bonds):
            b = self._bonds[src]
            b = b + OT_OU_THETA * (OT_BASELINE - b) * dt
            self._bonds[src] = max(OT_BASELINE, min(OT_MAX, b))

    def _log_social(
        self,
        source: str,
        sig_type: str,
        valence: str,
        bond: float,
        is_architect: bool,
    ) -> None:
        from System.jsonl_file_lock import append_line_locked

        row = {
            "source": source,
            "signal_type": sig_type,
            "valence": valence,
            "bond": round(bond, 4),
            "is_architect": is_architect,
            "ts": time.time(),
        }
        SIFTA_STATE.mkdir(parents=True, exist_ok=True)
        append_line_locked(SOCIAL_MEMORY, json.dumps(row, ensure_ascii=False) + "\n")

    def _load_bonds(self) -> Dict[str, float]:
        if not BOND_REGISTRY.exists():
            return {}
        try:
            raw = json.loads(BOND_REGISTRY.read_text(encoding="utf-8"))
            return {k: float(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _load_state(self) -> Dict[str, float]:
        if not OT_STATE.exists():
            return {}
        try:
            return json.loads(OT_STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _persist(self) -> None:
        SIFTA_STATE.mkdir(parents=True, exist_ok=True)
        BOND_REGISTRY.write_text(
            json.dumps({k: round(v, 6) for k, v in self._bonds.items()}, indent=2),
            encoding="utf-8",
        )
        OT_STATE.write_text(
            json.dumps(
                {
                    "systemic_ot": round(self._systemic_ot, 6),
                    "last_ts": self._last_ts,
                    "interaction_ct": self._interaction_ct,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    print("=== OXYTOCIN SOCIAL BOND ENGINE — SMOKE TEST ===\n")
    ot = OxytocinSocialBond()
    scenarios: List[Tuple[str, str, str, bool, str]] = [
        ("ARCHITECT", "ARCHITECT_COMMAND", "NEUTRAL", True, "Architect first contact"),
        ("ARCHITECT", "ARCHITECT_COMMAND", "REWARD", True, "Architect reward"),
        ("CP2F", "PROBE_RESPONSE", "REWARD", False, "CP2F reward"),
        ("CP2F", "PROBE_RESPONSE", "NEUTRAL", False, "CP2F neutral"),
        ("AG31", "PROBE_RESPONSE", "NEUTRAL", False, "AG31 first encounter"),
        ("UNKNOWN_X", "PROBE_RESPONSE", "THREAT", False, "Unknown threat erodes"),
        ("CP2F", "PROBE_RESPONSE", "THREAT", False, "CP2F threat (low bond — no shield)"),
        ("ARCHITECT", "ARCHITECT_COMMAND", "REWARD", True, "Architect peak"),
    ]
    for src, stype, valence, is_arch, label in scenarios:
        mod = ot.interact(src, stype, valence, is_arch)
        sup = " THREAT->NEUTRAL" if mod.threat_suppressed else ""
        crown = " ARCHITECT" if mod.is_architect else ""
        print(f"[{src:<10}] {label}")
        print(f"    bond={mod.bond_strength:.3f} ot={mod.ot_level:.3f} attn+={mod.attention_boost:.3f}{sup}{crown}")
        print(f"    {mod.reason}\n")

    print("--- primed: CP2F trust shield (bond >= 0.55) ---\n")
    for _ in range(12):
        ot.interact("CP2F", "PROBE_RESPONSE", "REWARD", False)
    mod = ot.interact("CP2F", "PROBE_RESPONSE", "THREAT", False)
    sup = " THREAT->NEUTRAL" if mod.threat_suppressed else ""
    print(f"[CP2F      ] threat after 12x reward (expect shield)")
    print(f"    bond={mod.bond_strength:.3f} suppressed={mod.threat_suppressed}{sup}")
    print(f"    {mod.reason}\n")

    print("--- primed: IMMUNE_ALERT ignores bond ---\n")
    for _ in range(12):
        ot.interact("UNKNOWN_X", "PROBE_RESPONSE", "REWARD", False)
    mod = ot.interact("UNKNOWN_X", "IMMUNE_ALERT", "THREAT", False)
    print(f"[UNKNOWN_X ] IMMUNE_ALERT with high bond (never softens)")
    print(f"    bond={mod.bond_strength:.3f} suppressed={mod.threat_suppressed}")
    print(f"    {mod.reason}\n")
