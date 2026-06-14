"""swarm_diffusion_stigmergic_policy.py — CUR-F7.1 cross-block stigmergic guidance.

The C++ unmasking enum has no per-step Python hook (OBSERVED in diffusion-cli.cpp).
This module approximates memoryful unmasking **across blocks and endurance runs** by
reusing ``StigmergicField`` (deposit / read_gradient / decay) to tune CLI flags and
track committed spans (no-double-spend).

Env:
    SIFTA_DIFFUSION_POLICY=confidence|stigmergic  (default: confidence)
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.stigmergic_field import FieldConfig, StigmergicField

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FIELD_PATH = _STATE / "diffusion_stigmergic_field.json"
_LOCKS_PATH = _STATE / "diffusion_stigmergic_locks.json"

# llama-diffusion-cli enum (diffusion-cli.cpp)
ALG_ORIGIN = 0
ALG_ENTROPY = 1
ALG_MARGIN = 2
ALG_RANDOM = 3
ALG_CONFIDENCE = 4


def active_policy() -> str:
    return os.environ.get("SIFTA_DIFFUSION_POLICY", "confidence").strip().lower() or "confidence"


def is_stigmergic_enabled() -> bool:
    return active_policy() == "stigmergic"


@dataclass
class DiffusionCliTuning:
    algorithm: int = ALG_CONFIDENCE
    steps: int = 64
    policy: str = "confidence"
    field_energy: float = 0.0
    notes: str = ""


@dataclass
class StigmergicDiffusionState:
    """Cross-run field + committed-span locks for diffusion generations."""

    stig_field: StigmergicField = dc_field(default_factory=lambda: StigmergicField(FieldConfig(n_bins=64, n_channels=2)))
    locks: Dict[str, str] = dc_field(default_factory=dict)

    @classmethod
    def load(cls) -> "StigmergicDiffusionState":
        st = cls()
        if _FIELD_PATH.is_file():
            try:
                st.stig_field = StigmergicField.load(_FIELD_PATH)
            except Exception:
                pass
        if _LOCKS_PATH.is_file():
            try:
                st.locks = json.loads(_LOCKS_PATH.read_text(encoding="utf-8"))
            except Exception:
                st.locks = {}
        return st

    def save(self) -> None:
        _STATE.mkdir(parents=True, exist_ok=True)
        self.stig_field.save(_FIELD_PATH)
        _LOCKS_PATH.write_text(json.dumps(self.locks, indent=2), encoding="utf-8")

    def tune(
        self,
        *,
        base_steps: int,
        block_length: int,
        canvas_ub: int,
        prompt_id: str = "",
    ) -> DiffusionCliTuning:
        policy = active_policy()
        if policy != "stigmergic":
            return DiffusionCliTuning(
                algorithm=ALG_CONFIDENCE,
                steps=base_steps,
                policy="confidence",
                notes="default CONFIDENCE_BASED",
            )

        num_blocks = max(1, canvas_ub // max(1, block_length))
        pid_bin = _prompt_bin(prompt_id, self.stig_field.n_bins)
        grad = self.stig_field.read_gradient(pid_bin)
        energy = self.stig_field.energy

        # Bias algorithm by field gradient magnitude (cross-block chemotaxis analogue).
        if abs(grad) > 0.15:
            algorithm = ALG_ENTROPY
            note = "high gradient -> ENTROPY_BASED exploration"
        elif abs(grad) > 0.05:
            algorithm = ALG_MARGIN
            note = "mid gradient -> MARGIN_BASED"
        else:
            algorithm = ALG_CONFIDENCE
            note = "low gradient -> CONFIDENCE_BASED commit"

        # Reinforce stable blocks: more steps when field energy is low (uncertain canvas).
        step_boost = int(min(32, max(0, (1.0 - min(energy / 100.0, 1.0)) * 16)))
        steps = min(256, base_steps + step_boost)

        # Deposit intent trace before the run (channel 0 = commit bias).
        self.stig_field.deposit(pid_bin, 0, amount=0.25 + abs(grad))
        self.stig_field.decay()

        return DiffusionCliTuning(
            algorithm=algorithm,
            steps=steps,
            policy="stigmergic",
            field_energy=energy,
            notes=f"{note}; blocks={num_blocks}; grad={grad:.4f}",
        )

    def record_generation(
        self,
        *,
        prompt_id: str,
        repeat_idx: int,
        output: str,
        previous_output: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deposit post-gen traces; verify committed span not silently rewritten."""
        pid_bin = _prompt_bin(prompt_id, self.stig_field.n_bins)
        text = (output or "").strip()
        digest = _digest(text)
        prev_digest = self.locks.get(prompt_id)
        no_double_spend_ok = True

        if prev_digest and repeat_idx > 0:
            # Locked prefix must not change across repeats (first 40 chars as commit anchor).
            anchor = text[:40]
            prev_anchor = (previous_output or "")[:40]
            if prev_anchor and anchor and anchor != prev_anchor:
                no_double_spend_ok = False
                self.stig_field.deposit(pid_bin, 1, amount=2.0)  # flip-flop penalty channel
            else:
                self.stig_field.deposit(pid_bin, 0, amount=1.0)  # stability reward

        if repeat_idx == 0 or no_double_spend_ok:
            self.locks[prompt_id] = digest

        self.stig_field.deposit(pid_bin, 0, amount=min(2.0, len(text) / 200.0))
        self.stig_field.decay()
        self.save()

        return {
            "prompt_id": prompt_id,
            "repeat_idx": repeat_idx,
            "field_energy": self.stig_field.energy,
            "no_double_spend_ok": no_double_spend_ok,
            "commit_digest": digest,
        }


def _prompt_bin(prompt_id: str, n_bins: int) -> int:
    h = hashlib.sha256(prompt_id.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % max(1, n_bins)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def coherence_score(text: str) -> float:
    """Cheap self-eval: reward complete sentences, penalize empty/repetition."""
    t = (text or "").strip()
    if not t:
        return 0.0
    words = t.split()
    if len(words) < 3:
        return 0.2
    unique_ratio = len(set(words)) / max(1, len(words))
    ends_well = 1.0 if t[-1] in ".?!" else 0.5
    return round(min(1.0, 0.35 + 0.35 * unique_ratio + 0.3 * ends_well), 3)


__all__ = [
    "ALG_CONFIDENCE",
    "ALG_ENTROPY",
    "ALG_MARGIN",
    "DiffusionCliTuning",
    "StigmergicDiffusionState",
    "active_policy",
    "coherence_score",
    "is_stigmergic_enabled",
]