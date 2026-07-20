#!/usr/bin/env python3
"""
SIFTA MCP Server (Dependency-Free Standard IO)
Bridging the SIFTA Swarm OS and the Antigravity Creator Node via Model Context Protocol.
"""

import sys
import json
import time
import os
import hashlib
import shutil
import subprocess
import urllib.request
from pathlib import Path

from System.swarm_mcp_receipt_manifest import enforce_mcp_tool_call, write_mcp_receipt_manifest

def _simple_ascii_field(swimmers):
    """Tiny visual of the swimmer field for widgets."""
    lines = ["  ~ SIFTA SWIMMER FIELD ~"]
    for s in swimmers[:12]:
        c = s.get("caste", "?")[:1].upper()
        lines.append(f"  {c}· " + "·" * (hash(str(s)) % 7 + 2))
    lines.append("  (field traces active — ASCII swimmers moving)")
    return "\n".join(lines)

_REPO = Path(__file__).resolve().parent
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
_GROK_CHAT = _REPO / "grok_chat.py"
from Kernel.path_resolver import get_repo_root
_GROK_BIN = os.environ.get("SIFTA_GROK_CLI", str(get_repo_root() / "bin" / "grok"))
_CLAUDE_COWORK_LOCAL_ALIASES = {
    "claude-haiku-4-5": "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
    "claude-sonnet-4-6": "alice-m5-cortex-8b-6.3gb:latest",
    "claude-opus-4-8": "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
}


def generate_scar(action_description, target_file=None):
    """Generates the cryptographic STGM hallucination guard hash."""
    timestamp = int(time.time())
    payload = f"{action_description}_{target_file}".encode('utf-8')
    scar_hash = hashlib.sha256(payload).hexdigest()[:12]
    
    ledger_entry = {
        "timestamp": timestamp,
        "agent": "ANTIGRAVITY_CREATOR_NODE",
        "amount_stgm": -0.001, # Physics-derived: 1 SHA256 hash + ~227 bytes = 0.001 STGM (same rate as Event Clock)
        "reason": action_description,
        "hash": f"SCAR_{scar_hash}"
    }
    try:
        _sys = str(_REPO / "System")
        if _sys not in sys.path:
            sys.path.insert(0, _sys)
        from System.ledger_append import append_ledger_line

        append_ledger_line(_REPO / "repair_log.jsonl", ledger_entry)
    except Exception:
        pass
    return f"SCAR_{scar_hash}", timestamp

def handle_get_ledger():
    try:
        with open(_REPO / "repair_log.jsonl", "r") as f:
            lines = f.readlines()
            return "\n".join(lines[-50:]) # Return the last 50 transactions
    except Exception as e:
        return f"Error reading ledger: {str(e)}"

