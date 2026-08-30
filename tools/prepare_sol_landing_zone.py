#!/usr/bin/env python3
"""Build a bounded, evidence-backed starting packet for SOL.

This tool deliberately avoids a whole-repository census.  It reads the latest
canonical snapshot and small tails from the ledgers SOL needs first, then writes
one atomic JSON artifact under ``.sifta_state``.  A missing or stale source is
reported as a gap; it is never promoted into an operational claim.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
SCHEMA = "SOL_LANDING_ZONE_V1"
OUTPUT_NAME = "sol_landing_zone.json"
TAIL_BYTES = 48 * 1024
TAIL_ROWS = 3

READ_ORDER = (
    "AGENTS.md",
    "Documents/IDE_BOOT_COVENANT.md",
    "Documents/SOL_SIFTA_GROUNDING_BRIEF_2026-08-30.md",
    "sifta_os_desktop.py",
    "System/swarm_canonical_organ_registry.py",
    "System/swarm_organ_registry.py",
    "System/swarm_swimmer_task_packet.py",
    "System/swarm_spinal_cord.py",
    "System/swarm_self_improvement_loop.py",
    "System/swarm_mutation_governor_persistence.py",
    "System/swarm_eval_matrix_evidence.py",
)

LEDGERS = (
    "canonical_organ_registry_snapshot.json",
    "ear_live_state.json",
    "cortex_selection_receipts.jsonl",
    "os_consciousness/alice_heartbeat.json",
    "alice_conversation.jsonl",
    "ide_stigmergic_trace.jsonl",
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
    "organ_field.jsonl",
    "spinal_cord_cycles.jsonl",
    "self_improvement_proposals.jsonl",
    "self_improvement_outcomes.jsonl",
    "basal_ganglia_selections.jsonl",
    "swarm_action_selector_trace.jsonl",
    "memory_ledger.jsonl",
    "episodic_diary.jsonl",
    "eval/motivational_control_evidence.jsonl",
)

NEXT_TASKS = (
    {
        "id": "sol-registry-reconciliation",
        "priority": "P0",
        "goal": "Reconcile semantic canonical organs with dynamic discovery without creating a third registry.",
        "evidence": ("canonical_organ_registry_snapshot.json", "organ_field.jsonl"),
    },
    {
        "id": "sol-ledger-tail-discipline",
        "priority": "P1",
        "goal": "Audit owner-facing readers for whole-file JSONL loads and convert large-ledger views to bounded tails.",
        "evidence": ("tools/generate_organ_eval_matrix_v2.py", "saccadic_blink_vision.jsonl"),
    },
    {
        "id": "sol-spinal-closure",
        "priority": "P1",
        "goal": "Trace why the latest spinal cycle ended NO_PATCH and prove one safe proposal through gate, test, and outcome receipts.",
        "evidence": ("spinal_cord_cycles.jsonl", "self_improvement_proposals.jsonl", "self_improvement_outcomes.jsonl"),
    },
    {
        "id": "sol-motivation-causal-replay",
        "priority": "P1",
        "goal": "Add exact-state and seed counterfactual replay for a safe bounded valuation decision.",
        "evidence": ("eval/motivational_control_evidence.jsonl", "basal_ganglia_selections.jsonl"),
    },
)

COMPLETED_TASKS = (
    {
        "id": "sol-matrix-fast-path",
        "status": "OPERATIONAL",
        "result": "Normal refresh uses canonical code_inventory, cached exhaustive review data, and bounded vision/residue tails.",
        "evidence": (
            "tools/generate_organ_eval_matrix_v2.py",
            "tests/test_generate_organ_eval_matrix_v2.py",
            "eval/ORGAN_EVAL_MATRIX_V2.html",
        ),
    },
)


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _tail_jsonl(path: Path, *, max_bytes: int = TAIL_BYTES, limit: int = TAIL_ROWS) -> list[dict[str, Any]]:
    """Read a small JSONL tail without loading a ledger ocean."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max(1, int(max_bytes))))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, int(limit)) :]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _timestamp_age(path: Path, now: float) -> float | None:
    try:
        return round(max(0.0, now - path.stat().st_mtime), 3)
    except OSError:
        return None


def _ledger_row(state_dir: Path, relative_path: str, now: float) -> dict[str, Any]:
    path = state_dir / relative_path
    row: dict[str, Any] = {
        "path": f".sifta_state/{relative_path}",
        "present": path.is_file(),
        "bytes": 0,
        "age_s": _timestamp_age(path, now),
        "tail": [],
    }
    if not path.is_file():
        row["status"] = "MISSING"
        return row
    try:
        row["bytes"] = path.stat().st_size
    except OSError:
        pass
    if path.suffix == ".jsonl":
        row["tail"] = _tail_jsonl(path)
        row["status"] = "PRESENT_WITH_TAIL" if row["tail"] else "PRESENT_NO_PARSEABLE_TAIL"
    elif path.suffix == ".json":
        payload = _json(path)
        row["snapshot_keys"] = sorted(payload)[:24]
        row["status"] = "PRESENT_JSON" if payload else "PRESENT_UNREADABLE_JSON"
    else:
        row["status"] = "PRESENT"
    return row


