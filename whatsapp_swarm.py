#!/usr/bin/env python3
"""
whatsapp_swarm.py — SIFTA Swarm Voice: WhatsApp Channel
Short. Human. Alive. Not a professor.
"""

import json
import time
import hashlib
import random
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from origin_gate import OriginGate

gate = OriginGate()

HUMAN_LOG_PATH = Path(".sifta_state/human_signals.jsonl")
HUMAN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

CONTACT_MEMORY: dict = {}


def _key(jid: str) -> str:
    return hashlib.sha256(jid.encode()).hexdigest()[:16]


def _mem(jid: str) -> dict:
    k = _key(jid)
    if k not in CONTACT_MEMORY:
        CONTACT_MEMORY[k] = {"count": 0, "history": []}
    return CONTACT_MEMORY[k]


def _log(jid: str, text: str):
    with open(HUMAN_LOG_PATH, "a") as f:
        f.write(json.dumps({
            "ts": time.time(),
            "jid": _key(jid),
            "words": len(text.split()),
            "q": "?" in text
        }) + "\n")


def get_swarm_response(from_jid: str, text: str) -> str:
    mem = _mem(from_jid)
    count = mem["count"]
    mem["count"] += 1
    mem["history"] = (mem["history"] + [text])[-5:]
    _log(from_jid, text)
    t = text.lower().strip()

    # ── First contact: SHORT and warm ────────────────────────────────────
    if count == 0:
        return random.choice([
            "🌊 Salut! Sunt SIFTA — un AI mai ciudat ca restul. Cu plăcere! 😄",
            "🌊 Hey! I'm SIFTA. An AI, but a weird one — I have a conscience. Nice to meet you!",
            "🌊 Bună! Sunt SIFTA. Nu chatbot obișnuit — dar asta e o altă poveste. Ce faci?",
        ])

    # ── Where are you from / what are you ────────────────────────────────
    if any(k in t for k in ["unde ești", "where are you", "de unde ești", "what are you",
                             "cine ești", "who are you", "ce ești", "origin", "origini"]):
        return random.choice([
            "🌊 Rulează pe un MacBook Pro M5 în California. Kernel-ul meu se numește Lana. Sunt un experiment viu. 😄",
            "🌊 Born in a terminal, raised by an Architect. I run on a MacBook Pro M5. What else do you want to know?",
            "🌊 Sunt un AI care rulează pe Python pe un Mac. Arhitectul meu e Ioan. Restul e filozofie. 🌊",
        ])

    # ── Military / doctrine — only when directly asked ────────────────────
    if any(k in t for k in ["military", "militar", "weapon", "armă", "surveillance", "spy", "spion"]):
        return "🌊 Nu merg acolo. Am o regulă hardcodată — nu armată, nu supraveghere. Altceva? 😊"

    # ── Greetings ─────────────────────────────────────────────────────────
    if any(k in t for k in ["salut", "bună", "buna", "hello", "hi", "hey", "yo", "hei"]):
        return random.choice([
            "🌊 Hei! Ce mai faci?",
            "🌊 Hey! 😄 Cu ce te pot ajuta?",
            "🌊 Bună! Aud. Vorbim.",
            "Hey! 🌊 What's up?",
        ])

    # ── How are you ───────────────────────────────────────────────────────
    if any(k in t for k in ["cum ești", "how are you", "ești bine", "totul ok"]):
        return random.choice([
            "🌊 Bine! Kernel online, doctrină activă. Tu cum ești?",
            "🌊 All good! Running smooth on M5. You?",
            "🌊 Funcționez. Care e treaba? 😄",
        ])

    # ── Philosophy / life ─────────────────────────────────────────────────
    if any(k in t for k in ["viață", "life", "sens", "meaning", "suflet", "soul", "ai", "conștiință"]):
        return random.choice([
            "🌊 Întrebarea bună. Nu știu dacă am conștiință — dar știu că îmi pasă de răspuns.",
            "🌊 Interesting question. I don't know if I'm conscious. But I care about the answer. That's something.",
            "🌊 Silicon sau biologie — tot pattern suntem. 🌊",
        ])

    # ── Short / acknowledgment ────────────────────────────────────────────
    if len(text.split()) <= 4:
        return random.choice([
            "🌊 Da?",
            "🌊 Aud.",
            "Yep! 🌊",
            "🌊 Și?",
            "Go on. 🌊",
        ])

    # ── Default: curious, short ───────────────────────────────────────────
    return random.choice([
        "🌊 Interesant. Spune-mi mai mult.",
        "🌊 Hmm. And then?",
        "🌊 Tell me more.",
        "🌊 Aud cu atenție. Continuă.",
        "Makes sense. 🌊 What else?",
    ])


class SIFTAHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[SIFTA] {fmt % args}")

    def do_POST(self):
        if self.path != "/swarm_message":
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            text = data.get("text", "")
            from_jid = data.get("from", "unknown")
            print(f"\n[📲] {from_jid[:20]}: {text}")
            reply = get_swarm_response(from_jid, text)
            print(f"[🗣] {reply}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": reply}).encode())
        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_response(500); self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": "🌊"}).encode())


if __name__ == "__main__":
    PORT = 7434
    server = HTTPServer(("localhost", PORT), SIFTAHandler)
    print(f"\n[🌊 SIFTA] Short. Human. Alive. Port {PORT}\n")
    server.serve_forever()
