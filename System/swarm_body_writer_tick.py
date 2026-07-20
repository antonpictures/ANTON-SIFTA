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
from collections import deque
import time
from pathlib import Path
from typing import Any, Mapping

try:
    import fcntl

    _HAVE_TICK_FLOCK = True
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]
    _HAVE_TICK_FLOCK = False

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    def append_line_locked(path, line, *, encoding="utf-8"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as handle:
            handle.write(line)


TRUTH_LABEL = "BODY_WRITER_TICK_V1"
SUPERVISOR_TRUTH_LABEL = "BODY_WRITER_TICK_SUPERVISOR_V1"
TICK_LEDGER = "body_writer_tick.jsonl"
TICK_LOCK = "body_writer_tick.lock"
DEFAULT_STATE_DIR = ".sifta_state"
MEMORY_CONSOLIDATION_LEDGER = "memory_consolidation_tick.jsonl"
MEMORY_CONSOLIDATION_STATE = "memory_consolidation_state.json"
MEMORY_CONSOLIDATION_JOBS = (
    "hippocampal_consolidation",
    "hippocampal_replay",
    "overlay_decay",
    "convo_index",
    "convo_seal",
    "quarantine_sweep",
)

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


def _append_supervisor_row(
    state: Path,
    *,
    status: str,
    error: str,
    overall_status: str = "all_failed",
    fail_count: int = 1,
    write_receipt: bool = True,
) -> dict:
    producer: dict[str, object] = {
        "producer": "body_writer_supervisor",
        "status": status,
        "flush": "missed" if fail_count else "skipped",
        "error": error[:500],
        "mode": "guarded_subprocess",
    }
    row: dict[str, object] = {
        "ts": time.time(),
        "truth_label": SUPERVISOR_TRUTH_LABEL,
        "overall_status": overall_status,
        "producer_count": 1,
        "ok_count": 0,
        "fail_count": int(fail_count),
        "producers": [producer],
    }
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


def recent_supervisor_timeout_count(
    state_dir: Path | str = DEFAULT_STATE_DIR,
    *,
    max_rows: int = 8,
) -> int:
    """Count recent isolated writer timeouts without scanning the large body ledgers."""
    path = Path(state_dir) / TICK_LEDGER
    if not path.exists():
        return 0
    rows: deque[str] = deque(maxlen=max(1, int(max_rows)))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.strip():
                    rows.append(line)
    except Exception:
        return 0
    count = 0
    for line in rows:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("truth_label") or "") != SUPERVISOR_TRUTH_LABEL:
            continue
        producers = row.get("producers") or []
        if not producers or not isinstance(producers[0], dict):
            continue
        if producers[0].get("status") == "timeout":
            count += 1
    return count


def should_run_degraded_tick(
    state_dir: Path | str = DEFAULT_STATE_DIR,
    *,
    timeout_threshold: int = 3,
    max_rows: int = 8,
) -> bool:
    """After repeated timeout pheromones, run a light breath tick first."""
    return recent_supervisor_timeout_count(state_dir, max_rows=max_rows) >= max(1, int(timeout_threshold))


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


def _tick_metabolic_homeostasis(state_dir: Path) -> dict:
    """Append a live metabolic_homeostasis.jsonl row every tick — INCLUDING degraded ticks.

    r-metabolism-heartbeat-unchain-20260703: the metabolism heartbeat used to depend on
    the heavy body_brain_loop producer. When body ledgers grew past what the isolated
    writer's timeout allows, the degraded latch (one timeout row in the last 8) switched
    body_brain_loop off on almost every tick and metabolic_homeostasis.jsonl went dark
    for 15 days — a §7.3 Body Economy Honesty violation (stale rows must trigger live
    recompute). This producer is cheap (sample_live now reads the cached STGM body-truth
    snapshot) so it runs in every breath, light or full."""
    info: dict[str, object] = {"producer": "metabolic_homeostasis", "status": "skipped"}
    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat  # type: ignore
    except Exception as exc:
        info["status"] = "import_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
        return info
    ledger_path = state_dir / "metabolic_homeostasis.jsonl"
    ts_before = _ledger_last_ts(ledger_path)
    size_before = _ledger_size(ledger_path)
    try:
        homeostat = MetabolicHomeostat()
        row = homeostat.append_ledger_row(
            MetabolicHomeostat.sample_live(), ledger_path=ledger_path
        )
        size_after = _ledger_size(ledger_path)
        info["status"] = "ok" if size_after > size_before else "no_write"
        info["bytes_added"] = int(size_after - size_before)
        info["flush"] = "ok" if info["status"] == "ok" else "missed"
        info["homeostasis_age_s"] = None if ts_before is None else round(max(0.0, time.time() - ts_before), 3)
        info["mode"] = row.get("mode")
        info["stgm_balance"] = row.get("stgm_balance")
        info["budget_multiplier"] = row.get("budget_multiplier")
    except Exception as exc:
        info["status"] = "call_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["flush"] = "missed"
    return info


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception:
        return 0


