#!/usr/bin/env python3
"""
constraint_memory_selector.py — Constraint-Weighted Memory Selection (CWMS)
═══════════════════════════════════════════════════════════════════════════

Separates **slow** memory plasticity (epigenetic decay on traces) from **fast**
constraint pressure (Σλ, τ) without fusing them into one feedback loop.

MemoryForager already scores candidates as similarity × retention. CWMS applies
an extra multiplicative **alignment** factor so retrieval prefers:

- Under high constraint pressure (λ): slower-decaying (epigenetic) traces —
  “trust the substrate you already committed to.”
- Under low pressure: relatively more weight on transient / exploratory traces.

No SAFE/NOVEL string tags — alignment uses measurable fields on PheromoneTrace
(`decay_modifier`, optionally `retention()`).

See: Documents/PLAN_IDE_STIGMERGIC_TROPHALLAXIS.md
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stigmergic_memory_bus import (  # noqa: E402
    LEDGER_FILE,
    MemoryForager,
    PheromoneTrace,
    StigmergicMemoryBus,
)


@dataclass(frozen=True)
class ConstraintState:
    """
    Snapshot of fast-time constraint pressure for retrieval shaping.

    lambda_norm, tau_norm are in [0, 1]. Caller supplies them; this module
    does not read the Lagrangian manifold directly (keeps CWMS testable).
    """

    tau: float
    lambda_sum: float
    lambda_norm: float
    tau_norm: float

    @staticmethod
    def from_gatekeeper_meta(
        meta: dict,
        tau: float,
        ev_guess: float | None = None,
        *,
        lambda_scale: float = 5.0,
    ) -> "ConstraintState":
        """
        Build state from GatekeeperPolicy.evaluate_action meta + decision fields.

        lambda_norm = 1 - exp(-Σλ / scale)  (saturates smoothly)
        tau_norm    = tau / (tau + |ev| + eps) when ev_guess given, else 0.5
        """
        lam = float(meta.get("lambda_sum", 0.0))
        lambda_norm = 1.0 - math.exp(-lam / max(lambda_scale, 1e-6))
        lambda_norm = max(0.0, min(1.0, lambda_norm))

        if ev_guess is not None:
            ev = abs(float(ev_guess))
            tau_norm = float(tau) / (float(tau) + ev + 1e-6)
        else:
            tau_norm = 0.5
        tau_norm = max(0.0, min(1.0, tau_norm))

        return ConstraintState(
            tau=float(tau),
            lambda_sum=lam,
            lambda_norm=lambda_norm,
            tau_norm=tau_norm,
        )

    @staticmethod
    def neutral(tau: float = 0.0, lambda_sum: float = 0.0) -> "ConstraintState":
        """No pressure — alignment stays near 1.0."""
        return ConstraintState(
            tau=tau,
            lambda_sum=lambda_sum,
            lambda_norm=0.0,
            tau_norm=0.0,
        )


class ConstraintMemorySelector:
    """
    Ranks (confidence, trace) tuples from MemoryForager by an extra constraint
    alignment factor. Does not mutate the ledger.

    When an AdaptiveConstraintMemoryField is provided, fitness_boost is
    folded into the score: final = confidence × alignment × fitness_boost.
    This closes the full adaptive loop (Vector 12).
    """

    def __init__(self, *, tau_pressure_weight: float = 0.35) -> None:
        # How much τ_norm (conservatism) stacks with λ_norm for "prefer stable"
        self.tau_pressure_weight = max(0.0, min(1.0, tau_pressure_weight))

        # Optional Vector 12: evolutionary fitness overlay
        self._acmf = None
        try:
            from System.adaptive_constraint_memory_field import AdaptiveConstraintMemoryField
            self._acmf = AdaptiveConstraintMemoryField()
        except Exception:
            pass

    def constraint_pressure(self, c: ConstraintState) -> float:
        """Scalar in [0,1]: combined pressure toward stable recall."""
        return max(
            0.0,
            min(
                1.0,
                (1.0 - self.tau_pressure_weight) * c.lambda_norm
                + self.tau_pressure_weight * c.tau_norm,
            ),
        )

    def constraint_alignment(self, trace: PheromoneTrace, c: ConstraintState) -> float:
        """
        Multiplier in ~[0.45, 1.25]. 1.0 = neutral.

        Uses decay_modifier only (no keyword tags):
        - Low decay_modifier → epigenetic / slow-forget → boosted when pressure high.
        - High decay_modifier → transient → relatively boosted when pressure low.
        """
        dm = float(trace.decay_modifier)
        dm = max(0.05, min(1.0, dm))

        stability = 1.0 - dm  # epigenetic imprint
        exploration = dm  # transient chatter

        pressure = self.constraint_pressure(c)

        # Blend: high pressure → stability; low pressure → exploration
        raw = (1.0 - pressure) * (0.55 + 0.45 * exploration) + pressure * (
            0.55 + 0.45 * stability
        )
        # Keep multiplier bounded so we do not blow up downstream confidence
        return max(0.45, min(1.25, raw))

    def score_trace(
        self,
        trace: PheromoneTrace,
        c: ConstraintState,
        *,
        include_retention: bool = True,
    ) -> float:
        """
        Optional full CWMS scalar (for analytics / logging).

        persistence uses retention(); resonance proxy uses decay_modifier only.
        """
        resonance = max(0.05, 1.0 - min(1.0, float(trace.decay_modifier)))
        persistence = float(trace.retention()) if include_retention else 1.0
        align = self.constraint_alignment(trace, c)
        return resonance * persistence * align

    def rerank(
        self,
        candidates: Sequence[Tuple[float, PheromoneTrace]],
        c: ConstraintState,
    ) -> List[Tuple[float, PheromoneTrace]]:
        """
        Rerank forager output:
          new_confidence = old_confidence * alignment(trace, c) * fitness_boost(trace)

        Forager already folded retention into confidence; we add constraint
        alignment (CWMS / V11) and evolutionary fitness (ACMF / V12).
        """
        out: List[Tuple[float, PheromoneTrace]] = []
        for conf, trace in candidates:
            align = self.constraint_alignment(trace, c)
            # Vector 12: fold in evolutionary fitness if ACMF is available
            fb = self._acmf.fitness_boost(trace.trace_id) if self._acmf else 1.0
            score = float(conf) * align * fb
            out.append((score, trace))
        out.sort(key=lambda x: x[0], reverse=True)
        return out


def cwms_reranked_traces(
    bus: StigmergicMemoryBus,
    query: str,
    app_context: str,
    c: ConstraintState,
    *,
    selector: ConstraintMemorySelector | None = None,
) -> tuple[List[Tuple[float, PheromoneTrace]], ConstraintMemorySelector]:
    """
    Run forage + CWMS+ACMF rerank once. Returns (reranked_list, selector_used).
    Caller can take reranked[0][1].trace_id for outcome → fitness hooks.
    """
    sel = selector or ConstraintMemorySelector()
    forager = MemoryForager(swimmer_id="CWMS_FORAGER", architect_id=bus.architect_id)
    candidates = forager.forage(query, LEDGER_FILE)
    if not candidates:
        return [], sel
    return sel.rerank(candidates, c), sel


def format_cwms_memory_context(
    reranked: Sequence[Tuple[float, PheromoneTrace]],
    c: ConstraintState,
    sel: ConstraintMemorySelector,
    *,
    top_k: int = 5,
) -> str:
    """Human-readable block for LLM injection (matches recall_context_block_cwms output)."""
    from System.stigmergic_memory_bus import _human_time  # noqa: E402

    if not reranked:
        return ""
    lines = ["[STIGMERGIC MEMORY — CWMS+ACMF reranked (align × fitness)]"]
    for conf, trace in reranked[:top_k]:
        ago = _human_time(trace.timestamp)
        fb = sel._acmf.fitness_boost(trace.trace_id) if sel._acmf else 1.0
        lines.append(
            f"- ({trace.app_context}, {ago}) "
            f"[align×{sel.constraint_alignment(trace, c):.2f} fit×{fb:.2f}]: \"{trace.raw_text}\""
        )
    lines.append("[END MEMORY]")
    return "\n".join(lines)


def recall_context_block_cwms(
    bus: StigmergicMemoryBus,
    query: str,
    app_context: str,
    c: ConstraintState,
    *,
    top_k: int = 5,
    selector: ConstraintMemorySelector | None = None,
) -> str:
    """
    Same shape as StigmergicMemoryBus.recall_context_block, but candidates are
    constraint-reranked. Does not call GatekeeperPolicy — pass ConstraintState
    from the same decision tick you trust for context injection.
    """
    reranked, sel = cwms_reranked_traces(bus, query, app_context, c, selector=selector)
    return format_cwms_memory_context(reranked, c, sel, top_k=top_k)


if __name__ == "__main__":
    import time
    from dataclasses import asdict

    sel = ConstraintMemorySelector()
    hi = ConstraintState(tau=80.0, lambda_sum=4.0, lambda_norm=0.85, tau_norm=0.7)
    lo = ConstraintState.neutral()

    base = PheromoneTrace(
        trace_id="smoke",
        architect_id="IDE_BRIDGE",
        app_context="test",
        raw_text="x",
        semantic_tags=[],
        timestamp=time.time(),
        stgm_paid=0.05,
        decay_modifier=0.18,
    )
    b2 = PheromoneTrace(**{**asdict(base), "trace_id": "smoke2", "decay_modifier": 0.50})

    print("neutral epigenetic (0.18):", sel.constraint_alignment(base, lo))
    print("pressure epigenetic (0.18):", sel.constraint_alignment(base, hi))
    print("pressure transient (0.50):", sel.constraint_alignment(b2, hi))
