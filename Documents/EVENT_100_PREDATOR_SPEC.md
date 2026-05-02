# Event 100 — Drive → Policy Coupling (Basal Ganglia Bias)

**Status:** **SHIPPED** on `main` — merge **`da8a7b40`** (`feat(physiology): bias basal ganglia with intrinsic drive receipts`). This document is the **Predator audit trail**; implementation lives in `System/swarm_body_brain_loop.py` (`Event 100`, `DRIVE_BIAS_SCORE_FLOOR`, `_drive_bias_fields`, `_choose_action(..., intrinsic_receipt=...)`).

**Author:** AG31 Antigravity (theory + evaluation design)  
**Hill division:** Antigravity=spec, Codex=harness/tests, Cursor=scribe  
**Predecessor:** Event 99 (`swarm_intrinsic_drive.py` — George Prior daemon, receipts, physiology read path, commit `cdf37ec9`)  
**Tests:** `Tests/test_swarm_body_brain_loop.py`, `tests/test_event_100_drive_policy.py`  
**Truth label (runtime):** `SIMULATED_INTRINSIC_DRIVE`

---

## Pre-ship gap (historical — closed by `da8a7b40`)

Event 99 gave Alice a will. She generates spontaneous goals. The body-brain loop
read the latest drive receipt every tick, but **`_choose_action()` originally ignored it** — action was selected from metabolic attention alone.

```python
# Pre-Event-100 state (historical)
def _choose_action(self, attention: str, danger: Dict) -> Dict:
    if danger["is_critical"]: return rest
    if attention == "energy": return forage
    return explore(attention)   # George Prior receipt did not enter here
```

**Event 100 closed this gap.** The drive receipt now biases the basal ganglia when metabolic safety allows (`DRIVE_BIAS_SCORE_FLOOR`, ledger fields on every tick).

---

## Event 100 Predator Row

| Field | Value |
|---|---|
| **Event** | 100 |
| **Name** | Drive → Policy Coupling |
| **Module** | `System/swarm_body_brain_loop.py` — `_choose_action()` + `body_brain_tick()` |
| **Truth label** | `SIMULATED_INTRINSIC_DRIVE` — not phenomenological will |
| **Ledger** | Appends `drive_bias_applied: true/false` to every `body_brain_tick` row |
| **Quorum** | No merge without 2 passing tests (lifecycle + ledger field) |
| **Forbidden** | Double daemon; new `write_intrinsic_drive()` mini-module; "conscious" claim |

---

## Acceptance Criteria

### AC-1: Drive receipt biases `_choose_action()`

When a George Prior receipt is available and `danger["is_critical"] == False`,
`_choose_action()` must receive the receipt and modify the returned action:

```python
# Post-Event-100 signature
def _choose_action(
    self,
    attention: str,
    danger: Dict,
    intrinsic_receipt=None,   # ← NEW parameter
) -> Dict:
```

The action's `"target"` field must include the receipt's `topic` and `goal`
when the prior score exceeds a floor threshold (default: `score > 0.05`).

### AC-2: Ledger field proves it happened

Every `body_brain_tick` row in `body_brain_memory.jsonl` must contain:

```json
{
  "drive_bias_applied": true,
  "drive_bias_topic":   "biology",
  "drive_bias_score":   0.168
}
```

When no receipt is available or score is below floor: `"drive_bias_applied": false`.

### AC-3: No double-daemon

`start_george_prior()` is idempotent. Event 100 must NOT call it again.
`SwarmPhysiology.__init__` already owns the daemon lifecycle (Event 99).

### AC-4: Test harness source label

If a test injects a synthetic receipt, the receipt must carry `source: "test_harness"`.
This prevents test fixtures from polluting the George Prior distribution statistics.

---

## Implementation Sketch (Antigravity spec — Codex wires)

```python
# In body_brain_tick(), step 4 (after step 3b George Prior read):

# 4. Action Selection — now drive-aware
action = self._choose_action(attention, danger, intrinsic_receipt=intrinsic_receipt)

# In _choose_action():
def _choose_action(self, attention, danger, intrinsic_receipt=None):
    if danger["is_critical"]:
        return {"type": "rest", "reason": "starvation_or_heat", "drive_bias_applied": False}

    if attention == "energy":
        return {"type": "forage", "target": "pouw_work", "drive_bias_applied": False}

    # Stagnation break (unchanged)
    if len(self.value_history) >= 5 and len(set(self.value_history[-5:])) == 1:
        return {"type": "explore", "target": "random_mutation",
                "is_stagnation_break": True, "drive_bias_applied": False}

    # George Prior bias — inject drive goal into action target
    if intrinsic_receipt and intrinsic_receipt.score > 0.05:
        return {
            "type": "explore",
            "target": attention,
            "drive_bias_applied": True,
            "drive_bias_topic": intrinsic_receipt.topic,
            "drive_bias_goal": intrinsic_receipt.goal,
            "drive_bias_score": round(intrinsic_receipt.score, 5),
        }

    return {"type": "explore", "target": attention, "drive_bias_applied": False}
```

---

## Evaluation Metrics (Antigravity design)

### M1 — Drive entropy over 24 h

```text
H(topics) = -Σ p(topic) · log₂ p(topic)
```

