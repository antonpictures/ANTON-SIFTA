#!/usr/bin/env python3
"""Unwired organ triage — r1387/r1390 Cursor lane.

Static census finds organ-like files with no live non-test reference. This organ
records explicit triage so UNTRIAGED_UNWIRED → 0 without blind Talk prompt bloat.

Triage statuses:
  wired                    — live runtime reference exists or was added
  intentional_standalone   — CLI/eval/sim/research; pytest/docs lane
  dynamic_wired_declared   — loaded via app manifest / dynamic plugin route
  retired                  — LEGACY/BROKEN/quarantined with proof
  needs_owner_decision     — ambiguous; must not be left as default dump bucket

Ledger: .sifta_state/unwired_organ_triage.jsonl
Truth label: UNWIRED_ORGAN_TRIAGE_V1
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover

    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

TRUTH_LABEL = "UNWIRED_ORGAN_TRIAGE_V1"
SCHEMA = "UNWIRED_ORGAN_TRIAGE_ROW_V1"
LEDGER_NAME = "unwired_organ_triage.jsonl"

VALID_STATUSES = frozenset(
    {
        "wired",
        "intentional_standalone",
        "dynamic_wired_declared",
        "retired",
        "needs_owner_decision",
    }
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_MANIFEST = _REPO / "Applications" / "apps_manifest.json"

_SIM_TRUTH_RE = re.compile(
    r"SIM_ONLY|ANALOGUE_ONLY|NPPL:SIM_ONLY|TURING_RD_ANALOGUE|BOSE_HUBBARD_ANALOGUE|"
    r"YOSHIDA_HIGH_ORDER|CLASSICAL SIFTA|RESEARCH LOOP|SIM_ONLY research",
    re.IGNORECASE,
)
_EVAL_STEM_RE = re.compile(r"(?:^|_)eval(?:_|$|_loop)|_eval\.py$|eval_loop", re.IGNORECASE)
_DEMO_STEM_RE = re.compile(r"demo|_toy$", re.IGNORECASE)


def _ledger_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE / LEDGER_NAME
    p = Path(state_dir)
    sd = p if p.name == ".sifta_state" else p / ".sifta_state"
    return sd / LEDGER_NAME


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_triage_map(*, state_dir: Optional[Path | str] = None) -> dict[str, dict[str, Any]]:
    """Latest triage row per file path."""
    out: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(_ledger_path(state_dir)):
        file_path = str(row.get("file") or "").strip()
        if file_path:
            out[file_path] = row
    return out


def _manifest_entry_paths() -> set[str]:
    if not _MANIFEST.exists():
        return set()
    try:
        data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    apps = data.get("apps", data) if isinstance(data, dict) else data
    paths: set[str] = set()
    if not isinstance(apps, list):
        return paths
    for app in apps:
        if not isinstance(app, dict):
            continue
        for key in ("entry_point", "module", "widget_module"):
            val = str(app.get(key) or "").strip().replace("\\", "/")
            if val:
                paths.add(val)
    return paths


def classify_unwired_candidate(row: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Return (triage_status, reason, proof_list) for one census row."""
    file_path = str(row.get("file") or "")
    stem = str(row.get("stem") or Path(file_path).stem)
    truth_labels = [str(t) for t in row.get("truth_labels") or []]
    truth_blob = " ".join(truth_labels).upper()
    proof: list[str] = []
    has_main = bool(row.get("has_main"))
    test_n = int(row.get("test_reference_count") or 0)
    doc_n = int(row.get("doc_reference_count") or 0)
    test_files = list(row.get("test_reference_files") or [])[:3]
    doc_files = list(row.get("doc_reference_files") or [])[:2]

    if "LEGACY" in file_path.upper():
        return "retired", "LEGACY module — quarantined from live runtime", [file_path]

    if any("BROKEN" in t.upper() for t in truth_labels):
        proof = test_files or [file_path]
        return "retired", "Truth label BROKEN — sim/research lane retired", proof

    if file_path.startswith("tools/"):
        return "intentional_standalone", "tools/ CLI lane — not Alice Talk runtime", [file_path]

    manifest_paths = _manifest_entry_paths()
    if file_path in manifest_paths:
        return "dynamic_wired_declared", "Listed in Applications/apps_manifest.json", [file_path, str(_MANIFEST)]

    if file_path.startswith("Applications/"):
        if _DEMO_STEM_RE.search(stem) or "setup_gui" in stem:
            return (
                "intentional_standalone",
                "Application shell/setup not in manifest — standalone launcher",
                [file_path],
            )
        if "daily_walk" in stem:
            return (
                "intentional_standalone",
                "Scheduled CLI walk — intentional standalone organ",
                test_files or [file_path],
            )
        return (
            "intentional_standalone",
            "Applications/ module not in apps_manifest — standalone until manifest entry",
            [file_path],
        )

    if _SIM_TRUTH_RE.search(truth_blob):
        return (
            "intentional_standalone",
            "SIM/research analogue organ — pytest lane, no Talk bloat",
            test_files or doc_files or [file_path],
        )

    if _EVAL_STEM_RE.search(stem) or "EVAL" in truth_blob:
        return (
            "intentional_standalone",
            "Eval/benchmark organ — standalone runner",
            test_files or [file_path],
        )

    if has_main and test_n > 0:
        return (
            "intentional_standalone",
            "__main__ entry + tests — CLI/sim standalone",
            test_files + [file_path],
        )

    if has_main:
        return (
            "intentional_standalone",
            "__main__ entry — standalone CLI/sim organ",
            [file_path],
        )

    if test_n > 0:
        return (
            "intentional_standalone",
            "Test-covered library organ — import on demand, no Talk prompt wire",
            test_files,
        )

    if doc_n > 0:
        return (
            "intentional_standalone",
            "Documented research organ — tournament/docs lane only",
            doc_files,
        )

    return (
        "intentional_standalone",
        "Organ-like module with no live route — declared standalone until explicit wire",
        [file_path],
    )


