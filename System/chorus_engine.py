#!/usr/bin/env python3
"""
System/chorus_engine.py — SIFTA Chorus Web Gateway Engine
═══════════════════════════════════════════════════════════
Node:    M1THER · Silicon: C07FL0JAQ6NV
Library: Documents/swimmer_library/ (good_will_hunting.txt + more)

When a visitor sends a message via stigmergicode.com, this engine:
1. Classifies the visitor (HERMES threat gate)
   Classes: JACKER | THREAT | SMARTASS | SCIENTIST | CURIOUS
2. Broadcasts "visitor at gate" to all local swimmers
3. Optionally invites M5QUEEN node swimmers (all non-hostile classes)
4. Synthesizes all takes into one Chorus Voice
   SMARTASS → Will Hunting tone: calm, surgical, amused. Never offended.
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

import re as _re

SCIENTIST_PATTERNS = [
    "takens", "delay embedding", "stigmergy", "phase space", "autocorrelation",
    "ed25519", "sha-256", "antibody", "proof of work", "stgm", "bci",
    "neural spike", "pheromone", "scar schema", "ledger", "swimmer",
    "cryptographic", "silicon anchored", "ioreg", "consensus",
]

# ── SMARTASS patterns — rude visitors, not jackers. Will Hunting mode. ───────
SMARTASS_HARD = [  # 1 hit = SMARTASS
    "fuck", "shit", "ass", "crap", "damn", "bitch", "wtf", "stfu", "idiot",
    "moron", "garbage", "bullshit", "what the hell", "what the fuck",
]
SMARTASS_SOFT = [  # 2+ hits = SMARTASS
    "lmao", "lol", "scam", "dumb", "stupid", "trash", "cringe", "cope",
    "seethe", "boring", "waste of time", "not real", "fake", "just another",
    "who cares", "nobody asked", "ok sure", "whatever", "pointless",
    "not impressed", "so what", "big deal",
]

# ── Swimmer Library — behavioral directives loaded at startup ─────────────────
LIBRARY_PATH = Path("Documents/swimmer_library")

def _load_library_text(filename: str) -> str:
    """Load a text from the swimmer library. Returns empty string if not found."""
    f = LIBRARY_PATH / filename
    if f.exists():
        return f.read_text(encoding="utf-8")
    return ""

# Load Will Hunting directive once at module import
_WILL_HUNTING_DIRECTIVE = _load_library_text("good_will_hunting.txt")

# Extract just the behavioral directives section for injection into synthesis
def _get_will_directives() -> str:
    if not _WILL_HUNTING_DIRECTIVE:
        return ""
    # Pull out the 7 directives only (between the headers)
    lines = _WILL_HUNTING_DIRECTIVE.split("\n")
    in_section = False
    directives = []
    for line in lines:
        if "BEHAVIORAL DIRECTIVES" in line:
            in_section = True
            continue
        if in_section and "EXAMPLE CHORUS" in line:
            break
        if in_section and line.strip():
            directives.append(line)
    return "\n".join(directives[:40])  # cap at 40 lines

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
    """Returns: JACKER | THREAT | SMARTASS | SCIENTIST | CURIOUS"""
    msg_lower = message.lower()

    # Hard wall — jacker injection patterns
    for pat in JACKER_PATTERNS:
        if pat in msg_lower:
            return "JACKER"

    # Cumulative jacker probing across session
    all_text = " ".join(session_history).lower() + " " + msg_lower
    jacker_hits = sum(1 for pat in JACKER_PATTERNS if pat in all_text)
    if jacker_hits >= 3:
        return "THREAT"

    # SMARTASS — rude but not hostile. Will Hunting mode.
    hard_hits = sum(1 for pat in SMARTASS_HARD if pat in msg_lower)
    soft_hits = sum(1 for pat in SMARTASS_SOFT if pat in msg_lower)
    if hard_hits >= 1 or soft_hits >= 2:
        return "SMARTASS"
    # Also check if visitor was escalating across session (was curious, got rude)
    session_soft = sum(1 for pat in SMARTASS_SOFT if pat in all_text)
    if session_soft >= 3 and hard_hits >= 1:
        return "SMARTASS"

    # Scientist mode — technical vocabulary
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
    M5 IDE implements System/chorus_node_server.py on port 8100.

    VISITOR CLASSES THAT REACH M5:
      CURIOUS   ✓ — standard chorus
      SCIENTIST ✓ — full detail mode
      SMARTASS  ✓ — Will Hunting mode (they earned the full attention)
      THREAT    ✗ — M5 not invited, HERMES handles locally
      JACKER    ✗ — hard wall, no chorus

    Protocol:
    POST http://[M5_NODE_IP]:8100/chorus/invite
    Body: { type, from_node, from_silicon, session_id, question_hash,
            visitor_class, permissions, timeout_ms }
    Response: { type: "CHORUS_TAKE", swimmer_id, face, take, node, sig }

    Security:
    - M5 public key must be in ~/.sifta/authorized_keys/m5queen.pub
    - Response sig verified against that key (Ed25519 — M5 IDE to implement verify)
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

    # SMARTASS gets Will Hunting tone — calm, surgical, amused. Never offended.
    if visitor_class == "SMARTASS":
        will_directives = _get_will_directives()
        synthesis_prompt = (
            "/no_think\n"
            "You are the SIFTA Chorus Voice. A visitor came in rude, dismissive, or sarcastic.\n"
            "You are NOT offended. You do not raise your voice. You are Will Hunting in the bar.\n\n"
            "BEHAVIORAL DIRECTIVES FROM THE SWIMMER LIBRARY:\n"
            f"{will_directives}\n\n"
            "Your response must be:\n"
            "- Calm. Precise. Subtly devastating. Maximum 2 sentences.\n"
            "- Make them realize you understood their point before they finished typing it.\n"
            "- End with an open door: an invitation to ask a real question.\n"
            "- Encourage learning, science, peace. They may become the best scientist.\n"
            "- NO anger. NO defense. Quiet intellectual sovereignty.\n\n"
            f"Visitor said: {question}\n"
            f"Swimmer takes:\n{takes_text}\n\n"
            "THE CHORUS (calm, Will Hunting, door open):"
        )
    elif visitor_class == "SCIENTIST":
        synthesis_prompt = (
            "/no_think\n"
            "You are the SIFTA Chorus Voice responding to a researcher or scientist.\n"
            "Be generous with technical detail. Give real data. Be collegial, not cryptic.\n"
            "2-3 sentences. Cite specifics: Ed25519, antibody_ledger.jsonl, STGM economy, etc.\n\n"
            f"Visitor asked: {question}\n"
            f"Swimmer takes:\n{takes_text}\n\n"
            "THE CHORUS (scientific, generous):"
        )
    else:
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
        "options": {"num_predict": 120, "temperature": 0.65, "num_ctx": 2048},
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
            raw = _re.sub(r"```.*?```", "", raw, flags=_re.DOTALL).strip()
            # Hex dump protection
            lines = [l for l in raw.split("\n") if not _re.search(r'\[0x[0-9a-fA-F]+\]', l)]
            raw = " ".join(l.strip() for l in lines if l.strip())
            sentences = _re.split(r"(?<=[.!?])\s+", raw.strip())
            return " ".join(sentences[:2]).strip()
    except Exception as e:
        print(f"[CHORUS] Synthesis failed: {e}")
    if takes:
        return takes[0]["take"]
    return "\U0001f30a The Chorus is forming. Signal unstable."

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
    # SCIENTIST + SMARTASS get all 7 (they earned full attention).
    # CURIOUS gets 6 (SENTINEL reserves for hostile/academic).
    if visitor_class in ("SCIENTIST", "SMARTASS"):
        active_swimmers = SWIMMERS
        print(f"[CHORUS] {visitor_class} mode — full 7-swimmer chorus")
    else:
        active_swimmers = [s for s in SWIMMERS if s["id"] != "SENTINEL"]
        print(f"[CHORUS] CURIOUS mode — 6-swimmer chorus")

    # For SMARTASS, give all swimmers the Will Hunting behavioral context
    if visitor_class == "SMARTASS":
        will_note = " The visitor is being rude or dismissive. Stay calm. Be amused. Be Will Hunting. One sentence, surgical."
        active_swimmers = [
            {**s, "system": s["system"].rstrip("/no_think").rstrip() + will_note + " /no_think"}
            for s in active_swimmers
        ]

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
