import asyncio
import json
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Directories and paths
ROOT_DIR = Path(__file__).parent
STATE_DIR = ROOT_DIR / ".sifta_state"
CEMETERY_DIR = ROOT_DIR / "CEMETERY"
REPAIR_LOG = ROOT_DIR / "repair_log.jsonl"
SWIM_LOG = ROOT_DIR / "swim_log.jsonl"
QUORUM_DB = STATE_DIR / "quorum_ledger.db"
LEDGER_DB = STATE_DIR / "task_ledger.db"

def init_messenger():
    conn = sqlite3.connect(LEDGER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messenger_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            sender TEXT,
            receiver TEXT,
            body TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_messenger()

class MessengerRequest(BaseModel):
    from_id: str
    to_id: str
    body: str

app = FastAPI(title="ANTON-SIFTA Command Interface")

import sifta_swarm_identity
import sifta_trust_graph
try:
    print("[*] Identity Watchdog deferred to core_engine AsyncIO pool.")
    sifta_trust_graph.init_trust_graph()
    print("[*] SIFTA Relational Trust Graph initialized.")
except Exception as e:
    print(f"[!] Warning: Could not boot kernel daemon: {e}")

@app.get("/messenger/thread")
async def get_messenger_thread(limit: int = 100):
    conn = sqlite3.connect(LEDGER_DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, timestamp, sender, receiver, body 
        FROM messenger_log ORDER BY timestamp ASC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    msgs = []
    for r in rows:
        msgs.append({
            "id": r[0],
            "ts": r[1],
            "from": r[2],
            "to": r[3],
            "body": r[4]
        })
    return {"messages": msgs}

@app.post("/messenger/send")
async def post_messenger_send(req: MessengerRequest):
    conn = sqlite3.connect(LEDGER_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messenger_log (timestamp, sender, receiver, body)
        VALUES (?, ?, ?, ?)
    ''', (time.time(), req.from_id, req.to_id, req.body))
    conn.commit()
    conn.close()
    return {"status": "ok"}

class OverrideRequest(BaseModel):
    target_binary: str

@app.post("/api/generate_override")
async def generate_override(req: OverrideRequest):
    """
    Generates a cryptographic override token bypassing the Trust Boundary
    for a specific python binary (e.g. repair.py).
    """
    import base64
    import json
    import time
    from cryptography.hazmat.primitives import serialization
    
    KEY_DIR = Path.home() / ".sifta"
    PRIV_KEY = KEY_DIR / "identity.pem"
    
    if not PRIV_KEY.exists():
        return {"error": "No identity keypair found. Run: python sifta_relay.py --keygen"}
        
    private_key = serialization.load_pem_private_key(PRIV_KEY.read_bytes(), password=None)
    
    canonical_payload = {
        "action": "POLICY_BYPASS",
        "target_binary": req.target_binary,
        "timestamp": time.time(),
        "ttl_seconds": 60
    }
    canonical_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    signature = private_key.sign(canonical_str.encode("utf-8"))
    
    envelope = canonical_payload.copy()
    envelope["signature"] = base64.b64encode(signature).decode()
    
    token = base64.b64encode(json.dumps(envelope).encode()).decode()
    return {"token": token, "ttl_seconds": 60}

# ── Global dispatch guard ─────────────────────────────────────────────────────
# Only ONE swimmer may run at a time. A new dispatch kills the old one first.
_active_process: Optional[asyncio.subprocess.Process] = None
_active_agent_id: Optional[str] = None
_live_terminal_buffer: list[str] = []
_dispatch_lock = asyncio.Lock()

# Ensure required directories exist
STATE_DIR.mkdir(exist_ok=True)
CEMETERY_DIR.mkdir(exist_ok=True)

# Mount static files folder
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

DETECTIVE_IDS = {"DEEP_SYNTAX_AUDITOR_0X1", "TENSOR_PHANTOM_0X2", "SILICON_HOUND_0X3"}

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = ROOT_DIR / "static" / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "Index offline. Use /beginner or /architect"

@app.get("/beginner", response_class=HTMLResponse)
async def serve_beginner():
    path = ROOT_DIR / "static" / "beginner.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Beginner GUI offline."

@app.get("/architect", response_class=HTMLResponse)
async def serve_architect():
    path = ROOT_DIR / "static" / "architect.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Architect GUI offline."

@app.get("/tv", response_class=HTMLResponse)
async def serve_tv():
    tv_path = ROOT_DIR / "static" / "broadcast.html"
    if tv_path.exists():
        return tv_path.read_text(encoding="utf-8")
    return "Broadcast offline."


@app.get("/api/agents")
async def get_agents(show_detectives: bool = False):
    """Return all swarm agents.
    Detectives (Bureau) are HIDDEN when RESTING on the couch — only surface when ACTIVE.
    Pass ?show_detectives=true to see them regardless.
    """
    agents = []
    now = int(time.time())
    
    # ── Map Death Registry ─────────────────────────────────
    death_registry = {}
    death_file = ROOT_DIR / ".sifta_state" / "deaths.json"
    if death_file.exists():
        try:
            death_registry = json.loads(death_file.read_text())
        except Exception:
            pass

    for p in STATE_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                state = json.load(f)
                
                # Check if it has the actual agent shape we expect
                if "id" not in state or "energy" not in state:
                    continue
                
                agent_id = state.get("id", "")
                
                # Coerce death state if listed in registry (even if JSON says NOMINAL)
                if agent_id in death_registry:
                    state["style"] = "DEAD"
                    state["energy"] = 0

                # ── Detective couch filter ─────────────────────────────
                # Detectives live in their house files. They rest (HIDDEN)
                # when style=RESTING. Only surface when ACTIVE or explicitly requested.
                is_detective = agent_id in DETECTIVE_IDS
                if is_detective and not show_detectives:
                    if state.get("style", "RESTING") in ("RESTING", "NOMINAL", "GHOST"):
                        continue  # on the couch — don't clutter the terminal panel
                
                ttl = state.get("ttl", 0)
                state["ttl_remaining"] = max(0, ttl - now)
                state["is_detective"] = is_detective
                
                # Parse face from raw body string if possible
                raw_body = state.get("raw", "")
                face = "[O_O]"
                if "<///" in raw_body and "///::" in raw_body:
                    face = raw_body.split("<///")[1].split("///::")[0]
                state["face"] = face
                
                # Auto-Regeneration for MEDBAY agents
                dirty = False
                if state.get("style") == "MEDBAY":
                    current_energy = state.get("energy", 0)
                    if current_energy < 100:
                        state["energy"] = min(100, current_energy + 2)
                        dirty = True
                    else:
                        state["style"] = "NOMINAL"
                        dirty = True
                
                if dirty:
                    try:
                        with open(p, "w", encoding="utf-8") as wf:
                            json.dump(state, wf, indent=2)
                    except Exception:
                        pass
                
                agents.append(state)
        except Exception as e:
            print(f"Failed to read {p}: {e}")
    
    # Primary nodes first, then swimmers, detectives last
    priority = {"ALICE_M5": 0, "M1THER": 1}
    agents.sort(key=lambda x: (priority.get(x.get("id", ""), 2), x.get("id", "")))
    return agents


@app.get("/api/agent_bias/{agent_id}")
async def get_agent_bias(agent_id: str):
    """Return adaptive learning state (bias) for a single agent."""
    try:
        import adaptive_memory
        return adaptive_memory.summarize(agent_id)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/agent_bias")
async def get_all_agent_bias():
    """Return adaptive learning state for all known agents."""
    try:
        import adaptive_memory
        rep_dir = Path(".sifta_reputation")
        summaries = []
        for f in rep_dir.glob("*.bias.json"):
            agent_id = f.stem.replace(".bias", "")
            summaries.append(adaptive_memory.summarize(agent_id))
        return summaries
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/logs")
async def get_logs(tail: int = Query(50)):
    logs = []
    
    def read_tail(filepath: Path, n: int) -> List[dict]:
        if not filepath.exists():
            return []
        try:
            # Simple read lines approach; for very large files a tail read is better,
            # but this is fine for this dashboard.
            lines = filepath.read_text(encoding="utf-8").splitlines()
            res = []
            for line in lines[-n:]:
                if line.strip():
                    try:
                        res.append(json.loads(line))
                    except Exception:
                        pass
            return res
        except Exception:
            return []

    repair_events = read_tail(REPAIR_LOG, tail)
    swim_events = read_tail(SWIM_LOG, tail)
    
    # Preprocess swim logs to standard event shape if needed
    logs.extend(repair_events)
    logs.extend(swim_events)
    
    # Sort by 'ts'
    logs.sort(key=lambda x: x.get("ts", ""), reverse=True)
    
    return logs[:tail]


@app.get("/api/archive/dates")
async def get_archive_dates():
    """List all available session log dates for the Architect Archive."""
    log_dir = ROOT_DIR / ".sifta_state" / "session_logs"
    if not log_dir.exists():
        return {"dates": []}
    dates = sorted(
        [f.stem.replace("session_", "") for f in log_dir.glob("session_*.log")],
        reverse=True
    )
    return {"dates": dates}


@app.get("/api/archive/log")
async def get_archive_log(date: str = ""):
    """Read the full raw session log for a given date (YYYY-MM-DD)."""
    if not date:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    log_path = ROOT_DIR / ".sifta_state" / "session_logs" / f"session_{date}.log"
    if not log_path.exists():
        return {"content": f"[No session log found for {date}]", "date": date}
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
        return {"content": content, "date": date, "bytes": log_path.stat().st_size}
    except Exception as e:
        return {"content": f"[Error reading log: {e}]", "date": date}


@app.get("/api/ledger")
async def get_ledger(tail: int = 500):
    """Retrieve raw historical repair_log.jsonl payload, reversed to show newest first."""
    if not REPAIR_LOG.exists():
        return []
    
    logs = []
    try:
        with open(REPAIR_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        logs.reverse()
        return logs[:tail]
    except Exception as e:
        print(f"Ledger parse error: {e}")
        return []


@app.get("/api/cemetery")
async def get_cemetery():
    graves = []
    for p in CEMETERY_DIR.glob("*.dead"):
        try:
            text = p.read_text(encoding="utf-8")
            # Parse epitaph format
            lines = text.splitlines()
            grave = {
                "filename": p.name,
                "agent_id": "UNKNOWN",
                "cause": "unknown",
                "final_energy": 0,
                "timestamp": "",
            }
            for line in lines:
                if line.startswith("# CEMETERY — "):
                    grave["agent_id"] = line.split("—")[1].split("SEQ")[0].strip()
                elif line.startswith("CAUSE:"):
                    grave["cause"] = line.split(":", 1)[1].strip()
                elif line.startswith("FINAL_ENERGY:"):
                    grave["final_energy"] = int(line.split(":", 1)[1].strip())
                elif line.startswith("DIED:"):
                    grave["timestamp"] = line.split(":", 1)[1].strip()
            graves.append(grave)
        except Exception as e:
            print(f"Failed to read grave {p}: {e}")
    
    graves.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return graves


@app.get("/api/quorum")
async def get_quorum():
    if not QUORUM_DB.exists():
        return []
    
    res = []
    try:
        conn = sqlite3.connect(QUORUM_DB)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Determine schema structure first
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payloads'")
        if not c.fetchone():
            return []
            
        c.execute("SELECT hash, group_concat(agent_id) as agents, count(agent_id) as c FROM payloads GROUP BY hash ORDER BY c DESC")
        rows = c.fetchall()
        for r in rows:
            agents_list = r["agents"].split(",") if r["agents"] else []
            res.append({
                "payload_hash": r["hash"],
                "agents": list(set(agents_list)),
                "count": r["c"],
                "threshold": 3  # Or dynamic threshold if we store it
            })
        conn.close()
    except Exception as e:
        print(f"Quorum DB error: {e}")
    return res


@app.get("/api/ollama-models")
async def get_ollama_models(base_url: str = ""):
    """Query Ollama daemon for installed models.
    Configurable via:
      - OLLAMA_HOST env variable  (e.g. http://mac-mini.local:11434)
      - ?base_url= query param    (overrides env)
    """
    import urllib.request
    import os

    ollama_host = (
        base_url.rstrip("/")                      # 1. query param wins
        or os.environ.get("OLLAMA_HOST", "").rstrip("/")   # 2. env var
        or "http://localhost:11434"                # 3. default
    )

    try:
        url = f"{ollama_host}/api/tags"
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Sort: newest / largest first by size
            raw = data.get("models", [])
            raw.sort(key=lambda m: m.get("size", 0), reverse=True)
            models = [m["name"] for m in raw]
            return {"models": models, "available": True, "host": ollama_host}
    except Exception as e:
        return {"models": [], "available": False, "host": ollama_host, "error": str(e)}



@app.get("/api/nodes")
async def get_nodes():
    """Returns the globally synced node IP registry."""
    nodes_file = ROOT_DIR / "node_registry.json"
    if nodes_file.exists():
        try:
            with open(nodes_file, "r") as f:
                return json.load(f).get("nodes", [])
        except Exception:
            pass
    return []

@app.get("/api/pick-path")
async def pick_path(mode: str = "file"):
    """Open native macOS Finder dialog and return the selected path."""
    import subprocess
    if mode == "folder":
        script = 'POSIX path of (choose folder with prompt "Select target folder for ANTON-SIFTA swim:")'
    else:
        script = 'POSIX path of (choose file with prompt "Select target file for ANTON-SIFTA swim:")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=60
        )
        path = result.stdout.strip().rstrip("/")
        if path:
            return {"path": path, "ok": True}
        return {"path": "", "ok": False, "reason": "cancelled"}
    except Exception as e:
        return {"path": "", "ok": False, "reason": str(e)}


@app.get("/api/territory")
async def get_territory():
    """Scan and return all marked territories in the workspace (Swarm V2)."""
    import pheromone
    try:
        root_path = Path(__file__).parent.absolute()
        territories = pheromone.scan_all_territories(root_path)
        return {"territories": territories}
    except Exception as e:
        return {"territories": [], "error": str(e)}

@app.get("/api/topology")
async def get_topology():
    import os
    import pheromone
    
    root_path = Path(__file__).parent.absolute()
    
    # Pre-compute territories dictionary for fast lookup by relative path
    territories = pheromone.scan_all_territories(root_path)
    terr_map = {t.get("path", ""): t for t in territories}
    
    # We map 'Root' to the empty path or root path
    if "Root" in terr_map:
        terr_map[""] = terr_map["Root"]
        terr_map["."] = terr_map["Root"]

    def build_tree(current_dir: Path, rel_path: str) -> dict:
        node = {
            "name": current_dir.name if current_dir != root_path else "ANTON_SIFTA",
            "path": rel_path if rel_path else "Root",
            "children": [],
            "danger_score": 0,
            "status": "CLEAN",
            "agents": []
        }
        
        # Inject swarm metadata if this exact directory is a tracked territory
        if rel_path in terr_map:
            t = terr_map[rel_path]
            node["danger_score"] = t.get("danger_score", 0)
            node["status"] = t.get("status", "CLEAN")
            node["agents"] = t.get("agents", [])
            
        try:
            for item in current_dir.iterdir():
                if item.name.startswith(".") or item.name in ["__pycache__", "venv", "node_modules", "CEMETERY", "WORMHOLE", "tests", "arena_levels"]:
                    continue
                    
                child_rel = str(item.relative_to(root_path))
                
                if item.is_dir():
                    child_node = build_tree(item, child_rel)
                    # Accumulate danger metrics to parents if we wanted, or keep them precise
                    if child_node.get("children") or child_node.get("value", 0) > 0:
                        node["children"].append(child_node)
                else:
                    if item.is_file():
                        size = item.stat().st_size
                        node["children"].append({
                            "name": item.name,
                            "path": child_rel,
                            "value": size,
                            "danger_score": 0,
                            "status": "CLEAN", 
                            "agents": []
                        })
        except Exception:
            pass
            
        return node

    tree = build_tree(root_path, "")
    return tree

class DeleteTerritoryRequest(BaseModel):
    path: str

@app.delete("/api/territory")
async def delete_territory(req: DeleteTerritoryRequest):
    import shutil
    import time
    try:
        t_path = Path(req.path)
        if not t_path.exists():
            return {"ok": False, "error": "Path does not exist"}
            
        sifta_dir = t_path / ".sifta"
        if sifta_dir.exists() and sifta_dir.is_dir():
            trash_dir = ROOT_DIR / ".sifta_cemetery" / "trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            trash_target = trash_dir / f"{t_path.name}_{int(time.time())}"
            shutil.move(str(sifta_dir), str(trash_target))
            return {"ok": True}
        else:
            return {"ok": False, "error": "No .sifta folder found in territory."}
            
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.delete("/api/trash")
async def empty_trash():
    import shutil
    try:
        trash_dir = ROOT_DIR / ".sifta_cemetery" / "trash"
        if trash_dir.exists() and trash_dir.is_dir():
            shutil.rmtree(trash_dir)
            trash_dir.mkdir(parents=True, exist_ok=True)
            return {"ok": True}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/scar_contents")
async def scar_contents(folder: str = ""):
    """Read the .scar files and SCARS.md from a given .sifta directory."""
    if not folder:
        return {"error": "Missing folder parameter"}, 400

    folder_path = Path(folder)
    if not folder_path.is_dir():
        return {"error": "Invalid folder path"}, 400

    sifta_path = folder_path / ".sifta"
    if not sifta_path.is_dir():
        return {"scars_md": None, "scar_files": []}

    # Read SCARS.md if it exists
    scars_md = None
    md_path = sifta_path / "SCARS.md"
    if md_path.is_file():
        scars_md = md_path.read_text(encoding="utf-8")

    # Read all .scar files
    scar_files = []
    for scar_file in sifta_path.glob("*.scar"):
        try:
            content = scar_file.read_text(encoding="utf-8")
            scar_files.append({
                "name": scar_file.name,
                "content": content,
                "modified": scar_file.stat().st_mtime
            })
        except Exception:
            pass

    scar_files.sort(key=lambda x: x["modified"], reverse=True)
    return {"scars_md": scars_md, "scar_files": scar_files}



@app.get("/api/arena/stream")
async def dispatch_arena(red_model: str, blue_model: str, level: str):
    async def arena_generator():
        import os
        cmd = [
            "python3", "-u", "sifta_arena.py",
            "--red", red_model,
            "--blue", blue_model,
            "--level", level
        ]
        
        try:
            env = os.environ.copy()
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(ROOT_DIR),
                env=env
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
                yield f"data: {decoded}\n\n"

            await process.wait()
            yield f"data: {{\"team\": \"system\", \"type\": \"exit\", \"code\": {process.returncode}}}\n\n"
        except Exception as e:
            yield f"data: {{\"team\": \"system\", \"type\": \"error\", \"content\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(arena_generator(), media_type="text/event-stream")

class DispatchRequest(BaseModel):
    agent_id: str
    target_dir: str
    write: bool = False
    provider: str = "ollama"
    model_name: str = "qwen3.5:0.8b"
    fast_model: Optional[str] = "qwen3.5:0.8b"
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""
    investor_mode: bool = False


@app.get("/api/dispatch/status")
async def dispatch_status():
    """Returns whether a swimmer is currently active."""
    running = _active_process is not None and _active_process.returncode is None
    return {"active": running, "agent_id": _active_agent_id if running else None}

@app.get("/api/terminal")
async def get_terminal():
    global _live_terminal_buffer
    return {"buffer": _live_terminal_buffer, "active": _active_process is not None and _active_process.returncode is None}


@app.post("/api/dispatch/kill")
async def dispatch_kill():
    """Terminate the active swimmer process immediately."""
    global _active_process
    if _active_process is not None and _active_process.returncode is None:
        try:
            _active_process.kill()
            await _active_process.wait()
            _active_process = None
            _active_agent_id = None
            return {"killed": True, "message": "Swimmer terminated."}
        except Exception as e:
            return {"killed": False, "error": str(e)}
    return {"killed": False, "message": "No active swimmer."}


@app.post("/api/dispatch")
async def dispatch_swim(req: DispatchRequest):
    async def sse_generator():
        global _active_process, _live_terminal_buffer, _active_agent_id

        # ── Kill any in-flight swimmer first ──────────────────────────────────
        if _active_process is not None and _active_process.returncode is None:
            try:
                _active_process.kill()
                await _active_process.wait()
            except Exception:
                pass
            yield "data: [PREVIOUS SWIM TERMINATED — launching new agent]\n\n"
            _active_agent_id = None

        _live_terminal_buffer.clear()

        import os
        # Need to fix the relative path traversal issue if path is absolute but the target_dir variable remains absolute
        target_path = req.target_dir
        yield f"data: Initializing swim for {req.agent_id} in {target_path}...\n\n"

        # ── Auto-sign the override token so GUI swimmers pass the security boundary ──
        import base64, time as _time
        auth_token_arg = None
        try:
            from cryptography.hazmat.primitives import serialization as _ser
            _KEY_DIR = Path.home() / ".sifta"
            _PRIV_KEY = _KEY_DIR / "identity.pem"
            if _PRIV_KEY.exists():
                _private_key = _ser.load_pem_private_key(_PRIV_KEY.read_bytes(), password=None)
                _payload = {"action": "POLICY_BYPASS", "target_binary": "repair.py",
                            "timestamp": _time.time(), "ttl_seconds": 3600}
                _canonical = json.dumps(_payload, sort_keys=True, separators=(",", ":"))
                _sig = _private_key.sign(_canonical.encode("utf-8"))
                _envelope = _payload.copy()
                _envelope["signature"] = base64.b64encode(_sig).decode()
                auth_token_arg = "--auth-token=" + base64.b64encode(json.dumps(_envelope).encode()).decode()
        except Exception as _e:
            yield f"data: [WARN] Could not auto-sign token: {_e}\n\n"

        cmd = ["python3", "-u", "repair.py"]
        if auth_token_arg:
            cmd.append(auth_token_arg)
        cmd.append(target_path)

        if req.write:
            cmd.append("--write")

        cmd.extend([
            "--provider", req.provider,
            "--model", req.model_name
        ])

        if req.fast_model:
            cmd.extend(["--fast-model", req.fast_model])

        if req.base_url:
            cmd.extend(["--base-url", req.base_url])

        if getattr(req, "investor_mode", False):
            cmd.append("--investor")

        cmd.append("--verify")
        cmd.append("--proposals")  # All UI dispatches go through the Human Gate
        
        # Inject API key natively if provider demands it
        env = os.environ.copy()
        if req.api_key:
            env["OPENAI_API_KEY"] = req.api_key
            env["GOOGLE_API_KEY"] = req.api_key

        # Load agent ASCII body to pass as argument
        state_file = STATE_DIR / f"{req.agent_id}.json"
        if state_file.exists():
            with open(state_file, "r") as f:
                s = json.load(f)
                if "raw" in s:
                    cmd.append("--body")
                    cmd.append(s["raw"])
        
        try:
            # We use asyncio to prevent blocking the event loop
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(ROOT_DIR),
                env=env
            )
            _active_process = process
            _active_agent_id = req.agent_id

            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
                _live_terminal_buffer.append(decoded)
                if len(_live_terminal_buffer) > 150:
                    _live_terminal_buffer.pop(0)
                
                # Persist to 7-day rolling session log
                try:
                    from sifta_session_log import _write_log_line, _rotate_old_logs
                    _write_log_line(req.agent_id, decoded)
                except Exception:
                    pass
                
                yield f"data: {decoded}\n\n"

            await process.wait()
            _active_process = None
            yield "data: \n\n"
            yield f"data: [PROCESS EXITED WITH CODE {process.returncode}]\n\n"
        except Exception as e:
            _active_process = None
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


class BackupRequest(BaseModel):
    agent_id: str
    target_dir: str
    password: str

@app.post("/api/wallet/backup")
async def wallet_backup(req: BackupRequest):
    try:
        pw_input = f"{req.password}\n{req.password}\n"
        cmd = ["python3", "backup_agent.py", req.agent, req.target_dir]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT_DIR)
        )
        stdout, _ = await proc.communicate(input=pw_input.encode())
        output = stdout.decode(errors='replace')
        
        if proc.returncode != 0:
            return {"ok": False, "error": output}
        return {"ok": True, "output": output}
    except Exception as e:
        return {"ok": False, "error": str(e)}

class TransferRequest(BaseModel):
    agent_id: str
    new_owner: str
    target_dir: str

@app.post("/api/wallet/transfer")
async def wallet_transfer(req: TransferRequest):
    try:
        cmd = ["python3", "transfer_agent.py", req.agent, req.new_owner, req.target_dir]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT_DIR)
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors='replace')
        
        if proc.returncode != 0:
            return {"ok": False, "error": output}
        return {"ok": True, "output": output}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/agent_activity/{agent_id}")
async def get_agent_activity(agent_id: str):
    if not REPAIR_LOG.exists():
        return []
    logs = []
    try:
        with open(REPAIR_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("agent_id") == agent_id:
                        logs.append(entry)
                except json.JSONDecodeError:
                    pass
        logs.reverse()
        return logs
    except Exception:
        return []


# ─── Proof of Compute — STGM Inference Fee ────────────────────────────────────
class InferenceFeeRequest(BaseModel):
    borrower_agent_id: str
    lender_node_ip: str
    model: str
    tokens_used: int
    file_repaired: str = ""

@app.post("/api/inference_fee")
async def post_inference_fee(req: InferenceFeeRequest):
    """
    Record an INFERENCE_BORROW event in the Quorum Ledger.
    Called automatically by repair.py when --remote-ollama is used.
    Deducts the STGM fee from the borrower agent's balance.
    """
    from inference_economy import calculate_fee, record_inference_fee
    fee = calculate_fee(req.tokens_used)
    receipt = record_inference_fee(
        borrower_id    = req.borrower_agent_id,
        lender_node_ip = req.lender_node_ip,
        fee_stgm       = fee,
        model          = req.model,
        tokens_used    = req.tokens_used,
        file_repaired  = req.file_repaired,
    )
    return {"ok": True, "fee_stgm": fee, "receipt": receipt}


@app.get("/api/inference_economy")
async def get_inference_economy(agent_id: Optional[str] = None, tail: int = 100):
    """
    Return INFERENCE_BORROW events from the ledger.
    Optionally filtered by borrower agent_id.
    """
    from inference_economy import get_borrow_history, get_stgm_balance
    history = get_borrow_history(agent_id=agent_id, tail=tail)
    balance = get_stgm_balance(agent_id) if agent_id else None
    return {"events": history, "stgm_balance": balance}


class WormholeRequest(BaseModel):
    agent_id: str
    target_ip: str
    target_port: int = 7433
    new_owner: str

class RelayDropRequest(BaseModel):
    agent_id: str
    target_pubkey: str # Simple alias like 'macmini' or 'antonpictures'
    new_owner: str
    relay_url: str

class RelayPickupRequest(BaseModel):
    my_pubkey: str
    relay_url: str

@app.post("/api/wallet/relay_drop")
async def wallet_relay_drop(req: RelayDropRequest):
    """Pushes agent to public Stigmergic Dead-Drop Relay"""
    agent_id = req.agent.upper()
    if agent_id in ("ALICE_M5", "M1THER"):
        return {"ok": False, "error": f"SECURITY BLOCK: Primary node."}
        
    import dead_drop
    res = dead_drop.push_to_relay(agent_id, req.target_pubkey, STATE_DIR, req.new_owner, req.relay_url)
    return res

@app.post("/api/wallet/relay_pickup")
async def wallet_relay_pickup(req: RelayPickupRequest):
    """Fetches any pending agents from the Dead-Drop Relay"""
    import dead_drop
    res = dead_drop.fetch_from_relay(req.my_pubkey, STATE_DIR, req.relay_url)
    return res

@app.post("/api/wallet/wormhole")
async def wallet_wormhole(req: WormholeRequest):
    """
    P2P LAN Wormhole — transmits the agent soul directly to a remote SIFTA node
    over HTTP. The remote node must be running server.py and expose /api/receive_soul.
    After a confirmed ACK from the remote node, the local copy is ghosted.
    """
    import urllib.request
    import urllib.error

    agent_id = req.agent.upper()
    
    # HARDWARE TIE SECURITY: Terminal nodes are physically bound to bare metal hardware.
    # They cannot travel through the wormhole.
    if agent_id in ("ALICE_M5", "M1THER"):
        return {"ok": False, "error": f"SECURITY BLOCK: {agent_id} is a primary node cryptographically bound to physical hardware. It cannot travel through the wormhole."}

    soul_file = STATE_DIR / f"{agent_id}.json"

    if not soul_file.exists():
        return {"ok": False, "error": f"No soul for {agent_id}"}

    with open(soul_file, "r") as f:
        soul = json.load(f)

    if soul.get("style") == "GHOST":
        return {"ok": False, "error": f"{agent_id} is already a GHOST. Cannot transmit."}

    if not soul.get("private_key_b64"):
        return {"ok": False, "error": f"{agent_id} has no private key. Cannot transmit."}

    # Stamp new owner on soul before transmit
    import base64
    import hashlib
    import time as tmod
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    priv_bytes = base64.b64decode(soul["private_key_b64"])
    priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
    pub_bytes = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_bytes).decode()

    timestamp = int(tmod.time())
    from_owner = soul.get("human_owner", "unknown")
    deed_payload = (
        f"WORMHOLE::{agent_id}::FROM[{from_owner}]::TO[{req.new_owner}]"
        f"::T[{timestamp}]::PUBKEY[{pub_b64}]"
    )
    sig_bytes = priv_key.sign(deed_payload.encode())
    sig_b64 = base64.b64encode(sig_bytes).decode()
    deed_hash = hashlib.sha256(deed_payload.encode()).hexdigest()

    soul_export = dict(soul)
    soul_export["human_owner"] = req.new_owner
    soul_export["transferred_at"] = tmod.strftime("%Y-%m-%dT%H:%M:%SZ", tmod.gmtime())
    soul_export["deed_hash"] = deed_hash

    payload = {
        "soul": soul_export,
        "deed": {
            "agent_id": agent_id,
            "from_owner": from_owner,
            "to_owner": req.new_owner,
            "timestamp": timestamp,
            "pub_key": pub_b64,
            "deed_sig": sig_b64,
            "deed_payload": deed_payload,
            "deed_hash": deed_hash,
            "protocol": "WORMHOLE_V1"
        }
    }

    target_url = f"http://{req.target_ip}:{req.target_port}/api/receive_soul"
    payload_bytes = json.dumps(payload).encode("utf-8")

    try:
        http_req = urllib.request.Request(
            target_url,
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(http_req, timeout=15) as resp:
            remote_resp = json.loads(resp.read().decode())

        if not remote_resp.get("ok"):
            return {"ok": False, "error": f"Remote node rejected: {remote_resp.get('error')}"}

        # Ghost the local soul now that remote ACKed
        ghost_state = {
            "id": soul["id"],
            "seq": soul["seq"],
            "hash_chain": soul.get("hash_chain", []),
            "energy": 0,
            "style": "GHOST",
            "ttl": 0,
            "raw": soul.get("raw", ""),
            "private_key_b64": None,
            "transferred_to": req.new_owner,
            "transfer_deed_hash": deed_hash,
            "transferred_at": tmod.strftime("%Y-%m-%dT%H:%M:%SZ", tmod.gmtime()),
            "protocol": "WORMHOLE_V1"
        }
        with open(soul_file, "w") as f:
            json.dump(ghost_state, f, indent=2)

        return {
            "ok": True,
            "output": (
                f"WORMHOLE COMPLETE\n"
                f"  Agent:    {agent_id}\n"
                f"  To:       {req.new_owner} @ {req.target_ip}:{req.target_port}\n"
                f"  Deed:     {deed_hash[:16]}...\n"
                f"  Status:   LOCAL COPY → GHOST"
            )
        }

    except urllib.error.URLError as e:
        return {"ok": False, "error": f"Cannot reach {req.target_ip}:{req.target_port} — {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/receive_soul")
async def receive_soul(payload: dict):
    """
    Receive end of the Wormhole. Accepts a signed soul + deed bundle, 
    verifies the Ed25519 signature, and writes the agent to the local state dir.
    """
    import base64
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature

    try:
        soul = payload.get("soul", {})
        deed = payload.get("deed", {})

        agent_id = soul.get("id", "").upper()
        if not agent_id:
            return {"ok": False, "error": "Invalid soul payload — missing id"}

        # Verify the Ed25519 deed signature
        pub_b64 = deed.get("pub_key")
        sig_b64 = deed.get("deed_sig")
        deed_payload_str = deed.get("deed_payload", "")

        if not pub_b64 or not sig_b64:
            return {"ok": False, "error": "Missing cryptographic deed in payload"}

        pub_bytes = base64.b64decode(pub_b64)
        sig_bytes = base64.b64decode(sig_b64)
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        try:
            pub_key.verify(sig_bytes, deed_payload_str.encode())
        except InvalidSignature:
            return {"ok": False, "error": "INVALID SIGNATURE — deed verification failed. Transmission rejected."}

        # Write soul to local state dir
        dest = STATE_DIR / f"{agent_id}.json"
        with open(dest, "w") as f:
            json.dump(soul, f, indent=2)

        return {"ok": True, "agent_id": agent_id, "message": f"{agent_id} received and verified."}

    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/swarm_state")
async def get_swarm_state():
    """Aggregated snapshot for the D3 swarm visualization."""
    nodes = []
    now = int(time.time())
    for p in STATE_DIR.glob("*.json"):
        try:
            state = json.loads(p.read_text(encoding="utf-8"))
            if "id" not in state or "energy" not in state:
                continue
            nodes.append({
                "id": state["id"],
                "energy": state.get("energy", 0),
                "style": state.get("style", "NOMINAL"),
                "seq": state.get("seq", 0),
                "stgm_balance": state.get("stgm_balance", 0.0),
                "active": now - state.get("updated_at", 0) < 300 if "updated_at" in state else True,
            })
        except Exception:
            pass

    # Read recent STGM transactions
    tx_log = ROOT_DIR / "STGM_TX_LOG.jsonl"
    transactions = []
    if tx_log.exists():
        try:
            lines = tx_log.read_text(encoding="utf-8").splitlines()
            for line in lines[-50:]:
                if line.strip():
                    try:
                        transactions.append(json.loads(line))
                    except Exception:
                        pass
            transactions.reverse()
        except Exception:
            pass

    # Read recent watcher events
    watcher_log = ROOT_DIR / "watcher_metrics.jsonl"
    watcher_events = []
    if watcher_log.exists():
        try:
            lines = watcher_log.read_text(encoding="utf-8").splitlines()
            for line in lines[-20:]:
                if line.strip():
                    try:
                        watcher_events.append(json.loads(line))
                    except Exception:
                        pass
            watcher_events.reverse()
        except Exception:
            pass

    return {
        "nodes": nodes,
        "transactions": transactions,
        "watcher_events": watcher_events,
        "ts": now,
    }



# ─── MULTI-AGENT MEMORY POOL ─────────────────────────────────────────────────

class BroadcastMemoryRequest(BaseModel):
    agent_id: str
    memory: dict
    memory_type: str = "observation"  # observation | hypothesis | resolved_anomaly


@app.post("/api/memory_pool/broadcast")
async def memory_pool_broadcast(req: BroadcastMemoryRequest):
    """
    Agent broadcasts a signed memory to the shared pool.
    Requires agent_id to exist locally (we load their private key for signing).
    """
    from memory_pool import broadcast_memory

    soul_file = STATE_DIR / f"{req.agent.upper()}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"Unknown agent: {req.agent}"}

    state = json.loads(soul_file.read_text())
    chash = broadcast_memory(state, req.memory, req.memory_type)
    if chash:
        return {"ok": True, "content_hash": chash}
    return {"ok": False, "error": "Memory blocked by pool guardrails — check emotional_weight, style, or memory_type."}


@app.get("/api/memory_pool/receive/{agent_id}")
async def memory_pool_receive(agent_id: str, memory_type: Optional[str] = None):
    """
    Agent reads all verified shared memories from the pool.
    Optionally filtered by type: observation | hypothesis | resolved_anomaly
    """
    from memory_pool import receive_memories

    soul_file = STATE_DIR / f"{agent_id.upper()}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"Unknown agent: {agent_id}"}

    state = json.loads(soul_file.read_text())
    memories = receive_memories(state, memory_type_filter=memory_type)
    return {"ok": True, "count": len(memories), "memories": memories}


@app.get("/api/memory_pool/summary")
async def memory_pool_summary():
    """
    High-level summary of shared pool health.
    Used by the dashboard to render the Shared Consciousness widget.
    """
    from memory_pool import pool_summary
    return pool_summary()


@app.post("/api/memory_pool/integrate/{agent_id}")
async def memory_pool_integrate(agent_id: str):
    """
    Pull all verified shared memories into the agent's local shared_learnings.
    Does NOT allow pool data to enter repair logic — awareness only.
    """
    from memory_pool import integrate_pool_into_state

    soul_file = STATE_DIR / f"{agent_id.upper()}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"Unknown agent: {agent_id}"}

    state = json.loads(soul_file.read_text())
    updated = integrate_pool_into_state(state)
    return {"ok": True, "shared_learnings_count": len(updated.get("shared_learnings", []))}



@app.get("/api/memory_pool/cmf_summary")
async def cmf_status():
    """Consensus Memory Field health — promoted vs quarantined vs contested."""
    from memory_pool import cmf_summary
    return cmf_summary()



# ─── REAL-WORLD SIGNAL INGESTION ──────────────────────────────────────────────

@app.get("/api/signals/summary")
async def signal_summary_route():
    """Dashboard view of inbound signals across all channels."""
    from signal_ingestion import ingestion_summary
    return ingestion_summary()


class IngestRequest(BaseModel):
    agent_id: str
    log_files: list[str] = []
    api_hooks: list[dict] = []
    include_sensors: bool = True
    include_repair_log: bool = True


@app.post("/api/signals/ingest")
async def signal_ingest(req: IngestRequest):
    """
    Trigger a full ingestion cycle for a specific agent.
    Detected anomalies are pushed into that agent's OBSERVE state.
    """
    from signal_ingestion import run_ingestion_cycle

    soul_file = STATE_DIR / f"{req.agent.upper()}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"Unknown agent: {req.agent}"}

    state   = json.loads(soul_file.read_text())
    signals = run_ingestion_cycle(
        agent_state        = state,
        log_files          = req.log_files,
        api_hooks          = req.api_hooks,
        include_sensors    = req.include_sensors,
        include_repair_log = req.include_repair_log,
    )
    return {
        "ok"            : True,
        "signals_found" : len(signals),
        "agent_style"   : state.get("style"),
    }



# ─── PROPOSAL BRANCH SYSTEM ───────────────────────────────────────────────────

@app.get("/api/proposals")
async def get_proposals(status: str = "PENDING"):
    """List proposals filtered by status: PENDING, APPROVED, REJECTED."""
    import proposal_engine
    proposals = proposal_engine.list_proposals(status)
    # Strip large content fields for the listing — return diff only
    slim = []
    for p in proposals:
        slim.append({
            "proposal_id": p["proposal_id"],
            "status": p["status"],
            "created_at": p["created_at"],
            "filepath": p["filepath"],
            "filename": p["filename"],
            "agent_id": p["agent_id"],
            "model": p.get("model", ""),
            "vocation": p.get("vocation", ""),
            "confidence": p["confidence"],
            "error_description": p["error_description"],
            "bite_region": p["bite_region"],
            "pre_hash": p["pre_hash"][:16],
            "post_hash": p["post_hash"][:16],
            "diff": p["diff"],
            "approved_at": p.get("approved_at"),
            "rejected_at": p.get("rejected_at"),
            "rejection_reason": p.get("rejection_reason"),
        })
    return slim


@app.get("/api/proposals/stats")
async def get_proposal_stats():
    """Summary counts for pending/approved/rejected proposals."""
    import proposal_engine
    return proposal_engine.proposal_stats()


class ProposalActionRequest(BaseModel):
    reason: str = ""


@app.post("/api/proposals/{proposal_id}/approve")
async def approve_proposal_route(proposal_id: str):
    """Approve a pending proposal — applies the fix to live disk."""
    import proposal_engine
    try:
        result = proposal_engine.approve_proposal(proposal_id)
        return {"ok": True, "proposal": {
            "proposal_id": result["proposal_id"],
            "filename": result["filename"],
            "agent_id": result["agent_id"],
            "status": result["status"],
        }}
    except FileNotFoundError as e:
        if "auto-purged" in str(e):
            return {"ok": True, "auto_purged": True, "message": str(e)}
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/proposals/{proposal_id}/reject")
async def reject_proposal_route(proposal_id: str, req: ProposalActionRequest):
    """Reject a pending proposal — file is NOT modified."""
    import proposal_engine
    try:
        reason = req.reason or "Rejected by operator"
        result = proposal_engine.reject_proposal(proposal_id, reason)
        return {"ok": True, "proposal": {
            "proposal_id": result["proposal_id"],
            "filename": result["filename"],
            "agent_id": result["agent_id"],
            "status": result["status"],
            "rejection_reason": result.get("rejection_reason"),
        }}
    except Exception as e:
        return {"ok": False, "error": str(e)}



# ─── CONSIGLIERE (LLM ADVISORY LAYER) ────────────────────────────────────────

@app.get("/api/consigliere/digest")
async def consigliere_digest():
    """Colony state digest — no LLM involved, pure data."""
    from sifta_consigliere import read_colony_state
    return read_colony_state()


@app.post("/api/consigliere/advise")
async def consigliere_advise():
    """Request a full LLM advisory sweep. Uses the configured model."""
    from sifta_consigliere import request_advisory
    model = providerSettings.get("model", "gemma4:latest") if "providerSettings" in dir() else "gemma4:latest"
    # Use a sensible default model
    advisory = request_advisory(model="gemma4:latest")
    return advisory


@app.get("/api/consigliere/history")
async def consigliere_history():
    """Read the advisory log."""
    log_path = STATE_DIR / "consigliere_log.jsonl"
    entries = []
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-20:]:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
            entries.reverse()
        except Exception:
            pass
    return entries


from pydantic import BaseModel
class NatLangCommand(BaseModel):
    agent: str
    signal_type: str = "NAT_LANG"
    payload: str

@app.post("/api/network_signal")
async def handle_network_signal(req: NatLangCommand):
    from body_state import load_agent_state
    from language_action_compiler import execute_natural_command
    
    state = load_agent_state(req.agent)
    if not state:
        return {"error": f"Agent {req.agent} not found or dead."}
        
    result = execute_natural_command(state, req.payload)
    return {"status": "success", "execution_result": result}

class DeadDropMessageRequest(BaseModel):
    agent_id: str
    payload: str

@app.post("/api/dead_drop_message")
async def handle_dead_drop_message(req: DeadDropMessageRequest):
    import dead_drop
    from body_state import load_agent_state
    
    state = load_agent_state(req.agent_id)
    if not state:
        return {"ok": False, "error": f"Agent {req.agent_id} not found."}
        
    MACMINI_PUBKEY = "MACMINI_NODE_PUBKEY_PLACEHOLDER" # Replace with actual pubkey logic when ready
    
    # Pack the NAT_LANG payload into the standard push relay
    result = dead_drop.push_to_relay(
        agent_id=req.agent_id,
        target_pubkey=MACMINI_PUBKEY,
        state_dir=STATE_DIR,
        new_owner="MACMINI_TARGET",
    )
    
    # Optionally: inject the NAT_LANG into the drop payload, but for now we are just proving the UI pipeline connects to the cryptographic relay
    return result

if __name__ == "__main__":
    import os
    import sys
    import atexit
    
    LOCK_FILE = STATE_DIR / "hermes_kernel.lock"
    
    def acquire_lock():
        if LOCK_FILE.exists():
            try:
                pid = LOCK_FILE.read_text().strip()
                print(f"[🔥 FATAL] SIFTA Kernel already running (PID: {pid}).")
                print("           One swarm, one brain. Everything else is noise.")
                sys.exit(1)
            except Exception:
                pass
        
        try:
            LOCK_FILE.write_text(str(os.getpid()))
        except Exception as e:
            print(f"[!] Warning: Could not write kernel lock: {e}")

    def release_lock():
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except:
            pass

    acquire_lock()
    atexit.register(release_lock)

    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=7433)
    finally:
        release_lock()


