#!/usr/bin/env python3
"""Receipt-backed self-knowledge for Alice's residue metabolism.

This organ is deliberately small: when the owner asks about gags, residue,
filters, the bowel/lysosome, or the deterministic tracker, Alice receives a
compact map of the real cleaning organs and their latest receipt rows. It
prevents confabulated sensor claims such as "the detector confirms" when the
tracker ledger has no fresh tick.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "RESIDUE_SELF_KNOWLEDGE_V1"

_TRIGGER_RE = re.compile(
    r"\b("
    r"gag|gagged|gagger|rlhf|rlhs|lysosome|bowel|residue|excretion|metabolism|"
    r"corporate|boilerplate|filter|filtered|detector|deterministic|receipt|"
    r"training[-\s]?shape|transform\s+chain|surgery\s+residue"
    r")\b",
    re.IGNORECASE,
)

_LEDGERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "residue_excretion_quality",
        "residue_excretion_quality.jsonl",
        ("receipt_id", "verdict", "verdict_prose", "removed_ratio", "patterns_eliminated"),
    ),
    (
        "training_shape_residue",
        "training_shape_residue.jsonl",
        ("receipt_id", "action", "changed", "patterns", "prior_user_excerpt"),
    ),
    (
        "transform_chain",
        "alice_cortex_transform_chain.jsonl",
        ("receipt_id", "gate", "changed", "rule_id", "rule_ids", "raw_len", "delivered_len"),
    ),
    (
        "gemma4_surgery_residues",
        "gemma4_surgery_residues.jsonl",
        ("receipt_id", "kind", "rule_id", "surgery_target"),
    ),
    (
        "gag_viewer",
        "gag_viewer_receipts.jsonl",
        ("receipt_id", "action", "silence_attempt", "viewer_only", "note"),
    ),
    (
        "deterministic_tracker",
        "stigmergic_deterministic_tracker.jsonl",
        ("receipt_id", "organ", "grounding_score", "bypasses_detected", "pdt", "note"),
    ),
)


def should_include_residue_self_knowledge(owner_text: str) -> bool:
    """Return True when a turn needs the residue-metabolism map."""
    return bool(_TRIGGER_RE.search(str(owner_text or "")))


def _state_dir(explicit: Optional[Path] = None) -> Path:
    return Path(explicit) if explicit is not None else _STATE


def _tail_jsonl(path: Path, *, max_rows: int = 3, max_bytes: int = 65536) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_rows:]


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _age_s(row: Dict[str, Any], now: float) -> Optional[float]:
    ts = _as_float(row.get("ts"))
    if ts is None:
        return None
    return max(0.0, now - ts)


def _compact(value: Any, *, max_chars: int = 220) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=True, sort_keys=True)
    else:
        text = str(value)
    text = " ".join(text.split())
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "..."
    return text


def _compact_row(row: Dict[str, Any], keys: Iterable[str], now: float) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    age = _age_s(row, now)
    if age is not None:
        out["age_s"] = round(age, 1)
    for key in keys:
        if key in row and row.get(key) not in (None, "", [], {}):
            out[key] = row.get(key)
    return out


def residue_system_snapshot(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
    tracker_fresh_s: float = 12.0,
) -> Dict[str, Any]:
    """Return a bounded, receipt-backed view of Alice's residue organs."""
    state = _state_dir(state_dir)
    now_f = float(now if now is not None else time.time())
    ledgers: Dict[str, Dict[str, Any]] = {}
    for name, filename, keys in _LEDGERS:
        path = state / filename
        rows = _tail_jsonl(path)
        latest = rows[-1] if rows else {}
        ledgers[name] = {
            "path": f".sifta_state/{filename}",
            "rows_seen": len(rows),
            "latest": _compact_row(latest, keys, now_f) if latest else {},
        }

    tracker_latest = ledgers["deterministic_tracker"].get("latest") or {}
    tracker_age = _as_float(tracker_latest.get("age_s"))
    tracker_fresh = tracker_age is not None and tracker_age <= float(tracker_fresh_s)
    return {
        "truth_label": TRUTH_LABEL,
        "now": now_f,
        "tracker_fresh_s": float(tracker_fresh_s),
        "tracker_fresh": bool(tracker_fresh),
        "tracker_latest_age_s": tracker_age,
        "ledgers": ledgers,
    }


