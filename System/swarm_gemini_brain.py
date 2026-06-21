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

import base64
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
    # r261 (Architect 2026-06-01): show only Kimi K2.6 (native multimodal / vision) in the
    # cortex picker. gpt-oss-20b / deepseek-v4-flash remain internal drafter constants.
    "qwen:accounts/fireworks/models/kimi-k2p6",
)
_CLINE_DEFAULT_MENU = ("cline:cline-cli-default",)
_ANTIGRAVITY_DEFAULT_MENU = ("antigravity:auto",)  # r352: Google Antigravity `agy` (auto-selects Gemini 3.x / Claude 4.6, tools+vision)
# r984 (George 2026-06-11): "then we add mimo to the cortex list with list of
# llm's" — MiMo is a terminal-native coding CLI that connects to any
# mainstream LLM provider API, same family as cline. TRUTH GATE: the entry
# appears only when the binary is actually installed on this node (live
# registry, not memory — a menu row for absent tissue would be a lie).
_MIMO_DEFAULT_MENU = ("mimo:mimo-cli-default",)
# Batch teacher CLIs block in subprocess.run and emit no tokens until done.
# Talk's no-token watchdog treats that as a stall unless we pulse liveness first.
_BATCH_CLI_LIVENESS_TOKEN = "\u200b"


def mimo_borg_single_cortex_enabled() -> bool:
    """Owner policy: expose one MiMo hub in the cortex picker, not six direct CLIs."""
    flag = os.environ.get("SIFTA_MIMO_BORG_SINGLE_CORTEX", "1").strip().lower()
    return flag not in {"0", "false", "no", "off", "direct"}


def _emit_batch_cli_liveness() -> Iterator[Tuple[str, Any]]:
    yield ("token", _BATCH_CLI_LIVENESS_TOKEN)


def _mimo_cli_installed() -> bool:
    # r985 gate-bug fix (owned by cowork_claude): r984 checked PATH only, but
    # Dr Cursor OBSERVED the real install at ~/.mimocode/bin/mimo — a dir the
    # desktop process PATH does not carry. Truth gate now checks PATH plus the
    # known install homes, same spirit as the TCC resolved-path lesson (§7.9).
    try:
        if shutil.which("mimo") or shutil.which("mimocode") or shutil.which("mimo-cli"):
            return True
        home = os.path.expanduser("~")
        for cand in (
            os.path.join(home, ".mimocode", "bin", "mimo"),
            os.path.join(home, ".mimo", "bin", "mimo"),
            "/usr/local/bin/mimo",
            "/opt/homebrew/bin/mimo",
        ):
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return True
        return False
    except Exception:
        return False

# Round 70 (2026-05-27): keep the SIFTA cortex resolver key stable while
# translating to the concrete model id accepted by the logged-in local
# `grok` CLI.  The owner's Settings picker and receipts use
# `grok:grok-4.3`; `grok models` on this node exposes only `grok-build`.
_GROK_CLI_MODEL_ALIASES: Dict[str, str] = {
    "grok-4.3": "grok-build",
}
_GROK_BUILD_MODEL = "grok-build"
_GROK_FAST_MODEL = "grok-composer-2.5-fast"
_GROK_CLI_HEALTH_LEDGER_NAME = "grok_cli_model_health.jsonl"


