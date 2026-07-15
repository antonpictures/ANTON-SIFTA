#!/usr/bin/env python3
"""r1698/r1700 — Alice MUST attempt dual scalps early (owner: no human gamble).

If paper→USD mirror misses or paper sits rich, this organ still tries fee-true
scalpable US$ tickets from live marks when:
  • lane + hand LIVE
  • secs left ≥ **8:00** (DEFAULT_MIN_SECS) — first ~7m of the 15m window
  • field side premium in 40–65¢ (prefer ≤58¢)
  • liquid major (not weird/dust)
  • flat (no open bags) — re-enter after TP until MAX_SCALPS_PER_WINDOW (3)
  • not already at max open / same-dir

r1700: **more scalps/session** — after a green cash-out, if still ≥8:00 left and
n_placed < 3, hunt again. Prefer all closed by 7:00 left (TP force_flat organ).

Last 7–8 minutes: no new risk. TP force-flats ≤7:00 left.

When no legal ticket exists, writes `alice_usd_sit_reason.json` so glass/owner
see **why** she sat — human must NOT fill the silence with gambling.

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
MAJORS = ("BTC", "ETH", "SOL", "XRP", "BNB")
WEIRD = frozenset({"HYPE", "ZEC", "NEAR", "DOGE"})


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
FORCE_FLAT_RED_COOLDOWN_S = 45 * 60.0  # sit ~45m after force-flat red cluster
FORCE_FLAT_RED_LOOKBACK_S = 60 * 60.0
FORCE_FLAT_RED_TRIGGER_N = 1  # even one material force-flat red → cool (stop the bleed)
SECOND_BAG_MAX_ENTRY = 0.52  # 2nd bag only if first was cheap or green


def _force_flat_red_cooldown(state_dir: Path) -> dict[str, Any]:
    """True if recent force-flat reds require cool-down (no new entries)."""
    now = time.time()
    p = state_dir / COOLDOWN_FILE
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
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
    """Auto dual scalps while early; up to TARGET_CONCURRENT open (2) · $2 AMMO each."""
    from System.kalshi_usd_hand import (
        is_hand_live,
        load_night,
        maybe_mirror_paper_bet,
    )
    from System.kalshi_usd_lane import is_usd_lane_armed
    from System.ledger_deal import MAX_OPEN, MAX_SAME_DIR, TARGET_CONCURRENT_OPEN
    from System.swarm_sifta_paper_loop import (
        DEFAULT_MIN_SECS,
        MAX_SCALPS_PER_WINDOW,
        MUST_FIRE_MAX_ENTRY,
        MUST_FIRE_MIN_ENTRY,
        RICH_ENTRY_PRICE,
        RICH_MIN_RAINMAN,
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

    if win.get("sat_final"):
        return {
            "ok": True,
            "reason": "window_already_handled",
            "window_id": wid,
            "n_placed": n_placed,
            "placed": n_placed > 0,
        }
    if n_placed >= max_scalps:
        return {
            "ok": True,
            "reason": "max_scalps_per_window",
            "window_id": wid,
            "n_placed": n_placed,
            "max_scalps": max_scalps,
            "placed": False,
        }

    night = load_night(root)
    opens = list(night.get("open") or [])
    n_open = len(opens)

    # r1709: cool-down after stacked force-flat reds (stop bleeding sessions)
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
        # full concurrent book — manage only (TP / force-flat)
        return {
            "ok": True,
            "reason": "concurrent_full_manage_only",
            "n_open": n_open,
            "target_open": target_open,
            "n_placed": n_placed,
            "placed": False,
        }

    # r1709: second bag only if first is fee-true green or entry was cheap
    if n_open == 1 and not _second_bag_allowed(opens, root):
        return {
            "ok": True,
            "reason": "second_bag_blocked_quality",
            "n_open": 1,
            "detail": "need first bag green fee-true or entry≤55¢",
            "placed": False,
        }

    open_assets = {
        str(o.get("asset") or "").upper()
        for o in opens
        if o.get("asset")
    }
    open_tickers = {str(o.get("ticker") or "") for o in opens if o.get("ticker")}
    same_dir_yes = sum(
        1 for o in opens if str(o.get("side") or "").lower() == "yes"
    )
    same_dir_no = sum(1 for o in opens if str(o.get("side") or "").lower() == "no")

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

    # field + co-dir (r1704: never fight open bags or STGM window side)
    try:
        from System.alice_15m_co_direction import board_field

        field = board_field(state_dir=root)
        anchor = str(field.get("anchor_side") or "")
        ranked = [
            str(r.get("asset") or "").upper()
            for r in (field.get("ranked") or [])
            if not r.get("contrarian")
        ]
    except Exception:
        anchor = ""
        ranked = list(MAJORS)
        field = {}

    if anchor not in ("yes", "no"):
        btc = next((m for m in marks if m["asset"] == "BTC"), None)
        if btc:
            anchor = "yes" if btc["yes"] >= 0.5 else "no"
        else:
            anchor = "yes"
    # lock to existing USD open side (two bags same way)
    if same_dir_yes or same_dir_no:
        anchor = "yes" if same_dir_yes >= same_dir_no else "no"
    # prefer STGM paper open assets (dual alignment) when still early + in band
    paper_pref: list[str] = []
    try:
        from System.swarm_sifta_paper_loop import load_open_book

        for row in load_open_book(root).get("open") or []:
            lab = str(row.get("label") or row.get("side") or "").upper()
            ps = "yes" if lab in ("UP", "YES") else ("no" if lab in ("DOWN", "NO") else "")
            if ps and ps != anchor:
                continue  # ignore STGM contrarian to our lock
            a = str(row.get("asset") or "").upper()
            if a and a not in paper_pref:
                paper_pref.append(a)
    except Exception:
        pass

    lo, hi = float(MUST_FIRE_MIN_ENTRY), float(MUST_FIRE_MAX_ENTRY)
    rich_px, rich_sc = float(RICH_ENTRY_PRICE), float(RICH_MIN_RAINMAN)
    # need room before force-flat so dual isn't in-and-out for fees only
    entry_buffer = 90.0
    if secs < float(min_secs) + entry_buffer:
        _write_sit(
            "too_close_to_flat_gate",
            {
                "secs_left": secs,
                "need": f">={min_secs + entry_buffer}",
                "human": "no new US$ this close to force-flat",
            },
            state_dir=root,
        )
        return {
            "ok": True,
            "reason": "too_close_to_flat_gate",
            "secs": secs,
            "placed": False,
        }

    # r1713 P0 parity: same regime_gate as STGM (strategies) — no fork
    try:
        from System.alice_15m_scalp_strategies import (
            regime_gate,
            regime_preferred_side,
            REGIME_GATE_IMPLIED_THRESH,
        )
    except Exception:
        regime_gate = None  # type: ignore
        regime_preferred_side = None  # type: ignore
        REGIME_GATE_IMPLIED_THRESH = 0.70

    field_rg = {
        "anchor_side": anchor,
        "majors_breadth": (field or {}).get("breadth")
        or (field or {}).get("majors_breadth"),
    }

    candidates: list[dict[str, Any]] = []
    regime_rejects = 0
    for m in marks:
        a = m["asset"]
        if a in WEIRD or a not in MAJORS:
            continue
        if a in open_assets or str(m.get("ticker") or "") in open_tickers:
            continue  # already bagged this name — diversify second ticket
        if m["volume"] < 500:
            continue
        yes = m["yes"]
        side = anchor
        entry = yes if side == "yes" else (1.0 - yes)
        # r1713: block fade vs strong drift (import THE SAME gate as paper)
        if regime_gate is not None:
            rg = regime_gate(side=side, yes_mid=yes, field=field_rg)
            if rg:
                pref = (
                    regime_preferred_side(yes, field=field_rg)
                    if regime_preferred_side
                    else None
                )
                if pref and pref != side:
                    alt = yes if pref == "yes" else (1.0 - yes)
                    if lo - 1e-9 <= float(alt) <= hi + 1e-9:
                        side = pref
                        entry = float(alt)
                    else:
                        regime_rejects += 1
                        continue
                else:
                    regime_rejects += 1
                    continue
        if entry < lo - 1e-9 or entry > hi + 1e-9:
            continue
        if side == "yes" and same_dir_yes >= int(MAX_SAME_DIR):
            continue
        if side == "no" and same_dir_no >= int(MAX_SAME_DIR):
            continue
        rank = ranked.index(a) if a in ranked else 99
        # prefer paper-open names for dual stigmergy
        pref_boost = 2.0 if a in paper_pref else 0.0
        score = (hi - entry) * 3.0 - rank * 0.1 + min(1.0, m["volume"] / 50_000) + pref_boost
        candidates.append(
            {
                **m,
                "side": side,
                "entry": entry,
                "pick_score": score,
                "rank": rank,
            }
        )

    if not candidates:
        # all field winners too rich or regime-blocked — SIT and tell human
        sample = []
        for m in marks:
            if m["asset"] not in MAJORS:
                continue
            e = m["yes"] if anchor == "yes" else (1.0 - m["yes"])
            sample.append({"asset": m["asset"], "field_side_px": round(e, 3)})
        reason = (
            "regime_gate_blocked_all"
            if regime_rejects > 0 and not sample
            else (
                "regime_or_band_empty"
                if regime_rejects > 0
                else "field_side_too_rich"
            )
        )
        done[wid] = {
            "sat_rich": reason == "field_side_too_rich",
            "reason": reason,
            "anchor": anchor,
            "regime_rejects": regime_rejects,
            "ts": time.time(),
        }
        # don't mark sat_final until late — prices can dip mid-window
        _save_windows(done, state_dir=root)
        _write_sit(
            reason,
            {
                "anchor": anchor,
                "band": [lo, hi],
                "majors": sample[:8],
                "secs_left": secs,
                "regime_rejects": regime_rejects,
                "regime_thresh": float(REGIME_GATE_IMPLIED_THRESH),
                "human": (
                    "DO NOT MANUAL GAMBLE — regime gate or band blocked; sit is valid"
                ),
            },
            state_dir=root,
        )
        return {
            "ok": True,
            "reason": reason,
            "anchor": anchor,
            "regime_rejects": regime_rejects,
            "placed": False,
            "sit_file": SIT_FILE,
        }

    candidates.sort(key=lambda x: -float(x["pick_score"]))
    pick = candidates[0]

    # rainman floor for rich picks
    rm_score = 0.63 if pick["entry"] > rich_px else 0.58
    if pick["entry"] > rich_px and rm_score < rich_sc:
        rm_score = rich_sc

    bet = {
        "ticker": pick["ticker"],
        "asset": pick["asset"],
        "side": pick["side"],
        "entry_price": pick["entry"],
        "price": pick["entry"],
        "kalshi_yes": pick["yes"],
        "volume": max(pick["volume"], 5000),
        "rainman": {
            "action": "fire",
            "score": rm_score,
            "bucket": "must_scalp",
        },
        "must_scalp": True,
        "window_id": wid,
    }

    # r1713 dual-lag harness: stamp decision-time book before submit
    try:
        from System.alice_usd_dual_lag_harness import stamp_decision

        stamp_decision(
            phase="must_scalp_candidate",
            bet=bet,
            mark=pick,
            secs_left=secs,
            dry_run=dry_run,
            state_dir=root,
        )
    except Exception:
        pass

    decision_ts_ms = int(time.time() * 1000)
    placed = maybe_mirror_paper_bet(bet, state_dir=root, dry_run=dry_run)
    try:
        from System.alice_usd_dual_lag_harness import stamp_submit_result

        stamp_submit_result(
            phase="must_scalp_submit",
            bet=bet,
            result=placed,
            decision_ts_ms=decision_ts_ms,
            dry_run=dry_run,
            state_dir=root,
        )
    except Exception:
        pass
    filled = bool(placed.get("filled")) or (
        placed.get("event") == "usd_place" and float(placed.get("fill_count") or 0) > 0
    )

    if filled:
        new_n = n_placed + 1
        hist = list(win.get("history") or [])
        hist.append(
            {
                "asset": pick["asset"],
                "side": pick["side"],
                "entry": pick["entry"],
                "ts": time.time(),
                "order": placed.get("order_id"),
                "scalp_n": new_n,
            }
        )
        done[wid] = {
            **win,
            "placed": True,
            "n_placed": new_n,
            "max_scalps": max_scalps,
            "asset": pick["asset"],
            "side": pick["side"],
            "entry": pick["entry"],
            "ts": time.time(),
            "order": placed.get("order_id"),
            "history": hist[-max_scalps:],
        }
        _save_windows(done, state_dir=root)
        # clear sit file
        try:
            (root / SIT_FILE).unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            try:
                if (root / SIT_FILE).exists():
                    (root / SIT_FILE).unlink()
            except Exception:
                pass
        _log(
            {
                "event": "must_scalp_placed",
                "window_id": wid,
                "asset": pick["asset"],
                "side": pick["side"],
                "entry": pick["entry"],
                "fill_count": placed.get("fill_count"),
                "n_placed": new_n,
                "max_scalps": max_scalps,
            },
            state_dir=root,
        )
        return {
            "ok": True,
            "placed": True,
            "window_id": wid,
            "asset": pick["asset"],
            "side": pick["side"],
            "entry": pick["entry"],
            "n_placed": new_n,
            "max_scalps": max_scalps,
            "result": placed,
            "truth_label": TRUTH,
        }

    # no fill this tick — keep trying later in window (does not burn a scalp slot)
    _log(
        {
            "event": "must_scalp_attempt",
            "window_id": wid,
            "asset": pick["asset"],
            "entry": pick["entry"],
            "result": placed.get("event"),
            "reason": placed.get("reason"),
            "n_placed": n_placed,
        },
        state_dir=root,
    )
    _write_sit(
        "attempted_no_fill_or_reject",
        {
            "asset": pick["asset"],
            "entry": pick["entry"],
            "event": placed.get("event"),
            "reason": placed.get("reason"),
            "secs_left": secs,
            "n_placed": n_placed,
            "max_scalps": max_scalps,
            "human": "Alice tried — wait for next tick, do not spam manual",
        },
        state_dir=root,
    )
    return {
        "ok": True,
        "placed": False,
        "window_id": wid,
        "attempt": pick["asset"],
        "n_placed": n_placed,
        "result": placed,
        "truth_label": TRUTH,
    }


__all__ = ["tick_must_scalp", "TRUTH", "SIT_FILE"]
