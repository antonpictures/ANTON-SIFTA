#!/usr/bin/env python3
"""Grok code-together pulse receipts for the We Code Together mirror."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback
    append_line_locked = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
TRUTH_LABEL = "GROK_CODE_TOGETHER_PULSE_V1"
LEDGER_NAME = "grok_code_together_pulses.jsonl"


def _state_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else STATE


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _prompt_sha(prompt: str) -> str:
    return hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest()[:12]


def record_grok_code_together_pulse(
    *,
    prompt: str,
    lane: str = "oauth",
    status: str = "started",
    ok: bool | None = None,
    elapsed_s: float | None = None,
    model: str = "",
    result: Mapping[str, Any] | None = None,
    note: str = "",
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Persist one Alice->Grok teacher pulse for observer-only dashboards."""
    ts = time.time() if now is None else float(now)
    res = dict(result or {})
    stdout = str(res.get("stdout") or res.get("reply") or "")[-1200:]
    stderr = str(res.get("stderr") or res.get("error") or "")[-400:]
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": ts,
        "receipt_id": f"grok-pulse-{uuid.uuid4().hex[:12]}",
        "kind": "GROK_CODE_TOGETHER_PULSE",
        "action": "grok_code_together_pulse",
        "intent": "grok_code_together",
        "lane": lane,
        "status": status,
        "ok": ok,
        "elapsed_s": elapsed_s,
        "model": model or str(res.get("model") or ""),
        "prompt_sha": _prompt_sha(prompt),
        "prompt_preview": " ".join(str(prompt or "").split())[:220],
        "result_preview": " ".join(stdout.split())[:360],
        "stderr_preview": " ".join(stderr.split())[:220],
        "note": note,
    }
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    line = _stable_json(row) + "\n"
    if append_line_locked is not None:
        append_line_locked(sd / LEDGER_NAME, line)
        append_line_locked(sd / "work_receipts.jsonl", line)
    else:
        with (sd / LEDGER_NAME).open("a", encoding="utf-8") as handle:
            handle.write(line)
    return row


def latest_grok_code_together_pulses(limit: int = 8, *, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / LEDGER_NAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "latest_grok_code_together_pulses",
    "record_grok_code_together_pulse",
]