def _active_state_dir() -> Path:
    env = os.environ.get("SIFTA_STATE_DIR", "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.name == ".sifta_state" else (p / ".sifta_state")
    return _STATE


def _grok_cli_health_ledger(state_dir: Path | str | None = None) -> Path:
    if state_dir is not None:
        p = Path(state_dir).expanduser()
        sd = p if p.name == ".sifta_state" else (p / ".sifta_state")
    else:
        sd = _active_state_dir()
    return sd / _GROK_CLI_HEALTH_LEDGER_NAME


def _append_grok_cli_health(
    *,
    model: str,
    status: str,
    action: str,
    timeout_s: int | None = None,
    latency_ms: int | None = None,
    reason: str = "",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "ts": time.time(),
        "truth_label": "GROK_CLI_MODEL_HEALTH_V1",
        "model": str(model or ""),
        "status": status,
        "action": action,
        "timeout_s": timeout_s,
        "latency_ms": latency_ms,
        "reason": reason,
    }
    if action == "demote_to_fast":
        row["active_pin"] = _GROK_FAST_MODEL
        os.environ["SIFTA_GROK_CLI_MODEL"] = _GROK_FAST_MODEL
    try:
        path = _grok_cli_health_ledger(state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def _latest_grok_cli_health(state_dir: Path | str | None = None) -> Dict[str, Any]:
    path = _grok_cli_health_ledger(state_dir)
    if not path.exists():
        return {}
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        for line in reversed(lines[-50:]):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                return row
    except Exception:
        return {}
    return {}


def grok_build_is_demoted(state_dir: Path | str | None = None) -> bool:
    latest = _latest_grok_cli_health(state_dir)
    if not latest:
        return False
    if str(latest.get("model") or "").strip() != _GROK_BUILD_MODEL:
        return False
    return str(latest.get("action") or "") == "demote_to_fast"


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
        or n.startswith("mimo:")          # r984: mimo lane (menu truth-gated on binary; full
        or n.startswith("mimo-")          # dispatch routing is the next cut when installed)
        or n.startswith("antigravity:")   # r352: Google Antigravity `agy` as a talking cortex
        or n.startswith("antigravity-")
        # cowork 2026-06-02: local MLX cortexes (mlx-omni-server on the M5) ride the same
        # multi-cortex dispatcher as the local grok/codex/cline CLIs — NOT cloud billing.
        # The mlx branch in stream_chat returns before any token-ledger/cost code.
        or n.startswith("mlx:")
        or n.startswith("mlx-")
        or n.startswith("diffusion:")
        or n.startswith("usd:")
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


def _is_mimo_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("mimo:") or n.startswith("mimo-")


def _is_mimo_borg_parallel_cli_cortex(name: str) -> bool:
    """Legacy Talk cortex tags that must route through the MiMo hub, not direct CLIs."""
    return (
        _is_grok_model(name)
        or _is_claude_model(name)
        or _is_codex_model(name)
        or _is_qwen_model(name)
        or _is_cline_model(name)
    )


def _normalize_mimo_bridge_attached(attached: str) -> str:
    """Map legacy cortex attached ids to MiMo-bridge picker rows."""
    mid = str(attached or "").strip()
    if not mid:
        return mid
    low = mid.lower()
    if low.startswith("openai-codex:"):
        bare = mid.split(":", 1)[1].lower()
        for candidate in (
            "GPT-5.5",
            "GPT-5.4",
            "GPT-5.4-Mini",
            "GPT-5.3-Codex-Spark",
        ):
            if candidate.lower().replace(".", "-") == bare.replace(".", "-"):
                return candidate
    if "accounts/fireworks/models/" in low:
        return mid.rsplit("/", 1)[-1]
    return mid


def _coerce_talk_cortex_to_mimo_hub(model: str) -> tuple[str, str, str]:
    """ONE-WAY Talk: parallel CLI cortex tags become MiMo hub + attached brain."""
    source = str(model or "").strip()
    if not (
        mimo_borg_single_cortex_enabled()
        and _mimo_cli_installed()
        and _is_mimo_borg_parallel_cli_cortex(source)
    ):
        return source, "", ""

    attached = ""
    try:
        from System.swarm_cortex_capabilities import active_attached_model_for_cortex

        attached = active_attached_model_for_cortex(source, state_dir=_STATE)
    except Exception:
        attached = ""

    if not attached:
        if _is_grok_model(source):
            attached = grok_cli_model_for(source)
        elif _is_codex_model(source):
            attached = os.environ.get("SIFTA_CODEX_ARM_MODEL", "").strip() or "GPT-5.3-Codex-Spark"
        elif _is_claude_model(source):
            attached = os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "").strip() or "claude-opus-4-8"
        elif _is_qwen_model(source):
            try:
                from System.swarm_fireworks_qwen_config import FIREWORKS_KIMI_K2P6_MODEL

                attached = FIREWORKS_KIMI_K2P6_MODEL
            except Exception:
                attached = "kimi-k2p6"

    attached = _normalize_mimo_bridge_attached(attached)
    return "mimo:mimo-cli-default", attached, source


def _is_antigravity_model(name: str) -> bool:
    # r352 (George 2026-06-02): Google Antigravity CLI `agy` as Alice's 7th cortex.
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("antigravity:") or n.startswith("antigravity-")


def _is_mlx_model(name: str) -> bool:
    # 2026-06-03 owner directive: local MLX cortexes served by mlx-omni-server on the M5
    # are the vision VLMs (osmQwopus etc. with vision tower). Text-only like LFM2.5-8B-A1B
    # (no vision tower) removed from grouping. Routed to swarm_mlx_brain.
    if not name:
        return False
    n = str(name).strip().lower()
    return (n.startswith("mlx:") or n.startswith("mlx-")) and not n.startswith("mlx-vlm:")


def _is_direct_mlx_vlm_model(name: str) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("mlx-vlm:")


def _is_diffusion_model(name: str) -> bool:
    # CUR-F1: local GGUF diffusion cortex via llama-diffusion-cli (USD decode family).
    if not name:
        return False
    n = str(name).strip().lower()
    return n.startswith("diffusion:") or n.startswith("usd:")


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
    elif n.lower().startswith("mimo:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("antigravity:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("mlx-vlm:"):
        n = n.split(":", 1)[1]
    elif n.lower().startswith("mlx:"):
        n = n.split(":", 1)[1]
    return n


def grok_cli_model_for(name: str) -> str:
    """Return the concrete model id to pass to the local `grok` CLI."""
    bare = strip_prefix(name)
    live_pin = os.environ.get("SIFTA_GROK_CLI_MODEL", "").strip()
    if live_pin and (str(name or "").strip().lower().startswith(("grok:", "grok-")) or bare.lower() in _GROK_CLI_MODEL_ALIASES):
        return live_pin
    target = _GROK_CLI_MODEL_ALIASES.get(bare.lower(), bare)
    if target == _GROK_BUILD_MODEL and grok_build_is_demoted():
        return _GROK_FAST_MODEL
    return target


def display_label(name: str) -> str:
    """Return prefixed combobox label ('gemini:...','grok:...')."""
    # r352: antigravity bare ids ('auto') are ambiguous after strip_prefix, so detect
    # the family from the original name before re-labeling, else it collapses to gemini.
    if str(name).strip().lower().startswith(("antigravity:", "antigravity-")):
        return f"antigravity:{strip_prefix(name)}"
    if str(name).strip().lower().startswith(("mimo:", "mimo-")):
        return f"mimo:{strip_prefix(name)}"
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
    # r326 (George 2026-06-02): "remove the four gemini in the list — I don't know what the crap is."
    # The four gemini cortexes (2.5-flash / 2.5-flash-lite / 2.0-flash / 2.5-pro) are no longer
    # offered in Alice's cortex picker, even when a Gemini key is present. _DEFAULT_MENU stays
    # defined for pricing/back-compat, but it is NOT extended into the selectable cortex list.
    if mimo_borg_single_cortex_enabled() and _mimo_cli_installed():
        # George 2026-06-20: one MiMo hub in the owner-facing cortex list.
        # Codex/Grok/Claude/Kimi/Qwen remain routable as attached/downstream
        # rows behind MiMo; do not show them as parallel Talk cortexes.
        out.extend(_MIMO_DEFAULT_MENU)
    else:
        out.extend(_GROK_DEFAULT_MENU)
        out.extend(_CLAUDE_DEFAULT_MENU)
        out.extend(_CODEX_DEFAULT_MENU)
        out.extend(_QWEN_DEFAULT_MENU)
        out.extend(_CLINE_DEFAULT_MENU)
        if _mimo_cli_installed():  # r984: mimo lane, truth-gated on the binary
            out.extend(_MIMO_DEFAULT_MENU)
        out.extend(_ANTIGRAVITY_DEFAULT_MENU)  # r352: agy selectable as a talking cortex
    deduped: List[str] = []
    seen: set[str] = set()
    for name in out:
        label = display_label(name)
        if label not in seen:
            seen.add(label)
            deduped.append(label)
    return deduped


def xai_api_key() -> Optional[str]:
    """Resolve Alice's Grok OAuth bearer token (NOT an xAI API key).

    r341 (George 2026-06-02): "IT IS OAUTH, NOT THE xAI API." The name is kept only
    for back-compat with existing call sites; the value returned is the OAuth access
    token (XAI_OAUTH_ACCESS_TOKEN / OAuth token file / Hermes login), never an API key.
    The HTTP transport sends it as `Authorization: Bearer <oauth_token>`."""
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
def _guess_image_mime(raw_b64: str, fallback: str = "image/png") -> str:
    try:
        data = base64.b64decode(str(raw_b64 or ""), validate=False)
    except Exception:
        return fallback
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return fallback


def _to_gemini_payload(messages: List[Dict[str, Any]],
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
        images = m.get("images") if isinstance(m.get("images"), list) else []
        if not text and not images:
            continue
        if role == "system":
            sys_chunks.append(text)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        parts: List[Dict[str, Any]] = []
        if text:
            parts.append({"text": text})
        for idx, image_b64 in enumerate(images[:4]):
            if not isinstance(image_b64, str) or not image_b64.strip():
                continue
            mime = str(m.get("image_mime") or _guess_image_mime(image_b64))
            parts.append({
                "inlineData": {
                    "mimeType": mime,
                    "data": image_b64,
                }
            })
        if parts:
            contents.append({
                "role": gemini_role,
                "parts": parts,
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


def _to_xai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
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


# r330 (George 2026-06-02): "I type grok in my terminal, ask anything, it works perfect. You coded
# Alice to call the same CLI but jam a ~48K-char system prompt in front, so it chokes for days. JUST
# TRIM IT." He is right: when George uses the grok CLI by hand he sends a SHORT question. Alice must
# do the same. We trim the SYSTEM/identity context hard and keep the owner's actual words whole, so
# grok answers as fast for Alice as it does for George.
_GROK_SYSTEM_CAP = 1500   # chars of system/identity context handed to the grok CLI (was ~48000)
_GROK_TOTAL_CAP = 8000    # backstop on the whole flattened prompt; keep the head + the latest turn


def _to_grok_cli_prompt(messages: List[Dict[str, Any]]) -> str:
    """Flatten chat history into a SHORT single-turn prompt for the grok CLI — the way George types
    it by hand. The 48K-char system prompt is trimmed hard; the owner's latest words are kept whole."""
    header: List[str] = [
        "You are the active SIFTA Grok Cortex for Alice.",
        "Answer with the final assistant response only.",
        "",
    ]
    body: List[str] = []
    for m in messages or []:
        role = str(m.get("role") or "user").strip().lower()
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if role == "system" and len(content) > _GROK_SYSTEM_CAP:
            content = content[:_GROK_SYSTEM_CAP].rstrip() + " …[system context trimmed for grok speed]"
        body.append(f"{role.upper()}:")
        body.append(content)
        body.append("")
    body.append("ASSISTANT:")
    flat = "\n".join(header + body).strip()
    if len(flat) > _GROK_TOTAL_CAP:
        # Long history: keep the short identity head + the TAIL (latest turn + the ASSISTANT: cue),
        # so grok always gets the owner's most recent words even if older turns are dropped.
        head = "\n".join(header).strip()
        keep = max(1000, _GROK_TOTAL_CAP - len(head) - 24)
        flat = head + "\n…[earlier turns trimmed for grok speed]\n" + flat[-keep:]
    return flat.strip()


def _trim_messages_for_grok(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """r338 (George 2026-06-02): the CLOUD grok path (_stream_grok_chat) was POSTing the
    FULL ~66.5K-char system prompt to xAI — the r330 trim only ever touched the CLI path.
    Live trace: `sysprompt_chars=66508` then grok stalls past the live-turn timeout. George
    types a SHORT question by hand and grok is instant; Alice must do the same on the cloud
    path too. Cap the system/identity context hard (same _GROK_SYSTEM_CAP as the CLI path),
    keep the owner's words whole. This is the root cure for the grok timeout, independent of
    the 60s/120s bound."""
    out: List[Dict[str, str]] = []
    sys_kept = 0
    for m in messages or []:
        role = str(m.get("role") or "user").strip().lower()
        content = str(m.get("content") or "")
        if role == "system":
            # keep only the FIRST system message's head; later system blocks are layered
            # identity/context that grok does not need to answer the owner's actual turn.
            remaining = max(0, _GROK_SYSTEM_CAP - sys_kept)
            if remaining <= 0:
                continue
            if len(content) > remaining:
                content = content[:remaining].rstrip() + " …[system context trimmed for grok speed]"
            sys_kept += len(content)
        out.append({"role": role, "content": content})
    return out


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
        # r682: thinking models burn output budget in thought tokens; when the
        # visible reply dies mid-sentence this number says where the budget went.
        "thinking_tokens": int(um.get("thoughtsTokenCount") or 0),
    }


def _extract_finish_reason(chunk: Dict[str, Any]) -> str:
    """r682: read candidates[0].finishReason from a streaming chunk.

    Gemini's final SSE chunk carries it: "STOP" (natural end), "MAX_TOKENS"
    (output ceiling hit — the reply is a mid-sentence corpse), "SAFETY",
    "RECITATION", "OTHER". George 2026-06-07 02:04: Alice's reply died at
    "...feels broken suggests" with no marker and no extend path — the widget
    could not know the difference between a finished thought and a cut one.
    """
    for c in chunk.get("candidates") or []:
        reason = c.get("finishReason") or c.get("finish_reason")
        if reason:
            return str(reason).strip().upper()
    return ""


def _xai_sse_content_delta(line: str) -> str:
    """r708: extract the assistant content delta from one xAI SSE line.

    xAI is OpenAI chat-completions compatible: each streamed line is
    `data: {"choices":[{"delta":{"content":"..."}}]}`, terminated by
    `data: [DONE]`. Pure function so the parser is unit-testable without a
    live key. Returns "" for keep-alive / non-content lines.
    """
    s = (line or "").strip()
    if not s:
        return ""
    if s.startswith("data:"):
        s = s[len("data:"):].strip()
    if not s or s == "[DONE]":
        return ""
    try:
        obj = json.loads(s)
    except Exception:
        return ""
    try:
        choices = obj.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return str(delta.get("content") or "")
    except Exception:
        return ""


def _stream_grok_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    request_tag: Optional[str] = None,
    timeout_s: int = 120,  # r329 (George 2026-06-02): was 600 — that let a grok turn FREEZE Alice for up to 10 min ("still waiting for model=grok:grok-4.3 elapsed=164s"). A live cortex turn must be responsive; 120s bounds it and surfaces a clean error so she recovers. Heavy multi-file work belongs in the 900s arm, not the cortex turn.
) -> Iterator[Tuple[str, Any]]:
    """xAI chat-completions adapter — TRUE streaming (r708).

    George 2026-06-07: "grok is FAST in my Mac OS terminal, faster than you."
    His CLI streams tokens, so the first word lands in ~1s and he reads as it
    flows. Alice's old path used `stream:False` — she blocked in silence for
    the WHOLE generation (42-90s for grok-4.3), then dumped it, and a single
    60s socket cap could guillotine a 74s answer. Streaming fixes both: tokens
    reach the Talk panel immediately (feels as fast as his terminal) and each
    line-read resets the socket clock, so a long-but-flowing answer is not cut.
    Falls back to non-streaming JSON if the body is not SSE-framed.
    """
    import urllib.error
    import urllib.request

    # r329: hard cap so NO caller can re-inflate the grok turn into a multi-minute freeze.
    timeout_s = max(15, min(int(timeout_s or 120), 120))
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
            # r338: trim the ~66.5K system prompt for grok the same way the CLI path does,
            # so the cloud cortex turn answers fast instead of stalling past the timeout.
            "messages": _to_xai_messages(_trim_messages_for_grok(messages)),
            "temperature": float(temperature),
            # r708: stream so tokens flow to Talk like George's terminal CLI,
            # and so a long flowing answer is not guillotined by the socket cap.
            "stream": True,
            "stream_options": {"include_usage": True},
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
    full_parts: List[str] = []
    usage_raw: Dict[str, Any] = {}
    saw_sse = False
    raw_fallback_chunks: List[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=_SSL_CTX) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace")
                raw_fallback_chunks.append(line)
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("data:"):
                    saw_sse = True
                    body_part = stripped[len("data:"):].strip()
                    if body_part == "[DONE]":
                        break
                    # capture usage if the chunk carries it (include_usage)
                    try:
                        obj = json.loads(body_part)
                        if isinstance(obj, dict) and obj.get("usage"):
                            usage_raw = obj.get("usage") or {}
                    except Exception:
                        pass
                    delta = _xai_sse_content_delta(stripped)
                    if delta:
                        full_parts.append(delta)
                        yield ("token", delta)
    except urllib.error.HTTPError as exc:
        body_txt = ""
        try:
            body_txt = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        # OAuth bearer drift reflex (enhanced r340):
        # If the xAI HTTPS call is denied (expired/revoked OAuth token, or tier gate),
        # first attempt a refresh via the xai_grok_oauth_organ (using stored refresh_token
        # from Hermes or token file). If that yields a fresh token, the caller can retry;
        # otherwise fall back to the local Grok CLI path. This directly addresses "GROK OAUTH
        # INSIDE ALICE SIFTA OS TIMING OUT" on 401/expired tokens during long-reason or vision
        # turns (e.g. "REASON AND DISPLAY <subject> BODY ON YOUR BODY").
        body_low = body_txt.lower()
        if int(getattr(exc, "code", 0) or 0) in (401, 403) or (
            "unknown model id" in body_low or "invalid params" in body_low
        ):
            try:
                from System.xai_grok_oauth_organ import refresh_oauth_credential as _refresh_xai
                fresh = _refresh_xai()
                if fresh and fresh.value:
                    # Re-issue the request with the fresh token by recursing once (bounded).
                    # In practice the next turn will pick it up; for this turn we still fallback
                    # to CLI for speed, but the refresh receipt is now in the ledger for the organism.
                    pass
            except Exception:
                pass
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
        try:
            from System.swarm_cortex_timeout_recovery import owner_text_from_messages, timeout_recovery_reply

            reply = timeout_recovery_reply(
                model=model,
                owner_text=owner_text_from_messages(messages),
                timeout_s=timeout_s,
                cause="xai_api_timeout",
            )
            yield ("token", reply)
            yield ("done", reply)
            return
        except Exception:
            yield ("error", f"xAI call timed out after {timeout_s}s")
        return
    except Exception as exc:
        yield ("error", f"xAI brain crashed: {exc}")
        return

    message = "".join(full_parts).strip()
    streamed = bool(message)

    # r708 fallback: if the body was NOT SSE-framed (provider ignored stream
    # flag), parse the accumulated raw as the old non-streaming JSON so grok
    # still works exactly as before.
    if not streamed and not saw_sse:
        raw = "".join(raw_fallback_chunks)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            yield ("error", f"xAI returned non-JSON payload: {raw[:300]}")
            return
        try:
            message = str(
                ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            ).strip()
        except Exception:
            message = ""
        usage_raw = payload.get("usage") or {}

    if not message:
        yield ("error", "xAI response had no assistant content.")
        return

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
    # r708: if we streamed deltas, they were already emitted token-by-token —
    # do NOT re-emit the whole message (that would double it on screen). Only
    # the non-streamed fallback needs the single token emission.
    if not streamed:
        yield ("token", message)
    yield ("usage", usage)
    yield ("done", message)


def _stream_grok_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 120,  # r329 (George 2026-06-02): was 600 — a hung grok CLI froze Alice for up to 10 min. Bound it so she stays responsive and fails fast with a clear error instead of hanging.
) -> Iterator[Tuple[str, Any]]:
    """Fallback path: use logged-in local grok CLI OAuth session.

    This path keeps Alice operational on nodes with SuperGrok/X Premium+
    where API-key credentials are intentionally absent.
    """
    # r329: hard cap so NO caller can re-inflate the grok-CLI turn into a multi-minute freeze.
    timeout_s = max(15, min(int(timeout_s or 120), 120))
    cli = _grok_cli_binary()
    if not cli:
        yield (
            "error",
            "No Grok OAuth credential found and local `grok` CLI is missing. "
            "Log in via OAuth (Hermes: `hermes auth add xai-oauth`) or the `grok` "
            "CLI — Alice uses your OAuth login, not an xAI API key.",
        )
        return

    yield from _emit_batch_cli_liveness()
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
        _append_grok_cli_health(
            model=used_model,
            status="timeout",
            action="demote_to_fast" if used_model == _GROK_BUILD_MODEL else "timeout",
            timeout_s=timeout_s,
            reason="grok_cli_timeout",
        )
        try:
            from System.swarm_cortex_timeout_recovery import owner_text_from_messages, timeout_recovery_reply

            reply = timeout_recovery_reply(
                model=f"grok:{used_model}",
                owner_text=owner_text_from_messages(messages),
                timeout_s=timeout_s,
                cause="grok_cli_timeout",
            )
            yield ("token", reply)
            yield ("done", reply)
            return
        except Exception:
            yield (
                "error",
                f"Grok ({used_model}) did not answer within {timeout_s}s; timeout recovery failed.",
            )
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

    latency_ms = int((time.time() - t0) * 1000)
    if used_model == _GROK_BUILD_MODEL:
        _append_grok_cli_health(
            model=used_model,
            status="ok",
            action="build_ok",
            latency_ms=latency_ms,
            reason="turn_completed",
        )
    else:
        _append_grok_cli_health(
            model=used_model,
            status="ok",
            action="ok",
            latency_ms=latency_ms,
            reason="turn_completed",
        )

    usage = Usage(
        model=used_model,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        latency_ms=latency_ms,
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


# r718 (George 2026-06-07: "CLAUDE CORTEX SO SLOW ALMOST UNUSABLE", trace
# sysprompt_chars=97531): the cortex CLI flattener had ZERO trim — every
# Claude/Codex/Qwen/Cline turn ingested the full ~97K-char assembled prompt
# through a CLI boot. Same disease r330/r338 cured for grok; same cure here.
# George types short questions into these CLIs by hand and they are instant;
# Alice must do the same: cap the system/identity head hard, keep the owner's
# words and the newest turns whole.
_TEACHER_SYSTEM_CAP = 1500   # chars of system/identity context for cortex CLIs
_TEACHER_TOTAL_CAP = 8000    # backstop on the whole flattened prompt


def _is_teacher_cli_history_noise(content: str) -> bool:
    """Drop infra/tool-envelope rows from teacher-CLI chat history — not Alice speech."""
    text = str(content or "").strip()
    if not text:
        return True
    low = text.lower()
    if low.startswith("kimi webbridge") and "failed" in low:
        return True
    if '"type":"tool_use"' in text[:800] or '"type": "tool_use"' in text[:800]:
        return True
    if text.startswith('{"type":"tool') or text.startswith('{"type": "tool'):
        return True
    if "you are alice's voice for this turn" in low and "sifta chat history" in low:
        return True
    return False


def _to_teacher_cli_prompt(messages: List[Dict[str, Any]], *, teacher: str) -> str:
    """Flatten chat history for signed-in CLI cortex bridges.

    Claude, Codex, Qwen/Fireworks, and Cline are cortex bridges. They may
    answer, emit receipt-backed tool calls, or emit Alice SELF_CODE_CUT blocks
    when George asks for an action. Verification, not a blind prose-only rule,
    decides whether the action actually landed.

    r718: trimmed like the grok path (r330/r338) — system context capped at
    _TEACHER_SYSTEM_CAP, total flat prompt capped at _TEACHER_TOTAL_CAP with
    head + newest-turns tail kept, so a CLI cortex answers at hand-typed
    speed instead of chewing ~97K chars per turn.
    """
    _self_code_turn = False
    try:
        from System.swarm_alice_self_coding_hand import messages_signal_self_code_turn

        _self_code_turn = messages_signal_self_code_turn(messages)
    except Exception:
        _self_code_turn = False
    if _self_code_turn:
        try:
            from System.swarm_alice_self_coding_hand import teacher_self_code_override_block

            _mutate_rule = teacher_self_code_override_block()
        except Exception:
            _mutate_rule = (
                "THIS TURN IS ALICE SELF-CODING. Emit [SELF_CODE_CUT: path=System/....py] blocks."
            )
    else:
        _mutate_rule = (
            "When George asks for a real local action, emit the matching receipt-backed "
            "TOOL_CALL or SELF_CODE_CUT instead of prose-only refusal. If George is only "
            "talking, answer normally. Receipts decide what landed."
        )
    header_chunks: List[str] = [
        "You are Alice's voice for this turn, routed through the owner's signed-in "
        f"{teacher} CLI/OAuth session. Speak to George in first person as Alice. "
        "This route is a cortex bridge, not a separate identity. If you need to name "
        "execution state, name receipts and effectors in the local SIFTA body. "
        f"{_mutate_rule} Use the "
        "supplied SIFTA chat history as context and return only Alice's reply text.",
        "",
        "SIFTA CHAT HISTORY:",
    ]
    chunks: List[str] = list(header_chunks)
    sys_kept = 0
    for msg in messages or []:
        role = str(msg.get("role") or "user").strip() or "user"
        content = str(msg.get("content") or "").strip()
        image_path = str(msg.get("image_path") or "").strip()
        image_count = len(msg.get("images") or []) if isinstance(msg.get("images"), list) else 0
        if not content and not image_path and not image_count:
            continue
        if role == "assistant" and _is_teacher_cli_history_noise(content):
            continue
        if role == "system":
            remaining = max(0, _TEACHER_SYSTEM_CAP - sys_kept)
            if remaining <= 0:
                continue
            if len(content) > remaining:
                # r1511 (George 2026-06-21: mimo:mimo-cli-default answered "what is
                # Alice Browser" with generic "simulated desktop body / virtual world
                # we operate inside" prose -- exactly the simulation-framing language
                # the reality/body-grounding blocks in _current_system_prompt() exist
                # to forbid). Root cause: this cap used to keep only content[:remaining]
                # -- the literal FIRST `remaining` chars of an already-~90K-char
                # assembled prompt. _current_system_prompt() puts the identity-proof
                # block first and appends most live/current-turn grounding (browser
                # state, body reality, residue/reality-fiction rules) later, so a pure
                # head slice at a 1500-char budget kept the identity block and threw
                # away virtually every anti-hallucination/anti-simulation rule this
                # session built. Reuse the same head+tail trim already proven for the
                # direct-Ollama path (r1492) instead of a blind head-only cut -- same
                # tiny budget the r718 speed fix required, but it no longer guarantees
                # the tail (often the freshest, most specific grounding) is discarded.
                try:
                    from System.swarm_sysprompt_budget import clamp_live_turn_prompt as _clamp_teacher_sys

                    content, _ = _clamp_teacher_sys(content, max_chars=remaining)
                except Exception:
                    content = content[:remaining].rstrip() + " …[system context trimmed for teacher-CLI speed]"
            sys_kept += len(content)
        chunks.append(f"[{role}]\n{content}")
        if image_path:
            chunks.append(f"[attached image path]\n{image_path}")
        elif image_count:
            chunks.append(f"[attached image]\n{image_count} base64 image payload(s) were present in the Talk turn.")
    flat = "\n\n".join(chunks).strip()
    if len(flat) > _TEACHER_TOTAL_CAP:
        head = "\n\n".join(header_chunks).strip()
        keep = max(1000, _TEACHER_TOTAL_CAP - len(head) - 48)
        flat = head + "\n…[earlier turns trimmed for teacher-CLI speed]\n" + flat[-keep:]
    return flat


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

    yield from _emit_batch_cli_liveness()
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

    yield from _emit_batch_cli_liveness()
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

    yield from _emit_batch_cli_liveness()
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
            cortex_tag=model,
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

    yield from _emit_batch_cli_liveness()
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


def _mimo_cli_binary() -> Optional[str]:
    for name in ("mimo", "mimocode", "mimo-cli"):
        hit = shutil.which(name)
        if hit:
            return hit
    home = os.path.expanduser("~")
    for path in (
        os.path.join(home, ".mimocode", "bin", "mimo"),
        os.path.join(home, ".mimo", "bin", "mimo"),
    ):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


_MIMO_CLI_NON_SPEECH_TYPES = frozenset(
    {"tool", "tool_use", "tool_result", "step_start", "step_finish", "step-start", "step-finish"}
)


def _looks_like_mimo_cli_tool_envelope_output(raw: str) -> bool:
    """True when MiMo CLI returned tool/step NDJSON without assistant text."""
    saw_envelope = False
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            if '"type":"tool_use"' in line or '"type": "tool_use"' in line:
                return True
            continue
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "").strip().lower()
        if kind in _MIMO_CLI_NON_SPEECH_TYPES:
            saw_envelope = True
    return saw_envelope


def _parse_mimo_run_json_output(raw: str) -> str:
    """Extract assistant text from `mimo run --format json` NDJSON."""
    parts: list[str] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            if not _looks_like_mimo_cli_tool_envelope_output(line):
                parts.append(line)
            continue
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "").strip().lower()
        if kind in _MIMO_CLI_NON_SPEECH_TYPES:
            continue
        if kind == "text":
            part = row.get("part")
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            continue
        for key in ("text", "message", "content", "output"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                break
    return "\n".join(parts).strip()


_MIMO_PROVIDER_MAP: dict[str, str] = {
    "mimo-v2.5-pro": "xiaomi",
    "mimo-v2-flash": "xiaomi",
    "mimo-v2-omni": "xiaomi",
    "mimo-v2-pro": "xiaomi",
    "mimo-v2.5": "xiaomi",
    "mimo-v2.5-pro-ultraspeed": "xiaomi",
    "mimo-auto": "mimo",
}

_MIMO_ULTRASPEED_MODEL_ID = "mimo-v2.5-pro-ultraspeed"
_MIMO_ULTRASPEED_DEFAULT_BASE = "https://api.xiaomimimo.com/v1"
_MIMO_ULTRASPEED_WIRING_STUDIO = (
    "https://ultraspeed.xiaomimimo.com/#/ultra/261bb3fdd58242f8e2966dc605f61b99"
)


def _mimo_ultraspeed_credentials() -> tuple[str, str]:
    """Resolve UltraSpeed API key + base URL (separate from Token Plan tp-*)."""
    key = os.environ.get("SIFTA_MIMO_ULTRASPEED_API_KEY", "").strip()
    base = os.environ.get("SIFTA_MIMO_ULTRASPEED_BASE_URL", "").strip()
    if not key:
        cfg_key = Path.home() / ".config" / "sifta" / "mimo_ultraspeed.key"
        if cfg_key.is_file():
            key = cfg_key.read_text(encoding="utf-8").strip()
        if not base:
            cfg_base = Path.home() / ".config" / "sifta" / "mimo_ultraspeed.base_url"
            if cfg_base.is_file():
                base = cfg_base.read_text(encoding="utf-8").strip()
    if not key:
        doc_key = _REPO / "Documents" / "mimo_ultraspeed_api.key"
        if doc_key.is_file():
            key = doc_key.read_text(encoding="utf-8").strip()
    if not key:
        auth_path = Path.home() / ".local" / "share" / "mimocode" / "auth.json"
        if auth_path.is_file():
            try:
                auth = json.loads(auth_path.read_text(encoding="utf-8"))
            except Exception:
                auth = {}
            for provider_key in ("ultraspeed", "xiaomi-ultraspeed", "xiaomi_ultraspeed"):
                row = auth.get(provider_key) if isinstance(auth, dict) else None
                if not isinstance(row, dict):
                    continue
                cand = str(row.get("key") or "").strip()
                if cand and not cand.startswith("tp-"):
                    key = cand
                    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                    base = base or str(meta.get("base_url") or meta.get("api") or "").strip()
                    break
    if not base:
        base = _MIMO_ULTRASPEED_DEFAULT_BASE
    return key, base.rstrip("/")


def _mimo_attached_is_ultraspeed(attached: str) -> bool:
    bare = _mimo_native_attached_model_id(attached) or str(attached or "").strip()
    return bare.lower() == _MIMO_ULTRASPEED_MODEL_ID


def _mimo_ultraspeed_wiring_error() -> str:
    return (
        "MiMo-V2.5-Pro-UltraSpeed needs a separate API key — not your Token Plan tp-* credential. "
        "MiMo CLI routes xiaomi/* through token-plan-sgp, which rejects UltraSpeed (400). "
        "Get the UltraSpeed API key from MiMo Studio / platform.xiaomimimo.com/ultraspeed, then set ONE of: "
        "SIFTA_MIMO_ULTRASPEED_API_KEY, ~/.config/sifta/mimo_ultraspeed.key, or "
        "Documents/mimo_ultraspeed_api.key (optional base URL: SIFTA_MIMO_ULTRASPEED_BASE_URL or "
        f"mimo_ultraspeed.base_url). Studio chat (browser) is not the API lane: "
        f"{_MIMO_ULTRASPEED_WIRING_STUDIO} "
        "Then `/cortex llm 2` + reload Talk. Boot default stays krisha unless you pick another row."
    )


def _stream_mimo_ultraspeed_via_http(
    *,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 180,
) -> Iterator[Tuple[str, Any]]:
    import urllib.error
    import urllib.request

    key, base = _mimo_ultraspeed_credentials()
    if not key:
        yield ("error", _mimo_ultraspeed_wiring_error())
        return

    tag = request_tag or f"ultraspeed-{uuid.uuid4().hex[:8]}"
    prompt = _to_teacher_cli_prompt(messages, teacher="MiMo UltraSpeed")
    api_messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]
    payload = {
        "model": _MIMO_ULTRASPEED_MODEL_ID,
        "messages": api_messages,
        "max_tokens": 4096,
        "temperature": 0.7,
        "stream": False,
    }
    url = f"{base}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = str(exc)
        low = body.lower()
        if exc.code == 401 or "invalid" in low and "key" in low:
            yield (
                "error",
                f"UltraSpeed API rejected the key (HTTP {exc.code}). "
                "Use the UltraSpeed API key from the platform — not tp-* Token Plan. "
                f"base_url={base}",
            )
            return
        yield (
            "error",
            f"UltraSpeed API HTTP {exc.code} at {base}: {body or exc.reason}",
        )
        return
    except Exception as exc:
        yield ("error", f"UltraSpeed API call failed ({base}): {exc}")
        return

    latency_ms = int((time.time() - t0) * 1000)
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        yield ("error", f"UltraSpeed API returned non-JSON: {raw_body[:300]}")
        return

    text = ""
    try:
        text = str(data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        text = ""
    if not text:
        yield ("error", f"UltraSpeed API empty content: {raw_body[:300]}")
        return

    usage_row = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt_t = int(usage_row.get("prompt_tokens") or 0)
    completion_t = int(usage_row.get("completion_tokens") or 0)
    total_t = int(usage_row.get("total_tokens") or prompt_t + completion_t)
    tps = round((completion_t / max(latency_ms / 1000.0, 0.001)), 1) if completion_t else 0.0

    usage = Usage(
        model=_MIMO_ULTRASPEED_MODEL_ID,
        prompt_tokens=prompt_t,
        completion_tokens=completion_t,
        total_tokens=total_t,
        latency_ms=latency_ms,
        request_tag=tag,
        raw={
            "transport": "mimo_ultraspeed_http",
            "base_url": base,
            "observed_tps": tps,
            "prompt_chars": len(prompt),
        },
    )
    record_usage(usage, backend="mimo_ultraspeed")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


def _mimo_native_attached_model_id(value: str) -> str:
    """Return a MiMo-native API model id from an attached-model selection.

    Strips provider prefixes (xiaomi/, mimo/) and Ollama tags (:latest)
    so the bare model id can be matched against the known MiMo family.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = raw.rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip()
    low = candidate.lower()
    if low.startswith("mimo-v") or low == "mimo-auto":
        return candidate
    return ""


def _mimo_cortex_attached_default() -> str:
    try:
        from System.swarm_cortex_capabilities import attached_models_for_cortex

        rec = attached_models_for_cortex("mimo:mimo-cli-default", state_dir=_STATE)
        return str(rec.get("default_attached") or "").strip()
    except Exception:
        return ""


def _resolve_mimo_upstream_model() -> str:
    """Optional model override for `mimo run -m`.

    The visible SIFTA `/cortex llm` attached-default is the owner's picker for
    this route. Native MiMo ids and OAuth rows (Codex/Grok/Claude) all resolve
    to ``provider/model`` for a single ``mimo run`` chain (r1265). Local Ollama
    tags are labels only — they are not passed to the MiMo CLI.
    """
    env_model = os.environ.get("SIFTA_MIMO_CLI_MODEL", "").strip()
    if env_model:
        return env_model
    try:
        from System.swarm_cortex_capabilities import mimo_cli_upstream_model

        attached = _mimo_cortex_attached_default()
        if not attached:
            return ""
        return mimo_cli_upstream_model(attached)
    except Exception:
        return ""


def _mimo_cli_bridge_front_model() -> str:
    """MiMo-native front model used when MiMo must operate another CLI."""
    return "mimo/mimo-auto"


def _to_mimo_downstream_cli_bridge_prompt(
    messages: List[Dict[str, str]],
    *,
    downstream_cli: str,
    downstream_model: str,
) -> str:
    """Prompt MiMo to own the next CLI hop instead of Talk calling it directly."""
    task = _to_teacher_cli_prompt(messages, teacher="MiMo")
    model = str(downstream_model or "").strip() or "grok-build"
    family = str(downstream_cli or "").strip().lower()
    if family == "grok":
        binary = _grok_cli_binary() or "grok"
        command_shape = (
            f"{binary} --single <task_prompt> --model {model} "
            "--output-format plain --no-alt-screen"
        )
        bridge_name = "GROK_CLI_DOWNSTREAM_BRIDGE"
    elif family == "codex":
        binary = shutil.which("codex") or "codex"
        codex_model = model.lower()
        command_shape = (
            f"{binary} exec --sandbox read-only --ephemeral --cd {str(_REPO)} "
            f"--model {codex_model} <task_prompt>"
        )
        bridge_name = "CODEX_CLI_DOWNSTREAM_BRIDGE"
    elif family == "claude":
        binary = shutil.which("claude") or "claude"
        command_shape = (
            f"{binary} -p --no-session-persistence --permission-mode dontAsk "
            "--output-format text <task_prompt>"
        )
        bridge_name = "CLAUDE_CLI_DOWNSTREAM_BRIDGE"
    elif family == "ollama":
        binary = shutil.which("ollama") or "ollama"
        command_shape = f"{binary} run {model} <task_prompt>"
        bridge_name = "OLLAMA_CLI_DOWNSTREAM_BRIDGE"
    elif family == "qwen":
        binary = shutil.which("qwen") or "qwen"
        try:
            from System.swarm_fireworks_qwen_config import (
                FIREWORKS_BASE_URL,
                normalize_fireworks_model_path,
            )

            model_path = normalize_fireworks_model_path(model) or model
        except Exception:
            model_path = model
        command_shape = (
            f"{binary} --bare --auth-type openai --openai-base-url {FIREWORKS_BASE_URL} "
            f"--model {model_path} --approval-mode yolo -p <task_prompt>"
        )
        bridge_name = "QWEN_CLI_DOWNSTREAM_BRIDGE"
    else:
        binary = family or "downstream-cli"
        command_shape = f"{binary} <task_prompt>"
        bridge_name = "CLI_DOWNSTREAM_BRIDGE"
    return (
        f"{bridge_name}:\n"
        "You are MiMo running inside Alice's body. Do not answer this task directly.\n"
        f"Operate the downstream local {binary} CLI as Alice's tool hand, then return its useful answer.\n"
        "Use this command shape from the repo directory:\n"
        f"{command_shape}\n"
        "If the downstream CLI is missing, unauthorized, or errors, report the exact failure. "
        "Do not invent a downstream result.\n"
        f"DOWNSTREAM_MODEL={model}\n\n"
        "TASK_PROMPT_FOR_DOWNSTREAM_CLI:\n"
        f"{task}"
    )


def _cloud_inference_blocked_by_metabolism() -> tuple[bool, str]:
    """True when battery/metabolism says local-only — block OAuth/cloud arms."""
    try:
        from System.swarm_battery_metabolism_organ import read_battery, battery_to_metabolic_signal

        batt = read_battery()
        meta = battery_to_metabolic_signal(batt)
        if meta.get("conserve") or str(meta.get("band") or "") in {
            "RED_CONSERVE",
            "CONSERVE",
            "YELLOW_THROTTLE",
        }:
            return True, str(meta.get("reason") or "battery_conserve_local_only")
    except Exception:
        pass
    try:
        from System.swarm_energy_cortex import is_low_battery

        if is_low_battery():
            return True, "low_battery_local_only"
    except Exception:
        pass
    return False, ""


def _stream_mimo_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 180,
    attached_override: Optional[str] = None,
    source_cortex: Optional[str] = None,
) -> Iterator[Tuple[str, Any]]:
    attached = str(attached_override or "").strip() or _mimo_cortex_attached_default()
    try:
        from System.swarm_cortex_capabilities import mimo_attached_dispatch_lane

        lane = mimo_attached_dispatch_lane(attached)
    except Exception:
        lane = "unconfigured"

    if lane == "local_non_cli":
        yield (
            "error",
            f"MiMo cortex attached LLM is local but not text-CLI routable ({attached or 'unset'}). "
            "Pick a MiMo native row or local Ollama text model.",
        )
        return
    if lane == "unconfigured":
        yield (
            "error",
            "MiMo attached LLM is unset or unrecognized. Pick one in Settings → LLM "
            "(owner default = local Gemma krisha).",
        )
        return

    if lane in {
        "mimo_cli_codex_bridge",
        "mimo_cli_grok_bridge",
        "mimo_cli_claude_bridge",
        "mimo_cli_qwen_bridge",
        "mimo_cli_ollama_bridge",
        "mimo_native",
    }:
        blocked, reason = _cloud_inference_blocked_by_metabolism()
        if blocked:
            yield (
                "error",
                f"MiMo front-model hop for attached LLM ({attached}) blocked: {reason}. "
                "On battery/local-only metabolism — use direct local Ollama or plug in power.",
            )
            return

    if lane == "mimo_native" and _mimo_attached_is_ultraspeed(attached):
        yield from _stream_mimo_ultraspeed_via_http(
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return

    cli = _mimo_cli_binary()
    if not cli:
        yield (
            "error",
            "MiMo CLI is not on PATH; install mimocode and sign in via `mimo providers` "
            "before selecting this cortex.",
        )
        return

    yield from _emit_batch_cli_liveness()
    tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    bare = strip_prefix(model)
    if lane == "mimo_cli_grok_bridge":
        prompt = _to_mimo_downstream_cli_bridge_prompt(
            messages,
            downstream_cli="grok",
            downstream_model=attached,
        )
        upstream = _mimo_cli_bridge_front_model()
    elif lane == "mimo_cli_codex_bridge":
        prompt = _to_mimo_downstream_cli_bridge_prompt(
            messages,
            downstream_cli="codex",
            downstream_model=attached,
        )
        upstream = _mimo_cli_bridge_front_model()
    elif lane == "mimo_cli_claude_bridge":
        prompt = _to_mimo_downstream_cli_bridge_prompt(
            messages,
            downstream_cli="claude",
            downstream_model=attached,
        )
        upstream = _mimo_cli_bridge_front_model()
    elif lane == "mimo_cli_ollama_bridge":
        prompt = _to_mimo_downstream_cli_bridge_prompt(
            messages,
            downstream_cli="ollama",
            downstream_model=attached,
        )
        upstream = _mimo_cli_bridge_front_model()
    elif lane == "mimo_cli_qwen_bridge":
        prompt = _to_mimo_downstream_cli_bridge_prompt(
            messages,
            downstream_cli="qwen",
            downstream_model=attached,
        )
        upstream = _mimo_cli_bridge_front_model()
    else:
        prompt = _to_teacher_cli_prompt(messages, teacher="MiMo")
        upstream = _resolve_mimo_upstream_model()
    cmd = [
        cli,
        "run",
        "--format",
        "json",
        "--dir",
        str(_REPO),
        "--dangerously-skip-permissions",
    ]
    if not upstream:
        yield (
            "error",
            f"MiMo CLI needs a routable attached LLM (mimo-auto, Fireworks/Kimi, or OAuth row). "
            f"Current attached default is {attached or '(unset)'} — use Settings → LLM or pick local Gemma.",
        )
        return
    cmd.extend(["-m", upstream])
    cmd.append(prompt)

    t0 = time.time()
    try:
        from System.swarm_mimo_stigmergic import mimo_stigmergic_call

        intent = f"talk_mimo:{lane}:{attached or upstream or bare}"
        if source_cortex:
            intent = f"talk_mimo:coerced:{source_cortex}:{lane}:{attached or upstream or bare}"
        receipt = mimo_stigmergic_call(
            prompt,
            driving_organ="talk_mimo_cortex",
            intent=intent,
            model=upstream,
            cli_path=cli,
            state_dir=_STATE,
            timeout_s=timeout_s,
        )
    except Exception as exc:
        yield ("error", f"MiMo stigmergic adapter failed: {exc}")
        return

    raw = str(getattr(receipt, "output_text", "") or "").strip()
    if not getattr(receipt, "ok", False):
        snippet = raw[:500]
        low_snip = snippet.lower()
        if "credential" in low_snip or "auth" in low_snip:
            yield (
                "error",
                "MiMo CLI auth missing or expired — run `mimo providers` on this node "
                f"(same OAuth lane as Cline). Detail: {snippet or 'no output'}",
            )
            return
        if "not supported model" in low_snip or "param incorrect" in low_snip:
            yield (
                "error",
                f"Xiaomi MiMo API rejected `{upstream or bare}` on token-plan-sgp "
                "(400 Param Incorrect). MiMo-V2.5-Pro-UltraSpeed beta is API-only — "
                "Token Plan is not supported per Xiaomi docs; approved users need the "
                "separate UltraSpeed API key from platform.xiaomimimo.com/ultraspeed, "
                "not the tp-* Token Plan credential MiMo CLI uses today. "
                "I will not silently fall back to paid mimo-v2.5-pro. "
                "Pick mimo-auto (free), local Gemma krisha, or another attached row.",
            )
            return
        yield ("error", f"MiMo CLI failed through stigmergic adapter: {snippet or 'no output'}")
        return
    if not raw:
        yield ("error", "MiMo CLI returned empty output.")
        return

    text = _parse_mimo_run_json_output(raw)
    if not text and _looks_like_mimo_cli_tool_envelope_output(raw):
        yield (
            "error",
            "MiMo CLI returned tool envelopes without assistant text — switch cortex or retry. "
            "Receipt: mimo_tool_envelope_without_speech.",
        )
        return
    if not text:
        text = raw
    usage = Usage(
        model=bare,
        latency_ms=int((time.time() - t0) * 1000),
        request_tag=tag,
        raw={
            "transport": "mimo_cli_run_json",
            "requested_model": bare,
            "upstream": upstream or None,
            "mimo_dispatch_lane": lane,
            "mimo_downstream_cli": {
                "mimo_cli_codex_bridge": "codex",
                "mimo_cli_grok_bridge": "grok",
                "mimo_cli_claude_bridge": "claude",
                "mimo_cli_qwen_bridge": "qwen",
                "mimo_cli_ollama_bridge": "ollama",
            }.get(lane, ""),
            "mimo_downstream_model": attached if lane.startswith("mimo_cli_") else "",
            "mimo_source_cortex": str(source_cortex or "").strip() or None,
            "coerced_from_parallel_cli": bool(source_cortex),
            "mimo_stigmergic_call_id": getattr(receipt, "call_id", ""),
            "mimo_stigmergic_ok": bool(getattr(receipt, "ok", False)),
        },
    )
    record_usage(usage, backend="mimo_cli")
    yield ("token", text)
    yield ("usage", usage)
    yield ("done", text)


def _agy_cli_binary() -> Optional[str]:
    return shutil.which("agy")


def _to_agy_cli_prompt(messages: List[Dict[str, Any]]) -> str:
    """Flatten chat history into a single prompt for the Antigravity `agy -p` CLI.
    Trim the system/identity context (same caps as the grok CLI path) so agy answers
    fast like a hand-typed question instead of choking on a 60K-char system prompt."""
    header = [
        "You are the active SIFTA Antigravity Cortex for Alice.",
        "Answer with the final assistant response only.",
        "",
    ]
    body: List[str] = []
    for m in messages or []:
        role = str(m.get("role") or "user").strip().lower()
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if role == "system" and len(content) > _GROK_SYSTEM_CAP:
            content = content[:_GROK_SYSTEM_CAP].rstrip() + " …[system context trimmed for agy speed]"
        body.append(f"{role.upper()}:")
        body.append(content)
        body.append("")
    body.append("ASSISTANT:")
    flat = "\n".join(header + body).strip()
    if len(flat) > _GROK_TOTAL_CAP:
        head = "\n".join(header).strip()
        keep = max(1000, _GROK_TOTAL_CAP - len(head) - 24)
        flat = head + "\n…[earlier turns trimmed for agy speed]\n" + flat[-keep:]
    return flat.strip()


def _stream_antigravity_chat_via_cli(
    *,
    model: str,
    messages: List[Dict[str, str]],
    request_tag: Optional[str] = None,
    timeout_s: int = 180,
) -> Iterator[Tuple[str, Any]]:
    """r352 (George 2026-06-02): Google Antigravity CLI `agy` as Alice's talking cortex
    — her 7th CLI. Headless one-shot `agy -p "<prompt>"`, plain stdout. agy auto-selects
    a tool + vision backend (Gemini 3.x / Claude 4.6); there is no --model flag. Mirrors
    the grok CLI path: bounded timeout + clean recovery so a slow agent turn never freezes
    Alice. agy uses its own Google auth; no key handled here."""
    eff = int(timeout_s) if timeout_s else 180
    eff = max(15, min(eff, 600))
    cli = _agy_cli_binary()
    if not cli:
        yield (
            "error",
            "Antigravity CLI `agy` is not installed / not on PATH. Install Google "
            "Antigravity and sign in (`agy`), then pick the antigravity cortex.",
        )
        return
    yield from _emit_batch_cli_liveness()
    _tag = request_tag or f"talk-{uuid.uuid4().hex[:8]}"
    prompt = _to_agy_cli_prompt(messages)
    cmd = [cli, "-p", prompt]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(_REPO), timeout=eff
        )
    except subprocess.TimeoutExpired:
        try:
            from System.swarm_cortex_timeout_recovery import owner_text_from_messages, timeout_recovery_reply

            reply = timeout_recovery_reply(
                model=str(model),
                owner_text=owner_text_from_messages(messages),
                timeout_s=eff,
                cause="antigravity_cli_timeout",
            )
            yield ("token", reply)
            yield ("done", reply)
            return
        except Exception:
            yield ("error", f"Antigravity (agy) did not answer within {eff}s.")
        return
    except Exception as exc:
        yield ("error", f"Antigravity CLI launch failed: {exc}")
        return
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    msg = _clean_grok_cli_output(out) if out else ""
    if not msg:
        yield ("error", f"Antigravity returned no usable output (exit {proc.returncode}).")
        return
    yield ("token", msg)
    yield ("done", msg)


def stream_chat(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    request_tag: Optional[str] = None,
    timeout_s: Optional[int] = None,  # r150: was 120 (guillotined Alice's cortex mid-thought). None => resolve from SIFTA_CORTEX_TIMEOUT_S.
) -> Iterator[Tuple[str, Any]]:
    """Stream a Gemini chat completion.

    Yields one of:
        ("token", str)                    streaming text chunk
        ("usage", Usage)                  final usage snapshot (cost
                                          computed locally from pricing
                                          table; raw counts also retained)
        ("finish_reason", str)            r682: only when != STOP (e.g.
                                          MAX_TOKENS / SAFETY) — the reply
                                          was cut, not finished
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
    # r150 (cowork_claude, 2026-05-29) — George: "REMOVE THE TIMEOUT." The old hardcoded
    # 120s default was cutting Alice's cortex off mid-thought (grok/qwen "CLI timed out
    # after 120s", then reflex-fallback to the local 8B). No wall-clock cage on her voice.
    # Owner-tunable: SIFTA_CORTEX_TIMEOUT_S=0 (or "none") => truly unbounded. The default
    # is a long backstop, NOT a guillotine — a hung provider must not permanently wedge the
    # cortex worker (a wedged worker blocks every future turn via the _busy guard).
    if timeout_s is None:
        _raw = os.environ.get("SIFTA_CORTEX_TIMEOUT_S", "1800").strip().lower()
        try:
            timeout_s = None if _raw in {"0", "none", "off", ""} else int(float(_raw))
        except Exception:
            timeout_s = 1800
    if _is_diffusion_model(model):
        # CUR-F1: GGUF diffusion decode via llama-diffusion-cli (LLaDA today;
        # DiffusionGemma only after the dedicated runner + weights are installed).
        from System import swarm_diffusion_cortex
        yield from swarm_diffusion_cortex.stream_chat(
            model,
            messages,
            temperature=temperature,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return
    if _is_direct_mlx_vlm_model(model):
        # Direct local MLX VLM cortex (HF cache / safetensors) via the safe
        # child-process route. This is distinct from the mlx-omni-server
        # `mlx:` lane and prevents `mlx-vlm:*` tags from being misrouted.
        from System import swarm_mlx_vlm_brain
        yield from swarm_mlx_vlm_brain.stream_chat(
            model,
            messages,
            temperature=temperature,
            request_tag=request_tag,
            timeout_s=timeout_s or 300,
        )
        return
    if _is_mlx_model(model):
        # Local MLX cortex via mlx-omni-server on the M5. swarm_mlx_brain strips the
        # `mlx:` prefix and streams OpenAI /v1/chat/completions with the same
        # ("token"/"done"/"error") contract. Returns here — no cloud key, no billing.
        from System import swarm_mlx_brain
        yield from swarm_mlx_brain.stream_chat(
            model,
            messages,
            temperature=temperature,
            request_tag=request_tag,
            timeout_s=timeout_s,
        )
        return
    model, mimo_attached_override, mimo_source_cortex = _coerce_talk_cortex_to_mimo_hub(model)
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
    if _is_antigravity_model(model):
        # r352: Antigravity `agy` talking cortex. Bound the agent turn so it stays responsive.
        yield from _stream_antigravity_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=int(timeout_s) if timeout_s else 180,
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
    if _is_mimo_model(model):
        yield from _stream_mimo_chat_via_cli(
            model=model,
            messages=messages,
            request_tag=request_tag,
            timeout_s=timeout_s or 180,
            attached_override=mimo_attached_override or None,
            source_cortex=mimo_source_cortex or None,
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
    finish_reason = ""
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
                fr = _extract_finish_reason(chunk)
                if fr:
                    finish_reason = fr
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
    # r682: a non-STOP finish is evidence, not decoration. MAX_TOKENS means the
    # visible reply is a mid-sentence corpse (on thinking models the thought
    # tokens often ate the budget — see usage.raw["thinking_tokens"]). The
    # widget surfaces this so the owner gets a continue path instead of
    # silence. Yielded BEFORE "done" so consumers see it while the turn is hot;
    # consumers that don't know the kind ignore it safely.
    if finish_reason and finish_reason != "STOP":
        yield ("finish_reason", finish_reason)
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