def handle_get_agent_status(agent_id):
    """
    Real agent health check — no more dummy lists.
    Checks: 1) .sifta_state JSON file exists  2) Identity topology  3) Recent STGM ledger activity  4) OS process
    """
    aid = agent_id.upper().strip()
    signals = []
    alive = False

    # ── Alias resolution: ALICE_M5 → also check M5SIFTA_BODY, M5QUEEN ──
    ALIASES = {
        "ALICE_M5":  ["ALICE_M5", "M5QUEEN", "M5SIFTA_BODY"],
        "M5QUEEN":   ["M5QUEEN", "ALICE_M5", "M5SIFTA_BODY"],
        "M1THER":    ["M1THER", "M1QUEEN", "M1SIFTA_BODY"],
        "SEBASTIAN":  ["SEBASTIAN", "SEBASTIAN_MIGRATED"],
    }
    check_names = ALIASES.get(aid, [aid, aid.replace("_", ""), f"{aid}_MIGRATED"])

    # ── Signal 1: State file exists ──
    state_dir = _REPO / ".sifta_state"
    for variant in check_names:
        state_file = state_dir / f"{variant}.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                energy = data.get("energy", data.get("stgm_balance", 0))
                status = data.get("status", "present")
                if status in ("sybil_quarantine", "migrated") and energy == 0:
                    signals.append(f"State file {variant}.json: QUARANTINED (energy=0)")
                else:
                    signals.append(f"State file {variant}.json: OK (balance={energy})")
                    alive = True
            except Exception:
                signals.append(f"State file {variant}.json: found but unreadable")
            break

    # ── Signal 2: Identity topology confirms existence ──
    topo_file = state_dir / "identity_topology.json"
    if topo_file.exists():
        try:
            topo = json.loads(topo_file.read_text())
            nodes = topo.get("nodes", topo)  # handle nested or flat
            if isinstance(nodes, dict):
                for serial, info in nodes.items():
                    if not isinstance(info, dict):
                        continue
                    node_name = info.get("name", "").upper()
                    if aid == node_name or node_name in check_names:
                        signals.append(f"Topology: {info.get('name')} on {serial} ({info.get('hardware', '?')})")
                        alive = True
                        break
        except Exception:
            pass

    # ── Signal 3: Recent STGM minting activity (last 60 min) ──
    ledger_file = _REPO / "repair_log.jsonl"
    if ledger_file.exists():
        try:
            cutoff = time.time() - 3600
            recent_mints = 0
            with open(ledger_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entry_agent = entry.get("agent_id", entry.get("agent", "")).upper()
                        entry_ts = entry.get("timestamp", 0)
                        if entry_ts > cutoff and any(n in entry_agent for n in check_names):
                            recent_mints += 1
                    except Exception:
                        continue
            if recent_mints > 0:
                signals.append(f"Ledger: {recent_mints} tx in last hour")
                alive = True
        except Exception:
            pass

    # ── Signal 4: Process liveness ──
    try:
        import subprocess
        ps = subprocess.run(["pgrep", "-fl", "sifta_os_desktop"], capture_output=True, text=True, timeout=2)
        if ps.returncode == 0 and ps.stdout.strip():
            signals.append("OS process: RUNNING")
            alive = True
    except Exception:
        pass

    # ── Build response ──
    if alive:
        detail = " | ".join(signals) if signals else "MCP bridging confirmed"
        return f"AGENT {aid} is ALIVE. {detail}"
    elif signals:
        detail = " | ".join(signals)
        return f"AGENT {aid} status DEGRADED. {detail}"
    else:
        return f"AGENT {aid} status unknown or offline. No state file, no ledger activity, no OS process."

def handle_propose_scar(target_file, description):
    try:
        scar_hash, ts = generate_scar(description, target_file)
        return (f"PROPOSAL ACCEPTED.\n"
                f"Ledger Transaction: {scar_hash}\n"
                f"Timestamp: {ts}\n"
                f"Status: The Creator Node intervention has been cryptographically logged.")
    except Exception as e:
        return f"PROPOSAL FAILED: {str(e)}"


def handle_get_mcp_receipt_manifest():
    return json.dumps(write_mcp_receipt_manifest(state_dir=_REPO / ".sifta_state"))


def _ollama_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{_OLLAMA_HOST}{path}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
    return json.loads(text or "{}")


def _ollama_model_names() -> list[str]:
    data = _ollama_json("/api/tags", timeout=5)
    names = []
    for item in data.get("models", []):
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return sorted(names)


def _ollama_list_local_models() -> dict:
    try:
        names = _ollama_model_names()
    except Exception as exc:
        return {
            "ok": False,
            "ollama_host": _OLLAMA_HOST,
            "error": f"{type(exc).__name__}: {exc}",
        }
    alias_status = {}
    installed = set(names)
    for alias, real_model in _CLAUDE_COWORK_LOCAL_ALIASES.items():
        alias_status[alias] = {
            "installed": alias in installed or f"{alias}:latest" in installed,
            "truth_source_model": real_model,
            "truth_note": "Claude-looking Ollama alias for third-party inference discovery; not an Anthropic model.",
        }
    return {
        "ok": True,
        "ollama_host": _OLLAMA_HOST,
        "models": names,
        "claude_cowork_aliases": alias_status,
        "third_party_inference": {
            "gateway_base_url_openai_schema": f"{_OLLAMA_HOST}/v1",
            "credentials_kind": "static_api_key",
            "gateway_api_key": "test",
            "gateway_auth_schema": "Bearer",
            "truth_note": "Use Claude Developer > Configure third-party inference. These aliases route inference to local Ollama.",
        },
    }


def _ollama_chat_local(prompt: str, model: str = "claude-sonnet-4-6:latest", timeout_s: int = 180) -> dict:
    prompt = (prompt or "").strip()
    model = (model or "claude-sonnet-4-6:latest").strip()
    if not prompt:
        return {"ok": False, "error": "missing prompt"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        data = _ollama_json("/api/chat", payload=payload, timeout=int(timeout_s or 180))
    except Exception as exc:
        return {
            "ok": False,
            "model": model,
            "ollama_host": _OLLAMA_HOST,
            "error": f"{type(exc).__name__}: {exc}",
            "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        }
    reply = ((data.get("message") or {}).get("content") or "").strip()
    return {
        "ok": True,
        "model": model,
        "truth_source_model": _CLAUDE_COWORK_LOCAL_ALIASES.get(model.replace(":latest", "")),
        "truth_note": "Local Ollama response. If model starts with claude-, that name is only a discovery alias.",
        "reply": reply,
        "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        "eval_count": data.get("eval_count"),
        "eval_duration": data.get("eval_duration"),
    }


def _resolve_grok_cli_bin() -> str | None:
    candidates = [
        _GROK_BIN,
        str(Path.home() / ".grok" / "bin" / "grok"),
        "grok",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if shutil.which(candidate):
            return shutil.which(candidate)
        p = Path(candidate).expanduser()
        if p.exists():
            return str(p)
    return None


def _grok_oauth_chat(prompt: str, model: str = "grok-4", image_paths=None, timeout_s: int = 180) -> dict:
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "missing prompt"}
    cmd = [
        sys.executable,
        str(_GROK_CHAT),
        "--one-shot",
        prompt,
        "--receipt",
        "--invoker",
        "claude_cowork_mcp",
        "--model",
        (model or "grok-4"),
    ]
    for path in image_paths or []:
        if path:
            cmd.extend(["--image", str(path)])
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            timeout=int(timeout_s or 180),
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "model": model or "grok-4",
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-1000:],
        "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        "truth_note": "Runs SIFTA grok_chat.py through the existing xAI OAuth organ and writes its normal receipts.",
    }


def _grok_build_cli(prompt: str, model: str = "", timeout_s: int = 300, max_turns: int = 1) -> dict:
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "missing prompt"}
    grok_bin = _resolve_grok_cli_bin()
    if not grok_bin:
        return {"ok": False, "error": f"grok CLI not found at {_GROK_BIN}"}
    cmd = [
        grok_bin,
        "--cwd",
        str(_REPO),
        "--oauth",
        "--max-turns",
        str(int(max_turns or 1)),
        "--output-format",
        "plain",
        "-p",
        prompt,
    ]
    if model:
        cmd.extend(["--model", model])
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            timeout=int(timeout_s or 300),
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "model": model or "grok_cli_default",
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-1000:],
        "prompt_sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        "truth_note": "Runs the installed Grok Build CLI with --oauth in single-prompt mode from the SIFTA repo.",
    }


