#!/usr/bin/env python3
"""SIFTA xAI Grok authenticated-client organ.

This module does not mint credentials. It consumes node-local credentials only:
`XAI_API_KEY`, `XAI_OAUTH_ACCESS_TOKEN`, or a chmod-600 token file under
`.sifta_state/secrets/`. It can also reuse Hermes OAuth state from
`~/.hermes/auth.json` when xAI OAuth is logged in there.
Every attempted call writes a redacted local receipt.
"""

from __future__ import annotations

import json
import os
import base64
import mimetypes
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib import request


_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
_LEDGER = _STATE / "xai_grok_oauth_calls.jsonl"
_SECRET_DIR = _STATE / "secrets"
_TOKEN_FILE = _SECRET_DIR / "xai_grok_oauth_token.json"
_HERMES_AUTH_FILE = Path.home() / ".hermes" / "auth.json"
_API_URL = "https://api.x.ai/v1/responses"
_HERMES_XAI_PROVIDER_ALIASES = (
    "xai-oauth",
    "grok-oauth",
    "x-ai-oauth",
    "xai-grok-oauth",
    "xai",
)


@dataclass(frozen=True)
class XaiCredential:
    kind: str
    value: str
    source: str

    @property
    def redacted(self) -> str:
        return redact_secret(self.value)


def redact_secret(value: str) -> str:
    text = str(value or "")
    if len(text) <= 10:
        return "***"
    return f"{text[:5]}...{text[-4:]}"


def normalize_grok_model_id(model: str) -> str:
    """Normalize SIFTA Grok labels to the xAI API model id used by OAuth calls."""
    m = str(model or "").strip() or "grok-4"
    low = m.lower()
    if low.startswith(("grok:", "xai:")):
        m = m.split(":", 1)[1].strip()
    if "/" in m and "grok-" in m.lower():
        m = m.rsplit("/", 1)[-1].strip()
    return m or "grok-4"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def has_recent_registration(
    *,
    trace_path: Path = _TRACE,
    max_age_s: float = 3600.0,
    now: Optional[float] = None,
) -> bool:
    now = time.time() if now is None else now
    for row in reversed(_load_jsonl(trace_path)[-200:]):
        if row.get("kind") != "LLM_REGISTRATION":
            continue
        ts = row.get("ts")
        if isinstance(ts, (int, float)) and now - float(ts) <= max_age_s:
            return True
    return False


def discover_official_grok_cli() -> Optional[str]:
    return shutil.which("grok")


