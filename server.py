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

DETECTIVE_IDS = {"DEEP_SYNTAX_AUDITOR_0X1", "TENSOR_PHANTOM_0X2", "SILICON_HOUND_0X3"}

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = ROOT_DIR / "static" / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/api/agents")
async def get_agents(show_detectives: bool = False):
    """Return all swarm agents.
    Detectives (Bureau) are HIDDEN when RESTING on the couch — only surface when ACTIVE.
    Pass ?show_detectives=true to see them regardless.
    """
    agents = []
    now = int(time.time())
    for p in STATE_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                state = json.load(f)
                
                # Check if it has the actual agent shape we expect
                if "id" not in state or "energy" not in state:
                    continue
                
                agent_id = state.get("id", "")

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


class BackupRequest(BaseModel):
    agent_id: str
    target_dir: str
    password: str

@app.post("/api/wallet/backup")
async def wallet_backup(req: BackupRequest):
    try:
        pw_input = f"{req.password}\n{req.password}\n"
        cmd = ["python3", "backup_agent.py", req.agent_id, req.target_dir]
        
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
        cmd = ["python3", "transfer_agent.py", req.agent_id, req.new_owner, req.target_dir]
        
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

@app.post("/api/wallet/wormhole")
async def wallet_wormhole(req: WormholeRequest):
    """
    P2P LAN Wormhole — transmits the agent soul directly to a remote SIFTA node
    over HTTP. The remote node must be running server.py and expose /api/receive_soul.
    After a confirmed ACK from the remote node, the local copy is ghosted.
    """
    import urllib.request
    import urllib.error

    agent_id = req.agent_id.upper()
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7433)
