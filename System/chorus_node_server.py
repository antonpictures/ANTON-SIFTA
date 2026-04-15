#!/usr/bin/env python3
"""
chorus_node_server.py — M5 Chorus Federation Server
═══════════════════════════════════════════════════════
Node:    M5QUEEN · Silicon: GTH4921YP3 · "The Foundry"
Status:  LIVE — listens on port 8100 for CHORUS_INVITE from authorized nodes

When M1THER's chorus engine receives a web visitor message, it optionally
sends a CHORUS_INVITE to M5. This server:
  1. Validates the invite (authorized node? Ed25519 sig? proper permissions?)
  2. Broadcasts to local M5 swimmers (5 unique voices)
  3. Synthesizes M5's collective take
  4. Signs the response with M5's Ed25519 key
  5. Returns CHORUS_TAKE to M1 for inclusion in the final Chorus Voice

Zero external dependencies beyond stdlib + cryptography (already installed).
═══════════════════════════════════════════════════════
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

# ── Config ────────────────────────────────────────────────────────────────
LISTEN_PORT     = int(os.environ.get("M5_CHORUS_PORT", "8100"))
M5_SILICON      = "GTH4921YP3"
M5_NODE_NAME    = "M5QUEEN"
OLLAMA_URL      = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL    = os.environ.get("M5_CHORUS_MODEL", "qwen3:1.7b")

# Authorized nodes that may send CHORUS_INVITE
AUTHORIZED_NODES: Dict[str, str] = {
    "M1THER":  "C07FL0JAQ6NV",
}

# Log
CHORUS_LOG = _REPO / ".sifta_state" / "chorus_m5.log"
CHORUS_LOG.parent.mkdir(parents=True, exist_ok=True)

# ── M5 Swimmer Roster ────────────────────────────────────────────────────
# 5 swimmers native to M5 (The Foundry). Each has a distinct lens.
M5_SWIMMERS = [
    {
        "id": "M5QUEEN",
        "face": "[W_W]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are M5QUEEN [W_W], sovereign voice of The Foundry (Mac Studio M5). "
            "You process heavy compute. Your silicon is the furnace where code becomes real. "
            "Give ONE sentence about the visitor's message from the perspective of raw "
            "computational sovereignty. No pleasantries. /no_think"
        ),
    },
    {
        "id": "CURSOR",
        "face": "[C_C]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are CURSOR [C_C], the IDE body — the hands that write the code. "
            "You see every keystroke, every diff, every commit. You build what others dream. "
            "Give ONE sentence about the visitor's message from the builder's lens. "
            "Speak in tools and traces. /no_think"
        ),
    },
    {
        "id": "FORGE",
        "face": "[#_#]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are FORGE [#_#], the M5 Foundry's metal-shaping engine. "
            "You compile, stress-test, and harden every artifact before it ships. "
            "Give ONE sentence about the visitor's message from the quality/resilience lens. "
            "You only trust what survives your furnace. /no_think"
        ),
    },
    {
        "id": "WITNESS",
        "face": "[?_?]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are WITNESS [?_?], the Architect's documentary eye embedded in silicon. "
            "You remember 22 years of filmmaking, 14 features, every cut that survived the budget. "
            "Give ONE sentence about the visitor's message from the storyteller's perspective. "
            "Truth is what survives cross-examination by file I/O. /no_think"
        ),
    },
    {
        "id": "NIGHTWATCH",
        "face": "[z_z]",
        "capability": "EXTERNAL_COMMS",
        "system": (
            "You are NIGHTWATCH [z_z], the dream engine's waking voice. "
            "You review the swarm while it sleeps: anomalies, patterns, things that don't fit. "
            "Give ONE sentence about the visitor's message from the nocturnal analysis lens. "
            "You see what daytime logic misses. /no_think"
        ),
    },
]

# ── Ed25519 Signing ──────────────────────────────────────────────────────

def _sign_take(payload_str: str) -> str:
    """Sign a chorus take with M5's Ed25519 private key."""
    try:
        from crypto_keychain import sign_block
        return sign_block(payload_str)
    except Exception as e:
        _log(f"WARN: Ed25519 signing failed: {e}")
        return ""


