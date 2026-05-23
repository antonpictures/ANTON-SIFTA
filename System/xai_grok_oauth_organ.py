#!/usr/bin/env python3
"""SIFTA xAI Grok authenticated-client organ.

This module does not mint credentials. It consumes node-local credentials only:
`XAI_API_KEY`, `XAI_OAUTH_ACCESS_TOKEN`, or a chmod-600 token file under
`.sifta_state/secrets/`. Every attempted call writes a redacted local receipt.
"""

from __future__ import annotations

import json
import os
import shutil
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
_API_URL = "https://api.x.ai/v1/responses"


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
    model: str = "grok-4.3",
    api_url: str = _API_URL,
    trace_path: Path = _TRACE,
    ledger_path: Path = _LEDGER,
    token_file: Path = _TOKEN_FILE,
    timeout_s: float = 60.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Call xAI only after local SIFTA registration and credential resolution."""
    credential = load_credential(token_file=token_file)
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


__all__ = [
    "XaiCredential",
    "call_xai_responses",
    "discover_official_grok_cli",
    "has_recent_registration",
    "load_credential",
    "redact_secret",
    "write_token_file",
]
