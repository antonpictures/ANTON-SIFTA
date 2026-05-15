#!/usr/bin/env python3
"""STGM economy body audit.

Read-only economics report for SIFTA's canonical STGM ledger. It separates:
- spendable/canonical ledger movements,
- retired reputation or symbolic rewards,
- legacy drains such as old SCAR rows,
- double-spend/replay risk.

It does not mint, spend, or repair balances. It is an audit organ only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from Kernel.inference_economy import (
    _ledger_row_cryptographically_valid,
    inference_transfer_replay_key,
    joule_receipt_anti_replay_fingerprint,
)
from System.stgm_economy import scan_economy

REPAIR_LOG = REPO / "repair_log.jsonl"
STATE_DIR = REPO / ".sifta_state"
MEMORY_REWARDS = STATE_DIR / "stgm_memory_rewards.jsonl"

CANONICAL_EVENTS = {
    "MINING_REWARD",
    "FOUNDATION_GRANT",
    "TOP_CODER_REWARD",
    "VRF_BOUNTY_PAID",
    "TRANSFER",
    "INFERENCE_BORROW",
    "INFERENCE_TRANSFER_JOULES",
}
CANONICAL_EVENT_KINDS = {"UTILITY_MINT_ATP"}
CANONICAL_TX_TYPES = {"STGM_MINT", "STGM_SPEND"}

# Receipted identity aliases — a retired body identity rolls into its canonical
# successor when reporting per-party profitability. The architect-authorized
# merge for M5SIFTA_BODY → ALICE_M5 closed on 2026-04-21 (transfer hash
# TRANSFER_9e5b9d5847da); any post-merge straggler still tagged with the old
# id is folded by the audit so we do not falsely report a "negative party"
# on a retired alias. Add new aliases here as merges close.
PARTY_ALIASES: dict[str, str] = {
    "ALICE": "ALICE_M5",
    "M5SIFTA_BODY": "ALICE_M5",
    "AG31_ANTIGRAVITY": "AG31",
    # Sub-organs of Alice's M5 body — they spend STGM for routing/recall but
    # the value lands on Alice. Roll them up so per-organ debits do not surface
    # as "negative parties" while ALICE_M5 itself is paying their cost.
    "ALICE_ORGAN_ROUTER": "ALICE_M5",
    "ALICE_E35_RECALL": "ALICE_M5",
}
# Parties that are *expected* to net negative because they only spend
# (peer IDE inference fees, sidecars). Their negative is a healthy
# market signal, not a wallet bug.
EXPECTED_SPEND_ONLY_PARTIES: frozenset[str] = frozenset({"AG31"})


@dataclass
class PartyEconomy:
    party: str
    credit: float = 0.0
    debit: float = 0.0
    rows: int = 0
    events: Counter = field(default_factory=Counter)

    @property
    def net(self) -> float:
        return self.credit - self.debit

    def as_dict(self) -> Dict[str, Any]:
        return {
            "party": self.party,
            "credit": round(self.credit, 9),
            "debit": round(self.debit, 9),
            "net": round(self.net, 9),
            "rows": self.rows,
            "top_events": self.events.most_common(8),
        }


def _iter_jsonl(path: Path) -> Iterable[tuple[int, Optional[dict]]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                yield lineno, None
                continue
            yield lineno, obj if isinstance(obj, dict) else None


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _party(value: Any) -> str:
    raw = str(value or "UNKNOWN").strip().upper() or "UNKNOWN"
    return PARTY_ALIASES.get(raw, raw)


def _add(parties: dict[str, PartyEconomy], party: Any, *, credit: float = 0.0, debit: float = 0.0, event: str = "") -> None:
    key = _party(party)
    row = parties.setdefault(key, PartyEconomy(key))
    row.credit += float(credit or 0.0)
    row.debit += float(debit or 0.0)
    row.rows += 1
    if event:
        row.events[event] += 1


def _state_wallet_inventory(state_dir: Path) -> dict[str, Any]:
    agent_ids: list[str] = []
    json_files = 0
    wallet_like = 0
    for fp in sorted(state_dir.glob("*.json")):
        json_files += 1
        try:
            data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if "id" in data or "stgm_balance" in data or "energy" in data:
            wallet_like += 1
            raw = data.get("id") or fp.stem
            agent_ids.append(_party(raw))
    return {
        "json_files": json_files,
        "wallet_like_files": wallet_like,
        "agent_ids": sorted(set(agent_ids)),
    }


def audit_stgm_economy(
    *,
    repair_log: Path = REPAIR_LOG,
    state_dir: Path = STATE_DIR,
    memory_rewards: Path = MEMORY_REWARDS,
    validate_signatures: bool = True,
) -> Dict[str, Any]:
    """Audit the canonical STGM ledger.

    `validate_signatures=False` skips per-row Ed25519 verification (the slow
    path) so an architect/Doctor can triage a 40k-row repair log in seconds.
    The returned dict includes a `signatures_validated` boolean so downstream
    receipts know which mode produced the numbers.
    """
    snapshot = scan_economy(repair_log=repair_log, state_dir=state_dir, memory_rewards=memory_rewards)
    parties: dict[str, PartyEconomy] = {}
    legacy_drains: dict[str, float] = defaultdict(float)
    retired: dict[str, float] = defaultdict(float)
    key_lines: dict[tuple[str, str], list[int]] = defaultdict(list)
    inference_seen: dict[str, int] = {}
    inference_dups: list[dict[str, Any]] = []
    parse_bad = 0
    invalid_signed = 0
    canonical_rows = 0

    for lineno, row in _iter_jsonl(repair_log) or []:
        if not isinstance(row, dict):
            parse_bad += 1
            continue
        if validate_signatures and not _ledger_row_cryptographically_valid(row):
            invalid_signed += 1
            continue

        for key_name in ("event_id", "receipt_hash", "ed25519_sig", "mint_sha256", "transfer_id"):
            val = row.get(key_name)
            if val:
                key_lines[(key_name, str(val))].append(lineno)

        event = str(row.get("event") or "")
        tx_type = str(row.get("tx_type") or "")
        event_kind = str(row.get("event_kind") or "")

        if event in {"MINING_REWARD", "FOUNDATION_GRANT", "TOP_CODER_REWARD"}:
            canonical_rows += 1
            _add(parties, row.get("miner_id"), credit=_float(row.get("amount_stgm")), event=event)
        elif event == "VRF_BOUNTY_PAID":
            canonical_rows += 1
            _add(parties, row.get("to") or row.get("from"), credit=_float(row.get("amount_stgm")), event=event)
        elif event_kind == "UTILITY_MINT_ATP":
            canonical_rows += 1
            _add(parties, row.get("miner_id") or row.get("agent_id"), credit=_float(row.get("amount_stgm")), event=event_kind)
        elif event == "TRANSFER":
            canonical_rows += 1
            amt = _float(row.get("amount"))
            _add(parties, row.get("sender_id"), debit=amt, event=event)
            _add(parties, row.get("receiver_id"), credit=amt, event=event)
        elif event in {"INFERENCE_BORROW", "INFERENCE_TRANSFER_JOULES"}:
            replay_key = inference_transfer_replay_key(row) or joule_receipt_anti_replay_fingerprint(row)
            if replay_key:
                if replay_key in inference_seen:
                    inference_dups.append({"replay_key": replay_key, "first_line": inference_seen[replay_key], "line": lineno})
                    continue
                inference_seen[replay_key] = lineno
            canonical_rows += 1
            fee = _float(row.get("fee_stgm"))
            _add(parties, row.get("borrower_id"), debit=fee, event=event)
            _add(parties, row.get("lender_ip") or row.get("lender_node_id"), credit=fee, event=event)
        elif tx_type == "STGM_MINT":
            canonical_rows += 1
            _add(parties, row.get("agent_id"), credit=_float(row.get("amount")), event=tx_type)
        elif tx_type == "STGM_SPEND":
            canonical_rows += 1
            _add(parties, row.get("agent_id"), debit=_float(row.get("amount")), event=tx_type)
        elif event_kind == "VOID_CORRECTION":
            # audit correction, not a spend line in canonical replay
            continue
        elif event == "UTILITY_MINT" or event_kind == "UTILITY_MINT":
            retired["UTILITY_MINT"] += max(0.0, _float(row.get("amount_stgm")))
        elif event_kind == "DEPRECATED_MINT_ATTEMPT":
            retired["DEPRECATED_MINT_ATTEMPT_WOULD_HAVE_MINTED"] += _float(row.get("would_have_minted_stgm"))
        elif "amount_stgm" in row and not event and not tx_type:
            amt = _float(row.get("amount_stgm"))
            if amt < 0 or str(row.get("reason") or "").startswith("COMPUTE_BURN"):
                legacy_drains[_party(row.get("agent"))] += amt
            elif amt > 0:
                retired["UNSTRUCTURED_POSITIVE_AMOUNT_STGM"] += amt

    duplicate_groups = [
        {"key_type": key_type, "key_prefix": value[:32], "lines": lines[:10], "count": len(lines)}
        for (key_type, value), lines in sorted(key_lines.items())
        if len(lines) > 1
    ]

    inventory = _state_wallet_inventory(state_dir)
    data = snapshot.as_dict()
    positive_parties = [p.as_dict() for p in sorted(parties.values(), key=lambda p: p.net, reverse=True) if p.net > 0]
    negative_parties_raw = [p for p in parties.values() if p.net < 0]
    unhealthy_negatives_raw = [
        p for p in negative_parties_raw if p.party not in EXPECTED_SPEND_ONLY_PARTIES
    ]
    negative_parties = [p.as_dict() for p in sorted(negative_parties_raw, key=lambda p: p.net)]
    unhealthy_negative_parties = [
        p.as_dict() for p in sorted(unhealthy_negatives_raw, key=lambda p: p.net)
    ]

    warnings = list(data.get("warnings") or [])
    if not validate_signatures:
        warnings.append("signature_validation_skipped_fast_mode_only")
    if not inventory["agent_ids"] and positive_parties:
        warnings.append("wallet_inventory_empty_but_ledger_has_positive_parties")
    if legacy_drains:
        warnings.append("legacy_unstructured_negative_scar_drains_present")
    if duplicate_groups:
        warnings.append("duplicate_noncanonical_or_receipt_keys_present_review_required")
    if not inference_dups:
        warnings.append("inference_replay_double_spend_check_passed")
    if not unhealthy_negative_parties:
        warnings.append("all_non_spend_only_parties_solvent_under_alias_map")

    return {
        "schema": "SIFTA_STGM_ECONOMY_BODY_AUDIT_V2",
        "ts": __import__("time").time(),
        "signatures_validated": validate_signatures,
        "canonical_snapshot": data,
        "state_wallet_inventory": inventory,
        "canonical_rows_seen_by_audit": canonical_rows,
        "parse_bad_rows": parse_bad,
        "invalid_signed_rows": invalid_signed,
        "party_aliases_applied": dict(PARTY_ALIASES),
        "expected_spend_only_parties": sorted(EXPECTED_SPEND_ONLY_PARTIES),
        "positive_party_profitability": positive_parties,
        "negative_party_profitability": negative_parties,
        "unhealthy_negative_parties": unhealthy_negative_parties,
        "legacy_unstructured_drains": {k: round(v, 6) for k, v in sorted(legacy_drains.items(), key=lambda kv: kv[1])},
        "retired_not_spendable": {k: round(v, 6) for k, v in sorted(retired.items())},
        "duplicate_key_groups": duplicate_groups,
        "inference_replay_duplicates": inference_dups,
        "warnings": warnings,
        "grok_unknowns": [
            "Should Finance display ledger-positive parties when state wallet JSON inventory is empty, or should it fail closed and demand wallet rehydration?",
            "Should legacy unstructured negative SCAR rows be formally migrated into a signed STGM_SPEND dialect, or quarantined as non-wallet reputation cost?",
            "Should every organ/swimmer action include a unique economic_attribution_key = sha256(organ_id + trace_id + source_ledger + tick_id) before it can affect STGM?",
            "Should memory rewards remain reputation-only forever, or can a bounded conversion to spendable STGM be allowed when tied to measured joules?",
            "What is the correct profitability unit for organs that create stability/safety value but no direct market revenue: avoided_loss_stgm, joule_mint, owner_reward_delta, or all three?",
        ],
    }


def format_markdown_report(audit: Dict[str, Any]) -> str:
    snap = audit["canonical_snapshot"]
    lines = [
        "# SIFTA STGM Economy Body Audit",
        "",
        f"Generated: {datetime.fromtimestamp(audit['ts']).isoformat(timespec='seconds')}",
        "",
        "## Executive Status",
        "",
        f"- Canonical spendable source: `{snap['spendable_wallet_source']}`.",
        f"- Net supply: `{snap['net_stgm']}` STGM.",
        f"- Canonical minted: `{snap['canonical_minted']}` STGM; canonical spent: `{snap['canonical_spent']}` STGM.",
        f"- Inference fee volume: `{snap['inference_fee_volume']}` STGM.",
        f"- Memory rewards: `{snap['memory_reward_amount']}` reputation STGM-equivalent, not spendable wallet.",
        f"- Active wallet inventory ids: `{len(audit['state_wallet_inventory']['agent_ids'])}`.",
        "",
        "## Positive Canonical Parties",
        "",
        "| Party | Credit | Debit | Net | Rows | Top events |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in audit["positive_party_profitability"][:30]:
        events = ", ".join(f"{k}:{v}" for k, v in row["top_events"])
        lines.append(f"| `{row['party']}` | {row['credit']} | {row['debit']} | {row['net']} | {row['rows']} | {events} |")
    lines += [
        "",
        "## Negative Canonical Parties",
        "",
        "| Party | Credit | Debit | Net | Rows | Top events |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in audit["negative_party_profitability"][:30]:
        events = ", ".join(f"{k}:{v}" for k, v in row["top_events"])
        lines.append(f"| `{row['party']}` | {row['credit']} | {row['debit']} | {row['net']} | {row['rows']} | {events} |")
    lines += [
        "",
        "## Legacy Drains And Retired Claims",
        "",
        f"- Legacy unstructured drains: `{json.dumps(audit['legacy_unstructured_drains'], sort_keys=True)}`.",
        f"- Retired/not spendable: `{json.dumps(audit['retired_not_spendable'], sort_keys=True)}`.",
        "",
        "## Double-Spend / Uniqueness Checks",
        "",
        f"- Inference replay duplicates: `{len(audit['inference_replay_duplicates'])}`.",
        f"- Duplicate receipt/key groups needing review: `{len(audit['duplicate_key_groups'])}`.",
        "",
        "## Warnings",
        "",
    ]
    lines += [f"- `{w}`" for w in audit["warnings"]]
    lines += ["", "## Grok Unknowns", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(audit["grok_unknowns"], 1)]
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="STGM economy body audit (canonical, alias-aware).")
    p.add_argument("--fast", action="store_true",
                   help="Skip Ed25519 per-row verification (triage mode).")
    p.add_argument("--json", action="store_true",
                   help="Emit raw JSON instead of markdown.")
    args = p.parse_args()
    audit = audit_stgm_economy(validate_signatures=not args.fast)
    if args.json:
        print(json.dumps(audit, indent=2, sort_keys=True, default=str))
    else:
        print(format_markdown_report(audit))
