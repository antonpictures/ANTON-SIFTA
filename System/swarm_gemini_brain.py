"""
swarm_gemini_brain.py — Cloud brain backend (Gemini + Grok)
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
        Returns True for any cloud model name the widget should route to
        cloud instead of Ollama. Back-compat name kept for callers that still
        import `is_gemini_model`. Accepts Gemini and Grok prefixes.

    • `gemini_api_key() -> Optional[str]`
        Resolves the API key from (in order):
          1. env `GEMINI_API_KEY`
          2. env `GOOGLE_API_KEY`
          3. `~/.config/sifta/gemini.key`
          4. `<repo>/Documents/google_gemini_api.key`
        Returns None if none of those exist (lets the widget grey out
        cloud models gracefully).

    • `available_gemini_models() -> List[str]`
        Back-compat cloud model list. Includes Gemini entries when a Gemini key
        is present, and includes the canonical Grok entry.

    • `stream_chat(model, messages, *, temperature=0.7) -> Iterator[Event]`
        The streaming generator the widget worker drains. Yields:
            ("token", piece)          — content chunks for live display
            ("usage", usage_dict)     — final usage snapshot from Gemini
            ("done",  full_text)      — full concatenated text
            ("error", err_message)    — terminal error
        For Gemini: parses SSE `data: {json}` chunks.
        For Grok: performs a non-streaming chat-completions call and emits
        one token chunk + final done.

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
import re
import shutil
import socket
import ssl
import subprocess
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
_XAI_API_BASE = "https://api.x.ai/v1/chat/completions"

# Stamped on every request so they're trivially filterable in the
# Google Cloud Console log viewer.
_USER_AGENT = "sifta-swarm/c47h-2026-04-20"
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


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
_GROK_DEFAULT_MENU = ("grok:grok-4.3",)
_CLAUDE_DEFAULT_MENU = ("claude:claude-code-cli-default",)
_CODEX_DEFAULT_MENU = ("codex:gpt-5.5",)
_QWEN_DEFAULT_MENU = (
    "qwen:accounts/fireworks/models/gpt-oss-20b",
    "qwen:accounts/fireworks/models/deepseek-v4-flash",
)
_CLINE_DEFAULT_MENU = ("cline:cline-cli-default",)

# Round 70 (2026-05-27): keep the SIFTA cortex resolver key stable while
# translating to the concrete model id accepted by the logged-in local
# `grok` CLI.  The owner's Settings picker and receipts use
# `grok:grok-4.3`; `grok models` on this node exposes only `grok-build`.
_GROK_CLI_MODEL_ALIASES: Dict[str, str] = {
    "grok-4.3": "grok-build",
}


# ─────────────────────────────────────────────────────────────────────
# Model name handling
# ─────────────────────────────────────────────────────────────────────
def is_gemini_model(name: str) -> bool:
    """True if the widget should route this model to a cloud/CLI teacher."""
    if not name:
        return False
    n = str(name).strip().lower()
    return (
        n.startswith("gemini:")
        or n.startswith("gemini-")
        or n.startswith("grok:")
        or n.startswith("grok-")
        or n.startswith("claude:")
        or n.startswith("claude-")
        or n.startswith("codex:")
        or n.startswith("codex-")
        or n.startswith("qwen:")
        or n.startswith("qwen-")
        or n.startswith("cline:")
        or n.startswith("cline-")
    )


def _is_grok_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("grok:") or n.startswith("grok-")


def _is_claude_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("claude:") or n.startswith("claude-")


def _is_codex_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("codex:") or n.startswith("codex-")


def _is_qwen_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("qwen:") or n.startswith("qwen-")


def _is_cline_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("cline:") or n.startswith("cline-")


def is_cloud_model(name: str) -> bool:
    """Provider-agnostic alias used by newer callers."""
    return is_gemini_model(name)


def strip_prefix(name: str) -> str:
    """Return bare API model id ('gemini-2.5-flash', 'grok-4.3')."""
    n = str(name).strip()
    if n.lower().startswith("gemini:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("grok:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("claude:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("codex:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("qwen:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("cline:"):
        n = n.split(":", 1)[1]
    return n


def grok_cli_model_for(name: str) -> str:
    """Return the concrete model id to pass to the local `grok` CLI."""
    bare = strip_prefix(name)
    return _GROK_CLI_MODEL_ALIASES.get(bare.lower(), bare)


def display_label(name: str) -> str:
    """Return prefixed combobox label ('gemini:...','grok:...')."""
    bare = strip_prefix(name)
    if bare.lower().startswith("grok-"):
        return f"grok:{bare}"
    if bare.lower().startswith("claude-"):
        return f"claude:{bare}"
    if bare.lower().startswith("codex-") or bare.lower().startswith("gpt-"):
        return f"codex:{bare}"
    if bare.lower().startswith("accounts/fireworks/models/") or bare.lower().startswith("qwen-") or bare.lower().startswith("kimi-"):
        return f"qwen:{bare}"
    if bare.lower().startswith("cline-"):
        return f"cline:{bare}"
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
    """Back-compat cloud model list for UI pickers.

    Gemini entries are exposed when a Gemini key is available.
    Grok entry stays visible as a selectable cortex so owner can bind
    credentials later without code changes.
    """
    out: List[str] = []
    if gemini_api_key():
        out.extend(_DEFAULT_MENU)
    out.extend(_GROK_DEFAULT_MENU)
    out.extend(_CLAUDE_DEFAULT_MENU)
    out.extend(_CODEX_DEFAULT_MENU)
    out.extend(_QWEN_DEFAULT_MENU)
    out.extend(_CLINE_DEFAULT_MENU)
    deduped: List[str] = []
    seen: set[str] = set()
    for name in out:
        label = display_label(name)
        if label not in seen:
            seen.add(label)
            deduped.append(label)
    return deduped


def xai_api_key() -> Optional[str]:
    """Resolve a local xAI credential (env or token file)."""
    try:
        from System.xai_grok_oauth_organ import load_credential as _load_xai_credential

        cred = _load_xai_credential()
        if cred and getattr(cred, "value", ""):
            return str(cred.value).strip() or None
    except Exception:
        pass
    return None


def available_cloud_models() -> List[str]:
    """Provider-agnostic alias used by newer selectors."""
    return available_gemini_models()


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


def _to_xai_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Normalize widget history for xAI chat-completions payload."""
    out: List[Dict[str, str]] = []
    for m in messages or []:
        role = str(m.get("role") or "user").strip().lower()
        content = str(m.get("content") or "")
        if not content.strip():
            continue
        if role not in {"system", "user", "assistant", "tool"}:
            role = "user"
        out.append({"role": role, "content": content})
    return out


