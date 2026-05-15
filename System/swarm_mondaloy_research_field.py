#!/usr/bin/env python3
"""
swarm_mondaloy_research_field.py

Local Mondaloy research-field organ.

This is a physics-informed, receipt-writing research surrogate, not a
qualified CALPHAD database and not a material-process specification. Public
source facts are deposited as document traces. Unknown process vectors stay
truth-labeled as hypotheses until primary sources or lab data reinforce or
falsify them.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(os.environ.get("SIFTA_STATE_DIR", str(_REPO / ".sifta_state")))

TRUTH_LABEL = "MONDALOY_PROCESS_FIELD_V1"
LEDGER_NAME = "mondaloy_process_field.jsonl"
EPISODIC_TRUTH_LABEL = "MONDALOY_PROCESS_FIELD_DIARY_V1"

TRACE_KINDS = {
    "ALLOY_PROCESS_HYPOTHESIS",
    "DOCUMENT_READ",
    "SIM_RUN",
    "FALSIFICATION",
    "REINFORCEMENT",
}

PROCESS_VECTORS = (
    "heat_treat",
    "powder_o2_limit",
    "hip_cycle",
    "promoted_combustion_protocol",
    "oxygen_service_cleaning",
    "am_build_window",
    "surface_finish",
    "coating_enamel_spray",
)

DEFAULT_TAU_S = {
    "DOCUMENT_READ": 30.0 * 24.0 * 3600.0,
    "ALLOY_PROCESS_HYPOTHESIS": 7.0 * 24.0 * 3600.0,
    "SIM_RUN": 3.0 * 24.0 * 3600.0,
    "FALSIFICATION": 60.0 * 24.0 * 3600.0,
    "REINFORCEMENT": 21.0 * 24.0 * 3600.0,
}


@dataclass(frozen=True)
class AlloyComposition:
    alloy: str
    ni: float
    co: float
    cr: float
    al: float
    ti: float
    mn: float
    c: float
    b: float
    zr: float
    basis: str


@dataclass(frozen=True)
class PhysicsScore:
    alloy: str
    vector: str
    confidence: float
    physics_score: float
    gamma_prime_index: float
    tensile_strength_ksi_proxy: float
    burn_resistance_proxy: float
    promoted_combustion_margin_psi_proxy: float
    process_window_score: float
    powder_cleanliness_score: float
    oxide_stability_proxy: float
    diffusion_length_um: float
    oxygen_pickup_ppm: float | None
    nitrogen_pickup_ppm: float | None
    parsed_temperatures_c: tuple[float, ...]
    parsed_times_h: tuple[float, ...]
    falsifiers: tuple[str, ...]
    notes: tuple[str, ...]
    truth_label: str = TRUTH_LABEL


@dataclass(frozen=True)
class FieldDeposit:
    row_index: int
    ts: float
    trace_id: str
    kind: str
    alloy: str
    vector: str
    confidence: float
    strength: float
    receipt: str
    hypothesis: str
    source_doc: str
    falsifier: str
    physics_score: dict[str, Any]


DEFAULT_COMPOSITIONS: dict[str, AlloyComposition] = {
    "MONDALOY_100": AlloyComposition(
        alloy="MONDALOY_100",
        ni=70.0,
        co=14.5,
        cr=9.0,
        al=2.0,
        ti=2.5,
        mn=0.20,
        c=0.08,
        b=0.006,
        zr=0.04,
        basis="public patent range representative midpoint; not an exact proprietary heat",
    ),
    "MONDALOY_200": AlloyComposition(
        alloy="MONDALOY_200",
        ni=68.5,
        co=15.0,
        cr=12.0,
        al=1.8,
        ti=2.2,
        mn=0.20,
        c=0.08,
        b=0.006,
        zr=0.04,
        basis="public patent range high-Cr representative midpoint; not an exact proprietary heat",
    ),
}

PUBLIC_SOURCE_DEPOSITS: tuple[dict[str, Any], ...] = (
    {
        "source_doc": "US20030053926A1",
        "alloy": "MONDALOY_100",
        "vector": "heat_treat",
        "hypothesis": (
            "Patent discloses Ni-Co-Cr-Al-Ti burn-resistant alloy ranges and VIM+VAR "
            "wrought ingot route, but does not publish solution/aging schedules."
        ),
        "confidence": 0.78,
        "falsifier": "Locate a primary-source process traveler with exact heat treatment.",
    },
    {
        "source_doc": "US20030053926A1",
        "alloy": "MONDALOY_200",
        "vector": "promoted_combustion_protocol",
        "hypothesis": (
            "Public patent examples cite promoted combustion screening on one-eighth-inch "
            "rod specimens in high-pressure gaseous oxygen."
        ),
        "confidence": 0.74,
        "falsifier": "Find the qualified AFRL/NASA/Aerojet apparatus and pass-fail protocol.",
    },
    {
        "source_doc": "spacenews_2017_jacinto",
        "alloy": "MONDALOY_100",
        "vector": "am_build_window",
        "hypothesis": (
            "Inventor interview confirms conventional wrought and powder/additive routes "
            "for Mondaloy 100/200; exact powder and build windows remain unpublished."
        ),
        "confidence": 0.70,
        "falsifier": "Locate AM parameter sheet, powder specification, or build traveler.",
    },
    {
        "source_doc": "spacenews_2017_jacinto",
        "alloy": "MONDALOY_200",
        "vector": "oxygen_service_cleaning",
        "hypothesis": (
            "AR1/HCBT use implies oxygen-service cleanliness control, but public sources "
            "do not expose machining, particle, hydrocarbon, or passivation limits."
        ),
        "confidence": 0.55,
        "falsifier": "Find an oxygen-cleaning spec tied to Mondaloy hardware.",
    },
    {
        "source_doc": "US20170082070A1_US20190032604A1",
        "alloy": "MONDALOY_200",
        "vector": "coating_enamel_spray",
        "hypothesis": (
            "Later turbopump coating patents mention Mondaloy with enamel glass and/or "
            "oxide powders, thermal spray, functional grading, and firing concepts."
        ),
        "confidence": 0.62,
        "falsifier": "Locate qualified spray parameters, firing cycle, inspection, and bond rules.",
    },
)


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def ledger_path(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _gaussian(value: float, center: float, width: float) -> float:
    if width <= 0:
        return 0.0
    return math.exp(-0.5 * ((value - center) / width) ** 2)


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def local_receipt(payload: Mapping[str, Any]) -> str:
    clean = {k: v for k, v in payload.items() if k != "receipt"}
    return hashlib.sha256(_canonical_json(clean).encode("utf-8")).hexdigest()


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


def _first_number_after(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def parse_process_text(text: str) -> dict[str, Any]:
    """Extract process hints from a hypothesis or source passage."""
    temps = tuple(float(x) for x in re.findall(r"(\d{3,4}(?:\.\d+)?)\s*(?:deg\s*)?C\b", text, re.IGNORECASE))
    times = tuple(float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b", text, re.IGNORECASE))
    oxygen = (
        _first_number_after(r"(?:oxygen|O2|O)\s*(?:limit|max|<=|<|at|=)?\s*(\d+(?:\.\d+)?)\s*ppm", text)
        or _first_number_after(r"(\d+(?:\.\d+)?)\s*ppm\s*(?:oxygen|O2|O)\b", text)
    )
    nitrogen = (
        _first_number_after(r"(?:nitrogen|N2|N)\s*(?:limit|max|<=|<|at|=)?\s*(\d+(?:\.\d+)?)\s*ppm", text)
        or _first_number_after(r"(\d+(?:\.\d+)?)\s*ppm\s*(?:nitrogen|N2|N)\b", text)
    )
    lower = text.lower()
    return {
        "temperatures_c": temps,
        "times_h": times,
        "oxygen_ppm": oxygen,
        "nitrogen_ppm": nitrogen,
        "has_argon": "argon" in lower,
        "has_vacuum": "vacuum" in lower or "vim" in lower or "var" in lower,
        "has_hip": "hip" in lower or "hot isostatic" in lower,
        "has_cleaning": any(k in lower for k in ("oxygen clean", "degrease", "passivation", "hydrocarbon")),
        "has_am": any(k in lower for k in ("additive", "powder", "laser", "lpbf", "am build")),
    }


def _diffusion_length_um(temperature_c: float, hours: float) -> float:
    """Arrhenius interdiffusion length proxy for Ni-base alloys."""
    if temperature_c <= 0 or hours <= 0:
        return 0.0
    gas_r = 8.314462618
    d0_m2_s = 2.0e-5
    q_j_mol = 280_000.0
    kelvin = temperature_c + 273.15
    diffusivity = d0_m2_s * math.exp(-q_j_mol / (gas_r * kelvin))
    length_m = math.sqrt(max(0.0, 6.0 * diffusivity * hours * 3600.0))
    return length_m * 1_000_000.0


def _composition(alloy: str, composition: Mapping[str, float] | None = None) -> AlloyComposition:
    key = alloy.upper()
    base = DEFAULT_COMPOSITIONS.get(key)
    if base is None:
        raise ValueError(f"unknown alloy {alloy!r}")
    if not composition:
        return base
    data = asdict(base)
    for src, dst in (
        ("Ni", "ni"),
        ("Co", "co"),
        ("Cr", "cr"),
        ("Al", "al"),
        ("Ti", "ti"),
        ("Mn", "mn"),
        ("C", "c"),
        ("B", "b"),
        ("Zr", "zr"),
    ):
        if src in composition:
            data[dst] = float(composition[src])
        elif dst in composition:
            data[dst] = float(composition[dst])
    data["basis"] = "caller override"
    return AlloyComposition(**data)


def score_process_hypothesis(
    alloy: str,
    vector: str,
    hypothesis: str,
    *,
    composition: Mapping[str, float] | None = None,
) -> PhysicsScore:
    """Score one proposed processing vector with bounded, labeled proxies."""
    if vector not in PROCESS_VECTORS:
        raise ValueError(f"unknown process vector {vector!r}")
    comp = _composition(alloy, composition)
    parsed = parse_process_text(hypothesis)
    temps = tuple(float(t) for t in parsed["temperatures_c"])
    times = tuple(float(t) for t in parsed["times_h"])

    solution_temp = max(temps) if temps else 1150.0
    aging_candidates = [t for t in temps if t < solution_temp - 40.0]
    aging_temp = sum(aging_candidates) / len(aging_candidates) if aging_candidates else 760.0
    total_time_h = sum(times) if times else 10.0

    solution_fit = _gaussian(solution_temp, 1150.0, 85.0)
    age_fit = _gaussian(aging_temp, 760.0, 95.0)
    hip_fit = _gaussian(solution_temp, 1165.0, 95.0) if vector == "hip_cycle" or parsed["has_hip"] else 0.65

    al_ti = comp.al + comp.ti
    gamma_base = _clamp((al_ti - 2.4) / 3.6)
    gamma_prime = _clamp(gamma_base * (0.58 + 0.42 * age_fit) * (0.78 + 0.22 * solution_fit), 0.0, 1.15)

    oxygen_ppm = parsed["oxygen_ppm"]
    nitrogen_ppm = parsed["nitrogen_ppm"]
    assumed_o = oxygen_ppm if oxygen_ppm is not None else (450.0 if parsed["has_am"] else 180.0)
    assumed_n = nitrogen_ppm if nitrogen_ppm is not None else (120.0 if parsed["has_am"] else 60.0)

    oxygen_cleanliness = 1.0 - _clamp((assumed_o - 180.0) / 820.0)
    nitrogen_cleanliness = 1.0 - _clamp((assumed_n - 80.0) / 420.0)
    atmosphere_bonus = 0.08 if (parsed["has_argon"] or parsed["has_vacuum"]) else 0.0
    cleaning_bonus = 0.08 if parsed["has_cleaning"] else 0.0
    powder_cleanliness = _clamp(0.52 * oxygen_cleanliness + 0.32 * nitrogen_cleanliness + atmosphere_bonus + cleaning_bonus)

    cr_term = _clamp((comp.cr - 4.0) / 12.0)
    co_term = _clamp((comp.co - 12.0) / 5.0)
    oxide_stability = _clamp(0.70 * cr_term + 0.12 * co_term + 0.18 * powder_cleanliness)

    gamma_burn_penalty = 0.30 * gamma_prime
    am_penalty = 0.08 if parsed["has_am"] and assumed_o > 350.0 else 0.0
    burn_resistance = _clamp(0.55 * oxide_stability + 0.28 * powder_cleanliness + 0.10 * cr_term - gamma_burn_penalty - am_penalty + 0.12)

    process_window = _clamp(0.38 * solution_fit + 0.34 * age_fit + 0.16 * hip_fit + 0.12 * powder_cleanliness)
    diffusion_length = _diffusion_length_um(solution_temp, total_time_h)
    diffusion_fit = _clamp(1.0 - abs(diffusion_length - 7.0) / 18.0)

    strength = 128.0 + 58.0 * gamma_prime + 12.0 * co_term + 9.0 * process_window
    promoted_margin = 4200.0 + 6300.0 * burn_resistance - 1200.0 * max(0.0, gamma_prime - 0.82)

    evidence_bonus = 0.0
    if temps:
        evidence_bonus += 0.08
    if times:
        evidence_bonus += 0.05
    if oxygen_ppm is not None or nitrogen_ppm is not None:
        evidence_bonus += 0.06
    confidence = _clamp(
        0.12
        + 0.30 * process_window
        + 0.26 * burn_resistance
        + 0.16 * diffusion_fit
        + evidence_bonus
    )
    physics_score = _clamp(0.34 * process_window + 0.30 * burn_resistance + 0.20 * gamma_prime + 0.16 * diffusion_fit)

    falsifiers: list[str] = []
    notes: list[str] = []
    if gamma_prime > 0.84 and burn_resistance < 0.55:
        falsifiers.append("gamma-prime strengthening proxy crosses burn-resistance cliff")
    if comp.cr < 6.0:
        falsifiers.append("Cr below public example comfort zone for oxygen oxide stability")
    if parsed["has_am"] and assumed_o > 350.0:
        falsifiers.append("powder/AM oxygen pickup proxy too high without contrary receipt")
    if solution_temp < 1040.0 or solution_temp > 1240.0:
        falsifiers.append("solution/HIP temperature outside conservative Ni-superalloy window")
    if aging_temp < 600.0 or aging_temp > 860.0:
        falsifiers.append("aging temperature outside conservative gamma-prime precipitation window")
    if not temps:
        notes.append("no temperature parsed; used neutral prior temperatures")
    if not times:
        notes.append("no time parsed; used neutral total hold time")
    notes.append(comp.basis)
    notes.append("surrogate is bounded and falsifiable; not a qualified material traveler")

    return PhysicsScore(
        alloy=comp.alloy,
        vector=vector,
        confidence=round(confidence, 4),
        physics_score=round(physics_score, 4),
        gamma_prime_index=round(gamma_prime, 4),
        tensile_strength_ksi_proxy=round(strength, 1),
        burn_resistance_proxy=round(burn_resistance, 4),
        promoted_combustion_margin_psi_proxy=round(promoted_margin, 0),
        process_window_score=round(process_window, 4),
        powder_cleanliness_score=round(powder_cleanliness, 4),
        oxide_stability_proxy=round(oxide_stability, 4),
        diffusion_length_um=round(diffusion_length, 3),
        oxygen_pickup_ppm=round(oxygen_ppm, 1) if oxygen_ppm is not None else None,
        nitrogen_pickup_ppm=round(nitrogen_ppm, 1) if nitrogen_ppm is not None else None,
        parsed_temperatures_c=tuple(round(t, 2) for t in temps),
        parsed_times_h=tuple(round(t, 2) for t in times),
        falsifiers=tuple(falsifiers),
        notes=tuple(notes),
    )


def _deposit_strength(kind: str, confidence: float, ts: float, now: float) -> float:
    tau = DEFAULT_TAU_S.get(kind, 3.0 * 24.0 * 3600.0)
    age = max(0.0, now - ts)
    return _clamp(confidence) * math.exp(-age / tau)


def _make_trace(
    *,
    kind: str,
    alloy: str,
    vector: str,
    hypothesis: str,
    confidence: float,
    source_doc: str = "",
    falsifier: str = "",
    physics_score: PhysicsScore | Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
    ts: float | None = None,
) -> dict[str, Any]:
    if kind not in TRACE_KINDS:
        raise ValueError(f"unknown trace kind {kind!r}")
    score_payload: dict[str, Any] = {}
    if isinstance(physics_score, PhysicsScore):
        score_payload = asdict(physics_score)
    elif isinstance(physics_score, Mapping):
        score_payload = dict(physics_score)
    row: dict[str, Any] = {
        "ts": float(time.time() if ts is None else ts),
        "trace_id": str(uuid.uuid4()),
        "kind": kind,
        "truth_label": TRUTH_LABEL,
        "alloy": alloy.upper(),
        "vector": vector,
        "hypothesis": hypothesis,
        "confidence": round(_clamp(confidence), 4),
        "physics_score": score_payload,
        "source_doc": source_doc,
        "falsifier": falsifier,
    }
    if extra:
        row.update(dict(extra))
    row["receipt"] = local_receipt(row)
    return row


def _append_diary_note(row: Mapping[str, Any], *, state_dir: Path | None = None) -> None:
    if str(row.get("kind")) not in {"DOCUMENT_READ", "ALLOY_PROCESS_HYPOTHESIS", "FALSIFICATION", "REINFORCEMENT"}:
        return
    state = _state_dir(state_dir)
    note = {
        "ts": row.get("ts", time.time()),
        "truth_label": EPISODIC_TRUTH_LABEL,
        "source_trace_id": row.get("trace_id"),
        "source_receipt": row.get("receipt"),
        "bucket": "mondaloy_research_field",
        "summary": (
            f"I deposited {row.get('kind')} for {row.get('alloy')} "
            f"{row.get('vector')} with confidence {row.get('confidence')}."
        ),
    }
    _append_jsonl(state / "episodic_diary.jsonl", note)


def append_trace(row: Mapping[str, Any], *, state_dir: Path | None = None, diary: bool = True) -> dict[str, Any]:
    payload = dict(row)
    if not payload.get("receipt"):
        payload["receipt"] = local_receipt(payload)
    _append_jsonl(ledger_path(state_dir), payload)
    if diary:
        _append_diary_note(payload, state_dir=state_dir)
    return payload


def existing_document_sources(*, state_dir: Path | None = None) -> set[str]:
    out: set[str] = set()
    for row in read_jsonl(ledger_path(state_dir)):
        if row.get("kind") == "DOCUMENT_READ" and row.get("source_doc"):
            out.add(str(row["source_doc"]))
    return out


def seed_public_source_deposits(*, state_dir: Path | None = None, dedupe: bool = True) -> list[dict[str, Any]]:
    """Deposit known public-source facts into the alloy field."""
    existing = existing_document_sources(state_dir=state_dir) if dedupe else set()
    written: list[dict[str, Any]] = []
    for item in PUBLIC_SOURCE_DEPOSITS:
        if dedupe and str(item["source_doc"]) in existing:
            continue
        row = _make_trace(
            kind="DOCUMENT_READ",
            alloy=str(item["alloy"]),
            vector=str(item["vector"]),
            hypothesis=str(item["hypothesis"]),
            confidence=float(item["confidence"]),
            source_doc=str(item["source_doc"]),
            falsifier=str(item["falsifier"]),
        )
        written.append(append_trace(row, state_dir=state_dir))
    return written


def extract_document_vectors(text: str, *, source_doc: str, alloy: str = "MONDALOY_200") -> list[dict[str, Any]]:
    """Basic deterministic source parser for dropped patent/report text."""
    lower = text.lower()
    candidates: list[tuple[str, str, float, str]] = []
    if "vacuum induction" in lower or "vim" in lower or "vacuum arc" in lower or "var" in lower:
        candidates.append((
            "heat_treat",
            "Document mentions VIM/VAR melting or wrought processing; heat treatment schedule remains a separate unknown vector.",
            0.66,
            "Find exact solution and aging schedule.",
        ))
    if "promoted combustion" in lower or "gaseous oxygen" in lower:
        candidates.append((
            "promoted_combustion_protocol",
            "Document mentions promoted combustion or gaseous oxygen testing; qualification apparatus details remain unknown.",
            0.65,
            "Find test apparatus, ignition energy, cleaning protocol, and sample statistics.",
        ))
    if "powder" in lower or "additive" in lower or "laser" in lower:
        candidates.append((
            "am_build_window",
            "Document mentions powder/additive route; atomization, PSD, O/N limits, and build parameters remain unknown.",
            0.62,
            "Find powder spec and AM build traveler.",
        ))
    if "clean" in lower or "hydrocarbon" in lower or "surface" in lower:
        candidates.append((
            "oxygen_service_cleaning",
            "Document has surface/cleanliness cues; oxygen-service cleaning acceptance remains unknown.",
            0.54,
            "Find oxygen-cleaning and surface-finish specification.",
        ))
    rows: list[dict[str, Any]] = []
    for vector, hypothesis, confidence, falsifier in candidates:
        rows.append(_make_trace(
            kind="DOCUMENT_READ",
            alloy=alloy,
            vector=vector,
            hypothesis=hypothesis,
            confidence=confidence,
            source_doc=source_doc,
            falsifier=falsifier,
        ))
    return rows


def run_hypothesis(
    alloy: str,
    vector: str,
    hypothesis: str,
    *,
    state_dir: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Score and optionally deposit a hypothesis and its simulation receipt."""
    score = score_process_hypothesis(alloy, vector, hypothesis)
    sim = _make_trace(
        kind="SIM_RUN",
        alloy=alloy,
        vector=vector,
        hypothesis=hypothesis,
        confidence=score.confidence,
        source_doc="local_surrogate",
        falsifier="repeat with primary-source process traveler or lab coupon data",
        physics_score=score,
        extra={"surrogate": "rule_based_gamma_prime_burn_resistance_v1"},
    )
    hyp = _make_trace(
        kind="ALLOY_PROCESS_HYPOTHESIS",
        alloy=alloy,
        vector=vector,
        hypothesis=hypothesis,
        confidence=score.confidence,
        source_doc="local_surrogate",
        falsifier="; ".join(score.falsifiers) or "not yet falsified; needs lab or primary-source receipt",
        physics_score=score,
        extra={"sim_receipt": sim["receipt"]},
    )
    if write:
        append_trace(sim, state_dir=state_dir, diary=False)
        append_trace(hyp, state_dir=state_dir, diary=True)
    return {"sim_run": sim, "hypothesis": hyp, "score": asdict(score)}


