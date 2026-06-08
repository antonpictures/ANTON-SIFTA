#!/usr/bin/env python3
"""
System/swarm_app_focus_reader.py — Generic typed reader for app_focus.jsonl
============================================================================
StigAuth: SIFTA_APP_FOCUS_READER_V0

Apps publish via :func:`System.swarm_app_focus.publish_focus`. This module
is the *generic* typed reader complement: given an alias set for a target
app, return the latest matching focus row as a normalised
:class:`AppFocusSnapshot`.

It is the seam that lets Alice answer "what is on the <app> screen?" for
any MDI app, not only the Ace reading lesson (whose lesson-cue-aware
reader stays in :mod:`System.swarm_acer_lesson_context`).

Design contract — IDE_BOOT_COVENANT §7.6 + §7.16:
    * apps publish; Alice reads receipts. No visual guessing.
    * generic seam — no per-app branching in this module.
    * tail-byte scan keeps reads bounded as the ledger grows.
    * a missing receipt is a missing receipt — never invent a scene.

Architect direction (2026-05-16): "teach the OS its own app contents and
how to see them and use them." Ace was the worked first example. This
module is the generalisation other apps' typed readers can adopt later.

Truth label: ``SIFTA_APP_FOCUS_READER_V0``.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = REPO_ROOT / ".sifta_state" / "app_focus.jsonl"
DEFAULT_MANIFEST = REPO_ROOT / "Applications" / "apps_manifest.json"
DEFAULT_HELP_DIR = REPO_ROOT / "Documents" / "app_help"
DEFAULT_MAX_AGE_S = 900.0
DEFAULT_TAIL_BYTES = 65536

# Metadata keys an app may use to declare a canonical app name even when the
# top-level ``app`` field is a vendor label (e.g. ``Acer`` vs ``WordAce`` vs
# ``Ace`` during the rename window). New apps should set ``app_canonical``;
# the older ``lesson_app`` key stays in the default tuple for back-compat
# with swarm_acer_lesson_context-style rows.
DEFAULT_CANONICAL_KEYS: tuple[str, ...] = ("lesson_app", "app_canonical", "canonical_app")


@dataclass
class AppFocusSnapshot:
    """Normalised view of one ``app_focus.jsonl`` row.

    All string fields are stripped; ``metadata`` is a plain dict copy.
    ``age_s`` is computed against the reader's ``now`` reference at read
    time, so it is meaningful even when ``ts`` is missing (0.0).
    """

    app: str
    detail: str
    tab: str
    selection: str
    metadata: Dict[str, Any]
    ts: float
    age_s: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "app": self.app,
            "detail": self.detail,
            "tab": self.tab,
            "selection": self.selection,
            "metadata": dict(self.metadata),
            "ts": self.ts,
            "age_s": self.age_s,
        }


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalise_aliases(aliases: Union[str, Iterable[str]]) -> set[str]:
    if isinstance(aliases, str):
        items: list[str] = [aliases]
    else:
        items = list(aliases or [])
    return {_normalise(a) for a in items if _normalise(a)}


def _safe_slug(app_name: str) -> str:
    import re

    cleaned = re.sub(r"[^\w\-]+", "_", (app_name or "unknown")).strip("_")
    return cleaned.lower() or "unknown"


def _load_manifest(path: Optional[Path] = None) -> Dict[str, Any]:
    manifest_path = Path(path) if path is not None else DEFAULT_MANIFEST
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _manifest_match_name(name: str, manifest: Dict[str, Any]) -> str:
    norm = _normalise(name)
    if not norm:
        return ""
    for title, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        candidates = [str(title)]
        legacy = entry.get("legacy_names")
        if isinstance(legacy, list):
            candidates.extend(str(item) for item in legacy)
        if norm in {_normalise(item) for item in candidates}:
            return str(title)
    return ""


def _canonical_app_from_snapshot(
    snap: AppFocusSnapshot,
    manifest: Dict[str, Any],
    canonical_keys: Sequence[str] = DEFAULT_CANONICAL_KEYS,
) -> str:
    candidates: List[str] = []
    for key in canonical_keys:
        val = snap.metadata.get(key)
        if val:
            candidates.append(str(val))
    if snap.app:
        candidates.append(snap.app)
    for candidate in candidates:
        match = _manifest_match_name(candidate, manifest)
        if match:
            return match
    for candidate in candidates:
        clean = str(candidate or "").strip()
        if clean:
            return clean
    return ""


def _resolve_ledger(
    root: Optional[Path],
    state_dir: Optional[Path],
    ledger_path: Optional[Path],
) -> Path:
    if ledger_path is not None:
        return Path(ledger_path)
    if state_dir is not None:
        return Path(state_dir) / "app_focus.jsonl"
    if root is not None:
        return Path(root) / ".sifta_state" / "app_focus.jsonl"
    return DEFAULT_LEDGER


def _tail_rows(path: Path, max_bytes: int) -> List[Dict[str, Any]]:
    """Return parsed dict rows from the last ``max_bytes`` of the ledger.

    Malformed lines and the partial first line of the tail window are
    silently skipped — this reader is read-only and must not crash on a
    half-written row.
    """
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


def _row_matches(
    row: Dict[str, Any],
    aliases: set[str],
    canonical_keys: Sequence[str],
) -> bool:
    """Return True if ``row``'s app or canonical-key metadata matches any
    alias. Empty alias set matches every row (newest-wins semantics)."""
    if not aliases:
        return True
    if _normalise(row.get("app")) in aliases:
        return True
    md = row.get("metadata")
    if not isinstance(md, dict):
        return False
    for key in canonical_keys:
        if _normalise(md.get(key)) in aliases:
            return True
    return False


def _row_to_snapshot(row: Dict[str, Any], now_f: float) -> AppFocusSnapshot:
    try:
        ts = float(row.get("ts") or 0.0)
    except (TypeError, ValueError):
        ts = 0.0
    age = max(0.0, now_f - ts) if ts > 0 else 0.0
    md = row.get("metadata")
    if not isinstance(md, dict):
        md = {}
    return AppFocusSnapshot(
        app=str(row.get("app") or "").strip(),
        detail=str(row.get("detail") or "").strip(),
        tab=str(row.get("tab") or "").strip(),
        selection=str(row.get("selection") or "").strip(),
        metadata=dict(md),
        ts=ts,
        age_s=age,
    )


def latest_focus_for(
    aliases: Union[str, Iterable[str]] = (),
    *,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    canonical_keys: Sequence[str] = DEFAULT_CANONICAL_KEYS,
    max_bytes: int = DEFAULT_TAIL_BYTES,
    now: Optional[float] = None,
) -> Optional[AppFocusSnapshot]:
    """Return the newest focus row whose ``app`` (or canonical-key
    metadata) matches the given alias set, or ``None`` when nothing
    fresh is on the ledger.

    Alias matching is exact after each candidate is normalised to
    ``str(x).strip().lower()``. An empty alias set means *match-anything*
    (newest row regardless of app).

    A row with ``ts`` older than ``max_age_s`` is skipped. Rows missing
    ``ts`` are kept (their ``age_s`` is reported as ``0.0``).
    """
    norm_aliases = _normalise_aliases(aliases)
    path = _resolve_ledger(root, state_dir, ledger_path)
    now_f = float(time.time() if now is None else now)
    rows = _tail_rows(path, max_bytes)
    for row in reversed(rows):
        if not _row_matches(row, norm_aliases, canonical_keys):
            continue
        snap = _row_to_snapshot(row, now_f)
        if snap.ts > 0 and snap.age_s > max_age_s:
            continue
        return snap
    return None


def recent_focus_for(
    aliases: Union[str, Iterable[str]] = (),
    *,
    n: int = 5,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    canonical_keys: Sequence[str] = DEFAULT_CANONICAL_KEYS,
    max_bytes: int = DEFAULT_TAIL_BYTES,
    now: Optional[float] = None,
) -> List[AppFocusSnapshot]:
    """Return up to ``n`` most-recent matching snapshots, newest first.

    Same matching semantics as :func:`latest_focus_for`.
    """
    if n <= 0:
        return []
    norm_aliases = _normalise_aliases(aliases)
    path = _resolve_ledger(root, state_dir, ledger_path)
    now_f = float(time.time() if now is None else now)
    rows = _tail_rows(path, max_bytes)
    out: List[AppFocusSnapshot] = []
    for row in reversed(rows):
        if not _row_matches(row, norm_aliases, canonical_keys):
            continue
        snap = _row_to_snapshot(row, now_f)
        if snap.ts > 0 and snap.age_s > max_age_s:
            continue
        out.append(snap)
        if len(out) >= n:
            break
    return out


def generic_app_focus_prompt_block(
    aliases: Union[str, Iterable[str]],
    *,
    app_label: Optional[str] = None,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    canonical_keys: Sequence[str] = DEFAULT_CANONICAL_KEYS,
    now: Optional[float] = None,
    metadata_field_cap: int = 8,
) -> str:
    """Return a receipt-anchored prompt block for the latest focus row that
    matches ``aliases`` — or ``""`` when no fresh receipt exists.

    The block deliberately names the app and the receipt age so Alice can
    cite the receipt instead of inventing a scene (§7.16).
    """
    snap = latest_focus_for(
        aliases,
        root=root,
        state_dir=state_dir,
        ledger_path=ledger_path,
        max_age_s=max_age_s,
        canonical_keys=canonical_keys,
        now=now,
    )
    if snap is None:
        return ""
    label = (app_label or snap.app or "this app").strip() or "this app"
    age = int(round(float(snap.age_s or 0.0)))
    parts: List[str] = [
        f"APP SCREEN STATE ({label}) — receipt from app_focus.jsonl, not visual guessing:"
    ]
    if snap.detail:
        parts.append(f"Detail: {snap.detail}")
    if snap.tab:
        parts.append(f"Tab: {snap.tab}")
    if snap.selection:
        parts.append(f"Selection: {snap.selection}")
    if snap.metadata:
        capped = list(snap.metadata.items())[: max(0, int(metadata_field_cap))]
        if capped:
            kv = ", ".join(f"{k}={v!r}" for k, v in capped)
            parts.append(f"Metadata: {kv}")
    parts.append(
        f"This receipt is {age}s old. If asked what is on the {label} screen, "
        f"answer from this receipt — do not invent a scene (§7.16)."
    )
    return "\n".join(parts)


def current_focused_app(
    *,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    max_age_s: float = 30.0,
    canonical_keys: Sequence[str] = DEFAULT_CANONICAL_KEYS,
    max_bytes: int = DEFAULT_TAIL_BYTES,
    now: Optional[float] = None,
    manifest_path: Optional[Path] = None,
    help_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return the current focused app as a receipt-grounded dict.

    This is the "one focused organ" contract for Alice's global chat:
    the newest fresh ``app_focus.jsonl`` row names the current territory.
    Missing or stale focus is returned explicitly instead of guessed.
    """
    snap = latest_focus_for(
        (),
        root=root,
        state_dir=state_dir,
        ledger_path=ledger_path,
        max_age_s=max_age_s,
        canonical_keys=canonical_keys,
        max_bytes=max_bytes,
        now=now,
    )
    if snap is None:
        return {
            "ok": False,
            "reason": "no_fresh_app_focus",
            "app": "",
            "raw_app": "",
            "age_s": None,
            "source": "app_focus.jsonl",
        }

    manifest = _load_manifest(manifest_path)
    app = _canonical_app_from_snapshot(snap, manifest, canonical_keys=canonical_keys)
    entry = manifest.get(app) if isinstance(manifest.get(app), dict) else {}
    help_root = Path(help_dir) if help_dir is not None else DEFAULT_HELP_DIR
    help_path = help_root / f"{_safe_slug(app)}.md" if app else None
    health_path = ""
    if isinstance(entry, dict):
        health_path = str(entry.get("health_trace_path") or "").strip()
    if not health_path and app:
        health_path = f".sifta_state/app_health/{_safe_slug(app)}/health_trace.jsonl"
    app_summary = ""
    try:
        from System.swarm_app_help_skills import app_one_sentence_summary

        app_summary = app_one_sentence_summary(app, entry)
    except Exception:
        app_summary = ""

    return {
        "ok": True,
        "app": app,
        "raw_app": snap.app,
        "title": app,
        "detail": snap.detail,
        "tab": snap.tab,
        "selection": snap.selection,
        "metadata": dict(snap.metadata),
        "ts": snap.ts,
        "age_s": snap.age_s,
        "source": "app_focus.jsonl",
        "app_summary": app_summary,
        "help_path": str(help_path) if help_path and help_path.exists() else "",
        "app_help_policy": (
            "Carry the one-sentence manifest summary by default; read help_path only "
            "when George asks how to use this app, asks for tools/controls, or the "
            "focused task needs app-specific procedure."
        ),
        "health_trace_path": health_path,
        "manifest_category": str(entry.get("category") or "") if isinstance(entry, dict) else "",
    }


