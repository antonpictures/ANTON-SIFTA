#!/usr/bin/env python3
"""Sort and score We Code Together proposal backlog rows.

This organ leaves the raw backlog append-only and writes derived ledgers:

* we_code_together_to_be_coded.clean.jsonl - one canonical row per proposal family
* we_code_together_proposal_scores.jsonl - score/decision receipts
* we_code_together_proposal_sorter_runs.jsonl - run summaries

The point is not to pretend a proposal was implemented. It teaches Alice to
separate "interesting repeated words" from "code this next because it has a
receipt path, tests, and a real organ improvement."
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"

SORTER_TRUTH_LABEL = "WE_CODE_TOGETHER_PROPOSAL_SORTER_V1"
SCORE_TRUTH_LABEL = "WE_CODE_TOGETHER_PROPOSAL_SCORE_V1"
CLEAN_TRUTH_LABEL = "WE_CODE_TOGETHER_TO_BE_CODED_CLEAN_V1"
STGM_TRUTH_LABEL = "WE_CODE_TOGETHER_PROPOSAL_STGM_V1"
CODED_TRUTH_LABEL = "WE_CODE_TOGETHER_CODED_V1"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _hash_text(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:n]


def proposal_family_key(row: Dict[str, Any]) -> str:
    """Return a stable dedup key for related proposals.

    Title/task is the family. Receipt ids are deliberately not part of this key:
    repeated captures of the same proposal should collapse into one family.
    """
    title = str(row.get("title") or row.get("task") or row.get("summary") or "").strip().lower()
    if title:
        normalized = re.sub(r"[^a-z0-9_]+", " ", title)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized:
            return normalized
    preview = " ".join(str(row.get("proposal_preview") or row.get("why") or "").split())[:220]
    return "preview_" + _hash_text(preview or json.dumps(row, sort_keys=True), 18)


def proposal_receipt_id(row: Dict[str, Any]) -> str:
    rid = str(row.get("receipt_id") or row.get("task_id") or row.get("source_receipt_id") or "")
    if rid:
        return rid
    blob = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return "wct-proposal-row-" + _hash_text(blob, 12)


def _normalize_family(text: str) -> str:
    """Normalize a title/task string the same way proposal_family_key does."""
    normalized = re.sub(r"[^a-z0-9_]+", " ", str(text).strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def read_coded_index(state_dir: Optional[Path | str] = None) -> Dict[str, set]:
    """Read we_code_together_coded.jsonl into coded family keys + receipt ids.

    A lane that actually landed (code on disk, tests, §4.1 receipt) gets a coded
    row here so the sorter stops re-ranking finished work as code_next. Without
    this the workbench double-spends Alice's attention: it keeps proposing work
    that already shipped because scoring is content-only.
    """
    state = _state_dir(state_dir)
    coded_path = state / "we_code_together_coded.jsonl"
    families: set = set()
    receipts: set = set()
    for row in _read_jsonl(coded_path):
        fam = str(row.get("family_key") or "")
        if not fam:
            fam = _normalize_family(row.get("title") or row.get("task") or "")
        if fam:
            families.add(fam)
        for key in ("proposal_receipt_id", "source_receipt_id", "receipt_id"):
            rid = str(row.get(key) or "")
            if rid:
                receipts.add(rid)
    return {"families": families, "receipts": receipts}


def mark_coded(
    *,
    title: str = "",
    proposal_receipt_id: str = "",
    landed_round_id: str = "",
    landed_receipt_id: str = "",
    doctor: str = "",
    summary: str = "",
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Append a coded row so the sorter drops this family out of code_next.

    Call this after a proposal lane actually lands with tests + §4.1 receipts.
    Append-only: it records that the family shipped; it never rewrites the raw
    proposal backlog (the courtroom transcript stays intact).
    """
    state = _state_dir(state_dir)
    coded_path = state / "we_code_together_coded.jsonl"
    fam = _normalize_family(title)
    row = {
        "truth_label": CODED_TRUTH_LABEL,
        "schema": CODED_TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": "wct-coded-" + _hash_text(f"{fam}|{proposal_receipt_id}|{landed_receipt_id}", 12),
        "family_key": fam,
        "title": title,
        "proposal_receipt_id": proposal_receipt_id,
        "landed_round_id": landed_round_id,
        "landed_receipt_id": landed_receipt_id,
        "doctor": doctor,
        "summary": summary,
    }
    _append_jsonl(coded_path, row)
    return row


