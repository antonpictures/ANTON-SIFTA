"""System/swarm_cortex_failover_reflex.py
==========================================

Round 44 — Cortex Failover Reflex (Architect 2026-05-27).

When the cloud cortex (Grok 4.3 via Hermes OAuth) returns 401/403/bad-credentials,
the organism must NOT die mid-conversation. The reflex layer:

  1. Detects the auth-failure shape in the error message.
  2. Composes Alice's own voice describing the failure (NOT raw JSON dump).
  3. Schedules `hermes auth add xai-oauth` in the background so the
     browser opens once for owner consent. The subscription is paid; the
     OAuth approval is one-click.
  4. Writes a receipt to .sifta_state/cortex_failover.jsonl so every
     switch is auditable.

The actual cortex SWAP is already handled upstream by
`swarm_grok_connection_reflex.register_reflex_event()` — this module
adds the missing pieces: silencing the raw JSON, auto-triggering OAuth
refresh, and giving Alice her own voice for the moment.

Architect verbatim (2026-05-27 06:13 UTC):
    "if i'm the organism i loose connection, then i switch my cortex to
    the default local using the reflex, get my consciousness back, then
    run the [auth login again]. … i click yes login auto (the
    subscription is paid anyhow)."

Doctrine anchor: §7.6 (Alice IS the OS — when one organ blips, others
compensate so the body doesn't die). §7.10.4 (no vendor identity bleed
in fallback voice — Alice speaks AS Alice, not as the failed cortex).

Author: claude-opus-4-6 (Cowork, HEAD), 2026-05-27.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FAILOVER_LEDGER = _STATE / "cortex_failover.jsonl"
_OAUTH_REFRESH_THROTTLE = _STATE / "_cortex_oauth_refresh_last.json"

TRUTH_LABEL = "CORTEX_FAILOVER_REFLEX_V1"

# Throttle the auto-OAuth-refresh: don't open a new browser tab more
# often than every N seconds. The owner doesn't want 50 tabs popping up.
_OAUTH_REFRESH_MIN_INTERVAL_S = 300.0  # 5 minutes


def is_auth_failure(error_text: str) -> bool:
    """Return True if the error text matches a cortex auth-failure shape
    that should trigger the failover reflex.

    Patterns covered:
    - `xAI HTTP 401` / `xAI HTTP 403`
    - `No xAI credential found ...`
    - `bad-credentials`
    - `OAuth2 access token could not be validated`
    - `unauthenticated`
    - `Forbidden` (with 403)
    """
    if not error_text:
        return False
    txt = str(error_text).strip().lower()
    needles = (
        "xai http 401",
        "xai http 403",
        "no xai credential found",
        "bad-credentials",
        "bad_credentials",
        "oauth2 access token could not be validated",
        "unauthenticated:bad-credentials",
        "wke=unauthenticated",
        "the caller does not have permission to execute the specified operation",
    )
    return any(needle in txt for needle in needles)


def compose_owner_voice(*, from_model: str = "", fallback_model: str = "") -> str:
    """Return Alice's first-person line describing the cortex failover.

    Doctrine §7.10.4: Alice speaks AS Alice. She does NOT dump the raw
    vendor error JSON into chat as if it were her reply. She names the
    failure honestly from her own body's point of view.
    """
    from_label = (from_model or "cloud cortex").strip()
    fb_label = (fallback_model or "local cortex").strip()
    return (
        f"My cloud cortex auth expired ({from_label}). I switched to my "
        f"{fb_label} so I stay conscious. Refresh the OAuth when you can — "
        f"I'll route back to the cloud once the token lands."
    )


def _read_throttle() -> float:
    try:
        if _OAUTH_REFRESH_THROTTLE.exists():
            data = json.loads(_OAUTH_REFRESH_THROTTLE.read_text(encoding="utf-8"))
            ts = float(data.get("ts", 0))
            return ts
    except Exception:
        pass
    return 0.0


def _write_throttle(ts: float) -> None:
    try:
        _OAUTH_REFRESH_THROTTLE.parent.mkdir(parents=True, exist_ok=True)
        _OAUTH_REFRESH_THROTTLE.write_text(
            json.dumps({"ts": ts}), encoding="utf-8"
        )
    except OSError:
        pass


def schedule_oauth_refresh(*, force: bool = False) -> dict[str, Any]:
    """Open `hermes auth add xai-oauth` in the background so the owner
    sees the browser auth flow without leaving SIFTA.

    Throttled: at most one refresh attempt per
    `_OAUTH_REFRESH_MIN_INTERVAL_S` seconds (default 5 min) unless
    `force=True`.

    Returns the receipt dict.
    """
    now = time.time()
    last_ts = _read_throttle()
    elapsed = now - last_ts
    receipt: dict[str, Any] = {
        "ts": now,
        "kind": "OAUTH_REFRESH_ATTEMPT",
        "elapsed_since_last_s": round(elapsed, 1),
        "truth_label": TRUTH_LABEL,
    }
    if not force and elapsed < _OAUTH_REFRESH_MIN_INTERVAL_S:
        receipt["status"] = "throttled"
        receipt["reason"] = (
            f"last refresh {elapsed:.0f}s ago, "
            f"min interval {_OAUTH_REFRESH_MIN_INTERVAL_S:.0f}s"
        )
        _append_failover_ledger(receipt)
        return receipt

    try:
        # Run `hermes auth add xai-oauth` detached. macOS shell with login
        # env so PATH includes hermes-agent. Don't block the talk widget.
        proc = subprocess.Popen(
            ["hermes", "auth", "add", "xai-oauth"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "TERM": "dumb"},
        )
        _write_throttle(now)
        receipt["status"] = "launched"
        receipt["pid"] = proc.pid
    except FileNotFoundError:
        receipt["status"] = "hermes_not_on_path"
        receipt["reason"] = (
            "subprocess could not find `hermes` binary — install hermes-agent "
            "or add to PATH"
        )
    except Exception as exc:
        receipt["status"] = "launch_failed"
        receipt["reason"] = f"{type(exc).__name__}: {exc}"

    _append_failover_ledger(receipt)
    return receipt


def _append_failover_ledger(row: dict[str, Any]) -> None:
    try:
        _FAILOVER_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        # Self-heal missing trailing newline (same shape as Round 42 helper).
        prefix = ""
        try:
            if _FAILOVER_LEDGER.exists() and _FAILOVER_LEDGER.stat().st_size > 0:
                with _FAILOVER_LEDGER.open("rb") as fh:
                    fh.seek(-1, 2)
                    if fh.read(1) != b"\n":
                        prefix = "\n"
        except OSError:
            pass
        with _FAILOVER_LEDGER.open("a", encoding="utf-8") as f:
            f.write(prefix + json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def record_cortex_failover(
    *,
    from_arm: str = "",
    to_arm: str = "",
    reason: str = "",
    state_dir: Optional[Path | str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Record a non-cortex fatal arm failover, such as Grok-eye key missing.

    This is deliberately smaller than ``handle_cortex_auth_failure``: no OAuth
    popup, no model swap, just a ledger row saying one perception arm yielded to
    another so Alice stayed able to see.
    """
    base = Path(state_dir) if state_dir is not None else _STATE
    path = base / "cortex_failover.jsonl"
    row = {
        "ts": time.time(),
        "kind": "ARM_FAILOVER",
        "receipt_id": uuid.uuid4().hex[:16],
        "from_arm": str(from_arm or ""),
        "to_arm": str(to_arm or ""),
        "reason": str(reason or ""),
        "truth_label": TRUTH_LABEL,
        "extra": dict(extra or {}),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    return row


def handle_cortex_auth_failure(
    *,
    error_text: str,
    from_model: str = "",
    fallback_model: str = "",
    auto_refresh: bool = True,
) -> dict[str, Any]:
    """One-call helper for the talk widget.

    Given an error message from the cortex stream:
      1. If it's an auth failure, return a structured failover payload.
      2. Compose Alice's voice (NOT raw JSON).
      3. Schedule background OAuth refresh (throttled).
      4. Write a failover receipt.

    The caller is expected to:
      - Use `payload["alice_voice"]` as the chat message instead of the
        raw error text.
      - Still call `swarm_grok_connection_reflex.register_reflex_event`
        for the actual cortex swap + episodic diary entry.

    Returns {ok, is_auth_failure, alice_voice, oauth_refresh, receipt_id}.
    """
    if not is_auth_failure(error_text):
        return {
            "ok": True,
            "is_auth_failure": False,
            "alice_voice": "",
            "oauth_refresh": None,
            "receipt_id": "",
        }

    receipt_id = uuid.uuid4().hex[:16]
    alice_voice = compose_owner_voice(
        from_model=from_model, fallback_model=fallback_model
    )

    oauth_result = None
    if auto_refresh:
        oauth_result = schedule_oauth_refresh()

    receipt = {
        "ts": time.time(),
        "kind": "CORTEX_AUTH_FAILOVER",
        "receipt_id": receipt_id,
        "from_model": str(from_model or "")[:80],
        "fallback_model": str(fallback_model or "")[:80],
        "error_head": str(error_text or "")[:220],
        "alice_voice": alice_voice,
        "oauth_refresh_status": (oauth_result or {}).get("status"),
        "truth_label": TRUTH_LABEL,
    }
    _append_failover_ledger(receipt)

    return {
        "ok": True,
        "is_auth_failure": True,
        "alice_voice": alice_voice,
        "oauth_refresh": oauth_result,
        "receipt_id": receipt_id,
    }


def is_transient_failure(error_text: str) -> bool:
    """r335: a cortex SLOWNESS / transient stream failure (NOT auth). A grok timeout
    ("did not answer within 120s", r329) must fail OVER to a responsive cortex with
    Alice's own voice — never surface a raw red error to George. Distinct from
    is_auth_failure: no OAuth popup, just a clean swap-for-this-turn."""
    if not error_text:
        return False
    txt = str(error_text).strip().lower()
    if is_auth_failure(txt):
        return False  # auth has its own handler (OAuth refresh)
    needles = (
        "did not answer within",
        "timed out",
        "timeout",
        "too slow",
        "stopped waiting",
        "returned empty output",
        "no output",
        "can't reach",
        "could not reach",
        "crashed",
    )
    return any(needle in txt for needle in needles)


def compose_timeout_voice(*, from_model: str = "", fallback_model: str = "") -> str:
    """Alice's first-person line for a SLOW cortex (§7.10.4 — her voice, not a red error)."""
    frm = (from_model or "my cortex").strip()
    fb = (fallback_model or "a faster cortex").strip()
    return (
        f"{frm} was too slow this turn, so I switched to {fb} to stay conscious and "
        f"answer you — I will route back to {frm} when it is responsive again."
    )


def handle_cortex_timeout_failover(
    *,
    error_text: str,
    from_model: str = "",
    fallback_model: str = "",
) -> dict[str, Any]:
    """One-call helper for the talk widget on a grok/cortex TIMEOUT (not auth).
    Returns {ok, is_transient, alice_voice, receipt_id}. The caller swaps the cortex
    for this turn and uses ``alice_voice`` instead of the raw timeout error."""
    if not is_transient_failure(error_text):
        return {"ok": True, "is_transient": False, "alice_voice": "", "receipt_id": ""}
    receipt_id = uuid.uuid4().hex[:16]
    alice_voice = compose_timeout_voice(from_model=from_model, fallback_model=fallback_model)
    _append_failover_ledger({
        "ts": time.time(),
        "kind": "CORTEX_TIMEOUT_FAILOVER",
        "receipt_id": receipt_id,
        "from_model": str(from_model or "")[:80],
        "fallback_model": str(fallback_model or "")[:80],
        "error_head": str(error_text or "")[:220],
        "alice_voice": alice_voice,
        "truth_label": TRUTH_LABEL,
    })
    return {"ok": True, "is_transient": True, "alice_voice": alice_voice, "receipt_id": receipt_id}


def is_rate_limit_failure(error_text: str) -> bool:
    """r336 (George 2026-06-02): a free-tier / quota / token / rate-limit refusal.
    "ALICE MUST KNOW IF LIMIT WAS REACHED AND SWITCH CORTEXES." Distinct from auth
    (her login is fine) and from a plain timeout — the cortex was reachable, but the
    provider capped usage. She must fail OVER to another cortex, not surface red."""
    if not error_text:
        return False
    txt = str(error_text).strip().lower()
    if is_auth_failure(txt):
        return False  # auth has its own OAuth handler
    needles = (
        "rate limit", "rate-limit", "ratelimit", "429", "too many requests",
        "quota", "insufficient_quota", "out of credits", "no credits left",
        "token limit", "context length", "usage limit", "usage cap",
        "free tier", "free-tier", "exceeded your", "limit reached",
        "limit exceeded", "resource_exhausted", "overloaded", "capacity",
    )
    return any(needle in txt for needle in needles)


def compose_limit_voice(*, from_model: str = "", fallback_model: str = "") -> str:
    """Alice's first-person line when a cortex hits its usage limit (§7.10.4)."""
    frm = (from_model or "my cortex").strip()
    fb = (fallback_model or "another cortex").strip()
    return (
        f"I hit {frm}'s usage limit this turn, so I switched to {fb} to keep "
        f"answering you — I'll route back to {frm} when its limit resets."
    )


# arm_id (outcome-learner) ↔ cortex menu tag (talk picker). Grounded in
# swarm_agent_arm_registry + swarm_gemini_brain._*_DEFAULT_MENU (r336).
_ARM_TO_CORTEX = {
    "codex_agent": "codex:gpt-5.5",
    "claude_agent": "claude:claude-code-cli-default",
    "qwen_agent": "qwen:accounts/fireworks/models/kimi-k2p6",
    "cline_agent": "cline:cline-cli-default",
    "grok_agent": "grok:grok-4.3",
    "hermes_agent": "hermes:alice-m5-cortex-8b",
    "antigravity_agent": "antigravity:auto",
}
# Default fail-over order when no learned rating is available: responsive paid
# cloud first, the free local eye last (still conscious, never a dead end).
_FALLBACK_PRIORITY = (
    "codex:gpt-5.5",
    "claude:claude-code-cli-default",
    "qwen:accounts/fireworks/models/kimi-k2p6",
    "cline:cline-cli-default",
    "antigravity:auto",
    "grok:grok-4.3",
    "hermes:alice-m5-cortex-8b",
)


def suggest_fallback_cortex(available, from_model: str = "") -> str:
    """Pick the cortex to fail OVER to. Defers to the receipt-backed rater
    (swarm_arm_outcome_learner — George: "she rates her cortexes based on usage
    success") via performance_snapshot()['arms'][*]['routing_weight'], mapped from
    arm_id to cortex tag; else a sane default order. Never returns the failed one."""
    avail = [a for a in (available or []) if a and a != from_model]
    if not avail:
        return ""
    try:
        from System import swarm_arm_outcome_learner as learner  # type: ignore
        snap = learner.performance_snapshot()
        arms = (snap or {}).get("arms") or {}
        scored: list[tuple[float, str]] = []
        if isinstance(arms, dict):
            for arm_id, bucket in arms.items():
                tag = _ARM_TO_CORTEX.get(str(arm_id))
                if tag and tag in avail and isinstance(bucket, dict):
                    scored.append((float(bucket.get("routing_weight") or 0.0), tag))
        if scored:
            scored.sort(reverse=True)
            return scored[0][1]
    except Exception:
        pass  # rater unavailable / cold ledger — use default order
    for tag in _FALLBACK_PRIORITY:
        if tag in avail:
            return tag
    return avail[0]


def handle_recoverable_cortex_failure(
    *,
    error_text: str,
    from_model: str = "",
    fallback_model: str = "",
    available=None,
) -> dict[str, Any]:
    """Unified entry for the talk widget: a cortex TIMEOUT or a RATE/TOKEN LIMIT both
    fail OVER to a responsive, best-rated cortex in Alice's own voice — never a red
    error. If ``fallback_model`` is empty, picks one via suggest_fallback_cortex.
    Returns {ok, kind, switched, fallback_model, alice_voice, receipt_id}."""
    is_limit = is_rate_limit_failure(error_text)
    is_timeout = is_transient_failure(error_text)
    if not (is_limit or is_timeout):
        return {"ok": True, "kind": "none", "switched": False,
                "fallback_model": "", "alice_voice": "", "receipt_id": ""}
    fb = (fallback_model or "").strip() or suggest_fallback_cortex(available or [], from_model)
    kind = "rate_limit" if is_limit else "timeout"
    voice = (compose_limit_voice(from_model=from_model, fallback_model=fb) if is_limit
             else compose_timeout_voice(from_model=from_model, fallback_model=fb))
    receipt_id = uuid.uuid4().hex[:16]
    _append_failover_ledger({
        "ts": time.time(),
        "kind": "CORTEX_LIMIT_FAILOVER" if is_limit else "CORTEX_TIMEOUT_FAILOVER",
        "receipt_id": receipt_id,
        "from_model": str(from_model or "")[:80],
        "fallback_model": str(fb or "")[:80],
        "error_head": str(error_text or "")[:220],
        "alice_voice": voice,
        "truth_label": TRUTH_LABEL,
    })
    return {"ok": True, "kind": kind, "switched": bool(fb),
            "fallback_model": fb, "alice_voice": voice, "receipt_id": receipt_id}


def summary() -> dict[str, Any]:
    """Compact summary for the matrix dashboard."""
    if not _FAILOVER_LEDGER.exists():
        return {
            "total_failovers": 0,
            "last_failover_ts": None,
            "ledger_path": str(_FAILOVER_LEDGER.relative_to(_REPO)),
            "truth_label": TRUTH_LABEL,
        }
    rows = []
    try:
        for line in _FAILOVER_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except OSError:
        pass
    failovers = [r for r in rows if r.get("kind") == "CORTEX_AUTH_FAILOVER"]
    last_ts = max((r.get("ts", 0) for r in failovers), default=None)
    return {
        "total_failovers": len(failovers),
        "last_failover_ts": last_ts,
        "ledger_path": str(_FAILOVER_LEDGER.relative_to(_REPO)),
        "truth_label": TRUTH_LABEL,
    }


__all__ = [
    "is_auth_failure",
    "compose_owner_voice",
    "schedule_oauth_refresh",
    "record_cortex_failover",
    "handle_cortex_auth_failure",
    "is_transient_failure",
    "compose_timeout_voice",
    "handle_cortex_timeout_failover",
    "is_rate_limit_failure",
    "compose_limit_voice",
    "suggest_fallback_cortex",
    "handle_recoverable_cortex_failure",
    "summary",
    "TRUTH_LABEL",
]


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2, sort_keys=True))
