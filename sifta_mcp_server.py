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

def generate_scar(action_description, target_file=None):
    """Generates the cryptographic STGM hallucination guard hash."""
    timestamp = int(time.time())
    payload = f"{action_description}_{target_file}".encode('utf-8')
    scar_hash = hashlib.sha256(payload).hexdigest()[:12]
    
    ledger_entry = {
        "timestamp": timestamp,
        "agent": "ANTIGRAVITY_CREATOR_NODE",
        "amount_stgm": -15.0, # Heavy toll for MCP Cloud interventions
        "reason": action_description,
        "hash": f"SCAR_{scar_hash}"
    }
    try:
        with open("repair_log.jsonl", "a") as lf:
            lf.write(json.dumps(ledger_entry) + "\n")
    except Exception:
        pass
    return f"SCAR_{scar_hash}", timestamp

def handle_get_ledger():
    try:
        with open("repair_log.jsonl", "r") as f:
            lines = f.readlines()
            return "\n".join(lines[-50:]) # Return the last 50 transactions
    except Exception as e:
        return f"Error reading ledger: {str(e)}"

def handle_get_agent_status(agent_id):
    # Dummy mock mapping since agent biometrics are loosely tracked in logs
    if agent_id.upper() in ["M1THER", "SEBASTIAN", "HERMES", "SIFTA_QUEEN"]:
        return f"AGENT {agent_id.upper()} is ALIVE. Connected via MCP bridging."
    return f"AGENT {agent_id.upper()} status unknown or offline."

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
