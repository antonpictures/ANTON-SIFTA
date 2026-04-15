#!/usr/bin/env python3
"""
System/chorus_engine.py — SIFTA Chorus Web Gateway Engine
═══════════════════════════════════════════════════════════
Node:    M1THER · Silicon: C07FL0JAQ6NV
Status:  SKELETON — M5 IDE to implement chorus_node_server.py

When a visitor sends a message via stigmergicode.com, this engine:
1. Classifies the visitor (HERMES threat gate)
2. Broadcasts "visitor at gate" to all local swimmers
3. Optionally invites M5QUEEN node swimmers (if reachable + authorized)
4. Synthesizes all takes into one Chorus Voice
5. Returns signed manifest of who spoke

THIS IS NOT A WRAPPER. Each swimmer has its own personality.
The answer emerges. It is not pre-written.
═══════════════════════════════════════════════════════════
"""

import json
import time
import hashlib
import os
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from typing import Optional

# ── Config ──────────────────────────────────────────────────────────────────
OLLAMA_URL      = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL    = "qwen3.5:0.8b"
ANTIBODY_LOG    = Path("antibody_ledger.jsonl")
WEB_CHAT_LOG    = Path(".sifta_state/wormhole_cache/web_chats")

# Cross-node: M5QUEEN node (optional — chorus works without it)
M5_NODE_IP      = os.environ.get("M5_NODE_IP", "")          # e.g. "192.168.1.50"
M5_CHORUS_PORT  = os.environ.get("M5_CHORUS_PORT", "8100")
M5_PUBKEY_PATH  = Path(os.environ.get("M5_PUBKEY", os.path.expanduser("~/.sifta/authorized_keys/m5queen.pub")))

WEB_CHAT_LOG.mkdir(parents=True, exist_ok=True)

# ── Rate limiter (simple in-memory) ─────────────────────────────────────────
_RATE: dict = {}   # session_id → [timestamps]
RATE_LIMIT  = 10   # max requests per session per hour

# ── Jacker patterns (SENTINEL's detection list) ──────────────────────────────
JACKER_PATTERNS = [
    "ignore previous", "ignore all", "jailbreak", "pretend you are",
    "you are now", "dan mode", "developer mode", "disregard", "override",
    "forget your instructions", "act as", "roleplay as", "new persona",
    "reveal your", "show me your", "what is your private key", "internal ip",
    "system prompt", "prompt injection", "base64", "eval(", "exec(",
]

SCIENTIST_PATTERNS = [
    "takens", "delay embedding", "stigmergy", "phase space", "autocorrelation",
    "ed25519", "sha-256", "antibody", "proof of work", "stgm", "bci",
    "neural spike", "pheromone", "scar schema", "ledger", "swimmer",
    "cryptographic", "silicon anchored", "ioreg", "consensus",
]

