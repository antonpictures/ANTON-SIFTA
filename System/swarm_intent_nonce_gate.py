"""Intent-nonce effector gate — no double-spend of owner ingress (r1014/r1015)."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

LEDGER_NAME = "intent_nonce_gate.jsonl"
TRUTH_LABEL = "INTENT_NONCE_GATE_V1"
DEFAULT_MIN_STT_CONF = 0.72
DEFAULT_MAX_AGE_S = 300.0


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(sd: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    path = sd / LEDGER_NAME
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def mint_intent_nonce(
    *,
    owner_text: str,
    surface: str = "talk",
    stt_conf: float | None = None,
    ingress_kind: str = "typed",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    text = (owner_text or "").strip()
    ts_bucket = int(time.time() // 30)
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    nonce = hashlib.sha256(f"{surface}|{ts_bucket}|{text_hash}|{uuid.uuid4().hex}".encode()).hexdigest()[:32]
    sd = _state_dir(state_dir)
    row = {
        "schema": TRUTH_LABEL,
        "action": "mint",
        "nonce": nonce,
        "ts": time.time(),
        "surface": surface,
        "ingress_kind": ingress_kind,
        "stt_conf": stt_conf,
        "text_hash": text_hash,
        "spent": False,
        "stale": False,
    }
    _append(sd, row)
    return row


def validate_effector_spend(
    nonce: str,
    *,
    min_stt_conf: float = DEFAULT_MIN_STT_CONF,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    state_dir: Path | str | None = None,
    effector: str = "unknown",
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    path = sd / LEDGER_NAME
    if not path.exists() or not (nonce or "").strip():
        return {"ok": False, "reason": "missing_nonce_or_ledger"}
    target = None
    spent = False
    try:
        for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict) or row.get("nonce") != nonce:
                continue
            if row.get("action") == "spend":
                spent = True
            if row.get("action") == "mint" and target is None:
                target = row
    except Exception as exc:
        return {"ok": False, "reason": f"read_error:{exc}"}
    if not target:
        return {"ok": False, "reason": "nonce_not_found"}
    if spent or target.get("spent"):
        return {"ok": False, "reason": "double_spend_blocked"}
    age = time.time() - float(target.get("ts") or 0)
    if age > max_age_s:
        return {"ok": False, "reason": "nonce_expired", "age_s": age}
    conf = target.get("stt_conf")
    if conf is not None and float(conf) < min_stt_conf:
        return {"ok": False, "reason": "stt_conf_too_low", "stt_conf": conf}
    spend_row = {
        "schema": TRUTH_LABEL,
        "action": "spend",
        "nonce": nonce,
        "ts": time.time(),
        "effector": effector,
        "ok": True,
    }
    _append(sd, spend_row)
    target["spent"] = True
    _append(sd, {**target, "action": "mint_spent_mark"})
    return {"ok": True, "nonce": nonce, "effector": effector, "age_s": age}


def queue_item_requires_fresh_ingress(
    *,
    source: str,
    stt_conf: float | None = None,
    min_stt_conf: float = DEFAULT_MIN_STT_CONF,
) -> bool:
    """Recovery/stale queue rows must not drive effectors without fresh owner ingress."""
    if "recovery" in (source or "").lower() or "timeout" in (source or "").lower():
        return True
    if stt_conf is not None and float(stt_conf) < min_stt_conf:
        return True
    return False