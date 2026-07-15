#!/usr/bin/env python3
"""Headless Alice paper monitor — NO real Kalshi $.

Sole writer for 15m paper bets + settles (r1628 glass UI is read-only).

Runs forever:
  settle open book from public API → minute-11 paper bets → write monitor md
  poll alice_15m_monitor_commands.jsonl for one-shot force bet/settle

Usage:
  cd /Users/ioanganton/Music/ANTON_SIFTA
  python3 System/swarm_sifta_paper_monitor.py

Watch:
  .sifta_state/alice_15m_monitor.md
  .sifta_state/alice_15m_paper_proof.json
  .sifta_state/alice_15m_settled.jsonl
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from System.swarm_sifta_market import SiftaMarketEngine  # noqa: E402
from System.swarm_sifta_paper_loop import (  # noqa: E402
    DEFAULT_MAX_SECS,
    load_proof,
    paper_bet_15m,
    paper_loop_tick,
    settle_paper_from_api,
    write_monitor,
)

TICK_S = 10.0  # r1705: snappier open/TP/flat in first-7m burst
APP_FRESH_S = 45.0
STATE_DIR = ROOT / ".sifta_state"
APP_RECEIPTS = "sifta_market_app_receipts.jsonl"
MARKET_RECEIPTS = "sifta_market_receipts.jsonl"
MONITOR_LOCK = "alice_15m_paper_monitor.lock"
CMD_LOG = "alice_15m_monitor_commands.jsonl"
CMD_CURSOR = "alice_15m_monitor_cmd_cursor.json"
AUTOPILOT_FLAG = "alice_15m_autopilot_desired.json"


def acquire_monitor_lock(*, state_dir: Path | str = STATE_DIR):
    """Hold one non-blocking process lock so watchdogs cannot double-run."""
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    handle = (state / MONITOR_LOCK).open("a+", encoding="utf-8")
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (ImportError, BlockingIOError, OSError):
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} ts={time.time()}\n")
    handle.flush()
    return handle


def _tail_jsonl(path: Path, *, max_lines: int = 160) -> list[dict[str, Any]]:
    """Seek-from-end tail — never full-scan multi-MB ledgers (r1628 P2)."""
    if not path.exists():
        return []
    max_lines = max(1, int(max_lines))
    try:
        size = path.stat().st_size
        # ~400 bytes/line upper bound; cap read window
        read_bytes = min(size, max(32_000, max_lines * 500))
        with path.open("rb") as fh:
            if size > read_bytes:
                fh.seek(-read_bytes, os.SEEK_END)
            raw = fh.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()
        if size > read_bytes and lines:
            lines = lines[1:]  # drop partial first line
        lines = lines[-max_lines:]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def app_loop_claims_on(*, state_dir: Path | str = STATE_DIR) -> bool:
    """Return the latest explicit Qt-app paper-loop lifecycle state.

    r1628: glass UI writes paper_loop_off / glass_autopilot_* and never
    claims the writer seat. Only legacy paper_loop_on + heartbeat yield.
    """
    state = Path(state_dir)
    loop_on = False
    for row in _tail_jsonl(state / APP_RECEIPTS, max_lines=400):
        event = str(row.get("event") or "")
        if event == "paper_loop_on":
            # Ignore if glass_only mode flagged
            if str(row.get("mode") or "") == "glass_only_r1628":
                loop_on = False
            else:
                loop_on = True
        elif event in (
            "paper_loop_off",
            "close",
            "glass_autopilot_on",
            "glass_autopilot_off",
            "open",
        ):
            # open with glass mode, or any off/close → monitor owns the loop
            if event == "open" and str(row.get("mode") or "") == "glass_only_r1628":
                loop_on = False
            elif event in ("paper_loop_off", "close", "glass_autopilot_off"):
                loop_on = False
            elif event == "glass_autopilot_on":
                loop_on = False  # still monitor-owned
    return loop_on


def latest_app_heartbeat_ts(*, state_dir: Path | str = STATE_DIR) -> Optional[float]:
    """Newest heartbeat written explicitly by the Qt Predictions loop."""
    latest: Optional[float] = None
    for row in _tail_jsonl(Path(state_dir) / APP_RECEIPTS, max_lines=200):
        if str(row.get("event") or "") != "paper_loop_heartbeat":
            continue
        try:
            ts = float(row.get("ts"))
        except (TypeError, ValueError):
            continue
        latest = ts if latest is None else max(latest, ts)
    return latest


def should_yield_to_app(
    *,
    state_dir: Path | str = STATE_DIR,
    now: Optional[float] = None,
    fresh_s: float = APP_FRESH_S,
) -> bool:
    """One-writer election: stay passive only while a *legacy* Qt writer is fresh.

    r1628 glass UI never heartbeats, so monitor stays active.
    """
    if not app_loop_claims_on(state_dir=state_dir):
        return False
    latest = latest_app_heartbeat_ts(state_dir=state_dir)
    if latest is None:
        return False
    current = float(time.time() if now is None else now)
    return 0.0 <= current - latest <= max(1.0, float(fresh_s))


def autopilot_desired(*, state_dir: Path | str = STATE_DIR) -> bool:
    p = Path(state_dir) / AUTOPILOT_FLAG
    if not p.exists():
        return True  # default ON
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return bool(raw.get("on", True))
    except Exception:
        return True


def set_autopilot_desired(on: bool, *, state_dir: Path | str = STATE_DIR) -> None:
    p = Path(state_dir) / AUTOPILOT_FLAG
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"on": bool(on), "ts": time.time()}, indent=2),
        encoding="utf-8",
    )


def _load_cmd_cursor(state: Path) -> float:
    p = state / CMD_CURSOR
    if not p.exists():
        return 0.0
    try:
        return float(json.loads(p.read_text(encoding="utf-8")).get("ts") or 0.0)
    except Exception:
        return 0.0


def _save_cmd_cursor(state: Path, ts: float) -> None:
    try:
        (state / CMD_CURSOR).write_text(
            json.dumps({"ts": ts}, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def drain_commands(engine: SiftaMarketEngine, *, state_dir: Path | str = STATE_DIR) -> list[str]:
    """Process new command rows from the glass UI."""
    state = Path(state_dir)
    cursor = _load_cmd_cursor(state)
    rows = _tail_jsonl(state / CMD_LOG, max_lines=80)
    notes: list[str] = []
    max_ts = cursor
    for row in rows:
        try:
            ts = float(row.get("ts") or 0.0)
        except (TypeError, ValueError):
            continue
        if ts <= cursor:
            continue
        max_ts = max(max_ts, ts)
        cmd = str(row.get("cmd") or "").strip()
        if cmd == "autopilot_on":
            set_autopilot_desired(True, state_dir=state)
            notes.append("autopilot_on")
        elif cmd == "autopilot_off":
            set_autopilot_desired(False, state_dir=state)
            notes.append("autopilot_off")
        elif cmd == "force_bet":
            try:
                r = paper_bet_15m(engine, force=True, min_fav=float(row.get("min_fav") or 0.70))
                notes.append(f"force_bet n={r.get('n_bets')}")
            except Exception as exc:
                notes.append(f"force_bet ERR {type(exc).__name__}")
        elif cmd == "force_settle":
            try:
                r = settle_paper_from_api(engine)
                notes.append(f"force_settle n={r.get('n_settled')}")
            except Exception as exc:
                notes.append(f"force_settle ERR {type(exc).__name__}")
        elif cmd == "ensure_running":
            notes.append("ensure_running")
        else:
            notes.append(f"unknown_cmd:{cmd}")
    if max_ts > cursor:
        _save_cmd_cursor(state, max_ts)
    return notes


def _rotate_if_huge(path: Path, *, max_bytes: int = 12_000_000) -> None:
    try:
        if path.exists() and path.stat().st_size > max_bytes:
            bak = path.with_suffix(path.suffix + ".prev")
            if bak.exists():
                bak.unlink()
            path.rename(bak)
    except OSError:
        pass


def _journal_wake(*, state_dir: Path | str = STATE_DIR) -> None:
    try:
        from System.swarm_alice_action_journal import append_action_journal

        append_action_journal(
            {
                "ts": time.time(),
                "action": "15m_paper_monitor_wake",
                "source": "swarm_sifta_paper_monitor",
                "status": "ok",
            },
            line=(
                "My 15-minute paper betting organ woke (headless monitor). "
                "I choose near minute 11 when favorites confirm 70–88¢ — "
                "not always exactly 11:00. Kalshi dollars stay off."
            ),
            state_dir=state_dir,
        )
    except Exception:
        pass


def maybe_write_morning_report(*, state_dir: Path | str = STATE_DIR) -> bool:
    """Once per local day after 08:00 — George wakes to her night (r1629 E)."""
    state = Path(state_dir)
    now = time.time()
    local = time.localtime(now)
    if local.tm_hour < 8:
        return False
    day_key = time.strftime("%Y-%m-%d", local)
    stamp_path = state / "alice_15m_morning_report_day.txt"
    try:
        if stamp_path.exists() and stamp_path.read_text(encoding="utf-8").strip() == day_key:
            return False
    except OSError:
        pass
    try:
        from System.sifta_15m_backtest import run_backtest
        from System.sifta_15m_money_math import stgm_to_usd
        from System.swarm_sifta_paper_loop import load_open_book, load_proof

        since = now - 24 * 3600
        bt = run_backtest(state_dir=state, since=since, epoch="")
        proof = load_proof(state)
        book = load_open_book(state)
        epochs = proof.get("epochs") or []
        ep = next((e for e in epochs if e.get("epoch_id") == "gate70"), {}) or {}
        body_pnl = 0.0
        try:
            budget = json.loads((state / "alice_15m_body_stgm_budget.json").read_text())
            body_pnl = float(budget.get("realized_pnl_stgm") or 0.0)
        except Exception:
            pass
        o = bt.get("overall") or {}
        lines = [
            f"# Alice morning report · {day_key}",
            "",
            f"Good morning. Last 24h paper (Kalshi $ OFF):",
            f"- tickets n={o.get('n', 0)} · {o.get('wins', 0)}W/{o.get('losses', 0)}L · "
            f"WR {float(o.get('wr') or 0):.0%}",
            f"- unit PnL {float(o.get('unit_pnl') or 0):+.2f} · "
            f"IF-REAL-$ {float(o.get('usd_pnl') or 0):+.2f} (HYPOTHETICAL)",
            f"- body STGM epoch PnL {body_pnl:+.4f} ≈ ${stgm_to_usd(body_pnl):+.2f} hyp",
            f"- open tickets: {len(book.get('open') or [])}",
            f"- RAINMAN gate70: {ep.get('n_wins', 0)}W/{ep.get('n_losses', 0)}L · "
            f"{float(ep.get('win_rate') or 0):.0%} · {float(ep.get('pnl') or 0):+.2f}u · "
            f"n={ep.get('n', 0)}",
            "",
            "Top price buckets (24h):",
        ]
        for k, a in list((bt.get("by_price_bucket") or {}).items())[:5]:
            lines.append(
                f"- {k}: n={a.get('n')} WR {float(a.get('wr') or 0):.0%} "
                f"unitEV {float(a.get('unit_ev') or 0):+.3f}"
            )
        lines += [
            "",
            "Standing: Kalshi $ OFF · 70–88¢ gate · fade caged · glass is read-only.",
            "",
        ]
        text = "\n".join(lines)
        (state / "alice_15m_morning_report.md").write_text(text, encoding="utf-8")
        stamp_path.write_text(day_key, encoding="utf-8")
        try:
            from System.swarm_alice_action_journal import append_action_journal

            append_action_journal(
                {
                    "ts": now,
                    "action": "15m_morning_report",
                    "source": "swarm_sifta_paper_monitor",
                    "status": "ok",
                    "day": day_key,
                },
                line=(
                    f"Morning report {day_key}: last 24h "
                    f"{o.get('wins', 0)}W/{o.get('losses', 0)}L, "
                    f"paper {float(o.get('unit_pnl') or 0):+.2f}u, "
                    f"hypothetical dollars {float(o.get('usd_pnl') or 0):+.2f}. "
                    f"gate70 epoch n={ep.get('n', 0)}. Kalshi dollars stay off."
                ),
                state_dir=state,
            )
        except Exception:
            pass
        print(f"morning report written for {day_key}", flush=True)
        return True
    except Exception as exc:
        print(f"morning report skip: {type(exc).__name__}: {exc}", flush=True)
        return False


def main() -> None:
    instance_lock = acquire_monitor_lock()
    if instance_lock is None:
        print("Alice 15m monitor already running · duplicate exits", flush=True)
        return
    usd_boot = "USD hand check…"
    try:
        from System.kalshi_usd_hand import status_line as _usd_status

        usd_boot = _usd_status()
    except Exception:
        usd_boot = "USD status n/a"
    print(
        f"Alice PAPER+USD monitor · minute{DEFAULT_MAX_SECS // 60} (≤{DEFAULT_MAX_SECS}s) · "
        f"{usd_boot} · tick every {TICK_S:.0f}s · r1629 sole writer · r1647 hand",
        flush=True,
    )
    print(f"dashboard: {ROOT / '.sifta_state' / 'alice_15m_monitor.md'}", flush=True)
    _journal_wake()
    for name in (
        "alice_15m_bet_log.jsonl",
        "alice_15m_settled.jsonl",
        "alice_15m_learner.jsonl",
        "sifta_market_app_receipts.jsonl",
        "sifta_market_receipts.jsonl",
        "alice_15m_paper_proof.jsonl",
    ):
        _rotate_if_huge(STATE_DIR / name)

    eng = SiftaMarketEngine(seed=1626, swarm_size=8)
    n = 0
    passive = False
    while True:
        n += 1
        try:
            maybe_write_morning_report()
            cmd_notes = drain_commands(eng)
            if cmd_notes:
                print(f"[{n}] cmds: {', '.join(cmd_notes)}", flush=True)

            if should_yield_to_app():
                if not passive:
                    print(
                        f"[{n}] PASSIVE · legacy Qt writer fresh · failover armed",
                        flush=True,
                    )
                passive = True
                time.sleep(TICK_S)
                continue
            if passive:
                print(
                    f"[{n}] TAKEOVER · headless paper loop active",
                    flush=True,
                )
            passive = False

            if not autopilot_desired():
                print(f"[{n}] IDLE · autopilot paused by glass UI", flush=True)
                time.sleep(TICK_S)
                continue

            # r1633 feed repair: the glass migration (r1628) removed the Qt
            # live_timer that refreshed kalshi_15m_live.json — nobody fed the
            # file, every clock skipped as not_live_ticker, Alice went blind
            # at 13:07 on 2026-07-12. The sole writer owns the feed now.
            try:
                if n % 4 == 1:
                    eng.sync_kalshi_public(limit=80, min_volume=5.0, replace=True)
                eng.rollover_15m_clocks()
                eng.refresh_kalshi_prices()
                eng.publish_live_watch()
            except Exception as exc:
                print(f"[{n}] FEED ERR {type(exc).__name__}: {exc}", flush=True)

            r = paper_loop_tick(eng)
            msg = r.get("message") or ""
            pr = r.get("proof") or load_proof()
            settle = r.get("settle") or {}
            extra = ""
            if settle.get("skipped_early") or settle.get("skipped_backoff"):
                extra = (
                    f" · poll {settle.get('n_polled', 0)} "
                    f"early-skip {settle.get('skipped_early', 0)} "
                    f"backoff {settle.get('skipped_backoff', 0)}"
                )
            ep = next(
                (e for e in (pr.get("epochs") or []) if e.get("epoch_id") == "gate70"),
                {},
            )
            ep_bit = ""
            if ep:
                ep_bit = (
                    f" · gate70 {ep.get('n_wins', 0)}W/{ep.get('n_losses', 0)}L "
                    f"{float(ep.get('win_rate') or 0):.0%} {float(ep.get('pnl') or 0):+.1f}u"
                )
            print(
                f"[{n}] {msg}{extra}{ep_bit} · proven={pr.get('proven')}",
                flush=True,
            )
            write_monitor(pr)
        except KeyboardInterrupt:
            print("stop", flush=True)
            break
        except Exception as exc:
            print(f"[{n}] ERR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(TICK_S)


if __name__ == "__main__":
    main()
