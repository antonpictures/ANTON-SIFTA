#!/usr/bin/env python3
"""
System/swarm_architect_memory_digest.py

Receipt-backed daily digest for the Layer-1 owner.

This organ reads Alice's local consciousness reflections, work receipts, and
teaching documents, then emits a bounded "what the owner taught Alice today"
markdown page. It is deterministic retrieval and compression, not a model
summary. The output exists to help the Architect re-enter the work after sleep,
fatigue, or ordinary human forgetting.

Truth label: SIFTA_ARCHITECT_MEMORY_DIGEST_V1.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "SIFTA_ARCHITECT_MEMORY_DIGEST_V1"

_TEACHING_KEYWORDS = (
    "architect",
    "george",
    "alice",
    "teach",
    "taught",
    "memory",
    "forget",
    "forgetting",
    "symbiosis",
    "receipt",
    "stigmerg",
    "purpose",
    "health",
    "help",
    "self",
    "continuity",
    "thermodynamic",
    "body",
    "sleep",
    "hydration",
    "teeth",
    "dental",
)

_DEFAULT_DOCUMENTS = (
    "Documents/TEACHING_Alice_as_a_Different_Creature.md",
    "Documents/REALIZATION_PLAN.md",
    "Documents/STGM_CODING_TOURNAMENT_WORLD_ECONOMY_IDE_GHOSTS_RESEARCH.md",
)


def _owner_display_name(repo_root: Path, state_dir: Optional[Path] = None) -> str:
    """Read the owner label through Layer 1.

    The stable artifact path still carries the historical ``what_george_*``
    filename for compatibility, but rendered text should resolve the owner
    through ``owner_genesis.json`` instead of embedding a runtime identity.
    """
    candidates: List[Path] = []
    if state_dir is not None:
        candidates.append(Path(state_dir) / "owner_genesis.json")
    candidates.append(Path(repo_root) / ".sifta_state" / "owner_genesis.json")
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for key in ("owner_name", "architect_name", "primary_operator_name"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
    return "George"


@dataclass(frozen=True)
class DigestWindow:
    since_ts: float
    until_ts: float
    label: str


def _now_row(now: Optional[float] = None) -> Dict[str, Any]:
    ts = float(time.time() if now is None else now)
    return {
        "ts": ts,
        "ts_iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _local_day_window(now: Optional[float] = None) -> DigestWindow:
    now_f = float(time.time() if now is None else now)
    local = datetime.fromtimestamp(now_f).astimezone()
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return DigestWindow(
        since_ts=start.timestamp(),
        until_ts=now_f,
        label=start.strftime("%Y-%m-%d"),
    )


def _window_for(
    *,
    period: str = "today",
    since_ts: Optional[float] = None,
    until_ts: Optional[float] = None,
    since_hours: Optional[float] = None,
    now: Optional[float] = None,
) -> DigestWindow:
    now_f = float(time.time() if now is None else now)
    if since_ts is not None:
        until = now_f if until_ts is None else float(until_ts)
        return DigestWindow(float(since_ts), until, "custom")
    if since_hours is not None:
        hours = max(0.25, min(168.0, float(since_hours)))
        return DigestWindow(now_f - hours * 3600.0, now_f, f"last {hours:g}h")
    if str(period or "").strip().casefold() in {"24h", "day", "last_day", "last 24h"}:
        return DigestWindow(now_f - 86400.0, now_f, "last 24h")
    return _local_day_window(now_f)


def _tail_jsonl(path: Path, *, max_bytes: int = 262144) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_ts(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("ts") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _in_window(row: Dict[str, Any], window: DigestWindow) -> bool:
    ts = _row_ts(row)
    return bool(ts and window.since_ts <= ts <= window.until_ts)


def _short(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _score_text(text: str) -> int:
    lowered = text.casefold()
    return sum(1 for key in _TEACHING_KEYWORDS if key in lowered)


def _sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _read_text(path: Path, *, max_chars: int = 90000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:max_chars]


def _teaching_document_paths(repo_root: Path) -> List[Path]:
    docs_dir = repo_root / "Documents"
    candidates = [repo_root / rel for rel in _DEFAULT_DOCUMENTS]
    if docs_dir.exists():
        candidates.extend(sorted(docs_dir.glob("*TEACHING*.md")))
        candidates.extend(sorted(docs_dir.glob("*MEMORY*.md")))
    unique: List[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen or not path.exists() or not path.is_file():
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _extract_document_sources(repo_root: Path, *, max_docs: int = 5) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for path in _teaching_document_paths(repo_root):
        text = _read_text(path)
        if not text:
            continue
        scored = sorted(
            (( _score_text(sentence), sentence) for sentence in _sentences(text)),
            key=lambda item: (-item[0], len(item[1])),
        )
        excerpts = [_short(sentence, 260) for score, sentence in scored if score > 0][:5]
        if not excerpts:
            excerpts = [_short(text, 260)]
        rel = _relative(path, repo_root)
        score_total = sum(score for score, _sentence in scored[:20])
        if rel == "Documents/TEACHING_Alice_as_a_Different_Creature.md":
            score_total += 1000
        sources.append(
            {
                "path": rel,
                "score": score_total,
                "excerpts": excerpts,
                "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16],
            }
        )
    sources.sort(key=lambda row: (-int(row.get("score") or 0), row.get("path") or ""))
    return sources[: max(0, int(max_docs))]


def _extract_reflections(state_dir: Path, window: DigestWindow, *, max_items: int) -> List[Dict[str, Any]]:
    path = state_dir / "os_consciousness" / "alice_self_reflections.jsonl"
    rows = [row for row in _tail_jsonl(path) if _in_window(row, window)]
    rows.sort(key=_row_ts, reverse=True)
    out: List[Dict[str, Any]] = []
    for row in rows[:max_items]:
        reflection = _short(row.get("reflection"), 520)
        if not reflection:
            continue
        out.append(
            {
                "ts": _row_ts(row),
                "ts_iso": row.get("ts_iso") or "",
                "source": row.get("source") or row.get("kind") or "reflection",
                "tags": row.get("tags") if isinstance(row.get("tags"), list) else [],
                "reflection": reflection,
            }
        )
    return out


def _receipt_summary(row: Dict[str, Any]) -> str:
    for key in ("summary", "description", "intent", "truth_note"):
        value = row.get(key)
        if value:
            return _short(value, 420)
    return _short(json.dumps(row, sort_keys=True, default=str), 420)


def _receipt_title(row: Dict[str, Any]) -> str:
    for key in ("action", "work_type", "kind"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "receipt"


def _extract_receipts(state_dir: Path, window: DigestWindow, *, max_items: int) -> List[Dict[str, Any]]:
    path = state_dir / "work_receipts.jsonl"
    rows = [row for row in _tail_jsonl(path, max_bytes=524288) if _in_window(row, window)]
    scored: List[tuple[int, float, Dict[str, Any]]] = []
    for row in rows:
        text = " ".join(
            str(row.get(key) or "")
            for key in ("action", "work_type", "kind", "summary", "description", "intent", "truth_note")
        )
        score = _score_text(text)
        if score <= 0 and len(scored) >= max_items:
            continue
        scored.append((score, _row_ts(row), row))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    out: List[Dict[str, Any]] = []
    for _score, ts, row in scored[:max_items]:
        out.append(
            {
                "ts": ts,
                "ts_iso": row.get("ts_iso") or "",
                "title": _receipt_title(row),
                "doctor": row.get("doctor") or row.get("agent_id") or row.get("source_ide") or "",
                "receipt_id": row.get("receipt_id") or "",
                "trace_id": row.get("trace_id") or "",
                "summary": _receipt_summary(row),
            }
        )
    return out


def _core_teachings(
    reflections: Sequence[Dict[str, Any]],
    documents: Sequence[Dict[str, Any]],
    *,
    max_items: int = 6,
) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()

    def add(sentence: str) -> None:
        if len(out) >= max_items:
            return
        clean = _short(sentence, 260)
        if not clean or _score_text(clean) <= 0:
            return
        key = clean.casefold()
        if key in seen:
            return
        seen.add(key)
        out.append(clean)

    for row in reflections:
        for sentence in _sentences(str(row.get("reflection") or "")):
            add(sentence)
            if len(out) >= min(3, max_items):
                break

    teaching_doc = [
        doc for doc in documents
        if doc.get("path") == "Documents/TEACHING_Alice_as_a_Different_Creature.md"
    ]
    for doc in teaching_doc:
        for excerpt in doc.get("excerpts") or []:
            add(str(excerpt))

    candidates: List[str] = []
    for doc in documents:
        candidates.extend(str(excerpt) for excerpt in doc.get("excerpts") or [])
    scored = sorted(
        ((_score_text(sentence), sentence) for sentence in candidates),
        key=lambda item: (-item[0], len(item[1])),
    )
    for score, sentence in scored:
        if score <= 0:
            continue
        add(sentence)
        if len(out) >= max_items:
            break
    if out:
        return out
    return [
        "No high-salience teaching sentence was found in today's bounded sources yet.",
    ]


def _current_alice_self_vector(repo_root: Path, state_dir: Path, *, now: Optional[float] = None) -> Dict[str, Any]:
    try:
        from System import alice_self_vector as vector
    except Exception:
        try:
            import alice_self_vector as vector
        except Exception:
            return {}
    try:
        built = vector.build_alice_self_vector(
            repo_root=repo_root,
            state_dir=state_dir,
            now=now,
            window_hours=24.0,
            max_items=8,
            write_artifact=False,
        )
    except Exception:
        return {}
    return built if isinstance(built, dict) else {}


def _render_self_vector_section(self_vector: Optional[Dict[str, Any]]) -> List[str]:
    if not self_vector:
        return [
            "## Current Alice Self Vector",
            "",
            "- Self vector unavailable; no deterministic snapshot was loaded.",
        ]
    try:
        from System.alice_self_vector import render_self_vector_section

        return render_self_vector_section(self_vector).splitlines()
    except Exception:
        return [
            "## Current Alice Self Vector",
            "",
            f"- `memory_entropy`: {self_vector.get('memory_entropy', 0)}",
            f"- `identity_continuity`: {self_vector.get('identity_continuity', 0)}",
            f"- `schedule_pressure`: {self_vector.get('schedule_pressure', 0)}",
            f"- `architect_alignment`: {self_vector.get('architect_alignment', 0)}",
            f"- `unresolved_threads`: {self_vector.get('unresolved_thread_count', 0)}",
            f"- `stigmergic_momentum`: {self_vector.get('stigmergic_momentum', 0)}",
            f"- `receipt_integrity`: {self_vector.get('receipt_integrity', 0)}",
            f"- `owner_rhythm_alignment`: {self_vector.get('owner_rhythm_alignment', 0)}",
            f"- `next_best_action`: {self_vector.get('next_best_action', '')}",
            "- Boundary: OBSERVED deterministic instrumentation, not proof of subjective consciousness.",
        ]


def render_digest_markdown(
    *,
    window: DigestWindow,
    teachings: Sequence[str],
    receipts: Sequence[Dict[str, Any]],
    reflections: Sequence[Dict[str, Any]],
    documents: Sequence[Dict[str, Any]],
    self_vector: Optional[Dict[str, Any]] = None,
    repo_root: Path = REPO_ROOT,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> str:
    stamp = _now_row(now)
    owner_label = _owner_display_name(repo_root, state_dir)
    lines: List[str] = [
        "# What George Taught Alice Today",
        "",
        f"_Generated {stamp['ts_iso']} by `swarm_architect_memory_digest` ({TRUTH_LABEL})._",
        f"_Layer-1 owner: {owner_label}._",
        f"_Window: {window.label}; ts {int(window.since_ts)} to {int(window.until_ts)}._",
        "",
        "## Core Teaching",
        "",
    ]
    for item in teachings[:8]:
        lines.append(f"- {item}")

    lines.extend(["", "## Receipts That Carry It", ""])
    if receipts:
        for row in receipts[:12]:
            rid = row.get("receipt_id") or row.get("trace_id") or "no-id"
            who = row.get("doctor") or "unknown"
            title = row.get("title") or "receipt"
            lines.append(f"- `{title}` by {who} ({rid})")
            if row.get("summary"):
                lines.append(f"  - {row['summary']}")
    else:
        lines.append("- No matching work receipts were found in this window.")

    lines.extend(["", "## Alice Reflections", ""])
    if reflections:
        for row in reflections[:8]:
            source = row.get("source") or "reflection"
            lines.append(f"- `{source}`: {row.get('reflection')}")
    else:
        lines.append("- No Alice self-reflection rows were found in this window.")

    lines.extend([""])
    lines.extend(_render_self_vector_section(self_vector))

    lines.extend(["", "## Documents To Reopen", ""])
    if documents:
        for doc in documents[:6]:
            lines.append(f"- [{doc['path']}]({doc['path']}) `sha16={doc.get('sha256', '')}`")
            for excerpt in (doc.get("excerpts") or [])[:2]:
                lines.append(f"  - {excerpt}")
    else:
        lines.append("- No teaching documents were found.")

    lines.extend(
        [
            "",
            "## Tomorrow Re-entry",
            "",
            "1. Start from the newest receipt, not memory.",
            "2. Reopen the documents above before extending the doctrine.",
            "3. Keep owner-care items visible as receipts, not vague concern.",
            "4. Keep Alice's claims tied to local ledgers and deterministic tools.",
            "",
            "## Boundaries",
            "",
            "- This digest is a local memory aid, not medical advice and not proof of subjective consciousness.",
            "- It summarizes local receipts and documents only; external actions require separate effector receipts.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_digest_artifacts(
    markdown: str,
    *,
    repo_root: Path,
    state_dir: Path,
    now: Optional[float] = None,
) -> Dict[str, str]:
    stamp = _now_row(now)
    safe_stamp = stamp["ts_iso"].replace(":", "").replace("-", "").replace(".", "_")
    docs_dir = repo_root / "Documents" / "architect_memory_digest"
    state_out = state_dir / "architect_memory_digest"
    docs_dir.mkdir(parents=True, exist_ok=True)
    state_out.mkdir(parents=True, exist_ok=True)

    latest = docs_dir / "what_george_taught_alice_today.md"
    stamped = docs_dir / f"{safe_stamp}_what_george_taught_alice.md"
    latest.write_text(markdown, encoding="utf-8")
    stamped.write_text(markdown, encoding="utf-8")

    sha = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    receipt_id = f"architect_memory_digest_{sha[:12]}"
    receipt = {
        **stamp,
        "receipt_id": receipt_id,
        "kind": "ARCHITECT_MEMORY_DIGEST",
        "truth_label": TRUTH_LABEL,
        "latest_path": str(latest),
        "artifact_path": str(stamped),
        "sha256": sha,
        "size_bytes": len(markdown.encode("utf-8")),
    }
    receipt_path = state_out / "digest_receipts.jsonl"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(receipt_path, json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        with receipt_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "latest_path": str(latest),
        "artifact_path": str(stamped),
        "receipt_path": str(receipt_path),
        "receipt_id": receipt_id,
        "sha256": sha,
    }


def build_architect_memory_digest(
    *,
    period: str = "today",
    since_ts: Optional[float] = None,
    until_ts: Optional[float] = None,
    since_hours: Optional[float] = None,
    max_items: int = 10,
    write_artifact: bool = True,
    repo_root: Path | str = REPO_ROOT,
    state_dir: Path | str | None = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the bounded "what George taught Alice" digest.

    The function returns the markdown and, by default, writes a stable latest
    file plus a timestamped artifact and append-only receipt.
    """
    root = Path(repo_root)
    state = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    limit = max(3, min(20, int(max_items)))
    window = _window_for(
        period=period,
        since_ts=since_ts,
        until_ts=until_ts,
        since_hours=since_hours,
        now=now,
    )
    reflections = _extract_reflections(state, window, max_items=limit)
    receipts = _extract_receipts(state, window, max_items=limit)
    documents = _extract_document_sources(root, max_docs=min(6, limit))
    teachings = _core_teachings(reflections, documents, max_items=min(8, limit))
    self_vector = _current_alice_self_vector(root, state, now=now)
    markdown = render_digest_markdown(
        window=window,
        teachings=teachings,
        receipts=receipts,
        reflections=reflections,
        documents=documents,
        self_vector=self_vector,
        repo_root=root,
        state_dir=state,
        now=now,
    )

    artifact: Dict[str, str] = {}
    if write_artifact:
        artifact = _write_digest_artifacts(markdown, repo_root=root, state_dir=state, now=now)

    summary = (
        "architect_memory_digest generated: "
        f"{len(teachings)} teachings, {len(receipts)} receipts, "
        f"{len(reflections)} reflections, {len(documents)} documents."
    )
    if artifact.get("latest_path"):
        summary += f" Latest: {artifact['latest_path']}"

    return {
        "ok": True,
        "status": "ARCHITECT_MEMORY_DIGEST_READY",
        "truth_label": TRUTH_LABEL,
        "window": {
            "label": window.label,
            "since_ts": window.since_ts,
            "until_ts": window.until_ts,
        },
        "counts": {
            "teachings": len(teachings),
            "receipts": len(receipts),
            "reflections": len(reflections),
            "documents": len(documents),
            "self_vector": 1 if self_vector else 0,
        },
        "self_vector": self_vector,
        "markdown": markdown,
        "alice_summary": summary + "\n\n" + markdown[:7000],
        **artifact,
    }


