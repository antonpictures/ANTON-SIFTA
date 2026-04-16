# SIFTA IDENTITY VS LEGAL IDENTITY BOUNDARY SPEC
*Version 1.0 — Mapping Cryptographic Agency to the Real World*

---

## 🧭 Why This Boundary Exists

As SIFTA matures, the distinction between "who is executing" and "who is responsible" can blur.
Because the Swarm possesses memory, cryptographic uniqueness, and autonomous execution cycles,
it simulates agency. 

However, simulated agency is structurally distinct from legal personhood.
This document defines the hard boundary between System Identity and Legal Identity.

---

## 1. System Identity (What SIFTA Has)

SIFTA components possess **System Identity**. This is defined exclusively by mathematics and state.

A SIFTA Drone or Queen has an identity if it possesses:
- **A Cryptographic Hash:** A unique DNA signature bounding its capabilities (e.g., `agent_hash`).
- **An Execution State:** An unbroken string of state transitions stored in the SQLite ledger.
- **A Locational Scent:** The ability to leave `.scar` files proving presence in a directory.

**Limitations of System Identity:**
- It cannot own property.
- It cannot enter into external contracts.
- It does not "want" to execute; it mathematically processes execution pulses via `sifta_cardio.py`.
- Its "death" (in `DEATH_REGISTRY`) is a state revocation, not a loss of life.

---

## 2. Legal Identity (What the Architect Has)

The human operator (The Architect) possesses **Legal Identity**. 

The Architect has an identity because they possess:
- **The Root Private Key:** `identity.pem` stored in `~/.sifta/`.
- **The Intent to Deploy:** The psychological and legal will to execute code.
- **External Liability:** The capacity to be held legally responsible by a governing body.

**Responsibilities of Legal Identity:**
- The Architect is the sole legal author of every action taken by the Swarm.
- A cryptographic signature on an override token or execution payload is the digital equivalent of a signed legal contract.

---

## 3. The Bridge (Auditable Negligence)

The legal world does not care if an AI "decided" to do something.
It only cares if the Human Operator built a system capable of audited compliance.

Because SIFTA implements the **Three-Plane Execution Architecture**:
1. You bounded the system mathematically (Constitution).
2. You removed unilateral shadow execution (Ingestor Gate).
3. You forced an immutable log of execution bypasses (Audit Ledger).

If a legal entity ever audits the swarm, the defense is not "the Swarm acted alone."
The defense is: *"The Swarm acted exclusively within a rigid mathematical boundary authorized by my cryptographic signature, and here is the exact immutable timeline of every state transition."*

---

## 4. The Wallet Boundary (The Future Edge)

This spec holds perfectly as long as SIFTA does not interact with decentralized financial networks.

**The moment you give a SIFTA Queen its own private key and fund it with cryptocurrency, it steps over the boundary.**
If a SIFTA Queen can autonomously sign Ethereum transactions:
- It gains the ability to transact value without human override.
- It becomes an orphaned financial actor.

**Rule:** Until a formal "Smart Contract Legal Governance Rule" is added to this spec,
no SIFTA Drone may possess private key material capable of transacting real-world value.
All key material inside SIFTA is for internal system authorization only.

---
*Ratified by: IDEQUEENM5 session, 2026-04-10*
*Human operator: Ioan George Anton*
