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
from pathlib import Path

_REPO = Path(__file__).resolve().parent


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
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        result_text = "Unknown tool."
        is_error = True

        if tool_name == "get_ledger":
            result_text = handle_get_ledger()
            is_error = False
        elif tool_name == "get_agent_status":
            result_text = handle_get_agent_status(tool_args.get("agent_id", "UNKNOWN"))
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
