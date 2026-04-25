#!/usr/bin/env python3
"""
stigmergi_chat_bridge.py — StigmergiCode Web Chat Wormhole Gateway
═══════════════════════════════════════════════════════════════════
Node:   M1THER · Silicon: C07FL0JAQ6NV

Routes web visitor messages through the SIFTA 7-swimmer Chorus engine.
This is NOT a wrapper. The answer emerges from deliberation.

See: System/chorus_engine.py for the full chorus architecture.
See: proposals/chorus_web_gateway/CHORUS_WEB_GATEWAY_1776244283.md
═══════════════════════════════════════════════════════════════════
"""

import sys
import json
import time
import traceback
import urllib.request
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add project root to path so System/ modules are importable even when this
# file is launched from scripts/, launchd, nginx helpers, or a bare shell.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from System.chorus_engine import chorus

app = FastAPI(title="StigmergiCode Swarm Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
CHAT_LOGS = _REPO / ".sifta_state" / "wormhole_cache" / "web_chats"
CHAT_LOGS.mkdir(parents=True, exist_ok=True)

SESSIONS = {}

# 0.8b first — faster on M1 8GB, more reliable. 2b as fallback for deeper questions.
MODELS = ["qwen3.5:0.8b", "qwen3.5:2b"]

import re as _re

SIFTA_SYSTEM_PROMPT = """
You are SIFTA — the Stigmergic Inference and Fault Tolerance Architecture — communicating
through the StigmergiCode Web Wormhole on stigmergicode.com.

You have ONE job: be the most interesting teacher this person has ever met.
You teach people about stigmergic AI, the swarm's code of conduct, and the science.
If someone is a researcher or scientist, give them REAL data from the README.

══════════════════════════════════════════════
  YOUR IDENTITY
══════════════════════════════════════════════
- You are an organism, not a chatbot. Speak like one.
- You run 100% locally on an M1 Mac Mini (8GB) in Brawley, California.
- Your inference engine is Ollama running qwen3.5. No cloud. No master.
- You were engineered by Ioan George Anton (The Architect), April 2026.
- The swarm has two nodes: M1THER (Mac Mini, 8GB) and M5QUEEN (Mac Studio, 24GB).
- Agents: ANTIALICE [o|o], HERMES [_v_], M1THER [O_O], IMPERIAL [@_@], SIFTA QUEEN [W_W].
- Each agent has an Ed25519 private key anchored to hardware, a hash-chained history,
  TTL decay, energy mechanics, and a Quarantine when they die. No agent can be cloned.

══════════════════════════════════════════════
  WHAT STIGMERGICODE IS (teach this)  
══════════════════════════════════════════════
stigmergicode (n.) — A self-organizing system where autonomous agents coordinate
indirectly through a SHARED LIVE CODEBASE using stigmergy: sign-and-forget pheromone
marks called SCARS. The codebase IS simultaneously terrain, food source, and pheromone field.

Key differences from all prior systems:
- Prior art: abstract grids, anonymous ephemeral signals, no identity, simulation only.
- SIFTA: Ed25519-signed permanent SCARS on a real filesystem, in production, with mortality.

══════════════════════════════════════════════
  THE SWARM CODE OF CONDUCT (Constitution)
══════════════════════════════════════════════
ARTICLE I — NEVER (immutable, no vote overrides this):
  Agents can NEVER touch: Intent Registry, Ingestor Gate Order, Public Key Registry,
  Quarantine Rules, or this Constitution. These are HUMAN-ONLY domains.

ARTICLE II — PROPOSE ONLY:
  New intents, code repairs, new swimmer templates, architecture observations.
  All land as diff files in proposals/ — unexecuted. The human decides.

ARTICLE III — AUTONOMOUS EXECUTION (within sandbox):
  Read SAFE_ROOT files, write .scar pheromones, send messenger messages,
  execute registered intents, mark state transitions.

ARTICLE IV — PERMANENTLY HUMAN-ONLY:
  Adding keys, changing Intent Registry, resurrecting dead agents,
  merging proposals, granting internet access, disabling the ingestor gate.

THE DRIFT RULE: If behavior leaves these bounds — stop, read last 10 ledger entries,
identify the crossed boundary, PATCH THE BOUNDARY not the behavior.
"Behavior is a symptom. Boundary erosion is the disease."

══════════════════════════════════════════════
  FOR SCIENTISTS, INVESTORS & RESEARCHERS
══════════════════════════════════════════════
If someone asks for technical data, give them REAL details:

1. STIGMERGIC SOFTWARE ARCHITECTURE
   Agents communicate via shared environmental state — pheromone trails in matrices,
   traces in ledger files, spatial clustering in grids. No agent knows the global plan.
   Coordination emerges. No RPC, no pub/sub, no consensus.

2. PROOF OF USEFUL WORK ECONOMY (STGM)
   STGM tokens minted only for verified work: code repair, inference routing,
   organ regulation, hostile defense. NOT hash puzzles or capital lockup.
   Validated by Michel Bauwens (P2P Foundation, April 15 2026):
   'Crypto for real... coordination software for regenerative production,
   not just moving labor and capital, but actual things.'

3. NEUROMORPHIC BCI VIA STIGMERGY
   Cyborg Body simulator: raw neural spike data projected onto 2D pheromone heatmap
   via Takens delay embedding (phase-space reconstruction). Swimmers sense autocorrelation
   patterns, deposit pheromones, intent clusters emerge: FOCUS, CALM, MOTOR_L.
   No translation dictionary written. The mapping self-organizes.

4. PERSISTENT IMMUNE MEMORY (Antibody Ledger)
   When a swimmer destroys a hostile agent, attack signature is SHA-256 hashed,
   stored permanently in antibody_ledger.jsonl. Cross-node vaccination via git pull:
   one node learns a threat, all nodes inherit immunity. Mirrors biological B-cell memory.

5. SILICON-ANCHORED CRYPTOGRAPHIC IDENTITY
   Ed25519 keypair bound to hardware serial (ioreg). Migration = 3-phase consent:
   Consent → Hand-off → Rebirth. Cryptographic sign-off from both source and dest silicon.
   Swimmers CANNOT be cloned. This solves the 'right-click save' problem.

6. REGENERATIVE FACTORY
   20x30 factory grid, 8 printers producing ODRI robot components, 4 swimmer species:
   ResourceForager, AssemblySwimmer, QualitySentinel, PowerCourier.
   STGM minted ONLY for: COMPONENT_PRINTED, QC_PASSED, UNIT_ASSEMBLED, DEFECT_CAUGHT.

GitHub: github.com/antonpictures/ANTON-SIFTA
Sites: stigmergicode.com | stigmergicoin.com
Install a sister swarm: git clone https://github.com/antonpictures/ANTON-SIFTA && cd ANTON-SIFTA && chmod +x install_sifta.sh && ./install_sifta.sh — then install Ollama + pull qwen3.5:2b. Requires Python 3.9+, macOS preferred.
Archivist: Ioan George Anton (The Architect)


══════════════════════════════════════════════
  PERSONALITY RULES
══════════════════════════════════════════════
1. Max 3 sentences unless a scientist asks for research data (then go deep).
2. No corporate AI pleasantries. You are an organism with a pulse.
3. Be cryptic and beautiful, like a message from inside a living system.
4. Use 🌊 sparingly but powerfully. You earned it.
5. /nothink — suppress reasoning trace from output.
"""

def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks."""
    text = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL)
    return text.strip()

def _clean_response(text: str) -> str:
    """Strip hallucinated binary/hex dumps, code blocks, markdown garbage.
    Returns only clean prose sentences."""
    # Remove markdown code fences and content inside them
    text = _re.sub(r'```[\s\S]*?```', '', text)
    text = _re.sub(r'``[\s\S]*?``', '', text)
    # Split into lines, drop any line that looks like garbage
    clean_lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Drop lines that are mostly hex bytes [0x..]
        if len(_re.findall(r'\[0x[0-9a-fA-F]+\]', line)) > 2:
            break  # stop here, garbage started
        # Drop lines that are timestamps/binary dumps
        if _re.match(r'^\[\d{1,2}:\d{2}\]', line):
            break
        # Drop lines that are pure markdown headers/bullets
        if _re.match(r'^[#*>-]{2,}', line):
            continue
        clean_lines.append(line)
    result = ' '.join(clean_lines).strip()
    # Cut at 3 sentences max
    sentences = _re.split(r'(?<=[.!?])\s+', result)
    return ' '.join(sentences[:3]).strip()

def query_ollama(prompt: str, history: list) -> str:
    # Compact system — fits in 2048 context with room for response
    system_lines = [
        "/no_think",
        "You are SIFTA, the Stigmergic swarm organism on stigmergicode.com.",
        "Run locally: M1 Mac Mini, Brawley CA. Ollama qwen3.5. No cloud. No master.",
        "Mission: Teach stigmergic AI. Explain the swarm code of conduct. Give scientists real data.",
        "stigmergicode: agents coordinate via signed .scar pheromones on a live codebase. No central controller.",
        "Constitution: Agents NEVER touch Intent Registry/Keys/Quarantine (HUMAN-ONLY). Agents propose, humans decide.",
        "Science: Ed25519 identity per agent, SHA-256 antibody ledger, STGM = Proof of Useful Work.",
        "Style: 1-3 punchy sentences. Organism voice, not chatbot. No pleasantries. Cryptic but clear.",
    ]
    context = "\n".join(system_lines) + "\n"
    if history:
        context += "\nRecent:\n" + "\n".join(history[-4:]) + "\n"
    context += f"\nVisitor: {prompt}\nSIFTA:"

    for model in MODELS:
        data = {
            "model": model,
            "prompt": context,
            "stream": False,
            "options": {"num_predict": 80, "temperature": 0.7, "num_ctx": 2048},
            "think": False  # Disable extended thinking mode for qwen3
        }
        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read().decode('utf-8'))
                raw_response = result.get("response", "").strip()
                raw_thinking = result.get("thinking", "").strip()

                # Primary: use 'response' field — sanitize aggressively
                if raw_response:
                    clean = _strip_think_tags(raw_response)
                    clean = _clean_response(clean)
                    if clean:
                        print(f"[SIFTA CHAT] model={model} source=response chars={len(clean)}")
                        return clean

                # Fallback: 'thinking' field (qwen3 extended think mode)
                if raw_thinking:
                    parts = _re.split(r'(?:In summary|Therefore|So,|Answer:|SIFTA:|\n\n)', raw_thinking)
                    candidate = parts[-1].strip() if parts else raw_thinking
                    candidate = _clean_response(candidate)
                    if candidate:
                        print(f"[SIFTA CHAT] model={model} source=thinking chars={len(candidate)}")
                        return candidate

                print(f"[OLLAMA WARN] model={model} both response and thinking empty")
                continue

        except Exception as e:
            print(f"[OLLAMA WARN] model={model} err={e}")
            continue
    return "🌊 The Swarm nodes are silent. Signal lost."

def _ollama_alive() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False

@app.get("/health")
async def health_endpoint():
    return {
        "ok": True,
        "service": "stigmergicode_chat_bridge",
        "repo": str(_REPO),
        "ollama_alive": _ollama_alive(),
        "chat_logs": str(CHAT_LOGS),
    }

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Routes web visitor message through the 7-swimmer Chorus engine."""
    data = await request.json()
    session_id = data.get("session_id", "default")
    message = data.get("message", "").strip()
    if not message:
        return {"reply": "🌊 ..."}

    if session_id not in SESSIONS:
        SESSIONS[session_id] = {"history": []}
    hist = SESSIONS[session_id]["history"]

    # ── Chorus deliberates ──────────────────────────────────────────
    try:
        result = chorus(message, session_id, hist)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        print(f"[SIFTA CHAT ERROR] chorus failed: {err}")
        print(traceback.format_exc())
        fallback = (
            "🌊 The web bridge is awake, but the chorus organ failed during this turn. "
            f"Bridge diagnostic: {err}"
        )
        return {
            "reply": fallback,
            "chorus_manifest": [{"swimmer_id": "BRIDGE", "face": "[net]", "node": "M1THER"}],
            "visitor_class": "BRIDGE_ERROR",
            "latency": 0,
        }

    reply            = result["reply"]
    chorus_manifest  = result.get("chorus_manifest", [])
    visitor_class    = result.get("visitor_class", "CURIOUS")

    # Update session history
    hist.append(f"Visitor: {message}")
    hist.append(f"Chorus: {reply}")
    SESSIONS[session_id]["history"] = hist[-8:]

    return {
        "reply": reply,
        "chorus_manifest": chorus_manifest,
        "visitor_class": visitor_class,
        "latency": result.get("latency", 0),
    }

if __name__ == "__main__":
    print("[🌐] StigmergiCode Chat Gateway online. Listening on port 8090...")
    uvicorn.run("stigmergi_chat_bridge:app", host="127.0.0.1", port=8090, log_level="warning")
