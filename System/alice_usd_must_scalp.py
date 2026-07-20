#!/usr/bin/env python3
"""r1698/r1723 — Alice US$ places **only as exact STGM paper copy**.

r1723 owner shout: freestyle must_scalp bought BTC/ETH NO while STGM OPEN was
empty — that is NOT listening. Cash may place **only** when paper has the same
asset/side open. No independent field hunting.

  • lane + hand LIVE
  • paper open book has tickets → mirror each (maybe_mirror_paper_bet)
  • paper empty → SIT `stgm_copy_only_no_paper` (valid — do not freelance)
  • band / never-sell-loss / ammo still apply on the mirror path

Truth: ALICE_USD_MUST_SCALP_V1
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_USD_MUST_SCALP_V1"
SIT_FILE = "alice_usd_sit_reason.json"
LOG = "alice_usd_must_scalp.jsonl"
WINDOW_FILE = "alice_usd_must_scalp_windows.json"
# r1720 owner: more tickers Alice knows (charts + liquid books). DOGE joins
# majors; HYPE liquid enough for cash when armed. ZEC/NEAR stay dust.
MAJORS = ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "HYPE")
WEIRD = frozenset({"ZEC", "NEAR"})


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _log(row: dict[str, Any], *, state_dir: Path) -> None:
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("truth_label", TRUTH)
    try:
        with (state_dir / LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _write_sit(reason: str, detail: dict[str, Any], *, state_dir: Path) -> None:
    row = {
        "ts": time.time(),
        "reason": reason,
        "detail": detail,
        "owner_note": (
            "Alice SIT — do NOT manual gamble. Empty is a valid trade. "
            "She only enters field-side 40–65¢ liquid majors."
        ),
        "truth_label": TRUTH,
    }
    try:
        (state_dir / SIT_FILE).write_text(
            json.dumps(row, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass
    _log({"event": "sit", **row}, state_dir=state_dir)


def _window_id(marks: list[dict[str, Any]]) -> str:
    for m in marks:
        t = str(m.get("ticker") or "")
        if t:
            parts = t.split("-")
            if len(parts) >= 2:
                return parts[1]
    return time.strftime("%Y%m%d%H%M")


def _load_marks(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / "kalshi_15m_live.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    now = time.time()
    for m in data.get("markets") or []:
        if not isinstance(m, dict):
            continue
        a = str(m.get("asset") or "").upper()
        if not a:
            continue
        yes = m.get("kalshi_yes")
        if yes is None:
            yes = m.get("yes_price")
        if yes is None:
            continue
        secs = m.get("seconds_to_close")
        if secs is None and m.get("close_ts"):
            try:
                secs = max(0, float(m["close_ts"]) - now)
            except Exception:
                secs = None
        vol = m.get("kalshi_volume_24h") or m.get("volume") or 0
        try:
            vol_f = float(vol)
        except (TypeError, ValueError):
            vol_f = 0.0
        out.append(
            {
                "asset": a,
                "ticker": str(m.get("kalshi_ticker") or m.get("ticker") or ""),
                "yes": float(yes),
                "secs": float(secs) if secs is not None else None,
                "volume": vol_f,
            }
        )
    return out


def _windows(state_dir: Path) -> dict[str, Any]:
    p = state_dir / WINDOW_FILE
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_windows(w: dict[str, Any], *, state_dir: Path) -> None:
    try:
        (state_dir / WINDOW_FILE).write_text(
            json.dumps(w, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass


# r1709: automatic bleed control (make money / stop stacking red force-flats)
COOLDOWN_FILE = "alice_usd_cooldown.json"
FORCE_FLAT_RED_COOLDOWN_S = 15 * 60.0  # r1716: 15m cool (was 45 — blocked all dual)
FORCE_FLAT_RED_LOOKBACK_S = 60 * 60.0
FORCE_FLAT_RED_TRIGGER_N = 2  # r1716: need 2 material reds (was 1 — one red froze dual)
SECOND_BAG_MAX_ENTRY = 0.65  # r1721 multi-scalp: 2nd bag ok if first in band


def clear_force_flat_cooldown(
    state_dir: Path, *, reason: str = "owner_clear"
) -> dict[str, Any]:
    """Owner override — stop auto-rearming cool from old ledger reds for this session."""
    row = {
        "cool": False,
        "until_ts": 0,
        "n_red": 0,
        "reason": str(reason or "owner_clear")[:200],
        "owner_override": True,
        "ts": time.time(),
        "truth_label": TRUTH,
    }
    try:
        (state_dir / COOLDOWN_FILE).write_text(
            json.dumps(row, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass
    return row


def _force_flat_red_cooldown(state_dir: Path) -> dict[str, Any]:
    """True if recent force-flat reds require cool-down (no new entries)."""
    now = time.time()
    p = state_dir / COOLDOWN_FILE
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            # Owner clear sticks — do not re-arm from ledger until override expires
            if d.get("owner_override") is True and d.get("cool") is False:
                return {
                    "cool": False,
                    "owner_override": True,
                    "reason": d.get("reason") or "owner_clear",
                    "n_red": 0,
                }
            until = float(d.get("until_ts") or 0)
            if until > now:
                return {
                    "cool": True,
                    "until_ts": until,
                    "reason": d.get("reason") or "cooldown_active",
                    "n_red": d.get("n_red"),
                }
        except Exception:
            pass
    # count recent force-flat red TPs from live ledger
    ledger = state_dir / "kalshi_usd_live_ledger.jsonl"
    n_red = 0
    if ledger.exists():
        try:
            for line in ledger.read_text(encoding="utf-8").splitlines()[-200:]:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if str(r.get("event") or "") != "usd_take_profit":
                    continue
                if not r.get("filled"):
                    continue
                ts = float(r.get("ts") or 0)
                if ts < now - FORCE_FLAT_RED_LOOKBACK_S:
                    continue
                if not (r.get("force_flat_7m") or r.get("force_flat")):
                    continue
                try:
                    pnl = float(r.get("pnl_usd") or 0)
                except (TypeError, ValueError):
                    pnl = 0.0
                if pnl < -0.02:  # material red, not noise
                    n_red += 1
        except OSError:
            pass
    if n_red >= FORCE_FLAT_RED_TRIGGER_N:
        until = now + FORCE_FLAT_RED_COOLDOWN_S
        row = {
            "cool": True,
            "until_ts": until,
            "n_red": n_red,
            "reason": "force_flat_red_cluster",
            "ts": now,
            "truth_label": TRUTH,
        }
        try:
            p.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            pass
        return row
    return {"cool": False, "n_red": n_red}


def _second_bag_allowed(opens: list[dict[str, Any]], state_dir: Path) -> bool:
    """Allow 2nd concurrent only if first bag is green fee-true or was cheap entry."""
    if len(opens) != 1:
        return len(opens) == 0
    o = opens[0]
    try:
        entry = float(o.get("price") or o.get("side_price") or 0.5)
    except (TypeError, ValueError):
        entry = 0.5
    if entry <= SECOND_BAG_MAX_ENTRY + 1e-9:
        return True
    # fee-true green on live mark?
    try:
        from System.alice_usd_take_profit import evaluate_take_profit, _live_yes

        mark = _live_yes(str(o.get("ticker") or ""), str(o.get("asset") or ""), state_dir)
        if mark:
            ev = evaluate_take_profit(o, mark, min_edge=0.01)
            if ev.get("take_profit") or float(ev.get("net_usd") or 0) >= 0.01:
                return True
    except Exception:
        pass
    return False


def tick_must_scalp(
    *,
    state_dir: Optional[Path | str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """r1723: STGM-copy only — mirror paper opens; never freelance cash."""
    from System.kalshi_usd_hand import (
        is_hand_live,
        load_night,
        maybe_mirror_paper_bet,
    )
    from System.kalshi_usd_lane import is_usd_lane_armed
    from System.ledger_deal import MAX_OPEN, TARGET_CONCURRENT_OPEN
    from System.swarm_sifta_paper_loop import (
        DEFAULT_MIN_SECS,
        MAX_SCALPS_PER_WINDOW,
        load_open_book,
    )

    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)

    if not is_usd_lane_armed(root) or not is_hand_live(root):
        _write_sit("lane_or_hand_off", {}, state_dir=root)
        return {"ok": False, "reason": "lane_or_hand_off", "placed": False}

    marks = _load_marks(root)
    if not marks:
        _write_sit("no_live_marks", {}, state_dir=root)
        return {"ok": False, "reason": "no_live_marks", "placed": False}

    wid = _window_id(marks)
    done = _windows(root)
    win = dict(done.get(wid) or {})
    n_placed = int(win.get("n_placed") or (1 if win.get("placed") else 0))
    max_scalps = int(MAX_SCALPS_PER_WINDOW)
    target_open = int(TARGET_CONCURRENT_OPEN)
    max_open = int(MAX_OPEN)

    night = load_night(root)
    opens = list(night.get("open") or [])
    n_open = len(opens)

    cool = _force_flat_red_cooldown(root)
    if cool.get("cool") and n_open == 0:
        _write_sit(
            "cooldown_after_force_flat_reds",
            {
                "n_red": cool.get("n_red"),
                "until_ts": cool.get("until_ts"),
                "human": "Alice sits — recent force-flat reds; wait for cool-down",
            },
            state_dir=root,
        )
        return {
            "ok": True,
            "reason": "cooldown_after_force_flat_reds",
            "n_red": cool.get("n_red"),
            "placed": False,
        }

    if n_open >= target_open or n_open >= max_open:
        return {
            "ok": True,
            "reason": "concurrent_full_manage_only",
            "n_open": n_open,
            "target_open": target_open,
            "n_placed": n_placed,
            "placed": False,
        }

    secs_list = [m["secs"] for m in marks if m.get("secs") is not None]
    secs = min(secs_list) if secs_list else None
    min_secs = float(DEFAULT_MIN_SECS)
    if secs is None:
        _write_sit("no_clock", {}, state_dir=root)
        return {"ok": False, "reason": "no_clock", "placed": False}
    if secs < min_secs:
        # late — no new entries; keep history of any early scalps
        done[wid] = {
            **win,
            "sat_final": True,
            "reason": "late_window",
            "secs": secs,
            "n_placed": n_placed,
            "ts": time.time(),
        }
        _save_windows(done, state_dir=root)
        _write_sit(
            "late_window_no_new",
            {
                "secs_left": secs,
                "need": f">={min_secs}",
                "n_placed": n_placed,
                "doctrine": (
                    "open+TP+flat until 7:30 left; force flat ≤7:30 — rest is sit"
                ),
                "human": "DO NOT MANUAL GAMBLE after 7:30 left",
            },
            state_dir=root,
        )
        return {
            "ok": True,
            "reason": "late_window",
            "secs": secs,
            "n_placed": n_placed,
            "placed": False,
        }

    # ── r1723: EXACT STGM COPY ONLY — no freestyle field hunt ─────────────
    paper_opens = list(load_open_book(root).get("open") or [])
    if not paper_opens:
        _write_sit(
            "stgm_copy_only_no_paper",
            {
                "secs_left": secs,
                "n_usd_open": n_open,
                "human": (
                    "US$ SIT — STGM OPEN is empty. Cash will NOT freelance. "
                    "Wait for paper scalps, then copy exact asset/side."
                ),
                "deal": "r1723-stgm-copy-only",
            },
            state_dir=root,
        )
        _log(
            {
                "event": "stgm_copy_sit",
                "reason": "stgm_copy_only_no_paper",
                "window_id": wid,
                "secs_left": secs,
            },
            state_dir=root,
        )
        return {
            "ok": True,
            "placed": False,
            "reason": "stgm_copy_only_no_paper",
            "window_id": wid,
            "n_placed": n_placed,
            "truth_label": TRUTH,
            "deal": "r1723",
        }

    usd_tickers = {str(o.get("ticker") or "") for o in opens if o.get("ticker")}
    usd_assets = {str(o.get("asset") or "").upper() for o in opens if o.get("asset")}
    mirrored: list[dict[str, Any]] = []
    last_result: dict[str, Any] = {}

    for row in paper_opens:
        if n_open + len(mirrored) >= max_open or n_open + len(mirrored) >= target_open:
            break
        if n_placed + len(mirrored) >= max_scalps:
            break
        asset = str(row.get("asset") or "").upper()
        ticker = str(row.get("ticker") or "")
        if not asset or not ticker:
            continue
        if ticker in usd_tickers or asset in usd_assets:
            continue  # already on cash book
        lab = str(row.get("label") or row.get("side") or "").upper()
        if lab in ("UP", "YES"):
            side = "yes"
        elif lab in ("DOWN", "NO"):
            side = "no"
        else:
            side = str(row.get("side") or "yes").lower()
            if side not in ("yes", "no"):
                continue
        try:
            entry = float(row.get("price") or row.get("entry_price") or 0.5)
        except (TypeError, ValueError):
            entry = 0.5
        bet = {
            "ticker": ticker,
            "asset": asset,
            "side": side,
            "entry_price": entry,
            "price": entry,
            "label": lab or ("UP" if side == "yes" else "DOWN"),
            "volume": float(row.get("volume") or 5000),
            "rainman": {
                "action": "fire",
                "score": 0.65,
                "bucket": "stgm_exact_copy",
            },
            "stgm_exact_copy": True,
            "window_id": wid,
            "paper_wager_id": row.get("wager_id") or row.get("body_stgm", {}).get("wager_id"),
        }
        decision_ts_ms = int(time.time() * 1000)
        placed = maybe_mirror_paper_bet(bet, state_dir=root, dry_run=dry_run)
        last_result = placed if isinstance(placed, dict) else {}
        filled = bool(last_result.get("filled")) or (
            last_result.get("event") == "usd_place"
            and float(last_result.get("fill_count") or 0) > 0
        )
        _log(
            {
                "event": "stgm_exact_copy_attempt",
                "window_id": wid,
                "asset": asset,
                "side": side,
                "entry": entry,
                "filled": filled,
                "result": last_result.get("event"),
                "reason": last_result.get("reason"),
                "deal": "r1723",
            },
            state_dir=root,
        )
        if not filled:
            continue
        mirrored.append(
            {
                "asset": asset,
                "side": side,
                "entry": entry,
                "order": last_result.get("order_id"),
            }
        )
        usd_tickers.add(ticker)
        usd_assets.add(asset)
        n_placed += 1
        hist = list(win.get("history") or [])
        hist.append(
            {
                "asset": asset,
                "side": side,
                "entry": entry,
                "ts": time.time(),
                "order": last_result.get("order_id"),
                "scalp_n": n_placed,
                "copy": "stgm_exact",
            }
        )
        win = {
            **win,
            "placed": True,
            "n_placed": n_placed,
            "max_scalps": max_scalps,
            "asset": asset,
            "side": side,
            "entry": entry,
            "ts": time.time(),
            "order": last_result.get("order_id"),
            "history": hist[-max_scalps:],
            "deal": "r1723-stgm-copy-only",
        }
        done[wid] = win
        _save_windows(done, state_dir=root)

    if mirrored:
        try:
            (root / SIT_FILE).unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass
        return {
            "ok": True,
            "placed": True,
            "window_id": wid,
            "n_placed": n_placed,
            "mirrored": mirrored,
            "n_mirrored": len(mirrored),
            "deal": "r1723-stgm-copy-only",
            "truth_label": TRUTH,
            "result": last_result,
        }

    _write_sit(
        "stgm_copy_no_fill",
        {
            "paper_n": len(paper_opens),
            "secs_left": secs,
            "last": {
                "event": last_result.get("event"),
                "reason": last_result.get("reason"),
            },
            "human": (
                "STGM has opens but US$ copy did not fill this tick "
                "(band/clock/caps) — wait next tick, do not manual"
            ),
            "deal": "r1723-stgm-copy-only",
        },
        state_dir=root,
    )
    return {
        "ok": True,
        "placed": False,
        "reason": "stgm_copy_no_fill",
        "window_id": wid,
        "paper_n": len(paper_opens),
        "n_placed": n_placed,
        "result": last_result,
        "truth_label": TRUTH,
        "deal": "r1723",
    }


__all__ = [
    "tick_must_scalp",
    "TRUTH",
    "SIT_FILE",
    "clear_force_flat_cooldown",
    "_force_flat_red_cooldown",
]
