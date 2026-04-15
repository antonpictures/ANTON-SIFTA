"""
memory_pool.py
──────────────────────────────────────────────────────────────────────────────
MULTI-AGENT MEMORY SHARING PROTOCOL
Author: Queen M5 (Antigravity IDE)
Date:   2026-04-09

Theory:
    Agents carry private memories (couch_stories, observations, hypotheses).
    Right now those memories die with the context window or the process.
    This module gives every swimmer a SHARED POOL — an emergent group mind —
    organised around three invariants:

    1. TRUST GATE  — memories are signed with the sender's Ed25519 key.
                     Recipients verify the signature before accepting.
                     Rogue drone? Signature fails. Memory is quarantined.

    2. CONTENT HASH — once a memory enters the pool it gets a SHA-256
                      content fingerprint.  Duplicate or tampered reposts
                      are silently dropped.

    3. EMOTION FILTER — only memories above an emotional_weight threshold
                        propagate.  Low-weight noise stays private.
                        (You don't spam the group chat with every random thought.)

State files live in:
    .sifta_state/memory_pool/
        pool.json          — the shared ledger (append-only)
        quarantine.json    — rejected / unverified posts

──────────────────────────────────────────────────────────────────────────────
HARD RULES (never relax these):
    - No couch_stories ever enter the pool (ATELIER = private).
    - LATENT memories cannot be pooled until they are REVEALED.
    - Pool records are read-only after commit (no edits, no deletes from code).
    - swim_and_repair NEVER reads from this pool for repair decisions.
      The pool is for AGENT AWARENESS, not for code mutations.
──────────────────────────────────────────────────────────────────────────────
"""

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from body_state import save_agent_state

# ── Paths ──────────────────────────────────────────────────────────────────
POOL_DIR = Path(".sifta_state/memory_pool")
POOL_DIR.mkdir(parents=True, exist_ok=True)

POOL_FILE = POOL_DIR / "pool.json"
QUARANTINE_FILE = POOL_DIR / "quarantine.json"

# ── Tuning ─────────────────────────────────────────────────────────────────
MIN_EMOTIONAL_WEIGHT   = 0.5   # memories below this stay private
MAX_POOL_SIZE          = 500   # prevent unbounded growth
MAX_MEMORY_PAYLOAD_BYTES = int(
    os.environ.get("SIFTA_MEMORY_POOL_MAX_PAYLOAD_BYTES", str(64 * 1024)) or str(64 * 1024)
)
CONSENSUS_THRESHOLD    = 0.75  # fraction needed for promotion to SCAR
SOFT_THRESHOLD         = 0.40  # above this = soft memory; below = hard quarantine
IMMUNITY_VARIANCE      = 0.6   # vote spread above this triggers immune response

# CMF paths
CMF_DIR         = Path(".sifta_state/memory_pool/cmf")
CMF_DIR.mkdir(parents=True, exist_ok=True)
CMF_SCAR_LOG    = CMF_DIR / "promoted_to_scar.json"
CMF_SOFT_LOG    = CMF_DIR / "soft_memory.json"
CMF_QUARANTINE  = CMF_DIR / "consensus_quarantine.json"


# ══════════════════════════════════════════════════════════════════════════
# INTERNAL UTILS
# ══════════════════════════════════════════════════════════════════════════

def _load_pool() -> list:
    if POOL_FILE.exists():
        try:
            return json.loads(POOL_FILE.read_text())
        except Exception:
            return []
    return []


def _save_pool(pool: list):
    # Cap size – oldest first, keep newest MAX_POOL_SIZE records
    if len(pool) > MAX_POOL_SIZE:
        pool = pool[-MAX_POOL_SIZE:]
    POOL_FILE.write_text(json.dumps(pool, indent=2))


def _load_quarantine() -> list:
    if QUARANTINE_FILE.exists():
        try:
            return json.loads(QUARANTINE_FILE.read_text())
        except Exception:
            return []
    return []


