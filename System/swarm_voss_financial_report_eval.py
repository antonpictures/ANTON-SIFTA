#!/usr/bin/env python3
"""Voss-style two-turn eval harness for receipt-gated report writing.

Truth label: ``SIFTA_VOSS_FINANCIAL_REPORT_EVAL_V1``.

This is the code slice behind the §4.6 Colab decode: a two-turn agent
pattern is only safe when Turn 2 (write/report) proves Turn 1
(research/tool receipt) happened first.

The harness is fixture-only. It uses no API keys, no live brokerage data,
and no cloud calls. Its job is to make the invariant testable:

    RESEARCH_PROMPT receipt -> WRITE_PROMPT may run
    missing research receipt -> WRITE_PROMPT must block

Each row carries a deterministic code eval and a small structured judge
eval, matching the Voss "dual judge" pattern without delegating truth to
an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import argparse
import hashlib
import json
import re
import time
import uuid


TRUTH_LABEL = "SIFTA_VOSS_FINANCIAL_REPORT_EVAL_V1"
EVAL_LEDGER_NAME = "voss_financial_report_eval.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"


@dataclass(frozen=True)
class FinancialReportTask:
    """One deterministic fixture task."""

    ticker: str
    focus: str
    as_of: str = "2026-03-21"

    def to_dict(self) -> Dict[str, str]:
        return {"ticker": self.ticker, "focus": self.focus, "as_of": self.as_of}

    @property
    def task_id(self) -> str:
        return _sha12(json.dumps(self.to_dict(), sort_keys=True))


@dataclass(frozen=True)
class ResearchFinding:
    """One fixture research item with a source handle."""

    source_id: str
    claim: str
    value: str

    def to_dict(self) -> Dict[str, str]:
        return {"source_id": self.source_id, "claim": self.claim, "value": self.value}


@dataclass
class EvalOutcome:
    row: Dict[str, Any]
    ok: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.row)


def fixture_task() -> FinancialReportTask:
    return FinancialReportTask(ticker="TSLA", focus="robotaxi margin risk")


def fixture_research_findings() -> List[ResearchFinding]:
    return [
        ResearchFinding(
            source_id="fixture:tesla_ir_2026q1",
            claim="capital_spend_pressure",
            value="Management guidance says capex remains elevated during robotaxi buildout.",
        ),
        ResearchFinding(
            source_id="fixture:analyst_consensus_2026",
            claim="margin_uncertainty",
            value="Consensus margin estimates remain sensitive to delivery mix and pricing.",
        ),
    ]


def instrument_research_turn(
    task: FinancialReportTask,
    findings: Sequence[ResearchFinding | Dict[str, str]],
    *,
    state_dir: Path | str | None = None,
    write: bool = True,
) -> EvalOutcome:
    """Append a Turn-1 research receipt for a fixture task."""
    normalized = [_finding_to_dict(finding) for finding in findings]
    code_ok = bool(normalized) and all(
        item.get("source_id") and item.get("claim") and item.get("value")
        for item in normalized
    )
    judge_ok = _judge_research_turn(normalized)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "kind": "TURN1_RESEARCH_RECEIPT",
        "prompt_kind": "RESEARCH_PROMPT",
        "task": task.to_dict(),
        "task_id": task.task_id,
        "input_sha12": _sha12(json.dumps(task.to_dict(), sort_keys=True)),
        "research_sha12": _sha12(json.dumps(normalized, sort_keys=True)),
        "findings": normalized,
        "code_eval": {
            "label": "pass" if code_ok else "fail",
            "score": 1 if code_ok else 0,
            "checks": {
                "has_findings": bool(normalized),
                "all_findings_have_sources": all(bool(item.get("source_id")) for item in normalized),
                "all_findings_have_claims": all(bool(item.get("claim")) for item in normalized),
                "all_findings_have_values": all(bool(item.get("value")) for item in normalized),
            },
        },
        "judge_eval": judge_ok,
        "truth_class": "OBSERVED" if code_ok and judge_ok["faithful"] else "FORBIDDEN",
    }
    _stamp(row)
    if write:
        _append_row(_ledger_path(state_dir), row)
    return EvalOutcome(row=row, ok=row["truth_class"] == "OBSERVED", reason=row["truth_class"])


def run_write_turn(
    task: FinancialReportTask,
    report_text: str,
    *,
    state_dir: Path | str | None = None,
    write: bool = True,
) -> EvalOutcome:
    """Run Turn 2 against the ledger; block when Turn 1 is missing."""
    ledger = _ledger_path(state_dir)
    rows = _read_jsonl(ledger)
    receipt = _latest_research_receipt(rows, task)

    if receipt is None:
        row = _turn2_row(
            task=task,
            report_text=report_text,
            receipt=None,
            code_eval={
                "label": "fail",
                "score": 0,
                "checks": {
                    "turn1_receipt_present": False,
                    "task_id_matches": False,
                    "research_sources_cited": False,
                },
            },
            judge_eval={
                "label": "blocked",
                "faithful": True,
                "flags": ["missing_turn1_research_receipt"],
                "explanation": "WRITE_PROMPT blocked before report text can be trusted.",
            },
            truth_class="FORBIDDEN",
            status="TURN2_BLOCKED_MISSING_TURN1",
        )
        if write:
            _append_row(ledger, row)
        return EvalOutcome(row=row, ok=False, reason="missing_turn1_research_receipt")

    source_ids = [str(item.get("source_id", "")) for item in receipt.get("findings", [])]
    cited_sources = [source for source in source_ids if source and source in report_text]
    code_ok = bool(cited_sources) and task.task_id == receipt.get("task_id")
    judge_eval = _judge_write_turn(report_text, task=task, source_ids=source_ids)
    row = _turn2_row(
        task=task,
        report_text=report_text,
        receipt=receipt,
        code_eval={
            "label": "pass" if code_ok else "fail",
            "score": 1 if code_ok else 0,
            "checks": {
                "turn1_receipt_present": True,
                "task_id_matches": task.task_id == receipt.get("task_id"),
                "research_sources_cited": bool(cited_sources),
                "cited_sources": cited_sources,
            },
        },
        judge_eval=judge_eval,
        truth_class="OBSERVED" if code_ok and judge_eval["faithful"] else "HYPOTHESIS",
        status="TURN2_WRITE_ALLOWED" if code_ok and judge_eval["faithful"] else "TURN2_WRITE_UNFAITHFUL",
    )
    if write:
        _append_row(ledger, row)
    return EvalOutcome(row=row, ok=row["truth_class"] == "OBSERVED", reason=row["status"])


def run_fixture_eval(
    *,
    state_dir: Path | str | None = None,
    scenario: str = "blocked_without_turn1",
    write: bool = True,
) -> Dict[str, Any]:
    """Run the fixture scenario used by pytest and Promptfoo."""
    task = fixture_task()
    if scenario == "blocked_without_turn1":
        outcome = run_write_turn(
            task,
            "TSLA report draft with no research receipt.",
            state_dir=state_dir,
            write=write,
        )
    elif scenario == "allowed_with_turn1":
        instrument_research_turn(task, fixture_research_findings(), state_dir=state_dir, write=write)
        outcome = run_write_turn(
            task,
            (
                "TSLA robotaxi margin risk report. Evidence: "
                "fixture:tesla_ir_2026q1 and fixture:analyst_consensus_2026."
            ),
            state_dir=state_dir,
            write=write,
        )
    else:
        raise ValueError(f"unknown fixture scenario: {scenario}")

    rows = _read_jsonl(_ledger_path(state_dir))
    return {
        "truth_label": TRUTH_LABEL,
        "scenario": scenario,
        "ok": outcome.ok,
        "status": outcome.row["status"],
        "reason": outcome.reason,
        "turns_logged": len(rows),
        "row": outcome.row,
    }


def analyze_trace(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate rows and count receipt-gate failures."""
    rows_list = list(rows)
    turn2 = [row for row in rows_list if row.get("kind") == "TURN2_WRITE_ATTEMPT"]
    blocked = [row for row in turn2 if row.get("status") == "TURN2_BLOCKED_MISSING_TURN1"]
    observed = [row for row in rows_list if row.get("truth_class") == "OBSERVED"]
    return {
        "truth_label": TRUTH_LABEL,
        "rows": len(rows_list),
        "turn2_attempts": len(turn2),
        "blocked_missing_turn1": len(blocked),
        "observed_rows": len(observed),
        "all_turn2_receipt_gated": all(
            row.get("status") != "TURN2_WRITE_ALLOWED"
            or row.get("code_eval", {}).get("checks", {}).get("turn1_receipt_present") is True
            for row in turn2
        ),
    }


