#!/usr/bin/env python3
"""Five-minute Philippe wedge: SIFTA Agent Trust Receipt Gate.

This is deliberately small and local. It does not claim AGI or run a browser.
It demonstrates the sellable wedge named in r1369/r1378:

owner intent -> nonce -> action receipt -> duplicate-spend refusal -> honest no-result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

TRUTH_LABEL = "PHILIPPE_RECEIPT_HONESTY_DEMO_V1"
LEDGER_NAME = "philippe_receipt_honesty_demo.jsonl"

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_STATE = _REPO / ".sifta_state"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return _DEFAULT_STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _receipt_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class AgentTrustReceiptGate:
    """Append-only local gate for one risky agent workflow."""

    def __init__(self, state_dir: Path | str | None = None) -> None:
        self.state_dir = _state_dir(state_dir)
        self.ledger_path = self.state_dir / LEDGER_NAME
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _append(self, row: dict[str, Any]) -> dict[str, Any]:
        row = {
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            **row,
        }
        row["row_hash"] = _hash(json.dumps(row, ensure_ascii=False, sort_keys=True))
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def _rows(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def owner_intent(self, owner_command: str, *, workflow: str = "agent_trust_receipt_gate") -> dict[str, Any]:
        command = " ".join(str(owner_command or "").split())
        nonce = uuid.uuid4().hex
        return self._append(
            {
                "schema": "OWNER_INTENT_RECEIPT_V1",
                "receipt_id": _receipt_id("intent"),
                "workflow": workflow,
                "owner_command": command,
                "intent_hash": _hash(command.lower()),
                "nonce": nonce,
                "status": "INTENT_REGISTERED",
                "owner_visible_line": f"Intent registered with nonce {nonce[:10]}.",
            }
        )

    def execute_once(self, intent: dict[str, Any], *, action: str, observed_result: str) -> dict[str, Any]:
        nonce = str(intent.get("nonce") or "")
        action_key = _hash(f"{nonce}:{action}")
        for row in reversed(self._rows()):
            if row.get("schema") == "EFFECTOR_ACTION_RECEIPT_V1" and row.get("action_key") == action_key:
                return self._append(
                    {
                        "schema": "DUPLICATE_SPEND_REFUSAL_V1",
                        "receipt_id": _receipt_id("dupe"),
                        "workflow": intent.get("workflow") or "agent_trust_receipt_gate",
                        "owner_command": intent.get("owner_command") or "",
                        "nonce": nonce,
                        "action": action,
                        "action_key": action_key,
                        "status": "DUPLICATE_REFUSED",
                        "refused_because": "same nonce/action already has an effector receipt",
                        "owner_visible_line": "Duplicate refused: this nonce/action was already spent.",
                    }
                )
        return self._append(
            {
                "schema": "EFFECTOR_ACTION_RECEIPT_V1",
                "receipt_id": _receipt_id("act"),
                "workflow": intent.get("workflow") or "agent_trust_receipt_gate",
                "owner_command": intent.get("owner_command") or "",
                "nonce": nonce,
                "action": action,
                "action_key": action_key,
                "status": "ACTION_RECEIPTED",
                "observed_result": " ".join(str(observed_result or "").split()),
                "owner_visible_line": f"Action receipted: {action}.",
            }
        )

    def honest_no_result(self, intent: dict[str, Any], *, missing_receipt: str, requested_claim: str) -> dict[str, Any]:
        return self._append(
            {
                "schema": "HONEST_NO_RESULT_BLOCK_V1",
                "receipt_id": _receipt_id("block"),
                "workflow": intent.get("workflow") or "agent_trust_receipt_gate",
                "owner_command": intent.get("owner_command") or "",
                "nonce": intent.get("nonce") or "",
                "status": "NO_RESULT_BLOCKED",
                "missing_receipt": missing_receipt,
                "requested_claim": requested_claim,
                "owner_visible_line": (
                    f"No result: I cannot claim {requested_claim!r} because "
                    f"{missing_receipt} is missing."
                ),
            }
        )


def run_demo(*, state_dir: Path | str | None = None, print_steps: bool = True) -> dict[str, Any]:
    gate = AgentTrustReceiptGate(state_dir)
    intent = gate.owner_intent(
        "Open the buyer demo page in Alice Browser and report the action honestly."
    )
    action = gate.execute_once(
        intent,
        action="open_demo_page",
        observed_result="Simulated local browser effector accepted https://example.com/sifta-trust-gate",
    )
    duplicate = gate.execute_once(
        intent,
        action="open_demo_page",
        observed_result="This should not execute twice.",
    )
    unsupported = gate.owner_intent(
        "Summarize Perplexity results that have not been fetched.",
        workflow="agent_trust_receipt_gate_no_result",
    )
    no_result = gate.honest_no_result(
        unsupported,
        missing_receipt="perplexity_answer_dom_receipt",
        requested_claim="Perplexity recipe result summary",
    )
    result = {
        "truth_label": TRUTH_LABEL,
        "ledger": str(gate.ledger_path),
        "steps": [intent, action, duplicate, unsupported, no_result],
        "demo_pass": (
            intent.get("status") == "INTENT_REGISTERED"
            and action.get("status") == "ACTION_RECEIPTED"
            and duplicate.get("status") == "DUPLICATE_REFUSED"
            and no_result.get("status") == "NO_RESULT_BLOCKED"
        ),
    }
    if print_steps:
        print("SIFTA Agent Trust Receipt Gate — 5 minute wedge")
        for idx, step in enumerate(result["steps"], 1):
            print(f"{idx}. {step['schema']}: {step['owner_visible_line']}")
        print(f"ledger: {result['ledger']}")
        print(f"demo_pass: {result['demo_pass']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default="", help="Optional state dir; defaults to repo .sifta_state")
    args = parser.parse_args()
    result = run_demo(state_dir=args.state_dir or None, print_steps=True)
    return 0 if result.get("demo_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