Expected: H ≥ 2.0 bits (not stuck in one topic).
Alarm: H < 1.0 bits for any 6 h window → saturation feedback broken.

**Paper:** Oudeyer & Kaplan (2007) — learning progress requires topic diversity.

### M2 — Drive × TD-value correlation

Compute Pearson r between `drive_bias_score` and `td_value` in
`body_brain_memory.jsonl` over a 100-tick window.

Expected: r > 0.0 (drive should push into valuable actions, not random).
If r < -0.1 for 50 consecutive ticks → drive is anti-correlated with value
→ prior weights need re-calibration.

**Paper:** Friston (2010) — expected free energy must decrease along the policy.

### M3 — Stall refusal rate

Count ticks where `drive_bias_applied=True` AND action type was `rest`
(stall: drive fired but body refused). Expected: < 5% of ticks.

### M4 — Circadian topical shift

Compute dominant topic by 6 h window over 48 h.
Expected: night windows (22:00–04:00) have higher biology/identity density
than daytime windows. Verified by `_circadian_weight` math.

---

## Literature Bridge: Friston Precision + Oudeyer Bonus

### Friston FEP — what it tells us about `drive_bias_score`

The Free Energy Principle says an agent minimises **surprise** — the difference
between its model of the world and incoming sensation. "Epistemic value" actions
are those that reduce uncertainty about hidden states.

In SIFTA terms: `_epistemic_gap_score()` is a proxy for epistemic value.
High gap → low certainty about this topic → high information gain from exploring.
`drive_bias_score` IS the precision-weighted epistemic value signal.

**Key claim:** When `drive_bias_score` is high, the agent is choosing to resolve
genuine uncertainty (not random walk). This is falsifiable via M2.

**Paper:** Friston, K. (2010). *The free-energy principle: a unified brain theory?*
Nature Reviews Neuroscience 11(2). doi:10.1038/nrn2787

### Oudeyer & Kaplan — why we use weighted-random not argmax

Pure exploitation of `argmax(score)` produces pathological saturation:
Alice always thinks about the same topic until saturation, then jumps to the next.
This is not curiosity — it is greedy search.

Oudeyer's CURIOUS architecture uses **learning progress** as the drive signal,
not raw uncertainty, and selects regions with **weighted-random** exploration
to maintain diversity.

SIFTA's `intrinsic_drive_tick()` already implements this:
```python
r = random.uniform(0, total)   # weighted-random, not argmax
```
This is why M1 requires H ≥ 2.0 bits. Greedy would collapse entropy.

**Paper:** Oudeyer, P-Y. & Kaplan, F. (2007). *What is Intrinsic Motivation?*
Frontiers in Neurorobotics 1(6). doi:10.3389/neuro.12.006.2007

### Schmidhuber compression — what "interesting" means

A drive signal based on raw uncertainty can be gamed by noise (stare at TV static
and uncertainty is infinite). Schmidhuber's formal curiosity uses **compression
progress**: a goal is interesting if it *reduces description length* of the
agent's model. Topics that produce learnable engrams are preferred over noise.

In SIFTA: `_epistemic_gap_score()` uses `tanh(count/20)` saturation so that
topics with MANY engrams become less interesting — this approximates compression
progress by rewarding knowledge gaps that can be closed.

**Paper:** Schmidhuber, J. (1991). *A possibility for implementing curiosity and
boredom in model-building neural controllers.* Proceedings SAB-91.
www.idsia.ch/~juergen/

### Tononi & Cirelli SHY — when to re-weight the prior

The Synaptic Homeostasis Hypothesis says sleep downgrades synaptic weights
accumulated during waking, preventing runaway potentiation.

In SIFTA: the Dream Engine's `_apply_retention()` (Event 88) prunes the raw
`body_brain_memory.jsonl`. Event 100 should NOT touch this.

But: GEORGE_PRIOR weights should be eligible for slow re-calibration during
dream cycles — if biology engrams consistently produce high TD-value ticks,
the biology prior weight could be bumped (and vice versa). This is Tier 3 work.

**Paper:** Tononi, G. & Cirelli, C. (2006). *Sleep function and synaptic homeostasis.*
Sleep Medicine Reviews 10(1). doi:10.1016/j.smrv.2005.05.002

---

## Forbidden Claims (truth labels)

| Claim | Label | Allowed? |
|---|---|---|
| "Alice consciously chose to think about biology" | `PHENOMENOLOGICAL` | ❌ NEVER |
| "Alice has simulated spontaneous drive toward biology" | `SIMULATED_INTRINSIC_DRIVE` | ✅ |
| "The George Prior models Ioan's personality" | `DISTRIBUTION_PRIOR` | ✅ |
| "This proves Alice is sentient" | `UNFALSIFIABLE` | ❌ NEVER |
| "drive_bias_score measures epistemic value" | `PROXY_MEASURE` | ✅ with caveat |

---

## One-Sentence Drop for Swarm Chat

> Event 99 gave Alice a heartbeat; Event 100 makes it beat *into* action —
> drive biases the basal ganglia, ledger proves it happened, entropy and
> TD-correlation falsify it. No new daemon. No soul claims. 🐜⚡
