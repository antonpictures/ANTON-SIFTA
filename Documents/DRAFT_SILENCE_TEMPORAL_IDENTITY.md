# Draft — Final Three Mechanisms (Post-Objective Registry)

**Date:** 2026-04-16  
**Type:** Design draft — **no implementation yet**.  
**Upstream dependency:** `System/objective_registry.py` (must exist first — it defines "good" vs "bad").  
**Build order:** Objective Registry → Failure Harvesting (#9) → Shadow Simulation (#7) → Contradiction Engine (#4) → **these three last**.

---

## Execution sequence within this trio

1. **Identity Decoupling (#8)** — schema + doc (low risk, clarifies everything else)
2. **Temporal Layering (#6)** — overlay on temporal_spine + swim (small, measurable)
3. **Silence Detection (#5)** — needs baselines from live metrics → last

---

## 1. Silence Detection (#5)

### Intent
React to **missing** signals: zones where something **should happen** but **doesn't**.

### Core predicate
```
if expected_activity(zone, window) > actual_activity(zone, window) + tolerance:
    trigger_probe(zone)
```

### Outputs
| Output | Purpose |
|--------|---------|
| `probe` | Cheap check (port open? file touched? process alive?) |
| `escalate` | Claw read-only diagnostic, or human ping |
| `record` | Append to silence log → feeds Failure Harvesting |

### Non-goals
- Not surveillance of the Architect
- Not a substitute for Contradiction Engine

---

## 2. Temporal Layering (#6)

### Three clocks
| Clock | Signal | Source |
|-------|--------|--------|
| **Wall** | Real seconds | `time.time()` |
| **Event** | Activity density | Traces/min, blackboard writes |
| **Cognitive** | Attention load | Attention budget spend, queue depth |

### Combined
```
perceived_urgency = α·f(wall_deadline) + β·g(event_density) + γ·h(cognitive_load)
```

### Guardrail
Do NOT redefine STGM or ledger time — subjective time is a policy overlay.

---

## 3. Identity Decoupling (#8)

### Rule
**Identity ≠ behavior ≠ authority** (lineage is symbolic, not permission).

### Schema (v1)
```
agent_record = {
    "id":             "<immutable — key-bound>",
    "lineage_tag":    "<symbolic — not permission>",
    "policy_profile": "<behavior preset>",
    "permissions":    "<capability set — Neural Gate tier>",
}
```

### Invariants
- `permissions` changes only through Governor + Gate
- Architect / serial / Ed25519 remain root of trust
- Gemma persona = presentation only, never kernel authorization

---

**POWER TO THE SWARM — directed, not merely loud.**
