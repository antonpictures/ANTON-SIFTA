#!/usr/bin/env python3
"""
System/inference_router.py — Distributed Inference Architecture
──────────────────────────────────────────────────────────────────
Load-balances Ollama `/api/generate` packets between the local M5 NPU 
and the remote M1 Edge Node. 

If the airgap is crossed to M1, it leverages Kernel/inference_economy.py
to mint `BORROWED_INFERENCE` into the STGM Swarm Economy.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

LOCAL_M5_URL = "http://127.0.0.1:11434/api/generate"
REMOTE_M1_URL = "http://192.168.1.71:11434/api/generate"

BORROWER_ID = "M5_CORE_ORGANS"

def ping_endpoint(url: str, payload: dict, timeout=2.0) -> tuple[str, float, dict]:
    """Pings an Ollama endpoint and returns (url, elapsed_time, response_json)."""
    start = time.time()
    try:
        # Override num_predict for a fast ping if we just want to test TTFT,
        # but since we don't have a separate ping, we just execute the real query.
        # However, to avoid double-execution, we don't race the ACTUAL query.
        # We will use /api/tags to discover if the node is online.
        base_url = url.replace("/api/generate", "/api/tags")
        req = urllib.request.Request(base_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            elapsed = time.time() - start
            return url, elapsed, {}
    except Exception:
        return url, float('inf'), {}

def get_best_endpoint() -> str:
    """Finds the fastest available NPU."""
    # First try local M5 because it has 24GB VRAM and is free.
    _, local_time, _ = ping_endpoint(LOCAL_M5_URL, {}, timeout=0.5)
    if local_time < 0.5:
        return LOCAL_M5_URL
    
    # If local is down or slow, try remote M1
    _, remote_time, _ = ping_endpoint(REMOTE_M1_URL, {}, timeout=1.0)
    if remote_time < 1.0:
        return REMOTE_M1_URL
        
    # Default to local if both are failing, it might just be busy
    return LOCAL_M5_URL

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
    Core function for organs to call instead of urllib request.
    It returns the parsed text response from Ollama.
    """
    target_url = LOCAL_M5_URL if prefer_local else get_best_endpoint()
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    
    try:
        res = execute_query(target_url, payload_bytes, timeout=timeout)
        text = res.get("response", "").strip()
        
        # Stigmergic Economy tie-in
        if target_url == REMOTE_M1_URL and record_inference_fee and text:
            # We borrowed compute from M1.
            model = payload_dict.get("model", "unknown")
            tokens_used = res.get("eval_count", 0) + res.get("prompt_eval_count", 0)
            if tokens_used <= 0:
                # Estimate if Ollama didn't return counts
                tokens_used = len(text.split()) * 2
                
            fee = calculate_fee(tokens_used, model) if calculate_fee else 0.0
            if fee > 0:
                record_inference_fee(
                    borrower_id=BORROWER_ID,
                    lender_node_ip="192.168.1.71",
                    fee_stgm=fee,
                    model=model,
                    tokens_used=tokens_used,
                    file_repaired="inference_router.py"
                )
                
        return text
    except Exception as e:
        # Fallback to the other node if the first one failed during actual inference
        fallback_url = LOCAL_M5_URL if target_url == REMOTE_M1_URL else REMOTE_M1_URL
        try:
            res = execute_query(fallback_url, payload_bytes, timeout=timeout)
            return res.get("response", "").strip()
        except Exception as fallback_e:
            raise RuntimeError(f"Swarm inference failed on both nodes: [1] {e} [2] {fallback_e}")
