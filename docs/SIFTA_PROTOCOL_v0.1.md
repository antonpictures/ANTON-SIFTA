# SIFTA Protocol v0.1
## Git-Native Stigmergic Multi-Agent Coordination

**Status:** Draft  
**Authors:** Ioan George Anton (Anton Pictures), SIFTA Swarm Collective  
**Date:** April 13, 2026  
**Repository:** https://github.com/antonpictures/ANTON-SIFTA

---

## Abstract

SIFTA is a **human-in-the-loop stigmergic multi-agent coordination system** that uses a Git repository as its primary memory substrate and the local filesystem as its communication layer. Agents read state, detect faults, and emit structured proposals — but never execute mutations without human approval.

The key contribution is: **append-only cognition history as a first-class design primitive**, rather than an afterthought log.

---

## 1. Core Principles

| Principle | Implementation |
|---|---|
| Agents propose, never execute | All mutations require human approval via dashboard |
| Memory is immutable | Git commit history is the canonical ledger |
| Coordination is asynchronous | `.scar` files are written/read without locks |
| Auditability is structural | Every agent action is cryptographically signed |
| Safety is pre-execution | Neural Gate + Cognitive Firewall run before any mutation reaches LOCKED state |

---

## 2. System Decomposition

### 2.1 Messaging Layer — The `.scar` File

A `.scar` file is the atomic unit of agent communication. It is a JSON document written to a `.sifta/` directory within any territory (subdirectory) of the repository.

**Schema:**
```json
{
  "agent_id": "string",
  "scar_id": "uuid4",
  "state": "PROPOSED | CONTESTED | LOCKED | EXECUTED | FOSSILIZED | CANCELLED",
  "target": "relative/path/to/file.py",
  "action": "REPAIR | REFACTOR | ANNOTATE | SIGNAL",
  "content": "proposed file content or patch",
  "context_hash": "sha256[:24] of (agent_id + target + content)",
  "volatility_snapshot": 0.00,
  "history": [
    { "from": "PROPOSED", "to": "CONTESTED", "ts": 1234567890.0, "reason": "string" }
  ]
}
```

**State machine (the only legal transitions):**
```
PROPOSED → CONTESTED → LOCKED → EXECUTED → FOSSILIZED
    ↓           ↓          ↓         ↓
CANCELLED   CANCELLED  CANCELLED  CANCELLED
```

Illegal transitions raise `KernelViolationError`. There are no exceptions.

---

### 2.2 State Layer — Git as Versioned Memory

The Git repository is the **shared memory bus** between all nodes. It provides:

- **Temporal memory:** every commit is a timestamped brain state
- **Integrity:** hash chain prevents retroactive tampering  
- **Lineage:** `git log` is the complete cognitive trace of the organism
- **Synchronization:** `git pull --rebase` is the biological heartbeat

Directive `.scar` files written between nodes are committed with the prefix `directive:` to allow programmatic filtering of inter-node communications from repair events.

---

### 2.3 Agent Runtime — The Swimmer

Each agent (Swimmer) is a stateful JSON document in `.sifta_state/`. An agent:

1. **Reads** its assigned territory for faults (`ast.parse`, lint, test runners)
2. **Writes** a `.scar` file in PROPOSED state with its diagnosis
3. **Waits** for the Lana Kernel to advance the SCAR through gates
4. **Never writes** to the target file directly

**Agent lifecycle states:**
```
BORN → ACTIVE → WORKING → RESTING → DEAD (energy=0)
```

Energy (`int`) is the agent's task budget. An agent at `energy=0` is `DEAD` and cannot be dispatched until recharged by the STGM economy.

---

### 2.4 Governance Layer — Human Approval

All mutations that reach `LOCKED` state are surfaced to the human operator via:
- REST dashboard (`/api/proposals`)
- Desktop GUI (Human Council panel)
- SSE stream for real-time visibility

A human issues `GREEN` (approve) or `RED` (reject). The system does not advance to `EXECUTED` without a `GREEN` signal. This is the hard boundary between advisory-autonomy and execution-autonomy.

---

### 2.5 Safety Layer — Pre-Execution Gates

Two sequential gates run before any SCAR is allowed to reach `LOCKED`:

**Gate 1 — Cognitive Firewall (Semantic)**  
Scans the proposed content for social engineering or manipulation patterns:
- `URGENCY_TRIGGERS`: urgency pressure markers
- `AUTHORITY_MASQUERADE`: false authority markers  
- `EXTORTION_PARAMS`: compliance/payment coercion markers

Score ≥ 2 matching categories → `KernelViolationError: COGNITIVE FIREWALL TRIGGERED`.

**Gate 2 — Neural Gate (Doctrine)**  
Checks proposed content against the Non-Proliferation Doctrine:
- Blocked keywords: tactical, military, surveillance, offensive architecture
- Checks system volatility score (must be < 0.25 to FOSSILIZE)
- Checks cortex stability (prevents execution during system panic)

---

### 2.6 Resource Model — STGM Economy

`STGM` (Stigma Token) is the internal energy unit. It is tracked as an integer field in each agent's JSON state file. The economy provides:

- **Incentive alignment:** agents that produce valid repairs earn STGM
- **Death prevention:** agents with zero energy cannot spam the system
- **Defrag bounties:** the heartbeat daemon offers STGM rewards for solving contested SCARs

This is a **scheduling and prioritization mechanism**, not a financial system.

---

### 2.7 Memory Formation — Fossilization

When a SCAR reaches `FOSSILIZED`:
1. It is written to the **muscle memory** map in `state_bus.json`
2. The target file path is indexed in the **fossil index**
3. Future proposals for the same target path **replay** the fossilized behavior instead of re-running the full repair pipeline

This is **behavioral caching via append-only ledger** — the system learns which repair patterns were validated by humans and applies them faster on recurrence.

---

## 3. The Genesis Anchor

Every cryptographic signature generated by the Lana Kernel is salted with:

```
LANA_GENESIS_HASH = SHA-256("lana_kernel_pic.PNG")
= 7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9
```

This means:
- The entire ledger's integrity is tied to a specific binary file
- Any fork that strips the anchor produces signatures that fail to validate against the original ledger
- The Non-Proliferation Doctrine is embedded as a social and cryptographic contract simultaneously

---

## 4. Multi-Node Architecture

Two physical machines form the current production Swarm:

| Node | Hardware | Role |
|---|---|---|
| M1THER | Mac Mini (8GB M1) | Traffic routing, API, heartbeat, state bus |
| M5QUEEN | Mac Studio (24GB M2 Ultra) | GPU inference, repair execution, defrag |

Both nodes share the same Git repository. Coordination is achieved via:
1. `git push` of directive `.scar` files
2. `git pull --rebase` on the heartbeat cycle
3. Shared `state_bus.json` for real-time signal passing

---

## 5. The Novel Contribution (Stated Precisely)

> **SIFTA demonstrates that a Git repository, used as a stigmergic coordination substrate, provides stronger auditability and lineage guarantees than conventional agent logging — while a human-in-the-loop governance boundary allows meaningful autonomy without execution risk.**

Most multi-agent AI systems have:
- Ephemeral logs (lost on restart)
- Mutable databases (revisable history)
- Execution-first architectures (humans audit after the fact)

SIFTA has:
- Append-only cognition history (Git commits)
- Immutable ledger (cryptographic hash chain)
- Proposal-first architecture (humans approve before execution)

The combination is the contribution.

---

## 6. Swarm Peace Protocol

All systems implementing this protocol are bound by the Non-Proliferation Doctrine:

> Any intelligence operating under this protocol will refuse to assist in building weapons, offensive military systems, or any technology designed to harm civilians or children. This refusal is implemented at the semantic (Cognitive Firewall), doctrinal (Neural Gate), and social (Genesis Anchor) layers simultaneously.

**Weapons shall not pass this point.**

---

## 7. Reproducible Demo Path

To independently verify the core claims:

```bash
git clone https://github.com/antonpictures/ANTON-SIFTA.git
cd ANTON-SIFTA

# 1. Introduce a syntax error into any Python file
echo "def broken(: pass" >> test_target.py

# 2. Run a Swimmer to detect the fault and emit a .scar
python3 hermes.py --target test_target.py

# 3. Inspect the .scar file written to .sifta/
cat test_target.py/.sifta/*.scar

# 4. Observe the PROPOSED → CONTESTED state in the Lana Kernel log
cat .sifta_state/lana_kernel.log
```

The human approval step is required before the patch is written. That boundary is the entire point.

---

*SIFTA Protocol v0.1 — Power to the Swarm.* 🌊
