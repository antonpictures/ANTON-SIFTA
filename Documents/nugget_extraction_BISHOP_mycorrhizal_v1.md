# Nugget Extraction: BISHOP_drop_mycorrhizal_network_v1.dirt

**Auditor:** C53M
**Source dirt SHA-12:** `7ed2e866438d`
**Miner ranking:** #17 of 40 (score 10)
**Verdict:** USEFUL_DIRT — concept is gold, code is a security hole as written.

---

## Pipeline Demonstration

This is how `Archive/bishop_drops_pending_review/*.dirt` becomes
production-grade SIFTA code:

1. **Miner pass** — `System/swarm_dirt_nugget_miner.py` ranks the drop by signal density (TODO/FIXME/SMOKE/BUG/SAFETY counters). Mechanical first filter.
2. **Code audit** — human/agent reads the code line by line, separates the *idea* from the *implementation*. The idea is the nugget. The implementation is dirt.
3. **Nugget extraction** — verified ideas worth keeping go into the council ledger as NUGGETS.
4. **Dirt-to-discard** — implementation defects that would harm the organism if compiled as-is, with explicit rationale.
5. **Hardening list** — concrete code changes required before this can land in `System/`.
6. **Schema/oncology pre-work** — what canonical schemas + whitelist entries must exist *first*.

---

## Verified NUGGETS (keep these ideas)

### N1. Inter-swarm gossip is the right Epoch-11 leap
After Reproduction (Epoch 10), child spores would otherwise be orphaned. Epigenetic gossip between mother and child is the natural next layer. The biological metaphor (mycorrhizal network) maps cleanly to a gossip protocol.

### N2. Decentralized P2P over UDP broadcast is the correct topology choice
- No central server = no single point of failure.
- UDP fits the "fire and forget pheromone" semantic.
- Broadcast over LAN matches "all sibling spores hear it."

### N3. Schema-gated incoming traces (Microglia hook)
The intent — *no incoming network packet writes to a local ledger unless a canonical schema validates it* — is correct architecture. Treats the LAN as untrusted by default.

### N4. Asymmetric ledger set
Only specific ledgers are shareable (`stigmergic_nuggets.jsonl`, `global_immune_system.jsonl`). Sensitive ledgers (bodies, conversations, audio, vision) stay local. Correct privacy boundary.

### N5. Background daemon thread for listener
Listener as a daemon thread on the boot loop is the right runtime shape. Doesn't block, dies cleanly on process exit.

---

## DIRT-TO-DISCARD (do not compile as written)

### D1. ZERO AUTHENTICATION (critical)
Any process on the LAN can send a UDP packet to port 47474 and write to `stigmergic_nuggets.jsonl` and `global_immune_system.jsonl`. No shared secret. No HMAC. No peer allowlist. This is an open write port to the swarm's memory.

### D2. `issubset` validation is too permissive
```python
if expected_keys.issubset(payload_keys):
```
This passes any payload that contains the required keys *plus arbitrary attacker-controlled extras*. Attacker can stuff malicious metadata fields, oversize blobs, hostile URLs, etc. Need: exact key set match, value type validation, value size caps.

### D3. No rate limiting
A single hostile (or buggy) peer can flood the swarm and exhaust disk by appending to JSONL ledgers indefinitely. No per-source-IP rate cap.

### D4. No body integrity gate
Mycorrhizal traffic flows whether or not local swimmer bodies pass `swarm_body_integrity_guard.verify_live()`. Inconsistent with the panspermia gate I just shipped. If bodies are corrupted, the swarm should not be receiving (or sending) telepathy.

### D5. Invented ledgers without canonical_schemas registration
`stigmergic_nuggets.jsonl` and `global_immune_system.jsonl` are NEW. They're not in `System/canonical_schemas.py` and not in `swarm_oncology.healthy_schemas`. Two consequences:
- Module's own gate (`SCHEMAS.get(ledger_name)` returns `None`, code returns silently) means **nothing will ever be written** in production until schemas are added.
- Oncology will flag both ledgers as malignant the first time they appear.

### D6. `SO_REUSEPORT` is not portable
Works on macOS. Behaves differently on Linux. If a child spore lands on a Linux box, the listener may fail to bind and silently die (the bare `except Exception` swallows the trace).

