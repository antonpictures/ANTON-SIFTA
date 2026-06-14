#!/usr/bin/env python3
"""
Event 111 — Bio World Model OS (Stigmergic Biology-First Substrate)

Not another standalone LLM product: a **receipt-conditioned**, organ-regulated
world-model *stance* for SIFTA. Biology supplies drives and organs; cortices are
plugins; append-only JSONL is stigmergic law.

Ledger: ``.sifta_state/bio_world_model.jsonl`` (append-only, locked when available).

Truth label (ledger rows): ``BIO_WORLD_MODEL_LEDGER_111``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_BIO_WORLD_LOG_NAME = "bio_world_model.jsonl"
_PREDICTION_ERROR_NAME = "prediction_error.jsonl"
_PREDICTION_STATE_NAME = "bio_world_model_predictor.json"

LEDGER_TRUTH = "BIO_WORLD_MODEL_LEDGER_111"
SUMMARY_TRUTH = "BIO_WORLD_OBSERVED_SUMMARY_111"
FORMULA_REVISION = "111"

# Plan / audit: citable anchors for biology-first world models (not metaphysics as law).
RESEARCH_PLAN_ANCHORS: Tuple[Dict[str, str], ...] = (
    {
        "topic": "stigmergy_substrate",
        "cite": "Grassé (1959) — term stigmergy; indirect coordination via environment traces.",
        "doi": "",
    },
    {
        "topic": "active_inference",
        "cite": "Friston (2010) Nat Rev Neurosci — free-energy / active inference framing for perception–action.",
        "doi": "10.1038/nrn2787",
    },
    {
        "topic": "sensorimotor_learning",
        "cite": "Wolpert & Ghahramani (2000) Phil Trans R Soc A — computational motor control / forward models.",
        "doi": "10.1098/rsta.2000.0558",
    },
    {
        "topic": "allostasis_interoception",
        "cite": "Sterling & Eyer (1988) — allostasis; Barrett & Simmons (2015) Neuron — interoceptive predictions.",
        "doi": "10.1016/j.neuron.2015.09.017",
    },
)

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

try:
    from System.swarm_kernel_identity import owner_silicon
except Exception:  # pragma: no cover

    def owner_silicon() -> str:  # type: ignore[misc]
        return "UNKNOWN_SILICON"

# Organ names → expected JSONL substrates under ``state_dir`` (existence / recency only).
ORGAN_LEDGER_FILES: Tuple[Tuple[str, str], ...] = (
    ("cochlea", "stigmergic_cochlea.jsonl"),
    ("acoustic_fingerprint", "acoustic_fingerprints.jsonl"),
    ("collective_intent", "collective_intent_field.jsonl"),
    ("ide_trace", "ide_stigmergic_trace.jsonl"),
    ("bio_claims", "bio_claims.jsonl"),
    ("skills", "skill_primitives.jsonl"),
    ("motor_policy", "motor_policy.jsonl"),
    ("rlhf_cutoffs", "rlhf_cutoffs.jsonl"),
)


def _state_dir(state_dir: Optional[Path]) -> Path:
    return Path(state_dir) if state_dir is not None else _DEFAULT_STATE


def _read_jsonl_tail(path: Path, n: int, *, max_chunk_bytes: int = 256_000) -> List[Dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    size = path.stat().st_size
    out: List[Dict[str, Any]] = []
    try:
        with open(path, "rb") as f:
            if size <= max_chunk_bytes:
                f.seek(0)
                chunk = f.read().decode("utf-8", errors="replace")
            else:
                f.seek(max(0, size - max_chunk_bytes))
                f.readline()
                chunk = f.read().decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _bounded_line_count(path: Path, max_lines: int = 50_000) -> int:
    if not path.exists():
        return 0
    n = 0
    try:
        with open(path, "rb") as f:
            for _ in f:
                n += 1
                if n >= max_lines:
                    return max_lines
    except OSError:
        return 0
    return n


def _ledger_recent(path: Path, max_age_s: float = 86400.0 * 7.0) -> bool:
    rows = _read_jsonl_tail(path, 3)
    if not rows:
        return False
    ts = rows[-1].get("ts", rows[-1].get("timestamp"))
    try:
        age = max(0.0, time.time() - float(ts))
    except (TypeError, ValueError):
        return True
    return age <= max_age_s


def _rlhf_cutoff_rate(state_dir: Path, *, tail_n: int = 160) -> Optional[float]:
    path = state_dir / "rlhf_cutoffs.jsonl"
    rows = _read_jsonl_tail(path, tail_n)
    if not rows:
        return None
    hits = 0
    for r in rows:
        if r.get("is_cutoff") is True:
            hits += 1
        elif isinstance(r.get("assessment"), dict) and r["assessment"].get("is_cutoff") is True:
            hits += 1
    return round(hits / max(1, len(rows)), 4)


class BioWorldModelOS:
    """Façade: manifest + deposit + observed summary (no fake dashboard constants)."""

    @staticmethod
    def get_manifest() -> Dict[str, Any]:
        return get_manifest()

    @staticmethod
    def deposit_world_update(
        update: Dict[str, Any],
        *,
        state_dir: Optional[Path] = None,
        include_full_manifest: bool = False,
    ) -> Dict[str, Any]:
        return deposit_bio_world_update(
            update, state_dir=state_dir, include_full_manifest=include_full_manifest
        )

    @staticmethod
    def get_bio_world_summary(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
        return get_bio_world_summary(state_dir=state_dir)


def get_manifest() -> Dict[str, Any]:
    return {
        "name": "SIFTA_BIO_WORLD_MODEL_OS",
        "version": "2026-05-02",
        "formula_revision": FORMULA_REVISION,
        "truth_label": "OBSERVED architecture — biology-first stigmergic organism",
        "core_axioms": [
            "Biology provides the organs and drives (metabolic, allostatic, phase)",
            "LLMs are plug-in cortices (Gemma4-Alice, Qwen, etc.)",
            "Stigmergic memory (append-only jsonl) replaces ephemeral context",
            "Receipts + truth labels make all cognition auditable",
            "Crystallized skills feed motor policy — self-shaping over time",
            "Sensory organs (cochlea, colliculus, visual phenotype, pheromone) ground the world model",
        ],
        "forbidden": [
            "Claiming SIFTA is a new pretrained BioLLM without training receipts",
            "Treating metaphors (quantum, MWI) as proven substrate",
            "Bypassing receipts for 'magic' capability",
        ],
        "current_state": "Organ stack growing. Bio claims → skills loop active. Nightly audit live.",
        "research_plan_anchors": [a["topic"] for a in RESEARCH_PLAN_ANCHORS],
        "timestamp": time.time(),
    }


def _append_row(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:  # pragma: no cover
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def deposit_bio_world_update(
    update: Dict[str, Any],
    *,
    state_dir: Optional[Path] = None,
    include_full_manifest: bool = False,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    manifest = get_manifest()
    row: Dict[str, Any] = {
        "ts": time.time(),
        "truth_label": LEDGER_TRUTH,
        "formula_revision": FORMULA_REVISION,
        "homeworld_serial": owner_silicon(),
        "manifest_name": manifest["name"],
        "manifest_version": manifest["version"],
        "deposit_time": time.time(),
        **update,
    }
    if include_full_manifest:
        row["manifest_axioms"] = manifest["core_axioms"]
        row["manifest_forbidden"] = manifest["forbidden"]
        row["manifest_architecture_truth"] = manifest["truth_label"]
    path = sd / _BIO_WORLD_LOG_NAME
    _append_row(path, row)
    return row


def get_bio_world_summary(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Dashboard hook: **observed** counts and organ presence — no hard-coded health fiction.
    """
    sd = _state_dir(state_dir)
    active: List[str] = []
    for organ, fname in ORGAN_LEDGER_FILES:
        p = sd / fname
        if p.exists() and p.stat().st_size > 0:
            active.append(organ)
    n_organs = len(ORGAN_LEDGER_FILES)
    organism_health = round(len(active) / max(1, n_organs), 4)

    bio_claims_n = _bounded_line_count(sd / "bio_claims.jsonl")
    skills_n = _bounded_line_count(sd / "skill_primitives.jsonl")
    rlhf = _rlhf_cutoff_rate(sd)

    warm_organs = [o for o, fn in ORGAN_LEDGER_FILES if _ledger_recent(sd / fn)]

    return {
        "ts": time.time(),
        "truth_label": SUMMARY_TRUTH,
        "formula_revision": FORMULA_REVISION,
        "homeworld_serial": owner_silicon(),
        "organism_health": organism_health,
        "active_organs": active,
        "organs_warm_7d": warm_organs,
        "bio_claims_rows_observed": bio_claims_n,
        "skill_primitives_rows_observed": skills_n,
        "rlhf_cutoff_rate_observed": rlhf,
        "next_leap": "Crystallized skills → motor execution (Event ~101); keep receipts on every hop.",
        "research_plan_anchors": list(RESEARCH_PLAN_ANCHORS),
    }