def rate_proposal(row: Dict[str, Any], *, duplicate_count: int = 1) -> Dict[str, Any]:
    """Score a canonical proposal row from 0.0 to 1.0."""
    title = str(row.get("title") or row.get("task") or "")
    preview = str(row.get("proposal_preview") or "")
    why = str(row.get("why") or row.get("problem") or "")
    blob = " ".join([title, preview, why]).lower()
    expected = row.get("expected_receipts")
    implementation_targets = row.get("implementation_targets")

    score = 0.18
    why_parts: List[str] = []

    if isinstance(expected, list) and expected:
        score += 0.17
        why_parts.append("has expected_receipts")
    elif "receipt" in blob:
        score += 0.10
        why_parts.append("mentions receipts")

    if "```python" in blob or re.search(r"\bdef\s+[a-zA-Z_]\w*\s*\(", preview):
        score += 0.19
        why_parts.append("contains concrete code/function")

    concrete_tokens = (
        "relational_coherence_score",
        "compute_attention_vector",
        "create_stigmergic_receipt",
        "verify_trace_chain",
        "known_content_replay",
        "stage_grok_self_type_command",
        "browser_stigmergic_memory",
        "no-double-spend",
        "no double spend",
    )
    if any(token in blob for token in concrete_tokens):
        score += 0.15
        why_parts.append("names live organ/function target")

    live_failure_tokens = (
        "duplicate",
        "missing wiring",
        "unverified",
        "dead turn",
        "stale",
        "wait",
        "clipboard drift",
        "wrong target",
        "not working",
        "remove what does not work",
    )
    if any(token in blob for token in live_failure_tokens):
        score += 0.11
        why_parts.append("addresses live failure")

    if "test" in blob or "pytest" in blob or "focused tests" in blob:
        score += 0.10
        why_parts.append("has test path")

    if row.get("source_receipt_id") or row.get("source_grok_copy_receipt"):
        score += 0.07
        why_parts.append("has source receipt")

    if isinstance(implementation_targets, list) and implementation_targets:
        score += 0.06
        why_parts.append("has implementation targets")

    priority = row.get("priority")
    if isinstance(priority, (int, float)):
        score += min(0.07, max(0.0, float(priority)) / 15.0)
        why_parts.append("priority present")

    weak_tokens = (
        "assuming the structure",
        "fully present",
        "beautiful",
        "vividly",
        "not real code",
        "generic",
    )
    if any(token in blob for token in weak_tokens) and "def " not in preview:
        score -= 0.12
        why_parts.append("weak/vague language penalty")

    if duplicate_count > 1:
        why_parts.append(f"family has {duplicate_count} captured rows")

    score = round(max(0.0, min(1.0, score)), 3)
    if score >= 0.78:
        decision = "code_next"
        stgm_delta = 0.12
    elif score >= 0.55:
        decision = "keep_backlog"
        stgm_delta = 0.05
    elif score >= 0.35:
        decision = "watch"
        stgm_delta = 0.0
    else:
        decision = "archive_candidate"
        stgm_delta = -0.02

    return {
        "score": score,
        "decision": decision,
        "stgm_delta": stgm_delta,
        "why": why_parts or ["insufficient signal"],
    }


def _score_key(row: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("task_receipt_id") or ""),
            str(row.get("family_key") or ""),
            str(row.get("decision") or ""),
            str(row.get("duplicate_of") or ""),
            str(row.get("score") or ""),
        ]
    )


def _existing_score_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for row in _read_jsonl(path):
        key = str(row.get("score_key") or "")
        if key:
            keys.add(key)
    return keys


def _append_score_once(path: Path, row: Dict[str, Any], seen: set[str]) -> bool:
    key = _score_key(row)
    row = {**row, "score_key": key}
    if key in seen:
        return False
    _append_jsonl(path, row)
    seen.add(key)
    return True


