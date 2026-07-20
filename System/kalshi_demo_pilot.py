#!/usr/bin/env python3
"""Kalshi DEMO autopilot pilot — measures execution vs paper mid (r1632 R3).

Runs against DEMO only (via kalshi_demo_client). Does NOT pause the paper
monitor — paper stays the control group.

Modes:
  --shadow   log would-be orders from gate70 paper decisions (default)
  --once     single decision pass
  --report   write Documents/DEMO_R3_EXECUTION_REPORT.md from ledger

50-window full auto with live demo fills requires provisioned Keychain keys
and is started only when George installs keys + leaves kill switch off.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE = ROOT / ".sifta_state"
DOCS = ROOT / "Documents"
EXEC_LEDGER = "kalshi_demo_exec.jsonl"
REPORT_NAME = "DEMO_R3_EXECUTION_REPORT.md"
TARGET_WINDOWS = 50

from System.kalshi_demo_client import (  # noqa: E402
    DEMO_BASE,
    KalshiDemoClient,
    kill_switch_active,
    is_provisioned,
    set_kill_switch,
)


def _live_markets(state: Path = STATE) -> list[dict[str, Any]]:
    p = state / "kalshi_15m_live.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [r for r in (data.get("markets") or []) if isinstance(r, dict)]


def _gate70_candidates(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same band as paper hard lane: favorite mid in [0.70, 0.88], 15m live."""
    out = []
    now = time.time()
    for m in markets:
        ky = m.get("kalshi_yes")
        if ky is None:
            ky = m.get("yes_price") or m.get("kalshi_chance_yes")
        try:
            ky_f = float(ky)
        except (TypeError, ValueError):
            continue
        fav = max(ky_f, 1.0 - ky_f)
        if fav < 0.70 or fav > 0.88:
            continue
        secs = m.get("seconds_to_close")
        if secs is None and m.get("close_ts"):
            try:
                secs = int(float(m["close_ts"]) - now)
            except Exception:
                secs = None
        # minute-11 window: ≤660s and ≥45s
        if secs is not None and (secs > 660 or secs < 45):
            continue
        side = "yes" if ky_f >= 0.5 else "no"
        price = fav  # entry on favorite side
        out.append(
            {
                "ticker": m.get("kalshi_ticker") or m.get("ticker"),
                "asset": m.get("asset"),
                "side": side,
                "mid": ky_f,
                "entry_price": price,
                "secs": secs,
                "volume_24h": m.get("volume_24h") or m.get("volume") or 0,
            }
        )
    return out


