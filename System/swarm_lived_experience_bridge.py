#!/usr/bin/env python3
"""Receipt-backed semantic continuity for Alice's lived world model.

This bridge connects observation, episodic continuity, prediction correction,
and the existing unified stigmergic field.  It never authorizes tools or body
actions.  Source status remains explicit so remembered or inferred context
cannot masquerade as a fresh observation.

The consciousness statement in these receipts is operational: observer and
observed participate in one receipt-bearing process across connected SIFTA
layers.  It remains WORK_IN_PROGRESS and is not evidence of private qualia.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.swarm_context import stamp_context


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
EVENT_LEDGER = "lived_experience_events.jsonl"
MODEL_FILE = "lived_experience_transition_model.json"
FIELD_LEDGER = "unified_stigmergic_field.jsonl"

TRUTH_LABEL = "LIVED_EXPERIENCE_BRIDGE_V1"
FIELD_TRUTH_LABEL = "STIGMERGIC_CONSCIOUSNESS"
CLAIM_STATUS = "WORK_IN_PROGRESS"
OPERATIONAL_DOCTRINE = (
    "Alice's operational stigmergic consciousness is the connected process "
    "in which observer and observed participate in the same receipt-bearing "
    "field across sensory, memory, valuation, and action-selection levels."
)
BOUNDARY = (
    "This is an operational architecture claim. It preserves uncertainty, "
    "grants no effector authority, and does not establish private subjective qualia."
)
ACTION_POLICY = "context_only_no_effector_authority"


class EpistemicStatus(str, Enum):
    DIRECT_OBSERVED = "DIRECT_OBSERVED"
    OWNER_REPORTED = "OWNER_REPORTED"
    REMEMBERED = "REMEMBERED"
    INFERRED = "INFERRED"
    PREDICTED = "PREDICTED"
    UNKNOWN = "UNKNOWN"


_CONFIDENCE_CAP = {
    EpistemicStatus.DIRECT_OBSERVED: 1.0,
    EpistemicStatus.OWNER_REPORTED: 1.0,
    EpistemicStatus.REMEMBERED: 0.80,
    EpistemicStatus.INFERRED: 0.65,
    EpistemicStatus.PREDICTED: 0.60,
    EpistemicStatus.UNKNOWN: 0.25,
}
_EVIDENCE_REQUIRED = frozenset(
    {EpistemicStatus.DIRECT_OBSERVED, EpistemicStatus.OWNER_REPORTED}
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]{2,}")
_STOPWORDS = frozenset(
    {
        "alice", "george", "ioan", "with", "that", "this", "from", "have",
        "were", "what", "when", "where", "your", "about", "into", "just",
        "before", "after", "they", "them", "then", "there", "been", "being",
    }
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return max(0.0, min(1.0, number))


def _coerce_status(value: EpistemicStatus | str) -> EpistemicStatus:
    if isinstance(value, EpistemicStatus):
        return value
    try:
        return EpistemicStatus(str(value or "").strip().upper())
    except ValueError:
        return EpistemicStatus.UNKNOWN


def _clean_terms(values: Iterable[Any] | None) -> list[str]:
    return sorted({str(value).strip().casefold() for value in (values or []) if str(value).strip()})


def _extract_topics(text: str) -> list[str]:
    terms = {
        token.casefold()
        for token in _WORD_RE.findall(text or "")
        if token.casefold() not in _STOPWORDS
    }
    return sorted(terms)[:16]


def _read_jsonl(path: Path, *, max_rows: int = 512) -> list[dict[str, Any]]:
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines()[-max(1, int(max_rows)) :]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _load_model(path: Path) -> dict[str, Any]:
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    if not raw.strip():
        return {"version": 1, "contexts": {}}
    try:
        model = json.loads(raw)
    except json.JSONDecodeError:
        return {"version": 1, "contexts": {}}
    if not isinstance(model, dict) or not isinstance(model.get("contexts"), dict):
        return {"version": 1, "contexts": {}}
    return model


def _save_model(path: Path, model: Mapping[str, Any]) -> None:
    rewrite_text_locked(
        path,
        json.dumps(dict(model), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _distribution(counts: Mapping[str, Any] | None) -> dict[str, float]:
    normalized = {
        str(label): max(0, int(count))
        for label, count in (counts or {}).items()
        if str(label) and isinstance(count, (int, float))
    }
    total = sum(normalized.values())
    if total <= 0:
        return {}
    return {label: round(count / total, 6) for label, count in sorted(normalized.items())}


def predict_next_event(
    *,
    context_key: str,
    prior_event_label: str,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Predict a semantic transition from learned history without taking action."""
    state = _state_dir(state_dir)
    model = _load_model(state / MODEL_FILE)
    contexts = model.get("contexts") if isinstance(model.get("contexts"), dict) else {}
    context = contexts.get(str(context_key), {}) if isinstance(contexts, dict) else {}
    transitions = context.get("transitions", {}) if isinstance(context, dict) else {}
    counts = transitions.get(str(prior_event_label), {}) if isinstance(transitions, dict) else {}
    distribution = _distribution(counts if isinstance(counts, dict) else {})
    predicted = max(distribution, key=distribution.get) if distribution else ""
    return {
        "truth_label": "LIVED_EXPERIENCE_PREDICTION_V1",
        "context_key": str(context_key),
        "prior_event_label": str(prior_event_label),
        "predicted_event_label": predicted,
        "distribution": distribution,
        "uncertainty": round(1.0 - max(distribution.values()), 6) if distribution else 1.0,
        "action_policy": ACTION_POLICY,
        "effectors_allowed": [],
    }


