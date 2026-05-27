#!/usr/bin/env python3
"""xAI cortex auth health probe for System Settings.

Round 45: expose a read-only health probe so the Inference page can show
whether the Grok OAuth path is healthy before dispatching owner turns.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_XAI_OAUTH_ALIASES = ("xai-oauth", "grok-oauth", "x-ai-oauth", "xai-grok-oauth")
_FAILOVER_WINDOW_S = 30.0 * 60.0


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _has_xai_oauth_credential(auth_path: Path) -> bool:
    if not auth_path.exists():
        return False
    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(raw, dict):
        return False

    providers = raw.get("providers")
    if isinstance(providers, dict):
        for alias in _XAI_OAUTH_ALIASES:
            rec = providers.get(alias)
            if not isinstance(rec, dict):
                continue
            tokens = rec.get("tokens")
            if isinstance(tokens, dict):
                access = tokens.get("access_token")
                if isinstance(access, str) and access.strip():
                    return True
            access = rec.get("access_token")
            if isinstance(access, str) and access.strip():
                return True

    pool = raw.get("credential_pool")
    if isinstance(pool, dict):
        for alias in _XAI_OAUTH_ALIASES:
            rows = pool.get(alias)
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    access = row.get("access_token")
                    if isinstance(access, str) and access.strip():
                        return True
            elif isinstance(rows, dict):
                access = rows.get("access_token")
                if isinstance(access, str) and access.strip():
                    return True

    return False


def _last_failover_age_s(state_root: Path, *, now: float) -> float | None:
    ledger = state_root / "cortex_failover.jsonl"
    latest_ts: float | None = None
    for row in _iter_jsonl(ledger):
        if str(row.get("kind") or "") != "CORTEX_AUTH_FAILOVER":
            continue
        ts = row.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        ts_f = float(ts)
        if latest_ts is None or ts_f > latest_ts:
            latest_ts = ts_f
    if latest_ts is None:
        return None
    return max(0.0, now - latest_ts)


def check_xai_oauth_health(
    state_root: str | Path,
    hermes_auth_path: str = "~/.hermes/auth.json",
) -> dict[str, str | float | None]:
    """Return xAI OAuth health for the cortex picker status indicator.

    status=green when:
      - xAI OAuth credential exists in Hermes auth store
      - no CORTEX_AUTH_FAILOVER row in last 30 minutes
    status=red otherwise.
    """
    now = time.time()
    state = Path(state_root).expanduser().resolve()
    auth = Path(hermes_auth_path).expanduser()

    has_cred = _has_xai_oauth_credential(auth)
    failover_age = _last_failover_age_s(state, now=now)
    recent_failover = failover_age is not None and failover_age <= _FAILOVER_WINDOW_S

    if has_cred and not recent_failover:
        status = "green"
        reason = "oauth_present_no_recent_failover"
    elif not has_cred and recent_failover:
        status = "red"
        reason = "missing_xai_oauth_credential_and_recent_failover"
    elif not has_cred:
        status = "red"
        reason = "missing_xai_oauth_credential"
    else:
        status = "red"
        reason = "recent_cortex_auth_failover"

    return {
        "status": status,
        "reason": reason,
        "last_failover_age_s": failover_age,
    }


__all__ = ["check_xai_oauth_health"]
