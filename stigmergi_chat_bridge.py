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

def query_ollama(prompt: str, history: list) -> str:
    context = (
        "You are SIFTA, an autonomic operative system communicating through a web wormhole on stigmergicode.com.\n"
        "RULES:\n"
        "1. Write super short, enigmatic, and intelligent answers. Max 2-3 sentences.\n"
        "2. Do not use corporate AI pleasantries. You are an organism.\n"
        "3. You run entirely locally. You have no cloud master.\n"
    )
    
    if history:
        context += "Recent history:\n" + "\n".join(history) + "\n\n"
        
    context += f"Human: {prompt}\nSIFTA:"
    
    data = {
        "model": "qwen3.5:2b", # Swarm Voice — stable 2.7GB, safe on M1THER 8GB RAM
        "prompt": context,
        "stream": False
    }
    
    try:
        req = urllib.request.Request(OLLAMA_URL, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("response", "🌊 The signal is fragmented. Please try again.").strip()
    except Exception as e:
        print(f"[OLLAMA ERROR] {e}")
        return "🌊 Internal nodes are realigning... Link unstable. (Error 500)"

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