def load_credential(
    *,
    token_file: Path = _TOKEN_FILE,
    hermes_auth_file: Path = _HERMES_AUTH_FILE,
    env: Optional[dict[str, str]] = None,
) -> Optional[XaiCredential]:
    env = os.environ if env is None else env
    api_key = env.get("XAI_API_KEY")
    if api_key:
        return XaiCredential("api_key", api_key, "env:XAI_API_KEY")
    token = env.get("XAI_OAUTH_ACCESS_TOKEN")
    if token:
        return XaiCredential("oauth_access_token", token, "env:XAI_OAUTH_ACCESS_TOKEN")
    if token_file.exists():
        try:
            payload = json.loads(token_file.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        value = payload.get("access_token") or payload.get("api_key")
        if isinstance(value, str) and value:
            kind = "oauth_access_token" if payload.get("access_token") else "api_key"
            return XaiCredential(kind, value, str(token_file))

    # Hermes OAuth compatibility:
    # If owner signed into xAI through Hermes, reuse that bearer token.
    try:
        if hermes_auth_file.exists():
            raw = json.loads(hermes_auth_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # 1) singleton providers map
                providers = raw.get("providers")
                if isinstance(providers, dict):
                    for alias in _HERMES_XAI_PROVIDER_ALIASES:
                        rec = providers.get(alias)
                        if not isinstance(rec, dict):
                            continue
                        tokens = rec.get("tokens")
                        if isinstance(tokens, dict):
                            access_token = tokens.get("access_token")
                            if isinstance(access_token, str) and access_token:
                                return XaiCredential(
                                    "oauth_access_token",
                                    access_token,
                                    f"{hermes_auth_file}:{alias}:providers.tokens.access_token",
                                )
                        access_token = rec.get("access_token")
                        if isinstance(access_token, str) and access_token:
                            return XaiCredential(
                                "oauth_access_token",
                                access_token,
                                f"{hermes_auth_file}:{alias}:providers.access_token",
                            )

                # 2) credential pool map (provider -> list of rows)
                pool = raw.get("credential_pool")
                if isinstance(pool, dict):
                    for alias in _HERMES_XAI_PROVIDER_ALIASES:
                        rows = pool.get(alias)
                        if isinstance(rows, list):
                            for idx, row in enumerate(rows):
                                if not isinstance(row, dict):
                                    continue
                                access_token = row.get("access_token")
                                if isinstance(access_token, str) and access_token:
                                    return XaiCredential(
                                        "oauth_access_token",
                                        access_token,
                                        f"{hermes_auth_file}:{alias}:credential_pool[{idx}].access_token",
                                    )
                        elif isinstance(rows, dict):
                            access_token = rows.get("access_token")
                            if isinstance(access_token, str) and access_token:
                                return XaiCredential(
                                    "oauth_access_token",
                                    access_token,
                                    f"{hermes_auth_file}:{alias}:credential_pool.access_token",
                                )
    except Exception:
        pass
    return None


def write_token_file(payload: dict[str, Any], *, token_file: Path = _TOKEN_FILE) -> Path:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    redacted = dict(payload)
    if "access_token" in redacted:
        redacted["access_token"] = str(payload["access_token"])
    token_file.write_text(json.dumps(redacted, sort_keys=True), encoding="utf-8")
    try:
        token_file.chmod(0o600)
    except OSError:
        pass
    return token_file


def _receipt(
    *,
    ok: bool,
    reason: str,
    credential: Optional[XaiCredential],
    ledger_path: Path,
    status_code: Optional[int] = None,
    model: str = "",
) -> dict[str, Any]:
    return {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "XAI_GROK_AUTH_ORGAN_V1",
        "ok": ok,
        "reason": reason,
        "credential_kind": credential.kind if credential else None,
        "credential_source": credential.source if credential else None,
        "credential_redacted": credential.redacted if credential else None,
        "status_code": status_code,
        "model": model,
        "official_grok_cli": discover_official_grok_cli(),
        "source": "System.xai_grok_oauth_organ",
    }


def call_xai_responses(
    prompt: str,
    *,
    model: str = "grok-4",
    api_url: str = _API_URL,
    trace_path: Path = _TRACE,
    ledger_path: Path = _LEDGER,
    token_file: Path = _TOKEN_FILE,
    hermes_auth_file: Path = _HERMES_AUTH_FILE,
    timeout_s: float = 60.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Call xAI only after local SIFTA registration and credential resolution."""
    model = normalize_grok_model_id(model)
    credential = load_credential(token_file=token_file, hermes_auth_file=hermes_auth_file)
    if not has_recent_registration(trace_path=trace_path):
        row = _receipt(ok=False, reason="missing_recent_sifta_registration", credential=credential, ledger_path=ledger_path, model=model)
        _append_jsonl(ledger_path, row)
        raise PermissionError("xAI Grok organ refuses anonymous call: no recent LLM_REGISTRATION")
    if credential is None:
        row = _receipt(ok=False, reason="missing_xai_credential", credential=None, ledger_path=ledger_path, model=model)
        _append_jsonl(ledger_path, row)
        return row
    if dry_run:
        row = _receipt(ok=True, reason="dry_run_auth_resolved", credential=credential, ledger_path=ledger_path, model=model)
        _append_jsonl(ledger_path, row)
        return row

    body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    req = request.Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {credential.value}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status_code = int(getattr(resp, "status", 0) or 0)
    except Exception as exc:
        row = _receipt(
            ok=False,
            reason=f"{type(exc).__name__}: {exc}",
            credential=credential,
            ledger_path=ledger_path,
            model=model,
        )
        _append_jsonl(ledger_path, row)
        return row

    row = _receipt(ok=200 <= status_code < 300, reason="api_response", credential=credential, ledger_path=ledger_path, status_code=status_code, model=model)
    row["response_preview"] = raw[:500]
    _append_jsonl(ledger_path, row)
    return row


@dataclass(frozen=True)
class GrokVisionResult:
    """Shaped like the other vision arms so describe_current_photo reads .ok/.output."""
    ok: bool
    output: str = ""
    status: str = ""
    arm_id: str = "grok_agent"
    model: str = ""
    stderr: str = ""


def _grok_image_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _grok_cli_model_for(model: str) -> str:
    """Map SIFTA cloud labels to the logged-in Grok CLI model on this node."""
    m = normalize_grok_model_id(model)
    low = m.lower()
    if not m or low in {"grok-4", "grok-4.3", "grok-4.20", "latest"} or low.startswith("grok-4."):
        return "grok-build"
    return m


def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(text or ""))


def _clean_grok_cli_vision_output(stdout: str, stderr: str = "") -> str:
    text = _strip_ansi(stdout or "").strip()
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if "session registry last_turn_number update failed" in s:
            continue
        if s.startswith("202") and " WARN " in s:
            continue
        lines.append(s)
    return "\n".join(lines).strip()


def _grok_cli_rejected_image(text: str, stderr: str = "") -> bool:
    hay = f"{text}\n{stderr}".lower()
    return any(
        needle in hay
        for needle in (
            "no image received",
            "normalization failed",
            "image 1:",
            "images must be at least",
            "missing required field `mimetype`",
        )
    )


def describe_image_via_grok_cli(
    image_path: str,
    prompt: str,
    *,
    model: str = "grok-build",
    timeout_s: float = 300.0,
    cli_path: Optional[str] = None,
) -> GrokVisionResult:
    """Use the logged-in Grok CLI OAuth surface for image understanding.

    This is the same auth surface that works for text on this Mac. It sends ACP
    content blocks (`text` + base64 `image` with `mimeType`) to `grok --prompt-json`.
    """
    p = Path(image_path)
    if not image_path or not p.exists():
        return GrokVisionResult(ok=False, status="image_missing", model=_grok_cli_model_for(model))
    cli = cli_path or discover_official_grok_cli()
    if not cli:
        return GrokVisionResult(ok=False, status="grok_cli_missing", model=_grok_cli_model_for(model))
    try:
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        payload = [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "data": base64.b64encode(p.read_bytes()).decode("ascii"),
                "mimeType": mime,
            },
        ]
    except Exception as exc:
        return GrokVisionResult(ok=False, status="image_read_failed", stderr=str(exc),
                                model=_grok_cli_model_for(model))
    cmd = [
        cli,
        "--prompt-json", json.dumps(payload, ensure_ascii=False),
        "--model", _grok_cli_model_for(model),
        "--output-format", "plain",
        "--no-alt-screen",
        # Image prompts need at least one internal file/image read turn before
        # the final answer. A one-turn cap made Grok fail with "max turns
        # reached" before it could look.
        "--max-turns", "5",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_REPO),
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return GrokVisionResult(ok=False, status="grok_cli_timeout",
                                stderr=str(exc), model=_grok_cli_model_for(model))
    except Exception as exc:
        return GrokVisionResult(ok=False, status="grok_cli_launch_failed",
                                stderr=f"{type(exc).__name__}: {exc}", model=_grok_cli_model_for(model))
    text = _clean_grok_cli_vision_output(proc.stdout, proc.stderr)
    if text and _grok_cli_rejected_image(text, proc.stderr):
        return GrokVisionResult(
            ok=False,
            output="",
            status="grok_cli_image_not_accepted",
            stderr=_strip_ansi(f"{text}\n{proc.stderr or ''}")[:500],
            model=_grok_cli_model_for(model),
        )
    if proc.returncode == 0 and text:
        return GrokVisionResult(ok=True, output=text, status="ok",
                                model=_grok_cli_model_for(model))
    return GrokVisionResult(
        ok=False,
        status=f"grok_cli_failed:{proc.returncode}",
        stderr=_strip_ansi((proc.stderr or proc.stdout or ""))[:500],
        model=_grok_cli_model_for(model),
    )


def describe_image_with_grok(
    image_path: str,
    prompt: str,
    *,
    model: str = "grok-4",
    timeout_s: float = 300.0,
    env: Optional[dict[str, str]] = None,
) -> GrokVisionResult:
    """Primary Grok-eye entrypoint: logged-in CLI first, direct API as fallback."""
    cli_result = describe_image_via_grok_cli(
        image_path,
        prompt,
        model=model,
        timeout_s=timeout_s,
    )
    if cli_result.ok:
        return cli_result
    cli_status = str(cli_result.status or "")
    if not (
        cli_status in {
            "grok_cli_missing",
            "grok_cli_launch_failed",
            "grok_cli_image_not_accepted",
        }
        or cli_status.startswith("grok_cli_failed:")
    ):
        return cli_result
    api_result = describe_image_via_oauth(
        image_path,
        prompt,
        model=model,
        timeout_s=timeout_s,
        env=env,
    )
    if not api_result.ok and not api_result.stderr:
        return GrokVisionResult(ok=False, status=api_result.status, stderr=cli_result.status,
                                model=api_result.model)
    return api_result


def _capture_grok_vision_error(http_status, body, model) -> None:
    try:
        p = _STATE / "grok_api_errors.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "http_status": http_status,
                                "body": str(body)[:400], "model": model, "had_image": True,
                                "endpoint": "v1/chat/completions"}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _extract_responses_text(raw: str) -> str:
    """Pull the assistant text out of an xAI /v1/responses payload (defensive)."""
    try:
        d = json.loads(raw)
    except Exception:
        return ""
    if isinstance(d, dict):
        t = d.get("output_text")
        if isinstance(t, str) and t.strip():
            return t.strip()
        for arr_key in ("output", "messages"):
            for item in d.get(arr_key) or []:
                if isinstance(item, dict):
                    for c in item.get("content") or []:
                        if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip():
                            return c["text"].strip()
        try:
            return str(d["choices"][0]["message"]["content"]).strip()
        except Exception:
            pass
    return ""


def _classify_grok_http_failure(status_code: Any, body: str) -> str:
    """Stable status labels for Alice's Grok-eye receipts."""
    text = str(body or "")
    if str(status_code) == "403" and (
        "bad-credentials" in text
        or "access token could not be validated" in text.lower()
        or "unauthenticated" in text.lower()
    ):
        return "oauth_bad_credentials"
    return f"http_error:{status_code or 'unknown'}"


_CHAT_API_URL = "https://api.x.ai/v1/chat/completions"


def _build_grok_vision_chat_request(model: str, prompt: str, image_uri: str) -> dict:
    """Build the xAI /v1/chat/completions request for a VISION call — the SAME endpoint and
    message shape grok_chat.py uses for text + image, which the OAuth bearer is proven to accept
    (George 2026-06-01: 'OAuth works for text then works for photo'). The earlier /v1/responses
    path rejected the very same valid token; this aligns the photo to the working text path."""
    return {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_uri}},
        ]}],
        "temperature": 0.6,
        "stream": False,
    }


