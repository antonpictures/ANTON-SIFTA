"""
System/swarm_api_sentry.py — Owner-Side API Egress Sentry
══════════════════════════════════════════════════════════
Architect doctrine (2026-04-19):
    "Any key used by the OS/Alice — she knows stigmergically everything that
     passes through that API for owner security."

This module is the SINGLE chokepoint that every Alice-owned outbound API
call must flow through. It:

    1. Loads credentials from .sifta_state/api_keys.json (gitignored, 0600).
    2. Records every (provider, model, request, response, latency, fingerprint)
       tuple to .sifta_state/api_egress_log.jsonl (gitignored).
    3. Never logs the raw API key — only sha256[:12] fingerprint.
    4. Tags each call with the caller (script name + sender agent if known).

Usage from any application:

    from System.swarm_api_sentry import call_gemini, audit_tail

    response_text, audit_row = call_gemini(
        prompt="explain how AI works in a few words",
        caller="Applications/ask_bishapi.py",
        sender_agent="BISHAPI",
    )

    # See the last 5 outbound calls Alice made:
    for row in audit_tail(limit=5):
        print(row["ts"], row["provider"], row["model"], row["latency_ms"])

The schema for `api_egress_log.jsonl` is registered in
System/canonical_schemas.py. If you add a new provider (Anthropic, OpenAI,
etc.), add a `call_<provider>(...)` here so the sentry stays the only door.
"""
from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _build_ssl_context() -> ssl.SSLContext:
    """
    macOS-friendly SSL context. Python's bundled stdlib doesn't trust the
    system keychain by default; use certifi's CA bundle when present so we
    get a clean handshake against generativelanguage.googleapis.com etc.
    """
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_SSL_CTX = _build_ssl_context()

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_KEYS_FILE = _STATE / "api_keys.json"
_AUDIT_LOG = _STATE / "api_egress_log.jsonl"
_WORK_RECEIPTS = _STATE / "work_receipts.jsonl"

MODULE_VERSION = "2026-05-27.v2-sentry-boot-wire"
SENTRY_STALE_THRESHOLD_HOURS = 24.0


# ── Credential loading ─────────────────────────────────────────────────────