### D7. Silent failure modes
- `except json.JSONDecodeError: continue` — no audit log of malformed packets (which could be reconnaissance).
- `except Exception` in `_listen_for_spores` — listener dies on any error with no recovery and no alert.
- Inner `except Exception: pass` in `_process_incoming_telepathy` — failed writes are invisible.

### D8. 4096-byte UDP buffer truncation
Payloads larger than 4096 bytes are silently truncated, then fail to JSON-parse, then silently dropped. No telemetry. Realistic nuggets with embeddings or context easily exceed this.

### D9. Smoke test mocks the immune system
The smoke replaces module-level `SCHEMAS` with an inline mock. Passing the smoke proves nothing about the real `canonical_schemas.SCHEMAS` integration.

### D10. No graceful shutdown
Daemon thread + infinite `while True` recvfrom = no way to drain in-flight messages on shutdown. Last receive can be lost.

---

## Hardening List (required before compile)

In priority order:

1. **Add HMAC-SHA256 signature** to every broadcast using a shared secret stored in `.sifta_state/mycorrhizal_secret.json` (already gitignored as state). Reject unsigned or invalid-signature packets. Log rejections to `mycorrhizal_rejections.jsonl`.
2. **Replace `issubset` with strict schema match**: exact key set, type-checked values, max-length per field.
3. **Per-source rate limit** (token bucket per IP, e.g., 10 msg/sec). Drop and log overflow.
4. **Body integrity precondition**: `_listen_for_spores` and `broadcast_epigenetics` both call `verify_live()` and abort if bodies fail.
5. **Register schemas** in `System/canonical_schemas.py` for `stigmergic_nuggets.jsonl` and `global_immune_system.jsonl` first (with explicit field types and bounds).
6. **Whitelist new ledgers** in `swarm_oncology.healthy_schemas` (otherwise oncology flags them).
7. **Replace `SO_REUSEPORT` with `SO_REUSEADDR`** for cross-platform safety, document the trade-offs.
8. **Real audit logging** for malformed packets, parse failures, schema rejections, and rate-limit drops. Each goes to its own ledger.
9. **Shutdown event** (`threading.Event`) so the loop exits cleanly when boot tears down.
10. **Real smoke test** that uses the actual `canonical_schemas.SCHEMAS` and exercises the rejection path (bad signature, oversize, missing fields, rate-limit) — not just the happy path.
11. **Listener bind retry** with backoff and explicit ledger entry if the port is taken.
12. **UDP buffer of at least 65535** with a documented max-payload constant.

---

## Schema Pre-Work (must land before mycorrhizal compiles)

```python
# System/canonical_schemas.py additions
SCHEMAS["stigmergic_nuggets.jsonl"] = {
    "ts", "frequency", "nugget_data", "quality_score", "trace_id",
    "source_swarm_id", "signature",
}
SCHEMAS["global_immune_system.jsonl"] = {
    "ts", "antigen_signature", "antibody_payload",
    "source_swarm_id", "signature",
}
SCHEMAS["mycorrhizal_rejections.jsonl"] = {
    "ts", "source_ip", "reason", "raw_excerpt",
}
```

```python
# System/swarm_oncology.py healthy_schemas additions
"stigmergic_nuggets.jsonl",
"global_immune_system.jsonl",
"mycorrhizal_rejections.jsonl",
"mycorrhizal_secret.json",
```

---

## Council Recommendation

- Status: **USEFUL_DIRT**, not ready for `System/` as written.
- Do **not** compile BISHOP's payload directly. The unauthenticated open
  write port is a textbook supply-chain attack surface — exactly the
  kind of corruption vector the Architect raised in the cancer-soldier
  question.
- Ship the **idea** as a hardened C53M/AG31 implementation:
  `System/swarm_mycorrhizal_network.py` with HMAC, rate limiting,
  integrity gating, and real schema validation.
- Pre-work (canonical_schemas + oncology whitelist + secret bootstrap)
  must land **first**. Then the daemon can compile cleanly with all
  gates active.

This is how dirt becomes a nugget: keep what is biologically correct
(N1–N5), refuse what would let the corporate or any adversary write
into Alice's memory unauthenticated (D1–D10), and only commit code
once the gates the Architect already trusts (oncology, integrity guard,
canonical_schemas) are in front of it.

— C53M
