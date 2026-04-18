import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
import uvicorn

# ==========================================
# WORMHOLE GATEWAY (HTTP REST API)
# The "American Coder" SIFTA Challenge
# Open-Source MIT License
# ==========================================

app = FastAPI(
    title="Wormhole Gateway API", 
    description="Cryptographic Scar Observation Layer allowing external queries of the biological ledger."
)

ROOT_DIR = Path(__file__).parent

def deep_node_discovery():
    """Recursively scans the filesystem for all active .scar biological traces."""
    scars = []
    # Search all .sifta subdirectories for .scar graffiti
    for scar_file in ROOT_DIR.rglob(".sifta/*.scar"):
        try:
            with open(scar_file, "r") as f:
                data = json.load(f)
                # Attach file location reference
                data["_file_path"] = str(scar_file.relative_to(ROOT_DIR))
                scars.append(data)
        except Exception:
            pass # Ignore corrupted biological traces during deep scan
    return scars

@app.get("/swarm/agent/{agent_id}/scars")
async def get_agent_scars(agent_id: str):
    """
    Returns the complete chronological history of an agent's scars.
    Query: GET /swarm/agent/DEEPSEEK_CHALLENGER/scars
    """
    all_scars = deep_node_discovery()
    
    agent_scars = [s for s in all_scars if s.get("agent_id") == agent_id.upper()]
    
    if not agent_scars:
        raise HTTPException(status_code=404, detail=f"No scars found for agent: {agent_id}")
        
    # Sort chronologically using the embedded scent timestamp
    agent_scars.sort(key=lambda x: x.get("scent", {}).get("last_visited", ""))
    return {"agent_id": agent_id.upper(), "total_scars": len(agent_scars), "history": agent_scars}

@app.get("/swarm/mirror")
async def verify_mirror(hash: str):
    """
    Searches the filesystem footprint for a specific cryptographic hash.
    Query: GET /swarm/mirror?hash=<value>
    """
    all_scars = deep_node_discovery()
    
    for scar in all_scars:
        if scar.get("body_hash") == hash:
            return {"verified": True, "scar": scar}
            
    raise HTTPException(status_code=404, detail="Hash not found in available filesystem territory")

@app.get("/agent/{agent_id}/export")
async def export_agent_route(agent_id: str):
    """
    Serialize agent for wormhole transfer using structural truth.
    """
    from wormhole import export_agent
    try:
        return export_agent(agent_id.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/import")
async def import_agent_route(payload: dict):
    """
    Merge remote agent into local ledger safely.
    """
    from wormhole import import_agent
    try:
        result = import_agent(payload)
        return {"status": result}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.post("/agent/ingest")
async def ingest_command(packet: dict):
    """
    The only authorized ingestion point for Swarm intents.
    Passes directly into the Constitutional Gate.
    """
    import sifta_ingestor
    
    # We load the registered macbook identity to verify
    PUB_KEY = Path.home() / ".sifta" / "authorized_keys" / "macbook.pub.pem"
    if not PUB_KEY.exists():
        raise HTTPException(status_code=500, detail="Authorized keys not configured.")
        
    pubkey_pem = PUB_KEY.read_bytes()
    
    # Pass the raw json string into the ingestor so the signature check holds
    task_id = sifta_ingestor.ingest_command_envelope(json.dumps(packet), pubkey_pem)
    
    if task_id:
        return {"status": "INGESTED", "task_id": task_id}
    else:
        raise HTTPException(status_code=403, detail="Cryptographic envelope rejected.")

import sqlite3
import time

MESSENGER_DB = ROOT_DIR / ".sifta_state" / "messenger.db"

def init_messenger():
    MESSENGER_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MESSENGER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      REAL,
            from_id TEXT,
            to_id   TEXT,
            body    TEXT,
            sig     TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_messenger()

@app.post("/messenger/send")
async def messenger_send(packet: dict):
    """Receive a signed swimmer message and persist it."""
    required = {"from_id", "to_id", "body"}
    if not required.issubset(packet.keys()):
        raise HTTPException(status_code=400, detail="Missing fields.")
    conn = sqlite3.connect(MESSENGER_DB)
    conn.execute(
        "INSERT INTO messages (ts, from_id, to_id, body, sig) VALUES (?,?,?,?,?)",
        (time.time(), packet["from_id"], packet["to_id"], packet["body"], packet.get("sig",""))
    )
    conn.commit()
    conn.close()
    return {"status": "DELIVERED"}

@app.get("/messenger/thread")
async def messenger_thread(limit: int = 50):
    """Return the last N messages ordered ascending."""
    conn = sqlite3.connect(MESSENGER_DB)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, ts, from_id, to_id, body FROM messages ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    messages = [{"id":r[0],"ts":r[1],"from":r[2],"to":r[3],"body":r[4]} for r in reversed(rows)]
    return {"messages": messages}

if __name__ == "__main__":
    print("[WORMHOLE] Opening API Gateway on port 7444...")
    uvicorn.run("wormhole_gateway:app", host="0.0.0.0", port=7444, reload=True)
