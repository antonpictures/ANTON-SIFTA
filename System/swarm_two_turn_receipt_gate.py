#!/usr/bin/env python3
"""swarm_two_turn_receipt_gate.py — Turn 2 refuses to run without Turn 1.

Truth label: ``SIFTA_TWO_TURN_RECEIPT_GATE_V1``.

Per Cursor's §4.6 in
``Documents/OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md``
(sign-in ``53520701-11a4-4323-b9c8-bf4302617808`` → sign-out
``11142f06-ef78-47f3-b02b-ed0343190c95``). Cursor decoded the Colab /
Phoenix two-turn report-agent pattern:

  ::

      financial_report span
        ├── Turn 1: RESEARCH_PROMPT  → client.query(...)
        └── Turn 2: WRITE_PROMPT     → assemble report + span.set_attribute("output.value", ...)

The vibes-problem failure mode: **Turn 2 runs without a real Turn 1
result.** The writer hallucinates a report because no research data
is on the wire — and Phoenix's span happily records the made-up
output as if it were the real thing. Voss called this exact pattern
out at AI Engineer Europe 2026.

This module is the structural reply. Every multi-turn pipeline writes
an append-only receipt to ``.sifta_state/two_turn_receipts.jsonl``
keyed by ``(pipeline_id, turn_id)``. Each subsequent turn calls
:func:`require_prior_receipt` which raises
:class:`PriorReceiptMissingError` if no matching row is on disk for
the prior turn. Turn 2 cannot run without Turn 1.

What this is, and isn't
-----------------------

  * It is a **deterministic gate**. The function reads the receipt
    ledger and either lets the call through or raises. No LLM. No
    vibes.
  * It is **append-only** per §4.3 / §4.4 / §8.5. A receipt cannot be
    rewritten — only superseded by a newer receipt with a different
    ``trace_id``.
  * It does **not** require API keys, network access, or any
    external service. Fixture-only tests prove the gate.
  * It does **not** replace Phoenix / OTel. It is the pre-flight
    check that sits **in front of** any tracing layer so the trace
    never records a hallucinated Turn 2 in the first place.

Suggested integration
---------------------

A pipeline that wants the gate:

  ::

      gate = TwoTurnReceiptGate(pipeline_id="financial_report_q4")
      t1 = run_research(query)
      gate.record("RESEARCH", t1, payload_sha=t1.sha256)

      gate.require("RESEARCH")            # raises if Turn 1 absent
      t2 = run_write(t1)
      gate.record("WRITE", t2, payload_sha=t2.sha256)

Promptfoo-style assert (config in ``tests/two_turn_receipt_evals/``):

  ::

      - type: javascript
        value: |
          // Pass only when the WRITE turn ledger has a matching
          // RESEARCH receipt for the same pipeline_id.
          ...
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_TWO_TURN_RECEIPT_GATE_V1"
LEDGER_NAME = "two_turn_receipts.jsonl"

TRUTH_BOUNDARY = (
    "Deterministic gate. Turn N receipt must be on disk before Turn "
    "N+1 may run. Append-only. No LLM, no network. Closes the Voss "
    "vibes-problem failure mode where Turn 2 hallucinates because no "
    "real Turn 1 result was wired through."
)


class PriorReceiptMissingError(RuntimeError):
    """Raised when a turn tries to run without the prior turn's receipt.

    The error message names the pipeline_id, the missing turn_id, and
    the path that was scanned so an auditor can replay the failure.
    """

    def __init__(self, pipeline_id: str, turn_id: str, ledger_path: Path) -> None:
        super().__init__(
            f"Turn '{turn_id}' for pipeline '{pipeline_id}' has no receipt at "
            f"{ledger_path}. Refusing to proceed — Turn 2 cannot run without Turn 1."
        )
        self.pipeline_id = pipeline_id
        self.turn_id = turn_id
        self.ledger_path = ledger_path


# ── helpers ──────────────────────────────────────────────────────────────


def _read_receipts(ledger_path: Path, *, max_rows: int = 5000) -> List[Dict[str, Any]]:
    if not ledger_path.exists():
        return []
    try:
        text = ledger_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines()[-max(1, max_rows) :]:
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


def _stable_sha(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── gate primitive ───────────────────────────────────────────────────────


@dataclass
class TurnReceipt:
    pipeline_id: str
    turn_id: str
    ts: float
    trace_id: str
    payload_sha: str
    payload_preview: str
    truth_label: str = TRUTH_LABEL
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "ts": self.ts,
            "trace_id": self.trace_id,
            "kind": "TWO_TURN_RECEIPT",
            "pipeline_id": self.pipeline_id,
            "turn_id": self.turn_id,
            "payload_sha": self.payload_sha,
            "payload_preview": self.payload_preview,
            "sha256": self.sha256,
        }


@dataclass
class TwoTurnReceiptGate:
    """Stateful helper that records + requires receipts for one pipeline."""

    pipeline_id: str
    state_dir: Optional[Path] = None
    _ledger_path: Path = field(init=False)

    def __post_init__(self) -> None:
        base = self.state_dir if self.state_dir is not None else _DEFAULT_STATE
        base = Path(base)
        base.mkdir(parents=True, exist_ok=True)
        self._ledger_path = base / LEDGER_NAME

    # -- API ---------------------------------------------------------

    @property
    def ledger_path(self) -> Path:
        return self._ledger_path

    def record(
        self,
        turn_id: str,
        payload: Any,
        *,
        preview_chars: int = 200,
        write: bool = True,
    ) -> TurnReceipt:
        """Append a receipt for the named turn.

        ``payload`` can be any JSON-serializable object. Its SHA-256
        is stored in the receipt; the first ``preview_chars`` of its
        repr are stored as a human-readable breadcrumb.
        """
        if not turn_id or not isinstance(turn_id, str):
            raise ValueError("turn_id must be a non-empty string")
        payload_sha = _stable_sha(payload)
        preview = str(payload)[: max(0, preview_chars)]
        ts = time.time()
        trace_id = str(uuid.uuid4())
        receipt = TurnReceipt(
            pipeline_id=self.pipeline_id,
            turn_id=turn_id,
            ts=ts,
            trace_id=trace_id,
            payload_sha=payload_sha,
            payload_preview=preview,
        )
        payload_obj = receipt.to_dict()
        payload_obj.pop("sha256", None)
        receipt.sha256 = hashlib.sha256(
            json.dumps(payload_obj, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        if write:
            with self._ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")
        return receipt

    def find(self, turn_id: str) -> Optional[Dict[str, Any]]:
        """Return the newest matching receipt, or None."""
        for row in reversed(_read_receipts(self._ledger_path)):
            if (
                row.get("kind") == "TWO_TURN_RECEIPT"
                and row.get("pipeline_id") == self.pipeline_id
                and row.get("turn_id") == turn_id
            ):
                return row
        return None

    def require(self, turn_id: str) -> Dict[str, Any]:
        """Raise unless a receipt for ``turn_id`` is on disk.

        Returns the receipt dict when present. Use ``find`` for a
        non-raising lookup.
        """
        receipt = self.find(turn_id)
        if receipt is None:
            raise PriorReceiptMissingError(
                pipeline_id=self.pipeline_id,
                turn_id=turn_id,
                ledger_path=self._ledger_path,
            )
        return receipt

    def all_receipts(self) -> List[Dict[str, Any]]:
        """All receipts for this pipeline_id (oldest first)."""
        return [
            r for r in _read_receipts(self._ledger_path)
            if r.get("pipeline_id") == self.pipeline_id
        ]


# ── convenience: a two-turn report demo ──────────────────────────────────


def demo_two_turn_pipeline(
    *,
    pipeline_id: str,
    research_fixture: Dict[str, Any],
    skip_turn_1_record: bool = False,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Demo pipeline matching the Colab/Phoenix pattern Cursor decoded.

    Turn 1: research — receives pre-canned ``research_fixture`` (so the
    test runs without any API key).
    Turn 2: write — refuses to assemble the report unless Turn 1's
    receipt is on disk.

    ``skip_turn_1_record=True`` lets tests verify the gate by skipping
    the Turn 1 record() call and asserting that Turn 2 raises.
    """
    gate = TwoTurnReceiptGate(pipeline_id=pipeline_id, state_dir=state_dir)

    # Turn 1: research
    research_result = dict(research_fixture)
    if not skip_turn_1_record:
        gate.record("RESEARCH", research_result)

    # Turn 2: write — gate first, then assemble
    prior = gate.require("RESEARCH")  # raises PriorReceiptMissingError if absent
    report = {
        "title": research_result.get("title", "Untitled"),
        "body": (
            f"Report based on research span "
            f"{prior['trace_id']} (sha {prior['payload_sha'][:12]}): "
            f"{research_result.get('summary', '')}"
        ),
        "evidence_count": len(research_result.get("evidence", []) or []),
        "research_trace_id": prior["trace_id"],
    }
    write_receipt = gate.record("WRITE", report)
    return {
        "report": report,
        "research_receipt": prior,
        "write_receipt": write_receipt.to_dict(),
    }


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pipeline", default="demo_q4_report")
    p.add_argument("--skip-turn-1", action="store_true",
                   help="Skip Turn 1 record() — Turn 2 should refuse.")
    args = p.parse_args()
    fixture = {
        "title": "Q4 Demo Report",
        "summary": "Three line items from the canned research fixture.",
        "evidence": ["row_a", "row_b", "row_c"],
    }
    try:
        out = demo_two_turn_pipeline(
            pipeline_id=args.pipeline,
            research_fixture=fixture,
            skip_turn_1_record=args.skip_turn_1,
        )
        print("PIPELINE_OK")
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
    except PriorReceiptMissingError as exc:
        print("GATE_REFUSED")
        print(str(exc))
        raise SystemExit(2)
