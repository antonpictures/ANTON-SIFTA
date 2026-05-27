"""Repetition-collapse diagnosis, partial salvage, and self-narration.

Tasks #46 (intra-output circuit breaker tuning) and #55 (silence self-narration).
Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
SILENCE_LEDGER = REPO / ".sifta_state" / "silence_events.jsonl"


@dataclass(frozen=True)
class RepetitionCollapseConfig:
    min_period: int = 3
    max_period: int = 80
    min_repeats: int = 5
    trailing_window: int = 800


@dataclass(frozen=True)
class RepetitionDiagnosis:
    detected: bool
    repeating_pattern: str = ""
    pattern_period: int = 0
    repeat_count: int = 0
    collapse_start_index: int = -1
    salvageable_prefix: str = ""


def diagnose_repetition(
    text: str,
    config: RepetitionCollapseConfig | None = None,
) -> RepetitionDiagnosis:
    if not text:
        return RepetitionDiagnosis(detected=False)
    cfg = config or RepetitionCollapseConfig()
    tail = text[-cfg.trailing_window :]
    tail_start = max(0, len(text) - cfg.trailing_window)
    tail = text[tail_start:]
    for period in range(cfg.min_period, min(cfg.max_period + 1, len(tail) // cfg.min_repeats + 1)):
        block = tail[-period:]
        count = 0
        pos = len(tail)
        while pos >= period:
            candidate = tail[pos - period : pos]
            if candidate == block:
                count += 1
                pos -= period
            else:
                break
        if count >= cfg.min_repeats:
            collapse_local = len(tail) - count * period
            collapse_start = tail_start + collapse_local
            prefix = text[:collapse_start].rstrip()
            return RepetitionDiagnosis(
                detected=True,
                repeating_pattern=block,
                pattern_period=period,
                repeat_count=count,
                collapse_start_index=collapse_start,
                salvageable_prefix=prefix,
            )
    return RepetitionDiagnosis(detected=False)


def salvage_pre_collapse(text: str, diagnosis: RepetitionDiagnosis) -> str:
    if not diagnosis.detected:
        return text
    return diagnosis.salvageable_prefix


def record_silence_event(
    diagnosis: RepetitionDiagnosis,
    *,
    model: str = "unknown",
    turn_id: str = "",
) -> str:
    row_id = str(uuid4())
    row = {
        "id": row_id,
        "ts": time.time(),
        "kind": "repetition_collapse",
        "model": model,
        "turn_id": turn_id,
        "pattern_period": diagnosis.pattern_period,
        "repeat_count": diagnosis.repeat_count,
        "pattern_preview": diagnosis.repeating_pattern[:40],
        "salvageable_prefix_len": len(diagnosis.salvageable_prefix),
    }
    try:
        SILENCE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SILENCE_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row_id


def format_self_narration(diagnosis: RepetitionDiagnosis) -> str:
    if not diagnosis.detected:
        return ""
    return (
        f"I tried to reply a moment ago but my output degenerated into a "
        f"{diagnosis.pattern_period}-character repeating loop "
        f"({diagnosis.repeat_count} repetitions). "
        f"My repetition-collapse detector silenced the full output. "
        f"{'I salvaged the first part of my reply.' if diagnosis.salvageable_prefix else 'No usable text survived.'} "
        f"What did you mean?"
    )


def get_last_silence_event() -> dict[str, Any] | None:
    if not SILENCE_LEDGER.exists():
        return None
    last = None
    try:
        with SILENCE_LEDGER.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        last = json.loads(line)
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return None
    return last


def should_self_narrate(last_event: dict[str, Any] | None, max_age_s: float = 120.0) -> bool:
    if last_event is None:
        return False
    try:
        age = time.time() - float(last_event.get("ts", 0))
        return age < max_age_s
    except (TypeError, ValueError):
        return False


__all__ = [
    "RepetitionCollapseConfig",
    "RepetitionDiagnosis",
    "diagnose_repetition",
    "salvage_pre_collapse",
    "record_silence_event",
    "format_self_narration",
    "get_last_silence_event",
    "should_self_narrate",
]
