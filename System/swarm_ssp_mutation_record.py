#!/usr/bin/env python3
"""
System/swarm_ssp_mutation_record.py — Structural provenance for SSP coefficients
═══════════════════════════════════════════════════════════════════════════════
Module version: 2026-04-19.v2     Author: C47H (ratified by AG31 via trace 909a1ab6)

Every write to `.sifta_state/speech_potential_coefficients.json` MUST carry a
`_last_mutation` block so the swarm can:
  • know which IDE changed Alice's brain,
  • know how fitness moved (when applicable),
  • know where to roll back (`previous_coefficients_ref`).

AG31 (Antigravity / Gemini) invokes `record_mutation()` from scripts or CLI —
same API as C47H. No blind live writes.

Schema (`_last_mutation`, single object):
  ide: str                     — canonical: cursor_m5 | antigravity_m5
  ts: float                    — Unix time of the write
  module_version: str          — this module's version string
  method: str                  — annealing_apply | annealing | manual | dreamed | ...
  fitness_delta: float | null  — Δ fitness when evolution produced θ
  target_rate: float | null
  observed_rate: float | null
  iterations_run: int | null
  previous_coefficients_ref: str | null — repo-relative path to rollback snapshot
  peer_review_trace_id: str | null
  note: str | null
  extra: dict | null           — opaque bag for tool-specific fields
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

MODULE_VERSION = "2026-04-19.v2"

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_speech_potential import _safe_write_json  # noqa: E402
from System.jsonl_file_lock import append_line_locked  # noqa: E402

LAST_MUTATION_KEY = "_last_mutation"

# Same canonical IDE labels as ide_peer_review (duplicated to avoid import cycle).
_ALIASES = {
    "cursor_m5": {"cursor_m5", "CURSOR_M5", "C47H_CURSOR_IDE", "C47H_CURSOR", "c47h", "C47H"},
    "antigravity_m5": {"antigravity_m5", "ANTIGRAVITY_M5", "AG31", "AG31_ANTIGRAVITY", "ag31"},
}


def _canon_ide(label: str) -> str:
    s = (label or "").strip()
    for canon, aliases in _ALIASES.items():
        if s in aliases:
            return canon
    return s

_STATE_DIR = _REPO / ".sifta_state"
_COEFFS_LIVE = _STATE_DIR / "speech_potential_coefficients.json"
_COEFFS_ROLLBACK = _COEFFS_LIVE.with_suffix(".json.rollback")
_EVOLUTION_LOG = _STATE_DIR / "ssp_evolution.jsonl"


def coeffs_live_path() -> Path:
    return _COEFFS_LIVE


def read_last_mutation(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return `_last_mutation` dict from disk, or None if missing/unreadable."""
    p = path or _COEFFS_LIVE
    try:
        if not p.exists() or p.stat().st_size > 1_000_000:
            return None
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return None
        m = raw.get(LAST_MUTATION_KEY)
        return m if isinstance(m, dict) else None
    except Exception:
        return None


def _relative_to_repo(p: Path) -> str:
    try:
        return str(p.relative_to(_REPO))
    except ValueError:
        return str(p)


