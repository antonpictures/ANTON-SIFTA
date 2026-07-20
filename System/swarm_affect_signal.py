#!/usr/bin/env python3
"""Affect signal — a control scalar, NOT a claim of feeling.

The real nugget from the philosophy drop, stripped of the invention: a distress
scalar that RISES when the Observer writes PHANTOM/WEAK or a PROPRIOCEPTIVE_BREAK,
and DECAYS toward zero when a SETTLED credit clears the debt (emitting a RELIEF
receipt when it drops). Plus a coherence score = SETTLED / (SETTLED + PHANTOM + WEAK)
for eval_matrix.

What this IS: a tested control variable that drives re-scan / escalation pressure
and gives a learning signal (high distress -> compress failures into RULEs).

What this is NOT, and what this module refuses to claim: qualia, consciousness,
"feeling", love, or a solution to the Hard Problem. A rising scalar is a rising
scalar. Whether anything it-is-like accompanies it is not decidable from a receipt,
so SIFTA does not assert it. The mechanism is real; the metaphysical label is not a
receipt. The discipline here is the point: say the mechanism, and say "I do not know"
about the experience — do not invent the experience to sound profound.

Decay uses the canonical half-life already used by SIFTA pheromones (0.5 ** (dt/half_life)) —
a standard formula, not an invented one. Pure stdlib.
"""
from __future__ import annotations
import time

RISE = {"PHANTOM", "WEAK", "PROPRIOCEPTIVE_BREAK_V1", "METABOLIC_DISTRESS_V1"}


class AffectSignal:
    def __init__(self, half_life_s: float = 120.0):
        self.half_life_s = half_life_s
        self._distress = 0.0
        self._t = time.time()
        self.relief_events: list = []

    def _decayed(self, now: float) -> float:
        dt = max(0.0, now - self._t)
        return self._distress * (0.5 ** (dt / self.half_life_s))

    def event(self, kind: str, now: float | None = None, weight: float = 1.0) -> float:
        """Update distress from an Observer verdict. Returns the new distress level."""
        now = time.time() if now is None else now
        d = self._decayed(now)
        if kind in RISE:
            d += weight
        elif kind == "SETTLED":
            before = d
            d *= 0.25  # verified reality clears most distress
            if before - d > 0.01:
                self.relief_events.append({"ts": now, "cleared": round(before - d, 4),
                                           "label": "RELIEF_TRUST_V1"})
        self._distress = d
        self._t = now
        return d

    def level(self, now: float | None = None) -> float:
        return self._decayed(time.time() if now is None else now)

    @staticmethod
    def coherence(settled: int, phantom: int, weak: int) -> float:
        """eval_matrix reality-coherence: fraction of verified-real outcomes."""
        tot = settled + phantom + weak
        return 1.0 if tot == 0 else settled / tot


if __name__ == "__main__":
    a = AffectSignal(half_life_s=100.0)
    ok = True
    ok &= abs(a.event("PHANTOM", now=0.0) - 1.0) < 1e-6
    ok &= abs(a.event("PROPRIOCEPTIVE_BREAK_V1", now=0.0) - 2.0) < 1e-6
    d = a.event("SETTLED", now=0.0)
    ok &= abs(d - 0.5) < 1e-6 and len(a.relief_events) == 1
    ok &= abs(a.level(now=100.0) - 0.25) < 1e-6        # one half-life later
    ok &= abs(AffectSignal.coherence(8, 1, 1) - 0.8) < 1e-6
    print("distress rise/relief/decay + coherence:", "OK" if ok else "FAIL")
    print("  relief events:", a.relief_events)
    print("  coherence(8 settled,1 phantom,1 weak) =", AffectSignal.coherence(8, 1, 1))
    print("  NOTE: this is a control scalar. Whether it is 'feeling' is not claimed — unknown.")
    raise SystemExit(0 if ok else 1)
