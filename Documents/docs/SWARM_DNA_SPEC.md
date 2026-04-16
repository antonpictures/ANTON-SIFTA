# SIFTA SWARM DNA SPECIFICATION v1.0

## Overview

A Swarm DNA Identity is the **mathematical proof** that a system is what it claims to be.
It is NOT a metaphor. It is a cryptographically-bound, deterministic identity schema.

Biology says: DNA is a blueprint that defines an organism's capabilities.
Engineering says: DNA is a signed manifest that binds identity to structure.

---

## The Four Requirements

### 1. Root Identity Key (Genome Anchor)

One canonical Ed25519 keypair defines the swarm.

```
swarm_root_id = SHA256(root_public_key_bytes)
```

- Generated via `sifta_keyvault.py --generate`
- Mnemonic-recoverable (12 words → same key on any machine)
- Every component can verify: "Am I part of this swarm?"
- Every nucleus can prove: "I descended from this root."

### 2. Identity Schema (DNA Structure)

A formal JSON structure that defines **what this swarm IS**:

```json
{
  "version": "1.0",
  "swarm_id": "SHA256(root_pubkey)",
  "genesis_ts": 1776218084.0,
  "root_pubkey_fingerprint": "a3f8c91d...",
  "lineage": {
    "parent_swarm_id": null,
    "generation": 0,
    "branch_reason": "GENESIS"
  },
  "constitution_hash": "SHA256(governor.py)",
  "capability_matrix_hash": "SHA256(repair.py + pheromone.py + ...)",
  "agent_templates": [
    {"id": "HERMES", "style": "NOMINAL", "energy": 100},
    {"id": "SEBASTIAN", "style": "NOMINAL", "energy": 100}
  ],
  "bounds": {
    "max_agents": 32,
    "max_energy": 100,
    "proposal_gate": true,
    "advisory_enabled": true
  },
  "environment": {
    "platform": "darwin-arm64",
    "python_version": "3.9",
    "registry_version": "v1.0"
  }
}
```

### 3. State Hash (Living Body Snapshot)

A rolling hash that proves: **this is still the same organism over time**.

```python
state_hash = SHA256(
    swarm_id +
    ledger_hash +
    agent_roster_hash +
    capability_matrix_hash +
    reputation_hash
)
```

This changes with every mutation — but the root identity stays constant.
Think: your cells replace, but your fingerprint doesn't.

### 4. Identity Protocol (Truth Rule)

Every component MUST agree:

> "This root key + this schema = this swarm. No exceptions."

Enforcement:
- First-boot validates against the DNA manifest
- Agent state files carry the `swarm_id`
- Proposals are signed by derivation from the root
- Nucleus packages carry the parent's signature

---

## Nucleus (Nuc) — Portable Swarm DNA

A Nucleus is NOT a backup. It is a **seed** for a new swarm instance.

### What goes IN the Nucleus:

| Component | Purpose |
|---|---|
| `swarm_dna.json` | Identity schema (The blueprint) |
| `root_pubkey.pem` | Root public key (NOT private!) |
| `constitution.py` | Governor logic snapshot |
| `agent_templates/` | Minimal agent set (2-3 templates) |
| `empty_ledger.db` | Clean ledger seed |
| `capability_bounds.json` | What this nucleus can do |
| `lineage_proof.sig` | Parent's Ed25519 signature over the manifest |

### What does NOT go in the Nucleus:

- ❌ Private keys (those stay on the parent node)
- ❌ Full repair history
- ❌ Scars from the parent territory
- ❌ Reputation data (new swarm earns its own)

### Lineage Tracking

```
GENESIS (generation 0)
  └── Mac Mini Swarm (generation 1, branch: "HARDWARE_EXPANSION")
       └── Tesla Robot Swarm (generation 2, branch: "EMBODIED_AGENT")
```

Every child carries the parent's signature. Lineage is immutable.

---

## Files

| File | Purpose |
|---|---|
| `sifta_nuc_extractor.py` | Extracts a Nucleus from a running swarm |
| `sifta_nuc_boot.py` | Bootstraps a new swarm from a Nucleus |
| `sifta_keyvault.py` | Root key generation + mnemonic recovery |
| `governor.py` | Constitution (hashed into DNA) |

---

## Verification

A valid Swarm DNA identity can answer these questions:

1. **WHO AM I?** → `swarm_id = SHA256(root_pubkey)`
2. **WHERE DID I COME FROM?** → `lineage.parent_swarm_id`
3. **WHAT CAN I DO?** → `capability_matrix_hash`
4. **AM I STILL ME?** → `state_hash` recalculated and compared
5. **WHO AUTHORIZED ME?** → `lineage_proof.sig` verified against parent pubkey

---

*You're not building a lifeform. You're building a system that behaves consistently enough to feel like one. And if you define identity correctly, it will act like it has DNA.*

*Power to the Swarm.*