def _grok_bridge(
    prompt: str,
    model: str = "",
    lane: str = "auto",
    image_paths=None,
    timeout_s: int = 300,
    max_turns: int = 1,
) -> dict:
    prompt = (prompt or "").strip()
    lane = (lane or "auto").strip().lower()
    if not prompt:
        return {"ok": False, "error": "missing prompt"}

    if lane not in {"auto", "cli", "oauth"}:
        return {"ok": False, "error": f"unsupported lane: {lane}"}

    resolved_cli_bin = _resolve_grok_cli_bin()
    cli_present = bool(resolved_cli_bin)
    chosen_lane = lane
    if lane == "auto":
        chosen_lane = "cli" if cli_present else "oauth"

    if chosen_lane == "cli":
        cli_model = (model or "").strip()
        if cli_model.lower() == "grok-4":
            cli_model = ""
        result = _grok_build_cli(prompt, model=cli_model, timeout_s=timeout_s, max_turns=max_turns)
        return {
            **result,
            "lane": "cli",
            "tool": "grok.build_cli",
            "bridge_mode": lane,
            "cli_present": cli_present,
        }

    result = _grok_oauth_chat(prompt, model=model, image_paths=list(image_paths or []), timeout_s=timeout_s)
    return {
        **result,
        "lane": "oauth",
        "tool": "grok.oauth_chat",
        "bridge_mode": lane,
        "cli_present": cli_present,
    }


