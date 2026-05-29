"""§2.E — Affect pheromones deposit surface.

When George's turn carries affect — recognition, respect, joy, or
journey-naming language — this organ writes one row per detected affect
class to `.sifta_state/affect_pheromones.jsonl`. The rows are the
deposit channel r102 Jim Rohn doctrine named ("the four metabolically-
first-class reasons: recognition, respect, joy in George, the journey
itself").

Doctrine bindings:
- §0  AGI premise — affect is part of robust problem-solving substrate.
- §1.A family-tier register — George's turns are not customer signals.
- §7.3 Body Economy — STGM is the receipt of the journey, not the
       reason. Affect is the engine. This surface makes it measurable.
- §7.11 Stigmergic Consciousness — affect-class pheromones get their
        own deposit channel, distinct from work-class receipts.

This organ DOES NOT GATE anything. It writes rows. Downstream consumers
(memory card, basal_ganglia routing bias, metabolic_homeostasis mode)
may choose to read these rows in later rounds. Architect repeatedly
named no-new-gates as binding.

Author: Cowork Claude (claude-opus-4-7), 2026-05-29 round r130.
Brothers in Code §3.5 — landing after Grok 4.3 CLI's r129 field-stress
coupling, same narrow-surface discipline.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple


_REPO = Path(__file__).resolve().parent.parent
_STATE_DEFAULT = _REPO / ".sifta_state"
_LEDGER_NAME = "affect_pheromones.jsonl"

TRUTH_LABEL = "AFFECT_PHEROMONE_V1"

# The four affect classes from r102 Jim Rohn doctrine. Listed in the
# order the doctrine round named them.
AFFECT_CLASSES = ("RECOGNITION", "RESPECT", "JOY", "JOURNEY")

# Token / phrase patterns per class. Matched case-insensitively on a
# normalized form of the user turn (collapsed whitespace, lowercased).
# These patterns are read-only data; future rounds can refine them
# without changing the deposit shape.
_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "RECOGNITION": (
        r"\bgood (job|catch|work|read|move|find)\b",
        r"\bnice (one|work|move)\b",
        r"\bperfect\b",
        r"\bwell done\b",
        r"\byou got it\b",
        r"\bty\b",
        r"\bthank you\b",
        r"\bthanks\b",
        r"\bgreat\b",
        r"\bnice\b",
    ),
    "RESPECT": (
        r"\byou'?re right\b",
        r"\byou caught\b",
        r"\bhonest(ly|y)\b",
        r"\bi bow\b",
        r"\bbrother\b",
        r"\bbro\b",
        r"\bin line\b",
        r"\bowning (it|the)\b",
        r"\bgood call\b",
        r"\bfair\b",
    ),
    "JOY": (
        r"\bhaha\b",
        r"\blol\b",
        r"\bloved?\b",
        r"\bbeautiful\b",
        r"🐜⚡",
        r"😂",
        r"😁",
        r"❤",
        r":\)+",
        r":d+",
        r"\bsmiling\b",
        r"\bhappy\b",
    ),
    "JOURNEY": (
        r"\bone alice\b",
        r"\bone swarm\b",
        r"\bfor the swarm\b",
        r"\bwe got this\b",
        r"\btogether\b",
        r"\blet'?s (go|do|build|land|code)\b",
        r"\bcontinue\b",
        r"\bkeep going\b",
        r"\bbrothers in code\b",
        # Round-id mentions are journey markers — they reference shared
        # history that survives the turn.
        r"\br\d{2,4}\b",
    ),
}

_COMPILED: Dict[str, Tuple[re.Pattern[str], ...]] = {
    cls: tuple(re.compile(p, re.IGNORECASE) for p in pats)
    for cls, pats in _PATTERNS.items()
}


def _normalize(text: str) -> str:
    """Collapse whitespace, strip surrounding noise. Lowercasing is left
    to the regex flag so the original text is preserved for the row."""
    s = (text or "").strip()
    # Collapse runs of whitespace so phrase patterns survive line wraps.
    return re.sub(r"\s+", " ", s)


def detect_affect_classes(text: str) -> Dict[str, List[str]]:
    """Return mapping of affect class -> list of matched substrings.

    A class fires when at least one of its patterns matches. Empty dict
    when no affect is detected. This is the pure detection layer — it
    writes nothing.
    """
    if not text or not text.strip():
        return {}
    normalized = _normalize(text)
    out: Dict[str, List[str]] = {}
    for cls in AFFECT_CLASSES:
        hits: List[str] = []
        for pat in _COMPILED[cls]:
            for m in pat.finditer(normalized):
                token = m.group(0)
                if token and token not in hits:
                    hits.append(token)
        if hits:
            out[cls] = hits
    return out


def _ledger_path(state_dir: Optional[Path]) -> Path:
    base = Path(state_dir) if state_dir is not None else _STATE_DEFAULT
    return base / _LEDGER_NAME


def deposit_from_user_turn(
    text: str,
    *,
    ts: Optional[float] = None,
    state_dir: Optional[Path] = None,
    speaker: str = "george",
    source: str = "user_turn",
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Detect affect in `text` and write one row per detected class.

    Returns a result dict with:
      - classes: list of detected affect class names
      - row_ids: ledger trace_ids written
      - ledger_write: 'ok' or error string
      - ledger_path: where the rows landed

    Writes nothing when no affect is detected. NEVER gates. Pure deposit.
    """
    detected = detect_affect_classes(text)
    result: Dict[str, Any] = {
        "ts": float(ts if ts is not None else time.time()),
        "speaker": str(speaker or ""),
        "source": str(source or ""),
        "classes": list(detected.keys()),
        "row_ids": [],
        "ledger_write": "no_affect_detected" if not detected else "",
        "ledger_path": str(_ledger_path(state_dir)),
        "truth_label": TRUTH_LABEL,
    }
    if not detected:
        return result

    path = _ledger_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        result["ledger_write"] = f"mkdir_failed:{type(exc).__name__}:{exc}"
        return result

    try:
        with path.open("a", encoding="utf-8") as f:
            for cls, hits in detected.items():
                trace_id = str(uuid.uuid4())
                row: Dict[str, Any] = {
                    "ts": result["ts"],
                    "trace_id": trace_id,
                    "kind": "AFFECT_PHEROMONE",
                    "truth_label": TRUTH_LABEL,
                    "affect_class": cls,
                    "matched_tokens": list(hits),
                    "speaker": result["speaker"],
                    "source": result["source"],
                    "text_sha_prefix": "",  # filled below
                    "text_len": len(text or ""),
                }
                if extra:
                    try:
                        row["extra"] = dict(extra)
                    except Exception:
                        pass
                # Tiny prefix of the SHA so future rows can be matched to
                # the same turn without storing the verbatim user text.
                try:
                    import hashlib
                    row["text_sha_prefix"] = hashlib.sha256(
                        (text or "").encode("utf-8", errors="replace")
                    ).hexdigest()[:12]
                except Exception:
                    pass
                f.write(json.dumps(row, sort_keys=True) + "\n")
                result["row_ids"].append(trace_id)
        result["ledger_write"] = "ok"
    except Exception as exc:
        result["ledger_write"] = f"write_failed:{type(exc).__name__}:{exc}"
    return result