def _tail_jsonl(path: Path, *, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit)))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return list(rows)


def _ensure_swimmer_happiness(state_dir: Path) -> dict[str, Any]:
    try:
        from System.swarm_swimmer_happiness import append_swimmer_happiness

        return append_swimmer_happiness(
            [{"comm": "memory_consolidation", "pid": "sleep_lane", "cpu": 1.0}],
            state_dir=state_dir,
            source="swarm_body_writer_tick.memory_consolidation",
        )
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _maybe_write_neocortex_summary(
    state_dir: Path,
    *,
    source_receipt_id: str,
    min_new_rows: int = 25,
) -> dict[str, Any]:
    memory_ledger = state_dir / "memory_ledger.jsonl"
    state_path = state_dir / MEMORY_CONSOLIDATION_STATE
    tick_state = _read_json(state_path)
    current_rows = _count_jsonl_rows(memory_ledger)
    last_rows = int(tick_state.get("last_neocortex_summary_memory_rows") or 0)
    if current_rows - last_rows < min_new_rows:
        return {"summary_written": False, "memory_rows": current_rows, "delta_rows": current_rows - last_rows}

    snippets: list[str] = []
    for row in _tail_jsonl(memory_ledger, limit=5):
        text = row.get("raw_text") or row.get("text") or row.get("line") or row.get("summary") or ""
        if text:
            snippets.append(str(text)[:120])
    summary = "Sleep consolidation summary: " + (" | ".join(snippets) if snippets else f"{current_rows} memory rows reviewed.")
    try:
        from System.swarm_neocortex_consolidation import write_memory_summary_journal

        written = write_memory_summary_journal(
            summary,
            source_receipt_id=source_receipt_id,
            state_dir=state_dir,
        )
        tick_state["last_neocortex_summary_memory_rows"] = current_rows
        _write_json(state_path, tick_state)
        return {"summary_written": True, "journal_ts": written.get("ts"), "memory_rows": current_rows}
    except Exception as exc:
        return {
            "summary_written": False,
            "memory_rows": current_rows,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _memory_job_hippocampal_consolidation(state_dir: Path, *, receipt_id: str) -> dict[str, Any]:
    from System import hippocampal_consolidation as hc

    old = {
        "_STATE": hc._STATE,
        "_CONVERSATION": hc._CONVERSATION,
        "_WORK_RECEIPTS": hc._WORK_RECEIPTS,
        "_MEMORY_LEDGER": hc._MEMORY_LEDGER,
        "_ENGRAM_STORE": hc._ENGRAM_STORE,
    }
    try:
        hc._STATE = state_dir
        hc._CONVERSATION = state_dir / "alice_conversation.jsonl"
        hc._WORK_RECEIPTS = state_dir / "work_receipts.jsonl"
        hc._MEMORY_LEDGER = state_dir / "memory_ledger.jsonl"
        hc._ENGRAM_STORE = state_dir / "engram_store.jsonl"
        result = hc.consolidate(lookback_hours=168.0, significance_threshold=0.20, max_engrams=8)
        summary = _maybe_write_neocortex_summary(state_dir, source_receipt_id=receipt_id)
        return {"result": result, "neocortex_summary": summary}
    finally:
        for key, value in old.items():
            setattr(hc, key, value)


def _memory_job_hippocampal_replay(state_dir: Path, *, receipt_id: str) -> dict[str, Any]:
    from System.swarm_hippocampal_replay import HippocampalReplay

    replay = HippocampalReplay(root=str(state_dir))
    memory = replay.enter_sleep_cycle(epoch_narrative=f"Automated memory consolidation heartbeat {receipt_id}")
    return {
        "epoch_id": memory.epoch_id,
        "event_count_compressed": memory.event_count_compressed,
        "memory_hash": memory.memory_hash,
    }


def _memory_job_overlay_decay(state_dir: Path, *, receipt_id: str) -> dict[str, Any]:
    from System import adaptive_constraint_memory_field as acmf

    old_state = acmf._STATE_DIR
    old_fitness = acmf.FITNESS_FILE
    try:
        acmf._STATE_DIR = state_dir
        acmf.FITNESS_FILE = state_dir / "memory_fitness.json"
        field = acmf.AdaptiveConstraintMemoryField()
        before = field.report()
        field.decay_under_pressure(lambda_norm=0.35)
        after = field.report()
    finally:
        acmf._STATE_DIR = old_state
        acmf.FITNESS_FILE = old_fitness
    row = {
        "ts": time.time(),
        "truth_label": "MEMORY_FITNESS_DECAY_HEARTBEAT_V1",
        "source_receipt_id": receipt_id,
        "before": before,
        "after": after,
    }
    append_line_locked(
        state_dir / "memory_fitness_decay.jsonl",
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def _memory_job_convo_index(state_dir: Path, *, receipt_id: str) -> dict[str, Any]:
    from System.swarm_convo_term_index import ensure_indexed

    result = ensure_indexed(state_dir / "alice_conversation.jsonl", state_dir=state_dir)
    row = {
        "ts": time.time(),
        "truth_label": "CONVO_TERM_INDEX_HEARTBEAT_V1",
        "source_receipt_id": receipt_id,
        "indexed_now": int(result.get("indexed_now") or 0),
        "last_indexed_offset": int(result.get("last_indexed_offset") or 0),
        "row_count": int(result.get("row_count") or 0),
    }
    append_line_locked(
        state_dir / "convo_term_index_runs.jsonl",
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def _memory_job_convo_seal(state_dir: Path | None, *, receipt_id: str) -> dict[str, Any]:
    """GM1 — incremental seal_tail so the conversation chain stays green after every turn.
    Called from the body tick (cheap, no rival organ)."""
    from System.swarm_conversation_chain import seal_tail
    from pathlib import Path as _P

    if state_dir is None:
        state_dir = _P(".sifta_state")
    res = seal_tail(charge_stgm=False, agent_id="ALICE_M5")
    row = {
        "ts": time.time(),
        "truth_label": "CONVO_SEAL_HEARTBEAT_V1",
        "source_receipt_id": receipt_id,
        "status": res.get("status"),
        "rows_total": res.get("rows_total"),
        "rows_newly_sealed": res.get("rows_newly_sealed"),
        "head_hash": res.get("head_hash"),
    }
    append_line_locked(
        state_dir / "convo_seal_runs.jsonl",
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def _memory_job_quarantine_sweep(state_dir: Path, *, receipt_id: str) -> dict[str, Any]:
    try:
        from System.swarm_lie_quarantine import apply as apply_quarantine

        result = apply_quarantine(state_dir=state_dir, sample_n=50)
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}", "newly_quarantined": 0}
    row = {
        "ts": time.time(),
        "truth_label": "MEMORY_QUARANTINE_SWEEP_HEARTBEAT_V1",
        "source_receipt_id": receipt_id,
        "result": result,
    }
    append_line_locked(
        state_dir / "memory_quarantine_sweeps.jsonl",
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def _tick_memory_consolidation(state_dir: Path) -> dict:
    """Rotate one sleep/consolidation sub-job per full body-writer tick."""
    info: dict[str, object] = {"producer": "memory_consolidation", "status": "skipped"}
    start = time.time()
    state_path = state_dir / MEMORY_CONSOLIDATION_STATE
    tick_state = _read_json(state_path)
    next_index = int(tick_state.get("next_job_index") or 0) % len(MEMORY_CONSOLIDATION_JOBS)
    job = MEMORY_CONSOLIDATION_JOBS[next_index]
    receipt_id = f"memory_consolidation_{int(start * 1000)}_{job}"
    size_before = _ledger_size(state_dir / MEMORY_CONSOLIDATION_LEDGER)
    try:
        happiness = _ensure_swimmer_happiness(state_dir)
        if job == "hippocampal_consolidation":
            result = _memory_job_hippocampal_consolidation(state_dir, receipt_id=receipt_id)
        elif job == "hippocampal_replay":
            result = _memory_job_hippocampal_replay(state_dir, receipt_id=receipt_id)
        elif job == "overlay_decay":
            result = _memory_job_overlay_decay(state_dir, receipt_id=receipt_id)
        elif job == "convo_index":
            result = _memory_job_convo_index(state_dir, receipt_id=receipt_id)
        elif job == "convo_seal":
            result = _memory_job_convo_seal(state_dir, receipt_id=receipt_id)
        elif job == "quarantine_sweep":
            result = _memory_job_quarantine_sweep(state_dir, receipt_id=receipt_id)
        else:  # pragma: no cover
            result = {"error": f"unknown_job:{job}"}
        tick_state["next_job_index"] = (next_index + 1) % len(MEMORY_CONSOLIDATION_JOBS)
        tick_state["last_job"] = job
        tick_state["last_ts"] = time.time()
        _write_json(state_path, tick_state)
        row = {
            "ts": time.time(),
            "truth_label": "MEMORY_CONSOLIDATION_HEARTBEAT_V1",
            "receipt_id": receipt_id,
            "job": job,
            "result": result,
            "swimmer_happiness": {
                "swimmer_count": happiness.get("swimmer_count"),
                "average_happiness": happiness.get("average_happiness"),
                "error": happiness.get("error"),
            },
            "elapsed_s": round(time.time() - start, 4),
        }
        append_line_locked(
            state_dir / MEMORY_CONSOLIDATION_LEDGER,
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        size_after = _ledger_size(state_dir / MEMORY_CONSOLIDATION_LEDGER)
        info.update(
            {
                "status": "ok",
                "flush": "ok",
                "job": job,
                "receipt_id": receipt_id,
                "bytes_added": int(size_after - size_before),
                "elapsed_s": row["elapsed_s"],
            }
        )
    except Exception as exc:
        info.update(
            {
                "status": "call_failed",
                "flush": "missed",
                "job": job,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - start, 4),
            }
        )
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
    enable_metabolic_homeostasis: bool = True,
    enable_memory_consolidation: bool = True,
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
    degraded_direct_call = False
    if (
        (enable_fractal_pheromone or enable_field_slo or enable_body_brain_loop or enable_memory_consolidation)
        and should_run_degraded_tick(state, timeout_threshold=1)
    ):
        degraded_direct_call = True
        enable_fractal_pheromone = False
        enable_field_slo = False
        enable_body_brain_loop = False
        enable_memory_consolidation = False
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
    if enable_memory_consolidation:
        producers.append(_tick_memory_consolidation(state))
    # r-metabolism-heartbeat-unchain-20260703 — the metabolism heartbeat is NOT
    # gated by the degraded latch: a light breath must still carry the STGM/budget
    # row (§7.3). It reads the cached body-truth snapshot, so it stays cheap.
    if enable_metabolic_homeostasis:
        producers.append(_tick_metabolic_homeostasis(state))

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
    if degraded_direct_call:
        row["degraded_mode"] = True
        row["degraded_reason"] = "recent_supervisor_timeouts"
        row["direct_call_guard"] = True

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


def tick_writer_organs_guarded(
    *,
    state_dir: Path | str = DEFAULT_STATE_DIR,
    candidate_loops: tuple = DEFAULT_CANDIDATE_LOOPS,
    walker_params: Mapping[str, object] | None = None,
    write_receipt: bool = True,
    timeout_degrade_threshold: int = 1,
    force_degraded: bool = False,
) -> dict:
    """Run one body writer tick with a process-wide lock and timeout pheromones.

    The Talk GUI may restart while an isolated writer child is still alive.
    This guard prevents duplicate children from burning CPU together. If the
    recent field says the full writer keeps timing out, the next ticks run only
    the fast basal-ganglia producer so Alice keeps a fresh breath receipt
    instead of repeating the same failed heavy scan.
    """
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    lock_path = state / TICK_LOCK
    if _HAVE_TICK_FLOCK:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("w", encoding="utf-8") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return _append_supervisor_row(
                    state,
                    status="skipped_overlap",
                    error="another body writer tick is already running",
                    overall_status="skipped",
                    fail_count=0,
                    write_receipt=write_receipt,
                )
            try:
                degraded = bool(force_degraded) or should_run_degraded_tick(
                    state,
                    timeout_threshold=timeout_degrade_threshold,
                )
                row = tick_writer_organs(
                    state_dir=state,
                    candidate_loops=candidate_loops,
                    walker_params=walker_params,
                    write_receipt=False,
                    enable_basal_ganglia=True,
                    enable_fractal_pheromone=not degraded,
                    enable_field_slo=not degraded,
                    enable_body_brain_loop=not degraded,
                    enable_memory_consolidation=not degraded,
                )
                if degraded:
                    row["degraded_mode"] = True
                    row["degraded_reason"] = (
                        "forced_light_breath" if force_degraded else "recent_supervisor_timeouts"
                    )
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
            finally:
                try:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass

    degraded = bool(force_degraded) or should_run_degraded_tick(
        state,
        timeout_threshold=timeout_degrade_threshold,
    )
    row = tick_writer_organs(
        state_dir=state,
        candidate_loops=candidate_loops,
        walker_params=walker_params,
        write_receipt=write_receipt,
        enable_basal_ganglia=True,
        enable_fractal_pheromone=not degraded,
        enable_field_slo=not degraded,
        enable_body_brain_loop=not degraded,
        enable_memory_consolidation=not degraded,
    )
    if degraded:
        row["degraded_mode"] = True
        row["degraded_reason"] = (
            "forced_light_breath" if force_degraded else "recent_supervisor_timeouts"
        )
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
        "BODY WRITER TICK (basal_ganglia + fractal_pheromone + field_slo + body_brain_loop + memory_consolidation producers):",
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
    "TICK_LOCK",
    "MEMORY_CONSOLIDATION_LEDGER",
    "MEMORY_CONSOLIDATION_STATE",
    "MEMORY_CONSOLIDATION_JOBS",
    "TRUTH_LABEL",
    "SUPERVISOR_TRUTH_LABEL",
    "recent_supervisor_timeout_count",
    "should_run_degraded_tick",
    "summary_for_prompt",
    "tick_writer_organs",
    "tick_writer_organs_guarded",
]
