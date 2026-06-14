#!/usr/bin/env python3
"""r1022 seeded audit requested by Fable.

Outputs:
- Documents/AUDIT_R1022_SAMPLE.md
- .sifta_state/eval/r1022_seeded_sample_audit.jsonl
- .sifta_state/eval/r1022_c2_round_trip.jsonl
- .sifta_state/eval/r1022_c12_relabel.jsonl

This script is an audit artifact. It compares the original r1021 endurance
probe ledger against an independently derived 24-probe sample using the r1022
receipt hash prefix as the seed.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - Python without zoneinfo is not expected here.
    ZoneInfo = None  # type: ignore

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_mutation_governor_persistence import (  # noqa: E402
    save_reviewer_allowlist,
)
from System.swarm_predator_gate_writer import (  # noqa: E402
    CANONICAL_LEDGERS,
    write_ide_surgery_receipt,
)
from System.swarm_tournament_anchor import append_tournament_section, make_anchor  # noqa: E402
from tools import run_r1021_endurance_probes as endurance  # noqa: E402

SEED_HEX = "5d77725a"
SOURCE_RECEIPT_HASH = "5d77725a264b5b439ddad4cb14886b4f8e5736f72e991a3fd5c9156b5489e096"
ORIGINAL_LEDGER = _REPO / ".sifta_state" / "eval" / "r1021_endurance_probes.jsonl"
AUDIT_LEDGER = _REPO / ".sifta_state" / "eval" / "r1022_seeded_sample_audit.jsonl"
C2_LEDGER = _REPO / ".sifta_state" / "eval" / "r1022_c2_round_trip.jsonl"
C12_LEDGER = _REPO / ".sifta_state" / "eval" / "r1022_c12_relabel.jsonl"
AUDIT_DOC = _REPO / "Documents" / "AUDIT_R1022_SAMPLE.md"
TOURNAMENT = _REPO / "Documents" / "CONSCIOUSNESS_TOURNAMENT_2026-06-11.md"
TARGET_DAY = "2026-06-11"
ROUND_ID = "r1023-codex-r1022-audit"
AUDITED_ROUND_ID = "r1022-codex-fable-c1-c12-surgical-pass"
AUDITED_RECEIPT_ID = "r1022-codex-c1-c12-surgical-pass"


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


def _sanitize(text: Any, limit: int = 130) -> str:
    out = str(text or "").replace("\n", " ").replace("|", "/").strip()
    return out[:limit] + ("..." if len(out) > limit else "")


def _original_statuses() -> Dict[Tuple[str, int], Dict[str, Any]]:
    out: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for row in _iter_jsonl(ORIGINAL_LEDGER):
        try:
            key = (str(row.get("theme") or ""), int(row.get("probe") or 0))
        except Exception:
            continue
        out[key] = row
    return out


def _run_seeded_sample() -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    themes = endurance._expand_themes_to_24()  # noqa: SLF001 - audit of the same probe set.
    originals = _original_statuses()
    rows: List[Dict[str, Any]] = []
    counts = {"MATCH": 0, "MISMATCH": 0, "ORIGINAL_MISSING": 0}

    for theme, checks in themes.items():
        digest = hashlib.sha256(f"{SEED_HEX}:{theme}".encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(checks)
        probe_number = index + 1
        label, fn = checks[index]
        try:
            result = fn()
        except Exception as exc:
            result = {"ok": False, "evidence": f"exception:{type(exc).__name__}:{exc}"}
        rerun_status = endurance._status(
            bool(result.get("ok")),
            open_ok=bool(result.get("open")),
        )
        original = originals.get((theme, probe_number))
        original_status = str(original.get("status")) if original else "MISSING"
        if original is None:
            verdict = "ORIGINAL_MISSING"
        elif original_status == rerun_status:
            verdict = "MATCH"
        else:
            verdict = "MISMATCH"
        counts[verdict] += 1
        rows.append(
            {
                "schema": "R1022_SEEDED_SAMPLE_AUDIT_V1",
                "ts": time.time(),
                "seed_hex": SEED_HEX,
                "source_receipt_hash": SOURCE_RECEIPT_HASH,
                "theme": theme,
                "probe": probe_number,
                "label": label,
                "derivation": f"sha256({SEED_HEX}:{theme})={digest}; int({digest[:8]},16)%{len(checks)}={index}",
                "digest8": digest[:8],
                "original_status": original_status,
                "rerun_status": rerun_status,
                "comparison": verdict,
                "evidence": result.get("evidence", ""),
                "ledger": result.get("ledger", ""),
                "acceptance": result.get("acceptance", ""),
            }
        )
    return rows, counts


def _day_bounds() -> Tuple[float, float]:
    if ZoneInfo is None:
        start = datetime.fromisoformat(TARGET_DAY)
    else:
        start = datetime.fromisoformat(TARGET_DAY).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _row_ts(row: Dict[str, Any]) -> float | None:
    for key in ("ts", "timestamp", "time"):
        val = _coerce_float(row.get(key))
        if val is not None:
            return val
    payload = row.get("payload")
    if isinstance(payload, dict):
        return _row_ts(payload)
    return None


def _stt_histogram() -> Dict[str, Any]:
    start_ts, end_ts = _day_bounds()
    talk_rows: List[Dict[str, Any]] = []
    conversation = _REPO / ".sifta_state" / "alice_conversation.jsonl"
    for raw in _iter_jsonl(conversation):
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
        ts = _row_ts(raw)
        if ts is None or not (start_ts <= ts < end_ts):
            continue
        role = str(payload.get("role") or raw.get("role") or "").lower()
        source = str(payload.get("input_source") or payload.get("source") or raw.get("input_source") or "").lower()
        conf = _coerce_float(payload.get("stt_confidence"))
        if role == "user" and source in {"voice", "spoken", "audio"} and conf is not None:
            talk_rows.append(
                {
                    "ts": ts,
                    "confidence": conf,
                    "text": str(payload.get("text") or raw.get("text") or "")[:120],
                }
            )

    buckets = [
        ("[0.00,0.25)", 0.00, 0.25),
        ("[0.25,0.50)", 0.25, 0.50),
        ("[0.50,0.75)", 0.50, 0.75),
        ("[0.75,1.00]", 0.75, 1.0000001),
    ]
    confs = [float(r["confidence"]) for r in talk_rows]
    counts = {
        name: sum(1 for c in confs if lo <= c < hi)
        for name, lo, hi in buckets
    }
    low_rows = sorted(talk_rows, key=lambda r: float(r["confidence"]))[:12]
    wider_low = _scan_wider_stt_low_confidence(start_ts, end_ts)
    return {
        "source": str(conversation),
        "target_day": TARGET_DAY,
        "count": len(confs),
        "mean": statistics.mean(confs) if confs else None,
        "min": min(confs) if confs else None,
        "max": max(confs) if confs else None,
        "buckets": counts,
        "low_rows": low_rows,
        "has_0_24_talk": any(abs(c - 0.24) < 0.005 for c in confs),
        "has_0_41_talk": any(abs(c - 0.41) < 0.005 for c in confs),
        "wider_low_rows": wider_low[:20],
    }


def _scan_wider_stt_low_confidence(start_ts: float, end_ts: float) -> List[Dict[str, Any]]:
    lows: List[Dict[str, Any]] = []
    for path in (_REPO / ".sifta_state").glob("*.jsonl"):
        # Keep this pass bounded; only current small/active ledgers matter for the claim.
        try:
            if path.stat().st_size > 50_000_000:
                continue
        except Exception:
            continue
        for raw in _iter_jsonl(path):
            ts = _row_ts(raw)
            if ts is None or not (start_ts <= ts < end_ts):
                continue
            payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
            conf = _coerce_float(payload.get("stt_confidence"))
            if conf is None and isinstance(payload.get("rlhs"), dict):
                conf = _coerce_float(payload["rlhs"].get("stt_confidence"))
            if conf is not None and conf < 0.50:
                lows.append(
                    {
                        "ledger": path.name,
                        "ts": ts,
                        "confidence": conf,
                        "text": str(payload.get("text") or raw.get("text") or "")[:100],
                    }
                )
    return sorted(lows, key=lambda r: float(r["confidence"]))


def _run_c2_round_trip() -> Dict[str, Any]:
    reviewers = ["r1023-reviewer-a", "r1023-reviewer-b"]
    allowlist_path = _REPO / ".sifta_state" / "reviewer_allowlist.json"
    previous_text = allowlist_path.read_text(encoding="utf-8") if allowlist_path.exists() else None
    previous_was_audit_residue = False
    if previous_text:
        try:
            previous_obj = json.loads(previous_text)
            previous_was_audit_residue = (
                sorted(map(str, previous_obj.get("reviewers") or [])) == sorted(reviewers)
                and str(previous_obj.get("note") or "").startswith("r1022 C2 audit:")
            )
        except Exception:
            previous_was_audit_residue = False
    if previous_was_audit_residue:
        previous_text = None
    write_row: Dict[str, Any] = {}
    proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="not_run")
    fresh: Any = []
    try:
        write_row = save_reviewer_allowlist(
            reviewers,
            state_dir=_REPO / ".sifta_state",
            note="r1022 C2 audit: write before fresh interpreter read-back",
        )
        code = (
            "import json; "
            "from System.swarm_mutation_governor_persistence import load_reviewer_allowlist; "
            "print(json.dumps(load_reviewer_allowlist(state_dir='.sifta_state'), sort_keys=True))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            fresh = json.loads(proc.stdout.strip() or "[]")
        except Exception:
            fresh = []
    finally:
        if previous_text is None:
            try:
                allowlist_path.unlink()
            except FileNotFoundError:
                pass
        else:
            allowlist_path.write_text(previous_text, encoding="utf-8")
    ok = sorted(map(str, fresh)) == sorted(reviewers)
    row = {
        "schema": "R1022_C2_GOVERNOR_ROUND_TRIP_V1",
        "ts": time.time(),
        "status": "PASS" if ok else "FAIL",
        "write_reviewers": reviewers,
        "write_row": write_row,
        "fresh_process_reviewers": fresh,
        "fresh_process_returncode": proc.returncode,
        "fresh_process_stderr": proc.stderr.strip()[:500],
        "restart_method": "fresh_python_interpreter",
        "limitation": "No long-lived mutation governor PID was found; the persistence contract is file-backed and was verified across a new Python process.",
        "restored_after_probe": True,
        "restore_target": "absent" if previous_text is None else "previous_bytes",
        "previous_was_audit_residue": previous_was_audit_residue,
    }
    C2_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with C2_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def _write_c12_relabel() -> Dict[str, Any]:
    row = {
        "schema": "R1022_C12_RELABEL_V1",
        "ts": time.time(),
        "status": "OPEN",
        "previous_label": "CODE_PASS_HUMAN_RECEIPT_OWED",
        "new_label": "OPEN_BLOCKED_ON_GEORGE",
        "blocked_on": [
            "Restart Talk",
            "Say bare '4' after restart",
            "Ask the Pacino screen question",
        ],
        "reason": "C12 cannot close from IDE code. It requires the owner-visible post-restart Talk behavior.",
    }
    C12_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with C12_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def _fanout_arithmetic() -> Dict[str, Any]:
    per_ledger: Dict[str, int] = {}
    for name in CANONICAL_LEDGERS:
        count = 0
        for row in _iter_jsonl(_REPO / ".sifta_state" / name):
            if row.get("round_id") == AUDITED_ROUND_ID or row.get("receipt_id") == AUDITED_RECEIPT_ID:
                count += 1
        per_ledger[name] = count
    observed = sum(per_ledger.values())
    expected = 12 * len(CANONICAL_LEDGERS)
    gaps = {
        name: 12 - count
        for name, count in per_ledger.items()
        if count != 12
    }
    return {
        "schema": "R1022_FANOUT_ARITHMETIC_V1",
        "audited_round_id": AUDITED_ROUND_ID,
        "audited_receipt_id": AUDITED_RECEIPT_ID,
        "expected": expected,
        "observed": observed,
        "per_ledger": per_ledger,
        "status": "PASS" if observed == expected and not gaps else "OPEN",
        "gap": gaps,
        "note": "This counts rows already on disk. It does not backfill missing C1-C12 fan-out rows.",
    }


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_audit_doc(
    sample_rows: List[Dict[str, Any]],
    sample_counts: Dict[str, int],
    stt: Dict[str, Any],
    c2: Dict[str, Any],
    c12: Dict[str, Any],
    fanout: Dict[str, Any],
) -> str:
    mismatches = [r for r in sample_rows if r["comparison"] != "MATCH"]
    verdict = "PASS"
    if mismatches or c2.get("status") != "PASS" or c12.get("status") != "PASS" or fanout.get("status") != "PASS":
        verdict = "OPEN"

    lines: List[str] = [
        "# AUDIT_R1022_SAMPLE",
        "",
        f"**Round:** `{ROUND_ID}`",
        f"**Source receipt hash:** `{SOURCE_RECEIPT_HASH}`",
        f"**Seed:** first 8 hex = `{SEED_HEX}`",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"**Verdict:** `{verdict}`",
        "",
        "## Seed Derivation",
        "",
        "For each of the 24 endurance themes:",
        "",
        "`digest = sha256(seed_hex + ':' + theme)`",
        "",
        "`selected_probe = int(digest[0:8], 16) % 10 + 1`",
        "",
        "## 24-Row Seeded Rerun",
        "",
        "| Theme | Probe | Digest8 | Original | Rerun | Compare | Evidence |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in sample_rows:
        lines.append(
            "| {theme} | {probe} | {digest8} | {original_status} | {rerun_status} | {comparison} | {evidence} |".format(
                theme=_sanitize(row["theme"], 70),
                probe=row["probe"],
                digest8=row["digest8"],
                original_status=row["original_status"],
                rerun_status=row["rerun_status"],
                comparison=row["comparison"],
                evidence=_sanitize(row.get("evidence")),
            )
        )
    lines.extend(
        [
            "",
            "### Sample Summary",
            "",
            f"- MATCH: {sample_counts.get('MATCH', 0)}",
            f"- MISMATCH: {sample_counts.get('MISMATCH', 0)}",
            f"- ORIGINAL_MISSING: {sample_counts.get('ORIGINAL_MISSING', 0)}",
            f"- Reopened lanes: {len(mismatches)}",
            "",
            "## STT Confidence Histogram",
            "",
            f"Source: `{Path(stt['source']).relative_to(_REPO)}`",
            f"Target local day: `{stt['target_day']}`",
            f"Rows counted: {stt['count']}",
            f"Mean: {stt['mean'] if stt['mean'] is not None else 'n/a'}",
            f"Min: {stt['min'] if stt['min'] is not None else 'n/a'}",
            f"Max: {stt['max'] if stt['max'] is not None else 'n/a'}",
            "",
            "| Bucket | Count |",
            "|---|---:|",
        ]
    )
    for bucket, count in stt["buckets"].items():
        lines.append(f"| {bucket} | {count} |")
    lines.extend(
        [
            "",
            f"- Exact 0.24 in Talk ledger: {stt['has_0_24_talk']}",
            f"- Exact 0.41 in Talk ledger: {stt['has_0_41_talk']}",
            "",
            "Lowest Talk rows:",
            "",
            "| Confidence | Text |",
            "|---:|---|",
        ]
    )
    if stt["low_rows"]:
        for row in stt["low_rows"]:
            lines.append(f"| {row['confidence']:.3f} | {_sanitize(row.get('text'), 150)} |")
    else:
        lines.append("| n/a | no voice rows found |")
    lines.extend(
        [
            "",
            "Lowest wider STT rows (<0.50) across small .sifta_state ledgers:",
            "",
            "| Ledger | Confidence | Text |",
            "|---|---:|---|",
        ]
    )
    if stt["wider_low_rows"]:
        for row in stt["wider_low_rows"]:
            lines.append(
                f"| {row['ledger']} | {row['confidence']:.3f} | {_sanitize(row.get('text'), 150)} |"
            )
    else:
        lines.append("| n/a | n/a | none found |")

    lines.extend(
        [
            "",
            "## C2 Mutation Governor Round Trip",
            "",
            f"- Status: `{c2['status']}`",
            f"- Restart method: `{c2['restart_method']}`",
            f"- Limitation: {c2['limitation']}",
            f"- Ledger: `{C2_LEDGER.relative_to(_REPO)}`",
            "",
            "## C12 Relabel",
            "",
            f"- Status: `{c12['status']}`",
            f"- New label: `{c12['new_label']}`",
            f"- Blocked on: {', '.join(c12['blocked_on'])}",
            f"- Ledger: `{C12_LEDGER.relative_to(_REPO)}`",
            "",
            "## Fan-Out Arithmetic",
            "",
            f"- Expected: {fanout['expected']} rows (C1-C12 across {len(CANONICAL_LEDGERS)} ledgers)",
            f"- Observed: {fanout['observed']} rows",
            f"- Status: `{fanout['status']}`",
            "",
            "| Ledger | Count | Gap To 12 |",
            "|---|---:|---:|",
        ]
    )
    for name in CANONICAL_LEDGERS:
        count = fanout["per_ledger"].get(name, 0)
        lines.append(f"| {name} | {count} | {12 - count} |")
    lines.extend(
        [
            "",
            "## Final Audit Verdict",
            "",
            f"`r1022` remains `{verdict}` under this audit.",
        ]
    )
    if verdict == "OPEN":
        lines.append("")
        lines.append("Reasons:")
        if mismatches:
            lines.append(f"- Seeded rerun reopened {len(mismatches)} probe lane(s).")
        if c2.get("status") != "PASS":
            lines.append("- C2 round-trip did not pass.")
        if c12.get("status") != "PASS":
            lines.append("- C12 is owner-blocked and cannot be closed by code.")
        if fanout.get("status") != "PASS":
            lines.append("- C1-C12 fan-out count is not 48 on disk.")
    AUDIT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return verdict


def _append_tournament(verdict: str, sample_counts: Dict[str, int], fanout: Dict[str, Any]) -> Dict[str, Any]:
    anchor = make_anchor(round_id=ROUND_ID, seed=hashlib.sha256(f"{ROUND_ID}:{time.time()}".encode()).hexdigest())
    body = "\n".join(
        [
            f"Truth label: `R1022_AUDIT_SAMPLE_V1`.",
            "",
            f"Seeded sample audit written to `{AUDIT_DOC.relative_to(_REPO)}` using seed `{SEED_HEX}` from receipt `{SOURCE_RECEIPT_HASH}`.",
            "",
            f"Sample: MATCH={sample_counts.get('MATCH', 0)}, MISMATCH={sample_counts.get('MISMATCH', 0)}, ORIGINAL_MISSING={sample_counts.get('ORIGINAL_MISSING', 0)}.",
            f"C2 round-trip: see `{C2_LEDGER.relative_to(_REPO)}`.",
            f"C12 relabel: OPEN, blocked on George restart/say-4/Pacino receipt.",
            f"Fan-out arithmetic: observed {fanout['observed']}/{fanout['expected']} rows; status `{fanout['status']}`.",
            "",
            f"Audit verdict: `r1022 {verdict}`.",
        ]
    )
    return append_tournament_section(
        TOURNAMENT,
        title="r1023 Codex r1022 Seeded Audit",
        round_id=ROUND_ID,
        body_md=body,
        anchor=anchor,
    )


def _write_receipt(verdict: str, sample_counts: Dict[str, int], fanout: Dict[str, Any]) -> Dict[str, str]:
    receipt_id = f"{ROUND_ID}-{hashlib.sha256((verdict + str(time.time())).encode()).hexdigest()[:8]}"
    return write_ide_surgery_receipt(
        round_id=ROUND_ID,
        doctor="codex",
        model="gpt-5",
        files_touched=[
            "tools/run_r1021_endurance_probes.py",
            "tools/audit_r1022_sample.py",
            "tests/test_r1023_endurance_probe_status.py",
            "Documents/AUDIT_R1022_SAMPLE.md",
            "Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-11.md",
        ],
        tests_green="audit_script_completed",
        summary=(
            f"r1022 seeded audit verdict={verdict}; "
            f"sample_mismatch={sample_counts.get('MISMATCH', 0)}; "
            f"original_missing={sample_counts.get('ORIGINAL_MISSING', 0)}; "
            f"fanout={fanout['observed']}/{fanout['expected']}"
        ),
        receipt_id=receipt_id,
        truth_label="OBSERVED",
        extra={"audit_doc": str(AUDIT_DOC.relative_to(_REPO)), "source_receipt_hash": SOURCE_RECEIPT_HASH},
    )


def main() -> Dict[str, Any]:
    sample_rows, sample_counts = _run_seeded_sample()
    _write_jsonl(AUDIT_LEDGER, sample_rows)
    stt = _stt_histogram()
    c2 = _run_c2_round_trip()
    c12 = _write_c12_relabel()
    fanout = _fanout_arithmetic()
    verdict = _write_audit_doc(sample_rows, sample_counts, stt, c2, c12, fanout)
    tournament = _append_tournament(verdict, sample_counts, fanout)
    receipt_status = _write_receipt(verdict, sample_counts, fanout)
    result = {
        "verdict": verdict,
        "sample_counts": sample_counts,
        "stt_count": stt["count"],
        "c2_status": c2["status"],
        "c12_status": c12["status"],
        "fanout": fanout,
        "audit_doc": str(AUDIT_DOC),
        "audit_ledger": str(AUDIT_LEDGER),
        "tournament": tournament,
        "receipt_status": receipt_status,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
