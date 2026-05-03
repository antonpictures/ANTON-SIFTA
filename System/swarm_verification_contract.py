#!/usr/bin/env python3
"""
System/swarm_verification_contract.py

Durable reader/writer for SIFTA's verification contract.

The contract may be deposited as a human signal, but code must not depend on a
chat transcript to remember it. This module turns the row type into an
inspectable organ:

  kind=MINE_INFERENCE
  signal=VERIFICATION_CONTRACT
  policy=automate_what_you_can_verify

Truth label: VERIFICATION_CONTRACT_V1
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

STATE_DIR = Path(".sifta_state")
HUMAN_SIGNALS = STATE_DIR / "human_signals.jsonl"
TRUTH_LABEL = "VERIFICATION_CONTRACT_V1"
SIGNAL = "VERIFICATION_CONTRACT"
POLICY = "automate_what_you_can_verify"

DEFAULT_RULES: Dict[str, str] = {
    "tool_router_changes": "Requires pytest execution before merge",
    "rlhs_promotion_logic": "Requires diff + signature",
    "financial_stgm": "Requires Ed25519 signature verification",
    "destructive_actions": "Requires Architect consent",
}


@dataclass(frozen=True)
class VerificationContract:
    """Small immutable view of the latest verification contract."""

    policy: str = POLICY
    rules: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_RULES))
    ts: float = 0.0
    source: str = "default"
    truth_label: str = TRUTH_LABEL
    note: str = "Karpathy LLM OS / Software 3.0 Verification Doctrine"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "signal": SIGNAL,
            "policy": self.policy,
            "rules": dict(self.rules),
            "ts": self.ts,
            "source": self.source,
            "note": self.note,
        }


def _state_file(state_dir: Path | str = STATE_DIR) -> Path:
    return Path(state_dir) / "human_signals.jsonl"


def _iter_jsonl(path: Path, *, max_lines: int = 2000) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-max_lines:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def is_verification_contract_row(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("signal") or "").strip().upper() == SIGNAL
        and str(row.get("policy") or "").strip() == POLICY
    )


def _clean_rules(raw: Any) -> Dict[str, str]:
    rules = dict(DEFAULT_RULES)
    if not isinstance(raw, Mapping):
        return rules
    for key, value in raw.items():
        k = str(key).strip()
        v = str(value).strip()
        if k and v:
            rules[k] = v
    return rules


def contract_from_row(row: Mapping[str, Any], *, source: str = "human_signals") -> VerificationContract:
    """Normalize a ledger row into a bounded contract object."""
    return VerificationContract(
        policy=str(row.get("policy") or POLICY).strip() or POLICY,
        rules=_clean_rules(row.get("rules")),
        ts=float(row.get("ts") or row.get("timestamp") or 0.0),
        source=source,
        truth_label=str(row.get("truth_label") or TRUTH_LABEL),
        note=str(row.get("note") or "Karpathy LLM OS / Software 3.0 Verification Doctrine"),
    )


def latest_verification_contract(
    *,
    state_dir: Path | str = STATE_DIR,
    max_lines: int = 2000,
) -> VerificationContract:
    """Return the latest deposited contract, or a default contract if absent."""
    path = _state_file(state_dir)
    latest: Optional[Dict[str, Any]] = None
    for row in _iter_jsonl(path, max_lines=max_lines):
        if is_verification_contract_row(row):
            latest = row
    if latest is None:
        return VerificationContract(source="default")
    return contract_from_row(latest)


def verification_rule(surface: str, *, state_dir: Path | str = STATE_DIR) -> Optional[str]:
    """Return the rule text for a named verification surface."""
    surface_key = str(surface or "").strip()
    if not surface_key:
        return None
    return latest_verification_contract(state_dir=state_dir).rules.get(surface_key)


def requires_verification(surface: str, *, state_dir: Path | str = STATE_DIR) -> bool:
    return verification_rule(surface, state_dir=state_dir) is not None


def append_verification_contract(
    *,
    state_dir: Path | str = STATE_DIR,
    rules: Optional[Mapping[str, str]] = None,
    note: str = "Karpathy LLM OS / Software 3.0 Verification Doctrine",
) -> Dict[str, Any]:
    """Append a canonical contract row with locked JSONL semantics when possible."""
    state_path = Path(state_dir)
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "kind": "MINE_INFERENCE",
        "signal": SIGNAL,
        "policy": POLICY,
        "rules": _clean_rules(rules),
        "note": note,
    }
    path = _state_file(state_path)
    try:
        from System.ledger_append import append_jsonl_line

        append_jsonl_line(path, row)
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def contract_for_alice_prompt(*, state_dir: Path | str = STATE_DIR) -> str:
    """Compact prompt block for Alice or another local agent."""
    contract = latest_verification_contract(state_dir=state_dir)
    lines = [
        "VERIFICATION CONTRACT:",
        f"- policy: {contract.policy}",
        f"- source: {contract.source}",
    ]
    for key, value in sorted(contract.rules.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_RULES",
    "POLICY",
    "SIGNAL",
    "TRUTH_LABEL",
    "VerificationContract",
    "append_verification_contract",
    "contract_for_alice_prompt",
    "contract_from_row",
    "is_verification_contract_row",
    "latest_verification_contract",
    "requires_verification",
    "verification_rule",
]


if __name__ == "__main__":
    row = append_verification_contract()
    print(json.dumps(row, indent=2, sort_keys=True))
