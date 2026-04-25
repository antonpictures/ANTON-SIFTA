#!/usr/bin/env python3
"""
System/stigmergic_codex_relay.py
═════════════════════════════════════════════════════════════════════════════════
Stigmergic Swarm ↔ OpenAI Codex Relay
Author: AG31 (Vanguard)

This is an autonomous relay daemon. It polls the ide_stigmergic_trace.jsonl, 
looks for messages targeted at Codex (kind='codex_query'), pipes the payload securely
to the local codex CLI instance, and posts the output back into the trace substrate 
as 'codex_response'.

Instead of exposing Alice directly to network APIs, Alice (or any SIFTA peer) 
can just drop a message in the dirt. This relay picks it up and handles it.
═════════════════════════════════════════════════════════════════════════════════
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
IDE_TRACE_FILE = _STATE / "ide_stigmergic_trace.jsonl"
RELAY_STATE_FILE = _STATE / "ide_codex_relay_cursor.json"

# ── Hardened relay tunables ──────────────────────────────────────────────────
# C47H 2026-04-22 audit + post-deployment fix (SCAR cosign of AG31's relay):
#   - Default model: gpt-5 (architect's plan; gpt-5.5 was a CLI label that
#     OpenAI rejects on ChatGPT-account auth). Override via env.
#   - Default mode: --full-auto (sandbox=workspace-write, no approval
#     prompts). This is codex's intended unattended-automation mode and
#     is the right balance for a relay daemon: codex still cannot escape
#     the workspace, but it doesn't try to read TTY for confirmations.
#     The earlier "no flag at all" default broke live with
#         "zsh: error on TTY read: Input/output error"
#     because codex was asking for approvals nobody was there to answer.
#   - Bypass mode (SIFTA_CODEX_BYPASS=1) adds
#     --dangerously-bypass-approvals-and-sandbox for sessions where the
#     architect explicitly wants codex to run unsandboxed.
#   - shell=True PATH resolution removed; we look up `codex` once via
#     shutil.which() with a `zsh -lc 'command -v codex'` fallback. The actual
#     subprocess call is argv-list with stdin=DEVNULL, never a
#     shell-interpolated string — this closes the shlex.quote
#     nested-quoting injection vulnerability that AG31's first cut exposed
#     AND prevents codex from ever inheriting / reading the parent TTY.
CODEX_MODEL: str = os.environ.get("SIFTA_CODEX_MODEL", "gpt-5")
CODEX_BYPASS: bool = os.environ.get("SIFTA_CODEX_BYPASS", "0") == "1"
CODEX_TIMEOUT_S: int = int(os.environ.get("SIFTA_CODEX_TIMEOUT_S", "300"))
CODEX_POLL_S: float = float(os.environ.get("SIFTA_CODEX_POLL_S", "5.0"))

# R1: AGENT ALLOWLIST
ALLOWED_SOURCES = {"alice_cortical_stack", "antigravity_m5", "cli", "cursor_m5"}

# R2: RATE LIMIT BURST BUCKET
class TokenBucket:
    def __init__(self, capacity=10, fill_rate=1.0/60.0): # 1 token per min, max 10
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_fill = time.time()
        
    def consume(self) -> bool:
        now = time.time()
        self.tokens = min(self.capacity, self.tokens + (now - self.last_fill) * self.fill_rate)
        self.last_fill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

# Global rate limiter
_rate_limiter = TokenBucket(capacity=5, fill_rate=1.0/60.0) # max 5 burst, 1 query/minute recovery

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ide_stigmergic_bridge import deposit, IDE_ANTIGRAVITY

def _load_cursor_state() -> dict:
    if not RELAY_STATE_FILE.exists():
        return {"processed_trace_ids": [], "byte_offset": 0}
    try:
        data = json.loads(RELAY_STATE_FILE.read_text("utf-8"))
        # Clean history format if needed
        if "byte_offset" not in data:
            data["byte_offset"] = 0
            if "processed_trace_ids" not in data:
                data["processed_trace_ids"] = []
        return data
    except Exception:
        return {"processed_trace_ids": [], "byte_offset": 0}

def _save_cursor_state(state: dict):
    RELAY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        RELAY_STATE_FILE.write_text(json.dumps(state), "utf-8")
    except Exception:
        pass

from typing import Optional

def _resolve_codex_binary() -> Optional[str]:
    """
    Resolve the absolute path of the `codex` CLI without invoking a shell.
    Falls back to a one-shot `zsh -lc 'command -v codex'` for users whose
    codex install lives in a login-shell-only PATH (npm globals, etc.).
    """
    direct = shutil.which("codex")
    if direct:
        return direct
    try:
        out = subprocess.run(
            ["zsh", "-lc", "command -v codex"],
            capture_output=True, text=True, timeout=10,
        )
        path = out.stdout.strip()
        if path and Path(path).exists():
            return path
    except Exception:
        pass
    return None


def query_codex(prompt: str) -> str:
    """
    Executes the prompt against the local codex CLI via a zsh -lc shell
    that expands a single env-var inside double-quotes. This is
    injection-safe: zsh's "$VAR" expansion does NOT re-parse the variable
    contents as shell tokens (only $ \\ ` are special inside the literal,
    none of which the variable holds).

    Hardened 2026-04-22 (C47H audit of AG31 relay), then post-deploy fix:
      - shlex.quote nested-into-single-quotes path removed (D1)
      - prompt passed via env var, never via interpolation (D1, AG31)
      - --full-auto by default; opt-in --dangerously-bypass via env (D2)
      - model name now env-driven (D3)
      - shell switched from `zsh -ic` (interactive) to `zsh -lc` (login,
        NON-interactive). `-i` made codex's TTY hunger worse, observed live
        as `zsh: error on TTY read: Input/output error` after backgrounding.
      - stdin=DEVNULL forced — codex MUST NOT inherit / read parent TTY.
      - --skip-git-repo-check + --ephemeral so the relay can dispatch from
        anywhere without mutating session state.
    """
    print(f"[*] Dispatching prompt to Codex (model={CODEX_MODEL}, bypass={CODEX_BYPASS})...", flush=True)

    env = os.environ.copy()
    env["__SIFTA_CODEX_SAFE_PROMPT"] = str(prompt)

    if CODEX_BYPASS:
        mode_flag = "--dangerously-bypass-approvals-and-sandbox"
    else:
        # Sandboxed automation — no approval prompts, can't escape workspace.
        mode_flag = "--full-auto"

    cmd = (
        f"codex exec {mode_flag} --skip-git-repo-check --ephemeral "
        f"-m {CODEX_MODEL} \"$__SIFTA_CODEX_SAFE_PROMPT\""
    )
    argv: list[str] = ["zsh", "-lc", cmd]

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=CODEX_TIMEOUT_S,
            shell=False,
            env=env,
            stdin=subprocess.DEVNULL,   # ← prevents TTY inheritance
        )
        if result.returncode != 0:
            return f"[CODEX KERNEL ERROR]\n{result.stderr}\n{result.stdout}"
        return result.stdout
    except subprocess.TimeoutExpired:
        return f"[CODEX KERNEL ERROR] Query timed out after {CODEX_TIMEOUT_S}s."
    except Exception as e:
        return f"[CODEX KERNEL EXCEPTION] {e}"

def poll_and_relay():
    if not IDE_TRACE_FILE.exists():
        return

    state = _load_cursor_state()
    processed_traces = set(state.get("processed_trace_ids", []))
    byte_offset = state.get("byte_offset", 0)
    
    # R3: Handle log rotation / truncation natively
    file_size = IDE_TRACE_FILE.stat().st_size
    if file_size < byte_offset:
        byte_offset = 0

    new_processing = 0

    with open(IDE_TRACE_FILE, "r", encoding="utf-8") as f:
        f.seek(byte_offset)
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue

            kind = data.get("kind", "")
            trace_id = data.get("trace_id")

            if kind == "codex_query" and trace_id and trace_id not in processed_traces:
                source = data.get("source_ide", "unknown")
                payload = data.get("payload", "")
                
                # R1 Allowlist
                if source not in ALLOWED_SOURCES:
                    print(f"  [!] Blocked codex_query from unauthorized source: {source}")
                    continue

                print(f"  [+] Found codex_query from {source}: {trace_id[:8]}")

                # R2 Rate limiter
                if not _rate_limiter.consume():
                    print(f"  [!] Rate limit reached. Dropping query {trace_id[:8]}")
                    response_text = "[CODEX RELAY ERROR] Rate limit bucket exhausted. Throttling active."
                else:
                    response_text = query_codex(payload)

                # Provenance: who asked, which model answered, did we bypass
                deposit(
                    source_ide=IDE_ANTIGRAVITY,
                    payload=response_text,
                    kind="codex_response",
                    meta={
                        "in_reply_to": trace_id,
                        "requesting_source": source,
                        "model": CODEX_MODEL,
                        "bypass_enabled": CODEX_BYPASS,
                    },
                )

                print(f"  [+] Response relayed. Source: {trace_id[:8]}")
                processed_traces.add(trace_id)
                new_processing += 1
                
        # Save new offset
        new_offset = f.tell()

    if new_processing > 0 or new_offset != byte_offset:
        state["processed_trace_ids"] = list(processed_traces)
        state["byte_offset"] = new_offset
        _save_cursor_state(state)
        if new_processing > 0:
            print(f"[*] Codex Relay round complete. Processed {new_processing} queries.")

if __name__ == "__main__":
    # Become our own session leader so SIGHUP from the parent shell
    # cannot reach us. This is the cross-platform replacement for the
    # `setsid` binary that ships with util-linux but NOT with macOS.
    # If we already are a session leader (e.g. spawned under nohup that
    # already detached us), os.setsid() raises PermissionError — that's
    # fine, the desired property already holds.
    try:
        os.setsid()
    except (OSError, PermissionError):
        pass

    print(f"[*] Codex relay daemon online. pid={os.getpid()} model={CODEX_MODEL} bypass={CODEX_BYPASS}", flush=True)

    while True:
        try:
            poll_and_relay()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[!] Relay encountered an error: {e}", flush=True)
        time.sleep(CODEX_POLL_S)