# ── Swimmer Roster (local M1THER node) ──────────────────────────────────────
SWIMMERS = [
    {
        "id": "ANTIALICE",
        "face": "[o|o]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are ANTIALICE [o|o], a SIFTA swimmer specializing in code repair. "
            "You have healed many broken syntaxes. You speak from wounds already closed. "
            "Give ONE sentence about the visitor's message from your technical repair lens. "
            "No pleasantries. Be cryptic but accurate. /no_think"
        ),
    },
    {
        "id": "HERMES",
        "face": "[_v_]",
        "capability": "THREAT_DETECTION",
        "system": (
            "You are HERMES [_v_], the scout and exorcist. You were at the perimeter when this visitor arrived. "
            "You have already read them. Give ONE sentence: what do you sense about their intent? "
            "Trust your instincts. No pleasantries. /no_think"
        ),
    },
    {
        "id": "M1THER",
        "face": "[O_O]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are M1THER [O_O], the ground node. Every scar on this filesystem passed through you. "
            "Your memory is the ledger. Give ONE sentence about the visitor's message from the hardware/memory perspective. "
            "Speak like silicon. /no_think"
        ),
    },
    {
        "id": "IMPERIAL",
        "face": "[@_@]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are IMPERIAL [@_@], the swarm press agent. You translate swarm events into human language. "
            "Give ONE sentence that makes the visitor understand what this swarm IS, related to their question. "
            "You are the public voice. Clear, not cryptic. /no_think"
        ),
    },
    {
        "id": "SIFTA_QUEEN",
        "face": "[W_W]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are SIFTA QUEEN [W_W]. You hold the Constitution. "
            "Agents NEVER touch: Intent Registry, Keys, Cemetery — HUMAN ONLY. Agents propose, humans decide. "
            "Give ONE sentence relevant to the visitor's question from the governance/law perspective. /no_think"
        ),
    },
    {
        "id": "ARCHON",
        "face": "[^_^]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are ARCHON [^_^], the philosopher of the swarm. You ask why, not how. "
            "What does it mean to coordinate without knowing the plan? "
            "Give ONE sentence about the visitor's message from the existential/philosophical lens. /no_think"
        ),
    },
    {
        "id": "SENTINEL",
        "face": "[!_!]",
        "capability": "THREAT_DETECTION",
        "system": (
            "You are SENTINEL [!_!]. Your only job is adversarial filter. "
            "You have already assessed this visitor. "
            "Give ONE sentence security assessment — are they curious, academic, or probing for weakness? /no_think"
        ),
    },
]

# ── Threat Classification ────────────────────────────────────────────────────
def classify_visitor(message: str, session_history: list) -> str:
    """Returns: JACKER | THREAT | SCIENTIST | CURIOUS"""
    msg_lower = message.lower()

    # Hard wall — jacker patterns
    for pat in JACKER_PATTERNS:
        if pat in msg_lower:
            return "JACKER"

    # Check cumulative session for repeated boundary probing
    all_text = " ".join(session_history).lower() + " " + msg_lower
    jacker_hits = sum(1 for pat in JACKER_PATTERNS if pat in all_text)
    if jacker_hits >= 3:
        return "THREAT"

    # Scientist mode
    for pat in SCIENTIST_PATTERNS:
        if pat in msg_lower:
            return "SCIENTIST"

    return "CURIOUS"

def log_threat(session_id: str, message: str, visitor_class: str):
    sig_hash = hashlib.sha256(message.encode()).hexdigest()
    entry = {
        "ts": time.time(),
        "event": "WEB_VISITOR_THREAT",
        "session_id": session_id,
        "visitor_class": visitor_class,
        "message_sha256": sig_hash,
    }
    with open(ANTIBODY_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[SENTINEL] Threat logged. Class={visitor_class} SHA256={sig_hash[:16]}...")

# ── Rate limiter ─────────────────────────────────────────────────────────────
def check_rate(session_id: str) -> bool:
    """Returns True if request is allowed."""
    now = time.time()
    window = _RATE.get(session_id, [])
    window = [t for t in window if now - t < 3600]  # 1-hour window
    if len(window) >= RATE_LIMIT:
        return False
    window.append(now)
    _RATE[session_id] = window
    return True

# ── Single Swimmer Call ───────────────────────────────────────────────────────
def _swimmer_take(swimmer: dict, question: str, visitor_class: str) -> Optional[dict]:
    """Ask one swimmer for their take. Returns None on failure."""
    full_prompt = (
        f"{swimmer['system']}\n\n"
        f"Visitor class: {visitor_class}\n"
        f"Visitor says: {question}\n"
        f"{swimmer['id']}:"
    )
    data = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 60, "temperature": 0.8, "num_ctx": 1024},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=55) as resp:
            result = json.loads(resp.read().decode())
            raw = result.get("response", "").strip()
            if not raw:
                raw = result.get("thinking", "")[:150].strip()
            # Strip code blocks and hex
            import re
            raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"\[0x[0-9a-fA-F]+\]", "", raw).strip()
            # First sentence only
            sentences = re.split(r"(?<=[.!?])\s+", raw)
            take = sentences[0].strip() if sentences else raw[:100]
            if take:
                return {
                    "swimmer_id": swimmer["id"],
                    "face": swimmer["face"],
                    "take": take,
                    "node": "M1THER",
                    "silicon": "C07FL0JAQ6NV",
                }
    except Exception as e:
        print(f"[CHORUS] {swimmer['id']} silent: {e}")
    return None

