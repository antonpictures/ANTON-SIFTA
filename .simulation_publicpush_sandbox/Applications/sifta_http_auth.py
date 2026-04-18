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
  SIFTA_TERMINAL_OPEN — bypass API key for GET /api/terminal (dev only).
  SIFTA_MESSENGER_THREAD_OPEN — bypass API key for GET /messenger/thread and GET /api/messenger/thread.
  SIFTA_EDITOR_OPEN — bypass API key for GET /editor (bundled HTML).
  SIFTA_QUIET_BOOT_WARNINGS — suppress optional startup hardening hints.
  SIFTA_MESSENGER_INTEGRITY_SECRET — HMAC rows in sqlite messenger_log (tamper-evident).
  SIFTA_RELAY_ALLOWLIST — comma-separated relay origins for dead_drop.py (defaults to 127.0.0.1:8000).
  SIFTA_DIRECTIVE_REQUIRE_SIGNATURE — refuse unsigned swarm directive .scar commits from this node.
  SIFTA_MEMORY_POOL_MAX_PAYLOAD_BYTES — max JSON size for one pooled memory (default 64KiB).
  SIFTA_REPAIR_LLM_SNIPPET_MAX / SIFTA_REPAIR_IDENTITY_TRACE_MAX — repair.py LLM prompt bounds.
  SIFTA_RATE_LIMIT_PER_MIN — max mutating requests per client IP per minute (0 = off).
  SIFTA_TRUST_PROXY — if 1/true/on, rate limits use first X-Forwarded-For hop (set only behind your own proxy).
  SIFTA_PROTECT_GET — require API key on selected sensitive GET routes (terminal, etc.) unless *_OPEN.
  SIFTA_OPEN_GET_API — when SIFTA_API_KEY is set, allow unauthenticated GET on all /api/* (legacy LAN reads).
    If unset (default with a key), GET /api/* requires the key except SIFTA_GET_PROTECT_ALLOW.
    SIFTA_PROTECT_GET=1 with SIFTA_OPEN_GET_API=1 still requires the key on non-allowlisted GET routes.

  /api/swarm_state and /api/agents: stgm_balance is derived from repair_log (ledger_balance); stgm_balance_state_file
  is the on-disk agent JSON for comparison. Transaction tail uses repair_log only, not STGM_TX_LOG.jsonl.
  Finance GUI uses the same quorum for STGM; genesis mismatch flags swimmers without zeroing ledger truth.

  SIFTA_MAX_STGM_LEDGER_CREDIT — max single-line STGM *credit* appended to repair_log.jsonl
    (STGM_MINT, MINING_REWARD, FOUNDATION_GRANT, UTILITY_MINT, positive legacy amount_stgm).
    Default 25000. Set 0/off/false/none/unlimited to disable (e.g. intentional whale grants).
  SIFTA_MAX_DEFRAG_BOUNTY_STGM — cap payout from memory_defrag_worker bounty rewards (default 50).

Hardening backlog (not solved here):
  - Wormhole / receive_soul still assume LAN trust unless you add mTLS or VPN.
  - Autonomous git writers (this repo, swarm_network_ledger) need branch locks + review hooks.
  - repair_log integrity assumes OS file permissions; root on box bypasses crypto.
  - .gitattributes merge=union on repair_log.jsonl can duplicate/reorder lines under concurrent merges;
    verify rows cryptographically; prefer single-writer epochs for economy truth.

Relay (relay_server.py):
  SIFTA_RELAY_API_KEY, SIFTA_RELAY_REQUIRE_AUTH (refuse boot without key),
  SIFTA_RELAY_MAX_BODY_BYTES (default 6MiB) — drop payload bound.

Swarm brain:
  SIFTA_MEMPOOL_MAX_LINE_BYTES, SIFTA_SWARM_BRAIN_MAX_PROMPT_CHARS — human_signals.jsonl safety.

whatsapp_bridge:
  SIFTA_BRIDGE_INJECT_KEY — required header X-Sifta-Inject-Key for POST /system_inject (inject server binds 127.0.0.1 only).
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
