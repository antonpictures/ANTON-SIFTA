import os
import sys
import json
import uuid
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_RELAY_MAX_BODY = int(os.environ.get("SIFTA_RELAY_MAX_BODY_BYTES", str(6 * 1024 * 1024)) or str(6 * 1024 * 1024))


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


class RelayAuthMiddleware(BaseHTTPMiddleware):
    """When SIFTA_RELAY_API_KEY is set, require matching X-SIFTA-Relay-Key on every request."""

    async def dispatch(self, request: Request, call_next):
        k = os.environ.get("SIFTA_RELAY_API_KEY", "").strip()
        if k and request.headers.get("x-sifta-relay-key", "").strip() != k:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        cl = request.headers.get("content-length")
        if cl and request.method in ("POST", "PUT", "PATCH"):
            try:
                if int(cl) > _RELAY_MAX_BODY:
                    return JSONResponse({"detail": "Payload too large"}, status_code=413)
            except ValueError:
                pass
        return await call_next(request)


app = FastAPI(title="SIFTA Dead-Drop Relay")
app.add_middleware(RelayAuthMiddleware)

# This is where the dumb post office stores things
RELAY_DIR = Path("relay_drops")
RELAY_DIR.mkdir(exist_ok=True)

class DropRequest(BaseModel):
    to_pubkey: str
    payload: dict

@app.post("/drop")
async def receive_drop(drop: DropRequest):
    """Stores an encrypted JSON blob bound for a specific public key."""
    # Sanitize pubkey for filesystem
    import urllib.parse
    safe_pub = urllib.parse.quote_plus(drop.to_pubkey)
    user_dir = RELAY_DIR / safe_pub
    user_dir.mkdir(exist_ok=True)
    
    drop_id = str(uuid.uuid4())
    filepath = user_dir / f"{drop_id}.json"
    
    record = {
        "drop_id": drop_id,
        "timestamp": int(time.time()),
        "payload": drop.payload
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        
    print(f"[RELAY] Accepted drop {drop_id} for {safe_pub[:20]}...")
    return {"ok": True, "drop_id": drop_id}

@app.get("/pickup/{pubkey:path}")
async def fetch_drops(pubkey: str):
    """Returns all pending drops for this public key."""
    import urllib.parse
    safe_pub = urllib.parse.quote_plus(pubkey)
    user_dir = RELAY_DIR / safe_pub
    
    if not user_dir.exists():
        return {"ok": True, "drops": []}
        
    drops = []
    for p in user_dir.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                drops.append(json.load(f))
        except Exception:
            pass
            
    print(f"[RELAY] Served {len(drops)} drops to {safe_pub[:20]}...")
    return {"ok": True, "drops": drops}

@app.delete("/pickup/{pubkey:path}/{drop_id}")
async def ack_drop(pubkey: str, drop_id: str):
    """Deletes a drop once the client acknowledges safe receipt."""
    import urllib.parse
    safe_pub = urllib.parse.quote_plus(pubkey)
    filepath = RELAY_DIR / safe_pub / f"{drop_id}.json"
    
    if filepath.exists():
        filepath.unlink()
        print(f"[RELAY] Ghosted drop {drop_id}")
        return {"ok": True}
    return {"ok": False, "error": "Not found"}

if __name__ == "__main__":
    if not os.environ.get("SIFTA_RELAY_API_KEY", "").strip():
        print(
            "[!] SIFTA_RELAY_API_KEY is unset — relay accepts unauthenticated requests on the LAN. "
            "Set the key and pass X-SIFTA-Relay-Key from dead_drop.py clients."
        )
    if _env_truthy("SIFTA_RELAY_REQUIRE_AUTH") and not os.environ.get("SIFTA_RELAY_API_KEY", "").strip():
        print("[RELAY] FATAL: SIFTA_RELAY_REQUIRE_AUTH=1 but SIFTA_RELAY_API_KEY is empty.")
        sys.exit(1)
    print("[RELAY] Starting Stigmergic Post Office on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