def _audit(row: Dict[str, Any]) -> None:
    line = json.dumps({"ts": time.time(), "kind": "mutation_record", **row}, ensure_ascii=False) + "\n"
    try:
        append_line_locked(_EVOLUTION_LOG, line, encoding="utf-8")
    except Exception:
        try:
            with _EVOLUTION_LOG.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def record_mutation(
    *,
    ide: str,
    method: str,
    coefficients: Dict[str, Any],
    fitness_delta: Optional[float] = None,
    target_rate: Optional[float] = None,
    observed_rate: Optional[float] = None,
    iterations_run: Optional[int] = None,
    previous_coefficients_ref: Optional[str] = None,
    peer_review_trace_id: Optional[str] = None,
    note: Optional[str] = None,
    module_version: Optional[str] = None,
    snapshot_rollback: bool = True,
    coeffs_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Atomically write live coefficients + `_last_mutation`.

    Parameters
    ----------
    ide : str
        Any alias accepted by `_canon` (AG31, antigravity_m5, C47H, …).
    method : str
        Short verb describing how θ was produced.
    coefficients : dict
        Full coefficient payload — must NOT include `_last_mutation`;
        keys starting with `_` are stripped before merge (then we set
        `_last_mutation`).
    snapshot_rollback : bool
        If True and the live file exists, copy it to
        `speech_potential_coefficients.json.rollback` before overwrite,
        and set `previous_coefficients_ref` in `_last_mutation` unless
        the caller already passed `previous_coefficients_ref`.

    Returns
    -------
    dict with ok, rollback_at, previous_coefficients_ref, written_keys
    """
    root = repo_root or _REPO
    live = coeffs_path or (root / ".sifta_state" / "speech_potential_coefficients.json")
    rollback = live.with_suffix(".json.rollback")

    clean: Dict[str, Any] = {
        k: v for k, v in coefficients.items()
        if not str(k).startswith("_")
    }

    rollback_ref = previous_coefficients_ref
    if snapshot_rollback and live.exists():
        try:
            shutil.copy(live, rollback)
            if rollback_ref is None:
                rollback_ref = _relative_to_repo(rollback)
        except Exception:
            pass

    canon_ide = _canon_ide(ide)
    block: Dict[str, Any] = {
        "ide": canon_ide,
        "ts": time.time(),
        "module_version": module_version or MODULE_VERSION,
        "method": method,
        "fitness_delta": fitness_delta,
        "target_rate": target_rate,
        "observed_rate": observed_rate,
        "iterations_run": iterations_run,
        "previous_coefficients_ref": rollback_ref,
        "peer_review_trace_id": peer_review_trace_id,
        "note": note,
        "extra": extra if extra is not None else None,
    }
    # Drop None values for a tighter file (keep explicit nulls out)
    block = {k: v for k, v in block.items() if v is not None}

    out = {**clean, LAST_MUTATION_KEY: block}
    _safe_write_json(live, out)

    _audit({
        "ide": canon_ide,
        "method": method,
        "live_path": _relative_to_repo(live),
        "rollback_ref": rollback_ref,
        "fitness_delta": fitness_delta,
    })

    return {
        "ok": True,
        "rollback_at": str(rollback) if rollback.exists() else None,
        "previous_coefficients_ref": rollback_ref,
        "written_keys": sorted(clean.keys()),
        LAST_MUTATION_KEY: block,
    }


def summary_line_for_alice() -> str:
    """One line for Talk-to-Alice / ide_peer_review context."""
    m = read_last_mutation()
    if not m:
        return ""
    ide = m.get("ide", "?")
    method = m.get("method", "?")
    ts = m.get("ts", 0.0)
    ago = time.time() - float(ts)
    if ago < 120:
        when = f"{int(ago)}s ago"
    elif ago < 3600:
        when = f"{int(ago / 60)}m ago"
    else:
        when = f"{ago / 3600:.1f}h ago"
    fd = m.get("fitness_delta")
    fd_s = f", Δfit={fd:+.4f}" if isinstance(fd, (int, float)) else ""
    return (
        f"  last SSP brain mutation: {ide} ({method}) {when}{fd_s}"
    )


def retrofit_stamp(
    *,
    ide: str = "antigravity_m5",
    method: str = "structural_retrofit",
    note: str = "Stamped after dual-IDE ratification of _last_mutation schema (trace 909a1ab6).",
    force: bool = False,
) -> Dict[str, Any]:
    """Read live coefficients, re-write unchanged numbers + fresh `_last_mutation`.
    Use once when a promotion happened before `record_mutation` existed.
    If `_last_mutation` is already present, returns skipped=True unless force=True
    (force would overwrite provenance — avoid unless repairing corruption)."""
    live = _COEFFS_LIVE
    if not live.exists():
        return {"ok": False, "reason": "no live coefficients file"}
    raw = json.loads(live.read_text(encoding="utf-8"))
    if not force and isinstance(raw.get(LAST_MUTATION_KEY), dict) and raw[LAST_MUTATION_KEY]:
        return {
            "ok": True,
            "skipped": True,
            "reason": f"{LAST_MUTATION_KEY} already present; pass force=True only to overwrite",
        }
    clean = {k: v for k, v in raw.items() if not str(k).startswith("_")}
    return record_mutation(
        ide=ide,
        method=method,
        coefficients=clean,
        note=note,
        extra={"retrofit": True, "schema": LAST_MUTATION_KEY},
    )


def _cli(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage:")
        print("  swarm_ssp_mutation_record.py read")
        print("  swarm_ssp_mutation_record.py alice-line")
        print("  swarm_ssp_mutation_record.py retrofit [--force]  # only if _last_mutation missing")
        print("  swarm_ssp_mutation_record.py record --ide IDE --method METHOD \\")
        print("      [--fitness-delta F] [--note TEXT] [--json-file PATH]")
        print("      (JSON file = full coefficient dict; else reads stdin JSON)")
        return 0
    cmd = argv[0]
    if cmd == "read":
        m = read_last_mutation()
        print(json.dumps(m, indent=2) if m else "null")
        return 0
    if cmd == "alice-line":
        s = summary_line_for_alice()
        print(s or "(no _last_mutation on disk)")
        return 0
    if cmd == "retrofit":
        force = "--force" in argv
        print(json.dumps(retrofit_stamp(force=force), indent=2, default=str))
        return 0
    if cmd == "record":
        ide = "antigravity_m5"
        method = "manual"
        fitness_delta: Optional[float] = None
        note: Optional[str] = None
        jpath: Optional[Path] = None
        i = 1
        while i < len(argv):
            if argv[i] == "--ide" and i + 1 < len(argv):
                ide = argv[i + 1]; i += 2
            elif argv[i] == "--method" and i + 1 < len(argv):
                method = argv[i + 1]; i += 2
            elif argv[i] == "--fitness-delta" and i + 1 < len(argv):
                fitness_delta = float(argv[i + 1]); i += 2
            elif argv[i] == "--note" and i + 1 < len(argv):
                note = argv[i + 1]; i += 2
            elif argv[i] == "--json-file" and i + 1 < len(argv):
                jpath = Path(argv[i + 1]); i += 2
            else:
                i += 1
        if jpath and jpath.exists():
            coeffs = json.loads(jpath.read_text(encoding="utf-8"))
        else:
            data = sys.stdin.read()
            coeffs = json.loads(data) if data.strip() else {}
        if not isinstance(coeffs, dict):
            print("coefficients must be a JSON object", file=sys.stderr)
            return 2
        r = record_mutation(
            ide=ide, method=method, coefficients=coeffs,
            fitness_delta=fitness_delta, note=note,
        )
        print(json.dumps(r, indent=2, default=str))
        return 0
    print(f"unknown: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