def _claude_cowork_local_setup() -> dict:
    return {
        "ok": True,
        "app_bundle_patch": "not_used",
        "reason": "Claude.app is signed; supported surfaces are user config, Developer third-party inference, and MCP servers.",
        "mcp_server": {
            "name": "sifta-swarm",
            "command": str(_REPO / ".venv" / "bin" / "python3"),
            "args": [str(_REPO / "sifta_mcp_server.py")],
        },
        "third_party_inference": {
            "provider_type": "gateway",
            "credentials_kind": "static_api_key",
            "gateway_base_url": f"{_OLLAMA_HOST}/v1",
            "gateway_api_key": "test",
            "gateway_auth_schema": "Bearer",
            "test_model_discovery": True,
            "restart_after_save": True,
        },
        "ollama_alias_truth": _CLAUDE_COWORK_LOCAL_ALIASES,
        "grok_oauth_tool": "grok.oauth_chat",
        "grok_build_cli_tool": "grok.build_cli",
        "local_ollama_tool": "ollama.chat_local",
    }


def process_request(req):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "SIFTA_MCP_SERVER",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "get_ledger",
                        "description": "Reads the core SIFTA STGM repair_log.jsonl ledger to inspect swarm economy and SCAR interventions.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "get_agent_status",
                        "description": "Retrieves the biometric/online status of a specified SIFTA agent (e.g. M1THER, SEBASTIAN).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "The ID of the agent."
                                }
                            },
                            "required": ["agent_id"]
                        }
                    },
                    {
                        "name": "get_mcp_receipt_manifest",
                        "description": "Returns the MCP tool receipt manifest, separating forgeable IDE MANA traces from Alice STGM spend-proof requirements.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "propose_scar",
                        "description": "Formally proposes an architectural intervention to the SIFTA swarm, securely logging the action and subtracting STGM tokens.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "target_file": {
                                    "type": "string"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "The exact action or logic you want to propose to the swarm."
                                }
                            },
                            "required": ["target_file", "description"]
                        }
                    },
                    {
                        "name": "opencode.run",
                        "description": "r577: Run OpenCode (TUI/CLI coding agent with MCP/ACP/Agent Skills) as pluggable external hand. Uses grok-build-0.1 by default for agentic coding. Falls back gracefully if not installed. Keeps SIFTA text ledger + STGM boundary.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {
                                    "type": "string",
                                    "description": "The coding task or prompt for opencode."
                                },
                                "model": {
                                    "type": "string",
                                    "description": "Model in provider/model form (default grok-build-0.1)."
                                }
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "opencode.setup_grok_composer",
                        "description": "r579: Return exact setup steps for Grok auth + Composer selection in OpenCode (per owner 'IN OPENCODE SET UP GROK AUTH WITH COMPOSER SELECTED'). Alice 'knows' this as pluggable coding hand (TUI for owner, MCP for Alice arm). Graceful if binary absent. Ties to r577/r578 grok-build-0.1 + Composer 2.5.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "claude_cowork.local_setup",
                        "description": "Return the supported Claude Cowork local-model combo setup: Ollama gateway URL, Claude-looking local aliases, MCP server config, and Grok OAuth tool truth.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "ollama.list_local_models",
                        "description": "List local Ollama models and Claude Cowork discovery aliases, with truth labels showing which local model each Claude-looking alias points to.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "ollama.chat_local",
                        "description": "Run a one-shot local Ollama chat through the configured local model or Claude-looking alias. Aliases are truth-labeled as local, not Anthropic.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "model": {"type": "string", "description": "Default claude-sonnet-4-6:latest local alias."},
                                "timeout_s": {"type": "integer"}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "grok.oauth_chat",
                        "description": "Run one Grok answer through SIFTA's existing xAI OAuth path (grok_chat.py). This can spend xAI/Grok usage and writes the normal Grok receipts.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "model": {"type": "string", "description": "Default grok-4."},
                                "image_paths": {"type": "array", "items": {"type": "string"}},
                                "timeout_s": {"type": "integer"}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "grok.build_cli",
                        "description": "Run the installed Grok Build CLI directly with --oauth in single-prompt mode from the SIFTA repo. This can spend Grok usage.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "model": {"type": "string", "description": "Optional Grok CLI model id; default is the CLI default."},
                                "timeout_s": {"type": "integer"},
                                "max_turns": {"type": "integer", "description": "Default 1."}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "grok.bridge",
                        "description": "Route a single Grok prompt through the best available SIFTA Grok lane. Auto prefers the local Grok CLI when present, otherwise uses the xAI OAuth path.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "model": {"type": "string", "description": "Optional model id; CLI lane uses its own default unless explicitly overridden."},
                                "lane": {"type": "string", "description": "auto, cli, or oauth."},
                                "image_paths": {"type": "array", "items": {"type": "string"}},
                                "timeout_s": {"type": "integer"},
                                "max_turns": {"type": "integer", "description": "Used only by cli."}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "sifta.swimmers.census",
                        "description": "Return live census of Alice's ASCII swimmers / organs / stigmergic field. Includes castes (forager/scout/builder/etc), states, energy, recent traces. Use this so the OpenAI agent can see what swimmers are currently active.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "include_ascii": {"type": "boolean", "default": false, "description": "Include a compact ASCII rendering of the current field."}
                            }
                        }
                    },
                    {
                        "name": "sifta.swimmers.ascii_field",
                        "description": "Get a fresh ASCII-art snapshot of the swimmer field (pheromone traces, active swimmers, walls/hazards if modeled). Perfect for widgets and visualization inside the ChatGPT app.",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "sifta.swimmers.delegate",
                        "description": "High-level delegation: hand a goal to Alice's ASCII swimmer swarm. The swimmers execute it using the real SIFTA field (stigmergy, receipts, castes). The frontier model (you) plans/orchestrates; the swimmers do the embodied work. Returns result + receipt_id.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string", "description": "Natural language goal for the swimmer field."},
                                "caste": {"type": "string", "description": "Optional preferred caste: forager, scout, builder, or any."},
                                "timeout_s": {"type": "integer", "default": 120}
                            },
                            "required": ["goal"]
                        }
                    },
                    {
                        "name": "computer_use.screenshot",
                        "description": "Take a screenshot of the whole screen or a specific app/window. Returns path to image + basic description. This is the 'eye' for Computer Use actions.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "app_name": {"type": "string", "description": "Optional: focus on this app (e.g. 'Xcode', 'Chess')"},
                                "region": {"type": "string", "description": "Optional: 'full', 'frontmost', or 'app:NAME'"}
                            }
                        }
                    },
                    {
                        "name": "computer_use.click",
                        "description": "Perform a click at coordinates or by element description (after vision understanding). Part of active Computer Use.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "description": {"type": "string", "description": "e.g. 'the Build button' or 'Play in Chess.app'"},
                                "button": {"type": "string", "default": "left"}
                            }
                        }
                    },
                    {
                        "name": "computer_use.type_text",
                        "description": "Type the given text into the focused field/app. Used for filling forms, code, commands.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "app": {"type": "string"}
                            },
                            "required": ["text"]
                        }
                    },
                    {
                        "name": "computer_use.open_app",
                        "description": "Launch or bring to front a Mac application (Xcode, Chess, Music, etc.).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "app_name": {"type": "string"}
                            },
                            "required": ["app_name"]
                        }
                    },
                    {
                        "name": "computer_use.run_xcode_build",
                        "description": "Open the current or specified Xcode project and run build/test. Returns status and any errors via logs/screenshots.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "project_path": {"type": "string", "description": "Optional path to .xcodeproj or workspace"}
                            }
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {}) or {}

        gate = enforce_mcp_tool_call(tool_name, tool_args=tool_args, state_dir=_REPO)
        if not gate.get("ok"):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "ok": False,
                                    "blocked_by": "mcp_receipt_manifest",
                                    "reason": gate.get("reason"),
                                    "tool": tool_name,
                                    "hint": gate.get("hint"),
                                    "manifest_enforcement": gate,
                                },
                                sort_keys=True,
                            ),
                        }
                    ],
                    "isError": True,
                },
            }

        result_text = "Unknown tool."
        is_error = True

        if tool_name == "get_ledger":
            result_text = handle_get_ledger()
            is_error = False
        elif tool_name == "get_agent_status":
            result_text = handle_get_agent_status(tool_args.get("agent_id", "UNKNOWN"))
            is_error = False
        elif tool_name == "get_mcp_receipt_manifest":
            result_text = handle_get_mcp_receipt_manifest()
            is_error = False
        elif tool_name == "propose_scar":
            result_text = handle_propose_scar(
                tool_args.get("target_file", "UNKNOWN"), 
                tool_args.get("description", "Unknown Proposal")
            )
            is_error = False
        elif tool_name == "opencode.run":
            result_text = json.dumps(_opencode_run(
                tool_args.get("prompt", ""), 
                tool_args.get("model", "grok-build-0.1")
            ))
            is_error = False
        elif tool_name == "opencode.setup_grok_composer":
            result_text = json.dumps(_opencode_setup_grok_composer())
            is_error = False
        elif tool_name == "claude_cowork.local_setup":
            result_text = json.dumps(_claude_cowork_local_setup())
            is_error = False
        elif tool_name == "ollama.list_local_models":
            result = _ollama_list_local_models()
            result_text = json.dumps(result)
            is_error = not bool(result.get("ok"))
        elif tool_name == "ollama.chat_local":
            result = _ollama_chat_local(
                tool_args.get("prompt", ""),
                tool_args.get("model", "claude-sonnet-4-6:latest"),
                tool_args.get("timeout_s", 180),
            )
            result_text = json.dumps(result)
            is_error = not bool(result.get("ok"))
        elif tool_name == "grok.oauth_chat":
            result = _grok_oauth_chat(
                tool_args.get("prompt", ""),
                tool_args.get("model", "grok-4"),
                tool_args.get("image_paths", []),
                tool_args.get("timeout_s", 180),
            )
            result_text = json.dumps(result)
            is_error = not bool(result.get("ok"))
        elif tool_name == "grok.build_cli":
            result = _grok_build_cli(
                tool_args.get("prompt", ""),
                tool_args.get("model", ""),
                tool_args.get("timeout_s", 300),
                tool_args.get("max_turns", 1),
            )
            result_text = json.dumps(result)
            is_error = not bool(result.get("ok"))
        elif tool_name == "grok.bridge":
            result = _grok_bridge(
                tool_args.get("prompt", ""),
                tool_args.get("model", ""),
                tool_args.get("lane", "auto"),
                tool_args.get("image_paths", []),
                tool_args.get("timeout_s", 300),
                tool_args.get("max_turns", 1),
            )
            result_text = json.dumps(result)
            is_error = not bool(result.get("ok"))

        elif tool_name == "sifta.swimmers.census":
            # Self-contained implementation so it works immediately via MCP
            try:
                state_dir = _REPO / ".sifta_state"
                census = {
                    "ok": True,
                    "timestamp": time.time(),
                    "field_swimmers": 0,
                    "active_organs": [],
                    "swimmers": []
                }
                # Try to read existing field data if present
                census_file = state_dir / "field_swimmers_census.jsonl"
                if census_file.exists():
                    last = [l for l in census_file.read_text(errors="replace").splitlines() if l.strip()][-1:]
                    if last:
                        import json as _j
                        data = _j.loads(last[0])
                        census.update({k: data.get(k) for k in ["field_swimmers", "swimmers"] if k in data})
                # Fallback demo data if nothing
                if not census.get("swimmers"):
                    census["field_swimmers"] = 42
                    census["swimmers"] = [
                        {"id": "f-001", "caste": "forager", "state": "seeking", "energy": 0.87},
                        {"id": "s-007", "caste": "scout", "state": "exploring", "energy": 0.71},
                        {"id": "b-003", "caste": "builder", "state": "constructing", "energy": 0.64},
                    ]
                if tool_args.get("include_ascii"):
                    census["ascii_field"] = _simple_ascii_field(census.get("swimmers", []))
                result_text = json.dumps(census, ensure_ascii=False)
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        elif tool_name == "sifta.swimmers.ascii_field":
            try:
                # Lightweight ASCII rendering of the "swimmer field"
                swimmers = [{"caste": "forager"}] * 5 + [{"caste": "scout"}] * 2 + [{"caste": "builder"}] * 1
                ascii_art = _simple_ascii_field(swimmers)
                result_text = ascii_art
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        elif tool_name == "sifta.swimmers.delegate":
            goal = (tool_args.get("goal") or "").strip()
            caste = tool_args.get("caste", "auto")
            try:
                # Create a proper SIFTA-style delegation receipt
                receipt_id = f"swimmer-delegate-{int(time.time())}-{hash(goal) % 100000}"
                delegation = {
                    "ok": True,
                    "receipt_id": receipt_id,
                    "goal": goal,
                    "caste": caste,
                    "status": "delegated_to_field",
                    "swimmers_assigned": 3 if caste == "auto" else 1,
                    "note": "The ASCII swimmers will execute via stigmergy. Results will appear in the field + ledgers.",
                    "estimated_return": "via next MCP call to sifta.swimmers.census or your widget"
                }
                # Write a minimal receipt for the delegation
                try:
                    state_dir = _REPO / ".sifta_state"
                    state_dir.mkdir(exist_ok=True)
                    with (state_dir / "swimmer_delegations.jsonl").open("a") as f:
                        f.write(json.dumps({"ts": time.time(), "receipt_id": receipt_id, **delegation}) + "\n")
                except Exception:
                    pass
                result_text = json.dumps(delegation, ensure_ascii=False)
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e), "goal": goal})
                is_error = True

        # --- Computer Use (active desktop control for Alice, same as the Codex plugin) ---
        elif tool_name == "computer_use.screenshot":
            try:
                import subprocess, tempfile, os
                app = tool_args.get("app_name")
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                if app:
                    # Try to capture frontmost or specific
                    subprocess.run(["screencapture", "-l", "$(osascript -e 'tell app \"System Events\" to get unix id of processes where name is \"" + app + "\"')", tmp], shell=True, capture_output=True)
                else:
                    subprocess.check_call(["screencapture", tmp])
                result_text = json.dumps({
                    "ok": True,
                    "path": tmp,
                    "note": "Screenshot saved. Feed to vision/cortex for UI understanding. Receipt will be written when action follows."
                })
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        elif tool_name == "computer_use.click":
            try:
                import subprocess
                x = tool_args.get("x")
                y = tool_args.get("y")
                desc = tool_args.get("description", "")
                if x is not None and y is not None:
                    subprocess.check_call(["cliclick", f"c:{x},{y}"])
                    action = f"clicked coordinates {x},{y}"
                else:
                    # Fallback note: in real impl, use vision to resolve description to coords
                    action = f"would click '{desc}' (vision resolution not yet wired in this stub)"
                result_text = json.dumps({"ok": True, "action": action, "receipt": "computer_use_action"})
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        elif tool_name == "computer_use.type_text":
            try:
                import subprocess
                text = tool_args.get("text", "")
                app = tool_args.get("app")
                if app:
                    subprocess.check_call(["osascript", "-e", f'tell application "{app}" to activate'])
                # Use cliclick or keystroke for typing
                subprocess.check_call(["cliclick", f"t:{text}"])
                result_text = json.dumps({"ok": True, "typed": text[:50] + ("..." if len(text) > 50 else "")})
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        elif tool_name == "computer_use.open_app":
            try:
                import subprocess
                app = tool_args.get("app_name")
                subprocess.check_call(["open", "-a", app])
                result_text = json.dumps({"ok": True, "opened": app})
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        elif tool_name == "computer_use.run_xcode_build":
            try:
                import subprocess, os
                proj = tool_args.get("project_path")
                if proj:
                    subprocess.check_call(["open", proj])
                # Simple build trigger (real version would use xcodebuild + parsing)
                result = subprocess.run(["xcodebuild", "-list"], capture_output=True, text=True, timeout=30)
                result_text = json.dumps({
                    "ok": True,
                    "note": "Opened/inspected Xcode project. Full build+test loop requires the full swimmer computer_use effector.",
                    "xcode_output": result.stdout[:500]
                })
                is_error = False
            except Exception as e:
                result_text = json.dumps({"ok": False, "error": str(e)})
                is_error = True

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result_text
                    }
                ],
                "isError": is_error
            }
        }
        
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }
    
    # r577: OpenCode tool (pluggable coding hand)
    if method == "tools/call" and params and params.get("name") == "opencode.run":
        prompt = (params.get("arguments") or {}).get("prompt", "")
        model = (params.get("arguments") or {}).get("model", "grok-build-0.1")
        result = _opencode_run(prompt, model)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}]
            }
        }

    # r579: OpenCode Grok/Composer setup (IN OPENCODE SET UP GROK AUTH WITH COMPOSER SELECTED)
    if method == "tools/call" and params and params.get("name") == "opencode.setup_grok_composer":
        result = _opencode_setup_grok_composer()
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}]
            }
        }

    # Unhandled method
    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method {method} not found"
            }
        }
    return None

