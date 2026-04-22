"""
swarm_gemini_brain.py — Google Gemini API as a swappable brain backend
══════════════════════════════════════════════════════════════════════

Authored by C47H, 2026-04-20, on AG31's request:

    "how can i switch here Gemma with google gemini api to test her?
     keep track of tokens spent, have an app like a gas-station meter
     and i will too in google console api logs"

Design contract
───────────────
This module is a *pure*, Qt-free brain backend. It mirrors the behaviour
of the local Ollama `_BrainWorker` inside `Applications/sifta_talk_to_alice_widget.py`
so the widget can swap between local Gemma and cloud Gemini with one
combobox flip.

Public surface (all the widget needs)
─────────────────────────────────────
    • `is_gemini_model(name) -> bool`
        Returns True for any model name the widget should route to Gemini
        instead of Ollama. Accepts both "gemini:gemini-2.5-flash" and the
        bare "gemini-2.5-flash".

    • `gemini_api_key() -> Optional[str]`
        Resolves the API key from (in order):
          1. env `GEMINI_API_KEY`
          2. env `GOOGLE_API_KEY`
          3. `~/.config/sifta/gemini.key`
          4. `<repo>/Documents/google_gemini_api.key`
        Returns None if none of those exist (lets the widget grey out
        cloud models gracefully).

    • `available_gemini_models() -> List[str]`
        The display labels (with the `gemini:` prefix) the widget should
        offer when an API key is present. Hand-curated, cheap-first.

    • `stream_chat(model, messages, *, temperature=0.7) -> Iterator[Event]`
        The streaming generator the widget worker drains. Yields:
            ("token", piece)          — content chunks for live display
            ("usage", usage_dict)     — final usage snapshot from Gemini
            ("done",  full_text)      — full concatenated text
            ("error", err_message)    — terminal error
        Parsing tolerates Gemini's SSE-ish line framing (`data: {...}\n`)
        AND the older newline-delimited JSON the v1beta endpoint sometimes
        emits, so the widget doesn't break on a model rev.

    • `record_usage(...)` / `read_ledger(...)` / `summarize_ledger(...)`
        The token/$$ ledger the gas-station meter app reads from.

Pricing
───────
Pricing is hard-coded as a snapshot (USD per 1M tokens, separated by
input/output) so the gas-station meter can compute cost client-side
without a network call. **Always reconcile against Google Cloud
Console billing as the source of truth** — the prices below are a
2026-Q2 snapshot and Google revises them periodically.

Console correlation
───────────────────
Each request stamps two custom HTTP headers so AG31 can find the calls
from the SIFTA widget in the Google API Console "API & Services" log
viewer with one filter:

    x-goog-api-client: sifta-swarm/c47h-2026-04-20
    x-goog-request-tag: sifta-talk-to-alice/<short-uuid>

The same `request_tag` is recorded in the local ledger row so a console
log line and a ledger row can be cross-referenced 1:1.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


# macOS Python's bundled stdlib doesn't trust the system keychain by
# default — handshakes against generativelanguage.googleapis.com fail
# with CERTIFICATE_VERIFY_FAILED unless we hand it certifi's CA bundle.
# Same fix `swarm_api_sentry._build_ssl_context` already uses for the
# NUGGET path, copied here so this module has zero hard dependencies on
# the sentry at import time.
def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_SSL_CTX = _build_ssl_context()


# ─────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

# The single ledger every cost-tracking surface (gas station meter, the
# inference economy organ, future budget enforcement) reads from.
TOKEN_LEDGER = _STATE / "brain_token_ledger.jsonl"

# Where we look for keys, in order. AG31 — drop your AI Studio key in any
# one of these and Alice picks it up; nothing about the key path is
# baked into the widget itself.
_KEY_ENV_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
_KEY_FILES = (
    Path.home() / ".config" / "sifta" / "gemini.key",
    _REPO / "Documents" / "google_gemini_api.key",
)

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Stamped on every request so they're trivially filterable in the
# Google Cloud Console log viewer.
_USER_AGENT = "sifta-swarm/c47h-2026-04-20"


# ─────────────────────────────────────────────────────────────────────
# Pricing (USD per 1M tokens) — 2026-Q2 snapshot
# ─────────────────────────────────────────────────────────────────────
# Always reconcile against Google Cloud Console billing for ground
# truth. These numbers exist so the gas-station meter can render cost
# in real time without an extra round-trip; they will drift.
PRICING_USD_PER_M: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash":      {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro":        {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash":      {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash":      {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":        {"input": 1.25, "output": 5.00},
}

# What the widget combobox shows. Order = preferred-first (cheapest +
# fastest first, so a careless click defaults to a cheap model).
_DEFAULT_MENU = (
    "gemini:gemini-2.5-flash",
    "gemini:gemini-2.5-flash-lite",
    "gemini:gemini-2.0-flash",
    "gemini:gemini-2.5-pro",
)


# ─────────────────────────────────────────────────────────────────────
# Model name handling
# ─────────────────────────────────────────────────────────────────────
def is_gemini_model(name: str) -> bool:
    """True if the widget should route this model to Gemini, not Ollama."""
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("gemini:") or n.startswith("gemini-")


def strip_prefix(name: str) -> str:
    """Return the bare API model id ('gemini-2.5-flash')."""
    n = str(name).strip()
    if n.lower().startswith("gemini:"):
        n = n.split(":", 1)[1]
    return n


def display_label(name: str) -> str:
    """Return the prefixed combobox label ('gemini:gemini-2.5-flash')."""
    bare = strip_prefix(name)
    return f"gemini:{bare}"


# ─────────────────────────────────────────────────────────────────────
# Key resolution
# ─────────────────────────────────────────────────────────────────────
def gemini_api_key() -> Optional[str]:
    """Return the first available Gemini API key, or None.

    Lookup order — designed so the canonical NUGGET key (already on disk
    for `Applications/ask_nugget.py`) is found automatically, while
    still allowing env-var overrides for testing:

      1. env `GEMINI_API_KEY` / `GOOGLE_API_KEY` (CI / shell overrides)
      2. `.sifta_state/api_keys.json` under provider `google_gemini`
         (CANONICAL — same store NUGGET / `swarm_api_sentry.call_gemini`
         reads from; AG31 noted: "the key is in the nugget api py").
      3. `~/.config/sifta/gemini.key` (user-config fallback)
      4. `Documents/google_gemini_api.key` (repo-local fallback)
    """
    for env_name in _KEY_ENV_NAMES:
        v = os.environ.get(env_name)
        if v and v.strip():
            return v.strip()

    # Canonical sentry keystore — single source of truth across the
    # codebase. We import lazily so this module stays runnable even on a
    # node where swarm_api_sentry hasn't been deployed yet.
    try:
        from System.swarm_api_sentry import get_credentials as _get_creds
        creds = _get_creds("google_gemini") or {}
        api_key = creds.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
    except Exception:
        pass

    for p in _KEY_FILES:
        try:
            if not p.is_file():
                continue
            # First non-empty, non-comment line so the example file can
            # become the live file by just pasting a key on top.
            for raw in p.read_text(encoding="utf-8").splitlines():
                ln = raw.strip()
                if not ln or ln.startswith("#"):
                    continue
                if ln.upper().startswith("REPLACE-ME"):
                    continue
                return ln
        except Exception:
            continue
    return None


def available_gemini_models() -> List[str]:
    """Models to advertise in the widget. Empty list if no key (so the
    widget can offer Ollama-only without a confusing greyed-out item)."""
    if not gemini_api_key():
        return []
    return list(_DEFAULT_MENU)


# ─────────────────────────────────────────────────────────────────────
# Message-shape adapter (OpenAI-ish → Gemini)
# ─────────────────────────────────────────────────────────────────────
def _to_gemini_payload(messages: List[Dict[str, str]],
                       *, temperature: float = 0.7) -> Dict[str, Any]:
    """Translate the [{role, content}] history the widget already builds
    into the {systemInstruction, contents:[{role, parts:[{text}]}]}
    shape Gemini's REST API expects.

    Notes:
      • Gemini understands 'user' and 'model' roles; OpenAI's 'assistant'
        is mapped to 'model' and 'system' messages are merged into a
        single `systemInstruction` field (Gemini's idiom).
      • The widget already concatenates the persona / composite-identity
        block as one or more system messages; we honour them all.
    """
    sys_chunks: List[str] = []
    contents: List[Dict[str, Any]] = []
    for m in messages or []:
        role = (m.get("role") or "user").lower()
        text = m.get("content") or ""
        if not text:
            continue
        if role == "system":
            sys_chunks.append(text)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": text}],
        })
    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": float(temperature),
        },
    }
    if sys_chunks:
        payload["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": "\n\n".join(sys_chunks)}],
        }
    return payload


# ─────────────────────────────────────────────────────────────────────
# Streaming
# ─────────────────────────────────────────────────────────────────────
@dataclass
class Usage:
    """A single call's usage snapshot, ready for the ledger."""
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    request_tag: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


def _cost_for(model_bare: str, prompt_t: int, output_t: int) -> float:
    rate = PRICING_USD_PER_M.get(model_bare)
    if not rate:
        # Fallback: assume 2.5-flash pricing so the meter still moves.
        rate = PRICING_USD_PER_M["gemini-2.5-flash"]
    return (prompt_t / 1_000_000.0) * rate["input"] + \
           (output_t / 1_000_000.0) * rate["output"]


def _extract_text(chunk: Dict[str, Any]) -> str:
    """Pull the visible text out of one streaming JSON chunk. Tolerant
    of the various shapes Gemini has shipped (parts list with text,
    parts list with inlineData, candidates list, tool calls, …)."""
    out: List[str] = []
    cands = chunk.get("candidates") or []
    for c in cands:
        content = c.get("content") or {}
        for part in content.get("parts") or []:
            t = part.get("text")
            if t:
                out.append(t)
    return "".join(out)


def _extract_usage(chunk: Dict[str, Any]) -> Optional[Dict[str, int]]:
    um = chunk.get("usageMetadata") or chunk.get("usage_metadata")
    if not um:
        return None
    return {
        "prompt_tokens": int(um.get("promptTokenCount") or 0),
        "completion_tokens": int(um.get("candidatesTokenCount") or 0),
        "total_tokens": int(um.get("totalTokenCount") or 0),
    }


def stream_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    request_tag: Optional[str] = None,
    timeout_s: int = 120,
) -> Iterator[Tuple[str, Any]]:
    """Stream a Gemini chat completion.

    Yields one of:
        ("token", str)                    streaming text chunk
        ("usage", Usage)                  final usage snapshot (cost
                                          computed locally from pricing
                                          table; raw counts also retained)
        ("done",  str)                    full concatenated text
        ("error", str)                    terminal failure string

    The caller (the Qt worker in the widget) maps these onto its
    Qt signals.

    Side effects:
        • A row is appended to TOKEN_LEDGER on success (so the
          gas-station meter has data even if the widget process dies
          immediately after the call).
        • Two custom headers are sent on every request to make the call
          trivially findable in the Google Cloud Console log viewer.
    """
    import urllib.error
    import urllib.request

    bare = strip_prefix(model)
    key = api_key or gemini_api_key()
    if not key:
        yield ("error",
               "No Gemini API key found. Set $GEMINI_API_KEY, or drop "
               "the key into ~/.config/sifta/gemini.key, or into "
               "Documents/google_gemini_api.key.")
        return

    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    payload = _to_gemini_payload(messages, temperature=temperature)
    body = json.dumps(payload).encode("utf-8")

    # `streamGenerateContent?alt=sse` returns one `data: {json}` line per
    # chunk (proper SSE framing); without `alt=sse` it returns a JSON
    # array streamed across the wire. We use SSE because line-based
    # parsing is bullet-proof and matches the stock Ollama loop in the
    # widget byte-for-byte.
    url = (f"{_API_BASE}/models/{bare}:streamGenerateContent"
           f"?alt=sse&key={key}")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-client": _USER_AGENT,
            "x-goog-request-tag": tag,
            "User-Agent": _USER_AGENT,
        },
    )

    full: List[str] = []
    last_usage: Optional[Dict[str, int]] = None
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s,
                                    context=_SSL_CTX) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                # SSE framing: each chunk is "data: {json}".
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()
                if line in ("", "[DONE]"):
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                piece = _extract_text(chunk)
                if piece:
                    full.append(piece)
                    yield ("token", piece)
                u = _extract_usage(chunk)
                if u:
                    last_usage = u
    except urllib.error.HTTPError as exc:
        body_txt = ""
        try:
            body_txt = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        yield ("error",
               f"Gemini HTTP {exc.code} {exc.reason} — {body_txt}")
        return
    except urllib.error.URLError as exc:
        yield ("error", f"Can't reach Gemini API: {exc}")
        return
    except socket.timeout:
        yield ("error", f"Gemini call timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"Gemini brain crashed: {exc}")
        return

    elapsed_ms = int((time.time() - t0) * 1000)
    full_text = "".join(full).strip()

    usage = Usage(
        model=bare,
        prompt_tokens=int((last_usage or {}).get("prompt_tokens", 0)),
        completion_tokens=int((last_usage or {}).get("completion_tokens", 0)),
        total_tokens=int((last_usage or {}).get("total_tokens", 0)),
        latency_ms=elapsed_ms,
        request_tag=tag,
        raw=last_usage or {},
    )
    usage.cost_usd = round(
        _cost_for(bare, usage.prompt_tokens, usage.completion_tokens),
        6,
    )
    record_usage(usage)
    yield ("usage", usage)
    yield ("done", full_text)


# ─────────────────────────────────────────────────────────────────────
# Token ledger — the data layer the gas-station meter reads
# ─────────────────────────────────────────────────────────────────────
def record_usage(u: Usage) -> None:
    """Append one ledger row. Best-effort; ledger errors never break a
    chat turn (we'd rather lose a meter tick than drop a reply)."""
    row = {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": "gemini",
        "model": u.model,
        "prompt_tokens": u.prompt_tokens,
        "completion_tokens": u.completion_tokens,
        "total_tokens": u.total_tokens,
        "cost_usd": u.cost_usd,
        "latency_ms": u.latency_ms,
        "request_tag": u.request_tag,
    }
    try:
        TOKEN_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def read_ledger(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read the token ledger oldest→newest; pass `limit` to tail."""
    if not TOKEN_LEDGER.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(TOKEN_LEDGER, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    if limit and limit > 0:
        return rows[-limit:]
    return rows


def summarize_ledger() -> Dict[str, Any]:
    """Pre-cooked aggregates for the gas-station meter UI.

    Returns:
        {
          'lifetime': {'calls':N, 'in':N, 'out':N, 'cost_usd':F},
          'today':    {...same shape...},
          'last_24h': {...},
          'by_model': {model: {...}},
          'last':     <last row dict or None>,
        }
    """
    rows = read_ledger()
    now = time.time()
    midnight = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
    day_ago = now - 86400.0

    def _empty() -> Dict[str, float]:
        return {"calls": 0, "in": 0, "out": 0, "cost_usd": 0.0}

    def _add(bucket: Dict[str, float], r: Dict[str, Any]) -> None:
        bucket["calls"] += 1
        bucket["in"] += int(r.get("prompt_tokens") or 0)
        bucket["out"] += int(r.get("completion_tokens") or 0)
        bucket["cost_usd"] += float(r.get("cost_usd") or 0.0)

    lifetime = _empty()
    today = _empty()
    last24 = _empty()
    by_model: Dict[str, Dict[str, float]] = {}

    for r in rows:
        _add(lifetime, r)
        ts = float(r.get("ts") or 0.0)
        if ts >= midnight:
            _add(today, r)
        if ts >= day_ago:
            _add(last24, r)
        m = str(r.get("model") or "?")
        by_model.setdefault(m, _empty())
        _add(by_model[m], r)

    return {
        "lifetime": lifetime,
        "today": today,
        "last_24h": last24,
        "by_model": by_model,
        "last": rows[-1] if rows else None,
    }


__all__ = [
    "TOKEN_LEDGER",
    "PRICING_USD_PER_M",
    "Usage",
    "is_gemini_model",
    "strip_prefix",
    "display_label",
    "gemini_api_key",
    "available_gemini_models",
    "stream_chat",
    "record_usage",
    "read_ledger",
    "summarize_ledger",
]