def score_and_clean_backlog(*, state_dir: Optional[Path | str] = None, limit: int = 800) -> Dict[str, Any]:
    """Build a sorted clean view and append score/STGM receipts for new decisions.

    This does not delete or rewrite the raw backlog. The raw ledger remains the
    courtroom transcript; the clean file is the ranked workbench.
    """
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)

    backlog_path = state / "we_code_together_to_be_coded.jsonl"
    clean_path = state / "we_code_together_to_be_coded.clean.jsonl"
    scores_path = state / "we_code_together_proposal_scores.jsonl"
    runs_path = state / "we_code_together_proposal_sorter_runs.jsonl"
    pulse_path = state / "we_code_together_monitor_pulse.jsonl"
    stgm_path = state / "stgm_memory_rewards.jsonl"

    raw_rows = _read_jsonl(backlog_path)[-limit:]
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in raw_rows:
        if str(row.get("status") or "") == "proposal_queued":
            key = proposal_family_key(row)
        else:
            key = "nonproposal_" + proposal_receipt_id(row)
        groups.setdefault(key, []).append(row)

    clean_rows: List[Dict[str, Any]] = []
    seen_scores = _existing_score_keys(scores_path)
    coded_index = read_coded_index(state)
    new_score_rows = 0
    new_duplicate_scores = 0
    new_canonical_scores = 0
    duplicate_rows_found = 0
    code_next_count = 0
    archive_count = 0
    coded_count = 0
    total_positive_delta = 0.0

    now = time.time()
    for family_key, family_rows in groups.items():
        duplicate_count = max(0, len(family_rows) - 1)
        duplicate_rows_found += duplicate_count

        scored = [(rate_proposal(row, duplicate_count=len(family_rows)), row) for row in family_rows]
        scored.sort(key=lambda pair: (pair[0]["score"], float(pair[1].get("ts") or 0)), reverse=True)
        rating, canonical = scored[0]
        canonical_receipt = proposal_receipt_id(canonical)
        duplicate_receipts = [proposal_receipt_id(row) for _, row in scored[1:]]

        family_receipts = {canonical_receipt, *duplicate_receipts}
        family_receipts.update(
            str(r.get("source_receipt_id") or "") for r in family_rows if r.get("source_receipt_id")
        )
        if family_key in coded_index["families"] or (family_receipts & coded_index["receipts"]):
            rating = {**rating, "decision": "already_coded"}
            coded_count += 1

        if rating["decision"] == "code_next":
            code_next_count += 1
        if rating["decision"] == "archive_candidate":
            archive_count += 1
        if rating["stgm_delta"] > 0:
            total_positive_delta += float(rating["stgm_delta"])

        sorter_receipt_id = "wct-proposal-sort-" + _hash_text(f"{family_key}|{canonical_receipt}|{rating['score']}", 12)
        clean_row = {
            **canonical,
            "truth_label": CLEAN_TRUTH_LABEL,
            "schema": CLEAN_TRUTH_LABEL,
            "proposal_family_key": family_key,
            "duplicate_count": len(family_rows),
            "duplicate_receipts": duplicate_receipts,
            "proposal_score": rating["score"],
            "sorter_decision": rating["decision"],
            "proposal_stgm_delta": rating["stgm_delta"],
            "score_why": rating["why"],
            "sorter_receipt_id": sorter_receipt_id,
            "sorter_ts": now,
        }
        clean_rows.append(clean_row)

        score_row = {
            "truth_label": SCORE_TRUTH_LABEL,
            "schema": SCORE_TRUTH_LABEL,
            "ts": now,
            "receipt_id": sorter_receipt_id,
            "task_receipt_id": canonical_receipt,
            "family_key": family_key,
            "title": str(canonical.get("title") or canonical.get("task") or ""),
            "score": rating["score"],
            "decision": rating["decision"],
            "stgm_delta": rating["stgm_delta"],
            "why": rating["why"],
            "duplicate_count": len(family_rows),
            "duplicate_of": "",
        }
        if _append_score_once(scores_path, score_row, seen_scores):
            new_score_rows += 1
            new_canonical_scores += 1

        for _, duplicate in scored[1:]:
            duplicate_receipt = proposal_receipt_id(duplicate)
            duplicate_score_row = {
                "truth_label": SCORE_TRUTH_LABEL,
                "schema": SCORE_TRUTH_LABEL,
                "ts": now,
                "receipt_id": "wct-proposal-dup-" + _hash_text(f"{family_key}|{duplicate_receipt}", 12),
                "task_receipt_id": duplicate_receipt,
                "family_key": family_key,
                "title": str(duplicate.get("title") or duplicate.get("task") or ""),
                "score": 0.0,
                "decision": "duplicate_archive",
                "stgm_delta": -0.03,
                "why": ["duplicate proposal family; keep canonical receipt only in clean workbench"],
                "duplicate_count": len(family_rows),
                "duplicate_of": canonical_receipt,
            }
            if _append_score_once(scores_path, duplicate_score_row, seen_scores):
                new_score_rows += 1
                new_duplicate_scores += 1

    decision_rank = {"code_next": 0, "keep_backlog": 1, "watch": 2, "archive_candidate": 3, "already_coded": 4}
    clean_rows.sort(
        key=lambda row: (
            decision_rank.get(str(row.get("sorter_decision") or ""), 9),
            -float(row.get("proposal_score") or 0.0),
            -float(row.get("priority") or 0.0) if isinstance(row.get("priority"), (int, float)) else 0.0,
            -float(row.get("ts") or 0.0),
        )
    )
    _write_jsonl(clean_path, clean_rows)

    signature_payload = [
        {
            "family": row.get("proposal_family_key"),
            "receipt": proposal_receipt_id(row),
            "decision": row.get("sorter_decision"),
            "score": row.get("proposal_score"),
            "duplicates": row.get("duplicate_count"),
        }
        for row in clean_rows
    ]
    clean_signature = _hash_text(json.dumps(signature_payload, ensure_ascii=False, sort_keys=True), 16)
    previous_runs = _read_jsonl(runs_path)
    previous_signature = str(previous_runs[-1].get("clean_signature") or "") if previous_runs else ""

    stgm_amount = 0.0
    if new_score_rows:
        stgm_amount = round(max(0.0, total_positive_delta) + 0.04 * new_duplicate_scores, 4)
        if stgm_amount > 0:
            _append_jsonl(
                stgm_path,
                {
                    "ts": now,
                    "truth_label": STGM_TRUTH_LABEL,
                    "app": "we_code_together",
                    "reason": "WCT_PROPOSAL_SORT_SCORE_AND_DEDUP",
                    "amount": stgm_amount,
                    "trace_id": "wct-proposal-stgm-" + _hash_text(str(now), 12),
                    "details": {
                        "new_score_rows": new_score_rows,
                        "new_duplicate_scores": new_duplicate_scores,
                        "code_next_count": code_next_count,
                    },
                },
            )

    run = {
        "truth_label": SORTER_TRUTH_LABEL,
        "schema": SORTER_TRUTH_LABEL,
        "ts": now,
        "receipt_id": "wct-proposal-sorter-run-" + _hash_text(str(now), 12),
        "raw_count": len(raw_rows),
        "family_count": len(groups),
        "clean_count": len(clean_rows),
        "duplicates_found": duplicate_rows_found,
        "new_score_rows": new_score_rows,
        "new_canonical_scores": new_canonical_scores,
        "new_duplicate_scores": new_duplicate_scores,
        "code_next_count": code_next_count,
        "archive_candidate_count": archive_count,
        "already_coded_count": coded_count,
        "stgm_awarded": stgm_amount,
        "clean_snapshot": str(clean_path),
        "clean_signature": clean_signature,
        "persisted": bool(new_score_rows or clean_signature != previous_signature),
    }
    if run["persisted"]:
        _append_jsonl(runs_path, run)

    if new_score_rows:
        _append_jsonl(
            pulse_path,
            {
                "ts": now,
                "truth_label": SORTER_TRUTH_LABEL,
                "event": "wct_proposal_sorter_ran",
                "message": (
                    f"Proposal sorter ranked {len(groups)} families; "
                    f"duplicates_found={duplicate_rows_found}; "
                    f"new_scores={new_score_rows}; stgm={stgm_amount}."
                ),
                "raw_count": len(raw_rows),
                "family_count": len(groups),
                "duplicates_found": duplicate_rows_found,
                "new_score_rows": new_score_rows,
                "stgm_awarded": stgm_amount,
            },
        )

    return run


if __name__ == "__main__":
    print(json.dumps(score_and_clean_backlog(), ensure_ascii=False, indent=2, sort_keys=True))
