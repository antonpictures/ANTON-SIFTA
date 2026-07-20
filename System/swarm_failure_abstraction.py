#!/usr/bin/env python3
"""Defecation that births strategy (Q4: the cognitive leap).

George's challenge: journal_defecation_once() compresses 50 "failed to click X" into a
time-range. A human instead ABSTRACTS: "X is broken — try a different route." Does the
pressure of duplicates merely compress, or does it birth a NEW swimmer with a new
strategy? True AGI: metabolic waste -> conceptual mutation.

This is the leap. Defecation here is TYPED by outcome:
  * success/noise clusters  -> housekeeping compression (a time-range, nothing learned);
  * FAILURE clusters        -> once their pressure crosses a threshold, the cluster is
    PROMOTED to a RULE ("route X is dead") AND SPAWNS a new strategy from a ladder.

The ladder is variation; failure-pressure is selection. Each promotion (a) writes a
durable rule, (b) advances to the next strategy, (c) resets the pressure so the NEW
strategy gets its own fair trial. Repeated failure of the new strategy promotes again ->
the search mutates until something works or it reaches the human limb. The waste is the
nutrient that grows the next organ.

No invented physics/math: a counter + an ordered strategy list. Pure stdlib.
"""
from __future__ import annotations
from collections import Counter

# variation space, cheap -> expensive. The last rung is the human-as-actuator limb.
STRATEGY_LADDER = ["retry_same", "sibling_element", "deep_shadow_scan",
                   "other_limb_webbridge", "direct_url", "ask_human"]


class FailureAbstractor:
    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self._fail: Counter = Counter()   # signature -> current pressure
        self._stage: dict = {}            # signature -> ladder index in use
        self.rules: list = []             # durable abstractions

    def ingest_failure(self, signature: str):
        """A failed action receipt. Returns a spawn-spec if pressure births a mutation."""
        self._fail[signature] += 1
        if self._fail[signature] >= self.threshold:
            return self._promote(signature)
        return None

    def ingest_success(self, signature: str):
        """Success relieves pressure (no rule, no spawn) — housekeeping only."""
        self._fail[signature] = 0

    def _promote(self, sig: str) -> dict:
        stage = self._stage.get(sig, 0)
        dead = STRATEGY_LADDER[min(stage, len(STRATEGY_LADDER) - 1)]
        nxt = STRATEGY_LADDER[min(stage + 1, len(STRATEGY_LADDER) - 1)]
        spawn = {
            "rule": "route '%s' via %s is dead after %d failures" % (sig, dead, self._fail[sig]),
            "dead_strategy": dead,
            "spawn_strategy": nxt,
            "signature": sig,
        }
        self.rules.append(spawn)
        self._stage[sig] = stage + 1
        self._fail[sig] = 0               # the new strategy earns its own trial
        return spawn


if __name__ == "__main__":
    fa = FailureAbstractor(threshold=5)
    ok = True
    spawns = []
    for _ in range(5):
        s = fa.ingest_failure("click:ButtonX")
        if s:
            spawns.append(s)
    ok &= len(spawns) == 1 and spawns[0]["spawn_strategy"] == "sibling_element"
    print("1st promotion ->", spawns and spawns[0]["spawn_strategy"], "(want sibling_element)")

    for _ in range(5):  # the new strategy also fails -> mutate again
        s = fa.ingest_failure("click:ButtonX")
        if s:
            spawns.append(s)
    ok &= spawns[-1]["spawn_strategy"] == "deep_shadow_scan"
    print("2nd mutation ->", spawns[-1]["spawn_strategy"], "(want deep_shadow_scan)")

    # keep failing -> the search climbs the ladder to the human limb
    for _ in range(20):
        fa.ingest_failure("click:ButtonX")
    ok &= fa.rules[-1]["spawn_strategy"] == "ask_human"
    print("ladder end ->", fa.rules[-1]["spawn_strategy"], "(want ask_human)")

    # success on a different control relieves pressure, no spurious rule
    before = len(fa.rules)
    for _ in range(4):
        fa.ingest_failure("click:Save")
    fa.ingest_success("click:Save")
    fa.ingest_failure("click:Save")
    ok &= len(fa.rules) == before
    print("success relieves pressure -> no new rule:", len(fa.rules) == before)

    print("FAILURE ABSTRACTION:", "OK" if ok else "FAIL", "| rules learned:", len(fa.rules))
    raise SystemExit(0 if ok else 1)
