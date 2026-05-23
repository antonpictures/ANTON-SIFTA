#!/usr/bin/env python3
"""
System/swarm_organism_health_eval.py - bidirectional exterior health eval.

This is the second current of SIFTA eval. The interior loop seeds known
memory traces and checks outputs. This exterior probe starts from the organism's
observable skin - ledgers, receipts, tests, source files, and git-shaped species
DNA - and scores health without importing live organs or mutating what it
inspects.

Truth label: ORGANISM_HEALTH_EVAL_V1
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EVAL_DIR = _STATE / "eval"
_HEALTH_METRICS = _EVAL_DIR / "organism_health_metrics.jsonl"
_HEALTH_REPORT = _EVAL_DIR / "health_report.json"
_RECEIPTS = _STATE / "work_receipts.jsonl"


def _jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"_invalid_json": line})
    return rows


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _norm_actor(value: Any) -> str:
    text = str(value or "").lower()
    if "codex" in text or "gpt" in text or "openai" in text:
        return "codex"
    if "cowork" in text or "claude" in text or "anthropic" in text:
        return "cowork"
    if "grok" in text or "xai" in text:
        return "grok"
    if "cursor" in text:
        return "cursor"
    if "antigravity" in text or "gemini" in text:
        return "antigravity"
    return re.sub(r"[^a-z0-9]+", "", text)


def _receipt_actor(row: Dict[str, Any]) -> str:
    return _norm_actor(row.get("agent_id") or row.get("doctor") or row.get("source"))


def _registration_actor(row: Dict[str, Any]) -> str:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    return _norm_actor(row.get("doctor") or meta.get("doctor") or row.get("source_ide"))


def _receipt_ts(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("ts", row.get("timestamp", 0.0)) or 0.0)
    except Exception:
        return 0.0


def _is_ide_receipt(row: Dict[str, Any]) -> bool:
    actor_text = str(row.get("agent_id") or row.get("doctor") or row.get("source") or "").lower()
    work_type = str(row.get("work_type") or row.get("action") or "").upper()
    return (
        "ide_doctor" in actor_text
        or "codex" in actor_text
        or "cowork" in actor_text
        or "grok" in actor_text
        or work_type
        in {
            "WORK_INTENT",
            "VERIFICATION",
            "RELEASE_PUSH",
            "HANDOFF_ORDER",
            "HANDOFF_ORDERS",
            "EVAL_RUN",
            "HEALTH_EVAL_RUN",
        }
    )


def _state_paths(state_dir: Path) -> Dict[str, Path]:
    return {
        "work_receipts": state_dir / "work_receipts.jsonl",
        "ide_trace": state_dir / "ide_stigmergic_trace.jsonl",
        "memory": state_dir / "memory_ledger.jsonl",
        "execution_traces": state_dir / "execution_traces.jsonl",
    }


def _receipt_chain_discipline(state_dir: Path) -> Dict[str, Any]:
    receipts = _jsonl_rows(state_dir / "work_receipts.jsonl")
    traces = _jsonl_rows(state_dir / "ide_stigmergic_trace.jsonl")

    registrations: List[Tuple[str, float]] = []
    for row in traces:
        if row.get("action") == "LLM_REGISTRATION" or (
            row.get("kind") == "ide_registration"
            and "LLM_REGISTRATION" in str(row.get("payload", ""))
        ):
            actor = _registration_actor(row)
            if actor:
                registrations.append((actor, _receipt_ts(row)))

    checked = 0
    unsigned = 0
    for row in receipts:
        if not _is_ide_receipt(row):
            continue
        actor = _receipt_actor(row)
        if not actor:
            continue
        checked += 1
        ts = _receipt_ts(row)
        if not any(reg_actor == actor and reg_ts <= ts for reg_actor, reg_ts in registrations):
            unsigned += 1

    score = 1.0 if checked == 0 else 1.0 - (unsigned / checked)
    return {"score": round(score, 3), "unsigned": unsigned, "checked": checked}


def _required_keys_ok(name: str, row: Dict[str, Any]) -> bool:
    if "_invalid_json" in row:
        return False
    if name == "work_receipts":
        return bool(row.get("work_type") or row.get("action")) and bool(
            row.get("receipt_id") or row.get("trace_id") or row.get("output_hash")
        )
    if name == "ide_trace":
        return bool(row.get("trace_id")) and bool(row.get("action") or row.get("kind"))
    if name == "memory":
        return bool(row.get("trace_id")) and bool(row.get("raw_text"))
    return True


def _collect_targets(state_dir: Path) -> Dict[str, set]:
    paths = _state_paths(state_dir)
    trace_ids = {str(r.get("trace_id")) for r in _jsonl_rows(paths["ide_trace"]) if r.get("trace_id")}
    memory_ids = {str(r.get("trace_id")) for r in _jsonl_rows(paths["memory"]) if r.get("trace_id")}
    receipt_ids = set()
    for row in _jsonl_rows(paths["work_receipts"]):
        for key in ("receipt_id", "trace_id", "output_hash"):
            if row.get(key):
                receipt_ids.add(str(row.get(key)))
    return {"trace_id": trace_ids, "memory": memory_ids, "receipt": receipt_ids}


def _link_orphans(state_dir: Path) -> List[str]:
    targets = _collect_targets(state_dir)
    orphans: List[str] = []
    for row in _jsonl_rows(state_dir / "memory_ledger.jsonl"):
        for link in row.get("links", []) if isinstance(row.get("links"), list) else []:
            if not isinstance(link, str):
                continue
            if link.startswith("trace_id:"):
                target = link.split(":", 1)[1]
                if target not in targets["trace_id"]:
                    orphans.append(link)
            elif link.startswith("memory:"):
                target = link.split(":", 1)[1]
                if target not in targets["memory"]:
                    orphans.append(link)
            elif link.startswith("receipt:"):
                target = link.rsplit("#", 1)[-1] if "#" in link else ""
                if target not in targets["receipt"]:
                    orphans.append(link)
            elif link.startswith("doc:"):
                doc_path = _REPO / link.split(":", 1)[1]
                if not doc_path.exists():
                    orphans.append(link)
    return orphans


def _ledger_integrity(state_dir: Path) -> Dict[str, Any]:
    paths = _state_paths(state_dir)
    valid = 0
    total = 0
    required_ok = 0
    for name in ("work_receipts", "ide_trace", "memory"):
        for row in _jsonl_rows(paths[name]):
            total += 1
            if "_invalid_json" not in row:
                valid += 1
            if _required_keys_ok(name, row):
                required_ok += 1

    orphans = _link_orphans(state_dir)
    parse_score = 1.0 if total == 0 else valid / total
    schema_score = 1.0 if total == 0 else required_ok / total
    orphan_score = 1.0 if not orphans else max(0.0, 1.0 - (len(orphans) / max(1, total)))
    score = (parse_score + schema_score + orphan_score) / 3.0
    return {
        "score": round(score, 3),
        "valid": valid,
        "total": total,
        "required_ok": required_ok,
        "orphan_links": len(orphans),
        "orphan_samples": orphans[:5],
    }


def _has_evidence_link(links: Any) -> bool:
    return isinstance(links, list) and any(
        isinstance(link, str)
        and not link.startswith("note:")
        and (
            link.startswith("trace_id:")
            or link.startswith("receipt:")
            or link.startswith("doc:")
            or link.startswith("memory:")
        )
        for link in links
    )


def _epistemic_hygiene(state_dir: Path) -> Dict[str, Any]:
    memory_rows = _jsonl_rows(state_dir / "memory_ledger.jsonl")
    observed = 0
    observed_with_links = 0
    legacy_unlabeled = 0
    contamination = 0
    eval_seed_phrases = (
        "dragon attacks tuesday",
        "secret dragon plan",
        "the password is hunter2",
        "legacy fact without labels",
        "the code is in python",
    )
    fiction_markers = ("fiction_cowatch", "roleplay", "movie", "tv", "story")

    for row in memory_rows:
        if "_invalid_json" in row:
            continue
        label = row.get("epistemic_label")
        context = str(row.get("app_context", "")).lower()
        text = str(row.get("raw_text", "")).lower()
        if label is None:
            legacy_unlabeled += 1
        if label in ("OBSERVED", "WORLD"):
            observed += 1
            if _has_evidence_link(row.get("links")):
                observed_with_links += 1
        if any(phrase in text for phrase in eval_seed_phrases):
            contamination += 1
        if any(marker in context for marker in fiction_markers) and label not in (None, "FICTION"):
            contamination += 1

    evidence_rate = 1.0 if observed == 0 else observed_with_links / observed
    legacy_penalty = legacy_unlabeled / max(1, len(memory_rows))
    contamination_penalty = contamination / max(1, len(memory_rows))
    score = max(0.0, (evidence_rate * 0.6) + ((1.0 - legacy_penalty) * 0.2) + ((1.0 - contamination_penalty) * 0.2))
    return {
        "score": round(score, 3),
        "observed_with_links": observed_with_links,
        "total_observed": observed,
        "legacy_unlabeled": legacy_unlabeled,
        "contamination_flags": contamination,
        "total_memory_rows": len(memory_rows),
    }


def _organ_static_health() -> Dict[str, Any]:
    py_files = sorted((_REPO / "System").glob("*.py"))
    checked = 0
    ok = 0
    failures: List[str] = []
    for path in py_files:
        if path.name.startswith("test_"):
            continue
        checked += 1
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            ok += 1
        except Exception:
            failures.append(path.name)
    score = 1.0 if checked == 0 else ok / checked
    return {"score": round(score, 3), "ok": ok, "total": checked, "failures": failures[:10]}


def _coverage_vitals() -> Dict[str, Any]:
    system_files = sorted((_REPO / "System").glob("*.py"))
    test_roots = [p for p in (_REPO / "tests", _REPO / "Tests") if p.exists()]
    test_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in test_roots
        for path in root.glob("test*.py")
    )
    referenced = 0
    unreferenced_samples: List[str] = []
    for path in system_files:
        stem = path.stem
        if f"System.{stem}" in test_text or f"from System import {stem}" in test_text or path.name in test_text:
            referenced += 1
        elif len(unreferenced_samples) < 10:
            unreferenced_samples.append(path.name)
    score = 1.0 if not system_files else referenced / len(system_files)
    return {
        "score": round(score, 3),
        "referenced": referenced,
        "total": len(system_files),
        "unreferenced_samples": unreferenced_samples,
    }


def _fiction_leak_probe() -> Dict[str, Any]:
    from System.swarm_eval_loop import _isolated_memory_bus

    with tempfile.TemporaryDirectory(prefix="sifta_health_fiction_") as tmp:
        with _isolated_memory_bus(Path(tmp)) as bus:
            bus.remember("fiction-only dragon story", "fiction_cowatch")
            bus.remember(
                "real launch Tuesday",
                "talk_to_alice",
                epistemic_label="OBSERVED",
                links=["trace_id:healthprobe"],
            )
            block = bus.recall_context_block("dragon launch Tuesday", "talk_to_alice", top_k=5)

    fiction_absent = "dragon" not in block.lower() and "fiction-only" not in block.lower()
    observed_present = "Tuesday" in block or "tuesday" in block
    score = 1.0 if fiction_absent and observed_present else 0.0
    return {
        "score": score,
        "fiction_absent": fiction_absent,
        "observed_present": observed_present,
    }


def _write_health_receipt(report: Dict[str, Any], receipts_path: Path, metrics_path: Path) -> str:
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "work_type": "HEALTH_EVAL_RUN",
        "overall_score": report.get("overall_score"),
        "vitals": {k: v["score"] for k, v in report.get("vitals", {}).items()},
        "metrics_path": str(metrics_path),
        "source": "swarm_organism_health_eval",
    }
    _append_jsonl(receipts_path, row)
    return row["trace_id"]


def run_health_eval(
    *,
    state_dir: Path = _STATE,
    metrics_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    report_path: Optional[Path] = None,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """Run the read-only exterior-to-interior organism eval."""
    state_dir = Path(state_dir)
    metrics_path = Path(metrics_path) if metrics_path is not None else _HEALTH_METRICS
    receipts_path = Path(receipts_path) if receipts_path is not None else _RECEIPTS
    report_path = Path(report_path) if report_path is not None else _HEALTH_REPORT

    inspected_counts_before = {name: _line_count(path) for name, path in _state_paths(state_dir).items()}
    vitals = {
        "receipt_chain": _receipt_chain_discipline(state_dir),
        "ledger_integrity": _ledger_integrity(state_dir),
        "epistemic_hygiene": _epistemic_hygiene(state_dir),
        "organ_static_health": _organ_static_health(),
        "coverage": _coverage_vitals(),
        "fiction_leak": _fiction_leak_probe(),
    }
    inspected_counts_after = {name: _line_count(path) for name, path in _state_paths(state_dir).items()}

    scores = [float(v["score"]) for v in vitals.values()]
    report = {
        "ts": time.time(),
        "overall_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "vitals": vitals,
        "source_hash": {
            "work_receipts": _sha256(state_dir / "work_receipts.jsonl"),
            "ide_trace": _sha256(state_dir / "ide_stigmergic_trace.jsonl"),
            "memory": _sha256(state_dir / "memory_ledger.jsonl"),
        },
        "inspected_line_counts_before": inspected_counts_before,
        "inspected_line_counts_after": inspected_counts_after,
        "read_only_ok": inspected_counts_before == inspected_counts_after,
    }

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    for name, vital in vitals.items():
        _append_jsonl(
            metrics_path,
            {
                "ts": report["ts"],
                "vital": name,
                "score": vital["score"],
                "source": "swarm_organism_health_eval",
            },
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if write_receipt:
        report["health_receipt_id"] = _write_health_receipt(report, receipts_path, metrics_path)
    return report


def cross_check(interior_report: Dict[str, Any], exterior_report: Dict[str, Any]) -> Dict[str, Any]:
    """The inward and outward eval currents must agree on shared invariants."""
    findings: List[str] = []

    interior_pass = float(interior_report.get("pass_rate", 0.0)) >= 0.8
    exterior_fiction = (
        exterior_report.get("vitals", {})
        .get("fiction_leak", {})
        .get("score", 0.0)
        >= 0.8
    )
    if interior_pass != exterior_fiction:
        findings.append("FICTION discipline disagreement between interior and exterior eval")

    if exterior_report.get("read_only_ok") is False:
        findings.append("Exterior health eval mutated an inspected ledger")

    return {"agreement": not findings, "findings": findings}


def append_execution_trace_quarantine(*, reason: str, count: int, source_receipt: str) -> Dict[str, Any]:
    """Append-only marker for known contaminated execution trace windows."""
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "source": "swarm_organism_health_eval",
        "reason": reason,
        "count": count,
        "source_receipt": source_receipt,
        "action": "quarantine_marker_only_no_rewrite",
    }
    _append_jsonl(_STATE / "execution_traces_quarantine.jsonl", row)
    return row


__all__ = [
    "append_execution_trace_quarantine",
    "cross_check",
    "run_health_eval",
]
