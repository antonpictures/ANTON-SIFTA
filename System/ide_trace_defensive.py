#!/usr/bin/env python3
"""
Defensive readers for ide_stigmergic_trace.jsonl.

Historically some rows were glued (`}{` or literal ``\\n`` between objects).
This module recovers zero or more dicts per physical line without mutating the file.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from json import JSONDecoder
from pathlib import Path
from typing import Any, Mapping

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"


def read_trace_defensive(
    path: Path | None = None,
    *,
    encoding: str = "utf-8",
) -> list[dict[str, Any]]:
    """
    Load the full ide stigmergic trace as a list of dicts.

    Recovers every valid JSON **object** per physical line, including lines
    where agents glued records with ``}{`` or a literal two-character ``\\n``
    instead of a real newline. Does not read or modify non-dict JSON values.
    The file itself is never mutated.
    """
    return list(iter_recovered_trace_rows(path=path, encoding=encoding))


def _skip_glue(s: str, idx: int) -> int:
    while idx < len(s) and s[idx] in " \t\r":
        idx += 1
    if idx < len(s) and s[idx] == "\n":
        idx += 1
        while idx < len(s) and s[idx] in " \t\r":
            idx += 1
    elif idx + 2 <= len(s) and s[idx] == "\\" and s[idx + 1] == "n":
        idx += 2
        while idx < len(s) and s[idx] in " \t\r":
            idx += 1
    return idx


def split_physical_line_to_dicts(line: str) -> list[dict[str, Any]]:
    """Return every JSON object recovered from one physical line (0..N)."""
    raw = line.strip()
    if raw.endswith("\\n"):
        raw = raw[:-2]
    if not raw:
        return []
    dec = JSONDecoder()
    objs: list[dict[str, Any]] = []
    idx = 0
    while idx < len(raw):
        while idx < len(raw) and raw[idx] in " \t\r\n":
            idx += 1
        if idx >= len(raw):
            break
        try:
            obj, end = dec.raw_decode(raw, idx)
        except json.JSONDecodeError:
            return []
        if not isinstance(obj, dict):
            return []
        objs.append(obj)
        idx = _skip_glue(raw, end)
    if idx < len(raw) and raw[idx:].strip():
        return []
    return objs


def iter_recovered_trace_rows(
    path: Path | None = None,
    *,
    encoding: str = "utf-8",
) -> Iterator[dict[str, Any]]:
    """Yield every recoverable dict from the trace file, in file order."""
    p = path or _DEFAULT_TRACE
    if not p.exists():
        return
    text = p.read_text(encoding=encoding, errors="replace")
    for physical in text.splitlines():
        if not physical.strip():
            continue
        if physical.strip().startswith("#"):
            continue
        got = split_physical_line_to_dicts(physical)
        if got:
            for o in got:
                yield o
            continue
        raw = physical.strip()
        if raw.endswith("\\n"):
            raw = raw[:-2]
        try:
            one = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(one, dict):
            yield one


def scan_trace_stats(path: Path | None = None, *, encoding: str = "utf-8") -> dict[str, int]:
    """Count physical lines, malformed (no recoverable object), and recovered row count."""
    p = path or _DEFAULT_TRACE
    physical = 0
    malformed = 0
    recovered = 0
    if not p.exists():
        return {"physical_lines": 0, "malformed_lines": 0, "recovered_rows": 0}
    for line in p.read_text(encoding=encoding, errors="replace").splitlines():
        if not line.strip():
            continue
        physical += 1
        n = len(split_physical_line_to_dicts(line))
        if n:
            recovered += n
            continue
        raw = line.strip()
        if raw.endswith("\\n"):
            raw = raw[:-2]
        try:
            json.loads(raw)
            recovered += 1
        except json.JSONDecodeError:
            malformed += 1
    return {"physical_lines": physical, "malformed_lines": malformed, "recovered_rows": recovered}


def _meta(row: Mapping[str, Any]) -> Mapping[str, Any]:
    m = row.get("meta")
    return m if isinstance(m, dict) else {}


def find_quorum_rows(
    subject: str,
    *,
    path: Path | None = None,
    limb: str | None = None,
) -> list[dict[str, Any]]:
    """Rows where meta.subject == subject (and optional meta.limb == limb)."""
    out: list[dict[str, Any]] = []
    for row in iter_recovered_trace_rows(path=path):
        meta = _meta(row)
        if meta.get("subject") != subject and row.get("subject") != subject:
            continue
        if limb is not None and meta.get("limb") != limb:
            continue
        out.append(dict(row))
    return out


def ag31_triple_ide_verdict(
    *,
    path: Path | None = None,
    subject: str = "TRIPLE_IDE_STIGMERGIC_AGREEMENT",
) -> str:
    """
    Return 'AG31' if a row exists with meta.subject, meta.limb == 'AG31',
    meta.verdict in ('AGREE', 'DIFF'). Otherwise 'MISSING_AG31'.
    """
    for row in find_quorum_rows(subject, path=path, limb="AG31"):
        meta = _meta(row)
        if meta.get("verdict") in ("AGREE", "DIFF"):
            return "AG31"
    return "MISSING_AG31"
