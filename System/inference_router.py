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

# ── Model sovereignty table ───────────────────────────────────────────
# Models that require the REMOTE node (too large for local RAM).
# Key: model name fragment (lowercase). Value: preferred endpoint.
# This is the ONLY place you need to update when adding new models.
_REMOTE_ONLY_MODELS: dict[str, str] = {
    # M1 (8 GB) → M5 (24 GB) delegations
    "gemma4":           REMOTE_URL if _THIS_NODE == "M1" else LOCAL_URL,
    "gemma3":           REMOTE_URL if _THIS_NODE == "M1" else LOCAL_URL,
    "llama4":           REMOTE_URL if _THIS_NODE == "M1" else LOCAL_URL,
    "llama3.3":         REMOTE_URL if _THIS_NODE == "M1" else LOCAL_URL,
    "deepseek-coder:6": REMOTE_URL if _THIS_NODE == "M1" else LOCAL_URL,
    "maverick":         REMOTE_URL if _THIS_NODE == "M1" else LOCAL_URL,
}

# Replacement model: if remote is down and the requested model can't run
# locally, fall back to this local model rather than crashing.
_LOCAL_FALLBACK_MODEL = (
    "alice-phc-0.8b-cure:latest" if _THIS_NODE == "M1"
    else "gemma4:latest"
)


def _get_local_model_names() -> list[str]:
    """Live probe of local Ollama — returns list of installed model names."""
    try:
        tags_url = LOCAL_URL.replace("/api/generate", "/api/tags")
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read())
            return [m["name"].lower() for m in data.get("models", [])]
    except Exception:
        return []


def _resolve_endpoint_for_model(model: str) -> str | None:
    """Return the correct Ollama endpoint for the requested model.

    Priority:
      1. Model is in _REMOTE_ONLY_MODELS → use that endpoint directly.
      2. Model is available locally (live probe) → use LOCAL_URL.
      3. Model name not recognized locally → use REMOTE_URL.
      4. Returns None only if model fragment cannot be matched anywhere
         (caller should fall back to _LOCAL_FALLBACK_MODEL).
    """
    model_lower = model.lower()

    # Check sovereign routing table first (large models)
    for fragment, endpoint in _REMOTE_ONLY_MODELS.items():
        if fragment in model_lower:
            _log_thermal_reroute(
                f"MODEL_SOVEREIGNTY: {model} requires {endpoint}",
                LOCAL_URL, endpoint,
            )
            return endpoint

    # Model not in sovereignty table — check if it's installed locally
    local_models = _get_local_model_names()
    for lm in local_models:
        if model_lower in lm or lm in model_lower:
            return LOCAL_URL  # installed here, run locally

    # Not found locally → route to remote (it might be there)
    return REMOTE_URL

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

    Model-aware routing (automatic, no human involvement):
      - If payload contains a model that doesn't fit locally, auto-routes
        to the remote node and charges STGM via inference_economy.
      - prefer_local=True bypasses model routing (emergency override only).
    """
    requested_model = payload_dict.get("model", "")

    if prefer_local:
        target_url = LOCAL_URL
    elif requested_model:
        # Let the swarm decide based on model identity
        target_url = _resolve_endpoint_for_model(requested_model) or get_best_endpoint()
    else:
        target_url = get_best_endpoint()

    # If model is remote-only and remote is down, substitute local fallback
    if target_url == REMOTE_URL:
        _, remote_time, _ = ping_endpoint(REMOTE_URL, timeout=1.5)
        if remote_time == float('inf'):  # remote unreachable
            _log_thermal_reroute(
                f"REMOTE_DOWN: substituting {_LOCAL_FALLBACK_MODEL} for {requested_model}",
                REMOTE_URL, LOCAL_URL,
            )
            target_url = LOCAL_URL
            payload_dict = {**payload_dict, "model": _LOCAL_FALLBACK_MODEL}

    payload_bytes = json.dumps(payload_dict).encode("utf-8")

    try:
        is_remote = ("127.0.0.1" not in target_url)
        
        # If remote, we must call the SIFTA server's joule receipt wrapper (port 8000)
        # to get a physically signed receipt, NOT the raw Ollama port (11434).
        if is_remote:
            receipt_target_url = target_url.replace(":11434/api/generate", ":8000/api/inference_joule_receipt")
            
            # Send payload with x-sifta-borrower header
            req = urllib.request.Request(
                receipt_target_url,
                data=payload_bytes,
                headers={"Content-Type": "application/json", "x-sifta-borrower": BORROWER_ID},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                receipt = json.loads(resp.read().decode("utf-8"))
                
            res = receipt.get("ollama_response", {})
            text = res.get("response", "").strip()
            
            # Record the signed receipt from the provider
            if record_inference_fee and "fee_stgm" in receipt:
                from Kernel.inference_economy import append_ledger_line, LOG_PATH
                try:
                    append_ledger_line(LOG_PATH, receipt)
                    print(f"  [STGM] Transfer Received: {receipt.get('fee_stgm')} STGM signed by {receipt.get('signing_node')}")
                except Exception as e:
                    print(f"  [ECONOMY] Failed to record signed transfer receipt: {e}")
                    
        else:
            # Local: execute normally
            res = execute_query(target_url, payload_bytes, timeout=timeout)
            text = res.get("response", "").strip()

        return text
    except Exception as e:
        # Fallback to the other node
        fallback_url = LOCAL_URL if target_url == REMOTE_URL else REMOTE_URL
        try:
            res = execute_query(fallback_url, payload_bytes, timeout=timeout)
            return res.get("response", "").strip()
        except Exception as fallback_e:
            raise RuntimeError(f"Swarm inference failed on both nodes: [1] {e} [2] {fallback_e}")
