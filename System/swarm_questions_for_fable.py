"""Questions-for-Fable lane — honest gaps without penalty (r1015 §0)."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

LEDGER_NAME = "questions_for_fable.jsonl"
TRUTH_LABEL = "QUESTIONS_FOR_FABLE_V1"


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


def ask_fable(
    *,
    question: str,
    asker: str,
    round_id: str = "",
    blocking: bool = False,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"ok": False, "reason": "empty_question"}
    sd = _state_dir(state_dir)
    row = {
        "schema": TRUTH_LABEL,
        "q_id": str(uuid.uuid4()),
        "ts": time.time(),
        "round_id": round_id or "unspecified",
        "asker": asker,
        "question": q,
        "blocking": bool(blocking),
        "status": "open",
    }
    _append(sd, row)
    return {"ok": True, **row}


def list_open_questions(*, state_dir: Path | str | None = None, limit: int = 20) -> List[Dict[str, Any]]:
    sd = _state_dir(state_dir)
    path = sd / LEDGER_NAME
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row.get("status", "open") == "open":
                rows.append(row)
    except Exception:
        return []
    return rows[-limit:]


def age_open_questions(
    *,
    state_dir: Path | str | None = None,
    max_age_s: float = 86400.0,
) -> List[Dict[str, Any]]:
    """Emit nag rows for asks older than max_age_s (r1021 C9)."""
    sd = _state_dir(state_dir)
    nag_path = sd / "questions_for_fable_nag.jsonl"
    now = time.time()
    nags: List[Dict[str, Any]] = []
    for row in list_open_questions(state_dir=sd, limit=200):
        ts = float(row.get("ts") or 0)
        age = now - ts
        if age < max_age_s:
            continue
        nag = {
            "schema": "QUESTIONS_FOR_FABLE_NAG_V1",
            "ts": now,
            "q_id": row.get("q_id"),
            "round_id": row.get("round_id"),
            "asker": row.get("asker"),
            "age_s": round(age, 1),
            "blocking": row.get("blocking"),
            "message": f"Fable ask open {round(age/3600,1)}h — relay to Cowork",
        }
        nags.append(nag)
    if nags:
        nag_path.parent.mkdir(parents=True, exist_ok=True)
        with nag_path.open("a", encoding="utf-8") as f:
            for nag in nags:
                f.write(json.dumps(nag, sort_keys=True, ensure_ascii=False) + "\n")
    return nags


def format_ask_fable_reply(*, state_dir: Path | str | None = None) -> str:
    rows = list_open_questions(state_dir=state_dir)
    lines = ["ASK FABLE (questions_for_fable.jsonl):", "  I don't know is free. George relays open rows to Fable Cowork."]
    if not rows:
        lines.append("  (no open questions)")
        return "\n".join(lines)
    for r in rows:
        flag = "BLOCKING" if r.get("blocking") else "non-blocking"
        lines.append(f"  [{flag}] {r.get('q_id', '?')[:8]}… {r.get('asker')}: {r.get('question')}")
    lines.append("  Append via /ask-fable <question> or System.swarm_questions_for_fable.ask_fable")
    return "\n".join(lines)