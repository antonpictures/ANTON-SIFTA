"""Eval matrix panel evidence pointers — real paths only (r1021 C7).
Lane contract: trace (zero-surprise).
"""
from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
_HUMAN_SUFFIX_RE = re.compile(r"\.(human|owner|george)\b", re.IGNORECASE)


def _resolve(path_str: str, *, repo_root: Path | None = None) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (repo_root or _REPO) / path_str
    return p


def panel_evidence_rows() -> List[Dict[str, Any]]:
    """Canonical evidence map for matrix panels."""
    return [
        {"panel": "living_substrate_loc", "path": "System/swarm_code_body_inventory.py", "ledger": ".sifta_state/canonical_organ_registry_snapshot.json"},
        {"panel": "appearance_walk", "path": ".sifta_state/eval/code_body_appearance_order.jsonl", "ledger": ".sifta_state/eval/code_body_appearance_order.jsonl"},
        {"panel": "organ_field", "path": "System/swarm_canonical_organ_registry.py", "ledger": ".sifta_state/organ_field.jsonl"},
        {"panel": "self_improvement", "path": "System/swarm_self_improvement_loop.py", "ledger": ".sifta_state/self_improvement_proposals.jsonl"},
        {"panel": "effector_gate", "path": "System/swarm_effector_gate.py", "ledger": ".sifta_state/effector_gate.jsonl"},
        {"panel": "intent_nonce", "path": "System/swarm_intent_nonce_gate.py", "ledger": ".sifta_state/intent_nonce_gate.jsonl"},
        {
            "panel": "shadow_swimmer_quarantine",
            "path": "System/swarm_ide_trace_quarantine.py",
            "ledger": ".sifta_state/ide_stigmergic_trace.jsonl",
            "quarantine_ledger": ".sifta_state/ide_stigmergic_trace_quarantine.jsonl",
            "mana_is_crypto": False,
            "stgm_is_crypto": True,
        },
        {"panel": "matrix_html", "path": "tools/generate_organ_eval_matrix_v2.py", "ledger": ".sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html"},
        {"panel": "census_delta", "path": "System/swarm_census_delta.py", "ledger": ".sifta_state/eval/code_body_census_delta.jsonl"},
    ]


def _path_age_s(path: Path, *, now: float | None = None) -> float | None:
    try:
        return max(0.0, float(now if now is not None else time.time()) - path.stat().st_mtime)
    except OSError:
        return None


# r1744 cut #1 from WCT r1743 §2 (the jewel-beetle failure). Hoffman's male
# beetle mates with a beer bottle because "dimpled, glossy, brown" was the only
# icon it ever had. This scorer had the same shape of bug: it asked whether a
# ledger FILE exists and how fresh its mtime is, never whether the ledger holds
# a single row. An empty-but-freshly-touched ledger scored green while proving
# nothing — .sifta_state/reply_language_mismatch.jsonl is exactly that today:
# 0 bytes, mtime hours old. Existence is the icon; rows are the evidence.
def ledger_evidence_rows(path: Path) -> int | None:
    """Count the rows of evidence a ledger actually holds.

    Append ledgers (.jsonl) are counted by non-blank lines. Snapshot artifacts
    (.json, .html, …) are not row-structured, so a non-empty file counts as one
    piece of evidence and an empty one as zero. None means unreadable — unknown
    is never silently treated as evidence.
    """
    try:
        if not path.is_file():
            return None
        size = path.stat().st_size
    except OSError:
        return None
    if size == 0:
        return 0
    if path.suffix.lower() != ".jsonl":
        return 1
    rows = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                rows += chunk.count(b"\n")
            handle.seek(max(0, size - 1))
            if handle.read(1) not in (b"\n", b""):
                rows += 1  # final line without a trailing newline
    except OSError:
        return None
    return rows


