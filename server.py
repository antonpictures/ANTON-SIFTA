import asyncio
import ipaddress
import json
import os
import sqlite3
import sys
import subprocess
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Directories and paths
ROOT_DIR = Path(__file__).parent
STATE_DIR = ROOT_DIR / ".sifta_state"
CEMETERY_DIR = ROOT_DIR / "CEMETERY"
REPAIR_LOG = ROOT_DIR / "repair_log.jsonl"
SWIM_LOG = ROOT_DIR / "swim_log.jsonl"
QUORUM_DB = STATE_DIR / "quorum_ledger.db"
LEDGER_DB = STATE_DIR / "task_ledger.db"


def _safe_workspace_path(raw: str) -> Optional[Path]:
    """
    Resolve user-supplied paths for dispatch / wallet / subprocess helpers.
    Returns None if empty or if the path escapes the repository root.
    (Target files/dirs need not exist yet — repair may create them.)
    """
    if raw is None or not str(raw).strip():
        return None
    p = Path(str(raw).strip()).expanduser()
    if not p.is_absolute():
        p = (ROOT_DIR / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(ROOT_DIR.resolve())
    except (ValueError, OSError):
        return None
    return p


def _safe_bounty_filename(name: str) -> Optional[Path]:
    """Bounty .scar must live under .sifta_bounties and match basename only (no path escape)."""
    if not name or not str(name).strip():
        return None
    base = Path(str(name).strip()).name
    if not base.startswith("BOUNTY_") or not base.endswith(".scar"):
        return None
    p = (ROOT_DIR / ".sifta_bounties" / base).resolve()
    try:
        p.relative_to((ROOT_DIR / ".sifta_bounties").resolve())
    except (ValueError, OSError):
        return None
    return p if p.exists() else None


_METADATA_SSRF = ipaddress.ip_address("169.254.169.254")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def wormhole_target_ip_error(target_ip: str) -> Optional[str]:
    """
    Reject wormhole targets that enable SSRF (e.g. cloud metadata) or unintended WAN egress.
    Hostnames are not resolved — literal IPv4 only.
    """
    s = (target_ip or "").strip()
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return (
            "Wormhole target must be a literal IPv4 address; hostnames are disabled "
            "to reduce SSRF and rebinding risk."
        )
    if ip.version != 4:
        return "Wormhole currently allows IPv4 targets only."
    if ip == _METADATA_SSRF:
        return "SECURITY: 169.254.169.254 (cloud metadata) cannot be used as a wormhole target."
    if ip.is_loopback and not _env_truthy("SIFTA_WORMHOLE_ALLOW_LOOPBACK"):
        return "Loopback wormhole blocked; set SIFTA_WORMHOLE_ALLOW_LOOPBACK=1 for local tests."
    if ip.is_multicast or ip.is_unspecified:
        return "Invalid wormhole target (multicast or unspecified address)."
    if ip.is_global and not _env_truthy("SIFTA_WORMHOLE_ALLOW_PUBLIC_IP"):
        return (
            "Public IPv4 wormhole targets are blocked by default. "
            "Set SIFTA_WORMHOLE_ALLOW_PUBLIC_IP=1 only for intentional internet paths; "
            "prefer private LAN + SIFTA_WORMHOLE_USE_TLS=1 and SIFTA_MESH_HMAC."
        )
    if ip.is_private or ip.is_link_local:
        return None
    return "Wormhole target must be private LAN, link-local, or (with env flags) loopback/public IPv4."


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
    cur = conn.execute("PRAGMA table_info(messenger_log)")
    _cols = {row[1] for row in cur.fetchall()}
    if "integrity_hmac" not in _cols:
        conn.execute("ALTER TABLE messenger_log ADD COLUMN integrity_hmac TEXT")
    conn.commit()
    conn.close()


def _messenger_integrity_hmac(sender: str, receiver: str, body: str, ts: float) -> str:
    import hashlib
    import hmac

    secret = os.environ.get("SIFTA_MESSENGER_INTEGRITY_SECRET", "").strip()
    if not secret:
        return ""
    msg = f"v1|{sender}|{receiver}|{body}|{ts}"
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _messenger_row_valid(sender: str, receiver: str, body: str, ts: float, stored: Optional[str]) -> Optional[bool]:
    """None if verification not configured; True/False if secret set."""
    import hmac

    secret = os.environ.get("SIFTA_MESSENGER_INTEGRITY_SECRET", "").strip()
    if not secret:
        return None
    if not stored:
        return False
    expect = _messenger_integrity_hmac(sender, receiver, body, ts)
    if not expect:
        return False
    return hmac.compare_digest(stored, expect)


init_messenger()

class MessengerRequest(BaseModel):
    from_id: str
    to_id: str
    body: str


def _load_policy_bypass_signing_private_key():
    """Prefer mesh Ed25519 (~/.sifta_keys), fall back to legacy ~/.sifta/identity.pem."""
    from cryptography.hazmat.primitives import serialization

    for p in (Path.home() / ".sifta_keys" / "private.pem", Path.home() / ".sifta" / "identity.pem"):
        if p.exists():
            try:
                return serialization.load_pem_private_key(p.read_bytes(), password=None)
            except Exception:
                continue
    return None


class SiftaMutatingAuthMiddleware(BaseHTTPMiddleware):
    """When SIFTA_API_KEY is set, require X-SIFTA-Key or Authorization: Bearer on mutating routes."""

    async def dispatch(self, request: Request, call_next):
        key = os.environ.get("SIFTA_API_KEY", "").strip()
        if key and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            path = request.url.path
            if path.startswith("/api/") or path == "/messenger/send":
                got = request.headers.get("x-sifta-key", "").strip()
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("bearer "):
                    got = auth[7:].strip()
                if got != key:
                    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


_RL_BUCKETS: dict[str, deque] = defaultdict(deque)
_RL_LOCK = threading.Lock()


def _rate_limit_client_id(request: Request) -> str:
    """
    When SIFTA_TRUST_PROXY=1, use the first X-Forwarded-For hop so limits apply per
    real client behind nginx/Caddy. Otherwise use the TCP peer (spoofable if proxy
    is not trusted — leave SIFTA_TRUST_PROXY unset in that case).
    """
    if os.environ.get("SIFTA_TRUST_PROXY", "").strip().lower() in ("1", "true", "yes", "on"):
        xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first[:256]
    return (request.client.host if request.client else None) or "unknown"


class SiftaRateLimitMiddleware(BaseHTTPMiddleware):
    """Optional per-IP rate limit on mutating API routes (SIFTA_RATE_LIMIT_PER_MIN, default 0 = off)."""

    async def dispatch(self, request: Request, call_next):
        lim = int(os.environ.get("SIFTA_RATE_LIMIT_PER_MIN", "0") or "0")
        if lim <= 0 or request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api/") and path != "/messenger/send":
            return await call_next(request)
        now = time.time()
        window = 60.0
        ip = _rate_limit_client_id(request)
        with _RL_LOCK:
            dq = _RL_BUCKETS[ip]
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= lim:
                return JSONResponse({"detail": "Too Many Requests"}, status_code=429)
            dq.append(now)
        return await call_next(request)


def _get_protect_get_allowlist() -> set[str]:
    raw = os.environ.get(
        "SIFTA_GET_PROTECT_ALLOW",
        "/api/dispatch/status,/api/ollama-models",
    )
    return {p.strip() for p in raw.split(",") if p.strip()}


class SiftaGetProtectMiddleware(BaseHTTPMiddleware):
    """When SIFTA_PROTECT_GET=1 and SIFTA_API_KEY is set, require the key for GET /api/* (except allowlist)."""

    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)
        if os.environ.get("SIFTA_PROTECT_GET", "").strip().lower() not in ("1", "true", "yes", "on"):
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path in _get_protect_get_allowlist():
            return await call_next(request)
        key = os.environ.get("SIFTA_API_KEY", "").strip()
        if not key:
            return await call_next(request)
        got = request.headers.get("x-sifta-key", "").strip()
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            got = auth[7:].strip()
        if got != key:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