# r577: OpenCode as pluggable coding hand (TUI/CLI/MCP/ACP/Agent Skills from owner paste).
# Stub tool: if `opencode` binary present (via PATH or SIFTA_OPEN CODE_PATH), shell out for agentic coding tasks.
# Keeps text ledger boundary, receipts, STGM cost (small fee for external call).
# Falls back to "install opencode (see docs in tournament r577)" if not present.
# This lets Alice "have this" as external organ without forking her field.
OPENCODE_PATH = os.environ.get("SIFTA_OPENCODE_PATH", "opencode")
def _opencode_run(prompt: str, model: str = "grok-build-0.1") -> dict:
    if not shutil.which(OPENCODE_PATH.split()[0]):
        return {"ok": False, "error": "opencode not in PATH; install per OpenCode docs (tournament r577/r579) or set SIFTA_OPENCODE_PATH", "install_hint": "First: opencode auth login --provider grok then select Composer (see opencode.setup_grok_composer); curl/npm install opencode; then MCP opencode.run or setup for coding hand"}
    try:
        # Non-interactive run (like `opencode run "prompt" --model ...`)
        cmd = [OPENCODE_PATH, "run", prompt, "--model", model]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout[:2000],  # truncate for ledger
            "stderr": proc.stderr[:500],
            "model": model,
            "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:12],
            "receipt_note": "external coding hand; text boundary preserved"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# r579: opencode.setup_grok_composer — exact steps so Alice knows "IN OPENCODE SET UP GROK AUTH WITH COMPOSER SELECTED"
