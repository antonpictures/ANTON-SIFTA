#!/usr/bin/env python3
"""
System/inference_router.py — Distributed Inference Architecture
──────────────────────────────────────────────────────────────────
Thermally-aware load-balancer for Ollama between the M1THER edge node
(Mac Mini 8GB) and ALICE_M5 (MacBook Pro 24GB).

BISHOP Closed Loop (Epoch 4):
  The thermal cortex reads substrate temperature via `pmset -g therm`.
  If the local node is overheating (thermal_warning ≥ 2 OR perf_warning ≥ 1),
  inference is force-routed to the remote node — the organism rests its hot
  limb and uses the cooler one. No human in the loop. This is biological
  self-regulation: a fever organism shifting load off the inflamed substrate.

Node auto-detection: reads hostname to decide which IPs are "local" vs
"remote". Works identically deployed on either M1 or M5.

Economy: if the airgap is crossed, Kernel/inference_economy mints
`BORROWED_INFERENCE` into the STGM ledger.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.request
import urllib.error
import time
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from Kernel.inference_economy import record_inference_fee, calculate_fee
except ImportError:
    record_inference_fee = None
    calculate_fee = None

# ── Thermal Cortex import (the BISHOP closed-loop sensor) ────────────
try:
    from System.swarm_thermal_cortex import is_overheating as _is_overheating
    _THERMAL_CORTEX_AVAILABLE = True
except ImportError:
    _is_overheating = lambda: False  # type: ignore
    _THERMAL_CORTEX_AVAILABLE = False

# ── Node-aware endpoint resolution ──────────────────────────────────
# Instead of hardcoding "LOCAL = M5", detect which machine we're on.
_M1_OLLAMA = "http://127.0.0.1:11434/api/generate"      # when running ON M1
_M5_OLLAMA = "http://192.168.1.100:11434/api/generate"   # M5 via LAN (Mac.lan)
# The M5 also listens locally at 127.0.0.1 when you're ON M5.

def _detect_node() -> str:
    """Return 'M1' or 'M5' based on hostname / env hint."""
    hint = os.environ.get("SIFTA_NODE_ID", "").upper()
    if hint in ("M1", "M1THER"):
        return "M1"
    if hint in ("M5", "ALICE_M5"):
        return "M5"
    hostname = socket.gethostname().lower()
    # M1 Mac Mini hostnames: macmini, georges-mac-mini, etc.
    if "macmini" in hostname or "mini" in hostname:
        return "M1"
    return "M5"  # default: assume M5 (the 24GB queen)

_THIS_NODE = _detect_node()

# Resolve local/remote URLs based on which node we're actually on.
if _THIS_NODE == "M1":
    LOCAL_URL  = _M1_OLLAMA                              # 127.0.0.1 on M1
    REMOTE_URL = _M5_OLLAMA                              # M5 across LAN
    BORROWER_ID = "M1THER_EDGE"
else:
    LOCAL_URL  = "http://127.0.0.1:11434/api/generate"   # 127.0.0.1 on M5
    REMOTE_URL = "http://192.168.1.71:11434/api/generate" # M1 across LAN (Macmini.lan)
    BORROWER_ID = "M5_CORE_ORGANS"

# Legacy aliases for callers that import by old name
LOCAL_M5_URL = LOCAL_URL
REMOTE_M1_URL = REMOTE_URL

# ── Thermal routing log (silent, append-only) ────────────────────────
_THERMAL_LOG = _REPO / ".sifta_state" / "thermal_routing_decisions.jsonl"


def _log_thermal_reroute(reason: str, from_url: str, to_url: str) -> None:
    """Append a single line so the Architect can audit thermal reroutes."""
    try:
        _THERMAL_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "node": _THIS_NODE,
            "reason": reason,
            "from": from_url,
            "to": to_url,
        }
        with open(_THERMAL_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def ping_endpoint(url: str, payload: dict = None, timeout: float = 2.0) -> tuple:
    """Pings an Ollama endpoint and returns (url, elapsed_time, response_json)."""
    start = time.time()
    try:
        base_url = url.replace("/api/generate", "/api/tags")
        req = urllib.request.Request(base_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            elapsed = time.time() - start
            return url, elapsed, {}
    except Exception:
        return url, float('inf'), {}


def get_best_endpoint() -> str:
    """Thermally-aware NPU selection — the BISHOP closed loop.

    Decision tree:
      1. If local substrate is overheating → force remote (organism rests).
      2. Else if local Ollama responds within 500ms → use local.
      3. Else if remote responds within 1s → use remote.
      4. Else → fall back to local (might just be loading a model).
    """
    # ── BISHOP GATE: Thermal override ────────────────────────────────
    if _THERMAL_CORTEX_AVAILABLE and _is_overheating():
        _, remote_time, _ = ping_endpoint(REMOTE_URL, timeout=1.5)
        if remote_time < 1.5:
            _log_thermal_reroute(
                "LOCAL_OVERHEATING — routing to cooler substrate",
                LOCAL_URL, REMOTE_URL,
            )
            return REMOTE_URL
        # Remote also unreachable — fall through to local despite heat
        # (better to run hot than not run at all).

    # ── Standard latency-based selection ─────────────────────────────
    _, local_time, _ = ping_endpoint(LOCAL_URL, timeout=0.5)
    if local_time < 0.5:
        return LOCAL_URL

    _, remote_time, _ = ping_endpoint(REMOTE_URL, timeout=1.0)
    if remote_time < 1.0:
        return REMOTE_URL

    return LOCAL_URL


def execute_query(url: str, payload: bytes, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def route_inference(payload_dict: dict, prefer_local: bool = False, timeout: int = 120) -> str:
    """
    Core function for organs to call instead of raw urllib.
    Returns the parsed text response from Ollama.
    """
    target_url = LOCAL_URL if prefer_local else get_best_endpoint()
    payload_bytes = json.dumps(payload_dict).encode("utf-8")

    try:
        res = execute_query(target_url, payload_bytes, timeout=timeout)
        text = res.get("response", "").strip()

        # Stigmergic Economy tie-in — charge for cross-node inference
        is_remote = ("127.0.0.1" not in target_url)
        if is_remote and record_inference_fee and text:
            model = payload_dict.get("model", "unknown")
            tokens_used = res.get("eval_count", 0) + res.get("prompt_eval_count", 0)
            if tokens_used <= 0:
                tokens_used = len(text.split()) * 2

            fee = calculate_fee(tokens_used, model) if calculate_fee else 0.0
            if fee > 0:
                record_inference_fee(
                    borrower_id=BORROWER_ID,
                    lender_node_ip=target_url.split("//")[1].split(":")[0],
                    fee_stgm=fee,
                    model=model,
                    tokens_used=tokens_used,
                    file_repaired="inference_router.py"
                )

        return text
    except Exception as e:
        # Fallback to the other node
        fallback_url = LOCAL_URL if target_url == REMOTE_URL else REMOTE_URL
        try:
            res = execute_query(fallback_url, payload_bytes, timeout=timeout)
            return res.get("response", "").strip()
        except Exception as fallback_e:
            raise RuntimeError(f"Swarm inference failed on both nodes: [1] {e} [2] {fallback_e}")
