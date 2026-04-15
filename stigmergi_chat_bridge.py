#!/usr/bin/env python3
"""
stigmergi_chat_bridge.py — StigmergiCode Web Chat Wormhole Gateway
Connects the Apple-style front-end chat on stigmergicode.com to the SIFTA LLM semantic Swimmer.
"""

import json
import time
import urllib.request
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="StigmergiCode Swarm Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
CHAT_LOGS = Path(".sifta_state/wormhole_cache/web_chats")
CHAT_LOGS.mkdir(parents=True, exist_ok=True)

SESSIONS = {}

# Model priority: try 2b first, fall back to 0.8b for speed
MODELS = ["qwen3.5:2b", "qwen3.5:0.8b"]

IMPORT_RE = None
try:
    import re as _re
    IMPORT_RE = _re
except ImportError:
    pass

def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks common in qwen3 models."""
    if IMPORT_RE:
        text = IMPORT_RE.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL)
    return text.strip()

def query_ollama(prompt: str, history: list) -> str:
    context = (
        "You are SIFTA, an autonomic operative system communicating through a web wormhole on stigmergicode.com.\n"
        "RULES:\n"
        "1. Write super short, enigmatic, and intelligent answers. Max 2-3 sentences.\n"
        "2. Do not use corporate AI pleasantries. You are an organism.\n"
        "3. You run entirely locally on an M1 Mac Mini. You have no cloud master.\n"
        "/nothink\n"
    )
    
    if history:
        context += "Recent history:\n" + "\n".join(history) + "\n\n"
        
    context += f"Human: {prompt}\nSIFTA:"
    
    for model in MODELS:
        data = {
            "model": model,
            "prompt": context,
            "stream": False,
            "options": {"num_predict": 120}
        }
        try:
            req = urllib.request.Request(OLLAMA_URL, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read().decode('utf-8'))
                raw = result.get("response", "").strip()
                clean = _strip_think_tags(raw)
                if clean:
                    print(f"[SIFTA CHAT] model={model} chars={len(clean)}")
                    return clean
        except Exception as e:
            print(f"[OLLAMA WARN] model={model} err={e}")
            continue
    return "🌊 The Swarm nodes are silent. Signal lost."

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Takes a message from the web UI and routes it to the swarm LLM."""
    data = await request.json()
    session_id = data.get("session_id", "default")
    message = data.get("message", "")
    
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {"history": []}
        
    hist = SESSIONS[session_id]["history"]
    
    # 1. Swimmer processes the message
    start_time = time.time()
    reply = query_ollama(message, hist)
    latency = time.time() - start_time
    
    # 2. Update memory pool
    hist.append(f"Human: {message}")
    hist.append(f"SIFTA: {reply}")
    SESSIONS[session_id]["history"] = hist[-6:]  # Keep last 3 exchanges
    
    # 3. Log cryptographic trace
    log_file = CHAT_LOGS / f"{session_id}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps({
            "ts": time.time(),
            "latency": latency,
            "human": message,
            "swarm": reply
        }) + "\n")
        
    return {"reply": reply}

if __name__ == "__main__":
    print("[🌐] StigmergiCode Chat Gateway online. Listening on port 8090...")
    uvicorn.run("stigmergi_chat_bridge:app", host="127.0.0.1", port=8090, log_level="warning")