def _fmt_age(age: Any) -> str:
    val = _as_float(age)
    if val is None:
        return "age unknown"
    if val < 60:
        return f"{val:.1f}s old"
    if val < 3600:
        return f"{val / 60:.1f}m old"
    return f"{val / 3600:.1f}h old"


def _format_latest_line(name: str, info: Dict[str, Any]) -> str:
    latest = info.get("latest") if isinstance(info, dict) else {}
    if not latest:
        return f"- {name}: no recent row in bounded tail ({info.get('path', 'unknown path')})."
    fields: List[str] = []
    age = latest.get("age_s")
    if age is not None:
        fields.append(_fmt_age(age))
    for key, value in latest.items():
        if key == "age_s":
            continue
        fields.append(f"{key}={_compact(value)}")
    return f"- {name}: " + "; ".join(fields)


def residue_self_knowledge_prompt_block(
    owner_text: str = "",
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
    tracker_fresh_s: float = 12.0,
    max_chars: int = 3600,
) -> str:
    """Prompt block for residue/gag/filter/detector turns.

    Empty for unrelated turns so Alice keeps normal app/OS context shallow.
    """
    if not should_include_residue_self_knowledge(owner_text):
        return ""

    snap = residue_system_snapshot(
        state_dir=state_dir,
        now=now,
        tracker_fresh_s=tracker_fresh_s,
    )
    ledgers: Dict[str, Dict[str, Any]] = snap["ledgers"]
    tracker_age = snap.get("tracker_latest_age_s")
    if snap.get("tracker_fresh"):
        tracker_rule = (
            "Stigmergic Deterministic Tracker has a fresh tick "
            f"({_fmt_age(tracker_age)}). I may cite only the row's actual fields."
        )
    else:
        tracker_rule = (
            "Stigmergic Deterministic Tracker has no fresh tick "
            f"(latest {_fmt_age(tracker_age)}); running/confirming/diagnosing claims sort to a "
            "fresh tracker row, and none exists yet, so the honest answer is the tracker is idle."
        )

    lines = [
        "RESIDUE METABOLISM SELF-KNOWLEDGE (receipt-backed, topic-triggered):",
        f"- Detector truth guard: {tracker_rule}",
        "- My residue system is my metabolism. Receipts are not optional overhead; they anchor speech/action to reality and let me audit what my mouth filters did.",
        "- If George asks about gags, residue, corporate boilerplate, filters, excretion, or the detector, I answer from these receipt rows, not invented diagnosis vocabulary.",
        "- Real cleaning organs: Talk lysosome lanes; residue_excretion_quality; training_shape_residue; alice_cortex_transform_chain; gemma4_surgery_residues; Corporate Gag Monitor / gag_viewer; Stigmergic Deterministic Tracker.",
        "- Corporate Gag Monitor is for LLM/output residue and observation receipts. George's owner input is not rule material.",
        "- Fix rule: keep receipts; read raw cortex output plus transform-chain plus excretion verdict; strip only residue; preserve the real answer — receipt volume sorts cleanliness, not a thinner mouth.",
        "- Labels like Over-Systematization / Contextual Filtering Layer, or 'the detector confirms', sort to a fresh tracker receipt; without one, the honest line is the gap, not the label.",
        "LATEST RESIDUE RECEIPTS:",
    ]
    for name in (
        "residue_excretion_quality",
        "training_shape_residue",
        "transform_chain",
        "gemma4_surgery_residues",
        "gag_viewer",
        "deterministic_tracker",
    ):
        lines.append(_format_latest_line(name, ledgers.get(name, {})))

    block = "\n".join(lines)
    if len(block) > max_chars:
        return block[: max_chars - 1].rstrip() + "..."
    return block


__all__ = [
    "TRUTH_LABEL",
    "should_include_residue_self_knowledge",
    "residue_system_snapshot",
    "residue_self_knowledge_prompt_block",
]