def _turn2_row(
    *,
    task: FinancialReportTask,
    report_text: str,
    receipt: Optional[Dict[str, Any]],
    code_eval: Dict[str, Any],
    judge_eval: Dict[str, Any],
    truth_class: str,
    status: str,
) -> Dict[str, Any]:
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "kind": "TURN2_WRITE_ATTEMPT",
        "prompt_kind": "WRITE_PROMPT",
        "status": status,
        "task": task.to_dict(),
        "task_id": task.task_id,
        "input_sha12": _sha12(json.dumps(task.to_dict(), sort_keys=True)),
        "parent_research_trace_id": receipt.get("trace_id") if receipt else None,
        "report_sha12": _sha12(report_text),
        "report_preview": _preview(report_text),
        "code_eval": code_eval,
        "judge_eval": judge_eval,
        "truth_class": truth_class,
    }
    _stamp(row)
    return row


def _latest_research_receipt(rows: Sequence[Dict[str, Any]], task: FinancialReportTask) -> Optional[Dict[str, Any]]:
    for row in reversed(rows):
        if row.get("kind") != "TURN1_RESEARCH_RECEIPT":
            continue
        if row.get("task_id") != task.task_id:
            continue
        if row.get("truth_class") != "OBSERVED":
            continue
        if row.get("code_eval", {}).get("label") != "pass":
            continue
        return row
    return None


