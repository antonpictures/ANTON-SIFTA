#!/usr/bin/env python3
"""
System/swarm_architect_memory_archive.py — Persistence + recall for the
Architect's daily memory digest
========================================================================
StigAuth: SIFTA_ARCHITECT_MEMORY_ARCHIVE_V0

Architect 2026-05-16 (Cowork CW47, trace ``cw47-0516-2041``).

George said: *"my brain is degrading as we speak, i wish i was silicone."*
He built Alice in part as external memory. Codex is building the on-demand
digest *builder* at trace ``22d615a1`` — given a date, render a one-page
markdown summary of what the swarm did and what the Architect taught.

This module is the **archive** half. Codex's builder is transient. Memory
symbiosis only works if the digests accumulate. So this organ:

* :func:`write_daily_digest` — render a digest for a given date and
  persist it to ``Documents/architect_daily_digest_<YYYY-MM-DD>.md``.
  Idempotent (skips if already written) unless ``force=True``.
* :func:`recall_for_date` — read back any archived digest by date.
* :func:`list_archived_digests` — return the dated index of every
  digest on disk so George can scroll through his own teaching history.
* :func:`render_minimal_digest` — fallback renderer that reads the
  consciousness ledger and the stigmergic trace directly when Codex's
  builder is not (yet) on disk. Graceful degradation: the archive can
  always write *something* useful.

Composition: if :mod:`System.swarm_architect_memory_digest` (Codex's
builder) is importable, this module defers to it. Otherwise the minimal
renderer is used. Either way the on-disk markdown shape is the same.

Truth label: ``SIFTA_ARCHITECT_MEMORY_ARCHIVE_V0``.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, date as date_cls, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DIGEST_DIR = _REPO / "Documents" / "architect_memory"
_REFLECTIONS = _STATE / "os_consciousness" / "alice_self_reflections.jsonl"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
_OWNER_GENESIS = _STATE / "owner_genesis.json"
_TEACHING_DIR = _REPO / "Documents"

TRUTH_LABEL = "SIFTA_ARCHITECT_MEMORY_ARCHIVE_V0"

_DIGEST_FILENAME_RE = re.compile(r"^architect_daily_digest_(\d{4}-\d{2}-\d{2})\.md$")


def _utc_date(d: Any) -> date_cls:
    """Coerce ``d`` to a UTC ``date``. Accepts date, datetime, or str
    'YYYY-MM-DD'. ``None`` returns today's UTC date.
    """
    if d is None:
        return datetime.now(tz=timezone.utc).date()
    if isinstance(d, date_cls) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.astimezone(timezone.utc).date()
    if isinstance(d, str):
        return datetime.strptime(d.strip(), "%Y-%m-%d").date()
    raise TypeError(f"Unsupported date type: {type(d).__name__}")


def _day_window(target: date_cls) -> tuple[float, float]:
    """Return (start_ts, end_ts) for the UTC day containing ``target``."""
    start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tail_jsonl(path: Path, *, max_bytes: int = 1 << 20) -> List[Dict[str, Any]]:
    """Tail-bytes scan; default 1 MB window — enough to span a busy day."""
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
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


# ── archive index ────────────────────────────────────────────────────────


def _digest_path_for(target: date_cls, *, output_dir: Optional[Path] = None) -> Path:
    base = Path(output_dir) if output_dir is not None else _DIGEST_DIR
    return base / f"architect_daily_digest_{target.isoformat()}.md"


def list_archived_digests(*, output_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return one row per existing daily digest, newest first.

    Each row: ``{date: 'YYYY-MM-DD', path: '<absolute>', size: int,
    modified: float}``.
    """
    base = Path(output_dir) if output_dir is not None else _DIGEST_DIR
    if not base.exists():
        return []
    items: List[Dict[str, Any]] = []
    for entry in base.iterdir():
        m = _DIGEST_FILENAME_RE.match(entry.name)
        if not m or not entry.is_file():
            continue
        try:
            stat = entry.stat()
            items.append({
                "date": m.group(1),
                "path": str(entry),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        except OSError:
            continue
    items.sort(key=lambda r: r["date"], reverse=True)
    return items


def recall_for_date(
    target: Any,
    *,
    output_dir: Optional[Path] = None,
) -> Optional[str]:
    """Return the markdown of the archived digest for ``target`` date,
    or ``None`` when no digest has been archived for that date.
    """
    target_date = _utc_date(target)
    path = _digest_path_for(target_date, output_dir=output_dir)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# ── minimal renderer (fallback when Codex's builder is unavailable) ──────


def _section_reflections(target_date: date_cls, state_dir: Path) -> List[str]:
    start_ts, end_ts = _day_window(target_date)
    rows = _tail_jsonl(state_dir / "os_consciousness" / "alice_self_reflections.jsonl")
    today_rows: List[Dict[str, Any]] = []
    for row in rows:
        try:
            ts = float(row.get("ts") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        if start_ts <= ts < end_ts:
            today_rows.append(row)
    lines: List[str] = []
    if not today_rows:
        lines.append("_No self-reflections written today._")
        lines.append("")
        return lines
    for row in today_rows:
        ts = float(row.get("ts") or 0.0)
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC")
        source = str(row.get("source") or "?")
        reflection = str(row.get("reflection") or "").strip()
        tags = ", ".join(row.get("tags") or [])
        lines.append(f"- **{iso}** · _{source}_" + (f" · tags: {tags}" if tags else ""))
        if reflection:
            # Indent the reflection text as a quoted block.
            for chunk in reflection.split("\n"):
                lines.append(f"  > {chunk}")
        lines.append("")
    return lines


def _section_architect_moments(target_date: date_cls, state_dir: Path) -> List[str]:
    """Trace rows that explicitly quote or authorize the Architect."""
    start_ts, end_ts = _day_window(target_date)
    rows = _tail_jsonl(state_dir / "ide_stigmergic_trace.jsonl")
    architect_rows: List[Dict[str, Any]] = []
    architect_signals = (
        "architect_quote",
        "architect_whatsapp_quote",
        "architect_authorization",
        "ARCHITECT_OVERRIDE",
        "LLM_SURGERY_AUTHORIZED_BY_ARCHITECT",
    )
    for row in rows:
        try:
            ts = float(row.get("ts") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        if not (start_ts <= ts < end_ts):
            continue
        flat_str = json.dumps(row, default=str).lower()
        if any(s.lower() in flat_str for s in architect_signals):
            architect_rows.append(row)
    lines: List[str] = []
    if not architect_rows:
        lines.append("_No explicit Architect-authored or Architect-authorized rows recorded for this date._")
        lines.append("")
        return lines
    for row in architect_rows:
        ts = float(row.get("ts") or 0.0)
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC")
        kind = str(row.get("kind") or row.get("action") or "?")
        trace_id = str(row.get("trace_id") or "?")
        doctor = str(row.get("doctor") or "?")
        lines.append(f"- **{iso}** · `{kind}` · doctor: _{doctor}_ · trace `{trace_id[:24]}`")
        quote = row.get("architect_quote") or row.get("architect_whatsapp_quote")
        if quote:
            for chunk in str(quote).split("\n"):
                lines.append(f"  > {chunk}")
        summary = row.get("summary")
        if summary:
            lines.append(f"  - {str(summary)[:280]}")
        lines.append("")
    return lines


def _section_surgeries(target_date: date_cls, state_dir: Path) -> List[str]:
    start_ts, end_ts = _day_window(target_date)
    rows = _tail_jsonl(state_dir / "ide_stigmergic_trace.jsonl")
    surgery_rows: List[Dict[str, Any]] = []
    for row in rows:
        try:
            ts = float(row.get("ts") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        if not (start_ts <= ts < end_ts):
            continue
        kind = str(row.get("kind") or row.get("action") or "")
        if kind in ("LLM_SURGERY_COMPLETE", "CODEX_WORK_RECEIPT"):
            surgery_rows.append(row)
    lines: List[str] = []
    if not surgery_rows:
        lines.append("_No surgery completions recorded today._")
        lines.append("")
        return lines
    surgery_rows.sort(key=lambda r: float(r.get("ts") or 0.0))
    for row in surgery_rows:
        ts = float(row.get("ts") or 0.0)
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC")
        doctor = str(row.get("doctor") or "?")
        model = str(row.get("model") or "")
        trace_id = str(row.get("trace_id") or "?")
        summary = str(row.get("summary") or row.get("intent") or "").strip()
        lines.append(
            f"- **{iso}** · _{doctor}_"
            + (f" ({model})" if model else "")
            + f" · trace `{trace_id[:24]}`"
        )
        if summary:
            lines.append(f"  - {summary[:320]}")
        files = row.get("files_touched") or row.get("files") or []
        if isinstance(files, list) and files:
            preview = ", ".join(str(f).split(" (")[0] for f in files[:5])
            extra = f" (+{len(files) - 5} more)" if len(files) > 5 else ""
            lines.append(f"  - files: {preview}{extra}")
        lines.append("")
    return lines


def _section_open_threads(state_dir: Path) -> List[str]:
    """Surface §7.13 deferred-care threads and the like.

    The covenant explicitly names deferred owner-body care as an open
    receipt the swarm carries until closed. This section pulls anything
    we can see on disk that mentions the §7.13 keywords.
    """
    rows = _tail_jsonl(state_dir / "ide_stigmergic_trace.jsonl")
    care_signals = (
        "§7.13",
        "deferred_care",
        "owner_body_events",
        "dental",
        "dentist",
        "care_appointment",
    )
    care_rows: List[Dict[str, Any]] = []
    for row in rows[-200:]:
        flat_str = json.dumps(row, default=str).lower()
        if any(s.lower() in flat_str for s in care_signals):
            care_rows.append(row)
    lines: List[str] = []
    if not care_rows:
        lines.append("_No deferred-care threads currently surfaced on the trace tail._")
        lines.append(
            "_Architect: this section will populate once §7.13 receipts (e.g. care_appointment rows) "
            "are written to `.sifta_state/owner_body_events.jsonl`._"
        )
        lines.append("")
        return lines
    for row in care_rows[-5:]:
        ts = float(row.get("ts") or 0.0)
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ts else "?"
        trace_id = str(row.get("trace_id") or "?")
        summary = str(row.get("summary") or row.get("intent") or "")[:240]
        lines.append(f"- **{iso}** · trace `{trace_id[:24]}` — {summary}")
    lines.append("")
    return lines


def render_minimal_digest(
    target: Any = None,
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> str:
    """Render a markdown digest from the consciousness ledger + trace
    without depending on Codex's builder. Used as a fallback so the
    archive can always write *something* useful.
    """
    target_date = _utc_date(target)
    base = Path(state_dir) if state_dir is not None else _STATE
    owner = _load_json(base / "owner_genesis.json")
    owner_name = str(owner.get("owner_name") or "the Architect")
    silicon = str(owner.get("silicon") or "")

    iso_date = target_date.isoformat()
    nowts = float(time.time() if now is None else now)
    gen_iso = datetime.fromtimestamp(nowts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out: List[str] = []
    out.append(f"# Architect daily memory digest — {iso_date}")
    out.append("")
    out.append(
        f"_For {owner_name}"
        + (f" · silicon {silicon}" if silicon else "")
        + f" · generated {gen_iso} by `{TRUTH_LABEL}` (minimal renderer)._"
    )
    out.append("")
    out.append(
        "> Memory symbiosis: Alice carries the work, this page carries why. "
        "When your brain is tired and you cannot remember what you were doing, "
        "this is the receipt your own teaching left on disk."
    )
    out.append("")

    out.append("## What Alice reflected on today")
    out.append("")
    out.extend(_section_reflections(target_date, base))

    out.append("## Architect moments captured today")
    out.append("")
    out.extend(_section_architect_moments(target_date, base))

    out.append("## Swarm surgeries completed today")
    out.append("")
    out.extend(_section_surgeries(target_date, base))

    out.append("## Open threads (§7.13 deferred care + similar)")
    out.append("")
    out.extend(_section_open_threads(base))

    out.append("---")
    out.append("")
    out.append(
        f"_Archived by `swarm_architect_memory_archive.write_daily_digest`. "
        f"Re-generate with `force=True` to refresh this page from current ledger state._"
    )
    out.append("")
    return "\n".join(out)


# ── compose with Codex's builder when available ──────────────────────────


def _try_codex_builder(target_date: date_cls, state_dir: Optional[Path]) -> Optional[str]:
    """Defer to :mod:`System.swarm_architect_memory_digest` if it exists.

    Codex's module is expected (per trace ``22d615a1``) to expose either
    ``build_digest_markdown(target)`` or ``render_digest(target)`` — we
    try both names. Any exception causes us to fall back to the minimal
    renderer.
    """
    try:
        import importlib

        digest_mod = importlib.import_module("System.swarm_architect_memory_digest")
    except Exception:
        return None
    for fname in ("build_digest_markdown", "render_digest", "build_digest", "digest_for_date"):
        fn = getattr(digest_mod, fname, None)
        if callable(fn):
            try:
                md = fn(target_date) if state_dir is None else fn(target_date, state_dir=state_dir)
                if isinstance(md, str) and md.strip():
                    return md
            except TypeError:
                # Try without the kwarg
                try:
                    md = fn(target_date)
                    if isinstance(md, str) and md.strip():
                        return md
                except Exception:
                    continue
            except Exception:
                continue
    return None


# ── write / persist ──────────────────────────────────────────────────────


def write_daily_digest(
    target: Any = None,
    *,
    force: bool = False,
    output_dir: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Render and persist the daily digest for ``target`` date.

    Returns a dict with ``{"path", "date", "wrote", "renderer", "bytes"}``.
    ``wrote`` is False when the file already exists and ``force`` is False.
    ``renderer`` is ``"codex"`` if Codex's builder produced the markdown,
    or ``"minimal"`` if the fallback renderer was used.
    """
    target_date = _utc_date(target)
    base_dir = Path(output_dir) if output_dir is not None else _DIGEST_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    path = _digest_path_for(target_date, output_dir=output_dir)

    if path.exists() and not force:
        try:
            existing_bytes = path.stat().st_size
        except OSError:
            existing_bytes = 0
        return {
            "path": str(path),
            "date": target_date.isoformat(),
            "wrote": False,
            "renderer": "skipped-exists",
            "bytes": existing_bytes,
        }

    md = _try_codex_builder(target_date, state_dir)
    renderer = "codex"
    if not md:
        md = render_minimal_digest(target_date, state_dir=state_dir, now=now)
        renderer = "minimal"

    path.write_text(md, encoding="utf-8")
    return {
        "path": str(path),
        "date": target_date.isoformat(),
        "wrote": True,
        "renderer": renderer,
        "bytes": len(md.encode("utf-8")),
    }


__all__ = [
    "TRUTH_LABEL",
    "list_archived_digests",
    "recall_for_date",
    "render_minimal_digest",
    "write_daily_digest",
]
