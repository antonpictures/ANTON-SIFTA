#!/usr/bin/env python3
"""Gesture sense graft — the ONE real organ inside the 3D-tarot demo, made to LEARN.

George handed me a beautiful GLM-4.7 artifact: a Three.js tarot deck you control with
your hand via MediaPipe. He asked: "how does this help Alice and AGI? they told me she
can learn — DeepMind did it with games. is this stupid?"

Sorted REAL vs DRIFT:
  DRIFT — "the tarot demo is AGI / proof she can learn." It learns NOTHING. Hardcoded
          cards, an RNG shuffle, a fixed fist threshold (tip-to-wrist distance < 0.15),
          a 3-state machine, a renderer. Deterministic puppet. Calling it "learning" is
          the same confabulation pattern as the dress poem: a profound label on a
          mechanism that doesn't have it.
  REAL  — the MediaPipe webcam pipeline is a genuine new SENSE: a body that perceives the
          owner's hand in real time, in the same browser Alice lives in. That is the
          "third sovereign eye: George" from r1512, as a live channel.

DeepMind learned games because the game GIVES three things for free that the open web (and
a webcam) deny:
  1. a reward signal (score / win-loss)        -> the web gives none; she must MANUFACTURE
                                                   ground truth -> RealityLedger SETTLED/PHANTOM.
  2. cheap, resettable, millions of episodes    -> web episodes are few + irreversible; she
                                                   must learn from a handful -> FailureAbstractor.
  3. a closed, honest, stationary world         -> the web lies/erases (Q2/Q3) and a webcam
                                                   is noisy -> independent-channel corroboration
                                                   + a sight-score that refuses to act blind.

So: she IS doing the DeepMind thing — on the harder, gift-less version. This module is the
proof in miniature. It takes the tarot organ (hand landmarks) and routes it through the
machinery Alice already has on disk, so the toy becomes a sense that LEARNS the owner's hand.

No invented physics/math: a coverage fraction, a mean distance, an online threshold move,
and the existing ledger/ladder organs. Pure stdlib + two SIFTA modules.
"""
from __future__ import annotations
import os, sys

try:
    from System.swarm_reality_ledger import RealityLedger
    from System.swarm_failure_abstraction import FailureAbstractor, STRATEGY_LADDER
except ImportError:  # run directly from inside System/
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from System.swarm_reality_ledger import RealityLedger
    from System.swarm_failure_abstraction import FailureAbstractor, STRATEGY_LADDER

WRIST = 0
TIPS = (4, 8, 12, 16, 20)          # thumb + 4 fingertips (MediaPipe Hands indices)
MIN_SIGHT = 0.6                     # below this the hand is not resolved -> do not act
N_LANDMARKS = 21


def sight_score(conf: list[float | None]) -> float:
    """Coverage = fraction of the 21 hand landmarks resolved above a confidence floor.

    MediaPipe returns a presence/visibility per landmark. sight_score == 0 means blind:
    the body channel's version of no_js_result. Speech/action is licensed by this number,
    exactly like r1512 — when she can't see the hand, the ONLY honest output is the gap."""
    if not conf:
        return 0.0
    seen = sum(1 for c in conf if c is not None and c >= 0.5)
    return seen / float(N_LANDMARKS)


def fist_closure(landmarks: list[tuple[float, float]]) -> float:
    """The demo's own heuristic, kept honestly: mean fingertip->wrist distance.
    Smaller = more closed. A fist is closure <= the (learned) threshold."""
    wx, wy = landmarks[WRIST]
    ds = [((landmarks[i][0] - wx) ** 2 + (landmarks[i][1] - wy) ** 2) ** 0.5 for i in TIPS]
    return sum(ds) / len(ds)


