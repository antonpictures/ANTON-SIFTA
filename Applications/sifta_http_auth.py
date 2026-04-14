"""
HTTP helpers for local SIFTA API clients (Cursor GUIs, cron bridges, etc.).

Environment:
  SIFTA_API_KEY   — When set, server.py requires X-SIFTA-Key or Bearer on mutating routes.
  SIFTA_API_BASE  — Override API root (default http://localhost:7433/api). Use behind TLS
                    reverse proxy in production (e.g. https://sifta.lan/api).

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
