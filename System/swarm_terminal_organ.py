#!/usr/bin/env python3
"""
swarm_terminal_organ.py
Terminal execution organ for Alice.
Allowlisted commands only.
Writes SHA-256 chained receipts to tool_router_trace.jsonl
Bills STGM.
Refuses dangerous commands with audited refusal.
"""

import subprocess
import hashlib
import json
import time
from pathlib import Path

_TRACE = Path(".sifta_state/tool_router_trace.jsonl")
_ALLOWLIST = ["ls", "cat", "echo", "pwd", "python3 -c", "head", "tail", "date", "whoami"]
_DENY = ["rm", "sudo", "curl", "wget", "nc ", "bash -c", "sh -c", "eval", "exec"]

def _previous_hash():
    if not _TRACE.exists():
        return "genesis"
    last = ""
    with _TRACE.open() as f:
        for line in f:
            if line.strip():
                last = line.strip()
    if not last:
        return "genesis"
    try:
        prev = json.loads(last)
        return str(prev.get("hash") or prev.get("receipt_hash") or hashlib.sha256(last.encode()).hexdigest()[:16])
    except Exception:
        return hashlib.sha256(last.encode()).hexdigest()[:16]

def _append_receipt(row):
    row["ts"] = time.time()
    row["organ"] = "terminal"
    row["prev_hash"] = _previous_hash()
    row["hash"] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
    with _TRACE.open("a") as f:
        f.write(json.dumps(row) + "\n")

def run_terminal(command: str, cwd: str = None, timeout_s: int = 30):
    for d in _DENY:
        if d in command.lower():
            receipt = {"type": "TERMINAL_REFUSED", "command": command, "reason": "denied_pattern"}
            _append_receipt(receipt)
            return receipt
    allowed = False
    for a in _ALLOWLIST:
        if command.startswith(a):
            allowed = True
            break
    if not allowed:
        receipt = {"type": "TERMINAL_REFUSED", "command": command, "reason": "not_allowlisted"}
        _append_receipt(receipt)
        return receipt
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout_s, cwd=cwd)
        receipt = {
            "type": "TERMINAL_EXECUTION",
            "command": command,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
            "exit_code": result.returncode,
            "cost_stgm": 0.1
        }
        _append_receipt(receipt)
        return receipt
    except Exception as e:
        receipt = {"type": "TERMINAL_ERROR", "command": command, "error": str(e)[:200]}
        _append_receipt(receipt)
        return receipt

def run_terminal_shell(command: str, cwd: str = None, timeout_s: int = 30):
    return run_terminal(command, cwd, timeout_s)
