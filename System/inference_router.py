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

import math
import json
import os
import socket
import urllib.request
import urllib.error
import time
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.sifta_inference_defaults import CANONICAL_OLLAMA_DEFAULT
except Exception:
    CANONICAL_OLLAMA_DEFAULT = "alice-m5-cortex-8b-6.3gb:latest"

try:
    from Kernel.inference_economy import record_inference_fee, calculate_fee
except ImportError:
    record_inference_fee = None
    calculate_fee = None

try:
    from Kernel.inference_economy import (
        LOG_PATH as _INFERENCE_LOG_PATH,
        append_ledger_line as _append_inference_ledger_line,
        validate_inference_transfer_receipt,
    )
except ImportError:
    _INFERENCE_LOG_PATH = None
    _append_inference_ledger_line = None
    validate_inference_transfer_receipt = None

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
    else CANONICAL_OLLAMA_DEFAULT
)

# Event 85: deterministic metabolic routing proof surface.
#
# These helpers are intentionally pure: no mesh-wide scalar, no network probes,
# and no implicit live state. Runtime callers may use them only after tests prove
# the selected cost vector behaves deterministically for synthetic candidates.
EVENT85_COST_VECTOR_VERSION = "EVENT85_COST_VECTOR_V1"
DEFAULT_EVENT85_COST_WEIGHTS: dict[str, float] = {
    "file_weight_mb": 0.05,
    "latency_ms": 1.0,
    "token_usage": 0.001,
}
_EVENT85_ROUTER_LEDGER = _REPO / ".sifta_state" / "event85_inference_router_decisions.jsonl"


@dataclass(frozen=True)
class InferenceRouteCandidate:
    """Synthetic or measured inference candidate used by the Event 85 cost vector."""

    candidate_id: str
    model: str
    endpoint: str = ""
    file_weight_mb: float = 0.0
    latency_ms: float = 0.0
    token_usage: float = 0.0
    utility: float = 0.0
    available: bool = True


def _candidate_mapping(candidate: InferenceRouteCandidate | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(candidate, InferenceRouteCandidate):
        return asdict(candidate)
    return dict(candidate)


def _finite_nonnegative(value: Any, field: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric, got {value!r}") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{field} must be finite and non-negative, got {value!r}")
    return numeric


def _cost_weights(weights: Mapping[str, float] | None = None) -> dict[str, float]:
    resolved = dict(DEFAULT_EVENT85_COST_WEIGHTS if weights is None else weights)
    for field, value in resolved.items():
        _finite_nonnegative(value, f"weight.{field}")
    return resolved


def event85_metabolic_cost(
    candidate: InferenceRouteCandidate | Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
) -> float:
    """Return the deterministic Event 85 cost for one route candidate.

    Formula from tournament §9:
      cost = w_m * file_weight_mb + w_l * latency_ms + w_t * token_usage

    Unknown candidate fields default to zero so tests can isolate one dimension.
    Weight values and candidate metrics must be finite and non-negative.
    """
    data = _candidate_mapping(candidate)
    resolved_weights = _cost_weights(weights)
    total = 0.0
    for field, weight in resolved_weights.items():
        total += weight * _finite_nonnegative(data.get(field, 0.0), field)
    return total


def score_event85_route_candidate(
    candidate: InferenceRouteCandidate | Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Attach Event 85 cost and net utility fields to one candidate."""
    data = _candidate_mapping(candidate)
    candidate_id = str(data.get("candidate_id") or data.get("id") or data.get("model") or "")
    if not candidate_id:
        raise ValueError("candidate_id is required")
    utility = float(data.get("utility", 0.0) or 0.0)
    if not math.isfinite(utility):
        raise ValueError(f"utility must be finite, got {utility!r}")
    cost = event85_metabolic_cost(data, weights)
    scored = dict(data)
    scored["candidate_id"] = candidate_id
    scored["cost_vector_version"] = EVENT85_COST_VECTOR_VERSION
    scored["cost_weights"] = _cost_weights(weights)
    scored["metabolic_cost"] = cost
    scored["net_utility"] = utility - cost
    return scored


def choose_event85_cost_vector_route(
    candidates: Iterable[InferenceRouteCandidate | Mapping[str, Any]],
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Choose the highest utility-minus-cost route with deterministic tie-breaks.

    Tie order:
      1. Higher net utility.
      2. Lower metabolic cost.
      3. Lexicographically smaller candidate_id.
    """
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        data = _candidate_mapping(candidate)
        if data.get("available", True) is False:
            continue
        scored.append(score_event85_route_candidate(data, weights))

    if not scored:
        raise ValueError("no available Event 85 route candidates")

    ranked = sorted(
        scored,
        key=lambda row: (
            -float(row["net_utility"]),
            float(row["metabolic_cost"]),
            str(row["candidate_id"]),
        ),
    )
    winner = dict(ranked[0])
    winner["decision_path"] = [str(row["candidate_id"]) for row in ranked]
    winner["decision_rule"] = "argmax(utility - metabolic_cost); tie=cost_then_candidate_id"
    return winner


def append_event85_route_decision(
    choice: Mapping[str, Any],
    ledger_path: str | Path | None = None,
    trace_id: str = "",
) -> dict[str, Any]:
    """Append a receipt-friendly Event 85 route choice to the organ ledger."""
    from System.ledger_append import append_jsonl_line

    target = Path(ledger_path) if ledger_path is not None else _EVENT85_ROUTER_LEDGER
    row = {
        "ts": time.time(),
        "event": "EVENT85_INFERENCE_ROUTE_DECISION",
        "schema": "SIFTA_EVENT85_INFERENCE_ROUTE_DECISION_V1",
        "trace_id": trace_id,
        "cost_vector_version": choice.get("cost_vector_version", EVENT85_COST_VECTOR_VERSION),
        "selected_candidate_id": choice.get("candidate_id"),
        "model": choice.get("model", ""),
        "endpoint": choice.get("endpoint", ""),
        "metabolic_cost": choice.get("metabolic_cost"),
        "net_utility": choice.get("net_utility"),
        "cost_weights": dict(choice.get("cost_weights", {})),
        "decision_path": list(choice.get("decision_path", [])),
        "decision_rule": choice.get("decision_rule", ""),
        "no_global_mesh_scalar": True,
    }
    append_jsonl_line(target, row)
    return row


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
            
            # Record only provider receipts that validate locally.
            if "fee_stgm" in receipt:
                if validate_inference_transfer_receipt is None or _append_inference_ledger_line is None or _INFERENCE_LOG_PATH is None:
                    raise RuntimeError("inference receipt validator unavailable; refusing ledger append")
                ok, reason, details = validate_inference_transfer_receipt(receipt)
                if not ok:
                    raise RuntimeError(f"remote inference receipt rejected: {reason} {details}")
                try:
                    _append_inference_ledger_line(_INFERENCE_LOG_PATH, receipt)
                    print(
                        f"  [STGM] Transfer Received: {receipt.get('fee_stgm')} STGM "
                        f"signed by {receipt.get('signing_node')} verified={reason}"
                    )
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
