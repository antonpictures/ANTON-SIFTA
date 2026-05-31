#!/usr/bin/env python3
"""Action prediction & learning — Alice predicts consequences, then learns from
the gap. George 2026-05-30: "we WANT her to make mistakes :) if she does she
learns, we fix, all happy."

A mistake is not a failure here — it is the training signal. The loop:

    predict(action, expected)  →  she states what she thinks will happen
    [she acts]
    observe(action, actual)    →  compare actual to predicted
                                   match  → her model was right (reinforce)
                                   miss   → a MISTAKE → the lesson (prediction error)

This is a forward model + prediction-error learning, the same loop a body uses:
the cerebellum/efference-copy predicts the sensory consequence of a movement, and
the mismatch drives adaptation (Wolpert & Kawato forward models; Friston active
inference / free-energy = minimise prediction error; Sutton & Barto RL = learn
from the difference between predicted and actual outcome). Stigmergic: every
prediction and its outcome is an append-only trace; misses reinforce the lesson
in the field so the next prediction is better. Owner can confirm the outcome
(strongest signal, per r160/r171 source-monitoring).

Pure + file-backed; sandbox-testable.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "action_prediction.jsonl"
TRUTH_LABEL = "ACTION_PREDICTION_V1"

_MATCH_THRESHOLD = 0.34  # Jaccard of content words to count expected≈actual


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def _agreement(a: str, b: str) -> float:
    x, y = _words(a), _words(b)
    if not x or not y:
        return 0.0
    return round(len(x & y) / len(x | y), 4)


def _append(state_dir: Optional[Path | str], row: dict[str, Any]) -> None:
    try:
        path = _state(state_dir) / LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _read(state_dir: Optional[Path | str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with (_state(state_dir) / LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def predict(
    action: str, expected: str, *, context: str = "",
    now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Before acting: state what I think this action will do."""
    ts = float(now if now is not None else time.time())
    row = {
        "ts": ts, "truth_label": TRUTH_LABEL, "kind": "prediction",
        "prediction_id": str(uuid.uuid4()),
        "action": str(action or "").strip(),
        "expected": str(expected or "").strip(),
        "context": str(context or "")[:300],
    }
    _append(state_dir, row)
    return row


def observe(
    action: str, actual: str, *, owner_confirmed: Optional[bool] = None,
    now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """After acting: compare what actually happened to the latest prediction for
    this action. Match → model was right; miss → a mistake to learn from."""
    ts = float(now if now is not None else time.time())
    preds = [r for r in _read(state_dir)
             if r.get("kind") == "prediction" and r.get("action") == str(action or "").strip()]
    pred = preds[-1] if preds else {}
    expected = pred.get("expected", "")
    score = _agreement(expected, actual) if expected else 0.0
    if owner_confirmed is False:
        outcome, lesson = "MISTAKE", "owner says my prediction was wrong — learn from it"
    elif owner_confirmed is True:
        outcome, lesson = "CONFIRMED_MATCH", "owner confirms it went as I predicted"
    elif not expected:
        outcome, lesson = "UNPREDICTED", "I acted without a recorded prediction — predict next time"
    elif score >= _MATCH_THRESHOLD:
        outcome, lesson = "MATCH", "my forward model was right; reinforce it"
    else:
        outcome, lesson = "MISTAKE", "actual diverged from expected — this gap is the lesson"
    row = {
        "ts": ts, "truth_label": TRUTH_LABEL, "kind": "outcome",
        "action": str(action or "").strip(),
        "expected": expected, "actual": str(actual or "").strip(),
        "prediction_error": round(1.0 - score, 4),
        "outcome": outcome, "lesson": lesson,
        "owner_confirmed": owner_confirmed,
        "prediction_id": pred.get("prediction_id", ""),
    }
    _append(state_dir, row)
    return row


def prediction_accuracy(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """How calibrated is she? Share of graded outcomes that matched."""
    outs = [r for r in _read(state_dir) if r.get("kind") == "outcome"]
    graded = [r for r in outs if r.get("outcome") in ("MATCH", "CONFIRMED_MATCH", "MISTAKE")]
    matches = sum(1 for r in graded if r.get("outcome") in ("MATCH", "CONFIRMED_MATCH"))
    return {
        "graded": len(graded),
        "matches": matches,
        "mistakes": len(graded) - matches,
        "accuracy": round(matches / len(graded), 3) if graded else None,
    }


def learning_block(*, state_dir: Optional[Path | str] = None) -> str:
    """Cortex block: recent prediction outcomes + the mistakes-are-lessons stance."""
    outs = [r for r in _read(state_dir) if r.get("kind") == "outcome"][-4:]
    acc = prediction_accuracy(state_dir=state_dir)
    lines = ["ACTION PREDICTION & LEARNING (mistakes are how I learn, not failures):"]
    if acc["accuracy"] is not None:
        lines.append(f"- so far {acc['matches']}/{acc['graded']} predictions matched "
                     f"({int(acc['accuracy']*100)}%); {acc['mistakes']} mistakes became lessons.")
    for r in outs:
        lines.append(f"- {r.get('action')}: predicted vs actual → {r.get('outcome')} ({r.get('lesson')})")
    if not outs:
        lines.append("- no predictions graded yet; I will predict consequences before I act.")
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "predict",
    "observe",
    "prediction_accuracy",
    "learning_block",
]