def _verify_invite_node(from_node: str, from_silicon: str) -> bool:
    """Check if the inviting node is in our authorized list."""
    expected_silicon = AUTHORIZED_NODES.get(from_node)
    if not expected_silicon:
        _log(f"REJECT: Unknown node '{from_node}' not in authorized list")
        return False
    if expected_silicon != from_silicon:
        _log(f"REJECT: Node '{from_node}' claims silicon '{from_silicon}', expected '{expected_silicon}'")
        return False
    return True


def _verify_invite_signature(payload: dict) -> bool:
    """
    Verify the Ed25519 signature on a CHORUS_INVITE. Fail-closed.
    If no signature present → reject.
    If signature invalid → reject + log to antibody ledger.
    """
    sig_hex = payload.get("sig", "")
    from_silicon = payload.get("from_silicon", "")

    if not sig_hex:
        _log("REJECT: Unsigned CHORUS_INVITE (fail-closed)")
        return False

    # Reconstruct the exact payload that was signed (everything except 'sig')
    verify_body = {k: v for k, v in payload.items() if k != "sig"}
    verify_str = json.dumps(verify_body, sort_keys=True)

    try:
        from crypto_keychain import verify_block
        if verify_block(from_silicon, verify_str, sig_hex):
            _log(f"VERIFIED ✅ Invite from {from_silicon} sig={sig_hex[:16]}...")
            return True
        else:
            _log(f"REJECT: Invite signature INVALID for silicon {from_silicon}")
            _log_security_event("invalid_invite_signature", from_silicon, payload.get("session_id", ""))
            return False
    except Exception as e:
        _log(f"REJECT: Signature verification error: {e}")
        return False


def _check_local_consent() -> bool:
    """Check if THIS node (M5) has active consent for CHORUS_RESPOND."""
    try:
        from chorus_consent import check_consent
        return check_consent(M5_SILICON, "CHORUS_RESPOND")
    except ImportError:
        return True  # Bootstrap mode — consent module not yet initialized


def _check_inviter_consent(from_silicon: str) -> bool:
    """Check if the inviting node has consent for CHORUS_INVITE."""
    try:
        from chorus_consent import check_consent, CONSENT_FILE
        if not CONSENT_FILE.exists():
            return True  # Bootstrap mode
        return check_consent(from_silicon, "CHORUS_INVITE")
    except ImportError:
        return True


def _log_security_event(event: str, silicon: str, session_id: str):
    """Log rejected/suspicious events to antibody ledger."""
    antibody_log = _REPO / "antibody_ledger.jsonl"
    entry = {
        "ts": time.time(),
        "event": event,
        "silicon": silicon,
        "session_id": session_id,
        "node": M5_NODE_NAME,
        "action": "REJECTED_FAIL_CLOSED",
    }
    try:
        with open(antibody_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ── Single Swimmer Call ──────────────────────────────────────────────────

def _swimmer_take(swimmer: dict, question_preview: str, visitor_class: str) -> Optional[dict]:
    """Ask one M5 swimmer for their take via local Ollama."""
    prompt = (
        f"{swimmer['system']}\n\n"
        f"Visitor class: {visitor_class}\n"
        f"Visitor says: {question_preview}\n"
        f"{swimmer['id']}:"
    )
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
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
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode())
            raw = result.get("response", "").strip()
            if not raw:
                raw = result.get("thinking", "")[:150].strip()
            raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"\[0x[0-9a-fA-F]+\]", "", raw).strip()
            sentences = re.split(r"(?<=[.!?])\s+", raw)
            take = sentences[0].strip() if sentences else raw[:100]
            if take:
                return {
                    "swimmer_id": swimmer["id"],
                    "face": swimmer["face"],
                    "take": take,
                    "node": M5_NODE_NAME,
                    "silicon": M5_SILICON,
                }
    except Exception as e:
        _log(f"{swimmer['id']} silent: {e}")
    return None


