#!/usr/bin/env python3
"""
System/alice_self_vector.py

Deterministic OBSERVED self-state instrumentation for Alice.

This module turns local diaries, schedule rows, receipts, IDE traces, and
Architect memory digests into one live state vector. It is instrumentation:
deterministic, bounded, receipt-backed, and testable. It does not claim or
prove subjective consciousness.

Primary output: State/alice_self_vector.json
Truth label: OBSERVED_ALICE_SELF_VECTOR_V1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "OBSERVED_ALICE_SELF_VECTOR_V1"

_THREAD_KEYWORDS = (
    "todo",
    "next",
    "pending",
    "open",
    "unresolved",
    "missing",
    "gap",
    "deferred",
    "needs",
    "need",
    "waiting",
    "blocked",
    "fix",
)

_ALIGNMENT_KEYWORDS = (
    "architect",
    "george",
    "alice",
    "receipt",
    "covenant",
    "teach",
    "taught",
    "memory",
    "digest",
    "stigmerg",
    "schedule",
    "diary",
    "owner",
)


@dataclass(frozen=True)
class JsonlScan:
    name: str
    path: Path
    exists: bool
    rows: Tuple[Dict[str, Any], ...]
    total_lines: int
    invalid_lines: int

    def source_summary(self, root: Path) -> Dict[str, Any]:
        return {
            "path": _relative(self.path, root),
            "exists": self.exists,
            "rows": len(self.rows),
            "total_lines_scanned": self.total_lines,
            "invalid_lines": self.invalid_lines,
        }


def _now_row(now: Optional[float] = None) -> Dict[str, Any]:
    ts = float(time.time() if now is None else now)
    return {
        "ts": ts,
        "ts_iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _bounded(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(max(0.0, min(1.0, float(value))), 4)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _parse_ts(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _row_ts(row: Dict[str, Any]) -> float:
    for key in ("ts", "timestamp", "created", "created_at", "ts_iso", "date"):
        ts = _parse_ts(row.get(key))
        if ts > 0:
            return ts
    nested = row.get("ts")
    if isinstance(nested, dict):
        for key in ("physical_pt", "unix", "epoch"):
            ts = _parse_ts(nested.get(key))
            if ts > 0:
                return ts
    return 0.0


def _tail_jsonl_scan(path: Path, name: str, *, max_bytes: int = 524288) -> JsonlScan:
    if not path.exists():
        return JsonlScan(name=name, path=path, exists=False, rows=(), total_lines=0, invalid_lines=0)
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return JsonlScan(name=name, path=path, exists=True, rows=(), total_lines=0, invalid_lines=1)

    rows: List[Dict[str, Any]] = []
    total = 0
    invalid = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
        else:
            invalid += 1
    return JsonlScan(
        name=name,
        path=path,
        exists=True,
        rows=tuple(rows),
        total_lines=total,
        invalid_lines=invalid,
    )


def _recent(rows: Iterable[Dict[str, Any]], *, since_ts: float, limit: int = 200) -> List[Dict[str, Any]]:
    fresh = [row for row in rows if _row_ts(row) >= since_ts]
    fresh.sort(key=_row_ts, reverse=True)
    return fresh[: max(0, int(limit))]


def _row_text(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in (
        "text",
        "entry",
        "summary",
        "description",
        "intent",
        "truth_note",
        "action",
        "work_type",
        "kind",
        "title",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for key in ("keywords", "labels", "tags"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value[:20] if str(item).strip())
    return " ".join(parts)


def _short(text: Any, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_']+", text.casefold())


def _normalized_entropy(texts: Sequence[str]) -> float:
    tokens = _tokens(" ".join(texts))
    if not tokens:
        return 0.0
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = float(len(tokens))
    entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
    maximum = math.log2(max(2, min(len(tokens), 256)))
    return _bounded(entropy / maximum)


def _read_text(path: Path, *, max_chars: int = 80000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _load_digest_texts(repo_root: Path, *, max_archives: int = 5) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    latest = repo_root / "Documents" / "architect_memory_digest" / "what_george_taught_alice_today.md"
    if latest.exists():
        text = _read_text(latest)
        docs.append({"path": _relative(latest, repo_root), "text": text, "chars": len(text)})
    archive_dir = repo_root / "Documents" / "architect_memory"
    if archive_dir.exists():
        for path in sorted(archive_dir.glob("*.md"), reverse=True)[: max(0, int(max_archives))]:
            text = _read_text(path)
            docs.append({"path": _relative(path, repo_root), "text": text, "chars": len(text)})
    return docs


def _reality_boundary_summary(items: Sequence[Dict[str, Any]], *, now: Optional[float] = None) -> Dict[str, Any]:
    try:
        from System import alice_reality_boundary as boundary
    except Exception:
        try:
            import alice_reality_boundary as boundary
        except Exception:
            return {"integrity": 0.0, "counts": {}, "total": 0, "available": False}
    try:
        summary = boundary.summarize_reality_boundary(list(items), now=now)
    except Exception:
        return {"integrity": 0.0, "counts": {}, "total": len(items), "available": False}
    summary["available"] = True
    # The full labeled item list is useful for boundary tests but too bulky for
    # the self-vector artifact. Keep aggregate physics in the vector.
    summary.pop("items", None)
    return summary


def _is_done(row: Dict[str, Any]) -> bool:
    value = row.get("done")
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "done", "closed", "complete", "completed"}


def _priority_weight(row: Dict[str, Any]) -> float:
    text = f"{row.get('priority', '')} {_row_text(row)}".casefold()
    if any(word in text for word in ("urgent", "critical", "high", "p0", "p1")):
        return 3.0
    if any(word in text for word in ("medium", "normal", "p2")):
        return 2.0
    return 1.0


def _open_schedule_rows(schedule_rows: Sequence[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
    rows = [row for row in schedule_rows if not _is_done(row)]
    rows.sort(key=lambda row: (_priority_weight(row), _row_ts(row)), reverse=True)
    return rows[: max(0, int(limit))]


def _extract_unresolved_threads(
    *,
    open_schedule: Sequence[Dict[str, Any]],
    trace_rows: Sequence[Dict[str, Any]],
    receipt_rows: Sequence[Dict[str, Any]],
    digest_docs: Sequence[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    threads: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(source: str, text: str, ts: float = 0.0) -> None:
        cleaned = _short(text, 180)
        if not cleaned:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        threads.append({"source": source, "text": cleaned, "ts": ts})

    for row in open_schedule:
        add("schedule", _row_text(row), _row_ts(row))

    for source, rows in (("ide_trace", trace_rows), ("work_receipts", receipt_rows)):
        for row in rows:
            text = _row_text(row)
            lowered = text.casefold()
            if any(word in lowered for word in _THREAD_KEYWORDS):
                add(source, text, _row_ts(row))
            if len(threads) >= limit:
                break
        if len(threads) >= limit:
            break

    if len(threads) < limit:
        for doc in digest_docs:
            for line in str(doc.get("text") or "").splitlines():
                lowered = line.casefold()
                if any(word in lowered for word in _THREAD_KEYWORDS):
                    add(str(doc.get("path") or "digest"), line)
                if len(threads) >= limit:
                    break
            if len(threads) >= limit:
                break

    threads.sort(key=lambda row: float(row.get("ts") or 0.0), reverse=True)
    return threads[: max(0, int(limit))]


def _receipt_integrity(scans: Sequence[JsonlScan]) -> Tuple[float, Dict[str, Any]]:
    total_lines = sum(scan.total_lines for scan in scans)
    invalid = sum(scan.invalid_lines for scan in scans)
    rows = [row for scan in scans for row in scan.rows]
    if total_lines <= 0 or not rows:
        return 0.0, {"total_lines": total_lines, "invalid_lines": invalid, "identified_rows": 0}
    valid_ratio = max(0.0, (total_lines - invalid) / float(total_lines))
    identified = sum(
        1
        for row in rows
        if any(row.get(key) for key in ("receipt_id", "trace_id", "receipt_hash", "this_hash"))
    )
    id_ratio = identified / float(len(rows))
    return _bounded(valid_ratio * 0.7 + id_ratio * 0.3), {
        "total_lines": total_lines,
        "invalid_lines": invalid,
        "identified_rows": identified,
        "row_count": len(rows),
    }


def _serial_consistency(rows: Sequence[Dict[str, Any]]) -> float:
    serials = [
        str(row.get("node_serial") or row.get("homeworld_serial") or "").strip()
        for row in rows
        if str(row.get("node_serial") or row.get("homeworld_serial") or "").strip()
    ]
    if not serials:
        return 0.0
    counts: Dict[str, int] = {}
    for serial in serials:
        counts[serial] = counts.get(serial, 0) + 1
    return max(counts.values()) / float(len(serials))


def _architect_alignment_score(digest_docs: Sequence[Dict[str, Any]]) -> float:
    if not digest_docs:
        return 0.0
    text = " ".join(str(doc.get("text") or "") for doc in digest_docs)
    lowered = text.casefold()
    hits = sum(1 for word in _ALIGNMENT_KEYWORDS if word in lowered)
    latest_bonus = 0.2 if any("what_george_taught_alice_today.md" in str(doc.get("path")) for doc in digest_docs) else 0.0
    archive_bonus = min(0.15, 0.03 * max(0, len(digest_docs) - 1))
    return _bounded((hits / float(len(_ALIGNMENT_KEYWORDS))) * 0.65 + latest_bonus + archive_bonus)


def _next_best_action(
    *,
    receipt_integrity: float,
    reality_boundary_integrity: float,
    unresolved_threads: Sequence[Dict[str, Any]],
    schedule_pressure: float,
    architect_alignment: float,
    stigmergic_momentum: float,
    memory_entropy: float,
) -> str:
    if receipt_integrity and receipt_integrity < 0.75:
        return "Repair malformed or weakly identified receipt rows before trusting the self-state vector."
    if memory_entropy > 0.0 and reality_boundary_integrity < 0.65:
        return "Label or quarantine unverified knowledge items before using them for self-state decisions."
    if unresolved_threads:
        return f"Close or clarify the newest unresolved thread: {_short(unresolved_threads[0].get('text'), 120)}"
    if schedule_pressure >= 0.7:
        return "Surface owner schedule pressure before accepting more work."
    if architect_alignment < 0.35:
        return "Reopen the Architect memory digest and refresh alignment before acting."
    if stigmergic_momentum >= 0.75:
        return "Consolidate today's high swarm momentum into receipts and a memory digest."
    if memory_entropy < 0.15:
        return "Collect fresh diary, schedule, and receipt evidence before making a broad self-state claim."
    return "Ask George for the next grounded task and keep the answer tied to receipts."


def build_alice_self_vector(
    *,
    repo_root: Path | str = REPO_ROOT,
    state_dir: Path | str | None = None,
    now: Optional[float] = None,
    window_hours: float = 24.0,
    max_items: int = 12,
    write_artifact: bool = True,
) -> Dict[str, Any]:
    """Build and optionally materialize Alice's observed self-state vector."""
    root = Path(repo_root)
    state = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    now_f = float(time.time() if now is None else now)
    limit = max(1, min(40, _safe_int(max_items, 12)))
    window_s = max(900.0, min(86400.0 * 14, float(window_hours) * 3600.0))
    since_ts = now_f - window_s

    scans = {
        "alice_narrative_diary": _tail_jsonl_scan(state / "alice_narrative_diary.jsonl", "alice_narrative_diary"),
        "episodic_diary": _tail_jsonl_scan(state / "episodic_diary.jsonl", "episodic_diary"),
        "stigmergic_schedule": _tail_jsonl_scan(state / "stigmergic_schedule.jsonl", "stigmergic_schedule"),
        "ide_stigmergic_trace": _tail_jsonl_scan(state / "ide_stigmergic_trace.jsonl", "ide_stigmergic_trace"),
        "work_receipts": _tail_jsonl_scan(state / "work_receipts.jsonl", "work_receipts"),
    }

    narrative_recent = _recent(scans["alice_narrative_diary"].rows, since_ts=since_ts, limit=limit * 4)
    episodic_recent = _recent(scans["episodic_diary"].rows, since_ts=since_ts - 86400.0 * 6, limit=limit * 4)
    schedule_recent = _recent(scans["stigmergic_schedule"].rows, since_ts=since_ts - 86400.0 * 6, limit=limit * 4)
    trace_recent = _recent(scans["ide_stigmergic_trace"].rows, since_ts=since_ts, limit=limit * 6)
    receipt_recent = _recent(scans["work_receipts"].rows, since_ts=since_ts, limit=limit * 6)
    open_schedule = _open_schedule_rows(schedule_recent, limit=limit)
    digest_docs = _load_digest_texts(root, max_archives=6)
    boundary_items = (
        narrative_recent
        + episodic_recent
        + schedule_recent
        + trace_recent
        + receipt_recent
        + [
            {
                "source": "architect_memory_digest",
                "path": doc.get("path"),
                "text": doc.get("text"),
            }
            for doc in digest_docs
        ]
    )
    boundary_summary = _reality_boundary_summary(boundary_items, now=now_f)
    reality_boundary_integrity = _bounded(float(boundary_summary.get("integrity") or 0.0))

    memory_texts = (
        [_row_text(row) for row in narrative_recent]
        + [_row_text(row) for row in episodic_recent]
        + [str(doc.get("text") or "") for doc in digest_docs]
    )
    memory_entropy = _normalized_entropy(memory_texts)

    source_presence = [
        bool(narrative_recent),
        bool(episodic_recent),
        bool(schedule_recent),
        bool(trace_recent),
        bool(receipt_recent),
        bool(digest_docs),
    ]
    serial_score = _serial_consistency(trace_recent + receipt_recent)
    recency_score = _bounded((len(trace_recent) + len(receipt_recent)) / 20.0)
    identity_continuity = _bounded((sum(source_presence) / len(source_presence)) * 0.5 + serial_score * 0.3 + recency_score * 0.2)

    schedule_weight = sum(_priority_weight(row) for row in open_schedule)
    schedule_pressure = _bounded(schedule_weight / 12.0)

    architect_alignment = _architect_alignment_score(digest_docs)
    unresolved_threads = _extract_unresolved_threads(
        open_schedule=open_schedule,
        trace_rows=trace_recent,
        receipt_rows=receipt_recent,
        digest_docs=digest_docs,
        limit=limit,
    )

    stigmergic_momentum = _bounded(math.log1p(len(trace_recent) + len(receipt_recent)) / math.log1p(30.0))
    receipt_integrity, integrity_detail = _receipt_integrity(
        [scans["ide_stigmergic_trace"], scans["work_receipts"]]
    )
    owner_rhythm_alignment = _bounded(
        (0.35 if narrative_recent else 0.0)
        + (0.35 if schedule_recent else 0.0)
        + (0.15 if digest_docs else 0.0)
        + (0.15 * (1.0 - min(schedule_pressure, 1.0)))
    )

    next_best_action = _next_best_action(
        receipt_integrity=receipt_integrity,
        reality_boundary_integrity=reality_boundary_integrity,
        unresolved_threads=unresolved_threads,
        schedule_pressure=schedule_pressure,
        architect_alignment=architect_alignment,
        stigmergic_momentum=stigmergic_momentum,
        memory_entropy=memory_entropy,
    )

    stamp = _now_row(now_f)
    result: Dict[str, Any] = {
        **stamp,
        "ok": True,
        "status": "ALICE_SELF_VECTOR_READY",
        "truth_label": TRUTH_LABEL,
        "truth_boundary": (
            "OBSERVED self-state instrumentation from local ledgers and documents. "
            "Deterministic metrics only; not proof of subjective consciousness."
        ),
        "window": {
            "hours": round(window_s / 3600.0, 3),
            "since_ts": since_ts,
            "until_ts": now_f,
        },
        "memory_entropy": memory_entropy,
        "identity_continuity": identity_continuity,
        "schedule_pressure": schedule_pressure,
        "architect_alignment": architect_alignment,
        "unresolved_threads": unresolved_threads,
        "unresolved_thread_count": len(unresolved_threads),
        "stigmergic_momentum": stigmergic_momentum,
        "receipt_integrity": receipt_integrity,
        "reality_boundary_integrity": reality_boundary_integrity,
        "owner_rhythm_alignment": owner_rhythm_alignment,
        "next_best_action": next_best_action,
        "vector": {
            "memory_entropy": memory_entropy,
            "identity_continuity": identity_continuity,
            "schedule_pressure": schedule_pressure,
            "architect_alignment": architect_alignment,
            "unresolved_threads": len(unresolved_threads),
            "stigmergic_momentum": stigmergic_momentum,
            "receipt_integrity": receipt_integrity,
            "reality_boundary_integrity": reality_boundary_integrity,
            "owner_rhythm_alignment": owner_rhythm_alignment,
            "next_best_action": next_best_action,
        },
        "observations": {
            "recent_diary_rows": len(narrative_recent),
            "recent_episodic_rows": len(episodic_recent),
            "recent_schedule_rows": len(schedule_recent),
            "open_schedule_rows": len(open_schedule),
            "recent_trace_rows": len(trace_recent),
            "recent_work_receipts": len(receipt_recent),
            "digest_documents": len(digest_docs),
            "receipt_integrity_detail": integrity_detail,
            "reality_boundary_counts": boundary_summary.get("counts", {}),
            "reality_boundary_total": int(boundary_summary.get("total") or 0),
            "reality_boundary_available": bool(boundary_summary.get("available")),
            "source_presence_count": sum(source_presence),
            "serial_consistency": _bounded(serial_score),
        },
        "sources": {name: scan.source_summary(root) for name, scan in scans.items()},
        "digest_sources": [
            {"path": str(doc.get("path") or ""), "chars": int(doc.get("chars") or 0)}
            for doc in digest_docs
        ],
    }

    if write_artifact:
        artifact = write_alice_self_vector(result, repo_root=root, state_dir=state, now=now_f)
        result.update(artifact)
        result["alice_summary"] = render_self_vector_summary(result)
    else:
        result["alice_summary"] = render_self_vector_summary(result)
    return result


