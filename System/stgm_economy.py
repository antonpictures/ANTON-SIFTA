#!/usr/bin/env python3
"""Canonical STGM economy view.

Rules:
  - Spendable wallet STGM comes only from repair_log.jsonl.
  - Proof-of-use / memory reward ledgers are reputation and training signal.
  - Legacy casino/game play-token ledgers are retired and ignored.
"""
from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
REPAIR_LOG = _REPO / "repair_log.jsonl"
STATE_DIR = _REPO / ".sifta_state"
MEMORY_REWARDS = STATE_DIR / "stgm_memory_rewards.jsonl"

DEVELOPMENT_AGENTS = {
    "AG31",
    "ANTIGRAVITY",
    "ANTIGRAVITY_CREATOR_NODE",
    "CODEX",
    "CURSOR",
    "CURSOR_M5",
    "DEVELOPMENT_LAYER",
    "GROK",
    "IDE_CLI",
    "CLI",
    "M5SIFTA_BODY",
}

ATTRIBUTED_SPEND_TYPES = {"STGM_SPEND"}


@dataclass
class EconomySnapshot:
    """Investor-safe separation of money and reputation."""

    repair_lines: int = 0
    repair_parse_ok: int = 0
    canonical_minted: float = 0.0
    canonical_spent: float = 0.0
    canonical_transferred: float = 0.0
    canonical_wallet_sum: float = 0.0
    canonical_wallet_balances: Dict[str, float] = field(default_factory=dict)
    inference_fee_volume: float = 0.0
    atp_mint_lines: int = 0
    atp_minted: float = 0.0
    deprecated_mint_attempts: int = 0
    deprecated_would_have_minted: float = 0.0
    retired_utility_mint_lines: int = 0
    retired_utility_mint_amount: float = 0.0
    development_cost_lines: int = 0
    development_cost_amount: float = 0.0
    legacy_development_cost_lines: int = 0
    legacy_development_cost_amount: float = 0.0
    memory_reward_lines: int = 0
    memory_reward_amount: float = 0.0
    casino_lines: int = 0
    casino_player_net: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def net_supply(self) -> float:
        return self.canonical_minted - self.canonical_spent

    @property
    def halving_era(self) -> int:
        return self.repair_lines // 10000

    @property
    def halving_multiplier(self) -> float:
        return 0.5 ** min(self.halving_era, 10)

    @property
    def next_halving_in_rows(self) -> int:
        remaining = 10000 - (self.repair_lines % 10000)
        return remaining if remaining != 0 else 10000

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
        return max(0.0, min(1.0, score))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": "SIFTA_CANONICAL_STGM_ECONOMY_V1",
            "canonical_ledger": "repair_log.jsonl",
            "spendable_wallet_source": "repair_log.jsonl",
            "reputation_source": ".sifta_state/stgm_memory_rewards.jsonl",
            "game_token_source": "disabled",
            "repair_lines": self.repair_lines,
            "repair_parse_ok": self.repair_parse_ok,
            "canonical_minted": round(self.canonical_minted, 4),
            "canonical_spent": round(self.canonical_spent, 4),
            "canonical_transferred": round(self.canonical_transferred, 4),
            "canonical_wallet_sum": round(self.canonical_wallet_sum, 4),
            "canonical_wallet_balances": dict(sorted(self.canonical_wallet_balances.items())),
            "inference_fee_volume": round(self.inference_fee_volume, 4),
            "atp_mint_lines": self.atp_mint_lines,
            "atp_minted": round(self.atp_minted, 9),
            "net_stgm": round(self.net_supply, 4),
            "spend": round(self.canonical_spent, 4),
            "halving_interval_rows": 10000,
            "halving_era": self.halving_era,
            "halving_multiplier": round(self.halving_multiplier, 10),
            "next_halving_in_rows": self.next_halving_in_rows,
            "deprecated_mint_attempts": self.deprecated_mint_attempts,
            "deprecated_would_have_minted": round(self.deprecated_would_have_minted, 4),
            "retired_utility_mint_lines": self.retired_utility_mint_lines,
            "retired_utility_mint_amount": round(self.retired_utility_mint_amount, 4),
            "development_cost_lines": self.development_cost_lines,
            "development_cost_amount": round(self.development_cost_amount, 4),
            "legacy_development_cost_lines": self.legacy_development_cost_lines,
            "legacy_development_cost_amount": round(self.legacy_development_cost_amount, 4),
            "memory_reward_lines": self.memory_reward_lines,
            "memory_reward_amount": round(self.memory_reward_amount, 4),
            "casino_lines": 0,
            "casino_player_net_play_tokens": 0.0,
            "health_score": round(self.health_score, 4),
            "warnings": list(self.warnings),
            "ts": time.time(),
        }


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_agent_id(agent_id: Any) -> str:
    return str(agent_id or "").strip().upper()