def _grok_cli_binary() -> Optional[str]:
    return shutil.which("grok")


def _to_grok_cli_prompt(messages: List[Dict[str, str]]) -> str:
    """Flatten chat history into a deterministic single-turn prompt for grok CLI."""
    lines: List[str] = [
        "You are the active SIFTA Grok Cortex for Alice.",
        "Answer with the final assistant response only.",
        "",
    ]
    for m in messages or []:
        role = str(m.get("role") or "user").strip().upper()
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}:")
        lines.append(content)
        lines.append("")
    lines.append("ASSISTANT:")
    return "\n".join(lines).strip()


def _clean_grok_cli_output(text: str) -> str:
    raw = _ANSI_RE.sub("", str(text or ""))
    out_lines: List[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        clean = line.strip()
        if not clean:
            out_lines.append("")
            continue
        lower = clean.lower()
        if lower.startswith("turn completed in "):
            continue
        if lower == "tokens used":
            # Some builds emit a short usage footer after the answer.
            break
        out_lines.append(line)
    cleaned = "\n".join(out_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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


def _stream_grok_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    request_tag: Optional[str] = None,
    timeout_s: int = 120,
) -> Iterator[Tuple[str, Any]]:
    """xAI chat-completions adapter.

    We use non-streaming mode and emit one token chunk + done. This keeps the
    worker contract intact while avoiding SSE parser drift across providers.
    """
    import urllib.error
    import urllib.request

    bare = strip_prefix(model)
    key = api_key or xai_api_key()
    if not key:
        yield from _stream_grok_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return

    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    body = json.dumps(
        {
            "model": bare,
            "messages": _to_xai_messages(messages),
            "temperature": float(temperature),
            "stream": False,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        _XAI_API_BASE,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "x-request-tag": tag,
        },
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body_txt = ""
        try:
            body_txt = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        # OAuth bearer drift reflex:
        # If the xAI HTTPS call is denied (expired/revoked OAuth token, or tier gate),
        # immediately fall back to the local Grok CLI path. The CLI session can often
        # recover using its own stored auth flow without requiring a full chat failure.
        body_low = body_txt.lower()
        if int(getattr(exc, "code", 0) or 0) in (401, 403) or (
            "unknown model id" in body_low or "invalid params" in body_low
        ):
            yield from _stream_grok_chat_via_cli(
                model=model,
                messages=messages,
                request_tag=request_tag,
                timeout_s=timeout_s,
            )
            return
        yield ("error", f"xAI HTTP {exc.code} {exc.reason} — {body_txt}")
        return
    except urllib.error.URLError as exc:
        yield ("error", f"Can't reach xAI API: {exc}")
        return
    except socket.timeout:
        yield ("error", f"xAI call timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"xAI brain crashed: {exc}")
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        yield ("error", f"xAI returned non-JSON payload: {raw[:300]}")
        return

    message = ""
    try:
        message = str(
            ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
    except Exception:
        message = ""
    if not message:
        yield ("error", "xAI response had no assistant content.")
        return

    usage_raw = payload.get("usage") or {}
    prompt_tokens = int(usage_raw.get("prompt_tokens") or 0)
    completion_tokens = int(usage_raw.get("completion_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or 0)
    cost_usd = usage_raw.get("cost_in_usd")
    try:
        cost_value = float(cost_usd) if cost_usd is not None else 0.0
    except Exception:
        cost_value = 0.0

    usage = Usage(
        model=bare,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw=usage_raw if isinstance(usage_raw, dict) else {},
    )
    usage.cost_usd = round(cost_value, 6)
    record_usage(usage, backend="xai_grok")
    yield ("token", message)
    yield ("usage", usage)
    yield ("done", message)


def _stream_grok_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 120,
) -> Iterator[Tuple[str, Any]]:
    """Fallback path: use logged-in local grok CLI OAuth session.

    This path keeps Alice operational on nodes with SuperGrok/X Premium+
    where API-key credentials are intentionally absent.
    """
    cli = _grok_cli_binary()
    if not cli:
        yield (
            "error",
            "No xAI credential found and local `grok` CLI is missing. "
            "Set XAI_API_KEY / XAI_OAUTH_ACCESS_TOKEN, or log in via Hermes "
            "OAuth after updating Hermes: `hermes auth add xai-oauth`.",
        )
        return

    bare = strip_prefix(model)
    cli_model = grok_cli_model_for(model)
    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    prompt = _to_grok_cli_prompt(messages)
    used_model = cli_model
    fallback_to_cli_default = False
    cmd = [
        cli,
        "--single",
        prompt,
        "--model",
        cli_model,
        "--output-format",
        "plain",
        "--no-alt-screen",
    ]

    def _run_once(run_cmd: List[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=timeout_s,
        )

    t0 = time.time()
    try:
        proc = _run_once(cmd)
    except subprocess.TimeoutExpired:
        yield ("error", f"Grok CLI timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"Grok CLI launch failed: {exc}")
        return

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout if stdout.strip() else stderr
    if proc.returncode != 0 and "unknown model id" in combined.lower():
        # The local CLI account may expose a curated model set (e.g. grok-build
        # only). Retry without explicit --model so Grok uses its configured
        # default model for this OAuth session.
        fallback_cmd = [
            cli,
            "--single",
            prompt,
            "--output-format",
            "plain",
            "--no-alt-screen",
        ]
        try:
            proc = _run_once(fallback_cmd)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            combined = stdout if stdout.strip() else stderr
            fallback_to_cli_default = proc.returncode == 0
            if fallback_to_cli_default:
                used_model = "grok-cli-default"
        except Exception:
            pass

    if proc.returncode != 0:
        snippet = _clean_grok_cli_output(combined)[:500]
        yield ("error", f"Grok CLI failed (rc={proc.returncode}): {snippet or 'no output'}")
        return

    text = _clean_grok_cli_output(combined)
    if not text:
        yield ("error", "Grok CLI returned empty output.")
        return

    usage = Usage(
        model=used_model,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw={
            "transport": "grok_cli_single",
            "requested_model": bare,
            "cli_model": cli_model,
            "fallback_to_cli_default": fallback_to_cli_default,
        },
    )
    usage.cost_usd = 0.0
    record_usage(usage, backend="xai_grok_cli")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


def _to_teacher_cli_prompt(messages: List[Dict[str, str]], *, teacher: str) -> str:
    """Flatten chat history for CLI teacher cortexes.

    Claude and Codex are used here as signed-in teacher substrates, not as
    file-mutating arms. The prompt explicitly asks for answer-only behavior;
    work that should mutate files still belongs to the agent-arm launcher.
    """
    chunks: List[str] = [
        "You are a SIFTA cortex teacher connected through the owner's signed-in "
        f"{teacher} CLI/OAuth session. Answer as Alice's configured teacher "
        "substrate for this turn. Do not claim external actions, do not mutate "
        "files, and do not speak as a separate Alice. Use the supplied SIFTA "
        "chat history as context and return only the reply text.",
        "",
        "SIFTA CHAT HISTORY:",
    ]
    for msg in messages or []:
        role = str(msg.get("role") or "user").strip() or "user"
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        chunks.append(f"[{role}]\n{content}")
    return "\n\n".join(chunks).strip()


def _stream_claude_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 180,
) -> Iterator[Tuple[str, Any]]:
    cli = shutil.which("claude")
    if not cli:
        yield ("error", "Claude CLI is not on PATH; run `claude auth` or install Claude Code.")
        return

    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    prompt = _to_teacher_cli_prompt(messages, teacher="Claude")
    bare = strip_prefix(model)
    cmd = [
        cli,
        "-p",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--output-format",
        "text",
        prompt,
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        yield ("error", f"Claude CLI timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"Claude CLI launch failed: {exc}")
        return

    if proc.returncode != 0:
        snippet = (proc.stderr or proc.stdout or "").strip()[:500]
        yield ("error", f"Claude CLI failed (rc={proc.returncode}): {snippet or 'no output'}")
        return

    text = (proc.stdout or "").strip()
    if not text:
        yield ("error", "Claude CLI returned empty output.")
        return

    usage = Usage(
        model=bare,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw={"transport": "claude_cli_print", "requested_model": bare},
    )
    record_usage(usage, backend="claude_cli")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


def _stream_codex_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 240,
) -> Iterator[Tuple[str, Any]]:
    cli = shutil.which("codex")
    if not cli:
        yield ("error", "Codex CLI is not on PATH; sign in/install Codex before selecting this teacher.")
        return

    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    bare = strip_prefix(model)
    prompt = _to_teacher_cli_prompt(messages, teacher="Codex")
    out_dir = _STATE / "codex_teacher_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{tag}.txt"
    cmd = [
        cli,
        "exec",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--cd",
        str(_REPO),
        "--output-last-message",
        str(out_path),
    ]
    configured_model = os.environ.get("SIFTA_CODEX_CLI_MODEL", "").strip()
    if configured_model:
        cmd.extend(["--model", configured_model])
    cmd.append(prompt)

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        yield ("error", f"Codex CLI timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"Codex CLI launch failed: {exc}")
        return

    if proc.returncode != 0:
        snippet = (proc.stderr or proc.stdout or "").strip()[:500]
        yield ("error", f"Codex CLI failed (rc={proc.returncode}): {snippet or 'no output'}")
        return

    text = ""
    try:
        text = out_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        pass
    if not text:
        text = (proc.stdout or "").strip()
    if not text:
        yield ("error", "Codex CLI returned empty output.")
        return

    usage = Usage(
        model=configured_model or bare,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw={
            "transport": "codex_cli_exec_read_only",
            "requested_model": bare,
            "configured_model": configured_model,
            "output_path": str(out_path),
        },
    )
    record_usage(usage, backend="codex_cli")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


def _stream_qwen_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 180,
) -> Iterator[Tuple[str, Any]]:
    cli = shutil.which("qwen")
    if not cli:
        yield ("error", "Qwen Code CLI is not on PATH; install qwen before selecting this teacher.")
        return

    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    bare = strip_prefix(model)
    prompt = _to_teacher_cli_prompt(messages, teacher="Qwen/Fireworks")
    try:
        from System.swarm_fireworks_qwen_config import (
            FIREWORKS_DEFAULT_MODEL,
            qwen_fireworks_child_env,
            qwen_fireworks_command,
        )

        cmd = qwen_fireworks_command(
            prompt,
            model=bare if bare else FIREWORKS_DEFAULT_MODEL,
            read_only=True,
            timeout_s=timeout_s,
        )
        env = qwen_fireworks_child_env(os.environ, state_dir=_STATE)
    except Exception as exc:
        yield ("error", f"Qwen Fireworks config unavailable: {exc}")
        return

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=timeout_s + 10,
            env=env,
        )
    except subprocess.TimeoutExpired:
        yield ("error", f"Qwen CLI timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"Qwen CLI launch failed: {exc}")
        return

    if proc.returncode != 0:
        snippet = (proc.stderr or proc.stdout or "").strip()[:500]
        yield ("error", f"Qwen CLI failed (rc={proc.returncode}): {snippet or 'no output'}")
        return

    text = (proc.stdout or "").strip()
    if not text:
        yield ("error", "Qwen CLI returned empty output.")
        return

    usage = Usage(
        model=bare,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw={"transport": "qwen_cli_fireworks_read_only", "requested_model": bare},
    )
    record_usage(usage, backend="qwen_fireworks_cli")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


def _stream_cline_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 180,
) -> Iterator[Tuple[str, Any]]:
    cli = shutil.which("cline")
    if not cli:
        yield ("error", "Cline CLI is not on PATH; install/sign in before selecting this teacher.")
        return

    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    bare = strip_prefix(model)
    prompt = _to_teacher_cli_prompt(messages, teacher="Cline")
    cmd = [
        cli,
        "--json",
        "--auto-approve",
        "false",
        "--cwd",
        str(_REPO),
        "--timeout",
        str(max(1, int(timeout_s))),
        "--plan",
        prompt,
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=timeout_s + 10,
        )
    except subprocess.TimeoutExpired:
        yield ("error", f"Cline CLI timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"Cline CLI launch failed: {exc}")
        return

    raw = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        yield ("error", f"Cline CLI failed (rc={proc.returncode}): {raw[:500] or 'no output'}")
        return
    if not raw:
        yield ("error", "Cline CLI returned empty output.")
        return

    text_parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            text_parts.append(line)
            continue
        for key in ("text", "message", "content", "output"):
            value = row.get(key) if isinstance(row, dict) else None
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
                break
    text = "\n".join(text_parts).strip() or raw
    usage = Usage(
        model=bare,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw={"transport": "cline_cli_plan_json", "requested_model": bare},
    )
    record_usage(usage, backend="cline_cli")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


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
    if _is_grok_model(model):
        yield from _stream_grok_chat(
            model,
            messages,
            temperature=temperature,
            api_key=api_key,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return
    if _is_claude_model(model):
        yield from _stream_claude_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return
    if _is_codex_model(model):
        yield from _stream_codex_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return
    if _is_qwen_model(model):
        yield from _stream_qwen_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return
    if _is_cline_model(model):
        yield from _stream_cline_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return

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
    record_usage(usage, backend="gemini")
    yield ("usage", usage)
    yield ("done", full_text)


# ─────────────────────────────────────────────────────────────────────
# Token ledger — the data layer the gas-station meter reads
# ─────────────────────────────────────────────────────────────────────
def record_usage(u: Usage, *, backend: str = "gemini") -> None:
    """Append one ledger row. Best-effort; ledger errors never break a
    chat turn (we'd rather lose a meter tick than drop a reply)."""
    row = {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": str(backend or "gemini"),
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
    "is_cloud_model",
    "is_gemini_model",
    "strip_prefix",
    "display_label",
    "gemini_api_key",
    "xai_api_key",
    "available_gemini_models",
    "available_cloud_models",
    "stream_chat",
    "record_usage",
    "read_ledger",
    "summarize_ledger",
]
