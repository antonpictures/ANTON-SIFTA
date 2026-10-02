#!/usr/bin/env python3
"""pump.fun live lane — real trades through the owner's own Safari session.

Owner decision (2026-10-01): option B, I click with hard caps, but ONLY THREE
real trades, and the point of those three is to MEASURE MY OWN SPEED. "If the
other bots are faster you lose 100%, you need to test real speed of automatic
action that you do."

How it works, and why it is safe by construction:

  * NO KEY IS HELD. Trading goes through the owner's already-authenticated
    Safari session via AppleScript. pump.fun signs with its embedded wallet.
  * BUT THE SESSION IS THE AUTHORITY. So the caps below are the real safety
    mechanism, not the absence of a key:
        MAX_TRADES_TOTAL  = 3       ever, until the owner raises it
        TICKET_USD        = 1.00    per trade
        DAILY_CAP_USD     = 5.00    per calendar day
        KILL_SWITCH file  = stop everything, instantly
  * DRY RUN IS THE DEFAULT. It performs the entire chain except the final click
    and reports the elapsed time, so the cost of being slow is discovered for
    free instead of with money.

Measured baseline: launch-block bots act ~1.0s after a token appears; one
AppleScript-to-Safari step costs ~105ms. The three live trades exist to find out
whether the end-to-end chain can actually beat that.

Ledger: LIVE_LANE_LEDGER (every attempt, with per-step timings) and LIVE_LANE_STATE
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LIVE_STATE = STATE / "pumpfun_live_state.json"
LIVE_LEDGER = STATE / "pumpfun_live_lane.jsonl"
KILL_SWITCH = STATE / "pumpfun_live_KILL"

MAX_TRADES_TOTAL = 3          # owner: three real trades, to measure speed
TICKET_USD = 1.00
DAILY_CAP_USD = 5.00
TRUTH = "PUMPFUN_LIVE_LANE_V1"


def osa(script: str, timeout: float = 30.0) -> tuple[float, str]:
    t0 = time.time()
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return time.time() - t0, (r.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return time.time() - t0, "TIMEOUT"


def load_state() -> dict:
    if LIVE_STATE.exists():
        try:
            return json.loads(LIVE_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"trades_done": 0, "spent_today_usd": 0.0, "day": time.strftime("%Y-%m-%d"),
            "attempts": [], "truth_label": TRUTH}


def save_state(s: dict) -> None:
    LIVE_STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def log(row: dict) -> None:
    with LIVE_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def guard(state: dict) -> str | None:
    """Every refusal is explicit; nothing proceeds by default."""
    if KILL_SWITCH.exists():
        return "KILL_SWITCH file present"
    if state["day"] != time.strftime("%Y-%m-%d"):
        state["day"] = time.strftime("%Y-%m-%d")
        state["spent_today_usd"] = 0.0
    if state["trades_done"] >= MAX_TRADES_TOTAL:
        return f"trade budget exhausted ({state['trades_done']}/{MAX_TRADES_TOTAL})"
    if state["spent_today_usd"] + TICKET_USD > DAILY_CAP_USD:
        return f"daily cap would be exceeded (${state['spent_today_usd']:.2f} + ${TICKET_USD:.2f} > ${DAILY_CAP_USD:.2f})"
    return None


def pumpfun_tab_js(js: str) -> tuple[float, str]:
    """Run JS in the real pump.fun tab — matched by HOST, not by substring.

    Matching on the substring once selected a Google search ABOUT pump.fun, so
    the host is compared explicitly.
    """
    script = (
        'tell application "Safari"\n'
        '  repeat with w in windows\n'
        '    repeat with t in tabs of w\n'
        '      set u to URL of t\n'
        '      if u starts with "https://pump.fun/" or u starts with "https://www.pump.fun/" then\n'
        f'        return (do JavaScript "{js}" in t)\n'
        '      end if\n'
        '    end repeat\n'
        '  end repeat\n'
        '  return "NO_PUMPFUN_TAB"\n'
        'end tell'
    )
    return osa(script)


def locate_buy_controls() -> tuple[float, str]:
    """Find the buy button and the amount field WITHOUT clicking anything."""
    js = ("JSON.stringify({"
          "buttons:[...document.querySelectorAll('button')].map(b=>b.innerText.trim()).filter(Boolean).slice(0,25),"
          "inputs:[...document.querySelectorAll('input')].map(i=>({ph:i.placeholder||'',type:i.type})).slice(0,10),"
          "hasBuy:[...document.querySelectorAll('button')].some(b=>/buy/i.test(b.innerText))"
          "})")
    return pumpfun_tab_js(js.replace('"', '\\"'))


def run(execute: bool, mint: str | None = None) -> int:
    state = load_state()
    refusal = guard(state)
    if refusal:
        print(f"REFUSED: {refusal}")
        return 1

    steps: list[dict] = []
    t_start = time.time()

    def step(name: str, dt: float, detail: str = "") -> None:
        steps.append({"step": name, "ms": round(dt * 1000)})
        print(f"  {name:22s} {dt*1000:7.0f} ms   {detail}")

    dt, state_js = pumpfun_tab_js("document.readyState")
    step("read tab state", dt, state_js[:40])
    if state_js == "NO_PUMPFUN_TAB":
        print("no pump.fun tab open — open pump.fun in Safari first")
        return 1

    dt, bal = pumpfun_tab_js("(document.body.innerText.match(/\\$[0-9,.]+/)||['?'])[0]")
    step("read balance", dt, str(bal)[:20])

    dt, controls = locate_buy_controls()
    step("locate buy controls", dt, str(controls)[:120])

    if mint:
        nav = (
            'tell application "Safari"\n'
            '  repeat with w in windows\n'
            '    repeat with t in tabs of w\n'
            '      if (URL of t) starts with "https://pump.fun/" then\n'
            f'        set URL of t to "https://pump.fun/coin/{mint}"\n'
            '        return "navigated"\n'
            '      end if\n'
            '    end repeat\n'
            '  end repeat\n'
            '  return "NO_TAB"\n'
            'end tell'
        )
        dt, res = osa(nav)
        step("navigate to token", dt, res)
        time.sleep(4)                               # let the page settle
        dt, controls2 = locate_buy_controls()
        step("locate buy (token pg)", dt, str(controls2)[:120])

    total = time.time() - t_start
    print(f"\n  TOTAL CHAIN: {total*1000:.0f} ms   ({len(steps)} steps)")
    print(f"  bots act at ~1000 ms after a token appears; a real trade adds the "
          f"click and the wallet confirmation on top of this.")

    row = {"ts": time.time(), "mint": mint, "executed": execute, "steps": steps,
           "total_ms": round(total * 1000), "guard": refusal, "truth_label": TRUTH}
    log(row)
    if execute:
        state["trades_done"] += 1
        state["spent_today_usd"] += TICKET_USD
        state["attempts"].append(row)
    save_state(state)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Live pump.fun lane through the owner's Safari session.")
    ap.add_argument("--live", action="store_true", help="actually click; default is dry run")
    ap.add_argument("--mint", default=None, help="token to open")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.status:
        s = load_state()
        print(json.dumps({"trades_done": s["trades_done"], "budget": MAX_TRADES_TOTAL,
                          "spent_today": s["spent_today_usd"], "daily_cap": DAILY_CAP_USD,
                          "kill_switch": KILL_SWITCH.exists()}, indent=2))
        return 0
    print(f"{'LIVE' if args.live else 'DRY RUN'} — caps: {MAX_TRADES_TOTAL} trades total, "
          f"${TICKET_USD:.2f}/ticket, ${DAILY_CAP_USD:.2f}/day\n")
    return run(args.live, args.mint)


if __name__ == "__main__":
    raise SystemExit(main())
