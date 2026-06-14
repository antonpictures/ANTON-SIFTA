"""Speech-lane salience selector — learn what deserves voice (r1015 §B1).

Print lane keeps full text; mouth speaks human sentences only.
Weights update from owner reactions — not hardcoded taste.
"""
from __future__ import annotations

import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

LEDGER_NAME = "speech_lane.jsonl"
WEIGHTS_NAME = "speech_lane_weights.json"
TRUTH_LABEL = "SPEECH_LANE_SELECTOR_V1"

_MACHINE_RE = re.compile(
    r"\b(?:receipt|uuid|hash|ledger|jsonl|\.sifta_state|/Users/|0x[0-9a-f]{6,}|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"CORTEX_|STGM_|OPERATIONAL|OBSERVED|FORBIDDEN)\b",
    re.IGNORECASE,
)
_PERSON_RE = re.compile(r"\b(?:I|you|George|we|your|my)\b", re.IGNORECASE)

_DEFAULT_WEIGHTS = {"w_novelty": 0.35, "w_person": 0.30, "w_brevity": 0.25, "w_machine_penalty": 0.45}
_DEFAULT_BUDGET_S = 12.0
_CHARS_PER_SEC = 14.0


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _load_weights(sd: Path) -> Dict[str, float]:
    path = sd / WEIGHTS_NAME
    if not path.exists():
        return dict(_DEFAULT_WEIGHTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        out = dict(_DEFAULT_WEIGHTS)
        if isinstance(data, dict):
            for k in _DEFAULT_WEIGHTS:
                if k in data:
                    out[k] = float(data[k])
        return out
    except Exception:
        return dict(_DEFAULT_WEIGHTS)


def _save_weights(sd: Path, weights: Dict[str, float]) -> None:
    (sd / WEIGHTS_NAME).write_text(json.dumps(weights, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_ledger(sd: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    path = sd / LEDGER_NAME
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def _recent_spoken_text(sd: Path, limit: int = 30) -> str:
    path = sd / LEDGER_NAME
    if not path.exists():
        return ""
    chunks: List[str] = []
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        for line in reversed(lines[-limit:]):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                chunks.extend(row.get("sentences_spoken") or [])
    except Exception:
        pass
    return " ".join(chunks).lower()


def _split_sentences(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", raw)
    return [p.strip() for p in parts if p.strip()]


def _score_sentence(s: str, *, weights: Dict[str, float], recent: str) -> Tuple[float, Dict[str, float]]:
    low = s.lower()
    machine_hits = len(_MACHINE_RE.findall(s))
    person_hits = len(_PERSON_RE.findall(s))
    words = max(1, len(s.split()))
    brevity = 1.0 / math.sqrt(words)
    novelty = 1.0
    if recent and low[:40] in recent:
        novelty = 0.2
    elif recent:
        overlap = sum(1 for w in low.split()[:8] if w in recent)
        novelty = max(0.15, 1.0 - overlap * 0.12)
    machine_penalty = min(1.0, machine_hits * 0.35)
    score = (
        weights["w_novelty"] * novelty
        + weights["w_person"] * min(1.0, person_hits * 0.2)
        + weights["w_brevity"] * brevity
        - weights["w_machine_penalty"] * machine_penalty
    )
    return score, {
        "novelty": novelty,
        "person": person_hits,
        "brevity": brevity,
        "machine_penalty": machine_penalty,
        "machine_hits": machine_hits,
    }


def _estimate_seconds(text: str) -> float:
    return max(0.5, len(text) / _CHARS_PER_SEC)


def get_speech_budget_s(*, state_dir: Path | str | None = None) -> float:
    sd = _state_dir(state_dir)
    path = sd / WEIGHTS_NAME
    if not path.exists():
        return _DEFAULT_BUDGET_S
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data.get("budget_s", _DEFAULT_BUDGET_S))
    except Exception:
        return _DEFAULT_BUDGET_S


def set_speech_budget_s(seconds: float, *, state_dir: Path | str | None = None) -> float:
    sd = _state_dir(state_dir)
    w = _load_weights(sd)
    budget = max(3.0, min(60.0, float(seconds)))
    data = {**w, "budget_s": budget}
    _save_weights(sd, data)
    return budget


def select_spoken_sentences(
    text: str,
    *,
    owner_text: str = "",
    turn_id: str = "",
    state_dir: Path | str | None = None,
    source: str = "talk_tts",
    budget_s: float | None = None,
) -> Dict[str, Any]:
    """Knapsack pick of human sentences under spoken-time budget."""
    sd = _state_dir(state_dir)
    weights = _load_weights(sd)
    budget = budget_s if budget_s is not None else get_speech_budget_s(state_dir=sd)
    recent = _recent_spoken_text(sd)
    sentences = _split_sentences(text)
    if not sentences:
        return {"ok": False, "spoken_text": "", "sentences_spoken": [], "sentences_suppressed": []}

    scored: List[Tuple[float, str, Dict[str, float]]] = []
    for s in sentences:
        sc, feats = _score_sentence(s, weights=weights, recent=recent)
        if feats.get("machine_hits", 0) >= 1 and feats.get("person", 0) == 0:
            continue
        if feats.get("machine_hits", 0) >= 2 and sc < 0.15:
            continue
        scored.append((sc, s, feats))
    scored.sort(key=lambda x: x[0], reverse=True)

    chosen: List[str] = []
    suppressed = [s for _, s, _ in scored if s not in chosen]
    used = 0.0
    for sc, s, feats in scored:
        if sc <= 0:
            suppressed.append(s)
            continue
        dur = _estimate_seconds(s)
        if used + dur > budget and chosen:
            suppressed.append(s)
            continue
        chosen.append(s)
        used += dur

    if not chosen:
        best = max(scored, key=lambda x: x[0], default=None)
        if best and best[0] > -0.5:
            chosen = [best[1]]
        else:
            human = [s for s in sentences if _MACHINE_RE.search(s) is None]
            chosen = human[:1] if human else sentences[:1]

    spoken_text = " ".join(chosen).strip()
    all_s = [s for _, s, _ in scored] or sentences
    suppressed = [s for s in all_s if s not in chosen]

    row = {
        "schema": TRUTH_LABEL,
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "turn_id": turn_id or "",
        "source": source,
        "sentences_spoken": chosen,
        "sentences_suppressed": suppressed,
        "weights": weights,
        "budget_s": budget,
        "owner_reaction": None,
    }
    _append_ledger(sd, row)
    return {
        "ok": True,
        "spoken_text": spoken_text,
        "sentences_spoken": chosen,
        "sentences_suppressed": suppressed,
        "weights": weights,
        "receipt_id": row["receipt_id"],
    }


def record_owner_reaction(
    reaction: str,
    *,
    turn_id: str = "",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Update weights from interruption / repeat / completion."""
    sd = _state_dir(state_dir)
    weights = _load_weights(sd)
    r = (reaction or "").strip().lower()
    delta = 0.0
    if r in {"interrupt", "interrupted", "stop"}:
        weights["w_machine_penalty"] = min(0.9, weights["w_machine_penalty"] + 0.03)
        weights["w_brevity"] = max(0.1, weights["w_brevity"] - 0.02)
        delta = -0.03
    elif r in {"what", "repeat", "huh", "again"}:
        weights["w_brevity"] = max(0.1, weights["w_brevity"] - 0.04)
        delta = -0.04
    elif r in {"ok", "good", "complete", "completion"}:
        weights["w_person"] = min(0.6, weights["w_person"] + 0.01)
        delta = 0.01
    _save_weights(sd, weights)
    row = {
        "schema": TRUTH_LABEL,
        "kind": "weight_update",
        "ts": time.time(),
        "turn_id": turn_id,
        "owner_reaction": reaction,
        "weights": weights,
        "delta_hint": delta,
    }
    _append_ledger(sd, row)
    return {"ok": True, "weights": weights, "delta_hint": delta}


def format_speech_reply(*, state_dir: Path | str | None = None) -> str:
    sd = _state_dir(state_dir)
    w = _load_weights(sd)
    budget = get_speech_budget_s(state_dir=sd)
    lines = [
        "SPEECH LANE:",
        f"  budget: {budget:.1f}s spoken-time",
        f"  weights: novelty={w['w_novelty']:.3f} person={w['w_person']:.3f} "
        f"brevity={w['w_brevity']:.3f} machine_penalty={w['w_machine_penalty']:.3f}",
    ]
    path = sd / LEDGER_NAME
    if path.exists():
        try:
            lines_raw = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            for line in reversed(lines_raw[-8:]):
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("kind") == "weight_update":
                    lines.append(f"  reaction: {row.get('owner_reaction')} → weights updated")
                    continue
                spoken = row.get("sentences_spoken") or []
                supp = row.get("sentences_suppressed") or []
                if spoken:
                    lines.append(f"  spoke: {spoken[0][:120]}{'…' if len(str(spoken[0])) > 120 else ''}")
                if supp:
                    lines.append(f"  suppressed: {len(supp)} sentence(s)")
        except Exception:
            pass
    lines.append("  /speech budget <seconds> — change spoken-time budget")
    return "\n".join(lines)