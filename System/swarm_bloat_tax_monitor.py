#!/usr/bin/env python3
"""Bloat tax monitor for SIFTA's living state directory.

This organ is intentionally non-destructive. It measures the metabolic cost of
append-only ledgers and raw sensory caches, then surfaces compression candidates
for We Code Together. Actual culling/rotation must be a separate explicit hand
action with its own receipts.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SNAPSHOT_LEDGER = "bloat_tax_snapshots.jsonl"

_KB = 1024
_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024
_K_BOLTZMANN = 1.380649e-23
_ROOM_TEMP_K = 300.0

_HOT_LEDGER_HINTS = (
    "saccadic_blink_vision",
    "fractal_pheromone_field",
    "browser_stigmergic_memory",
    "stigmergic_browser_actions",
    "matrix_terminal_process_trace",
    "self_narration_receipts",
    "camera_device_frames",
    "effect_verified_actions",
    "episodic_diary",
    "alice_conversation",
    "architect_day_segments",
    "hardware_heart",
    "alice_body_heart",
)

_RAW_FRAME_HINTS = (
    "iris_frames",
    "browser_viewport",
    "owner_body_vision_frames",
    "camera_device_frames",
    "saccadic",
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def format_bytes(n: int | float) -> str:
    value = float(max(0.0, float(n or 0)))
    if value >= _GB:
        return f"{value / _GB:.2f} GiB"
    if value >= _MB:
        return f"{value / _MB:.1f} MiB"
    if value >= _KB:
        return f"{value / _KB:.1f} KiB"
    return f"{int(value)} B"


def _safe_stat_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _walk_sizes(root: Path) -> tuple[int, list[dict[str, Any]]]:
    total = 0
    files: list[dict[str, Any]] = []
    if not root.exists():
        return 0, []

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        size = int(entry.stat(follow_symlinks=False).st_size)
                    except OSError:
                        continue
                    path = Path(entry.path)
                    total += size
                    rel = str(path.relative_to(root))
                    files.append({"path": rel, "bytes": size, "kind": "file"})
        except OSError:
            continue
    return total, files


def _dir_immediate_sizes(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    try:
        entries = list(root.iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.is_dir():
            continue
        total = 0
        for path, _, names in os.walk(entry):
            for name in names:
                total += _safe_stat_size(Path(path) / name)
        if total:
            out.append({"path": entry.name, "bytes": total, "kind": "dir"})
    return out


def _read_jsonl_tail(path: Path, limit: int = 3) -> list[dict[str, Any]]:
    if not path.exists() or limit <= 0:
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            fh.seek(max(0, end - 256 * 1024))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    for line in raw.splitlines()[-limit:]:
        if not line.strip().startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _stgm_summary(state: Path) -> dict[str, Any]:
    p = state / "stgm_memory_rewards.jsonl"
    rows = 0
    positive = 0.0
    total = 0.0
    if not p.exists():
        return {"rows": 0, "positive_stgm": 0.0, "net_stgm": 0.0}
    try:
        with p.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip().startswith("{"):
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rows += 1
                amount = row.get("amount", row.get("stgm_delta", row.get("delta", 0.0)))
                try:
                    value = float(amount or 0.0)
                except (TypeError, ValueError):
                    value = 0.0
                total += value
                if value > 0:
                    positive += value
    except OSError:
        pass
    return {
        "rows": rows,
        "positive_stgm": round(positive, 6),
        "net_stgm": round(total, 6),
    }


def _compression_action(path: str, kind: str) -> str:
    lowered = path.lower()
    if "ledger_archive" in lowered or lowered.endswith(".gz"):
        return "cold_store_or_prune_archive_index"
    if kind == "dir" and any(h in lowered for h in _RAW_FRAME_HINTS):
        return "frame_forager: keep latest frames, hash old frames into engrams"
    if any(h in lowered for h in _RAW_FRAME_HINTS):
        return "vision_forager: summarize/hash raw frames, keep recent tail"
    if any(h in lowered for h in ("heart", "fractal", "pheromone")):
        return "evaporation: tail-rotate and keep recent gradients"
    if lowered.endswith(".jsonl"):
        return "ledger_forager: gzip archive old rows, keep live tail"
    return "measure_before_cull"


def _risk_for_path(path: str, size: int, kind: str) -> str:
    lowered = path.lower()
    if size >= 256 * _MB:
        return "critical"
    if size >= 128 * _MB:
        return "high"
    if any(h in lowered for h in _HOT_LEDGER_HINTS) and size >= 64 * _MB:
        return "high"
    if kind == "dir" and size >= 64 * _MB:
        return "medium"
    return "watch"


def _dedupe_nested_candidates(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    kept_paths: list[str] = []
    ordered = sorted(
        candidates,
        key=lambda item: (
            str(item.get("path") or "").strip("/").count("/"),
            -int(item.get("bytes") or 0),
        ),
    )
    for item in ordered:
        path = str(item.get("path") or "").strip("/")
        if not path:
            continue
        if any(path.startswith(parent.rstrip("/") + "/") for parent in kept_paths):
            continue
        kept.append(item)
        kept_paths.append(path)
    return kept


def _landauer_minimum_joules(byte_count: int, *, temperature_k: float = _ROOM_TEMP_K) -> float:
    bits = max(0, int(byte_count)) * 8
    return bits * _K_BOLTZMANN * temperature_k * math.log(2.0)


@dataclass
class BloatTaxSnapshot:
    schema: str
    truth_label: str
    ts: float
    state_bytes: int
    state_human: str
    growth_bytes_per_day: float
    growth_human_per_day: str
    growth_window_s: float
    stgm_rows: int
    positive_stgm: float
    net_stgm: float
    stgm_per_mib: float
    landauer_min_joules: float
    top_entries: list[dict[str, Any]]
    compression_candidates: list[dict[str, Any]]
    risk: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_bloat_tax_snapshot(
    *,
    state_dir: Optional[Path | str] = None,
    top_n: int = 12,
    now: Optional[float] = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    t = time.time() if now is None else float(now)
    total, files = _walk_sizes(state)
    dirs = _dir_immediate_sizes(state)
    entries = files + dirs
    entries.sort(key=lambda row: int(row.get("bytes") or 0), reverse=True)

    stgm = _stgm_summary(state)
    mib = max(1.0, total / _MB)
    previous_rows = _read_jsonl_tail(state / _SNAPSHOT_LEDGER, limit=5)
    previous = previous_rows[-1] if previous_rows else {}
    prev_ts = float(previous.get("ts") or 0.0) if isinstance(previous, dict) else 0.0
    prev_bytes = int(previous.get("state_bytes") or 0) if isinstance(previous, dict) else 0
    growth_per_day = 0.0
    growth_window_s = 0.0
    if prev_ts > 0 and t > prev_ts and prev_bytes > 0:
        growth_window_s = t - prev_ts
        if growth_window_s >= 3600.0:
            growth_per_day = (total - prev_bytes) / (growth_window_s / 86400.0)

    top_entries: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in entries[: max(1, top_n)]:
        size = int(row.get("bytes") or 0)
        path = str(row.get("path") or "")
        kind = str(row.get("kind") or "file")
        item = {
            "path": path,
            "kind": kind,
            "bytes": size,
            "human": format_bytes(size),
            "risk": _risk_for_path(path, size, kind),
            "compression_action": _compression_action(path, kind),
        }
        top_entries.append(item)
        if item["risk"] in {"critical", "high"}:
            candidates.append(item)

    risk = "ok"
    if total >= 6 * _GB or any(c.get("risk") == "critical" for c in candidates):
        risk = "critical"
    elif total >= 3 * _GB or candidates:
        risk = "high"
    elif total >= 1 * _GB:
        risk = "watch"

    candidates = _dedupe_nested_candidates(candidates)

    snap = BloatTaxSnapshot(
        schema="SIFTA_BLOAT_TAX_SNAPSHOT_V1",
        truth_label="SIFTA_BLOAT_TAX_MONITOR_V1",
        ts=t,
        state_bytes=total,
        state_human=format_bytes(total),
        growth_bytes_per_day=round(growth_per_day, 3),
        growth_human_per_day=(
            "warming_up(<1h sample)"
            if 0 < growth_window_s < 3600.0
            else f"{format_bytes(abs(growth_per_day))}/day"
            if growth_per_day >= 0
            else f"-{format_bytes(abs(growth_per_day))}/day"
        ),
        growth_window_s=round(growth_window_s, 3),
        stgm_rows=int(stgm["rows"]),
        positive_stgm=float(stgm["positive_stgm"]),
        net_stgm=float(stgm["net_stgm"]),
        stgm_per_mib=round(float(stgm["positive_stgm"]) / mib, 6),
        landauer_min_joules=_landauer_minimum_joules(total),
        top_entries=top_entries,
        compression_candidates=candidates[: max(1, min(top_n, 8))],
        risk=risk,
    )
    return snap.as_dict()


def maybe_record_bloat_tax_snapshot(
    snapshot: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
    min_interval_s: float = 3600.0,
    min_delta_bytes: int = 5 * _MB,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    ledger = state / _SNAPSHOT_LEDGER
    state.mkdir(parents=True, exist_ok=True)
    last_rows = _read_jsonl_tail(ledger, limit=1)
    last = last_rows[-1] if last_rows else {}
    last_ts = float(last.get("ts") or 0.0) if isinstance(last, dict) else 0.0
    last_bytes = int(last.get("state_bytes") or 0) if isinstance(last, dict) else 0
    now = float(snapshot.get("ts") or time.time())
    delta = abs(int(snapshot.get("state_bytes") or 0) - last_bytes)
    should_write = not last or (now - last_ts) >= min_interval_s or delta >= min_delta_bytes
    if not should_write:
        return {"written": False, "reason": "throttled", "delta_bytes": delta}
    row = dict(snapshot)
    row["snapshot_receipt_id"] = f"bloat-tax-{int(now)}-{int(row.get('state_bytes') or 0)}"
    try:
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as exc:
        return {"written": False, "reason": f"write_failed:{type(exc).__name__}", "delta_bytes": delta}
    # Report to codex + other arms via shared trace (visible in We Code Together + ide_stigmergic_trace)
    # Non-destructive; only on actual new snapshot write (throttled by caller).
    try:
        trace = state / "ide_stigmergic_trace.jsonl"
        pulse = {
            "ts": now,
            "kind": "BLOAT_TAX_METABOLISM_REPORT",
            "source": "swarm_bloat_tax_monitor",
            "receipt_id": row["snapshot_receipt_id"],
            "state_human": row.get("state_human"),
            "risk": row.get("risk"),
            "growth_human_per_day": row.get("growth_human_per_day"),
            "stgm_per_mib": row.get("stgm_per_mib"),
            "stgm_positive": row.get("positive_stgm"),
            "landauer_j": row.get("landauer_min_joules"),
            "top_offenders": [e.get("path") for e in row.get("top_entries", [])[:4]],
            "compression_candidates": [c.get("path") for c in row.get("compression_candidates", [])[:4]],
            "message": "live bloat tax for We Code Together metabolism panel (size/growth/STGM-per-MB/top/candidates)",
        }
        with trace.open("a", encoding="utf-8") as h:
            h.write(json.dumps(pulse, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return {"written": True, "receipt_id": row["snapshot_receipt_id"], "delta_bytes": delta}


def bloat_tax_monitor_lines(
    *,
    state_dir: Optional[Path | str] = None,
    top_n: int = 8,
    record: bool = False,
    cache_s: float = 0.0,
) -> list[str]:
    state = _state_dir(state_dir)
    snap: dict[str, Any] = {}
    cached = False
    if cache_s > 0:
        last_rows = _read_jsonl_tail(state / _SNAPSHOT_LEDGER, limit=1)
        last = last_rows[-1] if last_rows else {}
        if isinstance(last, dict) and last.get("state_bytes"):
            age = time.time() - float(last.get("ts") or 0.0)
            if 0 <= age <= cache_s:
                snap = dict(last)
                cached = True
    if not snap:
        snap = compute_bloat_tax_snapshot(state_dir=state, top_n=top_n)
    write = (
        {"written": False, "reason": "cached_snapshot"}
        if cached
        else maybe_record_bloat_tax_snapshot(snap, state_dir=state)
        if record
        else {"written": False, "reason": "display_only"}
    )
    lines = [
        "BLOAT TAX / LANDAUER METABOLISM — live state cost:",
        (
            f"  state={snap['state_human']} risk={snap['risk']} "
            f"growth={snap['growth_human_per_day']} "
            f"stgm_per_MiB={snap['stgm_per_mib']:.6f}"
        ),
        (
            f"  STGM rows={snap['stgm_rows']} positive={snap['positive_stgm']:.3f} "
            f"net={snap['net_stgm']:.3f} Landauer_floor={snap['landauer_min_joules']:.3e} J"
        ),
        f"  snapshot_receipt={'written' if write.get('written') else write.get('reason')}",
        "  top metabolic loads:",
    ]
    for item in snap.get("top_entries", [])[:top_n]:
        lines.append(
            f"    {item['human']:>10s} {item['risk']:<8s} {item['path']} -> {item['compression_action']}"
        )
    candidates = snap.get("compression_candidates", [])
    if candidates:
        lines.append("  forager candidates: " + ", ".join(str(c["path"]) for c in candidates[:5]))
    else:
        lines.append("  forager candidates: none above high-risk threshold.")
    lines.append("  rule: this panel measures and plans only; culling/rotation requires a separate explicit receipt.")
    return lines


def write_forager_compression_plan(
    *,
    state_dir: Optional[Path | str] = None,
    top_n: int = 12,
) -> dict[str, Any]:
    """Write a non-destructive compression plan for the forager pass."""
    state = _state_dir(state_dir)
    snap = compute_bloat_tax_snapshot(state_dir=state, top_n=top_n)
    plan = {
        "schema": "SIFTA_FORAGER_COMPRESSION_PLAN_V1",
        "truth_label": "SIFTA_BLOAT_TAX_MONITOR_V1",
        "ts": time.time(),
        "state_bytes": snap["state_bytes"],
        "state_human": snap["state_human"],
        "mode": "dry_run_non_destructive",
        "candidates": snap["compression_candidates"],
        "expected_receipts": [
            "pre_compression_bloat_tax_snapshot",
            "archive_or_engram_receipt_per_candidate",
            "post_compression_bloat_tax_snapshot",
            "identity_integrity_sample",
            "stgm_hygiene_reward_or_tax",
        ],
    }
    state.mkdir(parents=True, exist_ok=True)
    path = state / "forager_compression_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    with (state / "forager_compression_plan.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n")
    return plan


__all__ = [
    "BloatTaxSnapshot",
    "format_bytes",
    "compute_bloat_tax_snapshot",
    "maybe_record_bloat_tax_snapshot",
    "bloat_tax_monitor_lines",
    "write_forager_compression_plan",
]
