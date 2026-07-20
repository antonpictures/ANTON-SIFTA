#!/usr/bin/env python3
"""Backtest harness over alice_15m_settled.jsonl (r1629 B).

Usage:
  python3 System/sifta_15m_backtest.py
  python3 System/sifta_15m_backtest.py --epoch gate70 --since 1752309360

Writes:
  .sifta_state/alice_15m_backtest.md
  .sifta_state/alice_15m_backtest.json
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE = ROOT / ".sifta_state"
SETTLED = "alice_15m_settled.jsonl"
GATE70_START = 1752309360.0


def _tail_jsonl(path: Path, limit: int = 50_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    size = path.stat().st_size
    read_n = min(size, max(256_000, limit * 400))
    with path.open("rb") as fh:
        if size > read_n:
            fh.seek(-read_n, 2)
        raw = fh.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    if size > read_n and lines:
        lines = lines[1:]
    rows = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("win") is not None:
            rows.append(row)
    return rows


def _bucket_price(p: float) -> str:
    c = int(round(float(p) * 100))
    if c < 70:
        return "<70"
    if c < 80:
        return "70-79"
    if c <= 88:
        return "80-88"
    return ">88"


def _depth_bucket(secs: Optional[float]) -> str:
    if secs is None:
        return "unknown"
    s = int(secs)
    if s > 660:
        return ">11m"
    if s > 480:
        return "8-11m"
    if s > 300:
        return "5-8m"
    if s > 120:
        return "2-5m"
    return "<2m"


def run_backtest(
    *,
    state_dir: Path | str = STATE,
    since: float = 0.0,
    epoch: str = "",
) -> dict[str, Any]:
    from System.sifta_15m_money_math import dollar_pnl_if_real

    state = Path(state_dir)
    if state.name != ".sifta_state":
        state = state / ".sifta_state"
    rows = _tail_jsonl(state / SETTLED)
    if epoch == "gate70" and since <= 0:
        since = GATE70_START

    filtered = []
    for r in rows:
        ts = float(r.get("ts") or 0.0)
        if since and ts < since:
            continue
        price = float(r.get("price") or 0.5)
        if epoch == "gate70" and (price < 0.70 or price > 0.88):
            continue
        win = bool(r.get("win"))
        unit = float(r.get("pnl") or 0.0)
        usd = float(r.get("if_real_usd") or dollar_pnl_if_real(price, win=win))
        filtered.append(
            {
                **r,
                "price": price,
                "unit_pnl": unit,
                "usd_hyp": usd,
                "price_bucket": _bucket_price(price),
                "depth": _depth_bucket(r.get("secs_left_at_entry") or r.get("secs")),
                "hour": time.localtime(ts).tm_hour if ts else -1,
            }
        )

    def _agg(items: list[dict]) -> dict[str, Any]:
        n = len(items)
        if not n:
            return {"n": 0, "wins": 0, "losses": 0, "wr": 0.0, "unit_ev": 0.0, "usd_ev": 0.0}
        wins = sum(1 for x in items if x.get("win"))
        unit_sum = sum(float(x.get("unit_pnl") or 0) for x in items)
        usd_sum = sum(float(x.get("usd_hyp") or 0) for x in items)
        return {
            "n": n,
            "wins": wins,
            "losses": n - wins,
            "wr": round(wins / n, 4),
            "unit_ev": round(unit_sum / n, 4),
            "usd_ev": round(usd_sum / n, 4),
            "unit_pnl": round(unit_sum, 4),
            "usd_pnl": round(usd_sum, 4),
        }

    by_bucket: dict[str, list] = defaultdict(list)
    by_asset: dict[str, list] = defaultdict(list)
    by_depth: dict[str, list] = defaultdict(list)
    by_hour: dict[str, list] = defaultdict(list)
    for r in filtered:
        by_bucket[r["price_bucket"]].append(r)
        by_asset[str(r.get("asset") or "?")].append(r)
        by_depth[r["depth"]].append(r)
        by_hour[str(r.get("hour"))].append(r)

    out = {
        "truth_label": "SIFTA_15M_BACKTEST_V1",
        "ts": time.time(),
        "epoch": epoch or "all",
        "since": since,
        "n": len(filtered),
        "overall": _agg(filtered),
        "by_price_bucket": {k: _agg(v) for k, v in sorted(by_bucket.items())},
        "by_asset": {k: _agg(v) for k, v in sorted(by_asset.items())},
        "by_clock_depth": {k: _agg(v) for k, v in sorted(by_depth.items())},
        "by_hour": {k: _agg(v) for k, v in sorted(by_hour.items(), key=lambda x: int(x[0]) if x[0].lstrip('-').isdigit() else 0)},
        "note": "Kalshi $ OFF · usd_* are HYPOTHETICAL $1 tickets net-of-fee mult",
    }

    # Markdown
    lines = [
        f"# Alice 15m backtest · epoch={out['epoch']} · n={out['n']}",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Overall",
        f"- W/L: {out['overall']['wins']}W/{out['overall']['losses']}L · WR {out['overall']['wr']:.0%}",
        f"- Unit EV/ticket: {out['overall']['unit_ev']:+.4f} · total {out['overall']['unit_pnl']:+.2f}",
        f"- IF-REAL-$ EV/ticket: {out['overall']['usd_ev']:+.4f} · total {out['overall']['usd_pnl']:+.2f} (HYPOTHETICAL)",
        "",
        "## By price bucket",
        "| Bucket | n | WR | unit EV | $ EV |",
        "|--------|---|----|---------|------|",
    ]
    for k, a in out["by_price_bucket"].items():
        lines.append(
            f"| {k} | {a['n']} | {a['wr']:.0%} | {a['unit_ev']:+.3f} | {a['usd_ev']:+.3f} |"
        )
    lines += ["", "## By asset", "| Asset | n | WR | unit EV | $ EV |", "|-------|---|----|---------|------|"]
    for k, a in out["by_asset"].items():
        lines.append(
            f"| {k} | {a['n']} | {a['wr']:.0%} | {a['unit_ev']:+.3f} | {a['usd_ev']:+.3f} |"
        )
    lines += [
        "",
        "## Standing rules",
        "- Kalshi USD OFF",
        "- Gate 70–88¢ is the hard lane under study",
        "- Backtest before any live knob change",
        "",
    ]
    md = "\n".join(lines)
    state.mkdir(parents=True, exist_ok=True)
    (state / "alice_15m_backtest.md").write_text(md, encoding="utf-8")
    (state / "alice_15m_backtest.json").write_text(
        json.dumps(out, indent=2, sort_keys=True), encoding="utf-8"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Alice 15m paper backtest")
    ap.add_argument("--since", type=float, default=0.0)
    ap.add_argument("--epoch", type=str, default="")
    args = ap.parse_args()
    out = run_backtest(since=args.since, epoch=args.epoch)
    print(
        f"backtest n={out['n']} WR={out['overall']['wr']:.0%} "
        f"unitEV={out['overall']['unit_ev']:+.3f} "
        f"$EV={out['overall']['usd_ev']:+.3f} → .sifta_state/alice_15m_backtest.md"
    )


if __name__ == "__main__":
    main()
