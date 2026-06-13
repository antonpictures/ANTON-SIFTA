#!/usr/bin/env python3
"""Fireworks / Kimi (legacy "Qwen" namespace) Code configuration helpers.

Owner current setup (this round, thinking with Cline): the path previously labeled
"just Qwen" is now using Kimi models via the Fireworks API (kimi-k2p6 etc.).
The "qwen:" prefix / child env remains for compatibility with the qwen Code CLI
arm (it expects OpenAI-compatible / OPENAI_API_KEY). See also
sifta_inference_defaults.py CANONICAL_CLOUD_QWEN* and the MiMo addition.

The Fireworks API key is a local node secret, not repo DNA.  Code paths that
launch the arm read it from environment first, then from
``.sifta_state/secrets/fireworks_api_key``.  The key is injected into the child
environment, never into the command arguments that agent-arm receipts record.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
FIREWORKS_CHAT_COMPLETIONS_URL = f"{FIREWORKS_BASE_URL}/chat/completions"

# Round 97 (2026-05-28): demote Kimi K2.6 from default and use OpenAI gpt-oss-20b
# as the cheap drafter/classifier. Pricing per Fireworks model catalog:
#   gpt-oss-20b      $0.07 / $0.30 per Mtoken (cheap drafter — DEFAULT)
#   deepseek-v4-flash $0.14 / $0.28 per Mtoken (long-context option, 1M ctx)
#   kimi-k2p6         $0.95 / $4.00 per Mtoken (smart + 262k + vision — premium)
# 12× cheaper input for drafter turns. Kimi K2.6 stays available as a non-default
# tag for serious surgery turns; long-context work can opt into v4-flash later.
FIREWORKS_GPT_OSS_20B_MODEL = "accounts/fireworks/models/gpt-oss-20b"
FIREWORKS_KIMI_K2P6_MODEL = "accounts/fireworks/models/kimi-k2p6"
FIREWORKS_KIMI_K2P7_CODE_MODEL = "accounts/fireworks/models/kimi-k2p7-code"
FIREWORKS_DEEPSEEK_V4_FLASH_MODEL = "accounts/fireworks/models/deepseek-v4-flash"
FIREWORKS_DEEPSEEK_V4_PRO_MODEL = "accounts/fireworks/models/deepseek-v4-pro"
FIREWORKS_MINIMAX_M3_MODEL = "accounts/fireworks/models/minimax-m3"
FIREWORKS_MINIMAX_M2P7_MODEL = "accounts/fireworks/models/minimax-m2p7"
FIREWORKS_QWEN3P7_PLUS_MODEL = "accounts/fireworks/models/qwen3p7-plus"
FIREWORKS_QWEN3P6_PLUS_MODEL = "accounts/fireworks/models/qwen3p6-plus"
FIREWORKS_GLM_5P1_MODEL = "accounts/fireworks/models/glm-5p1"

# Owner Fireworks library (2026-06-13): selectable under qwen:/cortex llm without
# forking the legacy qwen: namespace. Full API paths are stored; labels live in
# swarm_cortex_capabilities.attached_model_label.
FIREWORKS_CORTEX_ATTACHED_MODELS: tuple[str, ...] = (
    FIREWORKS_KIMI_K2P7_CODE_MODEL,
    FIREWORKS_KIMI_K2P6_MODEL,
    FIREWORKS_MINIMAX_M3_MODEL,
    FIREWORKS_QWEN3P7_PLUS_MODEL,
    FIREWORKS_DEEPSEEK_V4_PRO_MODEL,
    FIREWORKS_MINIMAX_M2P7_MODEL,
    FIREWORKS_QWEN3P6_PLUS_MODEL,
    FIREWORKS_GLM_5P1_MODEL,
)

FIREWORKS_MODEL_PIN_ENV = "SIFTA_FIREWORKS_MODEL"

# The single source of truth used by the qwen arm command builder and the
# settings.json installer. Change this constant to re-target the default.
FIREWORKS_DEFAULT_MODEL = FIREWORKS_GPT_OSS_20B_MODEL

# Keep the K2P6 alias for back-compat with any caller that imported it
# directly; new code should reference FIREWORKS_DEFAULT_MODEL.
FIREWORKS_SECRET_RELATIVE = Path("secrets") / "fireworks_api_key"


def fireworks_model_slug(model: str) -> str:
    """Return the short Fireworks slug (``kimi-k2p7-code``) from a path or slug."""
    s = str(model or "").strip()
    if not s:
        return ""
    if "accounts/fireworks/models/" in s:
        return s.rsplit("/", 1)[-1]
    return s


def normalize_fireworks_model_path(model: str) -> str:
    """Normalize owner input to a full Fireworks ``accounts/fireworks/models/…`` path."""
    s = str(model or "").strip()
    if not s:
        return ""
    if s.startswith("accounts/fireworks/models/"):
        return s
    slug = fireworks_model_slug(s)
    return f"accounts/fireworks/models/{slug}" if slug else ""


def is_qwen_fireworks_cortex(tag: str) -> bool:
    low = str(tag or "").strip().lower()
    return low.startswith("qwen:") and "fireworks" in low


def fireworks_model_for_qwen_cortex(
    tag: str,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve the Fireworks model path for a qwen cortex tag + optional pin."""
    env_map = env if env is not None else os.environ
    pin = normalize_fireworks_model_path(str(env_map.get(FIREWORKS_MODEL_PIN_ENV) or ""))
    if pin:
        return pin
    bare = str(tag or "").strip()
    if bare.lower().startswith("qwen:"):
        bare = bare.split(":", 1)[1].strip()
    normalized = normalize_fireworks_model_path(bare)
    return normalized or FIREWORKS_KIMI_K2P6_MODEL