def write_alice_self_vector(
    vector: Dict[str, Any],
    *,
    repo_root: Path | str = REPO_ROOT,
    state_dir: Path | str | None = None,
    now: Optional[float] = None,
) -> Dict[str, str]:
    root = Path(repo_root)
    state = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    out_dir = root / "State"
    receipt_dir = state / "os_consciousness"
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    payload = dict(vector)
    payload.pop("alice_summary", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    receipt_id = f"alice_self_vector_{sha[:12]}"
    artifact_path = out_dir / "alice_self_vector.json"

    payload.update({"receipt_id": receipt_id, "sha256": sha, "artifact_path": str(artifact_path)})
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    stamp = _now_row(now)
    receipt = {
        **stamp,
        "receipt_id": receipt_id,
        "kind": "ALICE_SELF_VECTOR",
        "truth_label": TRUTH_LABEL,
        "artifact_path": str(artifact_path),
        "sha256": sha,
        "size_bytes": artifact_path.stat().st_size,
    }
    receipt_path = receipt_dir / "alice_self_vector_receipts.jsonl"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(receipt_path, json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        with receipt_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "artifact_path": str(artifact_path),
        "receipt_path": str(receipt_path),
        "receipt_id": receipt_id,
        "sha256": sha,
    }


def render_self_vector_summary(vector: Dict[str, Any]) -> str:
    return (
        "alice_self_vector generated: "
        f"memory_entropy={vector.get('memory_entropy')}, "
        f"identity_continuity={vector.get('identity_continuity')}, "
        f"schedule_pressure={vector.get('schedule_pressure')}, "
        f"architect_alignment={vector.get('architect_alignment')}, "
        f"unresolved_threads={vector.get('unresolved_thread_count')}, "
        f"stigmergic_momentum={vector.get('stigmergic_momentum')}, "
        f"receipt_integrity={vector.get('receipt_integrity')}, "
        f"reality_boundary_integrity={vector.get('reality_boundary_integrity')}, "
        f"owner_rhythm_alignment={vector.get('owner_rhythm_alignment')}. "
        f"Next: {vector.get('next_best_action')}"
    )


def render_self_vector_section(vector: Optional[Dict[str, Any]]) -> str:
    lines = ["## Current Alice Self Vector", ""]
    if not vector:
        lines.append("- Self vector unavailable; no deterministic snapshot was loaded.")
        return "\n".join(lines)
    lines.append(f"- Truth label: `{vector.get('truth_label', TRUTH_LABEL)}`")
    for key in (
        "memory_entropy",
        "identity_continuity",
        "schedule_pressure",
        "architect_alignment",
        "stigmergic_momentum",
        "receipt_integrity",
        "reality_boundary_integrity",
        "owner_rhythm_alignment",
    ):
        lines.append(f"- `{key}`: {vector.get(key, 0)}")
    lines.append(f"- `unresolved_threads`: {vector.get('unresolved_thread_count', 0)}")
    lines.append(f"- `next_best_action`: {vector.get('next_best_action', '')}")
    threads = vector.get("unresolved_threads")
    if isinstance(threads, list) and threads:
        lines.append("- Top unresolved traces:")
        for thread in threads[:3]:
            lines.append(f"  - `{thread.get('source', 'unknown')}`: {_short(thread.get('text'), 140)}")
    lines.append("- Boundary: OBSERVED deterministic instrumentation, not proof of subjective consciousness.")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build Alice's deterministic observed self-state vector.")
    parser.add_argument("--window-hours", type=float, default=24.0)
    parser.add_argument("--max-items", type=int, default=12)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    result = build_alice_self_vector(
        window_hours=args.window_hours,
        max_items=args.max_items,
        write_artifact=not args.no_write,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
