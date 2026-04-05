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

app = FastAPI(title="ANTON-SIFTA Command Interface")

# ── Global dispatch guard ─────────────────────────────────────────────────────
# Only ONE swimmer may run at a time. A new dispatch kills the old one first.
_active_process: asyncio.subprocess.Process | None = None
_dispatch_lock = asyncio.Lock()

# Ensure required directories exist
STATE_DIR.mkdir(exist_ok=True)
CEMETERY_DIR.mkdir(exist_ok=True)

# Mount static files folder
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = ROOT_DIR / "static" / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/api/agents")
async def get_agents():
    agents = []
    now = int(time.time())
    for p in STATE_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                state = json.load(f)
                
                # Check if it has the actual agent shape we expect
                if "id" not in state or "energy" not in state:
                    continue
                
                ttl = state.get("ttl", 0)
                ttl_remaining = max(0, ttl - now)
                state["ttl_remaining"] = ttl_remaining
                
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
    
    # Sort agents by id
    agents.sort(key=lambda x: x.get("id", ""))
    return agents


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
async def get_ollama_models():
    """Query local Ollama daemon for installed models."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models, "available": True}
    except Exception as e:
        return {"models": [], "available": False, "error": str(e)}


class DispatchRequest(BaseModel):
    agent_id: str
    target_dir: str
    write: bool = False
    provider: str = "ollama"
    model_name: str = "qwen3.5:0.8b"
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""


@app.get("/api/dispatch/status")
async def dispatch_status():
    """Returns whether a swimmer is currently active."""
    running = _active_process is not None and _active_process.returncode is None
    return {"active": running}


@app.post("/api/dispatch/kill")
async def dispatch_kill():
    """Terminate the active swimmer process immediately."""
    global _active_process
    if _active_process is not None and _active_process.returncode is None:
        try:
            _active_process.kill()
            await _active_process.wait()
            _active_process = None
            return {"killed": True, "message": "Swimmer terminated."}
        except Exception as e:
            return {"killed": False, "error": str(e)}
    return {"killed": False, "message": "No active swimmer."}


@app.post("/api/dispatch")
async def dispatch_swim(req: DispatchRequest):
    async def sse_generator():
        global _active_process

        # ── Kill any in-flight swimmer first ──────────────────────────────────
        if _active_process is not None and _active_process.returncode is None:
            try:
                _active_process.kill()
                await _active_process.wait()
            except Exception:
                pass
            yield "data: [PREVIOUS SWIM TERMINATED — launching new agent]\n\n"

        import os
        # Need to fix the relative path traversal issue if path is absolute but the target_dir variable remains absolute
        target_path = req.target_dir
        yield f"data: Initializing swim for {req.agent_id} in {target_path}...\n\n"
        
        cmd = ["python3", "-u", "repair.py", target_path]
        if req.write:
            cmd.append("--write")
        
        cmd.extend([
            "--provider", req.provider,
            "--model", req.model_name
        ])
        
        if req.base_url:
            cmd.extend(["--base-url", req.base_url])
            
        cmd.append("--verify")
        
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

            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
                yield f"data: {decoded}\n\n"

            await process.wait()
            _active_process = None
            yield "data: \n\n"
            yield f"data: [PROCESS EXITED WITH CODE {process.returncode}]\n\n"
        except Exception as e:
            _active_process = None
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7433)
