"""Quorum outcome n-counter + theta_review_due at n=10 (r1021 C3)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

_LEDGER = "quorum_n_counter.jsonl"
_TRUTH = "QUORUM_N_COUNTER_V1"
_REVIEW_AT = 10


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(sd: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    path = sd / _LEDGER
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def record_quorum_outcome(
    *,
    proposal_id: str,
    applied: bool,
    vote: float,
    theta: float,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    n = 0
    path = sd / _LEDGER
    if path.exists():
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except Exception:
                continue
            if row.get("schema") == _TRUTH and row.get("kind") == "outcome":
                n += 1
    n += 1
    review_due = n >= _REVIEW_AT and (n % _REVIEW_AT == 0)
    row: Dict[str, Any] = {
        "schema": _TRUTH,
        "kind": "outcome",
        "n": n,
        "ts": time.time(),
        "proposal_id": proposal_id,
        "applied": bool(applied),
        "vote": float(vote),
        "theta": float(theta),
    }
    _append(sd, row)
    if review_due:
        review = {
            "schema": _TRUTH,
            "kind": "theta_review_due",
            "n": n,
            "ts": time.time(),
            "message": f"theta/weights review due after {n} quorum outcomes",
            "proposal_id": proposal_id,
        }
        _append(sd, review)
        row["theta_review_due"] = True
        row["review_row"] = review
    return row


def latest_theta_review(*, state_dir: Path | str | None = None) -> Optional[Dict[str, Any]]:
    sd = _state_dir(state_dir)
    path = sd / _LEDGER
    if not path.exists():
        return None
    last = None
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if row.get("kind") == "theta_review_due":
            last = row
    return last