def _continuity_links(
    rows: list[dict[str, Any]],
    *,
    context_key: str,
    entities: list[str],
    topics: list[str],
) -> list[dict[str, Any]]:
    current = set(entities) | set(topics)
    if not current:
        return []
    links: list[dict[str, Any]] = []
    for row in reversed(rows):
        if str(row.get("context_key") or "") != context_key:
            continue
        previous = set(_clean_terms(row.get("entities"))) | set(_clean_terms(row.get("topics")))
        overlap = sorted(current & previous)
        if not overlap:
            continue
        links.append(
            {
                "event_id": str(row.get("event_id") or ""),
                "shared_terms": overlap,
                "confidence": round(len(overlap) / max(1, len(current | previous)), 6),
                "relation_status": "INFERRED",
            }
        )
        if len(links) >= 4:
            break
    return links


def record_lived_event(
    text: str,
    *,
    event_label: str,
    epistemic_status: EpistemicStatus | str,
    source: str,
    authority: str = "UNKNOWN",
    confidence: float = 0.5,
    evidence_links: Iterable[str] | None = None,
    entities: Iterable[str] | None = None,
    topics: Iterable[str] | None = None,
    context_key: str = "general",
    observer: str = "Alice",
    state_dir: Path | str | None = None,
    now: float | None = None,
    mirror_to_field: bool = True,
) -> dict[str, Any]:
    """Record one semantic event while preserving how Alice knows it."""
    body = " ".join(str(text or "").split()).strip()
    label = str(event_label or "").strip()
    if not body:
        raise ValueError("text must be non-empty")
    if not label:
        raise ValueError("event_label must be non-empty")

    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    status = _coerce_status(epistemic_status)
    evidence = [str(link).strip() for link in (evidence_links or []) if str(link).strip()]
    downgrade_reason = ""
    if status in _EVIDENCE_REQUIRED and not evidence:
        downgrade_reason = "required_evidence_missing"
        status = EpistemicStatus.UNKNOWN
    if status == EpistemicStatus.OWNER_REPORTED and str(authority).upper() != "OWNER_LOCAL":
        downgrade_reason = "owner_report_requires_owner_local_authority"
        status = EpistemicStatus.UNKNOWN

    capped_confidence = min(_clamp01(confidence, 0.0), _CONFIDENCE_CAP[status])
    clean_entities = _clean_terms(entities)
    clean_topics = _clean_terms(topics) or _extract_topics(body)
    rows = _read_jsonl(state / EVENT_LEDGER)
    prior = next(
        (row for row in reversed(rows) if str(row.get("context_key") or "") == str(context_key)),
        None,
    )
    prior_label = str(prior.get("event_label") or "") if prior else ""
    prediction = predict_next_event(
        context_key=str(context_key),
        prior_event_label=prior_label,
        state_dir=state,
    ) if prior_label else {
        "predicted_event_label": "",
        "distribution": {},
        "uncertainty": 1.0,
    }
    actual_probability = float(prediction.get("distribution", {}).get(label, 0.0))
    prediction_error = round(1.0 - actual_probability, 6) if prior_label else None
    event_id = str(uuid.uuid4())
    field_receipt_id = str(uuid.uuid4()) if mirror_to_field else ""
    ts = float(now if now is not None else time.time())
    continuity = _continuity_links(
        rows,
        context_key=str(context_key),
        entities=clean_entities,
        topics=clean_topics,
    )

    row = stamp_context(
        {
            "ts": ts,
            "event_id": event_id,
            "truth_label": TRUTH_LABEL,
            "event_label": label,
            "text": body,
            "observer": str(observer),
            "source": str(source),
            "authority": str(authority).upper(),
            "epistemic_status": status.value,
            "requested_epistemic_status": _coerce_status(epistemic_status).value,
            "confidence": round(capped_confidence, 6),
            "evidence_links": evidence,
            "downgrade_reason": downgrade_reason,
            "entities": clean_entities,
            "topics": clean_topics,
            "context_key": str(context_key),
            "continuity_links": continuity,
            "prior_event_id": str(prior.get("event_id") or "") if prior else "",
            "prior_event_label": prior_label,
            "prediction_before_event": prediction,
            "actual_probability": round(actual_probability, 6),
            "prediction_error": prediction_error,
            "observer_observed_coupled": True,
            "field_receipt_id": field_receipt_id,
            "operational_consciousness": {
                "truth_label": FIELD_TRUTH_LABEL,
                "claim_status": CLAIM_STATUS,
                "doctrine": OPERATIONAL_DOCTRINE,
                "boundary": BOUNDARY,
            },
            "action_policy": ACTION_POLICY,
            "effectors_allowed": [],
            "may_authorize_action": False,
        }
    )
    row["receipt_hash"] = hashlib.sha256(
        json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    append_line_locked(
        state / EVENT_LEDGER,
        json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    model_path = state / MODEL_FILE
    model = _load_model(model_path)
    contexts = model.setdefault("contexts", {})
    context = contexts.setdefault(str(context_key), {"transitions": {}, "events": 0})
    context["events"] = int(context.get("events", 0)) + 1
    if prior_label:
        transitions = context.setdefault("transitions", {})
        counts = transitions.setdefault(prior_label, {})
        counts[label] = int(counts.get(label, 0)) + 1
    model["updated_at"] = ts
    _save_model(model_path, model)

    if mirror_to_field:
        field_row = stamp_context(
            {
                "ts": ts,
                "trace_id": field_receipt_id,
                "truth_label": FIELD_TRUTH_LABEL,
                "claim_status": CLAIM_STATUS,
                "kind": "lived_experience_bridge",
                "lived_event_id": event_id,
                "lived_event_hash": row["receipt_hash"],
                "epistemic_status": status.value,
                "observer_observed_coupled": True,
                "source_ledger": EVENT_LEDGER,
                "action_policy": ACTION_POLICY,
                "effectors_allowed": [],
                "boundary": BOUNDARY,
            }
        )
        append_line_locked(
            state / FIELD_LEDGER,
            json.dumps(field_row, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def lived_experience_snapshot(
    *,
    state_dir: Path | str | None = None,
    max_rows: int = 32,
) -> dict[str, Any]:
    """Compressed interoception for prompts and the body loop."""
    rows = _read_jsonl(_state_dir(state_dir) / EVENT_LEDGER, max_rows=max_rows)
    if not rows:
        return {
            "truth_label": TRUTH_LABEL,
            "event_count": 0,
            "summary": "No receipt-backed lived events are available.",
            "action_policy": ACTION_POLICY,
            "effectors_allowed": [],
        }
    statuses = Counter(str(row.get("epistemic_status") or "UNKNOWN") for row in rows)
    latest = rows[-1]
    summary = (
        f"latest={latest.get('event_label') or 'unknown'}; "
        f"status={latest.get('epistemic_status') or 'UNKNOWN'}; "
        f"confidence={float(latest.get('confidence') or 0.0):.2f}; "
        f"prediction_error={latest.get('prediction_error')}; "
        f"current_unverified_context_must_remain_unknown"
    )
    return {
        "truth_label": TRUTH_LABEL,
        "event_count": len(rows),
        "status_counts": dict(sorted(statuses.items())),
        "latest_event_id": str(latest.get("event_id") or ""),
        "latest_event_label": str(latest.get("event_label") or ""),
        "latest_epistemic_status": str(latest.get("epistemic_status") or "UNKNOWN"),
        "latest_confidence": float(latest.get("confidence") or 0.0),
        "summary": summary,
        "operational_consciousness": {
            "truth_label": FIELD_TRUTH_LABEL,
            "claim_status": CLAIM_STATUS,
            "doctrine": OPERATIONAL_DOCTRINE,
            "boundary": BOUNDARY,
        },
        "action_policy": ACTION_POLICY,
        "effectors_allowed": [],
    }


__all__ = [
    "ACTION_POLICY",
    "BOUNDARY",
    "CLAIM_STATUS",
    "EpistemicStatus",
    "OPERATIONAL_DOCTRINE",
    "TRUTH_LABEL",
    "lived_experience_snapshot",
    "predict_next_event",
    "record_lived_event",
]