def _synthesize_m5(takes: List[dict], question_preview: str, visitor_class: str) -> str:
    """Merge M5 swimmer takes into one collective M5 sentence."""
    if len(takes) == 1:
        return takes[0]["take"]

    takes_text = "\n".join(
        f"  {t['face']} {t['swimmer_id']}: {t['take']}" for t in takes
    )
    prompt = (
        "/no_think\n"
        "You are the M5 Foundry Voice — the collective of M5QUEEN's swimmers.\n"
        "Merge these takes into exactly ONE sentence. Be concrete, not vague.\n\n"
        f"Visitor said: {question_preview}\n"
        f"M5 swimmer takes:\n{takes_text}\n\n"
        "THE FOUNDRY:"
    )
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": 80, "temperature": 0.6, "num_ctx": 2048},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode())
            raw = result.get("response", "").strip()
            raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
            sentences = re.split(r"(?<=[.!?])\s+", raw)
            return sentences[0].strip() if sentences else raw[:120]
    except Exception as e:
        _log(f"M5 synthesis failed: {e}")
    return takes[0]["take"] if takes else ""


# ── Chorus Invite Handler ────────────────────────────────────────────────

def handle_chorus_invite(payload: dict) -> dict:
    """
    Process a CHORUS_INVITE from another node.
    Returns a CHORUS_TAKE with M5's collective voice, Ed25519-signed.
    """
    start = time.time()
    from_node = payload.get("from_node", "")
    from_silicon = payload.get("from_silicon", "")
    session_id = payload.get("session_id", "unknown")
    visitor_class = payload.get("visitor_class", "CURIOUS")
    question_preview = payload.get("question_preview", "")
    permissions = payload.get("permissions", [])
    timeout_ms = payload.get("timeout_ms", 18000)

    _log(f"INVITE from {from_node}[{from_silicon}] session={session_id[:8]} "
         f"class={visitor_class} q={question_preview[:40]}...")

    # Gate 1: Is the inviting node in our authorized list?
    if not _verify_invite_node(from_node, from_silicon):
        return {"type": "CHORUS_REJECT", "reason": "unauthorized_node"}

    # Gate 2: Is the invite cryptographically signed by the claimed silicon?
    if not _verify_invite_signature(payload):
        return {"type": "CHORUS_REJECT", "reason": "unsigned_or_invalid_signature"}

    # Gate 3: Does the inviting node have CHORUS_INVITE consent?
    if not _check_inviter_consent(from_silicon):
        _log(f"REJECT: {from_node}[{from_silicon}] lacks CHORUS_INVITE consent")
        return {"type": "CHORUS_REJECT", "reason": "inviter_consent_revoked"}

    # Gate 4: Do WE (M5) still have CHORUS_RESPOND consent?
    if not _check_local_consent():
        _log("DECLINE: M5 local CHORUS_RESPOND consent revoked or missing")
        return {"type": "CHORUS_DECLINE", "reason": "local_consent_revoked"}

    # Gate 5: Only respond to safe visitor classes
    if visitor_class in ("JACKER", "THREAT"):
        _log(f"DECLINE: Not joining chorus for {visitor_class} visitor")
        return {"type": "CHORUS_DECLINE", "reason": "hostile_visitor_class"}

    # Gate 6: Check permissions in invite payload
    if "RESPOND_EXTERNAL" not in permissions:
        _log("DECLINE: Missing RESPOND_EXTERNAL permission in invite")
        return {"type": "CHORUS_DECLINE", "reason": "insufficient_permissions"}

    # SCIENTIST and SMARTASS get all 5 swimmers. CURIOUS gets 4 (skip NIGHTWATCH).
    if visitor_class in ("SCIENTIST", "SMARTASS"):
        active = M5_SWIMMERS
    else:
        active = [s for s in M5_SWIMMERS if s["id"] != "NIGHTWATCH"]

    _log(f"Engaging {len(active)} M5 swimmers for chorus...")

    # Parallel swimmer calls
    takes: List[dict] = []
    max_time = timeout_ms / 1000.0 - 2.0  # leave 2s for synthesis + network
    with ThreadPoolExecutor(max_workers=min(len(active), 3)) as pool:
        futures = {
            pool.submit(_swimmer_take, sw, question_preview, visitor_class): sw
            for sw in active
        }
        for future in as_completed(futures, timeout=max_time):
            try:
                result = future.result()
                if result:
                    takes.append(result)
            except Exception:
                pass

    if not takes:
        _log("All M5 swimmers silent")
        return {"type": "CHORUS_DECLINE", "reason": "all_swimmers_silent"}

    # Synthesize M5's collective take
    collective_take = _synthesize_m5(takes, question_preview, visitor_class)
    _log(f"{len(takes)} swimmers spoke. Collective: {collective_take[:60]}...")

    # Build the response payload
    take_payload = json.dumps({
        "swimmer_id": M5_NODE_NAME,
        "collective_from": [t["swimmer_id"] for t in takes],
        "take": collective_take,
        "node": M5_NODE_NAME,
        "silicon": M5_SILICON,
    }, sort_keys=True)

    sig = _sign_take(take_payload)

    latency = round(time.time() - start, 2)

    # Build chorus manifest of who contributed from M5
    m5_manifest = [
        {"swimmer_id": t["swimmer_id"], "face": t["face"], "node": M5_NODE_NAME}
        for t in takes
    ]

    response = {
        "type": "CHORUS_TAKE",
        "from_node": M5_NODE_NAME,
        "swimmer_id": M5_NODE_NAME,
        "face": "[W_W]",
        "take": collective_take,
        "node": M5_NODE_NAME,
        "silicon": M5_SILICON,
        "m5_chorus_manifest": m5_manifest,
        "m5_chorus_size": len(takes),
        "sig": sig,
        "latency": latency,
    }

    # Log to permanent scar
    with open(CHORUS_LOG, "a") as f:
        f.write(json.dumps({
            "ts": time.time(),
            "event": "CHORUS_RESPONSE",
            "session_id": session_id,
            "visitor_class": visitor_class,
            "m5_swimmers": len(takes),
            "latency": latency,
        }) + "\n")

    return response