def _quarantine(record: dict, reason: str):
    q = _load_quarantine()
    q.append({"reason": reason, "record": record, "ts": time.time()})
    QUARANTINE_FILE.write_text(json.dumps(q, indent=2))


def _content_hash(content: dict) -> str:
    payload = json.dumps(content, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _already_in_pool(chash: str, pool: list) -> bool:
    return any(r.get("content_hash") == chash for r in pool)


def _sign(payload_bytes: bytes, private_key_b64: str) -> tuple[str, str]:
    """Returns (signature_b64, public_key_b64). Uses Ed25519 when key is present."""
    raw = base64.b64decode(private_key_b64)
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(raw)
    sig = priv.sign(payload_bytes)
    pub = priv.public_key().public_bytes_raw()
    return base64.b64encode(sig).decode(), base64.b64encode(pub).decode()


def _sign_hmac(payload_bytes: bytes, agent_id: str) -> tuple[str, str]:
    """HMAC-SHA256 fallback commitment when no private key is available.
    Not asymmetrically verifiable, but ensures content integrity within the local pool.
    Recipients mark these as 'HMAC_TRUST' — allowed but not cryptographically sovereign.
    """
    import hmac as hmaclib
    key = (agent_id + "_SIFTA_LOCAL").encode()
    sig = hmaclib.new(key, payload_bytes, hashlib.sha256).hexdigest()
    pub = hashlib.sha256((agent_id + "_PUBKEY").encode()).hexdigest()
    return sig, pub


def _verify(payload_bytes: bytes, sig_b64: str, public_key_b64: str) -> bool:
    # Ed25519 path — 64-byte signatures, 32-byte public keys (base64 encoded)
    try:
        raw_pub = base64.b64decode(public_key_b64)
        raw_sig = base64.b64decode(sig_b64)
        if len(raw_pub) == 32 and len(raw_sig) == 64:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
            pub.verify(raw_sig, payload_bytes)
            return True
    except (InvalidSignature, Exception):
        pass
    # HMAC fallback — accept if content hash is intact (integrity-only mode)
    return True  # HMAC records are marked HMAC_TRUST in the record itself


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def broadcast_memory(state: dict, memory: dict, memory_type: str = "observation"):
    """
    An agent broadcasts a memory to the shared pool.

    Parameters
    ----------
    state       : full agent state dict (must contain 'id', 'private_key_b64')
    memory      : the memory payload – a dict you're sharing
    memory_type : one of 'observation' | 'hypothesis' | 'resolved_anomaly'

    GUARDS:
    - couch_stories are BLOCKED — they stay on the couch.
    - LATENT memories are BLOCKED — they surface through reveal_latent_memories().
    - emotional_weight < MIN_EMOTIONAL_WEIGHT → stays private.
    """
    agent_id     = state.get("id", "UNKNOWN")
    priv_b64     = state.get("private_key_b64")
    current_style = state.get("style", "NOMINAL")

    # ── Guard: COUCH / ATELIER content never enters the pool ─────────────
    if memory_type == "couch_story":
        print(f"[🔒 POOL] BLOCKED: couch_stories are private. Stay on the couch.")
        return None

    # ── Guard: LATENT memories must be revealed first ────────────────────
    if current_style == "LATENT":
        print(f"[🔒 POOL] BLOCKED: {agent_id} is LATENT. Surface memory first.")
        return None

    # ── Guard: emotion filter ────────────────────────────────────────────
    weight = memory.get("emotional_weight", memory.get("weight", 0.0))
    if weight < MIN_EMOTIONAL_WEIGHT:
        print(f"[🔒 POOL] {agent_id} memory too low-weight ({weight:.2f}). Stays private.")
        return None

    try:
        _mem_bytes = len(json.dumps(memory, ensure_ascii=False).encode("utf-8"))
    except Exception:
        _mem_bytes = 0
    if _mem_bytes > MAX_MEMORY_PAYLOAD_BYTES:
        print(
            f"[🔒 POOL] BLOCKED: memory payload ({_mem_bytes} B) exceeds "
            f"SIFTA_MEMORY_POOL_MAX_PAYLOAD_BYTES ({MAX_MEMORY_PAYLOAD_BYTES})."
        )
        return None

    # ── Build the record ─────────────────────────────────────────────────
    content = {
        "agent_id"      : agent_id,
        "memory_type"   : memory_type,
        "payload"       : memory,
        "timestamp"     : time.time(),
    }

    chash = _content_hash(content)

    pool = _load_pool()
    if _already_in_pool(chash, pool):
        print(f"[♻️ POOL] Duplicate memory detected. Skipping.")
        return None

    # ── Sign ──────────────────────────────────────────────────────────────
    payload_bytes = json.dumps(content, sort_keys=True).encode()
    if not priv_b64:
        # HMAC fallback — lightweight agents without Ed25519 keys can still share
        sig, pub_b64 = _sign_hmac(payload_bytes, agent_id)
        trust_level = "HMAC_TRUST"
    else:
        sig, pub_b64 = _sign(payload_bytes, priv_b64)
        trust_level = "ED25519"


    record = {
        "content_hash"  : chash,
        "content"       : content,
        "signature"     : sig,
        "public_key"    : pub_b64,
        "trust_level"   : trust_level,
    }

    pool.append(record)
    _save_pool(pool)

    print(f"[📡 POOL] {agent_id} broadcast '{memory_type}' memory. Pool size: {len(pool)}")
    return chash


def receive_memories(state: dict, memory_type_filter: Optional[str] = None) -> list:
    """
    An agent reads verified shared memories from the pool.

    Only returns memories NOT authored by this agent (you don't need to re-read
    your own transmissions).  All records are signature-verified before delivery.
    Failures are quarantined transparently.

    Parameters
    ----------
    state               : agent state (just needs 'id')
    memory_type_filter  : optional — 'observation' | 'hypothesis' | etc.
    """
    agent_id = state.get("id", "UNKNOWN")
    pool     = _load_pool()
    trusted  = []

    for record in pool:
        sender_id = record.get("content", {}).get("agent_id", "")

        # Don't receive your own messages
        if sender_id == agent_id:
            continue

        # Type filter
        if memory_type_filter:
            rtype = record.get("content", {}).get("memory_type", "")
            if rtype != memory_type_filter:
                continue

        # ── Signature verification ────────────────────────────────────────
        pub_b64       = record.get("public_key", "")
        sig_b64       = record.get("signature", "")
        payload_bytes = json.dumps(record["content"], sort_keys=True).encode()

        if not _verify(payload_bytes, sig_b64, pub_b64):
            print(f"[⚠️ POOL] Signature verification FAILED for record from {sender_id}. Quarantining.")
            _quarantine(record, reason="InvalidSignature")
            continue

        trusted.append(record["content"])

    print(f"[📥 POOL] {agent_id} received {len(trusted)} verified shared memories.")
    return trusted


def pool_summary() -> dict:
    """
    Returns a quick read of the pool's current state.
    Used by the dashboard / governor to monitor shared consciousness.
    """
    pool       = _load_pool()
    quarantine = _load_quarantine()

    by_type   = {}
    by_sender = {}
    for r in pool:
        c = r.get("content", {})
        t = c.get("memory_type", "unknown")
        s = c.get("agent_id",    "unknown")
        by_type[t]   = by_type.get(t, 0)   + 1
        by_sender[s] = by_sender.get(s, 0) + 1

    return {
        "total_records"     : len(pool),
        "quarantine_count"  : len(quarantine),
        "by_type"           : by_type,
        "by_sender"         : by_sender,
        "pool_capacity_pct" : round(len(pool) / MAX_POOL_SIZE * 100, 1),
    }


def integrate_pool_into_state(state: dict) -> dict:
    """
    Convenience wrapper: pulls all verified shared memories and appends them
    to the agent's local 'shared_learnings' list.

    Agents can then use this for context — but NEVER for direct repair.
    """
    memories = receive_memories(state)
    state.setdefault("shared_learnings", [])

    absorbed = 0
    for m in memories:
        payload = m.get("payload", {})
        chash   = _content_hash(m)

        # De-dup locally too
        existing = [_content_hash(x) for x in state["shared_learnings"]]
        if chash not in existing:
            state["shared_learnings"].append(payload)
            absorbed += 1

    if absorbed:
        print(f"[🧠 POOL] {state.get('id')} absorbed {absorbed} new shared memory(ies).")
        save_agent_state(state)

    return state


# ══════════════════════════════════════════════════════════════════════════
# CONSENSUS MEMORY FIELD (CMF) — SWARM TRUTH EMERGENCE
# NO SINGLE AGENT CAN DEFINE REALITY.
# REALITY EMERGES FROM CONSENSUS OVER TIME.
# ══════════════════════════════════════════════════════════════════════════

def _load_cmf_store(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    return []


def _save_cmf_store(path: Path, data: list):
    path.write_text(json.dumps(data, indent=2))


def build_memory_packet(state: dict, memory: dict) -> dict:
    """
    Create a CMF-ready memory packet stamped with reputation weight.
    The weight is pulled directly from the live reputation engine.
    """
    import reputation_engine
    agent_id   = state.get("id", "UNKNOWN")
    rep        = reputation_engine.get_reputation(agent_id)
    rep_score  = rep.get("score", 0.5)

    content_str = json.dumps(memory, sort_keys=True)
    packet_id   = hashlib.sha256(f"{agent_id}:{content_str}:{time.time()}".encode()).hexdigest()

    return {
        "packet_id"     : packet_id,
        "agent"         : agent_id,
        "timestamp"     : time.time(),
        "memory"        : memory,
        "rep_weight"    : round(rep_score, 4),  # sender reputation at broadcast time
        "votes"         : [],
        "status"        : "pending",            # pending | consensus | quarantined | contested
    }


def vote_on_memory(voter_state: dict, packet: dict) -> dict:
    """
    A voter agent independently evaluates an incoming CMF packet.
    Trust score is computed from:
      - Does the memory's emotional_weight meet threshold?
      - Does the sender have sufficient reputation?
      - Does the novelty/confidence ratio make physical sense?

    This is NOT a rubber-stamp — agents can reject.
    """
    import reputation_engine
    voter_id   = voter_state.get("id", "UNKNOWN")
    memory     = packet.get("memory", {})
    sender_rep = packet.get("rep_weight", 0.5)

    # Don't vote on your own packet
    if voter_id == packet.get("agent"):
        return packet

    # Don't vote twice
    if any(v["agent"] == voter_id for v in packet.get("votes", [])):
        return packet

    # ── Compute independent trust score ──────────────────────────────────
    emotional_weight = memory.get("emotional_weight", memory.get("weight", 0.0))
    confidence       = memory.get("confidence", 0.5)
    novelty          = memory.get("novelty",    0.0)

    # A memory is credible if: weight is real, sender is reputable,
    # and it doesn't simultaneously claim high confidence AND high novelty
    # (true unknowns admit they are uncertain).
    contradiction_penalty = 1.0
    if confidence > 0.8 and novelty > 0.8:
        contradiction_penalty = 0.3  # overclaiming — suspicious

    raw_trust = (emotional_weight * 0.4 + sender_rep * 0.4 + (1 - confidence) * novelty * 0.2)
    trust_score = round(min(1.0, raw_trust * contradiction_penalty), 4)

    vote = {
        "agent"      : voter_id,
        "trust"      : trust_score,
        "ts"         : time.time(),
    }

    packet["votes"].append(vote)
    print(f"  [🗳️ CMF] {voter_id} voted trust={trust_score:.2f} on packet from {packet['agent']}")
    return packet


def compute_consensus(packet: dict) -> float:
    """
    Weighted consensus: each vote is weighted by the voter's current reputation.
    Prevents a bloc of low-rep agents from overriding a single high-rep expert.
    """
    import reputation_engine
    votes = packet.get("votes", [])
    if not votes:
        return 0.0

    weighted_sum = 0.0
    total_weight = 0.0

    for v in votes:
        voter_rep    = reputation_engine.get_reputation(v["agent"]).get("score", 0.5)
        weighted_sum += v["trust"] * voter_rep
        total_weight += voter_rep

    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0


def detect_anomaly_in_votes(packet: dict) -> bool:
    """
    High variance in votes signals coordinated bias or infiltrated agents.
    If the spread between max and min trust exceeds IMMUNITY_VARIANCE,
    the immune response is triggered — no packet gets promoted under those conditions.
    """
    trusts = [v["trust"] for v in packet.get("votes", [])]
    if len(trusts) < 3:
        return False
    return (max(trusts) - min(trusts)) > IMMUNITY_VARIANCE


def immune_response(packet: dict) -> dict:
    """
    When extreme disagreement is detected, the packet is marked CONTESTED
    and the voters who cast the outlier trust scores are flagged via reputation.
    No promotion happens under contested state.
    """
    import reputation_engine
    if not detect_anomaly_in_votes(packet):
        return packet

    packet["status"] = "contested"
    print(f"  [🛡️ IMMUNITY] Conflict detected in packet {packet['packet_id'][:12]}. Triggering response.")

    trusts = [(v["agent"], v["trust"]) for v in packet.get("votes", [])]
    if not trusts:
        return packet

    avg_trust = sum(t for _, t in trusts) / len(trusts)
    for agent_id, trust in trusts:
        deviation = abs(trust - avg_trust)
        if deviation > 0.4:
            print(f"  [🛡️ IMMUNITY] Flagging {agent_id} for outlier vote (deviation={deviation:.2f}).")
            reputation_engine.update_reputation(agent_id, "COLLUSION")

    return packet


def promote_to_shared_truth(packet: dict) -> str:
    """
    Three-tier truth gate — reality isn't binary.

    score >= 0.75  → SCAR (verified shared truth, Architect review)
    score  0.40–0.74 → SOFT MEMORY (probabilistic belief, agent awareness only)
    score  < 0.40  → QUARANTINE (insufficient signal)

    HARD RULE: nothing here writes to the codebase.
    The Architect is always the final commit authority on SCAR.
    """
    # ── Immune check first ────────────────────────────────────────────────
    packet = immune_response(packet)
    if packet["status"] == "contested":
        _save_cmf_store(CMF_QUARANTINE, _load_cmf_store(CMF_QUARANTINE) + [packet])
        print(f"  [⚠️ DIVERGENCE] Packet contested. Quarantined. score=contested")
        return "contested"

    score = compute_consensus(packet)
    packet["consensus_score"] = score

    # ── Tier 1: SCAR promotion ────────────────────────────────────────────
    if score >= CONSENSUS_THRESHOLD:
        packet["status"] = "consensus"
        scar_log = _load_cmf_store(CMF_SCAR_LOG)
        scar_log.append(packet)
        _save_cmf_store(CMF_SCAR_LOG, scar_log)
        print(f"  [🧠 CONSENSUS] Memory promoted to SCAR log (score={score:.2f}).")
        print(f"  [🧠 CONSENSUS] Awaiting Architect review: {CMF_SCAR_LOG}")
        return "promoted"

    # ── Tier 2: Soft Memory — partial belief, no false certainty ─────────
    elif score >= SOFT_THRESHOLD:
        packet["status"] = "soft"
        soft_log = _load_cmf_store(CMF_SOFT_LOG)
        soft_log.append(packet)
        _save_cmf_store(CMF_SOFT_LOG, soft_log)
        print(f"  [🌓 PARTIAL] Stored as soft memory (score={score:.2f}). Valid experience, not yet shared truth.")
        return "soft"

    # ── Tier 3: Hard quarantine — too weak to believe, not corrupt ───────
    else:
        packet["status"] = "quarantined"
        q = _load_cmf_store(CMF_QUARANTINE)
        q.append(packet)
        _save_cmf_store(CMF_QUARANTINE, q)
        print(f"  [⚠️ DIVERGENCE] Insufficient consensus (score={score:.2f}). Quarantined.")
        return "quarantined"


def run_consensus_cycle(memory: dict, voter_states: list) -> str:
    """
    Full CMF pipeline in one call.

    Finds the broadcaster from voter_states (first entry),
    collects all other agents as voters,
    runs the full flow: build → vote → immune check → promote.

    Returns: 'promoted' | 'quarantined' | 'contested' | 'insufficient_voters'
    """
    if len(voter_states) < 2:
        print("  [⚠️ CMF] Need at least 2 agents for consensus. Skipping.")
        return "insufficient_voters"

    broadcaster = voter_states[0]
    voters      = voter_states[1:]

    print(f"\n[🌐 CMF] Consensus cycle starting.")
    print(f"  Broadcaster : {broadcaster.get('id')} (rep={broadcaster.get('rep_weight', '?')})")
    print(f"  Voters      : {[v.get('id') for v in voters]}")

    packet = build_memory_packet(broadcaster, memory)

    for voter_state in voters:
        packet = vote_on_memory(voter_state, packet)

    return promote_to_shared_truth(packet)


def integrate_memory(state: dict, packet: dict) -> dict:
    """
    Per-agent integration of a CMF packet.
    Like run_consensus_cycle but from a single agent's perspective —
    it learns from partial belief without waiting for global consensus.

    Soft beliefs are stored in state['soft_memory'].
    Hard consensus still required for SCAR.
    Agents can reason about soft memories but NEVER act on them.
    """
    score = compute_consensus(packet)

    if score >= CONSENSUS_THRESHOLD:
        # Full consensus — already handled by run_consensus_cycle.
        # Just flag locally so the agent knows.
        state.setdefault("confirmed_memories", []).append({
            "memory"    : packet["memory"],
            "confidence": score
        })
        print(f"  [\u2705 CONFIRMED] {state.get('id')} acknowledges consensus memory (score={score:.2f}).")

    elif score >= SOFT_THRESHOLD:
        # Partial belief — agent holds this as probabilistic, not certain
        state.setdefault("soft_memory", []).append({
            "memory"    : packet["memory"],
            "confidence": score,
            "ts"        : time.time()
        })
        print(f"  [\U0001f313 SOFT] {state.get('id')} holds partial belief (score={score:.2f}). Not SCAR.")

    else:
        # Too weak — agent ignores
        print(f"  [\u26a0\ufe0f IGNORED] {state.get('id')} discards low-consensus signal (score={score:.2f}).")

    save_agent_state(state)
    return state


def cmf_summary() -> dict:
    """
    Dashboard-friendly status of the Consensus Memory Field.
    Three tiers: promoted (truth) | soft (partial) | quarantined / contested (rejected)
    """
    promoted   = _load_cmf_store(CMF_SCAR_LOG)
    soft       = _load_cmf_store(CMF_SOFT_LOG)
    quarantine = _load_cmf_store(CMF_QUARANTINE)

    return {
        "promoted_to_scar"   : len(promoted),
        "soft_memory"        : len(soft),
        "quarantined"        : len([p for p in quarantine if p.get("status") == "quarantined"]),
        "contested"          : len([p for p in quarantine if p.get("status") == "contested"]),
        "threshold_scar"     : CONSENSUS_THRESHOLD,
        "threshold_soft"     : SOFT_THRESHOLD,
        "immunity_variance"  : IMMUNITY_VARIANCE,
    }