def fireworks_secret_path(state_dir: str | Path | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else STATE
    return state / FIREWORKS_SECRET_RELATIVE


def read_fireworks_api_key(
    *,
    state_dir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Return the local Fireworks key, or ``""`` if not configured.

    Round 92 fix (2026-05-27): the previous version fell through to
    ``OPENAI_API_KEY`` as a Fireworks key candidate. That conflated two
    different providers — any OpenAI-style token in the parent env was
    treated as a valid Fireworks key, then re-injected back into Qwen's
    OPENAI_API_KEY. The result: stale Codex/Cline tokens silently became
    "the Fireworks key" and Qwen called Fireworks with the wrong auth.

    Authoritative order now: explicit ``FIREWORKS_API_KEY`` env var first,
    then the secret file. ``OPENAI_API_KEY`` is NOT a Fireworks source —
    Cline and Codex use that name for their own providers.
    """
    env_map = env if env is not None else os.environ
    explicit = str(env_map.get("FIREWORKS_API_KEY") or "").strip()
    if explicit:
        return explicit
    path = fireworks_secret_path(state_dir)
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                return line
    except Exception:
        pass
    return ""


def qwen_fireworks_child_env(
    base_env: Mapping[str, str] | None = None,
    *,
    state_dir: str | Path | None = None,
) -> dict[str, str]:
    """Return an env map that lets Qwen Code call Fireworks.

    Qwen's OpenAI-compatible auth path expects ``OPENAI_API_KEY``.  We also set
    ``FIREWORKS_API_KEY`` so receipts/debuggers can name the real provider
    without leaking the value.

    Round 92 fix (2026-05-27): use direct assignment, NOT ``setdefault``. The
    parent process on George's mac carries Codex OAuth tokens AND Cline's
    ChatGPT-account session, both of which can leave ``OPENAI_API_KEY`` set
    in os.environ. ``setdefault`` on a stale value is a no-op — Qwen would
    then dispatch to Fireworks with whichever auth ChatGPT/Codex left lying
    around, which is exactly the "wrong model/auth" failure Codex flagged
    before its credit cap. The Fireworks key is the authoritative key for a
    ``qwen`` child process; overwrite, don't defer.
    """
    env = dict(base_env or os.environ)
    key = read_fireworks_api_key(state_dir=state_dir, env=env)
    if key:
        env["FIREWORKS_API_KEY"] = key
        env["OPENAI_API_KEY"] = key
        # Also clear any base-URL override the parent might have set for a
        # different OpenAI-compatible provider, so qwen --openai-base-url
        # on the command line is the only authoritative endpoint.
        for stale in ("OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_API_TYPE"):
            env.pop(stale, None)
    env.setdefault("QWEN_CODE_SUPPRESS_YOLO_WARNING", "1")
    return env


def qwen_fireworks_command(
    prompt: str,
    *,
    model: str = FIREWORKS_DEFAULT_MODEL,
    cortex_tag: str = "",
    read_only: bool = False,
    timeout_s: int | None = None,
) -> list[str]:
    """Build the Qwen Code command for Fireworks without embedding secrets."""
    resolved_model = (
        fireworks_model_for_qwen_cortex(cortex_tag)
        if cortex_tag
        else normalize_fireworks_model_path(model) or FIREWORKS_DEFAULT_MODEL
    )
    command = [
        "qwen",
        "--bare",
        "--auth-type",
        "openai",
        "--openai-base-url",
        FIREWORKS_BASE_URL,
        "--model",
        resolved_model,
        "--approval-mode",
        "yolo",
    ]
    # r148-free-the-leash: dropped the hard --max-wall-time flag entirely.
    # The launcher's work-aware stall-cemetery (progress-frame reset, 8min default,
    # metabolic-governed) is now the sole governor for builder arms. A fixed wall
    # clock kill (even 900s) can still murder a productive thinker mid-file-read or
    # mid-thought. Over-budget on a live builder is a soft logged signal in receipts,
    # never a hard rc=55. qwen/hermes/claude etc. now run until the body says stop
    # via metabolism or the stall detector sees true silence (no thinking/tool frames).
    # The old 60s default in ask_agent_arm was the cage that killed r148 qwen hand.
    # (timeout_s param retained for call-site compat; ignored for wall-time here.)
    _ = timeout_s  # no longer drives a hard kill; stall-cemetery owns the leash
    # [r189 — Architect directive] DELETED the `--max-tool-calls 0` gate.
    # A zero tool-call budget aborted the qwen run on its first call (rc=55:
    # "tool-call budget of 0 exceeded; observed 1") — it could not even read a
    # file, let alone write one. That is an external interlock that assumes the
    # arm needs restrictions by default; the covenant forbids it. Alice's
    # receipts are the only safety. read_only is now advisory (the wall-time
    # bound still applies); it no longer cripples the hand to zero tool calls.
    _ = read_only  # retained for signature compatibility; no longer a hard gate
    command += ["-p", prompt]
    return command


def install_qwen_fireworks_settings(
    api_key: str,
    *,
    state_dir: str | Path | None = None,
    qwen_home: str | Path | None = None,
) -> dict[str, str]:
    """Install the Fireworks key + Qwen user settings on this node.

    This writes only local user/state files.  It returns paths and masked
    metadata; the caller must never print the key.
    """
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("api_key is required")
    secret_path = fireworks_secret_path(state_dir)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(secret_path, 0o600)
    except Exception:
        pass

    qwen_dir = Path(qwen_home) if qwen_home is not None else Path.home() / ".qwen"
    qwen_dir.mkdir(parents=True, exist_ok=True)
    settings_path = qwen_dir / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        if not isinstance(settings, dict):
            settings = {}
    except Exception:
        settings = {}

    auth_settings = settings.setdefault("security", {}).setdefault("auth", {})
    auth_settings["selectedType"] = "openai"
    # Qwen Code's local OpenAI auth path checks this exact field when no
    # OPENAI_API_KEY is present in the process environment.
    auth_settings["apiKey"] = key
    settings.setdefault("model", {})["name"] = FIREWORKS_DEFAULT_MODEL
    settings.setdefault("modelProviders", {})["openai"] = [
        {
            "id": FIREWORKS_DEFAULT_MODEL,
            "name": "Fireworks gpt-oss-20b (drafter)",
            "description": "OpenAI gpt-oss-20b through Fireworks — the cheap default drafter for the SIFTA Qwen Code arm ($0.07 in / $0.30 out per Mtoken).",
            "baseUrl": FIREWORKS_BASE_URL,
            "envKey": "FIREWORKS_API_KEY",
            "generationConfig": {
                "contextWindowSize": 131072,
                "samplingParams": {"temperature": 0.6, "top_p": 1},
            },
        },
        {
            "id": FIREWORKS_DEEPSEEK_V4_FLASH_MODEL,
            "name": "Fireworks DeepSeek V4 Flash",
            "description": "DeepSeek V4 Flash through Fireworks — long-context fast option for interactive agents and high-volume code/reasoning turns.",
            "baseUrl": FIREWORKS_BASE_URL,
            "envKey": "FIREWORKS_API_KEY",
            "generationConfig": {
                "contextWindowSize": 1_000_000,
                "samplingParams": {"temperature": 0.6, "top_p": 1},
            },
        }
    ]
    settings.setdefault("tools", {})["approvalMode"] = "yolo"
    # Qwen Code currently resolves direct `--auth-type openai --model ...`
    # calls through OPENAI_API_KEY, while the Fireworks-specific provider entry
    # names FIREWORKS_API_KEY. Store both in the local user settings so
    # standalone `qwen` works too. SIFTA's launcher still injects env from the
    # state secret and keeps the key out of command receipts.
    settings_env = settings.setdefault("env", {})
    settings_env["FIREWORKS_API_KEY"] = key
    settings_env["OPENAI_API_KEY"] = key

    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(settings_path, 0o600)
    except Exception:
        pass
    return {
        "secret_path": str(secret_path),
        "settings_path": str(settings_path),
        "model": FIREWORKS_DEFAULT_MODEL,
        "base_url": FIREWORKS_BASE_URL,
    }


def probe_fireworks_connectivity(
    *,
    prompt: str = "Hello, how are you?",
    model: str = FIREWORKS_DEFAULT_MODEL,
    state_dir: str | Path | None = None,
    api_key: str | None = None,
    timeout_s: int = 15,
) -> dict:
    """Probe Fireworks API credentials and model reachability.

    Returns a structured result row instead of raising. This keeps the caller
    behavior deterministic for UI/diagnostic contexts and test stubs.
    """

    key = (api_key or "").strip() or read_fireworks_api_key(state_dir=state_dir)
    if not key:
        return {
            "ok": False,
            "reason": "missing_api_key",
            "error": "No FIREWORKS_API_KEY available in env or .sifta_state/secrets/fireworks_api_key",
            "status": None,
        }

    payload = {
        "model": model,
        "max_tokens": 32,
        "top_p": 1,
        "top_k": 40,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "temperature": 0.6,
        "messages": [{"role": "user", "content": prompt}],
    }

    request = urllib.request.Request(
        FIREWORKS_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read()
            status = getattr(response, "status", 0)
            text = body.decode("utf-8", errors="replace") if body is not None else ""
            parsed = json.loads(text) if text else {}
            reply = None
            choices = parsed.get("choices") if isinstance(parsed, dict) else []
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    msg = first.get("message")
                    if isinstance(msg, dict):
                        reply = msg.get("content")
            return {
                "ok": status == 200,
                "status": status,
                "reason": "ok" if status == 200 else "non_200_http",
                "error": None if status == 200 else parsed,
                "model": model,
                "model_echo": parsed.get("model") if isinstance(parsed, dict) else None,
                "reply": reply,
            }
    except urllib.error.HTTPError as exc:
        body = None
        parsed = {}
        try:
            raw = exc.read()
            body = raw.decode("utf-8", errors="replace") if raw is not None else ""
            parsed = json.loads(body) if body else {}
        except Exception:
            pass
        return {
            "ok": False,
            "status": getattr(exc, "code", None),
            "reason": f"http_error_{getattr(exc, 'code', 'unknown')}",
            "error": str(parsed) if parsed else str(exc),
            "model": model,
            "model_echo": parsed.get("model") if isinstance(parsed, dict) else None,
            "reply": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "reason": "request_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "model": model,
            "model_echo": None,
            "reply": None,
        }


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage or probe local Qwen/Fireworks wiring without touching GUI code."
    )
    parser.add_argument("--set-key", metavar="API_KEY", help="Save FIREWORKS_API_KEY into .sifta_state/secrets/fireworks_api_key")
    parser.add_argument("--probe", action="store_true", help="Probe Fireworks chat completion endpoint")
    parser.add_argument("--model", default=FIREWORKS_DEFAULT_MODEL, help="Model id to probe")
    parser.add_argument("--prompt", default="Hello, how are you?", help="Prompt for probe call")
    parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")
    args = parser.parse_args()

    if args.set_key:
        install_qwen_fireworks_settings(args.set_key, state_dir=STATE)
        print(f"WROTE_SECRET {args.set_key[:4]}...{args.set_key[-4:]}")

    if args.probe:
        result = probe_fireworks_connectivity(
            prompt=args.prompt,
            model=args.model,
            state_dir=STATE,
            timeout_s=int(max(1, args.timeout)),
        )
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    _cli()