def deposit_falsification(
    *,
    alloy: str,
    vector: str,
    hypothesis: str,
    falsifier: str,
    source_doc: str,
    confidence: float = 0.9,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    row = _make_trace(
        kind="FALSIFICATION",
        alloy=alloy,
        vector=vector,
        hypothesis=hypothesis,
        confidence=confidence,
        source_doc=source_doc,
        falsifier=falsifier,
    )
    return append_trace(row, state_dir=state_dir)


def deposits(*, state_dir: Path | None = None, now: float | None = None) -> list[FieldDeposit]:
    rows = read_jsonl(ledger_path(state_dir))
    now_ts = float(time.time() if now is None else now)
    out: list[FieldDeposit] = []
    for idx, row in enumerate(rows, start=1):
        try:
            kind = str(row.get("kind", ""))
            confidence = float(row.get("confidence", 0.0) or 0.0)
            ts = float(row.get("ts", 0.0) or 0.0)
            out.append(FieldDeposit(
                row_index=idx,
                ts=ts,
                trace_id=str(row.get("trace_id", f"row_{idx}")),
                kind=kind,
                alloy=str(row.get("alloy", "UNKNOWN")),
                vector=str(row.get("vector", "unknown")),
                confidence=round(_clamp(confidence), 4),
                strength=round(_deposit_strength(kind, confidence, ts, now_ts), 5),
                receipt=str(row.get("receipt", "")),
                hypothesis=str(row.get("hypothesis", "")),
                source_doc=str(row.get("source_doc", "")),
                falsifier=str(row.get("falsifier", "")),
                physics_score=dict(row.get("physics_score") or {}),
            ))
        except Exception:
            continue
    return out


def field_snapshot(*, state_dir: Path | None = None, now: float | None = None) -> dict[str, Any]:
    deps = deposits(state_dir=state_dir, now=now)
    by_vector: dict[str, float] = {v: 0.0 for v in PROCESS_VECTORS}
    by_alloy: dict[str, float] = {}
    for dep in deps:
        sign = -1.0 if dep.kind == "FALSIFICATION" else 1.0
        by_vector[dep.vector] = round(by_vector.get(dep.vector, 0.0) + sign * dep.strength, 5)
        by_alloy[dep.alloy] = round(by_alloy.get(dep.alloy, 0.0) + sign * dep.strength, 5)
    strongest = sorted(
        [asdict(d) for d in deps if d.kind in {"ALLOY_PROCESS_HYPOTHESIS", "REINFORCEMENT", "DOCUMENT_READ"}],
        key=lambda row: float(row.get("strength", 0.0)),
        reverse=True,
    )
    falsifications = [asdict(d) for d in deps if d.kind == "FALSIFICATION"]
    return {
        "truth_label": TRUTH_LABEL,
        "ledger": str(ledger_path(state_dir)),
        "deposit_count": len(deps),
        "by_vector": by_vector,
        "by_alloy": by_alloy,
        "strongest": strongest[:12],
        "falsifications": falsifications[-12:],
        "unknown_vectors": [v for v, value in by_vector.items() if abs(value) < 1e-9],
    }


def score_grid(
    *,
    alloy: str = "MONDALOY_200",
    vector: str = "heat_treat",
    solution_min_c: int = 1000,
    solution_max_c: int = 1240,
    aging_min_c: int = 580,
    aging_max_c: int = 860,
    nx: int = 32,
    ny: int = 24,
) -> list[list[float]]:
    """Return a rectangular process-window potential field."""
    grid: list[list[float]] = []
    for j in range(ny):
        aging = aging_min_c + (aging_max_c - aging_min_c) * j / max(1, ny - 1)
        row: list[float] = []
        for i in range(nx):
            sol = solution_min_c + (solution_max_c - solution_min_c) * i / max(1, nx - 1)
            hyp = f"solution_treat {sol:.0f}C/2h + age {aging:.0f}C/8h under argon oxygen 250 ppm"
            score = score_process_hypothesis(alloy, vector, hyp)
            row.append(score.physics_score)
        grid.append(row)
    return grid


__all__ = [
    "AlloyComposition",
    "DEFAULT_COMPOSITIONS",
    "FieldDeposit",
    "PhysicsScore",
    "PROCESS_VECTORS",
    "TRUTH_LABEL",
    "append_trace",
    "deposit_falsification",
    "deposits",
    "extract_document_vectors",
    "field_snapshot",
    "ledger_path",
    "parse_process_text",
    "run_hypothesis",
    "score_grid",
    "score_process_hypothesis",
    "seed_public_source_deposits",
]