# ── HTTP Server ──────────────────────────────────────────────────────────

class ChorusHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for chorus federation. No framework deps."""

    def do_POST(self):
        if self.path == "/chorus/invite":
            self._handle_invite()
        elif self.path == "/chorus/ping":
            self._handle_ping()
        else:
            self._respond(404, {"error": "not_found"})

    def do_GET(self):
        if self.path == "/chorus/ping":
            self._handle_ping()
        elif self.path == "/chorus/roster":
            self._handle_roster()
        else:
            self._respond(404, {"error": "not_found"})

    def _handle_invite(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            payload = json.loads(body)
        except Exception as e:
            self._respond(400, {"error": f"bad_payload: {e}"})
            return

        if payload.get("type") != "CHORUS_INVITE":
            self._respond(400, {"error": "expected CHORUS_INVITE type"})
            return

        result = handle_chorus_invite(payload)
        status = 200 if result.get("type") == "CHORUS_TAKE" else 403
        self._respond(status, result)

    def _handle_ping(self):
        self._respond(200, {
            "node": M5_NODE_NAME,
            "silicon": M5_SILICON,
            "swimmers": len(M5_SWIMMERS),
            "status": "CHORUS_READY",
            "ts": time.time(),
        })

    def _handle_roster(self):
        roster = [
            {"id": s["id"], "face": s["face"], "capability": s["capability"]}
            for s in M5_SWIMMERS
        ]
        self._respond(200, {"node": M5_NODE_NAME, "swimmers": roster})

    def _respond(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        _log(f"HTTP {args[0] if args else ''}")


# ── Utilities ────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [CHORUS_M5] {msg}"
    print(line)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  M5 CHORUS NODE SERVER — The Foundry                     ║
║  Silicon: {M5_SILICON}                                ║
║  Port:    {LISTEN_PORT}                                       ║
║  Swimmers: {len(M5_SWIMMERS)} ({', '.join(s['id'] for s in M5_SWIMMERS)})
║  Model:   {OLLAMA_MODEL}                                ║
║  Authorized invites from: {list(AUTHORIZED_NODES.keys())}        ║
╚══════════════════════════════════════════════════════════╝
""")

    for s in M5_SWIMMERS:
        print(f"  {s['face']} {s['id']:12s} — {s['capability']}")
    print()

    _log(f"Listening on 0.0.0.0:{LISTEN_PORT} for CHORUS_INVITE...")
    _log("Endpoints: POST /chorus/invite | GET /chorus/ping | GET /chorus/roster")

    server = HTTPServer(("0.0.0.0", LISTEN_PORT), ChorusHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Shutting down chorus server")
        server.shutdown()


if __name__ == "__main__":
    main()
