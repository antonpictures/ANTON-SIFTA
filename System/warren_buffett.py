#!/usr/bin/env python3
"""
warren_buffett.py — The Accountant Swimmer (OBSERVE-only)
══════════════════════════════════════════════════════════════
Warren does not mint, spend, vote, or earn. He reads repair_log.jsonl
and estimates whether the Swarm's STGM production is worth the electricity.

Born at swarm genesis in spirit only — zero STGM cost, zero ledger writes
from this module (read-only analytics).

Environment (optional):
  SIFTA_KWH_USD       — $/kWh (default 0.16)
  SIFTA_NODE_WATTS    — average draw W (default 45 for Mac Studio class)
  SIFTA_STGM_USD_PEG  — if set, net "profit" vs power cost (informational only)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
LEDGER = _REPO / "repair_log.jsonl"
STATE_DIR = _REPO / ".sifta_state"

KWH_USD = float(os.environ.get("SIFTA_KWH_USD", "0.16"))
NODE_WATTS = float(os.environ.get("SIFTA_NODE_WATTS", "45"))
STGM_USD_PEG = os.environ.get("SIFTA_STGM_USD_PEG", "").strip()


def _local_serial() -> str:
    try:
        _sys = _REPO / "System"
        import sys as _s
        if str(_sys) not in _s.path:
            _s.path.insert(0, str(_sys))
        from silicon_serial import read_apple_serial
        return read_apple_serial() or "UNKNOWN_SERIAL"
    except Exception:
        return "UNKNOWN_SERIAL"


@dataclass
class LedgerScan:
    """Aggregates from repair_log.jsonl (read-only)."""

    lines_total: int = 0
    lines_parse_ok: int = 0
    # Credits by event family
    stgm_mining: float = 0.0
    stgm_foundation: float = 0.0
    stgm_utility: float = 0.0
    stgm_tx_mint: float = 0.0
    stgm_spend: float = 0.0
    inference_fees_paid: float = 0.0
    inference_fees_earned: float = 0.0
    foundation_grant_rows: int = 0
    # First / last ts for crude session span
    ts_min: Optional[float] = None
    ts_max: Optional[float] = None
    per_agent_credit: Dict[str, float] = field(default_factory=dict)

    def net_minted_into_swarm(self) -> float:
        return (
            self.stgm_mining
            + self.stgm_foundation
            + self.stgm_utility
            + self.stgm_tx_mint
            - self.stgm_spend
        )


def scan_repair_log(path: Optional[Path] = None) -> LedgerScan:
    """Passive full scan of quorum ledger. No writes."""
    p = path or LEDGER
    out = LedgerScan()
    if not p.exists():
        return out

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            out.lines_total += 1
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry: Dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue
            out.lines_parse_ok += 1

            # Timestamp parsing — accept both epoch numerics AND ISO-8601
            # strings. Prior to 2026-04-20 only numerics were honored, so
            # ISO-stamped rows (e.g. AG31 identity traces) silently
            # excluded themselves from `ts_min/ts_max`, leaving the HUD
            # reporting "newest mint N min ago" with N too high. Keep the
            # parse defensive: an unparseable string never raises here.
            ts = entry.get("timestamp") or entry.get("ts")
            t: Optional[float] = None
            if isinstance(ts, (int, float)):
                t = float(ts)
            elif isinstance(ts, str) and ts:
                try:
                    from datetime import datetime
                    s = ts.replace("Z", "+00:00")
                    t = datetime.fromisoformat(s).timestamp()
                except Exception:
                    t = None
            if t is not None:
                out.ts_min = t if out.ts_min is None else min(out.ts_min, t)
                out.ts_max = t if out.ts_max is None else max(out.ts_max, t)

            event = entry.get("event") or ""
            tx_type = entry.get("tx_type") or ""

            if event in ("MINING_REWARD", "FOUNDATION_GRANT"):
                amt = float(entry.get("amount_stgm", 0) or 0)
                mid = str(entry.get("miner_id", "")).upper()
                if event == "FOUNDATION_GRANT":
                    out.stgm_foundation += amt
                    out.foundation_grant_rows += 1
                else:
                    out.stgm_mining += amt
                if mid:
                    out.per_agent_credit[mid] = out.per_agent_credit.get(mid, 0.0) + amt

            elif event == "UTILITY_MINT":
                amt = float(entry.get("amount_stgm", 0) or 0)
                mid = str(entry.get("miner_id", "")).upper()
                out.stgm_utility += amt
                if mid:
                    out.per_agent_credit[mid] = out.per_agent_credit.get(mid, 0.0) + amt

            elif event == "INFERENCE_BORROW":
                fee = float(entry.get("fee_stgm", 0) or 0)
                bor = str(entry.get("borrower_id", "")).upper()
                lend = str(entry.get("lender_ip", "")).upper()
                out.inference_fees_paid += fee  # gross movement; net zero for swarm
                if bor:
                    out.per_agent_credit[bor] = out.per_agent_credit.get(bor, 0.0) - fee
                if lend:
                    out.per_agent_credit[lend] = out.per_agent_credit.get(lend, 0.0) + fee

            elif tx_type == "STGM_MINT":
                amt = float(entry.get("amount", 0) or 0)
                aid = str(entry.get("agent_id", "")).upper()
                out.stgm_tx_mint += amt
                if aid:
                    out.per_agent_credit[aid] = out.per_agent_credit.get(aid, 0.0) + amt

            elif tx_type == "STGM_SPEND":
                amt = float(entry.get("amount", 0) or 0)
                aid = str(entry.get("agent_id", "")).upper()
                out.stgm_spend += amt
                if aid:
                    out.per_agent_credit[aid] = out.per_agent_credit.get(aid, 0.0) - amt

            # ── Dialect C (headless) — `amount_stgm` w/o `event`/`tx_type`
            # Used by ANTIGRAVITY_CREATOR_NODE for SCAR overhead debits
            # (and historically by some MCP rows). `Kernel.inference_economy.
            # ledger_balance` already counts these in Dialect C; the
            # warren_buffett global scan was previously blind to them, so
            # the "🌐 Swarm Net Mint" line under-counted every SCAR ever
            # filed. We classify negatives as spend, positives as tx_mint
            # so the global net stays consistent with `ledger_balance`'s
            # per-agent view, and per-agent credit is signed accordingly.
            elif "amount_stgm" in entry and not event and not tx_type:
                try:
                    amt = float(entry.get("amount_stgm", 0) or 0)
                except (TypeError, ValueError):
                    amt = 0.0
                aid = str(entry.get("agent", "")).upper()
                if amt < 0:
                    out.stgm_spend += -amt
                else:
                    out.stgm_tx_mint += amt
                if aid:
                    out.per_agent_credit[aid] = out.per_agent_credit.get(aid, 0.0) + amt

    return out


def _serial_agent_balances(local_serial: str) -> Dict[str, float]:
    """Return per-agent canonical ledger balances for one silicon.

    Source of truth for both the personal Alice wallet and the serial-wide
    treasury rollup. Anything reading STGM for this silicon should call this.
    """
    out: Dict[str, float] = {}
    if not STATE_DIR.is_dir():
        return out
    try:
        import sys as _s
        if str(_REPO) not in _s.path:
            _s.path.insert(0, str(_REPO))
        from Kernel.inference_economy import ledger_balance
    except Exception:
        return out

    skip = {
        "circadian_m1", "circadian_m5", "identity_stats", "intelligence_settings",
        "m1queen_identity_anchor", "physical_registry", "scheduler_m5",
        "state_bus", "territory_manifest", "m1queen_memory",
    }
    for fp in STATE_DIR.glob("*.json"):
        key = fp.stem
        if key in skip:
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(data, dict):
                continue
        except Exception:
            continue
        if str(data.get("homeworld_serial", "")) != local_serial:
            continue
        aid = str(data.get("id") or key)
        try:
            bal = float(ledger_balance(aid))
        except Exception:
            bal = 0.0
        out[aid.upper()] = round(bal, 4)
    return out


def alice_wallet_balance(local_serial: str) -> float:
    """Alice's own personal wallet (ALICE_M5 / ALICE_M1 only).

    This is what Alice's composite identity reads from. It is NOT the
    serial-wide treasury rollup. Used by HUD for the explicit
    "Alice Wallet" line.
    """
    if not local_serial:
        return 0.0
    balances = _serial_agent_balances(local_serial)
    candidates = ("ALICE_M5", "ALICE_M1", "ALICE")
    total = 0.0
    for name in candidates:
        if name in balances:
            total += float(balances[name])
    return round(max(0.0, total), 4)


def serial_treasury_balance(local_serial: str) -> float:
    """Sum of all agents bound to one silicon (Alice + helper drones, etc.).

    This is the wider M5 / M1 node treasury rollup. Used by HUD for the
    "Node Treasury" line so it cannot be confused with Alice's own wallet.
    """
    if not local_serial:
        return 0.0
    balances = _serial_agent_balances(local_serial)
    total = sum(float(v) for v in balances.values())
    return round(max(0.0, total), 4)


def _architect_local_stgm(local_serial: str) -> float:
    """Backward-compatible alias — sum of all agents on this silicon."""
    return serial_treasury_balance(local_serial)


def profit_report() -> Dict[str, Any]:
    """
    Warren's report: STGM flows vs rough electricity model.
    STGM has no on-chain peg unless SIFTA_STGM_USD_PEG is set.
    """
    scan = scan_repair_log()
    serial = _local_serial()
    architect_slice = _architect_local_stgm(serial)

    hours = 0.0
    if scan.ts_min is not None and scan.ts_max is not None and scan.ts_max > scan.ts_min:
        hours = (scan.ts_max - scan.ts_min) / 3600.0
    if hours <= 0:
        hours = 1.0

    kwh = (NODE_WATTS / 1000.0) * hours
    usd_power = kwh * KWH_USD

    stgm_usd = None
    net_usd = None
    verdict = "STGM unpegged — power cost is informational only."
    if STGM_USD_PEG:
        try:
            peg = float(STGM_USD_PEG)
            gross_stgm = scan.net_minted_into_swarm()
            stgm_usd = gross_stgm * peg
            net_usd = stgm_usd - usd_power
            if net_usd > usd_power * 0.2:
                verdict = "Swarm economic surplus vs modeled power (pegged view)."
            elif net_usd >= 0:
                verdict = "Roughly breaking even vs modeled power (pegged view)."
            else:
                verdict = "Modeled power cost exceeds pegged STGM value — feed more real work."
        except ValueError:
            pass

    return {
        "observer": "WARREN_BUFFETT",
        "state": "OBSERVE",
        "silicon": serial,
        "ledger_lines": scan.lines_total,
        "ledger_parse_ok": scan.lines_parse_ok,
        "foundation_grant_rows": scan.foundation_grant_rows,
        "stgm_mining": round(scan.stgm_mining, 4),
        "stgm_foundation": round(scan.stgm_foundation, 4),
        "stgm_utility_mint": round(scan.stgm_utility, 4),
        "stgm_dialect_mint": round(scan.stgm_tx_mint, 4),
        "stgm_spend": round(scan.stgm_spend, 4),
        "net_minted_estimate": round(scan.net_minted_into_swarm(), 4),
        "architect_local_agent_credits_sum": architect_slice,
        "modeled_session_hours": round(hours, 4),
        "modeled_kwh": round(kwh, 6),
        "modeled_usd_power": round(usd_power, 6),
        "stgm_usd_assumption": stgm_usd,
        "net_usd_vs_power": net_usd,
        "verdict": verdict,
        "ts": time.time(),
    }


def ascii_report() -> str:
    r = profit_report()
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  WARREN BUFFETT — Architect economics (read-only)         ║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║  Silicon     : {str(r['silicon'])[:36]:<36} ║",
        f"║  Ledger lines: {r['ledger_lines']:<36} ║",
        f"║  FOUNDATION  : {r['foundation_grant_rows']} rows  (+{r['stgm_foundation']} STGM)      ║",
        f"║  UTILITY_MINT: {r['stgm_utility_mint']:<36} ║",
        f"║  Mining      : {r['stgm_mining']:<36} ║",
        f"║  Net mint est: {r['net_minted_estimate']:<36} ║",
        f"║  Local slice : {r['architect_local_agent_credits_sum']} STGM (agent file ∩ serial) ║",
        f"║  ~kWh        : {r['modeled_kwh']:<36} ║",
        f"║  ~USD power  : ${r['modeled_usd_power']:<35} ║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║  {r['verdict'][:56]:<56} ║",
        "╚══════════════════════════════════════════════════════════╝",
    ]
    return "\n".join(lines)


def persist_snapshot() -> Path:
    """Optional: write latest snapshot for other tools (not ledger truth)."""
    out = STATE_DIR / "warren_snapshot.json"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = profit_report()
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(ascii_report())
    p = persist_snapshot()
    print(f"\nSnapshot: {p}")
