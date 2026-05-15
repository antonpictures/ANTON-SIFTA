#!/usr/bin/env python3
"""
swarm_3i_evidence_field.py

Local 3I/ATLAS stigmergic evidence-field organ.

This module turns public astronomical data and claim surfaces into append-only
evidence deposits. It is an evidence auditor, not an endorsement engine: JPL,
MPC, MPEC, and peer-reviewed telescope papers are weighted above social posts,
and every claim carries a falsifier plus decaying field strength.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(os.environ.get("SIFTA_STATE_DIR", str(_REPO / ".sifta_state")))

TRUTH_LABEL = "INTERSTELLAR_3I_EVIDENCE_FIELD_V1"
LEDGER_NAME = "interstellar_3i_evidence_field.jsonl"
EPISODIC_TRUTH_LABEL = "INTERSTELLAR_3I_EVIDENCE_DIARY_V1"
OBJECT_ID = "3I/ATLAS"
HORIZONS_COMMAND = "'3I'"

TRACE_KINDS = {
    "EVIDENCE_DEPOSIT",
    "CLAIM",
    "REINFORCEMENT",
    "FALSIFICATION",
    "FETCH_RECEIPT",
    "SWIMMER_ACTION",
}

CLAIM_LANES = (
    "orbit_dynamics",
    "non_grav_acceleration",
    "coma_morphology",
    "chemistry",
    "instrument_coverage",
    "origin_model",
    "sentinel_claims",
)

SOURCE_WEIGHTS = {
    "JPL_HORIZONS": 0.95,
    "MPC": 0.92,
    "MPEC": 0.90,
    "PEER_REVIEWED": 0.86,
    "MISSION_RELEASE": 0.82,
    "PREPRINT": 0.74,
    "GROUND_BASED": 0.70,
    "SENTINEL_POST": 0.36,
    "LOCAL_ANALYSIS": 0.62,
}

DEFAULT_TAU_S = {
    "EVIDENCE_DEPOSIT": 45.0 * 24.0 * 3600.0,
    "CLAIM": 10.0 * 24.0 * 3600.0,
    "REINFORCEMENT": 30.0 * 24.0 * 3600.0,
    "FALSIFICATION": 75.0 * 24.0 * 3600.0,
    "FETCH_RECEIPT": 7.0 * 24.0 * 3600.0,
    "SWIMMER_ACTION": 5.0 * 24.0 * 3600.0,
}


@dataclass(frozen=True)
class FieldDeposit:
    row_index: int
    ts: float
    trace_id: str
    kind: str
    object_id: str
    lane: str
    source_type: str
    confidence: float
    source_weight: float
    strength: float
    stgm_reward_hint: float
    receipt: str
    title: str
    claim: str
    source_url: str
    evidence_hash: str
    falsifier: str
    payload: dict[str, Any]


PUBLIC_EVIDENCE_DEPOSITS: tuple[dict[str, Any], ...] = (
    {
        "kind": "EVIDENCE_DEPOSIT",
        "lane": "orbit_dynamics",
        "source_type": "JPL_HORIZONS",
        "title": "JPL Horizons orbit solution for 3I/ATLAS",
        "claim": (
            "3I/ATLAS is queryable as a small body in JPL Horizons with a "
            "strongly hyperbolic orbit and non-gravitational comet-model terms."
        ),
        "confidence": 0.94,
        "source_url": "https://ssd.jpl.nasa.gov/horizons/app.html#/",
        "falsifier": "Pull live Horizons vectors/elements and compare solution metadata against this deposit.",
        "payload": {
            "designation": "3I/ATLAS = C/2025 N1 (ATLAS)",
            "public_orbit_summary": {
                "eccentricity_approx": 6.14,
                "perihelion_distance_au_approx": 1.356,
                "perihelion_date": "2025-10-29",
                "inclination_deg_approx": 175.1,
            },
        },
    },
    {
        "kind": "EVIDENCE_DEPOSIT",
        "lane": "orbit_dynamics",
        "source_type": "MPC",
        "title": "Minor Planet Center observation archive",
        "claim": (
            "MPC carries official object records and an astrometric observation archive for 3I."
        ),
        "confidence": 0.91,
        "source_url": "https://minorplanetcenter.net/db_search/show_object?object_id=3I",
        "falsifier": "Fetch the MPC observation API for object 3I and verify observation count/date span.",
        "payload": {"designation": "3I", "data_layer": "astrometry"},
    },
    {
        "kind": "EVIDENCE_DEPOSIT",
        "lane": "instrument_coverage",
        "source_type": "MPEC",
        "title": "MPEC discovery and follow-up notices",
        "claim": "MPEC notices establish the official discovery/follow-up trail for C/2025 N1.",
        "confidence": 0.88,
        "source_url": "https://www.minorplanetcenter.net/mpec/",
        "falsifier": "Locate MPEC 2025-N12 / 2025-N102 or later MPEC notices and match designation text.",
        "payload": {"notices": ["MPEC 2025-N12", "MPEC 2025-N102"]},
    },
    {
        "kind": "EVIDENCE_DEPOSIT",
        "lane": "coma_morphology",
        "source_type": "PEER_REVIEWED",
        "title": "Hubble observations of active dust emission",
        "claim": (
            "Hubble observations constrain nucleus size and dust activity; morphology is comet-like "
            "and must be treated as evidence before anomaly narratives."
        ),
        "confidence": 0.84,
        "source_url": "https://iopscience.iop.org/article/10.3847/2041-8213/adf8d8",
        "falsifier": "Compare quoted radius/activity ranges to the published Hubble paper.",
        "payload": {"instrument": "HST", "observable": "dust coma morphology"},
    },
    {
        "kind": "EVIDENCE_DEPOSIT",
        "lane": "chemistry",
        "source_type": "PEER_REVIEWED",
        "title": "JWST spatial-spectral coma mapping",
        "claim": (
            "JWST/NIRSpec reports volatile detections such as CO, CO2, H2O, CH3OH, and CH4; "
            "chemistry claims should link to measured species and uncertainty."
        ),
        "confidence": 0.82,
        "source_url": "https://arxiv.org/abs/2603.20460",
        "falsifier": "Verify molecule list and abundance ratios against the JWST paper version cited.",
        "payload": {"instrument": "JWST NIRSpec", "species": ["CO", "CO2", "H2O", "CH3OH", "CH4"]},
    },
    {
        "kind": "EVIDENCE_DEPOSIT",
        "lane": "chemistry",
        "source_type": "PEER_REVIEWED",
        "title": "SPHEREx post-perihelion infrared mapping",
        "claim": (
            "SPHEREx reports post-perihelion activity and infrared coma gas/dust features; "
            "this reinforces a normal volatile-coma analysis lane."
        ),
        "confidence": 0.80,
        "source_url": "https://iopscience.iop.org/article/10.3847/2515-5172/ae3f95",
        "falsifier": "Check the SPHEREx note for the exact species/features and observation date.",
        "payload": {"instrument": "SPHEREx", "observable": "infrared coma mapping"},
    },
    {
        "kind": "CLAIM",
        "lane": "non_grav_acceleration",
        "source_type": "SENTINEL_POST",
        "title": "Sentinel-style acceleration anomaly claim",
        "claim": (
            "Social posts claim anomalous non-gravitational acceleration; SIFTA stores this as a "
            "low-weight hypothesis until orbit residuals are recomputed against comet outgassing models."
        ),
        "confidence": 0.38,
        "source_url": "https://thesentinelnetwork.substack.com/",
        "falsifier": "Fit Horizons/MPC residuals against published non-gravitational parameters and uncertainty.",
        "payload": {"claim_layer": "social", "truth_label": "HYPOTHESIS"},
    },
    {
        "kind": "CLAIM",
        "lane": "origin_model",
        "source_type": "PREPRINT",
        "title": "Interstellar origin and thick-disk/gcr-processing models",
        "claim": (
            "The hyperbolic orbit establishes interstellar origin; detailed galactic origin or cosmic-ray "
            "processing models remain paper-linked hypotheses."
        ),
        "confidence": 0.72,
        "source_url": "https://arxiv.org/html/2507.05252v3",
        "falsifier": "Compare any origin claim against peer-reviewed dynamics and chemistry papers.",
        "payload": {"origin_status": "interstellar_confirmed", "submodels": ["galactic origin", "GCR processing"]},
    },
)


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def ledger_path(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def local_receipt(payload: Mapping[str, Any]) -> str:
    clean = {k: v for k, v in payload.items() if k != "receipt"}
    return hashlib.sha256(_canonical_json(clean).encode("utf-8")).hexdigest()


def evidence_hash(payload: Mapping[str, Any] | str) -> str:
    if isinstance(payload, str):
        raw = payload
    else:
        raw = _canonical_json(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=True, separators=(",", ":")) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _source_weight(source_type: str) -> float:
    return SOURCE_WEIGHTS.get(str(source_type).upper(), 0.50)


def _stgm_reward(kind: str, source_type: str, confidence: float, falsifier: str) -> float:
    base = {
        "EVIDENCE_DEPOSIT": 1.0,
        "CLAIM": 0.35,
        "REINFORCEMENT": 1.4,
        "FALSIFICATION": 1.8,
        "FETCH_RECEIPT": 0.75,
        "SWIMMER_ACTION": 0.20,
    }.get(kind, 0.25)
    falsifier_bonus = 0.35 if falsifier.strip() else 0.0
    return round(base * (0.45 + _source_weight(source_type)) * (0.35 + _clamp(confidence)) + falsifier_bonus, 4)


def _deposit_strength(kind: str, confidence: float, source_weight: float, ts: float, now_ts: float) -> float:
    tau = DEFAULT_TAU_S.get(kind, 7.0 * 24.0 * 3600.0)
    age = max(0.0, now_ts - ts)
    return _clamp(confidence) * _clamp(source_weight) * math.exp(-age / max(1.0, tau))


def _make_trace(
    *,
    kind: str,
    lane: str,
    title: str,
    claim: str,
    confidence: float,
    source_type: str,
    source_url: str,
    falsifier: str,
    payload: Mapping[str, Any] | None = None,
    object_id: str = OBJECT_ID,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in TRACE_KINDS:
        raise ValueError(f"unknown 3I trace kind: {kind}")
    if lane not in CLAIM_LANES:
        raise ValueError(f"unknown 3I evidence lane: {lane}")
    payload_dict = dict(payload or {})
    source_weight = _source_weight(source_type)
    row: dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": kind,
        "truth_label": TRUTH_LABEL,
        "object_id": object_id,
        "lane": lane,
        "title": title,
        "claim": claim,
        "confidence": round(_clamp(confidence), 4),
        "source_type": str(source_type).upper(),
        "source_weight": round(source_weight, 4),
        "source_url": source_url,
        "evidence_hash": evidence_hash(payload_dict or claim),
        "falsifier": falsifier,
        "stgm_reward_hint": _stgm_reward(kind, source_type, confidence, falsifier),
        "payload": payload_dict,
    }
    if extra:
        row.update(dict(extra))
    row["receipt"] = local_receipt(row)
    return row


def append_trace(row: Mapping[str, Any], *, state_dir: Path | None = None, diary: bool = True) -> dict[str, Any]:
    payload = dict(row)
    if not payload.get("receipt"):
        payload["receipt"] = local_receipt(payload)
    _append_jsonl(ledger_path(state_dir), payload)
    if diary:
        _append_diary_note(payload, state_dir=state_dir)
    return payload


def _append_diary_note(row: Mapping[str, Any], *, state_dir: Path | None = None) -> None:
    state = _state_dir(state_dir)
    note = {
        "ts": time.time(),
        "truth_label": EPISODIC_TRUTH_LABEL,
        "bucket": "interstellar_3i_evidence_field",
        "summary": (
            f"I deposited {row.get('kind')} for {row.get('object_id')} "
            f"{row.get('lane')} with confidence {row.get('confidence')}."
        ),
        "source_receipt": row.get("receipt"),
        "source_trace_id": row.get("trace_id"),
    }
    _append_jsonl(state / "episodic_diary.jsonl", note)


def existing_receipts(*, state_dir: Path | None = None) -> set[str]:
    return {str(row.get("receipt")) for row in read_jsonl(ledger_path(state_dir)) if row.get("receipt")}


def seed_public_evidence_deposits(*, state_dir: Path | None = None, dedupe: bool = True) -> list[dict[str, Any]]:
    """Deposit curated public 3I/ATLAS evidence and claim-layer rows."""
    existing = existing_receipts(state_dir=state_dir) if dedupe else set()
    written: list[dict[str, Any]] = []
    for item in PUBLIC_EVIDENCE_DEPOSITS:
        row = _make_trace(
            kind=str(item["kind"]),
            lane=str(item["lane"]),
            title=str(item["title"]),
            claim=str(item["claim"]),
            confidence=float(item["confidence"]),
            source_type=str(item["source_type"]),
            source_url=str(item["source_url"]),
            falsifier=str(item["falsifier"]),
            payload=dict(item.get("payload") or {}),
        )
        if dedupe and row["receipt"] in existing:
            continue
        written.append(append_trace(row, state_dir=state_dir))
        existing.add(row["receipt"])
    return written


def add_claim(
    lane: str,
    claim: str,
    *,
    title: str = "Architect claim deposit",
    source_type: str = "LOCAL_ANALYSIS",
    source_url: str = "local://architect-note",
    confidence: float = 0.50,
    falsifier: str = "Attach a primary source or run a deterministic SIFTA refit.",
    payload: Mapping[str, Any] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    row = _make_trace(
        kind="CLAIM",
        lane=lane,
        title=title,
        claim=claim,
        confidence=confidence,
        source_type=source_type,
        source_url=source_url,
        falsifier=falsifier,
        payload=payload,
    )
    return append_trace(row, state_dir=state_dir)


def add_reinforcement(
    *,
    lane: str,
    title: str,
    claim: str,
    source_type: str,
    source_url: str,
    confidence: float,
    falsifier: str,
    payload: Mapping[str, Any] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    row = _make_trace(
        kind="REINFORCEMENT",
        lane=lane,
        title=title,
        claim=claim,
        confidence=confidence,
        source_type=source_type,
        source_url=source_url,
        falsifier=falsifier,
        payload=payload,
    )
    return append_trace(row, state_dir=state_dir)


def add_falsification(
    *,
    lane: str,
    title: str,
    claim: str,
    source_type: str = "LOCAL_ANALYSIS",
    source_url: str = "local://falsifier",
    confidence: float = 0.70,
    falsifier: str = "Re-run with updated observations.",
    payload: Mapping[str, Any] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    row = _make_trace(
        kind="FALSIFICATION",
        lane=lane,
        title=title,
        claim=claim,
        confidence=confidence,
        source_type=source_type,
        source_url=source_url,
        falsifier=falsifier,
        payload=payload,
    )
    return append_trace(row, state_dir=state_dir)


def horizons_api_url(
    *,
    start_time: str = "2025-07-01",
    stop_time: str = "2025-11-15",
    step_size: str = "10 d",
    center: str = "'500@10'",
    ephem_type: str = "VECTORS",
) -> str:
    params = {
        "format": "json",
        "COMMAND": HORIZONS_COMMAND,
        "OBJ_DATA": "YES",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": ephem_type,
        "CENTER": center,
        "START_TIME": f"'{start_time}'",
        "STOP_TIME": f"'{stop_time}'",
        "STEP_SIZE": f"'{step_size}'",
        "VEC_TABLE": "2",
        "CSV_FORMAT": "YES",
    }
    return "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(params)


def fetch_jpl_horizons(
    *,
    start_time: str = "2025-07-01",
    stop_time: str = "2025-11-15",
    step_size: str = "10 d",
    state_dir: Path | None = None,
    timeout_s: float = 12.0,
    write: bool = True,
) -> dict[str, Any]:
    """Fetch live JPL Horizons data and optionally receipt it into the field."""
    url = horizons_api_url(start_time=start_time, stop_time=stop_time, step_size=step_size)
    started = time.time()
    ok = False
    result_text = ""
    status = "not_started"
    try:
        req = Request(url, headers={"User-Agent": "SIFTA-3I-Evidence-Field/1.0"})
        with urlopen(req, timeout=timeout_s) as response:
            raw = response.read(1_500_000)
            result_text = raw.decode("utf-8", errors="replace")
            ok = True
            status = f"http_{getattr(response, 'status', 200)}"
    except Exception as exc:
        status = f"error:{type(exc).__name__}:{exc}"

    payload = {
        "ok": ok,
        "status": status,
        "url": url,
        "elapsed_s": round(time.time() - started, 3),
        "result_sha256": evidence_hash(result_text),
        "result_bytes": len(result_text.encode("utf-8", errors="replace")),
        "line_count": len(result_text.splitlines()),
        "preview": result_text[:1200],
        "query": {
            "command": HORIZONS_COMMAND,
            "start_time": start_time,
            "stop_time": stop_time,
            "step_size": step_size,
        },
    }
    confidence = 0.93 if ok else 0.15
    row = _make_trace(
        kind="FETCH_RECEIPT",
        lane="orbit_dynamics",
        title="Live JPL Horizons vector pull",
        claim=(
            "SIFTA attempted a live JPL Horizons VECTORS pull for 3I/ATLAS; "
            "the payload hash and preview are stored as the receipt."
        ),
        confidence=confidence,
        source_type="JPL_HORIZONS",
        source_url=url,
        falsifier="Repeat query and compare result_sha256 / solution metadata.",
        payload=payload,
    )
    if write:
        return append_trace(row, state_dir=state_dir)
    return row


def deposits(*, state_dir: Path | None = None, now: float | None = None) -> list[FieldDeposit]:
    rows = read_jsonl(ledger_path(state_dir))
    now_ts = float(time.time() if now is None else now)
    out: list[FieldDeposit] = []
    for idx, row in enumerate(rows, start=1):
        try:
            kind = str(row.get("kind", ""))
            confidence = _clamp(float(row.get("confidence", 0.0) or 0.0))
            source_weight = _clamp(float(row.get("source_weight", _source_weight(str(row.get("source_type", ""))))))
            strength = _deposit_strength(kind, confidence, source_weight, float(row.get("ts", 0.0) or 0.0), now_ts)
            out.append(FieldDeposit(
                row_index=idx,
                ts=float(row.get("ts", 0.0) or 0.0),
                trace_id=str(row.get("trace_id", f"row_{idx}")),
                kind=kind,
                object_id=str(row.get("object_id", OBJECT_ID)),
                lane=str(row.get("lane", "unknown")),
                source_type=str(row.get("source_type", "UNKNOWN")),
                confidence=round(confidence, 4),
                source_weight=round(source_weight, 4),
                strength=round(strength, 5),
                stgm_reward_hint=round(float(row.get("stgm_reward_hint", 0.0) or 0.0), 4),
                receipt=str(row.get("receipt", "")),
                title=str(row.get("title", "")),
                claim=str(row.get("claim", "")),
                source_url=str(row.get("source_url", "")),
                evidence_hash=str(row.get("evidence_hash", "")),
                falsifier=str(row.get("falsifier", "")),
                payload=dict(row.get("payload") or {}),
            ))
        except Exception:
            continue
    return out


def swimmer_actions(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_lane = dict(snapshot.get("by_lane") or {})
    unknown = list(snapshot.get("unknown_lanes") or [])
    actions: list[dict[str, Any]] = []
    if unknown:
        actions.append({
            "swimmer": "ClaimSentinel",
            "action": f"Pull primary evidence for cold lanes: {', '.join(unknown[:3])}",
            "stgm_reward_hint": 1.25,
        })
    if by_lane.get("sentinel_claims", 0.0) > by_lane.get("non_grav_acceleration", 0.0):
        actions.append({
            "swimmer": "Falsifier",
            "action": "Bind Sentinel anomaly language to a Horizons/MPC residual refit.",
            "stgm_reward_hint": 2.0,
        })
    if by_lane.get("chemistry", 0.0) < 1.0:
        actions.append({
            "swimmer": "ChemistryForager",
            "action": "Extract molecule, abundance, and uncertainty rows from JWST/SPHEREx papers.",
            "stgm_reward_hint": 1.6,
        })
    actions.append({
        "swimmer": "EphemerisMapper",
        "action": "Refresh JPL Horizons vectors and write hash receipt.",
        "stgm_reward_hint": 1.1,
    })
    return actions[:5]


def field_snapshot(*, state_dir: Path | None = None, now: float | None = None) -> dict[str, Any]:
    deps = deposits(state_dir=state_dir, now=now)
    by_lane: dict[str, float] = {lane: 0.0 for lane in CLAIM_LANES}
    by_source_type: dict[str, float] = {}
    total_reward = 0.0
    for dep in deps:
        sign = -1.0 if dep.kind == "FALSIFICATION" else 1.0
        by_lane[dep.lane] = round(by_lane.get(dep.lane, 0.0) + sign * dep.strength, 5)
        by_source_type[dep.source_type] = round(by_source_type.get(dep.source_type, 0.0) + sign * dep.strength, 5)
        total_reward += max(0.0, dep.stgm_reward_hint)
    strongest = sorted(
        [asdict(d) for d in deps if d.kind in {"EVIDENCE_DEPOSIT", "CLAIM", "REINFORCEMENT"}],
        key=lambda row: float(row.get("strength", 0.0)),
        reverse=True,
    )
    falsifications = [asdict(d) for d in deps if d.kind == "FALSIFICATION"]
    latest_fetch = next((asdict(d) for d in reversed(deps) if d.kind == "FETCH_RECEIPT"), None)
    snapshot = {
        "truth_label": TRUTH_LABEL,
        "object_id": OBJECT_ID,
        "ledger": str(ledger_path(state_dir)),
        "deposit_count": len(deps),
        "by_lane": by_lane,
        "by_source_type": by_source_type,
        "strongest": strongest[:12],
        "falsifications": falsifications[-12:],
        "latest_fetch": latest_fetch,
        "unknown_lanes": [lane for lane, value in by_lane.items() if abs(value) < 1e-9],
        "total_stgm_reward_hint": round(total_reward, 4),
    }
    snapshot["swimmer_actions"] = swimmer_actions(snapshot)
    return snapshot


def orbit_points_2d(n: int = 220) -> list[tuple[float, float, float]]:
    """
    Deterministic visual orbit proxy from public 3I parameters.

    The app uses this for the canvas when a full Horizons vector cache is not
    available. It is explicitly a visualization proxy; live pulls are receipted
    separately by fetch_jpl_horizons().
    """
    e = 6.14
    q = 1.356
    semi_latus = q * (1.0 + e)
    out: list[tuple[float, float, float]] = []
    max_true_anomaly = math.acos(-1.0 / e) - 0.04
    for i in range(n):
        t = -max_true_anomaly + 2.0 * max_true_anomaly * i / max(1, n - 1)
        r = semi_latus / max(0.08, 1.0 + e * math.cos(t))
        # Rotate the orbital-plane proxy so the path looks retrograde and not axis-aligned.
        rot = math.radians(128.0)
        x = r * math.cos(t)
        y = 0.34 * r * math.sin(t)
        xr = x * math.cos(rot) - y * math.sin(rot)
        yr = x * math.sin(rot) + y * math.cos(rot)
        out.append((xr, yr, r))
    return out


__all__ = [
    "CLAIM_LANES",
    "FieldDeposit",
    "LEDGER_NAME",
    "OBJECT_ID",
    "SOURCE_WEIGHTS",
    "TRACE_KINDS",
    "TRUTH_LABEL",
    "add_claim",
    "add_falsification",
    "add_reinforcement",
    "append_trace",
    "deposits",
    "evidence_hash",
    "fetch_jpl_horizons",
    "field_snapshot",
    "horizons_api_url",
    "ledger_path",
    "local_receipt",
    "orbit_points_2d",
    "read_jsonl",
    "seed_public_evidence_deposits",
    "swimmer_actions",
]


if __name__ == "__main__":
    seed_public_evidence_deposits()
    print(json.dumps(field_snapshot(), indent=2, sort_keys=True))