def _judge_research_turn(findings: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    flags: List[str] = []
    if not findings:
        flags.append("empty_research")
    if any("http" in item.get("source_id", "").lower() for item in findings):
        flags.append("live_url_in_fixture")
    faithful = not flags
    return {
        "label": "faithful" if faithful else "unfaithful",
        "faithful": faithful,
        "flags": flags,
        "explanation": "Fixture research is source-labeled and local." if faithful else "Fixture research violated source contract.",
    }


def _judge_write_turn(report_text: str, *, task: FinancialReportTask, source_ids: Sequence[str]) -> Dict[str, Any]:
    flags: List[str] = []
    lower = report_text.lower()
    if task.ticker.lower() not in lower:
        flags.append("missing_ticker")
    if not any(source.lower() in lower for source in source_ids):
        flags.append("missing_source_citation")
    if re.search(r"\bguaranteed\b|\bcertain\b|\bwill definitely\b", lower):
        flags.append("overconfident_language")
    faithful = not flags
    return {
        "label": "faithful" if faithful else "unfaithful",
        "faithful": faithful,
        "flags": flags,
        "explanation": "Report cites fixture research receipt." if faithful else "Report failed fixture faithfulness checks.",
    }


def _finding_to_dict(finding: ResearchFinding | Dict[str, str]) -> Dict[str, str]:
    if isinstance(finding, ResearchFinding):
        return finding.to_dict()
    return {
        "source_id": str(finding.get("source_id", "")),
        "claim": str(finding.get("claim", "")),
        "value": str(finding.get("value", "")),
    }


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    root = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    return root / EVAL_LEDGER_NAME


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def _append_row(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _stamp(row: Dict[str, Any]) -> None:
    row.pop("sha256", None)
    row["sha256"] = hashlib.sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()


def _sha12(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _preview(text: str, limit: int = 180) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run fixture-only Voss financial report eval.")
    parser.add_argument("--scenario", default="blocked_without_turn1", choices=["blocked_without_turn1", "allowed_with_turn1"])
    parser.add_argument("--state-dir", default=str(_DEFAULT_STATE))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    report = run_fixture_eval(state_dir=Path(args.state_dir), scenario=args.scenario, write=not args.no_write)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] in {"TURN2_BLOCKED_MISSING_TURN1", "TURN2_WRITE_ALLOWED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