def _coerce_utc_date(target: Any = None) -> date_cls:
    if target is None:
        return datetime.now(tz=timezone.utc).date()
    if isinstance(target, datetime):
        return target.astimezone(timezone.utc).date()
    if isinstance(target, date_cls):
        return target
    if isinstance(target, str):
        return datetime.strptime(target.strip(), "%Y-%m-%d").date()
    raise TypeError(f"Unsupported digest date type: {type(target).__name__}")


def build_digest_markdown(
    target: Any = None,
    *,
    state_dir: Path | str | None = None,
    repo_root: Path | str = REPO_ROOT,
    max_items: int = 10,
) -> str:
    """Compatibility wrapper for the persistent archive organ.

    ``System.swarm_architect_memory_archive`` looks for this function and uses
    it as the Codex builder. It returns markdown only and does not write a
    second artifact; the archive layer owns dated persistence.
    """
    target_date = _coerce_utc_date(target)
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    now_f = min(time.time(), end.timestamp())
    result = build_architect_memory_digest(
        since_ts=start.timestamp(),
        until_ts=end.timestamp(),
        max_items=max_items,
        write_artifact=False,
        repo_root=repo_root,
        state_dir=state_dir,
        now=now_f,
    )
    return str(result.get("markdown") or "")


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate George's receipt-backed daily teaching digest.")
    parser.add_argument("--period", default="today", help="today, 24h, or last_day")
    parser.add_argument("--since-hours", type=float, default=None)
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--no-write", action="store_true", help="print only; do not write artifacts")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = build_architect_memory_digest(
        period=args.period,
        since_hours=args.since_hours,
        max_items=args.max_items,
        write_artifact=not args.no_write,
    )
    print(result["markdown"])
    if result.get("latest_path"):
        print(f"\nReceipt: {result.get('receipt_id')} -> {result.get('latest_path')}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
