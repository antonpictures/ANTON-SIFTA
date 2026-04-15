"""
HTTP helpers for local SIFTA API clients (Cursor GUIs, cron bridges, etc.).

Environment:
  SIFTA_API_KEY   — When set, server.py requires X-SIFTA-Key or Bearer on mutating routes.
  SIFTA_REQUIRE_AUTH — If 1/true/on, FastAPI startup fails unless SIFTA_API_KEY is set (no open API).
  SIFTA_API_BASE  — Override API root (default http://localhost:7433/api). Use behind TLS
                    reverse proxy in production (e.g. https://sifta.lan/api).

Related (server / wormhole — see server.py):
  SIFTA_MESH_HMAC, SIFTA_WORMHOLE_USE_TLS, SIFTA_WORMHOLE_TLS_INSECURE, SIFTA_WORMHOLE_CAFILE,
  SIFTA_RECEIVE_SOUL_REQUIRE_PKI, SIFTA_RECEIVE_SOUL_MAX_BYTES (default 10MiB),
  SIFTA_WORMHOLE_DEED_MAX_SKEW_SEC (deed timestamp anti-replay, default 900),
  SIFTA_WORMHOLE_ALLOW_LOOPBACK, SIFTA_WORMHOLE_ALLOW_PUBLIC_IP (wormhole egress policy),
  SIFTA_STRICT_PKI_REGISTRY — refuse boot if node_pki_registry.json fails validation,
  SIFTA_RATE_LIMIT_PER_MIN — max mutating requests per client IP per minute (0 = off).
  SIFTA_TRUST_PROXY — if 1/true/on, rate limits use first X-Forwarded-For hop (set only behind your own proxy).
  SIFTA_PROTECT_GET — require API key on GET /api/* except SIFTA_GET_PROTECT_ALLOW (comma paths).

Hardening backlog (not solved here):
  - Wormhole / receive_soul still assume LAN trust unless you add mTLS or VPN.
  - Autonomous git writers (this repo, swarm_network_ledger) need branch locks + review hooks.
  - repair_log integrity assumes OS file permissions; root on box bypasses crypto.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

_DEFAULT_API_BASE = "http://localhost:7433/api"


def get_sifta_api_base() -> str:
    """Base URL for SIFTA HTTP API (includes /api path segment)."""
    return os.environ.get("SIFTA_API_BASE", _DEFAULT_API_BASE).rstrip("/")


def sifta_headers(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(extra or {})
    key = os.environ.get("SIFTA_API_KEY", "").strip()
    if key:
        out["X-SIFTA-Key"] = key
    return out