def evidence_score_for_row(
    row: Dict[str, Any],
    *,
    repo_root: str | Path | None = None,
    now: float | None = None,
    half_life_s: float = 7 * 24 * 3600.0,
) -> Dict[str, Any]:
    """Score one eval cell from concrete evidence, never prose alone."""
    root = Path(repo_root) if repo_root is not None else _REPO
    panel = str(row.get("panel") or "")
    path = str(row.get("path") or "")
    ledger = str(row.get("ledger") or "")
    evidence_path = ledger or path
    problems: List[str] = []
    if not panel:
        problems.append("missing_panel")
    if not evidence_path:
        problems.append("missing_evidence_path")
    if _HUMAN_SUFFIX_RE.search(path) or _HUMAN_SUFFIX_RE.search(ledger):
        problems.append("human_suffix_path")
    path_obj = _resolve(path, repo_root=root) if path else None
    ledger_obj = _resolve(ledger, repo_root=root) if ledger else None
    path_ok = bool(path_obj and path_obj.exists())
    ledger_ok = bool(ledger_obj and ledger_obj.exists())
    if path and not path_ok:
        problems.append("missing_path")
    if ledger and not ledger_ok:
        problems.append("missing_ledger")
    if not ledger:
        problems.append("missing_named_receipt_or_ledger")

    # An existing ledger with zero rows is a bottle, not a female beetle.
    evidence_rows = ledger_evidence_rows(ledger_obj) if ledger_ok else None
    if ledger_ok and evidence_rows == 0:
        problems.append("empty_ledger")

    age_s = _path_age_s(ledger_obj or path_obj, now=now) if (ledger_ok or path_ok) else None
    decay = 1.0
    if age_s is not None and half_life_s > 0:
        decay = math.pow(0.5, age_s / float(half_life_s))
    base_score = 0.0
    if path_ok:
        base_score += 0.35
    if ledger_ok:
        base_score += 0.65
    if not ledger_ok:
        base_score = min(base_score, 0.35)
    # A ledger that holds nothing cannot carry its 0.65 — the cell falls back to
    # what the code path alone proves, which is never enough to be green.
    if evidence_rows == 0:
        base_score = min(base_score, 0.35)
    score = round(max(0.0, min(1.0, base_score * decay)), 4)
    status = "red"
    if not problems and score >= 0.75:
        status = "green"
    elif score > 0.0 and "missing_evidence_path" not in problems:
        status = "yellow"
    return {
        "panel": panel,
        "score": score,
        "status": status,
        "path_ok": path_ok,
        "ledger_ok": ledger_ok,
        "evidence_rows": evidence_rows,
        "age_s": None if age_s is None else round(age_s, 3),
        "decay": round(decay, 4),
        "problems": problems,
    }


def score_panel_evidence_rows(
    rows: List[Dict[str, Any]] | None = None,
    *,
    repo_root: str | Path | None = None,
    now: float | None = None,
    half_life_s: float = 7 * 24 * 3600.0,
) -> Dict[str, Any]:
    scored = [
        evidence_score_for_row(
            row,
            repo_root=repo_root,
            now=now,
            half_life_s=half_life_s,
        )
        for row in (rows if rows is not None else panel_evidence_rows())
    ]
    green = sum(1 for row in scored if row["status"] == "green")
    return {
        "ok": green == len(scored) and bool(scored),
        "green_count": green,
        "total": len(scored),
        "rows": scored,
    }


def validate_panel_evidence(*, repo_root: str | Path | None = None) -> Dict[str, Any]:
    rows = panel_evidence_rows()
    problems: List[Dict[str, Any]] = []
    ok_count = 0
    for row in rows:
        path = str(row.get("path") or "")
        ledger = str(row.get("ledger") or "")
        if _HUMAN_SUFFIX_RE.search(path) or _HUMAN_SUFFIX_RE.search(ledger):
            problems.append({"panel": row["panel"], "reason": "human_suffix_path", "path": path})
            continue
        path_ok = _resolve(path, repo_root=Path(repo_root) if repo_root is not None else None).exists()
        ledger_ok = _resolve(ledger, repo_root=Path(repo_root) if repo_root is not None else None).exists()
        if not path_ok:
            problems.append({"panel": row["panel"], "reason": "missing_path", "path": path})
        elif not ledger_ok:
            problems.append({"panel": row["panel"], "reason": "missing_ledger", "ledger": ledger})
        else:
            ok_count += 1
    scored = score_panel_evidence_rows(rows, repo_root=repo_root)
    return {
        "ok": not problems and scored["ok"],
        "ok_count": ok_count,
        "green_count": scored["green_count"],
        "total": len(rows),
        "problems": problems,
        "scores": scored["rows"],
    }