def current_focused_app_prompt_block(
    *,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    max_age_s: float = 30.0,
    now: Optional[float] = None,
    metadata_field_cap: int = 8,
    manifest_path: Optional[Path] = None,
    help_dir: Optional[Path] = None,
) -> str:
    """Render the current focused app for Alice's system prompt."""
    focus = current_focused_app(
        root=root,
        state_dir=state_dir,
        ledger_path=ledger_path,
        max_age_s=max_age_s,
        now=now,
        manifest_path=manifest_path,
        help_dir=help_dir,
    )
    if not focus.get("ok"):
        return (
            "CURRENT FOCUSED APP (app_focus.jsonl): no fresh app-focus receipt. "
            "If George asks what app is active, say no fresh receipt instead of guessing."
        )
    age = int(round(float(focus.get("age_s") or 0.0)))
    lines = [
        "CURRENT FOCUSED APP (app_focus.jsonl receipt):",
        f"- app: {focus.get('app') or '(unknown)'}",
        f"- raw_app: {focus.get('raw_app') or '(none)'}",
        f"- age_s: {age}",
    ]
    if focus.get("detail"):
        lines.append(f"- detail: {focus['detail']}")
    if focus.get("tab"):
        lines.append(f"- tab: {focus['tab']}")
    if focus.get("selection"):
        lines.append(f"- selection: {focus['selection']}")
    if focus.get("app_summary"):
        lines.append(f"- app_summary: {focus['app_summary']}")
    if focus.get("help_path"):
        lines.append(f"- help_path: {focus['help_path']}")
    if focus.get("health_trace_path"):
        lines.append(f"- health_trace_path: {focus['health_trace_path']}")
    md = focus.get("metadata") if isinstance(focus.get("metadata"), dict) else {}
    capped = list(md.items())[: max(0, int(metadata_field_cap))]
    if capped:
        lines.append("- metadata: " + ", ".join(f"{k}={v!r}" for k, v in capped))
    lines.append(
        "Rule: this is the single focused app territory right now. Use only this fresh app context unless George explicitly names another app."
    )
    lines.append(
        "App-help rule: Alice's body is hardware + SIFTA OS + apps + one global chat; "
        "keep app knowledge shallow by default, then read help_path only on app use, "
        "tool/control questions, or focused procedure need."
    )
    return "\n".join(lines)


__all__ = [
    "AppFocusSnapshot",
    "DEFAULT_CANONICAL_KEYS",
    "DEFAULT_MAX_AGE_S",
    "current_focused_app",
    "current_focused_app_prompt_block",
    "generic_app_focus_prompt_block",
    "latest_focus_for",
    "recent_focus_for",
]
