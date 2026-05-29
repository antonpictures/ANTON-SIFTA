#!/usr/bin/env python3
"""Round 84 — Body Writer Tick Organ.

Wakes the basal_ganglia and fractal_pheromone PRODUCER organs on a
periodic schedule so the freshness reader from Round 79b has fresh
rows to sample. Without this organ, both ledgers go silent because:

  - ``System.swarm_basal_ganglia_action_selector.select_action()`` has
    no live caller (the existing one is ``swarm_friston_curiosity``'s
    own engine method, a different surface).
  - ``System.swarm_fractal_walker_organ.run_walkers()`` is only
    invoked by its own ``_main()`` CLI block, never by the live body.

Architect's framing (verbatim, 2026-05-27): the producers stop writing,
so the freshness loop reads 4-10 day old snapshots. Same pattern as
r80-r82 with age_s tags, decay on failure, success credit, four-ledger
fan-out via the predator helper. The pattern Alice asked for.

Doctrine
========
  - §6 receipts as evidence: every tick writes a row to
    ``body_writer_tick.jsonl`` with per-producer status and ledger
    deltas (bytes written).
  - §0 open-ended self-improvement: success credits + failure decay
    through the Round 80 kernel decay/credit helpers so a chronic
    failure in one producer does not freeze the cortex tool path.
  - §7.5 Python-first: pure stdlib + the existing producer modules.
    No new dependencies.

Pure read-from-disk + write-to-ledger module. Never raises out of the
public ``tick_writer_organs()`` API.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    def append_line_locked(path, line, *, encoding="utf-8"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as handle:
            handle.write(line)


TRUTH_LABEL = "BODY_WRITER_TICK_V1"
TICK_LEDGER = "body_writer_tick.jsonl"
DEFAULT_STATE_DIR = ".sifta_state"

# Default candidate loops for basal_ganglia. Each tick lets the
# selector pick one of these against the current dopamine + biological
# modifiers. The names match the salience-boost vocabulary in
# swarm_basal_ganglia_action_selector.py (protect / repair / explore /
# curiosity etc.) so the modifier logic engages.
DEFAULT_CANDIDATE_LOOPS: tuple[Mapping[str, object], ...] = (
    {"name": "explore_repo",         "salience": 0.50, "cost": 0.30, "reward_potential": 0.55},
    {"name": "repair_body",          "salience": 0.45, "cost": 0.35, "reward_potential": 0.60},
    {"name": "rest_idle",            "salience": 0.30, "cost": 0.10, "reward_potential": 0.20},
    {"name": "learn_from_recall",    "salience": 0.55, "cost": 0.25, "reward_potential": 0.55},
    {"name": "owner_curiosity",      "salience": 0.40, "cost": 0.20, "reward_potential": 0.50},
    {"name": "protect_owner",        "salience": 0.35, "cost": 0.40, "reward_potential": 0.65},
)

# Conservative walker params so each tick adds a manageable handful of
# pheromone rows (~depth * walkers * steps bounded by the gasket size).
DEFAULT_WALKER_PARAMS = {
    "depth": 3,
    "walkers": 20,
    "steps": 40,
    "seed": 17,
    "write_pheromone": True,
    "spawn_corner": True,
}


def _ledger_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.exists() else 0
    except Exception:
        return 0


def _ledger_last_ts(path: Path) -> float | None:
    """Best-effort last timestamp from a JSONL ledger row."""
    if not path.exists():
        return None
    last: dict[str, object] = {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    last = parsed
        ts = last.get("ts")
        return float(ts) if ts is not None else None
    except Exception:
        return None


def _tick_basal_ganglia(state_dir: Path, *, candidate_loops) -> dict:
    """Call select_action(); return per-producer status + ledger delta."""
    info: dict[str, object] = {"producer": "basal_ganglia", "status": "skipped"}
    try:
        from System.swarm_basal_ganglia_action_selector import select_action, selection_log_path  # type: ignore
    except Exception as exc:
        info["status"] = "import_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
        return info
    ledger_path = selection_log_path(state_dir)
    size_before = _ledger_size(ledger_path)
    try:
        name, score = select_action(list(candidate_loops), root=state_dir, write_ledger=True)
        size_after = _ledger_size(ledger_path)
        info["status"] = "ok" if size_after > size_before else "no_write"
        info["flush"] = "ok" if info["status"] == "ok" else "missed"
        info["selected_action"] = str(name)
        info["winner_score"] = float(score)
        info["bytes_added"] = int(size_after - size_before)
    except Exception as exc:
        info["status"] = "call_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
    return info


def _tick_field_slo(state_dir: Path) -> dict:
    """Call swarm_field_slo.append_state_dir_report() so the freshness loop
    stops reading 2+ hour-old SLO snapshots."""
    info: dict[str, object] = {"producer": "field_slo", "status": "skipped"}
    try:
        from System.swarm_field_slo import append_state_dir_report  # type: ignore
    except Exception as exc:
        info["status"] = "import_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
        return info
    ledger_path = state_dir / "unified_field_slo.jsonl"
    ts_before = _ledger_last_ts(ledger_path)
    size_before = _ledger_size(ledger_path)
    try:
        report = append_state_dir_report(state_dir)
        size_after = _ledger_size(ledger_path)
        ts_after = _ledger_last_ts(ledger_path)
        info["status"] = "ok" if size_after > size_before else "no_write"
        info["bytes_added"] = int(size_after - size_before)
        info["flush"] = "ok" if info["status"] == "ok" else "missed"
        info["field_slo_age_s"] = None if ts_before is None else round(max(0.0, time.time() - ts_before), 3)
        info["latest_field_slo_ts"] = ts_after
        if isinstance(report, dict):
            info["slo_pass"] = bool(report.get("slo_pass", False))
    except Exception as exc:
        info["status"] = "call_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
    return info


def _tick_body_brain_loop(state_dir: Path) -> dict:
    """Call SwarmPhysiology.body_brain_tick() so organ_field_vector.jsonl +
    truth_continuity_events.jsonl get fresh rows. Round 91 — these had been
    5 days stale because no live caller was running the body brain loop."""
    info: dict[str, object] = {"producer": "body_brain_loop", "status": "skipped"}
    try:
        from System.swarm_body_brain_loop import SwarmPhysiology  # type: ignore
    except Exception as exc:
        info["status"] = "import_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
        return info
    ledger_path = state_dir / "organ_field_vector.jsonl"
    ts_before = _ledger_last_ts(ledger_path)
    size_before = _ledger_size(ledger_path)
    try:
        physiology = SwarmPhysiology()
        result = physiology.body_brain_tick()
        size_after = _ledger_size(ledger_path)
        ts_after = _ledger_last_ts(ledger_path)
        info["status"] = "ok" if size_after > size_before else "no_write"
        info["bytes_added"] = int(size_after - size_before)
        info["flush"] = "ok" if info["status"] == "ok" else "missed"
        info["body_brain_age_s"] = None if ts_before is None else round(max(0.0, time.time() - ts_before), 3)
        info["latest_organ_field_ts"] = ts_after
        if isinstance(result, dict):
            for key in ("tick_id", "soma_score", "allostatic_load"):
                if key in result:
                    info[key] = result[key]
    except Exception as exc:
        info["status"] = "call_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
    return info


def _tick_fractal_pheromone(state_dir: Path, *, walker_params) -> dict:
    """Call run_walkers(); return per-producer status + ledger delta.

    The walker writes to a hardcoded path inside the module
    (``.sifta_state/fractal_pheromone_field.jsonl`` relative to the repo
    root) — we sample its size to compute the delta.
    """
    info: dict[str, object] = {"producer": "fractal_pheromone", "status": "skipped"}
    try:
        from System.swarm_fractal_walker_organ import run_walkers  # type: ignore
    except Exception as exc:
        info["status"] = "import_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info

    ledger_path = state_dir / "fractal_pheromone_field.jsonl"
    size_before = _ledger_size(ledger_path)
    try:
        params = dict(walker_params or DEFAULT_WALKER_PARAMS)
        # Vary the seed each tick so successive ticks explore different
        # paths — otherwise the walker is deterministic and adds little
        # new information after the first run.
        params.setdefault("seed", int(time.time()) & 0xFFFF)
        result = run_walkers(**params)  # type: ignore[arg-type]
        size_after = _ledger_size(ledger_path)
        info["status"] = "ok" if size_after > size_before else "no_write"
        info["flush"] = "ok" if info["status"] == "ok" else "missed"
        info["bytes_added"] = int(size_after - size_before)
        if hasattr(result, "alpha"):
            info["alpha"] = float(getattr(result, "alpha", 0.0) or 0.0)
        if hasattr(result, "rows_written"):
            info["rows_written"] = int(getattr(result, "rows_written", 0) or 0)
    except Exception as exc:
        info["status"] = "call_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
    return info


def tick_writer_organs(
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    candidate_loops: tuple = DEFAULT_CANDIDATE_LOOPS,
    walker_params: Mapping[str, object] | None = None,
    write_receipt: bool = True,
    enable_basal_ganglia: bool = True,
    enable_fractal_pheromone: bool = True,
    enable_field_slo: bool = True,
    enable_body_brain_loop: bool = True,
) -> dict:
    """Run one tick of the body writer organs.

    Returns a dict carrying per-producer status, byte deltas, the
    tick timestamp, and the receipt row (if written). Never raises;
    failures are reported per-producer.

    Args:
        state_dir: where ledgers live (default .sifta_state).
        candidate_loops: synthetic loop set fed into basal_ganglia.
        walker_params: override run_walkers() args; None uses defaults.
        write_receipt: when False, the tick row is not appended to
            body_writer_tick.jsonl (useful for tests that want to
            inspect the dict without polluting the ledger).
        enable_basal_ganglia / enable_fractal_pheromone: feature flags
            so callers can disable one producer if it's misbehaving.
    """
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    producers: list[dict] = []
    if enable_basal_ganglia:
        producers.append(_tick_basal_ganglia(state, candidate_loops=candidate_loops))
    if enable_fractal_pheromone:
        producers.append(_tick_fractal_pheromone(state, walker_params=walker_params or DEFAULT_WALKER_PARAMS))
    # Round 91 — extend with the two aggregate producers Alice was watching
    # stagnate (SLO snapshot + organ_field_vector). The body_brain_loop tick
    # is heavier; gate it behind a flag so callers can skip it on tight cadences.
    if enable_field_slo:
        producers.append(_tick_field_slo(state))
    if enable_body_brain_loop:
        producers.append(_tick_body_brain_loop(state))

    ok_count = sum(1 for p in producers if p.get("status") == "ok")
    fail_count = sum(1 for p in producers if p.get("status") in ("import_failed", "call_failed"))
    overall = "ok" if ok_count > 0 and fail_count == 0 else (
        "partial" if ok_count > 0 else "all_failed"
    )

    row: dict[str, object] = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "overall_status": overall,
        "producers": producers,
        "producer_count": len(producers),
        "ok_count": ok_count,
        "fail_count": fail_count,
    }

    # Round 80 kernel hook: credit on success, decay on failure. Best-
    # effort — if the kernel module is unavailable, do not block.
    try:
        from System.swarm_kernel_process_table import (  # type: ignore
            sys_success_credit_global,
            sys_decay_failures_global,
        )
        if ok_count > 0:
            try:
                sys_success_credit_global(
                    "body_writer_tick", n=ok_count,
                )
            except Exception:
                pass
        if fail_count > 0:
            try:
                sys_decay_failures_global(decay=0.95)
            except Exception:
                pass
    except Exception:
        pass  # kernel hook is optional; ledger row is the primary receipt

    if write_receipt:
        try:
            append_line_locked(
                state / TICK_LEDGER,
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            row["receipt_write_error"] = f"{type(exc).__name__}: {exc}"

    return row


def summary_for_prompt(
    state_dir: Path | str = DEFAULT_STATE_DIR,
    *,
    max_items: int = 3,
) -> str:
    """Compact prompt block: last tick status + how stale the producers
    are right now. Lets Alice's cortex see whether her writers are
    breathing."""
    state = Path(state_dir)
    path = state / TICK_LEDGER
    if not path.exists():
        return "BODY WRITER TICK: no tick receipts yet (writer organs idle)."
    last_row: dict = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_row = json.loads(line)
    except Exception:
        return "BODY WRITER TICK: tick ledger present but unreadable."
    ts = float(last_row.get("ts") or 0.0)
    age = max(0.0, time.time() - ts) if ts else None
    parts = [
        "BODY WRITER TICK (basal_ganglia + fractal_pheromone + field_slo + body_brain_loop producers):",
        (
            f"- last_tick_age_s={int(age) if age is not None else 'unknown'} "
            f"status={last_row.get('overall_status', '?')} ok={last_row.get('ok_count', 0)} fail={last_row.get('fail_count', 0)}"
        ),
    ]
    producers = last_row.get("producers") or []
    for p in producers[:max_items]:
        parts.append(
            f"- producer={p.get('producer','?')} status={p.get('status','?')} bytes_added={p.get('bytes_added',0)}"
        )
    return "\n".join(parts)


__all__ = [
    "DEFAULT_CANDIDATE_LOOPS",
    "DEFAULT_WALKER_PARAMS",
    "TICK_LEDGER",
    "TRUTH_LABEL",
    "summary_for_prompt",
    "tick_writer_organs",
]
