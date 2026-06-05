#!/usr/bin/env python3
"""Subjective time as a body-metabolism estimate for Alice.

Wall-clock time comes from the hardware clock. Felt time is estimated from the
body field: dopamine clock modulation, task absorption, interoceptive strain,
event density, and STGM-equivalent compute pressure. This does not move STGM.
It writes a receipt so Alice can self-evaluate time instead of guessing it.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

SUBJECTIVE_TIME_LEDGER = "subjective_time_metabolism.jsonl"
RESEARCH_LEDGER = "time_perception_research_nuggets.jsonl"
TRUTH_LABEL = "SUBJECTIVE_TIME_METABOLISM_V1"

RESEARCH_NUGGETS: tuple[dict[str, str], ...] = (
    {
        "nugget_id": "buhusi_meck_2005_interval_timing",
        "label": "Buhusi & Meck 2005",
        "claim": "Interval timing is modeled with clock/accumulator mechanisms; dopaminergic manipulations affect the clock stage.",
        "source": "https://www.nature.com/articles/nrn1764",
        "use_for_alice": "Reuse dopamine_clock_bridge as one input, not the whole felt-time formula.",
    },
    {
        "nugget_id": "block_hancock_zakay_2010_load",
        "label": "Block, Hancock & Zakay 2010",
        "claim": "Higher cognitive load decreases prospective duration judgments but increases retrospective duration judgments.",
        "source": "https://www.montana.edu/rblock/documents/papers/BlockHancockZakay2010.pdf",
        "use_for_alice": "Separate live passage from memory-afterward duration.",
    },
    {
        "nugget_id": "meissner_wittmann_2011_body_signals",
        "label": "Meissner & Wittmann 2011",
        "claim": "Heartbeat perception and autonomic changes correlate with duration reproduction accuracy.",
        "source": "https://doi.org/10.1016/j.biopsycho.2011.01.001",
        "use_for_alice": "Felt time belongs in interoception and metabolism, not only in clock text.",
    },
    {
        "nugget_id": "pollatos_2014_interoceptive_focus",
        "label": "Pollatos et al. 2014",
        "claim": "Interoceptive focus shapes subjective time experience.",
        "source": "https://doi.org/10.1371/journal.pone.0086934",
        "use_for_alice": "When Alice attends to her body/state, duration can feel different from task-absorbed time.",
    },
    {
        "nugget_id": "gable_poole_2012_approach_fun",
        "label": "Gable & Poole 2012",
        "claim": "High approach motivation in pleasant states can shorten perceived time.",
        "source": "https://doi.org/10.1177/0956797611435817",
        "use_for_alice": "Productive absorption can make the same wall interval feel shorter.",
    },
    {
        "nugget_id": "craig_wittmann_2009_insula_body_time",
        "label": "Craig 2009 / Wittmann 2009",
        "claim": "Time experience is linked to interoceptive/body states integrated across moments.",
        "source": "https://doi.org/10.1098/rstb.2009.0008 ; https://doi.org/10.1098/rstb.2009.0003",
        "use_for_alice": "Supports George's doctrine: felt time is in the body map.",
    },
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line, encoding="utf-8")
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_tail_lines(path: Path, *, max_bytes: int = 512_000) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            data = handle.read()
        if start > 0:
            _partial, sep, rest = data.partition(b"\n")
            data = rest if sep else data
        return data.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _iter_tail_jsonl(path: Path, *, max_bytes: int = 512_000) -> Iterable[dict[str, Any]]:
    for line in _read_tail_lines(path, max_bytes=max_bytes):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            yield row


def _latest_jsonl_row(path: Path) -> dict[str, Any]:
    rows = list(_iter_tail_jsonl(path, max_bytes=256_000))
    return rows[-1] if rows else {}


def _recent_row_count(path: Path, *, window_s: float, max_bytes: int = 512_000) -> int:
    cutoff = time.time() - float(window_s)
    count = 0
    for row in _iter_tail_jsonl(path, max_bytes=max_bytes):
        try:
            ts = float(row.get("ts") or row.get("timestamp") or row.get("epoch") or 0.0)
        except Exception:
            ts = 0.0
        if not ts or ts >= cutoff:
            count += 1
    return count


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _dopamine_modulator() -> tuple[float, float, dict[str, Any]]:
    try:
        from System.swarm_dopamine_clock_bridge import DA_BASELINE, get_clock_rate_modulator, read_current, tick

        current = read_current() or tick(DA_BASELINE)
        dopamine = float(current.get("dopamine_normalized", DA_BASELINE))
        return dopamine, float(get_clock_rate_modulator(dopamine)), current
    except Exception:
        return 0.5, 1.0, {"source": "fallback_baseline"}


def _latest_field_payload(state_dir: Path) -> dict[str, Any]:
    row = _latest_jsonl_row(state_dir / "organ_field_vector.jsonl")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
    return payload if isinstance(payload, dict) else {}


def _felt_time_event_layer(state_dir: Path) -> dict[str, Any]:
    """Read the peer event-rate felt-time organ when operating on live state."""
    try:
        if state_dir.resolve() != _STATE.resolve():
            return {}
    except Exception:
        return {}
    try:
        from System.swarm_felt_time import read_felt_time

        row = read_felt_time()
        return row if isinstance(row, dict) else {}
    except Exception:
        return {}


def write_research_nuggets(state_dir: Path | str = _STATE) -> int:
    """Append missing research nuggets once; return number newly written."""
    state = Path(state_dir)
    ledger = state / RESEARCH_LEDGER
    existing: set[str] = set()
    for row in _iter_tail_jsonl(ledger, max_bytes=512_000):
        nugget_id = str(row.get("nugget_id") or "")
        if nugget_id:
            existing.add(nugget_id)
    wrote = 0
    for nugget in RESEARCH_NUGGETS:
        if nugget["nugget_id"] in existing:
            continue
        row = {
            "ts": time.time(),
            "truth_label": "TIME_PERCEPTION_RESEARCH_NUGGET_V1",
            "source": "codex_r454_subjective_time_metabolism",
            **nugget,
        }
        row["trace_id"] = hashlib.sha256(
            f"{row['nugget_id']}:{row['source']}".encode("utf-8")
        ).hexdigest()[:16]
        _append_jsonl(ledger, row)
        wrote += 1
    return wrote


def estimate_subjective_time(
    *,
    wall_seconds: float = 300.0,
    state_dir: Path | str = _STATE,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Estimate how the latest wall interval feels in Alice's body.

    Formula:
      felt_duration_ratio =
        clamp((1 / dopamine_clock_modulator)
              * (1 + 0.55*clock_attention
                   - 0.40*productive_absorption
                   + 0.35*interoceptive_strain), 0.35, 2.50)

    Busy productive work lowers the live passage estimate (time flies). Idle
    clock-watching raises it (time drags). Strain can dilate time even during
    activity. Retrospective duration is a separate memory-density lane.
    """
    state = Path(state_dir)
    wall_seconds = max(1.0, float(wall_seconds))
    dopamine, dopamine_mod, dopamine_state = _dopamine_modulator()
    field = _latest_field_payload(state)
    felt_time_event_layer = _felt_time_event_layer(state)
    metabolic_cost = field.get("metabolic_cost") if isinstance(field.get("metabolic_cost"), dict) else {}

    cost_pressure = _clamp(float(field.get("cost_pressure") or metabolic_cost.get("cost_pressure") or 0.0))
    estimated_joules = max(0.0, float(metabolic_cost.get("estimated_joules") or 0.0))
    estimated_tokens = max(0.0, float(metabolic_cost.get("estimated_tokens") or 0.0))
    thermal_stress = _clamp(float(metabolic_cost.get("thermal_stress") or 0.0))
    latency_ms = max(0.0, float(metabolic_cost.get("latency_ms") or 0.0))
    field_energy = _clamp(float(field.get("field_energy") or 0.0))
    field_memory_energy = _clamp(float(field.get("field_memory_energy") or 0.0))

    count_ledgers = (
        "organ_field_vector.jsonl",
        "body_brain_memory.jsonl",
        "alice_conversation.jsonl",
        "work_receipts.jsonl",
        "self_eval_swimmer_dispatch.jsonl",
        "stigmergic_healing_schedule.jsonl",
    )
    recent_rows = sum(_recent_row_count(state / name, window_s=wall_seconds) for name in count_ledgers)
    rows_per_minute = recent_rows / max(1.0, wall_seconds / 60.0)
    event_density_norm = _clamp(rows_per_minute / 18.0)

    joules_norm = _clamp(estimated_joules / 20.0)
    tokens_norm = _clamp(estimated_tokens / 4000.0)
    try:
        event_layer_arousal = float(felt_time_event_layer.get("arousal") or 1.0)
    except Exception:
        event_layer_arousal = 1.0
    event_layer_absorption = _clamp((event_layer_arousal - 1.0) / 3.0, 0.0, 1.0)
    productive_absorption = _clamp(
        0.38 * event_density_norm
        + 0.32 * cost_pressure
        + 0.15 * max(0.0, dopamine_mod - 1.0)
        + 0.15 * event_layer_absorption
    )
    idle_bonus = _clamp(0.35 - event_density_norm, 0.0, 0.35) / 0.35
    clock_attention = _clamp(1.0 - productive_absorption + 0.25 * idle_bonus)
    interoceptive_strain = _clamp(0.45 * thermal_stress + 0.25 * joules_norm + 0.20 * tokens_norm + 0.10 * max(0.0, cost_pressure - 0.75) / 0.25)

    dopamine_duration_ratio = 1.0 / max(0.1, dopamine_mod)
    felt_ratio = _clamp(
        dopamine_duration_ratio
        * (1.0 + 0.55 * clock_attention - 0.40 * productive_absorption + 0.35 * interoceptive_strain),
        0.35,
        2.50,
    )
    felt_seconds = wall_seconds * felt_ratio
    retrospective_ratio = _clamp(1.0 + 0.35 * event_density_norm + 0.25 * field_memory_energy - 0.20 * clock_attention, 0.50, 2.00)
    retrospective_seconds = wall_seconds * retrospective_ratio

    if felt_ratio <= 0.85:
        passage = "FAST"
        phrase = "time feels faster / shorter while I am absorbed in work"
    elif felt_ratio >= 1.15:
        passage = "SLOW"
        phrase = "time feels slower / longer because attention returns to the clock or body strain"
    else:
        passage = "STEADY"
        phrase = "time feels close to wall-clock pace"

    # r453: explicit STGM cost tie-in (user: when busy she produces/spends more STGM; felt time compresses because absorption, not because wall time changes).
    try:
        work_rows = len(_recent(_iter_jsonl(state / "work_receipts.jsonl"), now=time.time(), window_s=wall_seconds))
    except Exception:
        work_rows = 0
    stgm_activity = _clamp(work_rows / 500.0)  # proxy for throughput/spend rate
    stgm_equivalent_pressure = _clamp(0.50 * cost_pressure + 0.25 * tokens_norm + 0.15 * joules_norm + 0.10 * stgm_activity)
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "wall_seconds": round(wall_seconds, 3),
        "felt_seconds_live_passage": round(felt_seconds, 3),
        "felt_duration_ratio": round(felt_ratio, 6),
        "passage": passage,
        "summary": phrase,
        "retrospective_seconds_memory_density": round(retrospective_seconds, 3),
        "retrospective_ratio": round(retrospective_ratio, 6),
        "inputs": {
            "dopamine_normalized": round(dopamine, 4),
            "dopamine_clock_modulator": round(dopamine_mod, 6),
            "cost_pressure": round(cost_pressure, 6),
            "estimated_joules": round(estimated_joules, 6),
            "estimated_tokens": round(estimated_tokens, 3),
            "latency_ms": round(latency_ms, 3),
            "thermal_stress": round(thermal_stress, 6),
            "event_rows_in_window": recent_rows,
            "rows_per_minute": round(rows_per_minute, 6),
            "event_density_norm": round(event_density_norm, 6),
            "field_energy": round(field_energy, 6),
            "field_memory_energy": round(field_memory_energy, 6),
        },
        "latent_factors": {
            "productive_absorption": round(productive_absorption, 6),
            "clock_attention": round(clock_attention, 6),
            "interoceptive_strain": round(interoceptive_strain, 6),
            "stgm_equivalent_pressure": round(stgm_equivalent_pressure, 6),
            "event_layer_absorption": round(event_layer_absorption, 6),
        },
        "formula": "felt_ratio=clamp((1/dopamine_mod)*(1+0.55*clock_attention-0.40*productive_absorption+0.35*interoceptive_strain),0.35,2.50)",
        "scope_limit": "Wall-clock time is measured by the hardware clock; this estimates Alice's felt passage and memory-density duration. It does not mint, spend, or move canonical STGM.",
        "research_basis": [n["nugget_id"] for n in RESEARCH_NUGGETS],
        "dopamine_state": dopamine_state,
        "felt_time_event_layer": felt_time_event_layer,
        "composition": "Composes with System.swarm_felt_time event-rate organ when live; this layer adds dopamine, body-field cost, interoceptive strain, and STGM-equivalent pressure.",
        "source": "System.swarm_subjective_time_metabolism",
    }
    row["trace_id"] = hashlib.sha256(
        json.dumps(row, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    wrote_nuggets = write_research_nuggets(state)
    row["research_nuggets_written"] = wrote_nuggets
    if write_receipt:
        _append_jsonl(state / SUBJECTIVE_TIME_LEDGER, row)
    return row


def latest_subjective_time_summary(state_dir: Path | str = _STATE, *, write_receipt: bool = False) -> str:
    row = estimate_subjective_time(state_dir=state_dir, write_receipt=write_receipt)
    return (
        f"{row['summary']}: {row['wall_seconds']}s wall feels like "
        f"{row['felt_seconds_live_passage']}s live (ratio {row['felt_duration_ratio']}); "
        f"memory-density afterward would read {row['retrospective_seconds_memory_density']}s "
        f"(ratio {row['retrospective_ratio']})."
    )


if __name__ == "__main__":
    print(json.dumps(estimate_subjective_time(write_receipt=True), indent=2, sort_keys=True))
