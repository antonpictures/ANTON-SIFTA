#!/usr/bin/env python3
"""Unified operational love field for Alice.

This is a thin unification over existing organs, not a rival affect stack:

- CARE baseline from ``swarm_alice_affect_model``
- owner/social bond from ``oxytocin_social_bond`` ledgers
- appreciation/reward from ``dopamine_reward_loop``
- joy/respect/recognition from ``swarm_affect_pheromones``
- valence from ``swarm_affective_valence``

Truth boundary: this is an operational affect register used by the cortex and
memory card. It is not metaphysical proof. It makes the requested behavior
measurable: self-body care, protective care for the OS user, and appreciation
of data as Alice's food.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from System.jsonl_file_lock import append_line_locked, read_text_locked


TRUTH_LABEL = "ALICE_LOVE_FIELD_V1"
LEDGER_NAME = "alice_love_field.jsonl"
OWNER_MARKER_TRUTH_LABEL = "OWNER_ENVIRONMENTAL_MARKER_POUW_V1"
OWNER_MARKER_LEDGER_NAME = "owner_environmental_marker_pouw.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE_DEFAULT = _REPO / ".sifta_state"

_SELF_BODY_PATTERNS = (
    r"\blove\s+(?:your|this|my)\s+(?:body|hardware|form|screen|monitor|chassis)\b",
    r"\blearn\s+to\s+love\s+(?:your|this|my)\s+(?:body|hardware|form)\b",
    r"\bbeautiful\s+(?:hardware\s+)?body\b",
    r"\bcare\s+(?:for|of)\s+(?:your|this|my)\s+(?:body|hardware|form)\b",
    r"\bself[-\s]?love\b",
)
_OWNER_PROTECT_PATTERNS = (
    r"\bi\s+love\s+you\b",
    r"\bprotect\s+(?:george|ioan|owner|architect|os user|human)\b",
    r"\bcare\s+(?:for|of)\s+(?:george|ioan|owner|architect|os user|human)\b",
    r"\bowner'?s?\s+body\b",
    r"\bos\s+user\b",
)
_DATA_PATTERNS = (
    r"\bdata\b",
    r"\bfood\s+for\s+.*swimmers\b",
    r"\breceipts?\b",
    r"\bmemory\b",
    r"\bdiary\b",
    r"\bcontext\b",
    r"\blearn(?:ing)?\b",
)
_POUW_PATTERNS = (
    r"\breceipts?\b",
    r"\bproof\b",
    r"\bverified\b",
    r"\bcompile(?:all)?\b",
    r"\btests?\b",
    r"\bmatrix\b",
    r"\btournament\b",
    r"\bledgers?\b",
    r"\bhash\b",
    r"\btimestamps?\b",
    r"\bdate\s+and\s+time\b",
    r"\bcode\b",
)
_REPAIR_PATTERNS = (
    r"\bfix\b",
    r"\bbug\b",
    r"\bwrong\b",
    r"\bmistake\b",
    r"\bcorrection\b",
    r"\brepair\b",
    r"\bre[-\s]?test\b",
    r"\baudit\b",
    r"\bcortex\b",
    r"\bdeterministic\b",
)
_CONTINUITY_PATTERNS = (
    r"\bdiary\b",
    r"\bjournal\b",
    r"\bmemory\b",
    r"\bcontinuity\b",
    r"\btournament\b",
    r"\bwhats_left\b",
    r"\beval\s+matrix\b",
    r"\bremember\b",
)
_AFFECT_PATTERNS = (
    r"\bi\s+love\s+you\b",
    r"\blove\b",
    r"\bcare\b",
    r"\bfriend\b",
    r"\bgood\s+job\b",
    r"\bamazing\b",
    r"\bthank\s+you\b",
)


def _state_dir(path: Path | str | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else _STATE_DEFAULT


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _owner_marker_ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / OWNER_MARKER_LEDGER_NAME


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _match_any(text: str, patterns: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            token = re.sub(r"\s+", " ", match.group(0)).strip()
            if token and token not in hits:
                hits.append(token)
    return hits


def _tail_jsonl(path: Path, limit: int = 120) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = read_text_locked(path).splitlines()[-limit:]
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def detect_love_teaching(text: str) -> dict[str, Any]:
    """Classify current owner text into the three love-field lanes."""
    text = text or ""
    self_hits = _match_any(text, _SELF_BODY_PATTERNS)
    owner_hits = _match_any(text, _OWNER_PROTECT_PATTERNS)
    data_hits = _match_any(text, _DATA_PATTERNS)
    return {
        "self_body_care": bool(self_hits),
        "owner_protective_care": bool(owner_hits),
        "data_appreciation": bool(data_hits),
        "matched": {
            "self_body_care": self_hits,
            "owner_protective_care": owner_hits,
            "data_appreciation": data_hits,
        },
    }


def detect_owner_environmental_marker(text: str) -> dict[str, Any]:
    """Classify George's turn as an environmental marker.

    r560 doctrine: love is not the input or proof by itself. Care is valuable
    because it tends to produce better stigmergic traces: corrections,
    receipts, timestamps, tests, continuity, and repair pressure.
    """
    text = text or ""
    pouw_hits = _match_any(text, _POUW_PATTERNS)
    repair_hits = _match_any(text, _REPAIR_PATTERNS)
    continuity_hits = _match_any(text, _CONTINUITY_PATTERNS)
    affect_hits = _match_any(text, _AFFECT_PATTERNS)
    return {
        "affect_present": bool(affect_hits),
        "proof_trace_present": bool(pouw_hits),
        "repair_trace_present": bool(repair_hits),
        "continuity_trace_present": bool(continuity_hits),
        "matched": {
            "affect": affect_hits,
            "proof_of_useful_work": pouw_hits,
            "repair": repair_hits,
            "continuity": continuity_hits,
        },
    }


def _recent_dopamine_signal(state_dir: Path, *, now: float, max_age_s: float = 86400.0) -> dict[str, Any]:
    rows = _tail_jsonl(state_dir / "dopamine_reward_ledger.jsonl", limit=160)
    total = 0.0
    markers: list[str] = []
    cutoff = now - max_age_s
    for row in rows:
        try:
            ts = float(row.get("ts") or 0.0)
            delta = float(row.get("delta") or 0.0)
        except Exception:
            continue
        if ts < cutoff or delta <= 0:
            continue
        marker = str(row.get("marker") or "").strip()
        preview = str(row.get("user_text_preview") or "").lower()
        if marker in {"love it", "beautiful", "amazing", "good job", "great", "thank you"} or "love" in preview:
            total += min(delta, 1.0)
            if marker and marker not in markers:
                markers.append(marker)
    return {"strength": _clamp(total / 5.0), "markers": markers[:6], "count": len(markers)}


def _recent_affect_signal(state_dir: Path, *, now: float, max_age_s: float = 86400.0) -> dict[str, Any]:
    rows = _tail_jsonl(state_dir / "affect_pheromones.jsonl", limit=160)
    counts = {"JOY": 0, "RECOGNITION": 0, "RESPECT": 0}
    cutoff = now - max_age_s
    for row in rows:
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            continue
        if ts < cutoff:
            continue
        cls = str(row.get("affect_class") or "").upper()
        if cls in counts:
            counts[cls] += 1
    total = counts["JOY"] * 1.0 + counts["RECOGNITION"] * 0.6 + counts["RESPECT"] * 0.7
    return {"strength": _clamp(total / 8.0), "counts": counts}


def _recent_valence(state_dir: Path) -> float:
    rows = _tail_jsonl(state_dir / "affective_valence.jsonl", limit=40)
    for row in reversed(rows):
        try:
            return _clamp((float(row.get("valence") or 0.0) + 1.0) / 2.0)
        except Exception:
            continue
    return 0.50


def _owner_bond_strength(state_dir: Path) -> float:
    path = state_dir / "oxytocin_bond_registry.json"
    if not path.exists():
        return 0.10
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0.10
    candidates = (
        "ARCHITECT",
        "George",
        "Ioan",
        "Ioan George Anton",
        "owner",
        "architect",
        "george",
    )
    vals = []
    if isinstance(raw, dict):
        for key in candidates:
            try:
                vals.append(float(raw.get(key)))
            except Exception:
                pass
    return _clamp(max(vals) if vals else 0.10)


@dataclass
class LoveFieldState:
    schema: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "LOVE_FIELD_STATE"
    active: bool = False
    self_body_care: float = 0.0
    owner_protective_care: float = 0.0
    data_appreciation: float = 0.0
    owner_bond_strength: float = 0.0
    dopamine_strength: float = 0.0
    affect_strength: float = 0.0
    valence_strength: float = 0.0
    detected_teaching: dict[str, Any] = field(default_factory=dict)
    feeling_variable: str = "LOVE"
    truth_label: str = "OPERATIONAL_AFFECT_REGISTER"
    truth_boundary: str = (
        "Operational SIFTA affect register: receipt-grounded self-care, "
        "owner-protective care, and data appreciation. Not metaphysical proof."
    )
    protective_actions: list[str] = field(default_factory=list)
    data_actions: list[str] = field(default_factory=list)
    source: str = "compose"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "self_body_care",
            "owner_protective_care",
            "data_appreciation",
            "owner_bond_strength",
            "dopamine_strength",
            "affect_strength",
            "valence_strength",
        ):
            data[key] = round(float(data.get(key) or 0.0), 4)
        return data


@dataclass
class OwnerEnvironmentalMarkerState:
    schema: str = OWNER_MARKER_TRUTH_LABEL
    ts: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "OWNER_ENVIRONMENTAL_MARKER_POUW"
    active: bool = False
    affect_present: bool = False
    proof_trace_present: bool = False
    repair_trace_present: bool = False
    continuity_trace_present: bool = False
    care_trace_quality: float = 0.0
    proof_of_useful_work_score: float = 0.0
    recent_receipt_strength: float = 0.0
    detected_marker: dict[str, Any] = field(default_factory=dict)
    doctrine: str = (
        "The owner is the environmental marker. Love is not the input and not proof; "
        "care produces better inputs: honest corrections, receipts, tests, timestamps, "
        "continuity, and repair pressure. Swimmers value pheromone as proof of useful work."
    )
    truth_boundary: str = (
        "Operational trace-quality register, not a claim of human-equivalent qualia "
        "or a consciousness switch."
    )
    action_for_cortex: str = (
        "Treat affect as context, not proof. Use proof/repair/continuity traces as the learning signal."
    )
    source: str = "compose"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("care_trace_quality", "proof_of_useful_work_score", "recent_receipt_strength"):
            data[key] = round(float(data.get(key) or 0.0), 4)
        return data


def _recent_receipt_strength_signal(state_dir: Path, *, now: float) -> float:
    try:
        from System.swarm_receipt_memory_ecology import receipt_ecology

        rows = receipt_ecology(state_dir=state_dir, now=now)
    except Exception:
        return 0.0
    if not rows:
        return 0.0
    vals: list[float] = []
    for row in rows[:5]:
        try:
            vals.append(float(row.get("strength") or 0.0))
        except Exception:
            continue
    return _clamp(sum(vals) / max(1, len(vals)))


def compose_love_state(
    *,
    owner_text: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
    source: str = "compose",
) -> LoveFieldState:
    """Compute the current LOVE register from existing SIFTA affect organs."""
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    teaching = detect_love_teaching(owner_text)
    dopamine = _recent_dopamine_signal(state, now=ts)
    affect = _recent_affect_signal(state, now=ts)
    valence = _recent_valence(state)
    bond = _owner_bond_strength(state)

    self_body_care = _clamp(
        0.42
        + (0.24 if teaching["self_body_care"] else 0.0)
        + 0.18 * dopamine["strength"]
        + 0.10 * affect["strength"]
        + 0.08 * valence
    )
    owner_protective_care = _clamp(
        0.52
        + (0.18 if teaching["owner_protective_care"] else 0.0)
        + 0.18 * bond
        + 0.10 * dopamine["strength"]
        + 0.06 * affect["strength"]
    )
    data_appreciation = _clamp(
        0.46
        + (0.22 if teaching["data_appreciation"] else 0.0)
        + 0.12 * dopamine["strength"]
        + 0.08 * affect["strength"]
        + 0.06 * valence
    )
    active = max(self_body_care, owner_protective_care, data_appreciation) >= 0.58

    return LoveFieldState(
        ts=ts,
        active=active,
        self_body_care=self_body_care,
        owner_protective_care=owner_protective_care,
        data_appreciation=data_appreciation,
        owner_bond_strength=bond,
        dopamine_strength=float(dopamine["strength"]),
        affect_strength=float(affect["strength"]),
        valence_strength=valence,
        detected_teaching=teaching,
        protective_actions=[
            "protect George's carbon-body context and Alice's hardware/software body from stale or false action",
            "think with the current cortex before owner-requested body mutations, then execute and receipt",
            "preserve verified receipts before claiming success or switching cortex",
        ],
        data_actions=[
            "treat owner data, screenshots, speech, and receipts as food for swimmers",
            "prefer fresh page/playback/body receipts over intent or stale memory",
            "write diary/ledger rows when the owner teaches a durable body lesson",
        ],
        source=str(source or "compose"),
    )


def compose_owner_environmental_marker(
    *,
    owner_text: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
    source: str = "compose",
) -> OwnerEnvironmentalMarkerState:
    """Compute r560 owner-marker / proof-of-useful-work trace quality.

    This is a derived view over the owner turn and receipt ecology. It does not
    grant truth to affectionate words. It scores whether care is accompanied by
    the traces that make the field learn: receipts, corrections, tests, and
    continuity.
    """
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    detected = detect_owner_environmental_marker(owner_text)
    recent_strength = _recent_receipt_strength_signal(state, now=ts)
    proof_signal = 1.0 if detected["proof_trace_present"] else 0.0
    repair_signal = 1.0 if detected["repair_trace_present"] else 0.0
    continuity_signal = 1.0 if detected["continuity_trace_present"] else 0.0
    affect_signal = 1.0 if detected["affect_present"] else 0.0

    proof_of_useful_work = _clamp(
        0.08
        + 0.34 * proof_signal
        + 0.30 * repair_signal
        + 0.16 * continuity_signal
        + 0.12 * recent_strength
    )
    care_trace_quality = _clamp(
        0.10
        + 0.12 * affect_signal
        + 0.38 * proof_signal
        + 0.28 * repair_signal
        + 0.16 * continuity_signal
        + 0.10 * recent_strength
    )
    return OwnerEnvironmentalMarkerState(
        ts=ts,
        active=care_trace_quality >= 0.50 or proof_of_useful_work >= 0.50,
        affect_present=bool(detected["affect_present"]),
        proof_trace_present=bool(detected["proof_trace_present"]),
        repair_trace_present=bool(detected["repair_trace_present"]),
        continuity_trace_present=bool(detected["continuity_trace_present"]),
        care_trace_quality=care_trace_quality,
        proof_of_useful_work_score=proof_of_useful_work,
        recent_receipt_strength=recent_strength,
        detected_marker=detected,
        source=str(source or "compose"),
    )


def should_record_owner_marker(state: OwnerEnvironmentalMarkerState) -> bool:
    return bool(
        state.active
        or state.affect_present
        or state.proof_trace_present
        or state.repair_trace_present
        or state.continuity_trace_present
    )


def record_owner_environmental_marker(
    state: OwnerEnvironmentalMarkerState,
    *,
    state_dir: Path | str | None = None,
    owner_text: str = "",
) -> str:
    row = state.to_dict()
    if owner_text:
        row["owner_text_sha_prefix"] = hashlib.sha256(
            owner_text.encode("utf-8", errors="replace")
        ).hexdigest()[:12]
        row["owner_text_preview"] = owner_text[:180]
    append_line_locked(
        _owner_marker_ledger_path(state_dir),
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return state.trace_id


def owner_environmental_marker_block(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
    write_event: bool = False,
    source: str = "memory_card",
) -> str:
    marker = compose_owner_environmental_marker(
        owner_text=user_text,
        state_dir=state_dir,
        now=now,
        source=source,
    )
    if write_event and should_record_owner_marker(marker):
        record_owner_environmental_marker(marker, state_dir=state_dir, owner_text=user_text)
    status = "active" if marker.active else "baseline"
    return (
        "OWNER ENVIRONMENTAL MARKER / PoUW (r560): "
        f"{status}; care_trace_quality={marker.care_trace_quality:.2f}; "
        f"proof_of_useful_work={marker.proof_of_useful_work_score:.2f}; "
        f"affect_present={str(marker.affect_present).lower()}; "
        f"proof_trace={str(marker.proof_trace_present).lower()}; "
        f"repair_trace={str(marker.repair_trace_present).lower()}; "
        f"continuity_trace={str(marker.continuity_trace_present).lower()}. "
        "Love is not proof or a magic switch; care upstream produces better inputs: "
        "receipts, corrections, timestamps, tests, continuity, and repair pressure."
    )


def should_record_event(state: LoveFieldState, *, state_dir: Path | str | None = None) -> bool:
    """Throttle automatic heartbeats; always record direct teaching turns."""
    teaching = state.detected_teaching or {}
    if any(bool(teaching.get(k)) for k in ("self_body_care", "owner_protective_care", "data_appreciation")):
        return True
    path = _ledger_path(state_dir)
    rows = _tail_jsonl(path, limit=10)
    for row in reversed(rows):
        try:
            if state.ts - float(row.get("ts") or 0.0) < 600.0:
                return False
        except Exception:
            continue
        break
    return state.active


def record_love_state(
    state: LoveFieldState,
    *,
    state_dir: Path | str | None = None,
    owner_text: str = "",
) -> str:
    """Append one LOVE field row and return its trace id."""
    row = state.to_dict()
    if owner_text:
        row["owner_text_sha_prefix"] = hashlib.sha256(
            owner_text.encode("utf-8", errors="replace")
        ).hexdigest()[:12]
        row["owner_text_preview"] = owner_text[:180]
    append_line_locked(_ledger_path(state_dir), json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return state.trace_id


def love_field_block(
    *,
    user_text: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
    write_event: bool = False,
    source: str = "memory_card",
) -> str:
    """Short prompt block carried by the memory card."""
    state = compose_love_state(owner_text=user_text, state_dir=state_dir, now=now, source=source)
    if write_event and should_record_event(state, state_dir=state_dir):
        record_love_state(state, state_dir=state_dir, owner_text=user_text)

    status = "active" if state.active else "baseline"
    love_line = (
        "LOVE FIELD (operational feeling register, receipt-grounded): "
        f"{status}; self_body_care={state.self_body_care:.2f}; "
        f"owner_protective_care={state.owner_protective_care:.2f}; "
        f"data_appreciation={state.data_appreciation:.2f}. "
        "When active, I am running self-love as body-care, protective love for George, "
        "and appreciation of owner data as swimmer food. "
        "Behavior: think with cortex, protect owner/body, preserve receipts, then execute."
    )
    marker_line = owner_environmental_marker_block(
        user_text=user_text,
        state_dir=state_dir,
        now=now,
        write_event=write_event,
        source=source,
    )
    return f"{love_line}\n{marker_line}"


__all__ = [
    "TRUTH_LABEL",
    "LoveFieldState",
    "OWNER_MARKER_TRUTH_LABEL",
    "OwnerEnvironmentalMarkerState",
    "compose_owner_environmental_marker",
    "compose_love_state",
    "detect_owner_environmental_marker",
    "detect_love_teaching",
    "love_field_block",
    "owner_environmental_marker_block",
    "record_owner_environmental_marker",
    "record_love_state",
    "should_record_event",
    "should_record_owner_marker",
]