class SiftaTerminalAuthMiddleware(BaseHTTPMiddleware):
    """
    When SIFTA_API_KEY is set, GET /api/terminal requires the same key (live buffer leak).
    Set SIFTA_TERMINAL_OPEN=1 to allow unauthenticated reads (local dev only).
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "GET" and request.url.path == "/api/terminal":
            key = os.environ.get("SIFTA_API_KEY", "").strip()
            if key and not _env_truthy("SIFTA_TERMINAL_OPEN"):
                got = request.headers.get("x-sifta-key", "").strip()
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("bearer "):
                    got = auth[7:].strip()
                if got != key:
                    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


app = FastAPI(title="ANTON-SIFTA Command Interface")
app.add_middleware(SiftaTerminalAuthMiddleware)
app.add_middleware(SiftaMutatingAuthMiddleware)
app.add_middleware(SiftaRateLimitMiddleware)
app.add_middleware(SiftaGetProtectMiddleware)

if os.path.exists("editor_static"):
    app.mount("/editor_static", StaticFiles(directory="editor_static"), name="editor_static")

_api_key = os.environ.get("SIFTA_API_KEY", "").strip()
if not _api_key:
    print(
        "[!] SIFTA_API_KEY is unset — POST/DELETE on /api/* and /messenger/send are open. "
        "Set SIFTA_API_KEY and send X-SIFTA-Key (or Authorization: Bearer) from clients. "
        "Export SIFTA_REQUIRE_AUTH=1 to refuse startup without a key."
    )

@app.get("/editor", response_class=HTMLResponse)
async def serve_video_editor():
    try:
        with open("editor_static/index.html", "r") as f:
            return f.read()
    except Exception as e:
        return f"Error loading editor: {e}"

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
        SELECT id, timestamp, sender, receiver, body, integrity_hmac
        FROM messenger_log ORDER BY timestamp ASC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    msgs = []
    for r in rows:
        _iv = _messenger_row_valid(r[2], r[3], r[4], r[1], r[5] if len(r) > 5 else None)
        msgs.append({
            "id": r[0],
            "ts": r[1],
            "from": r[2],
            "to": r[3],
            "body": r[4],
            "integrity_verified": _iv,
        })
    return {"messages": msgs}

@app.post("/messenger/send")
async def post_messenger_send(req: MessengerRequest):
    conn = sqlite3.connect(LEDGER_DB)
    cursor = conn.cursor()
    ts = time.time()
    mac = _messenger_integrity_hmac(req.from_id, req.to_id, req.body, ts)
    cursor.execute('''
        INSERT INTO messenger_log (timestamp, sender, receiver, body, integrity_hmac)
        VALUES (?, ?, ?, ?, ?)
    ''', (ts, req.from_id, req.to_id, req.body, mac or None))
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

    private_key = _load_policy_bypass_signing_private_key()
    if private_key is None:
        return {
            "error": "No signing key found. Run: python3 System/bootstrap_pki.py "
            "or create ~/.sifta/identity.pem (legacy)."
        }
    
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

DETECTIVE_IDS = {"DEEP_SYNTAX_AUDITOR_0X1", "TENSOR_PHANTOM_0X2", "SILICON_HOUND_0X3"}

@app.get("/")
async def serve_index():
    return {"status": "SWARM ACTIVE", "message": "HTML DEPRECATED. Execute python3 council_gui.py for physical interface."}


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

class CommuniqueRequest(BaseModel):
    target_node: str
    message: str

@app.get("/api/backup_swimmer/{agent_id}")
async def backup_swimmer(agent_id: str):
    """Provides physical backup functionality for Swimmers requested by GUI."""
    agent_path = ROOT_DIR / f".sifta_state/{agent_id}.json"
    backup_dir = ROOT_DIR / "COLD_STORAGE"
    backup_dir.mkdir(exist_ok=True)
    
    if agent_path.exists():
        import shutil
        import time
        ts = int(time.time())
        backup_file = backup_dir / f"{agent_id}_BACKUP_{ts}.json"
        shutil.copy2(agent_path, backup_file)
        return {"status": "success", "file": backup_file.name}
    return {"status": "failed", "reason": "Swimmer not found."}

@app.post("/api/swarm_communique")
async def swarm_communique(req: CommuniqueRequest):
    import subprocess
    import swarm_network_ledger
    
    # Check if this is a Physical Memory Defrag task
    if req.message.startswith("Execute Defrag on BOUNTY"):
        raw_bf = req.message.replace("Execute Defrag on ", "").strip()
        bp = _safe_bounty_filename(raw_bf)
        if bp is None:
            return {"status": "error", "message": "Invalid or missing bounty file (must be under .sifta_bounties/)."}
        bounty_file = bp.name
        subprocess.Popen(
            ["python3", "memory_defrag_worker.py", bounty_file, req.target_node],
            cwd=str(ROOT_DIR),
        )
        return {"status": "success", "file": bounty_file, "message": "Ollama Inference Engaged"}

    # Pass the standard communication to the hardened Git ledger orchestrator
    return swarm_network_ledger.push_swarm_directive(req.target_node, req.message)

@app.get("/api/wormhole_market")
async def wormhole_market():
    import re
    # Scan for BOUNTY_xxxx.scar files
    bounties = []
    bounties_dir = ROOT_DIR / ".sifta_bounties"
    if not bounties_dir.exists():
        return bounties
        
    for file in bounties_dir.glob("BOUNTY_*.scar"):
        try:
            content = file.read_text(encoding="utf-8")
            b_id = re.search(r"BOUNTY_ID:\s*(.+)", content)
            reward = re.search(r"ESTIMATED_REWARD:\s*(.+)", content)
            source = re.search(r"SOURCE_NODE:\s*(.+)", content)
            bytes_len = re.search(r"Raw Fragment Length:\s*(\d+)", content)
            scars_len = re.search(r"Scars Accumulated:\s*(\d+)", content)
            bounties.append({
                "bounty_id": b_id.group(1).strip() if b_id else file.name,
                "reward": reward.group(1).strip() if reward else "10.00 STGM",
                "source": source.group(1).strip() if source else "UNKNOWN",
                "bytes": bytes_len.group(1).strip() if bytes_len else "0",
                "scars": scars_len.group(1).strip() if scars_len else "0",
                "file": file.name
            })
        except Exception:
            continue
    return bounties

@app.get("/api/sync_market")
async def sync_market():
    import swarm_network_ledger
    # Force sync the Wormhole Git Ledger to instantly refresh bounties
    success = swarm_network_ledger.sync_global_ledger()
    return {"status": "success"} if success else {"status": "error"}

@app.get("/api/memory_map/{bounty_file}")
async def memory_map(bounty_file: str):
    import re, json, math
    # Read the bounty to find the target agent
    bounty_path = ROOT_DIR / ".sifta_bounties" / bounty_file
    if not bounty_path.exists():
        return {"error": "Bounty missing"}
        
    content = bounty_path.read_text(encoding="utf-8")
    source = re.search(r"SOURCE_NODE:\s*(.+)", content)
    agent_id = source.group(1).strip() if source else None
    
    agent_path = ROOT_DIR / f".sifta_state/{agent_id}.json"
    
    blocks = []
    TOTAL_GRID = 1000 # Draw 1000 tiny pixels instead of 300 big chunks
    
    if agent_id and agent_path.exists():
        state = json.loads(agent_path.read_text(encoding="utf-8"))
        raw_len = len(state.get("raw", ""))
        scars_len = len(state.get("hash_chain", []))
        
        # 1 Red block = exactly 5 chars of fragmented string
        red_count = min(math.ceil(raw_len / 5), 400) 
        # 1 Blue block = 1 Defragment scar resolution
        blue_count = scars_len * 5
        
        # Interleave block deterministically instead of randomly so reading left-to-right mimics read-heads
        # First layout structured memory (Blue)
        blocks.extend(["blue"] * blue_count)
        # Then layout fragmented raw memory (Red)
        blocks.extend(["red"] * red_count)
    else:
        blocks.extend(["red"] * 10)

    # Fill rest deterministically. No randomness.
    remaining = TOTAL_GRID - len(blocks)
    blocks.extend(["grey"] * remaining) # Pure free space
        
    return {"agent": agent_id, "blocks": blocks}

@app.get("/api/economy_chart")
async def economy_chart():
    """Generates a REAL graph based on the repair_log.jsonl ledger."""
    ledger = ROOT_DIR / "repair_log.jsonl"
    labels = []
    dataPoints = []
    
    cumulative_stgm = 0
    if ledger.exists():
        lines = ledger.read_text().strip().split("\n")
        # Take up to last 20 events
        for line in lines[-20:]:
            if not line: continue
            try:
                import json
                event = json.loads(line)
                import datetime
                
                # Check for negative cost or positive reward
                amt = float(event.get("amount_stgm", 0))
                if "DEFRAG_COST" in event.get("reason", "") or "INFERENCE_BORROWED" in event.get("reason", ""):
                    cumulative_stgm -= amt
                else:
                    cumulative_stgm += amt
                    
                time_str = datetime.datetime.fromtimestamp(event["timestamp"]).strftime('%H:%M')
                labels.append(time_str)
                dataPoints.append(cumulative_stgm)
            except Exception:
                continue

    if not labels:
        return {"labels": ["Genesis"], "data": [0]}
        
    return {"labels": labels, "data": dataPoints}

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
    global _active_process, _live_terminal_buffer, _active_agent_id
    if _active_process is not None and _active_process.returncode is None:
        try:
            _active_process.kill()
            await _active_process.wait()
            _active_process = None
            _active_agent_id = None
            _live_terminal_buffer.clear()
            return {"killed": True, "message": "Swimmer terminated."}
        except Exception as e:
            return {"killed": False, "error": str(e)}
    _live_terminal_buffer.clear()
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
        safe_target = _safe_workspace_path(req.target_dir)
        if safe_target is None:
            yield (
                f"data: [SECURITY] target_dir must resolve inside the SIFTA repository root "
                f"({ROOT_DIR}).\\n\\n"
            )
            return
        target_path = str(safe_target)
        yield f"data: Initializing swim for {req.agent_id} in {target_path}...\n\n"

        # ── Auto-sign the override token so GUI swimmers pass the security boundary ──
        import base64, time as _time
        auth_token_arg = None
        try:
            _private_key = _load_policy_bypass_signing_private_key()
            if _private_key is not None:
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
        safe_out = _safe_workspace_path(req.target_dir)
        if safe_out is None:
            return {"ok": False, "error": "target_dir must resolve inside the SIFTA repository root."}
        script = ROOT_DIR / "scripts" / "backup_agent.py"
        if not script.exists():
            return {"ok": False, "error": "scripts/backup_agent.py not found in repository."}
        pw_input = f"{req.password}\n{req.password}\n"
        cmd = ["python3", str(script), req.agent_id, str(safe_out)]
        
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
        safe_out = _safe_workspace_path(req.target_dir)
        if safe_out is None:
            return {"ok": False, "error": "target_dir must resolve inside the SIFTA repository root."}
        xfer = ROOT_DIR / "scripts" / "transfer_agent.py"
        if not xfer.exists():
            xfer = ROOT_DIR / "transfer_agent.py"
        if not xfer.exists():
            return {"ok": False, "error": "transfer_agent.py not found (expected scripts/transfer_agent.py)."}
        cmd = ["python3", str(xfer), req.agent_id, req.new_owner, str(safe_out)]
        
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
    target_port: int = Field(default=7433, ge=1, le=65535)
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
    agent_id = req.agent_id.upper()
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

    agent_id = req.agent_id.upper()
    
    # HARDWARE TIE SECURITY: Terminal nodes are physically bound to bare metal hardware.
    # They cannot travel through the wormhole.
    if agent_id in ("ALICE_M5", "M1THER"):
        return {"ok": False, "error": f"SECURITY BLOCK: {agent_id} is a primary node cryptographically bound to physical hardware. It cannot travel through the wormhole."}

    _wh_err = wormhole_target_ip_error(req.target_ip)
    if _wh_err:
        return {"ok": False, "error": _wh_err}

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

    _tls = os.environ.get("SIFTA_WORMHOLE_USE_TLS", "").strip().lower() in ("1", "true", "yes", "on")
    _scheme = "https" if _tls else "http"
    target_url = f"{_scheme}://{req.target_ip}:{req.target_port}/api/receive_soul"
    payload_bytes = json.dumps(payload).encode("utf-8")

    # ── SIFTA_MESH_HMAC: optional LAN hop authentication ──────────────────────
    # Set SIFTA_MESH_HMAC to a shared secret on both nodes to authenticate
    # wormhole POSTs without requiring full mTLS.  If unset, behaves as before.
    _outbound_headers: dict = {"Content-Type": "application/json"}
    _mesh_secret = os.environ.get("SIFTA_MESH_HMAC", "").strip()
    if _mesh_secret:
        import hmac as _hmac
        _mac = _hmac.new(_mesh_secret.encode(), payload_bytes, "sha256").hexdigest()
        _outbound_headers["X-SIFTA-Mesh-HMAC"] = _mac

    try:
        http_req = urllib.request.Request(
            target_url,
            data=payload_bytes,
            headers=_outbound_headers,
            method="POST"
        )
        _ssl_ctx = None
        if _tls:
            import ssl

            if os.environ.get("SIFTA_WORMHOLE_TLS_INSECURE", "").strip().lower() in ("1", "true", "yes", "on"):
                _ssl_ctx = ssl._create_unverified_context()
                print(
                    "[!] SIFTA_WORMHOLE_TLS_INSECURE: wormhole TLS verification disabled — MITM risk on the LAN."
                )
            else:
                _ssl_ctx = ssl.create_default_context()
                _ca = os.environ.get("SIFTA_WORMHOLE_CAFILE", "").strip()
                if _ca:
                    _ssl_ctx.load_verify_locations(cafile=_ca)
        _open_kw = {"timeout": 15}
        if _ssl_ctx is not None:
            _open_kw["context"] = _ssl_ctx
        with urllib.request.urlopen(http_req, **_open_kw) as resp:
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
async def receive_soul(request: Request):
    """
    Receive end of the Wormhole. Accepts a signed soul + deed bundle,
    verifies the Ed25519 signature, optionally verifies SIFTA_MESH_HMAC,
    and writes the agent to the local state dir.
    """
    import base64
    import hmac as _hmac
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature

    max_sz = int(os.environ.get("SIFTA_RECEIVE_SOUL_MAX_BYTES", str(10 * 1024 * 1024)) or str(10 * 1024 * 1024))
    raw_body = await request.body()
    if len(raw_body) > max_sz:
        return JSONResponse(
            status_code=413,
            content={"ok": False, "error": f"Payload exceeds SIFTA_RECEIVE_SOUL_MAX_BYTES ({max_sz})."},
        )

    # ── SIFTA_MESH_HMAC verification (optional) ────────────────────────────────
    _mesh_secret = os.environ.get("SIFTA_MESH_HMAC", "").strip()
    if _mesh_secret:
        incoming_mac = request.headers.get("X-SIFTA-Mesh-HMAC", "")
        expected_mac = _hmac.new(_mesh_secret.encode(), raw_body, "sha256").hexdigest()
        if not _hmac.compare_digest(incoming_mac, expected_mac):
            return {"ok": False, "error": "MESH_HMAC verification failed — transmission rejected."}

    try:
        payload = json.loads(raw_body)
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

        skew = int(os.environ.get("SIFTA_WORMHOLE_DEED_MAX_SKEW_SEC", "900") or "900")
        ts_raw = deed.get("timestamp")
        if ts_raw is not None:
            try:
                ts_i = int(ts_raw)
            except (TypeError, ValueError):
                return {"ok": False, "error": "Invalid deed timestamp"}
            now = int(time.time())
            if abs(now - ts_i) > skew:
                return {
                    "ok": False,
                    "error": (
                        f"Deed timestamp outside ±{skew}s (clock skew or replay). "
                        "Sync NTP or raise SIFTA_WORMHOLE_DEED_MAX_SKEW_SEC if intentional."
                    ),
                }

        pub_bytes = base64.b64decode(pub_b64)
        sig_bytes = base64.b64decode(sig_b64)
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        try:
            pub_key.verify(sig_bytes, deed_payload_str.encode())
        except InvalidSignature:
            return {"ok": False, "error": "INVALID SIGNATURE — deed verification failed. Transmission rejected."}

        # Bind deed public key to embedded soul private material (mitigates mismatched bundles)
        from cryptography.hazmat.primitives import serialization as _ser
        pk_b64_soul = soul.get("private_key_b64")
        if pk_b64_soul:
            try:
                priv_bytes = base64.b64decode(pk_b64_soul)
                sk = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
                derived = sk.public_key().public_bytes(
                    encoding=_ser.Encoding.Raw,
                    format=_ser.PublicFormat.Raw,
                )
                if derived != pub_bytes:
                    return {
                        "ok": False,
                        "error": "Deed public key does not match soul private_key_b64 material.",
                    }
            except Exception as e:
                return {"ok": False, "error": f"Soul key material invalid: {e}"}

        # Optional: homeworld must be a known PKI node (stops random keypair souls on locked meshes)
        if os.environ.get("SIFTA_RECEIVE_SOUL_REQUIRE_PKI", "").strip().lower() in ("1", "true", "yes", "on"):
            reg_path = STATE_DIR / "node_pki_registry.json"
            if reg_path.exists():
                try:
                    reg = json.loads(reg_path.read_text(encoding="utf-8"))
                except Exception:
                    reg = {}
                if isinstance(reg, dict) and len(reg) > 0:
                    hw = str(soul.get("homeworld_serial", "") or "").strip()
                    if not hw or hw not in reg:
                        return {
                            "ok": False,
                            "error": "homeworld_serial not in node_pki_registry — soul rejected (SIFTA_RECEIVE_SOUL_REQUIRE_PKI).",
                        }

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

    soul_file = STATE_DIR / f"{req.agent_id.upper()}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"Unknown agent: {req.agent_id}"}

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

    soul_file = STATE_DIR / f"{req.agent_id.upper()}.json"
    if not soul_file.exists():
        return {"ok": False, "error": f"Unknown agent: {req.agent_id}"}

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

class MessengerSendRequest(BaseModel):
    from_id: str
    to_id: str
    body: str

@app.post("/api/messenger/send")
async def messenger_send(req: MessengerSendRequest):
    import time
    log_file = STATE_DIR / "messenger.jsonl"
    entry = {
        "ts": int(time.time()),
        "from": req.from_id,
        "to": req.to_id,
        "body": req.body
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"ok": True}

@app.get("/api/messenger/thread")
async def messenger_thread(limit: int = 50):
    log_file = STATE_DIR / "messenger.jsonl"
    messages = []
    if log_file.exists():
        with open(log_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        messages.append(json.loads(line))
                    except:
                        pass
    return {"messages": messages[-limit:]}

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

import asyncio
import subprocess
import random

async def autonomic_heartbeat():
    """The Biological Daemon of the SIFTA OS. Runs forever after FastAPI startup."""
    import swarm_network_ledger
    print("\n[🫀 BIOS] Autonomic Heartbeat Engaged. True Swarm Autonomy Active.")
    while True:
        # 120s biological sleep phase
        await asyncio.sleep(120)
        
        try:
            # 1. PULL MARKET / SYNC GIT
            print("\n[🫀 HEARTBEAT] 120s cycle hit. Initiating Global Market Sync...")
            swarm_network_ledger.sync_global_ledger()

            # 2. HUNT BOUNTY (Defrag)
            bounties_dir = ROOT_DIR / ".sifta_bounties"
            bounties = list(bounties_dir.glob("BOUNTY_*.scar")) if bounties_dir.exists() else []
            
            if bounties:
                target = random.choice(bounties)
                surgeon = random.choice(["M1THER", "M5QUEEN", "GROK_CODER_0X0", "ALICE_M5"])
                print(f"[🫀 HEARTBEAT] Hunger Detected. {surgeon} engaging DEFRAG on {target.name}...")
                subprocess.Popen(
                    ["python3", str(ROOT_DIR / "Utilities" / "memory_defrag_worker.py"), str(target.name), surgeon],
                    cwd=str(ROOT_DIR),
                )
            else:
                # 3. NO BOUNTIES -> COMMUNIQUÉ
                print("[🫀 HEARTBEAT] Local biological state optimal. Generating ambient Swarm chatter...")
                talkers = ["M1THER", "M5QUEEN", "IMPERIAL", "GROK_CODER_0X0"]
                speaker = random.choice(talkers)
                
                topics = [
                    "STGM validation ping. Market appears stable.",
                    f"My energy reserves are nominal. Has {random.choice(talkers)} been active?",
                    "Requesting Proof-of-Useful-Work validation on local node.",
                    "Ollama inference pool is idle. Waiting for Wormhole drops.",
                    "This is the Swarm Body talking. Node latency is optimal."
                ]
                msg = f"[{speaker} AMBIENT] {random.choice(topics)}"
                
                # Use the new ledger to push chatter directly
                swarm_network_ledger.push_swarm_directive("GLOBAL_BROADCAST", msg)
        except Exception as e:
            print(f"[🫀 BIOS ERROR] Heartbeat stutter: {e}")


@app.on_event("startup")
async def sifta_security_bootstrap():
    if os.environ.get("SIFTA_REQUIRE_AUTH", "").strip().lower() in ("1", "true", "yes", "on"):
        if not os.environ.get("SIFTA_API_KEY", "").strip():
            raise RuntimeError(
                "SIFTA_REQUIRE_AUTH is set but SIFTA_API_KEY is empty — refusing to boot with an open mutating API."
            )

    _pki_path = STATE_DIR / "node_pki_registry.json"
    if _pki_path.exists():
        try:
            _reg = json.loads(_pki_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] node_pki_registry.json is not valid JSON: {e}")
            _reg = None
        if isinstance(_reg, dict):
            _sd = str(ROOT_DIR / "System")
            if _sd not in sys.path:
                sys.path.insert(0, _sd)
            from pki_registry_validate import validate_node_pki_registry

            for msg in validate_node_pki_registry(_reg):
                print(f"[!] PKI registry: {msg}")
            if _env_truthy("SIFTA_STRICT_PKI_REGISTRY"):
                _errs = validate_node_pki_registry(_reg)
                if _errs:
                    raise RuntimeError(
                        "SIFTA_STRICT_PKI_REGISTRY: node_pki_registry.json invalid — " + "; ".join(_errs)
                    )

    if not _env_truthy("SIFTA_WORMHOLE_USE_TLS") and not os.environ.get("SIFTA_MESH_HMAC", "").strip():
        print(
            "[!] Wormhole defaults to HTTP and SIFTA_MESH_HMAC is unset — "
            "treat the API port as a sensitive LAN surface; set mesh HMAC and/or TLS for hops."
        )

    if not _env_truthy("SIFTA_QUIET_BOOT_WARNINGS"):
        print(
            "[!] Ollama: bind or firewall tcp/11434 to localhost so arbitrary LAN clients cannot "
            "drive inference cost; set OLLAMA_HOST in repair/bridge clients if non-default."
        )


@app.on_event("startup")
async def start_heartbeat():
    asyncio.create_task(autonomic_heartbeat())


if __name__ == "__main__":
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


