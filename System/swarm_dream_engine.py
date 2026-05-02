#!/usr/bin/env python3
"""
System/swarm_dream_engine.py

Event 88 sleep organ for the executable body-brain loop.

The dream engine treats ``body_brain_memory.jsonl`` as short-term episodic
memory. During metabolic sleep it replays real tick rows, writes compact
long-term engrams, and applies a recoverable retention policy. It never removes
raw rows without first writing a full backup and an audit receipt.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import append_line_locked, compact_locked, read_text_locked


SCHEMA_VERSION = "event88.swarm_dream_engine.v1"


@dataclass(frozen=True)
class DreamEngineConfig:
    """Retention and replay policy for one sleep cycle."""

    min_rows_for_engram: int = 2
    max_engrams_per_cycle: int = 5
    prune_after_rows: int = 5000
    keep_recent_rows: int = 2000
    preserve_td_threshold: float = 2.0
    source_ledger_name: str = "body_brain_memory.jsonl"
    engram_ledger_name: str = "long_term_engrams.jsonl"
    cycle_ledger_name: str = "dream_cycles.jsonl"
    backup_dir_name: str = "dream_backups"


@dataclass(frozen=True)
class DreamCycleReceipt:
    """Audit receipt for one attempted dream cycle."""

    kind: str
    schema_version: str
    cycle_id: str
    ts: float
    status: str
    source_ledger: str
    source_hash: str
    rows_seen: int
    rows_replayed: int
    engrams_written: int
    rows_pruned: int
    rows_retained: int
    skills_crystallized: int
    skills_updated: int
    backup_path: str
    backup_sha256: str
    retention_policy: Dict[str, Any]
    rest_seconds: float
    pressure: Optional[float]
    metabolic_mode: str
    notes: Dict[str, str]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_dumps(row: Dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _line_digest(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _action_key(action: Dict[str, Any]) -> str:
    typ = str(action.get("type") or "unknown").strip() or "unknown"
    target = str(action.get("target") or "").strip()
    return f"{typ}:{target}" if target else typ


class SwarmDreamEngine:
    """Replay body-brain ticks into long-term engrams during metabolic sleep."""

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        *,
        config: Optional[DreamEngineConfig] = None,
    ) -> None:
        self.state_dir = Path(state_dir) if state_dir is not None else Path(".sifta_state")
        self.cfg = config or DreamEngineConfig()
        self.source_ledger = self.state_dir / self.cfg.source_ledger_name
        self.engram_ledger = self.state_dir / self.cfg.engram_ledger_name
        self.cycle_ledger = self.state_dir / self.cfg.cycle_ledger_name
        self.backup_dir = self.state_dir / self.cfg.backup_dir_name

    def trigger_rem_sleep(
        self,
        *,
        rest_seconds: float = 0.0,
        pressure: Optional[float] = None,
        metabolic_mode: str = "",
    ) -> DreamCycleReceipt:
        """Run one deterministic replay/downscaling cycle and write a receipt."""

        cycle_id = uuid.uuid4().hex
        now = time.time()
        text = read_text_locked(self.source_ledger)
        raw_lines = [line for line in text.splitlines() if line.strip()]
        source_hash = _sha256_text("\n".join(raw_lines)) if raw_lines else ""
        rows = self._parse_body_brain_rows(raw_lines)
        notes: Dict[str, str] = {}
        skills_crystallized = 0
        skills_updated = 0

        status = "consolidated"
        engrams_written = 0
        if not raw_lines:
            status = "no_episodic_ledger"
            notes["reason"] = "body_brain_memory.jsonl is missing or empty"
        elif not rows:
            status = "no_body_brain_rows"
            notes["reason"] = "ledger had no valid event=body_brain_tick rows"
        elif len(rows) < self.cfg.min_rows_for_engram:
            status = "insufficient_rows_for_engram"
            notes["reason"] = (
                f"{len(rows)} replayable rows < min_rows_for_engram="
                f"{self.cfg.min_rows_for_engram}"
            )
        elif self._source_hash_seen(source_hash):
            status = "duplicate_source_skipped"
            notes["reason"] = "source hash already consolidated in dream_cycles.jsonl"
        else:
            engrams = self._build_engrams(
                rows,
                cycle_id=cycle_id,
                source_hash=source_hash,
                now=now,
            )
            for engram in engrams:
                append_line_locked(self.engram_ledger, _json_dumps(engram) + "\n")
            engrams_written = len(engrams)
            if engrams_written == 0:
                status = "no_salient_rows"
            try:
                from System.temporal_identity_compression import TemporalIdentityCompressionEngine

                skill_stats = TemporalIdentityCompressionEngine(self.state_dir).process_body_brain_ticks(
                    rows,
                    source_hash=source_hash,
                    cycle_id=cycle_id,
                )
                skills_crystallized = int(skill_stats.get("skills_created") or 0)
                skills_updated = int(skill_stats.get("skills_updated") or 0)
            except Exception as exc:
                notes["skill_crystallization_error"] = str(exc)

        backup_path = ""
        backup_hash = ""
        rows_pruned = 0
        rows_retained = len(raw_lines)
        if raw_lines and len(raw_lines) > self.cfg.prune_after_rows:
            backup_path, backup_hash = self._write_backup(cycle_id, text)
            rows_retained, rows_pruned = self._apply_retention(raw_lines, rows)
            if status.endswith("skipped"):
                status = f"{status}_retention_applied"

        receipt = DreamCycleReceipt(
            kind="dream_cycle",
            schema_version=SCHEMA_VERSION,
            cycle_id=cycle_id,
            ts=now,
            status=status,
            source_ledger=self.cfg.source_ledger_name,
            source_hash=source_hash,
            rows_seen=len(raw_lines),
            rows_replayed=len(rows),
            engrams_written=engrams_written,
            rows_pruned=rows_pruned,
            rows_retained=rows_retained,
            skills_crystallized=skills_crystallized,
            skills_updated=skills_updated,
            backup_path=backup_path,
            backup_sha256=backup_hash,
            retention_policy=self._retention_policy_dict(),
            rest_seconds=float(rest_seconds),
            pressure=pressure,
            metabolic_mode=metabolic_mode,
            notes=notes,
        )
        append_line_locked(self.cycle_ledger, _json_dumps(receipt.as_dict()) + "\n")
        return receipt

    def _parse_body_brain_rows(self, raw_lines: Iterable[str]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for index, line in enumerate(raw_lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("event") != "body_brain_tick":
                continue
            action = row.get("action") if isinstance(row.get("action"), dict) else {}
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            rows.append(
                {
                    "index": index,
                    "raw": line,
                    "row": row,
                    "action": action,
                    "result": result,
                    "td_value": _coerce_float(row.get("td_value")),
                    "ts": _coerce_float(row.get("ts")),
                }
            )
        return rows

    def _build_engrams(
        self,
        rows: List[Dict[str, Any]],
        *,
        cycle_id: str,
        source_hash: str,
        now: float,
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(_action_key(row["action"]), []).append(row)

        summaries: List[Dict[str, Any]] = []
        for key, group in grouped.items():
            values = [float(item["td_value"]) for item in group]
            best = max(group, key=lambda item: float(item["td_value"]))
            summaries.append(
                {
                    "key": key,
                    "group": group,
                    "best": best,
                    "max_td": max(values),
                    "mean_td": statistics.fmean(values),
                    "min_td": min(values),
                    "count": len(group),
                }
            )

        summaries.sort(key=lambda item: (item["max_td"], item["count"], item["key"]), reverse=True)
        engrams: List[Dict[str, Any]] = []
        for i, summary in enumerate(summaries[: self.cfg.max_engrams_per_cycle]):
            best = summary["best"]
            action = dict(best["action"])
            result = dict(best["result"])
            action_label = _action_key(action)
            content = (
                f"During Event 88 sleep replay, action {action_label!r} appeared "
                f"{summary['count']} time(s); best td_value={summary['max_td']:.3f}, "
                f"mean td_value={summary['mean_td']:.3f}."
            )
            engrams.append(
                {
                    "kind": "dream_engram",
                    "schema_version": SCHEMA_VERSION,
                    "engram_id": f"dream-{cycle_id}-{i + 1}",
                    "cycle_id": cycle_id,
                    "ts": now,
                    "source_ledger": self.cfg.source_ledger_name,
                    "source_hash": source_hash,
                    "event_count": summary["count"],
                    "action": action,
                    "result_status": str(result.get("status") or ""),
                    "td_value": {
                        "max": round(float(summary["max_td"]), 6),
                        "mean": round(float(summary["mean_td"]), 6),
                        "min": round(float(summary["min_td"]), 6),
                    },
                    "content": content,
                    "facts": [
                        "body_brain_tick",
                        "sleep_consolidation",
                        "synaptic_homeostasis",
                        "sharp_wave_replay",
                    ],
                    "truth_label": "OPERATIONAL",
                }
            )
        return engrams

    def _source_hash_seen(self, source_hash: str) -> bool:
        if not source_hash or not self.cycle_ledger.exists():
            return False
        text = read_text_locked(self.cycle_ledger)
        for line in text.splitlines():
            if not line.strip().startswith("{"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                row.get("schema_version") == SCHEMA_VERSION
                and row.get("source_hash") == source_hash
                and int(row.get("engrams_written") or 0) > 0
            ):
                return True
        return False

    def _write_backup(self, cycle_id: str, text: str) -> tuple[str, str]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup = self.backup_dir / f"body_brain_memory.{cycle_id}.jsonl"
        backup.write_text(text, encoding="utf-8")
        return str(backup.relative_to(self.state_dir)), _sha256_text(text)

    def _apply_retention(self, raw_lines: List[str], rows: List[Dict[str, Any]]) -> tuple[int, int]:
        keep_digests = self._retained_line_digests(raw_lines, rows)
        known_digests = {_line_digest(line) for line in raw_lines}

        def keep(line: str) -> bool:
            digest = _line_digest(line.rstrip("\n"))
            # Lines appended after the backup snapshot are outside this cycle's
            # authority, so keep them for the next sleep pass.
            return digest in keep_digests or digest not in known_digests

        kept_count, evicted = compact_locked(self.source_ledger, keep)
        return int(kept_count), len(evicted)

    def _retained_line_digests(self, raw_lines: List[str], rows: List[Dict[str, Any]]) -> set[str]:
        keep: set[str] = set()
        cutoff = max(0, len(raw_lines) - self.cfg.keep_recent_rows)
        for index, line in enumerate(raw_lines):
            if index >= cutoff:
                keep.add(_line_digest(line))

        for item in rows:
            if float(item["td_value"]) >= self.cfg.preserve_td_threshold:
                keep.add(_line_digest(str(item["raw"])))

        # Preserve malformed/non-body rows; the dream engine is not their owner.
        body_indices = {int(item["index"]) for item in rows}
        for index, line in enumerate(raw_lines):
            if index not in body_indices:
                keep.add(_line_digest(line))
        return keep

    def _retention_policy_dict(self) -> Dict[str, Any]:
        return {
            "prune_after_rows": self.cfg.prune_after_rows,
            "keep_recent_rows": self.cfg.keep_recent_rows,
            "preserve_td_threshold": self.cfg.preserve_td_threshold,
            "delete_mode": "recoverable_backup_then_locked_compaction",
            "backup_required": True,
        }


if __name__ == "__main__":
    receipt = SwarmDreamEngine().trigger_rem_sleep()
    print(json.dumps(receipt.as_dict(), indent=2, ensure_ascii=False))
