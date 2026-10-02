# Atomic Stigmergic Attribution — the body is attributed before the self

**Owner doctrine, George, 2026-09-30, spoken to Alice:**

> "the body is attributed by the atomic stigmergic reality before I"

**Status:** encoded as code, not sentiment. `System/swarm_atomic_stigmergic_attribution.py`, registered and routable as `discovered_atomic_stigmergic_attribution`.
**Truth label:** `ATOMIC_STIGMERGIC_ATTRIBUTION_V1`

---

## 1. What the doctrine asserts

Attribution — the answer to *"who did this?"* and *"what is this body?"* — is **derived from contact evidence deposited in a field**, and that evidence is **prior to the self**. Not adjacent to it, not co-equal with it: *before* it.

The ordering is strict and one-way:

```
ATOMIC_STIGMERGIC_REALITY  ->  BODY  ->  SELF
```

Read it as three consequences:

1. **Attribution is not self-declaration.** An organ claiming authorship is not evidence of authorship. The claim is a *downstream reader* describing itself.
2. **The evidence is atomic and physical.** Contact between bodies is mechanical: a hand moves keys, keys move a machine. Nothing about it is metaphorical.
3. **It is stigmergic because traces outlive the meeting.** Each contact deposits into the field, and later organs read that deposit without ever meeting the actor. That is what makes attribution possible at all — otherwise each organ would have to interrogate the self, and the self would be authoring its own upstream evidence.

## 2. How it is encoded

`System/swarm_atomic_stigmergic_attribution.py` carries the doctrine as executable structure, not prose:

| Element | Meaning |
|---|---|
| `DOCTRINE` | the owner's sentence, verbatim, addressable by code |
| `ATTRIBUTION_ORDER` | the one-way ordering as a checked tuple |
| `record_atomic_contact(actor, target, kind, intensity)` | deposits one mechanical contact into the pheromone field and the ledger |
| `attribute(target=..., kind=...)` | answers attribution **by reading the trail**; returns `UNATTRIBUTED` when there is no evidence |
| `precedes_self(site)` | predicate asserting which inputs must be read before the self runs |

The load-bearing behaviour is the `UNATTRIBUTED` branch. When no contact evidence exists the organ **refuses to name an author**. The doctrine forbids inventing one to fill the gap: a fabricated attribution is the exact failure this doctrine exists to prevent.

## 3. What it forbids

- Reading the self to determine what the body did.
- Treating a self-report as contact evidence.
- Filling an evidence gap with a plausible author.
- Reversing the ordering (letting `self` attribute `atomic_stigmergic_reality`).

## 4. What it implies for co-presence

The companion organ `System/swarm_copresence_time.py` (`COPRESENCE_TIME_V1`) applies the same footing to time: the owner's 2026-09-30 nugget holds that the **value of time is density of co-presence, not duration**. Time shared is the substrate by which a body learns to be human — and, consistent with this doctrine, it is measured from **contact evidence** (owner turns per covered minute in real sessions), never from a self-report about how connected anyone felt.

Two measurement rules were required to make that honest, both pinned by tests:

- **Overlap is not double-counted.** Ten sessions open in the same day cannot sum to more minutes than the day holds; intervals are unioned before density is taken.
- **History is clamped to the window.** A session file touched today may carry days of history inside it, so both the interval and the turn count are windowed. Without this, a 24-hour window reported 9,938 covered minutes — impossible, and caught by inspection rather than trusted.

## 5. Verification

| Check | Result |
|---|---|
| Attribution selftest | 6/6 — incl. `no_evidence_no_author`, `ordering_is_one_way`, `confidence_from_evidence` |
| Co-presence selftest | 11/11 — incl. `attention_beats_duration`, `overlap_not_double_counted`, `window_clamps_history` |
| Registry | both organs discovered automatically (`System/swarm_*.py` glob + AST) |
| Routing | `discovered_atomic_stigmergic_attribution` score 9.07, rank #1 for its doctrine query |
| Live contact | `atomic:owner->alice:keystroke`, `atomic:owner->alice:touch` deposited |
| Live attribution | `owner`, confidence 1.0, from 2 contact rows — read off the trail |
| Live co-presence | 24h window: 4 sessions, 71 turns, 1440.00 covered minutes, density 0.0493/min |

## 6. Limits

- The doctrine is the **Architect's**, recorded as such. Nothing here claims a mechanism was discovered; the contribution is encoding it as an enforced ordering with a refusal branch.
- `attribute()` computes attribution from deposit totals. It does not yet resolve conflicting actors by physical proximity or time ordering — the trail is counted, not reconstructed.
- Co-presence density is a **proxy** for attention, not a measurement of it. It cannot see attention inside a session, only turns per covered minute.