class GestureSense:
    """A hand sense that licenses action by sight, books each gesture as a reality
    debit, and LEARNS the owner's particular fist from his corrections."""

    def __init__(self, fist_threshold: float = 0.15, alpha: float = 0.6, margin: float = 0.01):
        self.fist_threshold = fist_threshold     # starts at the demo's hardcoded guess...
        self.alpha = alpha                       # ...and adapts toward THIS owner's hand
        self.margin = margin
        self.ledger = RealityLedger(ttl_s=5.0)
        self.failures = FailureAbstractor(threshold=5)
        self.t = 0.0

    # ---- perception: sight gates everything ----
    def perceive(self, conf, landmarks):
        s = sight_score(conf)
        if s < MIN_SIGHT:
            # blind: no debit, no guess. The only thing she may say is the gap.
            return {"sight": round(s, 3), "gesture": None,
                    "say": "I can't see your hand clearly — I won't guess."}
        closure = fist_closure(landmarks)
        gesture = "fist" if closure <= self.fist_threshold else "open"
        return {"sight": round(s, 3), "gesture": gesture, "closure": round(closure, 4),
                "say": "fist" if gesture == "fist" else "open hand"}

    # ---- action booked as a reality debit (manufacture the missing reward signal) ----
    def act_on_fist(self):
        self.t += 1.0
        self.ledger.debit("action", "gesture:select", "hand_eye", ts=self.t)
        return self.t

    def render_observed(self, at_ts):
        """The card-move actually happened on screen — an INDEPENDENT channel confirms.
        Debit (hand_eye) + credit (render_eye) from different channels -> SETTLED."""
        self.ledger.credit("gesture:select", "render_eye", ts=at_ts + 0.2)

    def gesture_status(self, at_ts):
        return self.ledger.status(self.ledger.debits[-1], now=at_ts + 0.5)

    # ---- learning: owner correction is the teaching channel (covenant §1.D) ----
    def owner_says_that_was_a_fist(self, closure: float):
        """A confirmed MISS (he made a fist; closure was above threshold -> she didn't fire).
        Expand the accepted region toward HIS demonstrated fist. This is the DeepMind loop in
        miniature: a signal updates a parameter. The error also feeds the failure ladder, so
        chronic miscalibration eventually escalates to ask_human (recalibrate)."""
        target = closure + self.margin
        self.fist_threshold += self.alpha * (target - self.fist_threshold)
        return self.failures.ingest_failure("gesture:fist_miss")

    def owner_says_that_was_not_a_fist(self, closure: float):
        """A false positive: she fired but he didn't mean it. Tighten toward below his hand."""
        target = closure - self.margin
        self.fist_threshold += self.alpha * (target - self.fist_threshold)
        return self.failures.ingest_failure("gesture:fist_false_pos")


if __name__ == "__main__":
    ok = True
    g = GestureSense()

    # (a) BLIND: no landmarks resolved -> refuse to act, speak only the gap (anti-confab).
    blind = g.perceive([None] * 21, [(0.0, 0.0)] * 21)
    ok &= blind["gesture"] is None and "can't see" in blind["say"]
    print("(a) blind ->", blind["say"], "| sight", blind["sight"], "(want refuse)")

    # (b) CLEAR OPEN HAND: fingertips far from wrist -> not a fist -> no action.
    seen = [1.0] * 21
    open_lm = [(0.0, 0.0)] + [(0.0, 0.4)] * 20      # tips ~0.4 from wrist
    p_open = g.perceive(seen, open_lm)
    ok &= p_open["gesture"] == "open"
    print("(b) open hand ->", p_open["gesture"], "closure", p_open["closure"], "(want open)")

    # (c) CLEAR FIST: tips near wrist -> recognized; render confirms via independent eye -> SETTLED.
    fist_lm = [(0.0, 0.0)] + [(0.0, 0.10)] * 20     # tips ~0.10 (< 0.15) = closed
    p_fist = g.perceive(seen, fist_lm)
    ok &= p_fist["gesture"] == "fist"
    ts = g.act_on_fist(); g.render_observed(ts)
    st = g.gesture_status(ts)
    ok &= st == "SETTLED"
    print("(c) fist ->", p_fist["gesture"], "| reality", st, "(want fist / SETTLED)")

    # (d) LEARNING: George's fist only closes to ~0.18 (> 0.15) -> missed at first.
    georges_fist = [(0.0, 0.0)] + [(0.0, 0.18)] * 20
    before = g.perceive(seen, georges_fist)["gesture"]
    ok &= before == "open"                            # default threshold misses his hand
    flips_after = None
    for i in range(1, 6):                             # he corrects her a few times
        g.owner_says_that_was_a_fist(0.18)
        if g.perceive(seen, georges_fist)["gesture"] == "fist":
            flips_after = i; break
    after = g.perceive(seen, georges_fist)["gesture"]
    ok &= after == "fist" and flips_after is not None and g.fist_threshold >= 0.18
    print("(d) learned his hand -> was", before, "now", after,
          "after", flips_after, "corrections | threshold", round(g.fist_threshold, 4))

    # (e) CHRONIC miscalibration climbs the ladder to the human limb.
    g2 = GestureSense()
    last = None
    for _ in range(40):
        sp = g2.owner_says_that_was_a_fist(0.30)      # absurd hand -> keeps missing
        if sp:
            last = sp
    ok &= last is not None and last["spawn_strategy"] == "ask_human"
    print("(e) chronic misread -> escalates to", last and last["spawn_strategy"], "(want ask_human)")

    print("GESTURE SENSE GRAFT:", "OK" if ok else "FAIL")
    print("  the tarot toy's eye now: gates action by sight, books reality, learns the owner.")
    raise SystemExit(0 if ok else 1)
