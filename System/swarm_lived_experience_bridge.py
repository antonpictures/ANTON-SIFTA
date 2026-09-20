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
import math
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


# ── D2: queryable belief snapshot over lived observations ─────────────────────
#
# The event ledger above records *what happened*. This section records *what
# Alice currently believes about an object or tool*, and how strongly. Three
# laws make it falsifiable:
#
#   1. A replayed or older observation can never freshen a belief. The row is
#      kept as history but stamped `freshens: False` and excluded from the view.
#   2. Missing pose is null, never (0, 0). An absent pose is recorded as unknown.
#   3. Contradictions stay visible. A moved object or a changed attribute adds a
#      conflict and raises the entity revision; neither side is deleted.

BELIEF_LEDGER = "belief_observations.jsonl"
BELIEF_TRUTH_LABEL = "LIVED_EXPERIENCE_BELIEF_V1"
POSE_UNITS = "m"
DEFAULT_EVIDENCE_TTL_S = 900.0
DEFAULT_MOVED_THRESHOLD_M = 0.25
ENTITY_KINDS = tuple(sorted({"object", "tool", "agent", "place", "resource", "unknown"}))
BELIEF_RECORD_CLASSES = ("DUPLICATE_REPLAY", "FRESH", "STALE_REPLAY")


def _utc(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts)))


def _finite_number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} must be a finite number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite number, got {value!r}") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{field_name} must be finite, got {value!r}")
    return number


def _canonical_pose(
    pose: Mapping[str, Any] | None,
    *,
    frame: str | None,
    uncertainty_m: Any = None,
) -> dict[str, Any] | None:
    """Return a metric pose, or None when the pose is genuinely unknown.

    A caller that passes a pose must pass both coordinates; defaulting a missing
    coordinate to 0.0 would invent an origin that was never observed.
    """
    if pose is None:
        return None
    if not isinstance(pose, Mapping):
        raise ValueError("pose must be a mapping or None")
    for axis in ("x", "y"):
        if pose.get(axis) is None:
            raise ValueError(f"pose.{axis} is missing; an unknown pose must be passed as pose=None")
    clean_frame = str(frame or pose.get("frame") or "").strip()
    if not clean_frame:
        raise ValueError("pose requires a frame name")
    out: dict[str, Any] = {
        "x": round(_finite_number(pose.get("x"), field_name="pose.x"), 6),
        "y": round(_finite_number(pose.get("y"), field_name="pose.y"), 6),
        "frame": clean_frame,
        "units": POSE_UNITS,
    }
    if pose.get("z") is not None:
        out["z"] = round(_finite_number(pose.get("z"), field_name="pose.z"), 6)
    if pose.get("yaw_rad") is not None:
        out["yaw_rad"] = round(_finite_number(pose.get("yaw_rad"), field_name="pose.yaw_rad"), 6)
    if uncertainty_m is not None:
        out["uncertainty_m"] = round(
            max(0.0, _finite_number(uncertainty_m, field_name="pose_uncertainty_m")), 6
        )
    return out


def _pose_distance(a: Mapping[str, Any] | None, b: Mapping[str, Any] | None) -> float | None:
    if not a or not b:
        return None
    if str(a.get("frame")) != str(b.get("frame")):
        return None
    dx = float(a.get("x", 0.0)) - float(b.get("x", 0.0))
    dy = float(a.get("y", 0.0)) - float(b.get("y", 0.0))
    dz = float(a.get("z", 0.0)) - float(b.get("z", 0.0))
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _belief_rows(state: Path, entity_id: str) -> list[dict[str, Any]]:
    rows = _read_jsonl(state / BELIEF_LEDGER, max_rows=4096)
    return [row for row in rows if str(row.get("entity_id") or "") == entity_id]


def _normalise_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, raw in (attributes or {}).items():
        key = str(name).strip()
        if not key:
            continue
        if isinstance(raw, Mapping):
            value = raw.get("value")
            if value is None:
                raise ValueError(f"attribute {key!r} carries no value")
            entry: dict[str, Any] = {"value": value}
            if raw.get("units") is not None:
                entry["units"] = str(raw.get("units"))
            out[key] = entry
        else:
            if raw is None:
                raise ValueError(f"attribute {key!r} carries no value")
            out[key] = {"value": raw}
    return out