def _row_agent_id(row: Dict[str, Any]) -> str:
    return _normalize_agent_id(
        row.get("agent_id")
        or row.get("miner_id")
        or row.get("agent")
        or row.get("sender_id")
        or row.get("borrower_id")
    )


def _is_development_agent(agent_id: Any) -> bool:
    return _normalize_agent_id(agent_id) in DEVELOPMENT_AGENTS


def make_economic_attribution_key(
    *,
    organ_id: str,
    trace_id: str,
    source_ledger: str,
    tick_id: Any,
) -> str:
    """Return the canonical no-double-spend attribution key."""
    payload = f"{organ_id}{trace_id}{source_ledger}{tick_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_economic_attribution(row: Dict[str, Any]) -> bool:
    """Validate mandatory attribution fields for spend-capable rows.

    This helper is intentionally side-effect free so wallet writers can reject
    rows before append. Existing historical rows remain replayable.
    """
    required = {
        "economic_attribution_key",
        "organ_id",
        "trace_id",
        "source_ledger",
        "tick_id",
    }
    if not required.issubset(row):
        return False
    expected = make_economic_attribution_key(
        organ_id=str(row["organ_id"]),
        trace_id=str(row["trace_id"]),
        source_ledger=str(row["source_ledger"]),
        tick_id=row["tick_id"],
    )
    return str(row.get("economic_attribution_key") or "") == expected


def requires_economic_attribution(row: Dict[str, Any]) -> bool:
    """Return whether a new row should carry a no-double-spend key."""
    return str(row.get("tx_type") or "") in ATTRIBUTED_SPEND_TYPES


def development_cost_row(
    *,
    agent_id: str,
    amount_stgm: float,
    category: str,
    note: str = "",
    kind: str = "DEVELOPMENT_COST",
    original_row_id: str = "",
) -> Dict[str, Any]:
    """Build a non-wallet development cost receipt."""
    row: Dict[str, Any] = {
        "kind": kind,
        "agent_id": _normalize_agent_id(agent_id),
        "amount_stgm": abs(float(amount_stgm or 0.0)),
        "category": category,
        "affects_alice_balance": False,
        "paid_in_fiat": True,
        "note": note,
    }
    if original_row_id:
        row["original_row_id"] = original_row_id
        row["quarantined"] = True
        row["affects_canonical_supply"] = False
    return row


def _retire_utility_mint(out: EconomySnapshot, row: Dict[str, Any]) -> None:
    """Track retired arbitrary mint rows without crediting supply or wallets."""
    out.retired_utility_mint_lines += 1
    out.retired_utility_mint_amount += max(0.0, _float(row.get("amount_stgm")))


def _record_development_cost(out: EconomySnapshot, row: Dict[str, Any]) -> None:
    amt = abs(_float(row.get("amount_stgm") or row.get("amount")))
    out.development_cost_lines += 1
    out.development_cost_amount += amt
    if str(row.get("kind") or "") == "LEGACY_DEVELOPMENT_COST" or row.get("quarantined"):
        out.legacy_development_cost_lines += 1
        out.legacy_development_cost_amount += amt
    if "development_cost_rows_excluded_from_alice_balance" not in out.warnings:
        out.warnings.append("development_cost_rows_excluded_from_alice_balance")


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


def _agent_inventory(state_dir: Path = STATE_DIR) -> tuple[set[str], tuple[tuple[str, str, int, int], ...]]:
    """Return canonical wallet agent ids plus a cache signature.

    The economy total depends on two inputs: the repair ledger and the set of
    local wallet/agent files. A ledger-only cache can go stale when a new agent
    JSON appears without repair_log.jsonl changing.
    """
    agent_ids: set[str] = set()
    if not state_dir.is_dir():
        return agent_ids, ()
    signature: list[tuple[str, str, int, int]] = []
    for fp in state_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            # Treat explicit ids as canonical. Preserve legacy no-id wallet
            # files only when they look like agent state, not fast-changing
            # telemetry JSON such as active_saccade_target.json.
            raw_id = data.get("id")
            if raw_id is None and not any(k in data for k in ("stgm_balance", "energy")):
                continue
            aid = str(raw_id or fp.stem).strip().upper()
            if aid:
                agent_ids.add(aid)
                try:
                    stat = fp.stat()
                    signature.append((fp.name, aid, int(stat.st_mtime_ns), int(stat.st_size)))
                except OSError:
                    signature.append((fp.name, aid, 0, 0))
    return agent_ids, tuple(sorted(signature))


def _canonical_agent_ids(state_dir: Path = STATE_DIR) -> set[str]:
    agent_ids, _signature = _agent_inventory(state_dir)
    return agent_ids