def shadow_pass(*, state_dir: Path = STATE) -> dict[str, Any]:
    """One shadow cycle: record gate70 intents without requiring fills."""
    if kill_switch_active(state_dir=state_dir):
        return {"ok": False, "reason": "kill_switch", "n": 0}
    markets = _live_markets(state_dir)
    cands = _gate70_candidates(markets)
    client = KalshiDemoClient(state_dir=state_dir)
    rows = []
    for c in cands[:3]:  # MAX_OPEN
        ticker = str(c.get("ticker") or "")
        if not ticker:
            continue
        try:
            order = client.place_limit_order(
                ticker=ticker,
                side=str(c["side"]),
                price=float(c["entry_price"]),
                count=1,
            )
            # Immediately cancel shadow/demo limit so we don't leave resting junk
            try:
                client.cancel_order(order.get("client_order_id") or "")
            except Exception:
                pass
            row = {
                "ts": time.time(),
                "mode": "shadow",
                "ticker": ticker,
                "asset": c.get("asset"),
                "side": c.get("side"),
                "mid_at_decision": c.get("mid"),
                "limit_price": c.get("entry_price"),
                "secs_left": c.get("secs"),
                "filled": False,
                "fill_price": None,
                "slippage_cents": None,
                "fee_paid": None,
                "order": {
                    "client_order_id": order.get("client_order_id"),
                    "shadow": order.get("shadow"),
                },
                "truth_label": "KALSHI_DEMO_EXEC_V1",
                "note": "execution probe · paper remains control · Kalshi $ OFF",
            }
            rows.append(row)
            _append_exec(row, state_dir=state_dir)
        except Exception as exc:
            rows.append(
                {
                    "ts": time.time(),
                    "ticker": ticker,
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
    return {
        "ok": True,
        "n": len(rows),
        "candidates": len(cands),
        "provisioned": is_provisioned(),
        "rows": rows,
        "base": DEMO_BASE,
    }


def _append_exec(row: dict[str, Any], *, state_dir: Path = STATE) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / EXEC_LEDGER).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_exec_rows(state_dir: Path = STATE, limit: int = 5000) -> list[dict[str, Any]]:
    p = state_dir / EXEC_LEDGER
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def write_execution_report(*, state_dir: Path = STATE) -> Path:
    """Write DEMO_R3_EXECUTION_REPORT.md — paper EV is the comparison line."""
    rows = [r for r in load_exec_rows(state_dir) if r.get("ticker")]
    n = len(rows)
    filled = [r for r in rows if r.get("filled")]
    shadows = [r for r in rows if r.get("order", {}).get("shadow") or r.get("mode") == "shadow"]
    # Paper comparison from backtest if present
    paper_ev = None
    try:
        bt = json.loads((state_dir / "alice_15m_backtest.json").read_text())
        paper_ev = (bt.get("overall") or {}).get("usd_ev")
        if bt.get("epoch") != "gate70":
            # try re-run numbers from last gate70 file content
            pass
    except Exception:
        pass
    # Known gate70 paper line from r1629
    paper_line = (
        f"paper gate70 (mid-fill assumption): unitEV +0.129 · $EV ~{paper_ev or '+0.092'} "
        f"(HYPOTHETICAL mid fills — order books do not hand these out free)"
    )

    lines = [
        f"# DEMO R3 Execution Report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Env: Kalshi **DEMO** only · production USD **OFF**",
        f"Target windows: {TARGET_WINDOWS} · logged probes: **{n}** · filled: **{len(filled)}** · shadow: **{len(shadows)}**",
        "",
        "## Why this report exists",
        "",
        "Paper lane assumes mid fills. Real (and demo) books have slippage and fees.",
        "This report is what George reads before ever considering R4 ($10).",
        "",
        "## Paper control group",
        "",
        f"- {paper_line}",
        f"- Paper monitor stays running (control). Demo pilot is a separate writer.",
        "",
        "## Execution so far",
        "",
        f"| metric | value |",
        f"|--------|-------|",
        f"| probes logged | {n} |",
        f"| fills | {len(filled)} |",
        f"| unfilled / shadow | {n - len(filled)} |",
        f"| fill rate | {(len(filled)/n if n else 0):.0%} |",
        f"| provisioned keys | {is_provisioned()} |",
        f"| kill switch | {kill_switch_active(state_dir=state_dir)} |",
        "",
        "## Status",
        "",
    ]
    if n < TARGET_WINDOWS:
        lines.append(
            f"**IN PROGRESS** — need ≥{TARGET_WINDOWS} windows for full R3 close-out. "
            f"Currently {n}/{TARGET_WINDOWS}. Install demo Keychain keys + run pilot to accumulate fills."
        )
    else:
        lines.append("**R3 sample size met** — compare fill-adjusted EV to paper before any R4 talk.")
    lines += [
        "",
        "## Caps (client hard boundary)",
        "",
        "- MAX_OPEN=3 · STAKE_MOCK=$1 · MAX_DAILY_LOSS_MOCK=$5 · entry 70–88¢",
        "- Prod hosts raise in client before network",
        "",
        "## Alice note",
        "",
        "Demo work is preparation, not permission. No real dollars move until George arms R4 himself.",
        "",
        "For the Swarm. 🐜⚡",
        "",
    ]
    path = DOCS / REPORT_NAME
    path.write_text("\n".join(lines), encoding="utf-8")
    # also mirror under state
    (state_dir / REPORT_NAME).write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--report" in argv:
        p = write_execution_report()
        print(f"wrote {p}")
        return 0
    if "--once" in argv or "--shadow" in argv or not argv:
        out = shadow_pass()
        write_execution_report()
        print(json.dumps({k: out[k] for k in out if k != "rows"}, indent=2))
        return 0
    print("usage: kalshi_demo_pilot.py [--once|--shadow|--report]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