def _normalise_relations(relations: Iterable[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in relations or []:
        if not isinstance(raw, Mapping):
            raise ValueError("each relation must be a mapping")
        predicate = str(raw.get("predicate") or "").strip()
        obj = str(raw.get("object") or "").strip()
        if not predicate or not obj:
            raise ValueError("each relation needs a predicate and an object")
        entry = {
            "subject": str(raw.get("subject") or "").strip(),
            "predicate": predicate,
            "object": obj,
        }
        if raw.get("value") is not None:
            entry["value"] = raw.get("value")
        if raw.get("units") is not None:
            entry["units"] = str(raw.get("units"))
        out.append(entry)
    return out


def observe_entity(
    entity_id: str,
    *,
    kind: str = "object",
    source: str,
    label: str = "",
    aliases: Iterable[str] | None = None,
    pose: Mapping[str, Any] | None = None,
    frame: str | None = None,
    pose_uncertainty_m: Any = None,
    attributes: Mapping[str, Any] | None = None,
    relations: Iterable[Any] | None = None,
    confidence: float = 0.5,
    epistemic_status: EpistemicStatus | str = EpistemicStatus.DIRECT_OBSERVED,
    evidence_links: Iterable[str] | None = None,
    observation_id: str | None = None,
    observed_at: float | None = None,
    ttl_s: float = DEFAULT_EVIDENCE_TTL_S,
    context_key: str = "general",
    observer: str = "Alice",
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append one observation of an entity to the belief ledger.

    Always appends — history is never rewritten. The returned row states whether
    this observation may freshen the current belief (`freshens`) or was rejected
    as a stale or duplicate replay, and why.
    """
    ident = str(entity_id or "").strip()
    if not ident:
        raise ValueError("entity_id must be non-empty")
    src = str(source or "").strip()
    if not src:
        raise ValueError("source must be non-empty")
    kind_clean = str(kind or "unknown").strip().lower()
    if kind_clean not in ENTITY_KINDS:
        raise ValueError(f"unknown entity kind {kind_clean!r}; allowed: {', '.join(ENTITY_KINDS)}")

    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    source_ts = float(observed_at if observed_at is not None else ts)
    if source_ts != source_ts:
        raise ValueError("observed_at must be finite")
    ttl = max(0.0, _finite_number(ttl_s, field_name="ttl_s"))

    status = _coerce_status(epistemic_status)
    evidence = [str(link).strip() for link in (evidence_links or []) if str(link).strip()]
    downgrade_reason = ""
    if status in _EVIDENCE_REQUIRED and not evidence:
        downgrade_reason = "required_evidence_missing"
        status = EpistemicStatus.UNKNOWN
    capped = min(_clamp01(confidence, 0.0), _CONFIDENCE_CAP[status])
    clean_pose = _canonical_pose(pose, frame=frame, uncertainty_m=pose_uncertainty_m)
    clean_attrs = _normalise_attributes(attributes)
    clean_relations = _normalise_relations(relations)

    rows = _belief_rows(state, ident)
    oid = str(observation_id or "").strip() or str(uuid.uuid4())
    prior_ids = {str(row.get("observation_id") or "") for row in rows}
    newest = None
    for row in rows:
        if newest is None or float(row.get("observed_at") or 0.0) > float(newest.get("observed_at") or 0.0):
            newest = row

    content = {
        "entity_id": ident,
        "entity_kind": kind_clean,
        "identity_label": str(label or "").strip() or ident,
        "aliases": _clean_terms(aliases),
        "identity_source": src,
        "pose": clean_pose,
        "attributes": clean_attrs,
        "relations": clean_relations,
        "observer": str(observer),
        "source": src,
        "epistemic_status": status.value,
        "confidence": round(capped, 6),
        "evidence_links": evidence,
        "observed_at": round(source_ts, 6),
        "context_key": str(context_key),
    }
    content_hash = hashlib.sha256(
        json.dumps(content, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    # A replay is the same evidence arriving twice, whether or not it carries the
    # same observation id. Identity of the record is checked first, then identity of
    # its content; anything older than the newest evidence is stale, never fresh.
    if oid in prior_ids:
        record_class, freshens, reason = "DUPLICATE_REPLAY", False, "observation_id already recorded"
    elif any(str(row.get("content_hash") or "") == content_hash for row in rows):
        record_class, freshens, reason = "DUPLICATE_REPLAY", False, "an identical observation is already recorded"
    elif newest is not None and source_ts <= float(newest.get("observed_at") or 0.0):
        record_class, freshens, reason = "STALE_REPLAY", False, "source timestamp is not newer than the newest evidence"
    else:
        record_class, freshens, reason = "FRESH", True, ""

    row = stamp_context(
        {
            "ts": ts,
            "content_hash": content_hash,
            "truth_label": BELIEF_TRUTH_LABEL,
            "observation_id": oid,
            "entity_id": ident,
            "entity_kind": kind_clean,
            "identity": {
                "label": str(label or "").strip() or ident,
                "aliases": _clean_terms(aliases),
                "identity_source": src,
            },
            "pose": clean_pose,
            "pose_known": clean_pose is not None,
            "attributes": clean_attrs,
            "relations": clean_relations,
            "observer": str(observer),
            "source": src,
            "epistemic_status": status.value,
            "requested_epistemic_status": _coerce_status(epistemic_status).value,
            "confidence": round(capped, 6),
            "evidence_links": evidence,
            "downgrade_reason": downgrade_reason,
            "observed_at": round(source_ts, 6),
            "observed_at_utc": _utc(source_ts),
            "recorded_at": round(ts, 6),
            "evidence_ttl_s": round(ttl, 6),
            "context_key": str(context_key),
            "record_class": record_class,
            "freshens": freshens,
            "replay_reason": reason,
            "prior_observation_id": str(newest.get("observation_id") or "") if newest else "",
            "action_policy": ACTION_POLICY,
            "effectors_allowed": [],
            "may_authorize_action": False,
        }
    )
    row["receipt_hash"] = hashlib.sha256(
        json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    append_line_locked(
        state / BELIEF_LEDGER,
        json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def entity_belief(
    entity_id: str,
    *,
    now: float | None = None,
    state_dir: Path | str | None = None,
    conflict_uncertainty: float = 0.15,
) -> dict[str, Any]:
    """Current belief about one entity, with evidence age, conflicts and uncertainty."""
    ident = str(entity_id or "").strip()
    if not ident:
        raise ValueError("entity_id must be non-empty")
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    rows = _belief_rows(state, ident)
    empty = {
        "truth_label": BELIEF_TRUTH_LABEL,
        "entity_id": ident,
        "entity_kind": "unknown",
        "known": False,
        "revision": 0,
        "identity": {"label": ident, "aliases": []},
        "pose": None,
        "pose_known": False,
        "attributes": {},
        "relations": [],
        "conflicts": [],
        "contested": False,
        "uncertainty": 1.0,
        "evidence_age_s": None,
        "evidence_ttl_s": DEFAULT_EVIDENCE_TTL_S,
        "stale": True,
        "moved_count": 0,
        "supporting_observation_ids": [],
        "expired_evidence_ids": [],
        "superseded_observation_ids": [],
        "observation_count": 0,
        "action_policy": ACTION_POLICY,
        "effectors_allowed": [],
    }
    if not rows:
        return empty

    fresh = [row for row in rows if bool(row.get("freshens"))]
    rejected = [row for row in rows if not bool(row.get("freshens"))]
    if not fresh:
        empty["observation_count"] = len(rows)
        empty["rejected_observation_ids"] = [str(row.get("observation_id") or "") for row in rejected]
        empty["replay_reason"] = "every recorded observation was a stale or duplicate replay"
        return empty

    fresh.sort(key=lambda row: (float(row.get("observed_at") or 0.0), str(row.get("observation_id"))))
    current = fresh[-1]
    ttl = float(current.get("evidence_ttl_s") or DEFAULT_EVIDENCE_TTL_S)
    observed_at = float(current.get("observed_at") or 0.0)
    age = max(0.0, ts - observed_at)
    expired = [row for row in fresh if ttl > 0.0 and (ts - float(row.get("observed_at") or 0.0)) > ttl]
    live = [row for row in fresh if row not in expired]
    newest_live = live[-1] if live else current

    conflicts: list[dict[str, Any]] = []
    superseded: list[str] = []
    moved_from_by_id: dict[str, dict[str, Any]] = {}
    moved_count = 0
    revision = 0
    for prior, later in zip(fresh, fresh[1:]):
        prior_pose, later_pose = prior.get("pose"), later.get("pose")
        distance = _pose_distance(prior_pose, later_pose)
        if distance is not None and distance > DEFAULT_MOVED_THRESHOLD_M:
            moved_count += 1
            revision += 1
            superseded.append(str(prior.get("observation_id") or ""))
            later_pose = dict(later_pose or {})
            later_pose["moved_from"] = {
                "pose": prior_pose,
                "distance_m": round(distance, 6),
                "observation_id": str(prior.get("observation_id") or ""),
            }
            moved_from_by_id[str(later.get("observation_id") or "")] = dict(later_pose["moved_from"])
            conflicts.append(
                {
                    "field": "pose",
                    "prior_value": prior_pose,
                    "new_value": later.get("pose"),
                    "distance_m": round(distance, 6),
                    "prior_observation_id": str(prior.get("observation_id") or ""),
                    "new_observation_id": str(later.get("observation_id") or ""),
                    "detected_at_utc": _utc(ts),
                    "resolution": "UNRESOLVED",
                }
            )
        if prior_pose is not None and later_pose is not None:
            if str(prior_pose.get("frame") or "") != str(later_pose.get("frame") or ""):
                # Re-expressed in another frame: incomparable, so no distance is
                # claimed and no conflict is raised, but the belief basis changed.
                revision += 1
        if prior_pose is None and later_pose is not None:
            revision += 1
        for name in sorted(set(prior.get("attributes") or {}) | set(later.get("attributes") or {})):
            before = (prior.get("attributes") or {}).get(name)
            after = (later.get("attributes") or {}).get(name)
            before_value = before.get("value") if isinstance(before, Mapping) else None
            after_value = after.get("value") if isinstance(after, Mapping) else None
            if before_value != after_value:
                revision += 1
                conflicts.append(
                    {
                        "field": f"attribute:{name}",
                        "prior_value": before_value,
                        "new_value": after_value,
                        "prior_observation_id": str(prior.get("observation_id") or ""),
                        "new_observation_id": str(later.get("observation_id") or ""),
                        "detected_at_utc": _utc(ts),
                        "resolution": "UNRESOLVED",
                    }
                )
        if (prior.get("relations") or []) != (later.get("relations") or []):
            revision += 1
            conflicts.append(
                {
                    "field": "relations",
                    "prior_value": prior.get("relations") or [],
                    "new_value": later.get("relations") or [],
                    "prior_observation_id": str(prior.get("observation_id") or ""),
                    "new_observation_id": str(later.get("observation_id") or ""),
                    "detected_at_utc": _utc(ts),
                    "resolution": "UNRESOLVED",
                }
            )

    identity = dict(newest_live.get("identity") or {})
    current_pose = newest_live.get("pose")
    if current_pose is not None:
        current_pose = dict(current_pose)
        moved = moved_from_by_id.get(str(newest_live.get("observation_id") or ""))
        if moved is not None:
            current_pose["moved_from"] = moved
    attributes: dict[str, Any] = {}
    for row in live:
        for name, entry in (row.get("attributes") or {}).items():
            attributes[name] = {
                "value": entry.get("value"),
                "units": entry.get("units"),
                "observation_id": str(row.get("observation_id") or ""),
                "observed_at": float(row.get("observed_at") or 0.0),
                "observed_at_utc": _utc(float(row.get("observed_at") or 0.0)),
            }
    relations: list[dict[str, Any]] = []
    for row in live:
        for entry in row.get("relations") or []:
            item = dict(entry)
            item["observation_id"] = str(row.get("observation_id") or "")
            relations.append(item)

    age_uncertainty = 1.0 if ttl <= 0.0 else min(1.0, age / ttl)
    source_uncertainty = 1.0 - float(newest_live.get("confidence") or 0.0)
    conflict_penalty = min(1.0, conflict_uncertainty * len(conflicts))
    uncertainty = min(1.0, max(age_uncertainty, source_uncertainty) + conflict_penalty)

    return {
        "truth_label": BELIEF_TRUTH_LABEL,
        "entity_id": ident,
        "entity_kind": str(newest_live.get("entity_kind") or "unknown"),
        "known": True,
        "revision": revision,
        "moved_count": moved_count,
        "moved_threshold_m": DEFAULT_MOVED_THRESHOLD_M,
        "identity": identity,
        "pose": current_pose,
        "pose_known": newest_live.get("pose") is not None,
        "attributes": attributes,
        "relations": relations,
        "conflicts": conflicts,
        "contested": bool(conflicts),
        "uncertainty": round(uncertainty, 6),
        "uncertainty_components": {
            "evidence_age": round(age_uncertainty, 6),
            "source_confidence": round(source_uncertainty, 6),
            "open_conflicts": round(conflict_penalty, 6),
        },
        "epistemic_status": str(newest_live.get("epistemic_status") or "UNKNOWN"),
        "source": str(newest_live.get("source") or ""),
        "last_seen": observed_at,
        "last_seen_utc": _utc(observed_at),
        "evidence_age_s": round(age, 6),
        "evidence_ttl_s": ttl,
        "stale": bool(newest_live in expired) if expired else False,
        "supporting_observation_ids": [str(row.get("observation_id") or "") for row in live],
        "expired_evidence_ids": [str(row.get("observation_id") or "") for row in expired],
        "superseded_observation_ids": superseded,
        "rejected_observation_ids": [str(row.get("observation_id") or "") for row in rejected],
        "observation_count": len(rows),
        "action_policy": ACTION_POLICY,
        "effectors_allowed": [],
    }


def target_is_stale(
    entity_id: str,
    *,
    target_observation_id: str | None = None,
    now: float | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Answer a planner's question: is the observation I aimed at still valid?

    A target bound to an observation that a later observation superseded (the
    object moved) or whose evidence expired must be replanned, not retried.
    """
    belief = entity_belief(entity_id, now=now, state_dir=state_dir)
    target = str(target_observation_id or "").strip()
    if not belief.get("known"):
        return {
            "entity_id": entity_id,
            "target_stale": True,
            "reason": "entity is not currently believed to exist",
            "current_observation_id": None,
        }
    live_ids = list(belief["supporting_observation_ids"])
    current_id = live_ids[-1] if live_ids else None
    if target and target in belief["superseded_observation_ids"]:
        return {
            "entity_id": entity_id,
            "target_stale": True,
            "reason": "a later observation moved the entity",
            "current_observation_id": current_id,
        }
    if target and target in belief["expired_evidence_ids"]:
        return {
            "entity_id": entity_id,
            "target_stale": True,
            "reason": "the evidence behind this target expired",
            "current_observation_id": current_id,
        }
    if target and target not in belief["supporting_observation_ids"]:
        return {
            "entity_id": entity_id,
            "target_stale": True,
            "reason": "the target observation is not part of the live evidence",
            "current_observation_id": current_id,
        }
    return {
        "entity_id": entity_id,
        "target_stale": False,
        "reason": "",
        "current_observation_id": current_id,
    }


def _require_map_ref(map_ref: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if map_ref is None:
        return None
    if not isinstance(map_ref, Mapping):
        raise ValueError("map_ref must be a mapping or None")
    map_id = str(map_ref.get("map_id") or "").strip()
    revision = str(map_ref.get("map_revision") or "").strip()
    if not map_id or not revision:
        raise ValueError("map_ref requires map_id and map_revision")
    if len(revision) != 71 or not revision.startswith("sha256:"):
        raise ValueError("map_ref.map_revision must be a sha256: hash")
    return {"map_id": map_id, "map_revision": revision}


def _project_pose(
    pose: Mapping[str, Any] | None,
    *,
    map_ref: Mapping[str, Any] | None,
    entity_id: str,
) -> dict[str, Any] | None:
    """Project an internal metric pose into the C0 POSE shape.

    A pose without a map identity cannot be expressed on the wire, so it is
    withheld rather than invented. An unmeasured heading is projected as a zero
    angle carrying a (pi/2)^2 variance: the belief says "heading unknown", and
    the yaw slot is never mistaken for a measurement.
    """
    if pose is None:
        return None
    if map_ref is None:
        raise ValueError(
            f"entity {entity_id!r} has a pose but no map_ref was supplied; "
            "a pose without a map identity must not be projected"
        )
    uncertainty = float(pose.get("uncertainty_m") or 0.0)
    variance = max(uncertainty * uncertainty, 1e-9)
    yaw = pose.get("yaw_rad")
    yaw_value = 0.0 if yaw is None else float(yaw)
    yaw_variance = (math.pi / 2.0) ** 2 if yaw is None else max(variance, 1e-9)
    return {
        "map_id": str(map_ref["map_id"]),
        "map_revision": str(map_ref["map_revision"]),
        "frame_id": str(pose.get("frame") or "map"),
        "x_m": float(pose["x"]),
        "y_m": float(pose["y"]),
        "yaw_rad": round(yaw_value, 6),
        "covariance": [
            variance, 0.0, 0.0,
            0.0, variance, 0.0,
            0.0, 0.0, yaw_variance,
        ],
    }


def _project_hypotheses(hypotheses: Iterable[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in hypotheses or []:
        if isinstance(raw, Mapping):
            statement = str(raw.get("statement") or "").strip()
            confidence = raw.get("confidence", 0.5)
            support = [str(item) for item in (raw.get("supporting_observation_ids") or [])]
            hypothesis_id = str(raw.get("hypothesis_id") or "").strip() or str(uuid.uuid4())
        else:
            statement = str(raw).strip()
            confidence = 0.5
            support = []
            hypothesis_id = str(uuid.uuid4())
        if not statement:
            raise ValueError("each hypothesis needs a statement")
        out.append(
            {
                "hypothesis_id": hypothesis_id,
                "statement": statement,
                "confidence": round(min(1.0, max(0.0, _finite_number(confidence, field_name="hypothesis.confidence"))), 6),
                "supporting_observation_ids": support,
            }
        )
    return out


def _project_resource_state(resource_state: Iterable[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in resource_state or []:
        item = dict(raw) if isinstance(raw, Mapping) else {"resource": str(raw)}
        name = str(item.get("resource") or item.get("name") or "").strip()
        if not name:
            raise ValueError("each resource entry needs a resource name")
        value = item.get("value")
        age_ms = item.get("source_age_ms", item.get("age_ms"))
        out.append(
            {
                "resource": name,
                "value": None if value is None else round(_finite_number(value, field_name="resource.value"), 6),
                "unit": None if item.get("unit") is None else str(item.get("unit")),
                "source_age_ms": None if age_ms is None else int(max(0, age_ms)),
                "reason": None if item.get("reason") is None else str(item.get("reason")),
            }
        )
    return out


def belief_content_hash(snapshot: Mapping[str, Any]) -> str:
    """Fingerprint a belief snapshot's content, excluding its own identity."""
    content = {key: value for key, value in snapshot.items() if key != "belief_id"}
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def belief_snapshot(
    *,
    body_id: str,
    entity_ids: Iterable[str] | None = None,
    pose: Mapping[str, Any] | None = None,
    frame: str | None = None,
    map_ref: Mapping[str, Any] | None = None,
    hypotheses: Iterable[Any] | None = None,
    resource_state: Iterable[Any] | None = None,
    now: float | None = None,
    state_dir: Path | str | None = None,
    max_entities: int = 64,
) -> dict[str, Any]:
    """One queryable belief snapshot as a C0 `belief_state` record.

    The returned object is exactly the frozen C0 record: it is validated by
    `BeliefState.verify()` before it is returned, so it can cross the robot wire
    unchanged. Alice's richer per-entity metadata rides inside the entity
    `attributes` map under the reserved `belief.` prefix, because the C0 entity
    shape is closed and must not be extended here.
    """
    from System.swarm_adaptive_contracts import RECORDS_SCHEMA_VERSION, BeliefState  # local: keeps this module import-light

    body = str(body_id or "").strip()
    if not body:
        raise ValueError("body_id must be non-empty")
    state = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    clean_map_ref = _require_map_ref(map_ref)
    rows = _read_jsonl(state / BELIEF_LEDGER, max_rows=4096)
    ids = [str(item).strip() for item in (entity_ids or []) if str(item).strip()]
    if not ids:
        seen: list[str] = []
        for row in rows:
            ident = str(row.get("entity_id") or "")
            if ident and ident not in seen:
                seen.append(ident)
        ids = sorted(seen)[:max_entities]

    entities: list[dict[str, Any]] = []
    conflicting: list[dict[str, Any]] = []
    supporting: list[str] = []
    expired: list[str] = []
    relations: list[dict[str, Any]] = []
    revision = 0
    for ident in ids:
        belief = entity_belief(ident, now=ts, state_dir=state)
        if not belief.get("known"):
            continue
        revision = max(revision, int(belief["revision"]))
        attributes: dict[str, Any] = {}
        for name, entry in sorted(belief["attributes"].items()):
            attributes[name] = entry["value"]
            attributes[f"belief.attribute.{name}"] = {
                "units": entry.get("units"),
                "observation_id": entry.get("observation_id"),
                "observed_at_utc": entry.get("observed_at_utc"),
            }
        attributes["belief.uncertainty"] = belief["uncertainty"]
        attributes["belief.uncertainty_components"] = dict(belief["uncertainty_components"])
        attributes["belief.evidence_age_s"] = belief["evidence_age_s"]
        attributes["belief.stale"] = belief["stale"]
        attributes["belief.revision"] = belief["revision"]
        attributes["belief.moved_count"] = belief["moved_count"]
        attributes["belief.contested"] = belief["contested"]
        attributes["belief.pose_known"] = belief["pose_known"]
        attributes["belief.observation_ids"] = list(belief["supporting_observation_ids"])
        attributes["belief.rejected_observation_ids"] = list(belief["rejected_observation_ids"])
        attributes["belief.identity"] = dict(belief["identity"])
        entities.append(
            {
                "entity_id": belief["entity_id"],
                "kind": belief["entity_kind"],
                "pose": _project_pose(belief["pose"], map_ref=clean_map_ref, entity_id=ident),
                "region": None,
                "attributes": attributes,
            }
        )
        for conflict in belief["conflicts"]:
            detail = (
                f"{belief['entity_id']} {conflict['field']} "
                f"prior={conflict['prior_value']!r} new={conflict['new_value']!r} "
                f"unresolved"
            )
            if conflict.get("distance_m") is not None:
                detail += f" distance_m={conflict['distance_m']}"
            conflicting.append(
                {
                    "observation_ids": [
                        str(conflict["prior_observation_id"]),
                        str(conflict["new_observation_id"]),
                    ],
                    "detail": detail,
                }
            )
        supporting.extend(belief["supporting_observation_ids"])
        expired.extend(belief["expired_evidence_ids"])
        for entry in belief["relations"]:
            relations.append(
                {
                    "relation": str(entry.get("predicate") or ""),
                    "subject_id": str(entry.get("subject") or "").strip() or belief["entity_id"],
                    "object_id": str(entry.get("object") or ""),
                }
            )

    clean_body_pose = None
    if pose is not None:
        clean_body_pose = _project_pose(
            _canonical_pose(pose, frame=frame), map_ref=clean_map_ref, entity_id=body
        )
    raw = {
        "schema_version": RECORDS_SCHEMA_VERSION,
        "belief_id": str(uuid.uuid4()),
        "revision": int(revision),
        "body_id": body,
        "created_at_utc": _utc(ts),
        "entities": entities,
        "relations": relations,
        "pose": clean_body_pose,
        "map_ref": dict(clean_map_ref) if clean_map_ref is not None else None,
        "hypotheses": _project_hypotheses(hypotheses),
        "supporting_observation_ids": supporting,
        "expired_evidence_ids": [item for item in expired if item not in supporting],
        "conflicting_evidence": conflicting,
        "resource_state": _project_resource_state(resource_state),
    }
    record = BeliefState.from_dict(raw)
    record.verify()
    return record.to_dict()


__all__ = [
    "ACTION_POLICY",
    "BELIEF_LEDGER",
    "BELIEF_RECORD_CLASSES",
    "BELIEF_TRUTH_LABEL",
    "BOUNDARY",
    "CLAIM_STATUS",
    "DEFAULT_EVIDENCE_TTL_S",
    "DEFAULT_MOVED_THRESHOLD_M",
    "ENTITY_KINDS",
    "EpistemicStatus",
    "OPERATIONAL_DOCTRINE",
    "POSE_UNITS",
    "TRUTH_LABEL",
    "belief_content_hash",
    "belief_snapshot",
    "entity_belief",
    "lived_experience_snapshot",
    "observe_entity",
    "predict_next_event",
    "record_lived_event",
    "target_is_stale",
]