def canonical_wallet_balance(agent_id: str) -> float:
    """Spendable wallet balance from repair_log.jsonl only."""
    try:
        from Kernel.inference_economy import ledger_balance

        return round(float(ledger_balance(agent_id)), 4)
    except Exception:
        return 0.0


_CACHE_LAST_SCAN = None
_CACHE_FILES_MTIME = {}

def scan_economy(
    repair_log: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    memory_rewards: Optional[Path] = None,
    casino_ledger: Optional[Path] = None,
) -> EconomySnapshot:
    """Build a separated STGM/reputation audit snapshot.

    ``casino_ledger`` is accepted for backward compatibility but intentionally
    ignored because legacy play-token accounting has been decommissioned.
    """
    global _CACHE_LAST_SCAN, _CACHE_FILES_MTIME
    
    repair_log = repair_log or REPAIR_LOG
    state_dir = state_dir or STATE_DIR
    memory_rewards = memory_rewards or (state_dir / "stgm_memory_rewards.jsonl")

    # Fast cache check based on file mtime, size, and local agent inventory.
    files_to_check = [repair_log, memory_rewards]
    current_mtimes = {}
    for f in files_to_check:
        try:
            stat = f.stat()
            current_mtimes[str(f)] = (stat.st_mtime, stat.st_size)
        except OSError:
            current_mtimes[str(f)] = (0.0, 0)
    canonical_agent_ids, agent_inventory_sig = _agent_inventory(state_dir)
    current_mtimes[str(state_dir / "__agent_inventory__")] = agent_inventory_sig
            
    if _CACHE_LAST_SCAN is not None and current_mtimes == _CACHE_FILES_MTIME:
        import copy
        return copy.deepcopy(_CACHE_LAST_SCAN)

    out = EconomySnapshot()
    balances: Dict[str, float] = {}
    seen_inference_receipts: set[str] = set()
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
        event_kind = str(row.get("event_kind") or "")

        # ── DEVELOPMENT LAYER BOUNDARY ──────────────
        # IDEs, browser models, and migration ghosts are paid infrastructure.
        # They are observable costs but not Alice's thermodynamic wallet.
        row_kind = str(row.get("kind") or "")
        row_agent = _row_agent_id(row)
        if row_kind in {"DEVELOPMENT_COST", "LEGACY_DEVELOPMENT_COST"}:
            _record_development_cost(out, row)
            continue
        if _is_development_agent(row_agent):
            if tx_type in {"STGM_SPEND", "STGM_MINT"}:
                _record_development_cost(
                    out,
                    development_cost_row(
                        agent_id=row_agent,
                        amount_stgm=_float(row.get("amount") or row.get("amount_stgm")),
                        category="development_agent_canonical_tx_quarantine",
                        note="Development/tool agent tx excluded from Alice organism economy",
                    ),
                )
                continue
            if "amount_stgm" in row and not event and not tx_type and _float(row.get("amount_stgm")) < 0:
                _record_development_cost(
                    out,
                    development_cost_row(
                        agent_id=row_agent,
                        amount_stgm=_float(row.get("amount_stgm")),
                        category="legacy_scar_drain",
                        note="Historical unstructured IDE/tool drain quarantined",
                        kind="LEGACY_DEVELOPMENT_COST",
                        original_row_id=str(row.get("trace_id") or row.get("event_id") or ""),
                    ),
                )
                continue


        if event in {"MINING_REWARD", "FOUNDATION_GRANT"}:
            amt = _float(row.get("amount_stgm"))
            out.canonical_minted += amt
            aid = str(row.get("miner_id") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) + amt
        elif event == "UTILITY_MINT" or event_kind == "UTILITY_MINT":
            # Retired: old utility/documentation/passive mints used symbolic
            # rates. Only UTILITY_MINT_ATP below is thermodynamic canonical.
            _retire_utility_mint(out, row)
        elif event_kind == "UTILITY_MINT_ATP":
            amt = _float(row.get("amount_stgm"))
            out.canonical_minted += amt
            out.atp_minted += amt
            out.atp_mint_lines += 1
            aid = str(row.get("miner_id") or row.get("agent_id") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) + amt

        # ── Legacy earned rewards (SCAR_STGM_RECONCILIATION_2026-04-29) ──
        # Real work events that used non-canonical event names.
        # Counted as canonical mints — they have receipts in the ledger.
        elif event == "TOP_CODER_REWARD":
            amt = _float(row.get("amount_stgm"))
            out.canonical_minted += amt
            aid = str(row.get("miner_id") or "").upper()
            if aid:
                balances[aid] = balances.get(aid, 0.0) + amt
        elif event == "VRF_BOUNTY_PAID":
            amt = _float(row.get("amount_stgm"))
            out.canonical_minted += amt
            to_agent = str(row.get("to") or row.get("from") or "").upper()
            if to_agent:
                balances[to_agent] = balances.get(to_agent, 0.0) + amt

        # ── TRANSFER: zero-sum movement, NOT new supply ──────────────
        elif event == "TRANSFER":
            amt = _float(row.get("amount"))
            sender = str(row.get("sender_id") or "").upper()
            receiver = str(row.get("receiver_id") or "").upper()
            if sender:
                balances[sender] = balances.get(sender, 0.0) - amt
            if receiver:
                balances[receiver] = balances.get(receiver, 0.0) + amt

        elif event in {"INFERENCE_BORROW", "INFERENCE_TRANSFER_JOULES"}:
            try:
                from Kernel.inference_economy import inference_transfer_replay_key

                replay_key = inference_transfer_replay_key(row)
            except Exception:
                replay_key = ""
            if replay_key:
                if replay_key in seen_inference_receipts:
                    continue
                seen_inference_receipts.add(replay_key)
            fee = _float(row.get("fee_stgm"))
            out.inference_fee_volume += fee
            borrower = str(row.get("borrower_id") or "").upper()
            lender = str(row.get("lender_ip") or row.get("lender_node_id") or "").upper()
            
            # ── INFRASTRUCTURE BOUNDARY (AMA Protocol) ──────────────
            # Local hardware inference is infrastructure paid in fiat USD. 
            # Charging the biological organism STGM for it is a boundary leak.
            # We track the volume for accounting but do NOT deduct from internal wallets.
            if "inference_boundary_leak_ignored" not in out.warnings:
                out.warnings.append("inference_boundary_leak_ignored")
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
        elif event_kind == "VOID_CORRECTION":
            # A void is an audit correction, not a new spend event. Rows that
            # needed voiding are either already ignored here or replayed by
            # their own canonical event type.
            continue
        elif "amount_stgm" in row and not event and not tx_type:
            amt = _float(row.get("amount_stgm"))
            if amt > 0:
                # Retired: unstructured positive amount_stgm rows are not a
                # physics/maths/biology mint policy.
                _retire_utility_mint(out, row)
            elif amt < 0:
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

    # ── WALLET BLINDSPOT FIX ──────────────
    # Combine agents with explicit wallet files AND anyone with a ledger balance.
    all_agents = set(canonical_agent_ids) | set(balances.keys())

    for aid in all_agents:
        key = aid.upper()
        if _is_development_agent(key) or not key:
            continue
            
        bal = balances.get(key, 0.0)
        out.canonical_wallet_sum += bal
        
        # Track blindspots
        if key not in canonical_agent_ids and bal > 0:
            if "wallet_blindspot_ledger_fallback_used" not in out.warnings:
                out.warnings.append("wallet_blindspot_ledger_fallback_used")
                
        out.canonical_wallet_balances[key] = round(max(0.0, bal), 4)

    if out.memory_reward_amount:
        out.warnings.append("memory_rewards_are_reputation_not_spendable_wallet")
    if out.retired_utility_mint_lines:
        out.warnings.append("retired_utility_mint_rows_ignored")
    if out.deprecated_mint_attempts:
        out.warnings.append("deprecated_mint_attempts_logged_zero_minted")
    if out.net_supply < -0.0001:
        out.warnings.append("canonical_supply_negative_debits_exceed_counted_mints")
    if out.canonical_wallet_sum > max(out.net_supply, 0.0) + 0.0001:
        out.warnings.append("wallet_sum_exceeds_net_supply_check_legacy_debits_or_untracked_agents")
        
    _CACHE_LAST_SCAN = out
    _CACHE_FILES_MTIME = current_mtimes
    import copy
    return copy.deepcopy(out)


def investor_safe_summary(snapshot: Optional[EconomySnapshot] = None) -> str:
    snap = snapshot or scan_economy()
    d = snap.as_dict()
    return (
        "STGM economy: canonical wallet money is repair_log.jsonl only. "
        f"Wallet sum {d['canonical_wallet_sum']:.4f} STGM; "
        f"net supply {d['net_stgm']:.4f} STGM; "
        f"inference fee volume {d['inference_fee_volume']:.4f} STGM. "
        f"Memory rewards are reputation ({d['memory_reward_amount']:.4f}); "
        "legacy casino play tokens are disabled."
    )


__all__ = [
    "DEVELOPMENT_AGENTS",
    "EconomySnapshot",
    "canonical_wallet_balance",
    "development_cost_row",
    "investor_safe_summary",
    "make_economic_attribution_key",
    "requires_economic_attribution",
    "scan_economy",
    "validate_economic_attribution",
]