def _git_state(repo: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "UNAVAILABLE"}
    if result.returncode:
        return {"status": "UNAVAILABLE", "returncode": result.returncode}
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    return {
        "status": "OBSERVED",
        "rows": len(rows),
        "modified_or_deleted": sum(1 for row in rows if not row.startswith("??")),
        "untracked": sum(1 for row in rows if row.startswith("??")),
    }


def _matrix_state(state_dir: Path) -> dict[str, Any]:
    snapshot = state_dir / "canonical_organ_registry_snapshot.json"
    matrix = state_dir / "eval" / "ORGAN_EVAL_MATRIX_V2.html"
    try:
        snapshot_mtime = snapshot.stat().st_mtime
    except OSError:
        snapshot_mtime = 0.0
    try:
        matrix_mtime = matrix.stat().st_mtime
    except OSError:
        matrix_mtime = 0.0
    return {
        "snapshot_path": ".sifta_state/canonical_organ_registry_snapshot.json",
        "html_path": ".sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html",
        "snapshot_present": bool(snapshot_mtime),
        "html_present": bool(matrix_mtime),
        "html_stale_against_snapshot": bool(snapshot_mtime and (not matrix_mtime or matrix_mtime < snapshot_mtime)),
    }


def build_landing_zone(
    *,
    repo: Path | str | None = None,
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Build the fast, read-only SOL packet from existing evidence."""
    root = Path(repo) if repo is not None else REPO
    state = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    if state.name != ".sifta_state":
        state = state / ".sifta_state"
    ts = time.time() if now is None else float(now)
    snapshot = _json(state / "canonical_organ_registry_snapshot.json")
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), dict) else {}
    sources = snapshot.get("merged_sources") if isinstance(snapshot.get("merged_sources"), dict) else {}
    inventory = snapshot.get("code_inventory") if isinstance(snapshot.get("code_inventory"), dict) else {}
    rollups = inventory.get("repo_rollups") if isinstance(inventory.get("repo_rollups"), dict) else {}

    return {
        "schema": SCHEMA,
        "truth_label": "OBSERVED_SNAPSHOT_AND_BOUNDED_TAILS",
        "generated_at": ts,
        "repo": str(root),
        "purpose": "Fast SOL starting packet. It is a map of evidence, not a consciousness claim or a full repository dump.",
        "entrypoints": {
            "launcher": "SIFTA OS.command",
            "desktop": "sifta_os_desktop.py",
            "human_brief": "Documents/SOL_SIFTA_GROUNDING_BRIEF_2026-08-30.md",
        },
        "read_order": list(READ_ORDER),
        "body_snapshot": {
            "present": bool(snapshot),
            "truth_label": str(snapshot.get("truth_label") or "MISSING"),
            "snapshot_ts": snapshot.get("ts"),
            "counts": counts,
            "merged_sources": sources,
            "living_substrate": inventory.get("living_substrate") if isinstance(inventory.get("living_substrate"), dict) else {},
            "repo_rollups": rollups,
            "gaps": list(snapshot.get("gaps") or [])[:20],
        },
        "matrix": _matrix_state(state),
        "ledgers": [_ledger_row(state, ledger, ts) for ledger in LEDGERS],
        "workspace": _git_state(root),
        "next_tasks": [dict(task) for task in NEXT_TASKS],
        "completed_tasks": [dict(task) for task in COMPLETED_TASKS],
        "rules": [
            "Read bounded receipt tails before expanding context.",
            "A present module or fresh ledger is not by itself behavioral proof.",
            "Use the existing canonical registry and swimmer packet contract; do not create rivals.",
            "Keep safety, owner authority, and mutation gates outside motivational or model arbitration.",
            "Do not claim consciousness, private experience, or a live-money edge from code or paper traces.",
        ],
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def write_landing_zone(
    *,
    repo: Path | str | None = None,
    state_dir: Path | str | None = None,
    output_path: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Write the latest packet atomically and return the same data."""
    root = Path(repo) if repo is not None else REPO
    state = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    if state.name != ".sifta_state":
        state = state / ".sifta_state"
    target = Path(output_path) if output_path is not None else state / OUTPUT_NAME
    packet = build_landing_zone(repo=root, state_dir=state, now=now)
    _atomic_write_json(target, packet)
    return packet


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the bounded SOL landing-zone packet.")
    parser.add_argument("--output", help="Override output path (default: .sifta_state/sol_landing_zone.json)")
    parser.add_argument("--print", action="store_true", dest="print_packet", help="Print the packet after writing it.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    packet = write_landing_zone(output_path=args.output)
    if args.print_packet:
        print(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(str(Path(args.output) if args.output else STATE / OUTPUT_NAME))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