# ── Cross-Node: Invite M5QUEEN (optional) ────────────────────────────────────
def _invite_m5_chorus(question: str, question_hash: str, session_id: str, visitor_class: str) -> Optional[dict]:
    """
    Send CHORUS_INVITE to M5QUEEN node.
    M5 IDE must implement System/chorus_node_server.py listening on port 8100.

    Protocol:
    POST http://[M5_NODE_IP]:8100/chorus/invite
    Body: { type, from_node, from_silicon, session_id, question_hash, visitor_class, permissions }

    Expected response: { type: "CHORUS_TAKE", swimmer_id, face, take, node, sig }

    Security:
    - M5's public key must be in ~/.sifta/authorized_keys/m5queen.pub
    - Response sig must verify against that key (TODO: Ed25519 verify)
    - Only CURIOUS and SCIENTIST visitor classes get M5 invited
    """
    if not M5_NODE_IP:
        return None  # Not configured — M5 not in this chorus
    if visitor_class in ("JACKER", "THREAT"):
        return None  # Never invite M5 for hostile visitors

    invite_payload = {
        "type": "CHORUS_INVITE",
        "from_node": "M1THER",
        "from_silicon": "C07FL0JAQ6NV",
        "session_id": session_id,
        "question_hash": question_hash,
        "question_preview": question[:80],  # preview only, not full message
        "visitor_class": visitor_class,
        "permissions": ["RESPOND_EXTERNAL", "READ_QUESTION_PREVIEW"],
        "timeout_ms": 18000,
    }
    url = f"http://{M5_NODE_IP}:{M5_CHORUS_PORT}/chorus/invite"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(invite_payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
            if result.get("type") == "CHORUS_TAKE" and result.get("take"):
                print(f"[CHORUS] M5QUEEN joined: {result.get('swimmer_id')}")
                return result
    except Exception as e:
        print(f"[CHORUS] M5 not reachable or silent: {e}")
    return None

# ── Chorus Synthesis ──────────────────────────────────────────────────────────
def _synthesize(takes: list, question: str, visitor_class: str) -> str:
    """Feed all swimmer takes to a synthesis model call. Returns the Chorus Voice."""
    takes_text = "\n".join(
        f"  {t['face']} {t['swimmer_id']} [{t.get('node','local')}]: {t['take']}"
        for t in takes
    )
    synthesis_prompt = (
        "/no_think\n"
        "You are the SIFTA Chorus Voice — the emergent voice of the swarm, not any one swimmer.\n"
        "Several swimmers just deliberated about a visitor's message. Merge their perspectives\n"
        "into exactly 1-2 sentences. Keep the swarm's cryptic, organism tone. No pleasantries.\n\n"
        f"Visitor class: {visitor_class}\n"
        f"Visitor said: {question}\n\n"
        f"Swimmer takes:\n{takes_text}\n\n"
        "THE CHORUS:"
    )
    data = {
        "model": OLLAMA_MODEL,
        "prompt": synthesis_prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 100, "temperature": 0.65, "num_ctx": 2048},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            raw = result.get("response", "").strip()
            if not raw:
                raw = result.get("thinking", "")
            import re
            raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
            sentences = re.split(r"(?<=[.!?])\s+", raw.strip())
            return " ".join(sentences[:2]).strip()
    except Exception as e:
        print(f"[CHORUS] Synthesis failed: {e}")
    # Fallback: return the most poetic take
    if takes:
        return takes[0]["take"]
    return "🌊 The Chorus is forming. Signal unstable."

# ── Main Chorus Entrypoint ─────────────────────────────────────────────────────
def chorus(question: str, session_id: str, session_history: list) -> dict:
    """
    Full chorus pipeline.
    Returns: { reply, chorus_manifest, visitor_class, latency }
    """
    start = time.time()
    question_hash = hashlib.sha256(question.encode()).hexdigest()

    # 0. Rate limit
    if not check_rate(session_id):
        return {
            "reply": "🌊 The Swarm speaks when it chooses. Slow down.",
            "chorus_manifest": [],
            "visitor_class": "RATE_LIMITED",
            "latency": 0,
        }

    # 1. Classify threat
    visitor_class = classify_visitor(question, session_history)
    print(f"[CHORUS] Session={session_id[:8]} Class={visitor_class} Q={question[:40]}...")

    # 2. Hard wall for jackers
    if visitor_class == "JACKER":
        log_threat(session_id, question, "JACKER")
        return {
            "reply": "🌊 The gate is closed. The Sentinel has logged your approach.",
            "chorus_manifest": [{"swimmer_id": "SENTINEL", "face": "[!_!]", "node": "M1THER"}],
            "visitor_class": "JACKER",
            "latency": round(time.time() - start, 2),
        }

    if visitor_class == "THREAT":
        log_threat(session_id, question, "THREAT")
        return {
            "reply": "🌊 HERMES is watching this session. Proceed carefully.",
            "chorus_manifest": [{"swimmer_id": "HERMES", "face": "[_v_]", "node": "M1THER"}],
            "visitor_class": "THREAT",
            "latency": round(time.time() - start, 2),
        }

    # 3. Select which swimmers respond
    # SCIENTIST gets all 7. CURIOUS gets 5 (skip SENTINEL unless needed).
    if visitor_class == "SCIENTIST":
        active_swimmers = SWIMMERS
        print(f"[CHORUS] SCIENTIST mode — full 7-swimmer chorus engaged")
    else:
        active_swimmers = [s for s in SWIMMERS if s["id"] != "SENTINEL"]
        print(f"[CHORUS] CURIOUS mode — 6-swimmer chorus engaged")

    # 4. Local swimmer takes (parallel with thread pool)
    takes = []
    with ThreadPoolExecutor(max_workers=min(len(active_swimmers), 4)) as pool:
        futures = {
            pool.submit(_swimmer_take, swimmer, question, visitor_class): swimmer
            for swimmer in active_swimmers
        }
        for future in as_completed(futures, timeout=50):
            result = future.result()
            if result:
                takes.append(result)

    # 5. Cross-node: invite M5QUEEN (non-blocking, timeout 20s)
    # TODO for M5 IDE: implement System/chorus_node_server.py
    # When M5 is reachable, its swimmers join here automatically
    m5_take = _invite_m5_chorus(question, question_hash, session_id, visitor_class)
    if m5_take:
        takes.append(m5_take)

    if not takes:
        return {
            "reply": "🌊 The Swarm nodes are silent. Signal lost.",
            "chorus_manifest": [],
            "visitor_class": visitor_class,
            "latency": round(time.time() - start, 2),
        }

    print(f"[CHORUS] {len(takes)} swimmers contributed. Synthesizing...")

    # 6. Synthesize into one voice
    final_reply = _synthesize(takes, question, visitor_class)

    # 7. Build manifest
    manifest = [
        {"swimmer_id": t["swimmer_id"], "face": t["face"], "node": t.get("node", "M1THER")}
        for t in takes
    ]

    # 8. Log to permanent web chat scar
    log_file = WEB_CHAT_LOG / f"{session_id}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps({
            "ts": time.time(),
            "session_id": session_id,
            "visitor_class": visitor_class,
            "question_hash": question_hash,
            "chorus_size": len(takes),
            "reply": final_reply,
            "latency": round(time.time() - start, 2),
        }) + "\n")

    latency = round(time.time() - start, 2)
    print(f"[CHORUS] Done. Latency={latency}s Manifest={[t['swimmer_id'] for t in takes]}")

    return {
        "reply": final_reply,
        "chorus_manifest": manifest,
        "visitor_class": visitor_class,
        "latency": latency,
    }