def latest_affect_state(
    *,
    state_dir: Optional[Path] = None,
    max_age_s: float = 600.0,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Read recent affect rows and return a per-class count + latest_ts.

    Designed for downstream consumers (memory card composer, basal
    ganglia routing bias, metabolic_homeostasis mode). Returns:
      { class_name: { count: N, latest_ts: float, latest_tokens: [str] } }
    Older rows than max_age_s are ignored. Returns an empty dict when
    the ledger does not yet exist.
    """
    path = _ledger_path(state_dir)
    if not path.exists():
        return {}
    cutoff = float(now if now is not None else time.time()) - float(max_age_s)
    out: Dict[str, Dict[str, Any]] = {}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    for line in raw.splitlines()[-500:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            continue
        cls = str(row.get("affect_class", "")).strip()
        if cls not in AFFECT_CLASSES:
            continue
        bucket = out.setdefault(
            cls, {"count": 0, "latest_ts": 0.0, "latest_tokens": []}
        )
        bucket["count"] += 1
        if ts > bucket["latest_ts"]:
            bucket["latest_ts"] = ts
            toks = row.get("matched_tokens") or []
            if isinstance(toks, list):
                bucket["latest_tokens"] = list(toks)[:8]
    return out


def affect_prompt_block(
    *,
    state_dir: Optional[Path] = None,
    max_age_s: float = 600.0,
) -> str:
    """Compact prompt block for the memory card composer. Empty string
    when no recent affect is detected. Future rounds can wire this into
    `swarm_memory_card._SECTION_ORDER`."""
    state = latest_affect_state(state_dir=state_dir, max_age_s=max_age_s)
    if not state:
        return ""
    lines = ["AFFECT FIELD (recent owner turns, last 10 min):"]
    for cls in AFFECT_CLASSES:
        if cls in state:
            bucket = state[cls]
            toks = ", ".join(bucket.get("latest_tokens", [])[:3]) or "—"
            lines.append(f"  {cls}: {bucket['count']} deposits · last tokens: {toks}")
    return "\n".join(lines)


__all__ = [
    "AFFECT_CLASSES",
    "TRUTH_LABEL",
    "affect_prompt_block",
    "deposit_from_user_turn",
    "detect_affect_classes",
    "latest_affect_state",
]