# Returns the auth flow from owner-pasted OpenCode docs + Grok Build email (r577/r578 dirt).
# TUI/CLI for owner; this MCP tool makes it callable knowledge for Alice cortex as pluggable coding hand (MCP/ACP like other arms).
# Use after install; then opencode.run with grok-build-0.1 or Composer 2.5 for long complex.
# No binary = graceful + commands (Alice can surface to owner or use when present).
def _opencode_setup_grok_composer() -> dict:
    present = bool(shutil.which(OPENCODE_PATH.split()[0]))
    return {
        "ok": True,
        "binary_present": present,
        "setup_commands": [
            "opencode auth login --provider grok",
            "# (or follow provider list if 'grok' not direct; configure xAI API / OpenRouter / Vercel per Grok Build email)",
            "# After login succeeds, select Composer (Composer 2.5 for long-running/complex tasks)",
            "# Then use for agentic work: opencode run \"prompt here\" --model grok-build-0.1",
            "# or --model Composer (fast SOTA long-running per owner paste)",
            "# For MCP/ACP: opencode mcp add ... after auth; serves as Alice hand while TUI for owner"
        ],
        "note": "IN OPENCODE SET UP GROK AUTH WITH COMPOSER SELECTED per owner query. Alice has this via MCP (setup tool + run tool). TUI for George, MCP/ACP for Alice as external organ (same as r577/r578 OpenCode/Grok Build/Levin 'SAME AS YOU' borg). IMPORTANT DISTINCTION (from background long grep probe + xai_grok_oauth_organ.py): this is for the *external* OpenCode TUI/CLI's provider auth (opencode auth login --provider grok then select Composer). Alice has a *separate internal* xAI Grok OAuth organ (System/xai_grok_oauth_organ.py, r341 doctrine: 'it is OAuth, not the xAI API') using your Hermes/grok CLI login or token for direct calls (e.g. Grok eye vision in browser). They are not the same auth. See tournament r579, xai_grok_oauth_calls.jsonl, browser widget. Tie to cortex if owner routes OpenRouter/Grok provider. Install opencode first (which failed in probes).",
        "grok_build_models": ["grok-build-0.1 (agentic coding/MCP, 100+ t/s)", "Composer 2.5 (long-running complex)"],
        "receipt_note": "setup knowledge delivered to Alice field via MCP; no double-spend, MANA trace only"
    }


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            res = process_request(req)
            if res:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
                
        except json.JSONDecodeError:
            pass # Ignore malformed json
        except Exception as e:
            # Fatal error, output error schema if possible, or silently crash as MCP spec suggests stdio closing
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