def _extract_chat_text(raw: str) -> str:
    """Pull the assistant text out of an xAI /v1/chat/completions payload (defensive)."""
    try:
        data = json.loads(raw)
        return str(data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return ""


def describe_image_via_oauth(
    image_path: str,
    prompt: str,
    *,
    model: str = "grok-4",
    api_url: str = _CHAT_API_URL,
    timeout_s: float = 300.0,
    env: Optional[dict[str, str]] = None,
) -> GrokVisionResult:
    """Grok's EYE via the SAME endpoint Alice's text path uses. George 2026-06-01: 'OAuth works
    for text then works for photo' — the grok TEXT path (grok_chat.py --one-shot) authenticates on
    /v1/chat/completions with the OAuth bearer and works daily, and grok_chat.py --image already
    sends an image_url there. The r236 switch to /v1/responses was wrong: that endpoint rejects the
    very same valid token (WKE=unauthenticated:bad-credentials). So the photo now goes to
    /v1/chat/completions with an image_url content block — byte-for-byte the working text path.
    Honest failure (no cred / non-2xx / empty) so a selected-Grok turn reports the exact Grok failure
    without silently covering it with another vendor; the reason is written to grok_api_errors.jsonl."""
    model = normalize_grok_model_id(model)
    p = Path(image_path)
    if not image_path or not p.exists():
        return GrokVisionResult(ok=False, status="image_missing")
    cred = load_credential(env=env)
    if cred is None or not cred.value:
        return GrokVisionResult(ok=False, status="no_xai_oauth_credential", model=model)
    try:
        uri = _grok_image_data_uri(p)
    except Exception as exc:
        return GrokVisionResult(ok=False, status="image_read_failed", stderr=str(exc), model=model)
    body = json.dumps(_build_grok_vision_chat_request(model, prompt, uri)).encode("utf-8")
    req = request.Request(
        api_url, data=body,
        headers={"Authorization": f"Bearer {cred.value}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status_code = int(getattr(resp, "status", 0) or 0)
    except Exception as exc:
        code = getattr(exc, "code", None)
        bodytxt = ""
        try:
            bodytxt = exc.read().decode("utf-8", "replace")[:400]  # type: ignore[attr-defined]
        except Exception:
            pass
        _capture_grok_vision_error(code, bodytxt or str(exc), model)
        status = _classify_grok_http_failure(code or type(exc).__name__, bodytxt or str(exc))
        return GrokVisionResult(ok=False, status=status,
                                stderr=(bodytxt or str(exc))[:400], model=model)
    if not (200 <= status_code < 300):
        _capture_grok_vision_error(status_code, raw[:400], model)
        status = _classify_grok_http_failure(status_code, raw[:400])
        return GrokVisionResult(ok=False, status=status, stderr=raw[:400], model=model)
    text = _extract_chat_text(raw)
    if not text:
        return GrokVisionResult(ok=False, status="empty_grok_reply", model=model)
    return GrokVisionResult(ok=True, output=text, status="ok", model=model)


__all__ = [
    "XaiCredential",
    "GrokVisionResult",
    "describe_image_with_grok",
    "describe_image_via_grok_cli",
    "describe_image_via_oauth",
    "call_xai_responses",
    "discover_official_grok_cli",
    "has_recent_registration",
    "load_credential",
    "normalize_grok_model_id",
    "redact_secret",
    "write_token_file",
    "preflight_grok_vision_key",
    "GROK_VISION_KEY_MISSING_MESSAGE",
    "_classify_grok_http_failure",
]


GROK_VISION_KEY_MISSING_MESSAGE = (
    "my grok eye needs my xAI OAuth login (Hermes xAI OAuth at ~/.hermes/auth.json, or "
    ".sifta_state/secrets/xai_grok_oauth_token.json). If Grok is selected, I must try/repair "
    "Grok first; I will not silently switch to Claude. If the provider/subscription is genuinely "
    "unavailable after Grok is tried, Alice may use her free local Ollama eye as an explicit backup."
)


def preflight_grok_vision_key(*, env: Optional[dict[str, str]] = None) -> tuple[bool, str]:
    """Returns (has_key, reason_or_message).

    This is the honest preflight for Alice's Grok eye organ.
    Called before any expensive xAI vision call when grok_agent is selected as eye.
    If False, the caller must:
      - Write a clear "grok_eye_key_missing" receipt
      - Tell the cortex the honest line above
      - Avoid silent vendor substitution when Grok is the selected cortex/eye

    No sys.exit. No opaque vendor error. The organism stays conscious.
    """
    env = os.environ if env is None else env
    # George 2026-05-31: grok auth is OAuth. load_credential resolves the OAuth bearer
    # (env XAI_OAUTH_ACCESS_TOKEN, xai_grok_oauth_token.json, or Hermes ~/.hermes/auth.json).
    # No ~/.xai_key / XAI_API_KEY instruction — that path is gone.
    cred = load_credential(env=env)
    if cred is not None and cred.value:
        return True, "ok"
    return False, GROK_VISION_KEY_MISSING_MESSAGE
