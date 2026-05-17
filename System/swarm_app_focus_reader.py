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


__all__ = [
    "AppFocusSnapshot",
    "DEFAULT_CANONICAL_KEYS",
    "DEFAULT_MAX_AGE_S",
    "generic_app_focus_prompt_block",
    "latest_focus_for",
    "recent_focus_for",
]