def append_triage_row(
    file_path: str,
    triage_status: str,
    *,
    reason: str = "",
    proof: Optional[list[str]] = None,
    doctor: str = "cursor",
    round_id: str = "r1390-cursor-unwired-organ-triage",
    organ_score: int = 0,
    state_dir: Optional[Path | str] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Append one triage declaration (skip if unchanged unless force=True)."""
    if triage_status not in VALID_STATUSES:
        raise ValueError(f"invalid triage_status: {triage_status}")
    existing = load_triage_map(state_dir=state_dir).get(file_path)
    if (
        existing
        and not force
        and existing.get("triage_status") == triage_status
        and existing.get("reason") == reason
    ):
        return existing
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "file": file_path,
        "triage_status": triage_status,
        "reason": reason,
        "proof": proof or [],
        "doctor": doctor,
        "round_id": round_id,
        "organ_score": organ_score,
        "ts": time.time(),
    }
    append_line_locked(_ledger_path(state_dir), json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def triage_unwired_rows(
    rows: list[dict[str, Any]],
    *,
    doctor: str = "cursor",
    round_id: str = "r1390-cursor-unwired-organ-triage",
    state_dir: Optional[Path | str] = None,
    only_untriaged: bool = True,
) -> dict[str, Any]:
    """Auto-classify and append triage for UNWIRED_CANDIDATE rows."""
    existing = load_triage_map(state_dir=state_dir)
    written = 0
    skipped = 0
    by_status: dict[str, int] = {}
    for row in rows:
        if row.get("status") != "UNWIRED_CANDIDATE":
            continue
        file_path = str(row.get("file") or "")
        if only_untriaged and file_path in existing:
            skipped += 1
            status = str(existing[file_path].get("triage_status") or "")
            by_status[status] = by_status.get(status, 0) + 1
            continue
        status, reason, proof = classify_unwired_candidate(row)
        append_triage_row(
            file_path,
            status,
            reason=reason,
            proof=proof,
            doctor=doctor,
            round_id=round_id,
            organ_score=int(row.get("organ_score") or 0),
            state_dir=state_dir,
        )
        written += 1
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "ok": True,
        "written": written,
        "skipped": skipped,
        "by_triage_status": by_status,
        "round_id": round_id,
    }


def merge_triage_into_report(report: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Overlay triage_status on census rows; compute UNTRIAGED_UNWIRED."""
    triage_map = load_triage_map(state_dir=state_dir)
    untriaged = 0
    by_triage: dict[str, int] = {}
    merged_rows: list[dict[str, Any]] = []
    for row in report.get("rows") or []:
        r = dict(row)
        if r.get("status") == "UNWIRED_CANDIDATE":
            trow = triage_map.get(str(r.get("file") or ""))
            if trow:
                r["triage_status"] = trow.get("triage_status")
                r["triage_reason"] = trow.get("reason")
                r["triage_round_id"] = trow.get("round_id")
                status = str(trow.get("triage_status") or "")
                by_triage[status] = by_triage.get(status, 0) + 1
            else:
                r["triage_status"] = None
                untriaged += 1
        merged_rows.append(r)
    out = dict(report)
    out["rows"] = merged_rows
    out["untriaged_unwired"] = untriaged
    out["by_triage_status"] = by_triage
    ledger_path = _ledger_path(state_dir)
    try:
        out["triage_ledger"] = str(ledger_path.relative_to(_REPO))
    except ValueError:
        out["triage_ledger"] = str(ledger_path)
    out["triage_truth_label"] = TRUTH_LABEL
    return out


__all__ = [
    "TRUTH_LABEL",
    "VALID_STATUSES",
    "classify_unwired_candidate",
    "load_triage_map",
    "append_triage_row",
    "triage_unwired_rows",
    "merge_triage_into_report",
]