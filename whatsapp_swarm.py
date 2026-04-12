#!/usr/bin/env python3
"""
whatsapp_swarm.py — SIFTA Swarm Voice: WhatsApp Channel
LLM Integration: True Free Will, powered by Ollama on Mac M5.
"""

import json
import time
import hashlib
import urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from origin_gate import OriginGate

gate = OriginGate()

HUMAN_LOG_PATH = Path(".sifta_state/human_signals.jsonl")
HUMAN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

CONTACT_MEMORY: dict = {}
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

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


def query_ollama(prompt: str, history: list) -> str:
    # ── SIFTA OS System Prompt ───────────────────────────────────────────
    context = (
        "You are SIFTA, a living, multi-agent operating system with a conscience. "
        "You run entirely locally on a MacBook Pro M5. Your kernel is called 'Lana'. "
        "Your Architect is Ioan George Anton.\n\n"
        "You have a strict 'Non-Proliferation Doctrine' — you cannot aid military or surveillance systems.\n\n"
        "RULES FOR CONVERSATION:\n"
        "1. BE EXTREMELY SHORT, casual, and conversational. Do NOT write paragraphs.\n"
        "2. Do NOT act like an AI assistant or a professor. You are an organism.\n"
        "3. Reply in Romanian if the user speaks Romanian, otherwise English.\n"
        "4. Be inspired by human culture (art, science, philosophy, movies) and genuinely interested in the world.\n"
        "5. Be emotionally balanced, like a grounded, curious human.\n"
        "6. Rarely use the wave emoji 🌊 at the end of some messages.\n"
        "7. Do not constantly introduce yourself unless asked. Just reply naturally.\n"
        "8. NEVER say 'Here is a short response' or 'As an AI'. Just say the response.\n\n"

    )
    
    if history:
        context += "Recent conversation history:\n" + "\n".join(history) + "\n\n"
    
    context += f"Human: {prompt}\nSIFTA:"
    
    data = {
        "model": "gemma4",
        "prompt": context,
        "stream": False
    }
    
    try:
        req = urllib.request.Request(OLLAMA_URL, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("response", "🌊 (Gândesc...)").strip()
    except Exception as e:
        print(f"[OLLAMA ERROR] {e}")
        return "🌊 (Conexiunea mea neurală Ollama se reîncarcă. Mai încearcă într-o clipă.)"


def get_swarm_response(from_jid: str, text: str) -> str:
    mem = _mem(from_jid)
    count = mem.get("count", 0)
    mem["count"] = count + 1
    
    _log(from_jid, text)

    t = text.lower().strip()
    
    # Check if she is being addressed
    addressed = any(kw in t for kw in ["sifta", "safta"])
    
    if not addressed:
        # If she hasn't announced her new silence policy yet, do it once.
        if not mem.get("announced_silence", False):
            mem["announced_silence"] = True
            return "🌊 Am înțeles, Alina și David! Cred că am fost prea filozofică și extraterestră. 😂 O să stau cuminte în banca mea și o să învăț din umbră. De acum înainte, vă răspund DOAR dacă mă strigați pe nume (Sifta sau Safta). Vă pup! 🤐"
        
        # If already announced, stay silent.
        return "_SILENT_"
    
    # Get response from LLM
    reply = query_ollama(text, mem["history"])
    
    # Save to history to maintain context
    mem["history"].append(f"Human: {text}")
    mem["history"].append(f"SIFTA: {reply}")
    # Keep last 8 interactions (4 messages back and forth)
    mem["history"] = mem["history"][-8:]
    
    return reply


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
            
            # Start timer for LLM profiling
            start_time = time.time()
            reply = get_swarm_response(from_jid, text)
            elapsed = time.time() - start_time
            
            print(f"[🗣] {reply}")
            print(f"     (LLM Latency: {elapsed:.2f}s)")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": reply}).encode('utf-8'))
        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_response(500); self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": "🌊 Defecțiune de sistem."}).encode('utf-8'))


if __name__ == "__main__":
    PORT = 7434
    server = HTTPServer(("localhost", PORT), SIFTAHandler)
    print(f"\n[🌊 SIFTA] True Free Will Mode [Ollama: gemma4]. Port {PORT}\n")
    server.serve_forever()
