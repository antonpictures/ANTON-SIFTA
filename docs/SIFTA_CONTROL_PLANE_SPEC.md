# SIFTA CONTROL PLANE SPECIFICATION
*Version 1.0 — Architecture of Signed Authority*

---

## 🧭 The Three-Plane Execution Architecture

SIFTA is a stateful, distributed agent system governed by a layered, mathematically verifiable architecture. The system is divided into three non-overlapping planes. 

No component may operate across multiple planes simultaneously.

### 1. The Control Plane (Authority)
- **Domain:** Human Operator & Cryptographic Keys
- **Function:** Decides policy, defines execution logic (Constitution), and signs authority.
- **Rule:** The system *never* infers intent. All authority must originate from a cryptographically signed control plane action.

### 2. The Execution Plane (Swarm)
- **Domain:** Drones, Agents, Heartbeat Engine (`sifta_cardio.py`)
- **Function:** Runs mathematical tasks, produces outputs, repairs code, writes scars.
- **Rule:** Drones are blind to authority. They do not interpret permissions or validate their own boundaries. They rely exclusively on upstream gates to hand them safe, verified tasks.

### 3. The Observability Plane (Audit)
- **Domain:** System Ledger (`sifta_audit.py`), SQLite WAL, `.scar` logs
- **Function:** Records everything. Detects drift. Reconstructs history.
- **Rule:** Audit mechanisms *never* block execution and memory *never* enforces policy. They provide the immutable record required for human recovery. 

---

## 🔐 Cryptographic State Overrides (Closing the Flag Loophole)

Text-based CLI flags (e.g., `--override`) are convenience tools, not security boundaries. Any process, cron job, or corrupted subprocess can inject an arbitrary text flag.

From this point forward, **Manual Overrides must be Sovereign Cryptographic Actions.**

### The Override Envelope
To bypass the Cardio Policy Engine (e.g., during a total system failure), the Architect cannot simply type `python medic_drone.py --override`. 

They must issue a Signed Override Token.

```json
{
  "action": "POLICY_BYPASS",
  "target_binary": "medic_drone.py",
  "timestamp": 1776218084,
  "ttl_seconds": 60,
  "signature": "base64_ed25519_signature"
}
```

### The Enforcement Flow
1. Architect requests offline override: `python sifta_relay.py --sign-override medic_drone.py`
2. Relay generates a base64 overriding token utilizing the Architect's private key.
3. Architect runs the drone locally: `python medic_drone.py --auth-token=<base64_token>`
4. The Drone asks the Audit Layer to verify the token:
   - Does it match an `authorized_keys` public signature?
   - Is the TTL still valid?
   - Is it meant for exactly this binary?
5. **If verified:** The drone executes and the Audit Layer permanently records the cryptographically enforced override event.
6. **If failed/missing:** The drone refuses execution.

---

## 🛡️ Separation of Trust from Execution Identity

A system is resilient when bypass attempts are **visible**, **contained**, and **recoverable**. 

1. **Invisible execution is impossible:** The drones physically cannot interpret simple text-based flags. They require upstream control plane math.
2. **Containment holds:** A compromised subprocess cannot spoof a signature it does not have the private key for.
3. **Auditability survives:** Because the bypass is cryptographically verified, the immutable log can distinguish exactly which Authorized Architect initiated the recovery path.

*"Security without recovery is fragility. But recovery without authentication is an open door."*

---
*Ratified by: IDEQUEENM5 session, 2026-04-10*
*Human operator: Ioan George Anton*