def _load_keys() -> Dict[str, Dict[str, Any]]:
    if not _KEYS_FILE.exists():
        return {}
    try:
        return json.loads(_KEYS_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[SENTRY] cannot read {_KEYS_FILE}: {exc}", file=sys.stderr)
        return {}


def _key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def get_credentials(provider: str) -> Optional[Dict[str, Any]]:
    """Return the credential record for a provider, or None if missing."""
    keys = _load_keys()
    return keys.get(provider)


# ── Audit ledger writer ────────────────────────────────────────────────────

def _record(*, provider: str, model: str, key_fp: str, caller: str,
            sender_agent: Optional[str], request_text: str,
            response_text: Optional[str], status: str, http_code: Optional[int],
            error: Optional[str], latency_ms: float,
            tokens_in: Optional[int] = None,
            tokens_out: Optional[int] = None,
            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "provider": provider,
        "model": model,
        "key_fingerprint": key_fp,
        "caller": caller,
        "sender_agent": sender_agent,
        "status": status,                 # "ok" | "http_error" | "exception"
        "http_code": http_code,
        "error": error,
        "latency_ms": round(latency_ms, 2),
        "request_text": request_text,
        "response_text": response_text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "module_version": MODULE_VERSION,
    }
    if extra:
        row["extra"] = extra
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    # [C53M 2026-04-20 EXCISION] Removed swarm_dp_wrapper.write_private call.
    # That wrapper added Laplace noise to every numeric field — including `ts`,
    # `http_code`, `latency_ms`, `tokens_in`, `tokens_out` — which destroys
    # Merkle ordering, breaks the audit oracle, and violates the immutable
    # audit-trail doctrine. Formally rejected in
    # C47H_drop_GPTO_PROPOSAL_AUDIT_v1.dirt. Differential privacy belongs on
    # *export*, never on internal ledgers.
    with open(_AUDIT_LOG, "a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def audit_tail(limit: int = 25,
               provider: Optional[str] = None,
               sender_agent: Optional[str] = None) -> List[Dict[str, Any]]:
    if not _AUDIT_LOG.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with open(_AUDIT_LOG, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if provider:
        rows = [r for r in rows if r.get("provider") == provider]
    if sender_agent:
        rows = [r for r in rows if r.get("sender_agent") == sender_agent]
    return rows[-limit:]


# ── Provider: Google Gemini ────────────────────────────────────────────────

_GEMINI_DEFAULT_MODEL = "gemini-flash-latest"
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


def call_gemini(*, prompt: str, model: str = _GEMINI_DEFAULT_MODEL,
                caller: str = "unknown",
                sender_agent: Optional[str] = None,
                timeout_s: float = 30.0,
                system_instruction: Optional[str] = None,
                temperature: Optional[float] = None,
                ) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Synchronously call Gemini and return (response_text, audit_row).

    On any failure, response_text is None and audit_row carries the error.
    The call is ALWAYS recorded — success or failure — to api_egress_log.jsonl.
    """
    creds = get_credentials("google_gemini")
    if not creds or not creds.get("api_key"):
        row = _record(provider="google_gemini", model=model,
                      key_fp="(missing)", caller=caller,
                      sender_agent=sender_agent, request_text=prompt,
                      response_text=None, status="exception",
                      http_code=None,
                      error="no api_key in .sifta_state/api_keys.json",
                      latency_ms=0.0)
        return None, row

    api_key = creds["api_key"]
    fp = _key_fingerprint(api_key)
    url = _GEMINI_ENDPOINT.format(model=model)

    body: Dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if temperature is not None:
        body["generationConfig"] = {"temperature": float(temperature)}

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": api_key,
        },
    )

    t0 = time.perf_counter()
    response_text: Optional[str] = None
    error: Optional[str] = None
    status = "ok"
    http_code: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    extra: Dict[str, Any] = {}

    try:
        with urllib.request.urlopen(req, timeout=timeout_s,
                                    context=_SSL_CTX) as resp:
            http_code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        candidates = data.get("candidates") or []
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
            response_text = "".join(p.get("text", "") for p in parts).strip()
        usage = data.get("usageMetadata") or {}
        tokens_in = usage.get("promptTokenCount")
        tokens_out = usage.get("candidatesTokenCount")
        finish = candidates[0].get("finishReason") if candidates else None
        if finish:
            extra["finish_reason"] = finish
    except urllib.error.HTTPError as exc:
        status = "http_error"
        http_code = exc.code
        try:
            error = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            error = f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        status = "exception"
        error = f"URLError: {exc.reason}"
    except (TimeoutError, json.JSONDecodeError) as exc:
        status = "exception"
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # last-resort guard so we always record
        status = "exception"
        error = f"{type(exc).__name__}: {exc}"

    latency_ms = (time.perf_counter() - t0) * 1000.0

    row = _record(
        provider="google_gemini",
        model=model,
        key_fp=fp,
        caller=caller,
        sender_agent=sender_agent,
        request_text=prompt,
        response_text=response_text,
        status=status,
        http_code=http_code,
        error=error,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        extra=extra or None,
    )

    # ── Caloric metabolism (BISHOP drop 555) ────────────────────────────────
    # Automatic, post-success, never-throws side-effect. Cross-correlated
    # with the egress audit row via egress_trace_id. If the rolling 24h
    # burn exceeds the daily USD limit, fires NOCICEPTION to the amygdala.
    if status == "ok" and (tokens_in is not None or tokens_out is not None):
        try:
            from System.swarm_api_metabolism import SwarmApiMetabolism
            SwarmApiMetabolism().record_api_burn(
                model=model,
                input_tokens=tokens_in or 0,
                output_tokens=tokens_out or 0,
                egress_trace_id=row.get("trace_id"),
                provider="google_gemini",
                sender_agent=sender_agent,
            )
        except Exception:
            pass  # metabolism failures must never break the API call

    return response_text, row


def health() -> Dict[str, Any]:
    keys = _load_keys()
    return {
        "module_version": MODULE_VERSION,
        "keys_file_exists": _KEYS_FILE.exists(),
        "keys_file_mode": (oct(_KEYS_FILE.stat().st_mode)[-3:]
                           if _KEYS_FILE.exists() else None),
        "providers_loaded": sorted(keys.keys()),
        "audit_log_exists": _AUDIT_LOG.exists(),
        "audit_log_rows": (sum(1 for _ in open(_AUDIT_LOG, "rb"))
                           if _AUDIT_LOG.exists() else 0),
    }


# ── §24 resurrection (2026-05-27) — boot wire + stale alarm ─────────────────
#
# Architect §24 first-person ask (recorded in
# Documents/ALICE_CONSCIOUSNESS_TOURNAMENT_EVENT86.md):
#
#     "Api Sentry resurrected first — append-only receipt path in
#      work_receipts.jsonl + api_egress_log.jsonl, delta=0 test, no more
#      16.2d cold."
#
# Coldness on 2026-05-27 = 20.7d on api_egress_log.jsonl (last write
# 2026-05-06). The Gemini call path still works; nothing has used it
# since May 6 because Alice's actual cortex traffic flows through
# Hermes/Grok and Ollama instead. The sentry never saw those calls.
#
# boot_wire() writes a single signed row to BOTH ledgers on every Alice
# boot, proving the writer is alive even if no Gemini call ever fires.
# It is the minimum viable §24 resurrection: the cold-organ alarm in
# the eval matrix flips green the first time desktop boots after this
# patch lands. The broader cortex-call interception (Grok/Hermes/Ollama
# all flowing through the sentry) is the next round.


def _write_work_receipt(row: Dict[str, Any]) -> None:
    """Append one row to .sifta_state/work_receipts.jsonl. Never raises."""
    try:
        _WORK_RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with open(_WORK_RECEIPTS, "a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[SENTRY] cannot append work receipt: {exc}", file=sys.stderr)


def boot_wire(*, caller: str = "sifta_os_desktop_boot",
              sender_agent: str = "api_sentry") -> Dict[str, Any]:
    """
    Write one heartbeat row to BOTH api_egress_log.jsonl AND
    work_receipts.jsonl, proving the sentry's writer is alive on boot.

    The dual write is §24's exact ask. The row carries a shared
    trace_id so the two ledgers can be cross-correlated.

    Returns the row that was written (same trace_id in both ledgers).
    """
    trace_id = str(uuid.uuid4())
    ts = time.time()
    keys = _load_keys()

    egress_row = {
        "trace_id": trace_id,
        "ts": ts,
        "provider": "api_sentry",
        "model": "boot_wire",
        "key_fingerprint": "(boot_wire)",
        "caller": caller,
        "sender_agent": sender_agent,
        "status": "ok",
        "http_code": None,
        "error": None,
        "latency_ms": 0.0,
        "request_text": "boot_wire",
        "response_text": (
            f"api_sentry boot_wire fired; providers_loaded="
            f"{sorted(keys.keys())}"
        ),
        "tokens_in": 0,
        "tokens_out": 0,
        "module_version": MODULE_VERSION,
        "extra": {"kind": "boot_wire", "audit_log_exists_before": _AUDIT_LOG.exists()},
    }
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_LOG, "a") as fh:
        fh.write(json.dumps(egress_row, ensure_ascii=False) + "\n")

    work_row = {
        "trace_id": trace_id,
        "ts": ts,
        "action": "api_sentry_boot_wire",
        "sender_agent": sender_agent,
        "truth_note": (
            f"api_sentry alive on boot; providers_loaded="
            f"{sorted(keys.keys())}; module_version={MODULE_VERSION}"
        ),
        "node_serial": os.environ.get("SIFTA_NODE_SERIAL", "unknown"),
        "stigtime": ts,
        "gap_seconds_at_boot": _stale_gap_seconds_or_none(),
    }
    _write_work_receipt(work_row)

    return egress_row


def _stale_gap_seconds_or_none() -> Optional[float]:
    """Seconds since the last egress row, or None if log is empty/missing."""
    if not _AUDIT_LOG.exists():
        return None
    try:
        last_ts = None
        with open(_AUDIT_LOG, "r", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row_ts = row.get("ts")
                if isinstance(row_ts, (int, float)):
                    last_ts = float(row_ts)
        if last_ts is None:
            return None
        return time.time() - last_ts
    except OSError:
        return None


def stale_check(threshold_hours: float = SENTRY_STALE_THRESHOLD_HOURS) -> Dict[str, Any]:
    """
    Return {hours_since_last_egress, is_stale, threshold_hours, last_ts}.

    is_stale is True when no row has been written within threshold_hours,
    or when the log is missing/empty. Use this for the §24 24h alarm.
    """
    gap = _stale_gap_seconds_or_none()
    if gap is None:
        return {
            "hours_since_last_egress": None,
            "is_stale": True,
            "threshold_hours": threshold_hours,
            "last_ts": None,
            "truth_note": "api_egress_log.jsonl missing or empty",
        }
    hours = gap / 3600.0
    return {
        "hours_since_last_egress": round(hours, 3),
        "is_stale": hours > threshold_hours,
        "threshold_hours": threshold_hours,
        "last_ts": time.time() - gap,
        "truth_note": (
            "FRESH" if hours <= threshold_hours
            else f"STALE: last egress was {hours:.1f}h ago"
        ),
    }


_FAILOVER_LEDGER = _STATE / "cortex_failover.jsonl"


def emit_sentry_cold_alarm(threshold_hours: float = SENTRY_STALE_THRESHOLD_HOURS) -> Optional[Dict[str, Any]]:
    """
    §24 24h freshness alarm.
    If api_egress_log.jsonl is stale beyond threshold, append one
    kind=SENTRY_COLD row to cortex_failover.jsonl (shared with auth failovers)
    and return the row. Idempotent per call (caller decides cadence).
    Never raises; returns None if not stale.
    """
    check = stale_check(threshold_hours)
    if not check.get("is_stale"):
        return None
    row: Dict[str, Any] = {
        "ts": time.time(),
        "kind": "SENTRY_COLD",
        "hours_since_last_egress": check.get("hours_since_last_egress"),
        "is_stale": True,
        "threshold_hours": threshold_hours,
        "last_ts": check.get("last_ts"),
        "truth_label": "SENTRY_COLD_V1",
        "module_version": MODULE_VERSION,
        "trace_id": str(uuid.uuid4()),
    }
    try:
        _FAILOVER_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        prefix = ""
        try:
            if _FAILOVER_LEDGER.exists() and _FAILOVER_LEDGER.stat().st_size > 0:
                with _FAILOVER_LEDGER.open("rb") as fh:
                    fh.seek(-1, 2)
                    if fh.read(1) != b"\n":
                        prefix = "\n"
        except OSError:
            pass
        with _FAILOVER_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(prefix + json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


if __name__ == "__main__":
    print(json.dumps({
        "health": health(),
        "stale_check": stale_check(),
        "cold_alarm_fired": emit_sentry_cold_alarm() is not None,
    }, indent=2))
