#!/usr/bin/env python3
"""Canonical STGM economy view.

Rules:
  - Spendable wallet STGM comes only from repair_log.jsonl.
  - Proof-of-use / memory reward ledgers are reputation and training signal.
  - Casino/game ledgers are play money and never count as STGM.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
REPAIR_LOG = _REPO / "repair_log.jsonl"
STATE_DIR = _REPO / ".sifta_state"
MEMORY_REWARDS = STATE_DIR / "stgm_memory_rewards.jsonl"
CASINO_LEDGER = STATE_DIR / "casino_vault.jsonl"


@dataclass
class EconomySnapshot:
    """Investor-safe separation of money, reputation, and quarantined game rows."""

    repair_lines: int = 0
    repair_parse_ok: int = 0
    canonical_minted: float = 0.0
    canonical_spent: float = 0.0
    canonical_transferred: float = 0.0
    canonical_wallet_sum: float = 0.0
    inference_fee_volume: float = 0.0
    deprecated_mint_attempts: int = 0
    deprecated_would_have_minted: float = 0.0
    memory_reward_lines: int = 0
    memory_reward_amount: float = 0.0
    casino_lines: int = 0
    casino_player_net: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def net_supply(self) -> float:
        return self.canonical_minted - self.canonical_spent

    @property
    def health_score(self) -> float:
        if self.repair_lines == 0:
            return 0.5
        score = 0.55
        if self.canonical_minted > 0 or self.inference_fee_volume > 0:
            score += 0.25
        if self.deprecated_mint_attempts == 0:
            score += 0.10
        else:
            score -= min(0.20, self.deprecated_mint_attempts / 100.0)
        if self.casino_player_net:
            score -= 0.05
        return max(0.0, min(1.0, score))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": "SIFTA_CANONICAL_STGM_ECONOMY_V1",
            "canonical_ledger": "repair_log.jsonl",
            "spendable_wallet_source": "repair_log.jsonl",
            "reputation_source": ".sifta_state/stgm_memory_rewards.jsonl",
            "game_token_source": ".sifta_state/casino_vault.jsonl",
            "repair_lines": self.repair_lines,
            "repair_parse_ok": self.repair_parse_ok,
            "canonical_minted": round(self.canonical_minted, 4),
            "canonical_spent": round(self.canonical_spent, 4),
            "canonical_transferred": round(self.canonical_transferred, 4),
            "canonical_wallet_sum": round(self.canonical_wallet_sum, 4),
            "inference_fee_volume": round(self.inference_fee_volume, 4),
            "net_stgm": round(self.net_supply, 4),
            "spend": round(self.canonical_spent, 4),
            "deprecated_mint_attempts": self.deprecated_mint_attempts,
            "deprecated_would_have_minted": round(self.deprecated_would_have_minted, 4),
            "memory_reward_lines": self.memory_reward_lines,
            "memory_reward_amount": round(self.memory_reward_amount, 4),
            "casino_lines": self.casino_lines,
            "casino_player_net_play_tokens": round(self.casino_player_net, 4),
            "health_score": round(self.health_score, 4),
            "warnings": list(self.warnings),
            "ts": time.time(),
        }


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield None


def _ledger_row_valid(row: Dict[str, Any]) -> bool:
    try:
        from Kernel.inference_economy import _ledger_row_cryptographically_valid

        return bool(_ledger_row_cryptographically_valid(row))
    except Exception:
        return True


def _canonical_agent_ids(state_dir: Path = STATE_DIR) -> set[str]:
    agent_ids: set[str] = set()
    if not state_dir.is_dir():
        return agent_ids
    for fp in state_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            aid = str(data.get("id") or fp.stem).strip().upper()
            if aid:
                agent_ids.add(aid)
    return agent_ids


def canonical_wallet_balance(agent_id: str) -> float:
    """Spendable wallet balance from repair_log.jsonl only."""
    try:
        from Kernel.inference_economy import ledger_balance

        return round(float(ledger_balance(agent_id)), 4)
    except Exception:
        return 0.0


def scan_economy(
    repair_log: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    memory_rewards: Optional[Path] = None,
    casino_ledger: Optional[Path] = None,
) -> EconomySnapshot:
    """Build a separated STGM/reputation/play-token audit snapshot."""
    repair_log = repair_log or REPAIR_LOG
    state_dir = state_dir or STATE_DIR
    memory_rewards = memory_rewards or (state_dir / "stgm_memory_rewards.jsonl")
    casino_ledger = casino_ledger or (state_dir / "casino_vault.jsonl")

    out = EconomySnapshot()
    balances: Dict[str, float] = {}
    for row in _iter_jsonl(repair_log):
        out.repair_lines += 1
        if not isinstance(row, dict):
            continue
        if not _ledger_row_valid(row):
            if "invalid_signed_repair_log_rows_ignored" not in out.warnings:
                out.warnings.append("invalid_signed_repair_log_rows_ignored")
            continue
        out.repair_parse_ok += 1
        event = str(row.get("event") or "")
        tx_type = str(row.get("tx_type") or "")

        if event in {"MINING_REWARD", "FOUNDATION_GRANT", "UTILITY_MINT"}:
            amt = _float(row.get("amount_stgm"))
            out.canonical_minted += amt
            aid = str(row.get("miner_id") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) + amt
        elif event == "INFERENCE_BORROW":
            fee = _float(row.get("fee_stgm"))
            out.inference_fee_volume += fee
            borrower = str(row.get("borrower_id") or "").upper()
            lender = str(row.get("lender_ip") or "").upper()
            if borrower:
                balances[borrower] = balances.get(borrower, 0.0) - fee
            if lender:
                balances[lender] = balances.get(lender, 0.0) + fee
        elif tx_type == "STGM_MINT":
            amt = _float(row.get("amount"))
            out.canonical_minted += amt
            out.canonical_transferred += amt
            aid = str(row.get("agent_id") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) + amt
        elif tx_type == "STGM_SPEND":
            amt = _float(row.get("amount"))
            out.canonical_spent += amt
            out.canonical_transferred += amt
            aid = str(row.get("agent_id") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) - amt
        elif "amount_stgm" in row and not event and not tx_type:
            amt = _float(row.get("amount_stgm"))
            if amt >= 0:
                out.canonical_minted += amt
            else:
                out.canonical_spent += abs(amt)
            aid = str(row.get("agent") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) + amt
        elif row.get("event_kind") == "DEPRECATED_MINT_ATTEMPT":
            out.deprecated_mint_attempts += 1
            out.deprecated_would_have_minted += _float(row.get("would_have_minted_stgm"))

    for row in _iter_jsonl(memory_rewards):
        if not isinstance(row, dict):
            continue
        out.memory_reward_lines += 1
        out.memory_reward_amount += _float(row.get("amount"))

    for row in _iter_jsonl(casino_ledger):
        if not isinstance(row, dict):
            continue
        out.casino_lines += 1
        out.casino_player_net += _float(row.get("player_delta"))

    for aid in _canonical_agent_ids(state_dir):
        out.canonical_wallet_sum += balances.get(aid.upper(), 0.0)

    if out.memory_reward_amount:
        out.warnings.append("memory_rewards_are_reputation_not_spendable_wallet")
    if out.casino_lines:
        out.warnings.append("casino_rows_are_play_tokens_not_stgm")
    if out.deprecated_mint_attempts:
        out.warnings.append("deprecated_mint_attempts_logged_zero_minted")
    return out


def investor_safe_summary(snapshot: Optional[EconomySnapshot] = None) -> str:
    snap = snapshot or scan_economy()
    d = snap.as_dict()
    return (
        "STGM economy: canonical wallet money is repair_log.jsonl only. "
        f"Wallet sum {d['canonical_wallet_sum']:.4f} STGM; "
        f"net supply {d['net_stgm']:.4f} STGM; "
        f"inference fee volume {d['inference_fee_volume']:.4f} STGM. "
        f"Memory rewards are reputation ({d['memory_reward_amount']:.4f}), "
        f"casino is play tokens ({d['casino_player_net_play_tokens']:.4f})."
    )


__all__ = [
    "EconomySnapshot",
    "canonical_wallet_balance",
    "investor_safe_summary",
    "scan_economy",
]