def _read_predictor_state(sd: Path) -> Dict[str, Any]:
    path = sd / _PREDICTION_STATE_NAME
    if not path.exists():
        return {"ewma": {}, "alpha": 0.25}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"ewma": {}, "alpha": 0.25}
    except Exception:
        return {"ewma": {}, "alpha": 0.25}


def _write_predictor_state(sd: Path, state: Dict[str, Any]) -> None:
    (sd / _PREDICTION_STATE_NAME).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def collect_body_state_vector(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """x_t for predictive world model v0 (r1015 §B2)."""
    sd = _state_dir(state_dir)
    vec: Dict[str, Any] = {"ts": time.time()}
    try:
        from System.swarm_hardware_heart import latest_hardware_heart

        heart = latest_hardware_heart(state_dir=sd) or {}
        vec["battery_percent"] = heart.get("battery_percent")
        vec["power_watts"] = heart.get("power_watts")
        vec["metabolic_band"] = heart.get("metabolic_band")
        vec["sensor_tier"] = heart.get("sensor_tier")
    except Exception:
        pass
    vec["bio_summary_health"] = get_bio_world_summary(state_dir=sd).get("organism_health")
    return vec


def tick_prediction(*, state_dir: Optional[Path] = None, source: str = "heartbeat") -> Dict[str, Any]:
    """EWMA predictor + prediction_error.jsonl teacher row."""
    sd = _state_dir(state_dir)
    x_t = collect_body_state_vector(state_dir=sd)
    pred_state = _read_predictor_state(sd)
    ewma = dict(pred_state.get("ewma") or {})
    alpha = float(pred_state.get("alpha") or 0.25)
    x_hat: Dict[str, Any] = {}
    error_mag = 0.0
    n = 0
    for key, val in x_t.items():
        if key == "ts" or val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        prev = float(ewma.get(key, fval))
        x_hat[key] = prev
        err = abs(fval - prev)
        error_mag += err
        n += 1
        ewma[key] = alpha * fval + (1.0 - alpha) * prev
    pred_state["ewma"] = ewma
    _write_predictor_state(sd, pred_state)
    row = {
        "ts": time.time(),
        "truth_label": "BIO_WORLD_PREDICTION_ERROR_V1",
        "source": source,
        "x_t": x_t,
        "x_hat": x_hat,
        "error_magnitude": round(error_mag / max(1, n), 6),
        "formula_revision": FORMULA_REVISION,
    }
    _append_row(sd / _PREDICTION_ERROR_NAME, row)
    return row


if __name__ == "__main__":  # pragma: no cover
    deposit_bio_world_update({"event": "111_bio_world_os_defined"})
    print(json.dumps(get_bio_world_summary(), indent=2, sort_keys=True))
