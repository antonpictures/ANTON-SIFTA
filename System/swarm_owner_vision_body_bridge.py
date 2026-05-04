"""
swarm_owner_vision_body_bridge.py — Camera frame → owner_body_events (vision probe)

Bridges one PNG frame (live eye) through local Ollama vision into a single
`body_check` row on `owner_body_events.jsonl`, anchored to the same sha8 the
photon HUD already computes.

Truth labels (IDE_BOOT_COVENANT §7.11):
  OBSERVED: frame bytes, sha8, model id, model text output.
  NOT OBSERVED: clinical diagnosis, cancer, certainty beyond pixels.

The model is instructed not to diagnose; the ledger still carries model opinion
only — Alice must treat extreme claims as unverified unless corroborated.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from System.sifta_inference_defaults import resolve_ollama_model
from System.swarm_owner_body_schema import log_body_event


_DEFAULT_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FRAME_DIR = _STATE / "owner_body_vision_frames"
_PROMPT_VERSION = "OWNER_BODY_VISION_PROBE_V1"

_VISION_SYSTEM = (
    "You caption one camera frame for an owner body maintenance ledger. "
    "Do not diagnose disease, cancer, or infection. "
    "Do not claim certainty beyond what pixels support. "
    "Follow the user's output format exactly."
)

_VISION_USER = """Inspect this single camera frame. The human may be showing their mouth for dental / body maintenance logging.

Reply in EXACTLY these two lines and nothing else:
MOUTH_VISIBILITY: CLEAR | PARTIAL | NOT_VISIBLE
ORAL_NOTES: <one short English clause (max 25 words); visible teeth/gums/lips, OR "mouth not visible", OR "uncertain from pixels">

Do not output a third line."""


def _strip_thinking_tags(text: str) -> str:
    return re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()


def parse_vision_body_reply(text: str) -> Dict[str, Any]:
    """Parse the two-line vision reply into bounded, citable evidence fields."""
    clean = _strip_thinking_tags(text or "")
    visibility = "UNKNOWN"
    notes = "uncertain from pixels"
    for raw_line in clean.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().upper()
        value = " ".join(value.strip().split())
        if key == "MOUTH_VISIBILITY":
            candidate = value.upper().replace(" ", "_")
            if candidate in {"CLEAR", "PARTIAL", "NOT_VISIBLE"}:
                visibility = candidate
        elif key == "ORAL_NOTES" and value:
            notes = value[:180]

    confidence_by_visibility = {
        "CLEAR": 0.85,
        "PARTIAL": 0.55,
        "NOT_VISIBLE": 0.2,
        "UNKNOWN": 0.1,
    }
    return {
        "mouth_visibility": visibility,
        "oral_notes": notes,
        "observation_confidence": confidence_by_visibility[visibility],
        "raw_model_reply": clean[:1000],
    }


def _safe_sha8(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]", "", value or "")[:32]
    return safe or "nohudsha"


def _write_frame_artifact(png_bytes: bytes, sha8: str) -> Tuple[str, str]:
    """Persist the exact local frame Alice inspected and return (path, sha256)."""
    digest = hashlib.sha256(png_bytes).hexdigest()
    _FRAME_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = _FRAME_DIR / f"{stamp}_{_safe_sha8(sha8)}_{digest[:16]}.png"
    path.write_bytes(png_bytes)
    return str(path), digest


def call_ollama_vision_png(
    png_bytes: bytes,
    *,
    model: str,
    base_url: str = _DEFAULT_BASE,
    timeout_s: float = 120.0,
) -> Tuple[str, str]:
    """
    POST one PNG to Ollama /api/chat. Returns (assistant_text, error_string).
    On success error_string is "".
    """
    if not png_bytes:
        return "", "empty_png"
    b64 = base64.b64encode(png_bytes).decode("ascii")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _VISION_SYSTEM},
            {"role": "user", "content": _VISION_USER, "images": [b64]},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 256},
    }
    url = f"{base_url}/api/chat"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return "", f"http_{e.code}:{body[:200]}"
    except Exception as e:
        return "", f"request_failed:{e}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "", "invalid_json"

    msg = data.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, str):
        content = data.get("response")
    if not isinstance(content, str):
        return "", "no_content"
    return _strip_thinking_tags(content), ""


def log_owner_body_from_vision_bytes(
    png_bytes: bytes,
    sha8: str,
    *,
    model: Optional[str] = None,
    base_url: str = _DEFAULT_BASE,
    timeout_s: float = 120.0,
    write_ledger: bool = True,
    save_artifact: bool = True,
) -> Dict[str, Any]:
    """
    Run vision probe and append one `body_check` event. Returns dict with ok, row or error.
    """
    m = model or resolve_ollama_model(app_context="owner_vision_body")
    text, err = call_ollama_vision_png(
        png_bytes, model=m, base_url=base_url, timeout_s=timeout_s
    )
    if err:
        return {"ok": False, "error": err, "model": m}
    parsed = parse_vision_body_reply(text)
    artifact_path = ""
    png_sha256 = hashlib.sha256(png_bytes).hexdigest()
    if write_ledger and save_artifact:
        artifact_path, png_sha256 = _write_frame_artifact(png_bytes, sha8)
    evidence = {
        "kind": "OWNER_BODY_VISUAL_EVIDENCE_V1",
        "prompt_version": _PROMPT_VERSION,
        "frame_sha8": sha8,
        "png_sha256": png_sha256,
        "png_bytes": len(png_bytes),
        "artifact_path": artifact_path,
        "model": m,
        "mouth_visibility": parsed["mouth_visibility"],
        "oral_notes": parsed["oral_notes"],
        "observation_confidence": parsed["observation_confidence"],
        "raw_model_reply": parsed["raw_model_reply"],
        "diagnosis_policy": "local visual observation only; no disease/cancer/infection diagnosis",
    }
    note = (
        f"vision_probe frame_sha8={sha8} png_sha256={png_sha256[:16]} "
        f"model={m} mouth_visibility={parsed['mouth_visibility']} "
        f"confidence={parsed['observation_confidence']:.2f}; "
        f"oral_notes={parsed['oral_notes']}"
    )[:500]
    row = log_body_event(
        "body_check",
        note,
        status="DONE",
        source="stigmergic_vision:ollama",
        evidence=evidence,
        write_ledger=write_ledger,
    )
    if row.get("disabled"):
        return {"ok": False, "error": "SIFTA_OWNER_BODY_DISABLE=1", "model": m}
    return {
        "ok": True,
        "row": row,
        "raw": text,
        "parsed": parsed,
        "evidence": evidence,
        "model": m,
    }


__all__ = [
    "call_ollama_vision_png",
    "log_owner_body_from_vision_bytes",
    "parse_vision_body_reply",
]
