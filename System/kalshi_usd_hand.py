#!/usr/bin/env python3
"""Alice's real-USD hand — r1644 caps · owner-armed only (r1647).

Parallel to STGM/paper forever. Never pauses body STGM.
Places at most 1 Kalshi contract per accepted ticket when:
  • US $ lane armed  AND  hand session live
  • kill switch OFF
  • ticket passes FIRE-only 80–88¢ + open/dir/budget/loss floors

Ledger: .sifta_state/kalshi_usd_live_ledger.jsonl (separate from paper forever).
"""

from __future__ import annotations

import fcntl
import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
NIGHT_FILE = "kalshi_usd_night.json"
LEDGER = "kalshi_usd_live_ledger.jsonl"
SESSION_FILE = "kalshi_usd_hand_session.json"
TRUTH = "KALSHI_USD_HAND_V1"

# r1644 / r1648 ledger deal — single source of truth
try:
    from System.ledger_deal import (
        FIRE_ONLY_USD as FIRE_ONLY,
        MAX_BUDGET_USD as MAX_BUDGET,
        MAX_NIGHT_LOSS_USD as MAX_NIGHT_LOSS,
        MAX_OPEN,
        MAX_SAME_DIR,
        MIN_VOLUME,
        STAKE_USD,
        USD_MAX_ENTRY as MAX_ENTRY,
        USD_MIN_ENTRY as MIN_ENTRY,
        contracts_for_ammo,
        get_ammo_usd,
        live_contract_pnl,
        log_ev_row,
        paper_unit_pnl,
    )
except Exception:
    MIN_ENTRY = 0.40
    MAX_ENTRY = 0.65
    MAX_OPEN = 3
    MAX_SAME_DIR = 2
    MAX_NIGHT_LOSS = 5.0
    MAX_BUDGET = 12.0
    STAKE_USD = 2.0
    MIN_VOLUME = 0.0
    FIRE_ONLY = False

    def get_ammo_usd(*, state_dir=None) -> float:  # type: ignore
        return float(STAKE_USD)

    def contracts_for_ammo(*, ammo_usd=None, state_dir=None) -> int:  # type: ignore
        a = float(ammo_usd) if ammo_usd is not None else float(STAKE_USD)
        return max(1, min(5, int(round(a))))

    def live_contract_pnl(win: bool, price: float) -> float:  # type: ignore
        p = max(0.01, min(0.99, float(price)))
        return round(1.0 - p, 4) if win else round(-p, 4)

    def paper_unit_pnl(win: bool, price: float) -> float:  # type: ignore
        p = max(0.01, min(0.99, float(price)))
        return round(1.0 / p - 1.0, 4) if win else -1.0

    def log_ev_row(row: dict, *, state_dir=None) -> None:  # type: ignore
        return None


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


@contextmanager
def _order_lock(*, state_dir: Optional[Path | str] = None):
    """Serialize cap-check → order → local-book across processes."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / "kalshi_usd_order.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _log(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("truth_label", TRUTH)
    try:
        with (root / LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def load_night(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _state(state_dir) / NIGHT_FILE
    day = time.strftime("%Y-%m-%d")
    default = {
        "day": day,
        "realized_pnl_usd": 0.0,
        "open": [],
        "n_placed": 0,
        "n_skipped": 0,
        "n_settled": 0,
        "halted": False,
        "halt_reason": "",
        "truth_label": TRUTH,
    }
    if not p.exists():
        return default
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("night state is not an object")
        # roll calendar day
        if raw.get("day") != day:
            # A 15-minute position may cross local midnight. Carry verified
            # exposure forward even while realized PnL starts a fresh day.
            default["open"] = list(raw.get("open") or [])
            default["carried_from_day"] = raw.get("day")
            return default
        raw.setdefault("open", [])
        raw.setdefault("realized_pnl_usd", 0.0)
        return raw
    except Exception:
        default["halted"] = True
        default["halt_reason"] = "night_state_corrupt"
        return default


def save_night(night: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    night = dict(night)
    night["ts"] = time.time()
    night["truth_label"] = TRUTH
    path = root / NIGHT_FILE
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(night, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def load_session(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _state(state_dir) / SESSION_FILE
    if not p.exists():
        return {"live": False, "truth_label": TRUTH}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {"live": False}
    except Exception:
        return {"live": False}


def set_hand_live(
    live: bool,
    *,
    reason: str = "",
    owner_phrase: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Start/stop the USD hand session (still needs lane armed + no kill)."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "live": bool(live),
        "ts": time.time(),
        "reason": str(reason or "")[:240],
        "owner_phrase": str(owner_phrase or "")[:240],
        "caps": {
            "band": [MIN_ENTRY, MAX_ENTRY],
            "max_open": MAX_OPEN,
            "max_same_dir": MAX_SAME_DIR,
            "stake_usd": get_ammo_usd(state_dir=root),
            "ammo_usd": get_ammo_usd(state_dir=root),
            "contracts": contracts_for_ammo(state_dir=root),
            "max_night_loss": MAX_NIGHT_LOSS,
            "max_budget": MAX_BUDGET,
            "fire_only": FIRE_ONLY,
            "min_volume": MIN_VOLUME,
        },
        "truth_label": TRUTH,
        "note": (
            "USD hand LIVE — real orders under r1644 caps when lane armed"
            if live
            else "USD hand IDLE — no orders"
        ),
    }
    (root / SESSION_FILE).write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    _log({"event": "hand_session", **row}, state_dir=state_dir)
    return row


def is_hand_live(state_dir: Optional[Path | str] = None) -> bool:
    return load_session(state_dir).get("live") is True


def status_line(state_dir: Optional[Path | str] = None) -> str:
    from System.kalshi_usd_lane import is_usd_lane_armed
    from System.kalshi_prod_trade_client import kill_switch_active

    if kill_switch_active(state_dir=_state(state_dir)):
        return "US $ HAND HALT"
    if is_usd_lane_armed(state_dir) and is_hand_live(state_dir):
        n = load_night(state_dir)
        return f"US $ HAND LIVE · open {len(n.get('open') or [])}/{MAX_OPEN}"
    if is_usd_lane_armed(state_dir):
        return "US $ LANE ON · hand idle"
    return "US $ HAND OFF"


def _dir_counts(open_rows: list[dict[str, Any]]) -> dict[str, int]:
    c = {"yes": 0, "no": 0}
    for r in open_rows:
        s = str(r.get("side") or "").lower()
        if s in c:
            c[s] += 1
    return c


def evaluate_ticket(
    *,
    entry_price: float,
    side: str,
    rainman_action: str = "",
    rainman_score: Optional[float] = None,
    volume: Optional[float] = None,
    ticker: str = "",
    asset: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Pure gate — no network. Returns {ok, reason, ...}."""
    from System.kalshi_usd_lane import is_usd_lane_armed
    from System.kalshi_prod_trade_client import kill_switch_active

    # r1667: fee-net shadow epoch — hard refuse USD (policy + config)
    try:
        from System.alice_fee_net_tournament import load_config, policy_allows_trade

        cfg = load_config(state_dir=state_dir)
        if cfg.get("epoch_active") and cfg.get("usd_shadow_only", True):
            return {"ok": False, "reason": "r1667_usd_shadow_only"}
        ok_p, why_p = policy_allows_trade(state_dir=state_dir)
        if not ok_p:
            return {"ok": False, "reason": "policy_hash_block", "detail": why_p}
    except Exception:
        pass

    if not is_usd_lane_armed(state_dir):
        return {"ok": False, "reason": "lane_off"}
    if not is_hand_live(state_dir):
        return {"ok": False, "reason": "hand_idle"}
    if kill_switch_active(state_dir=_state(state_dir)):
        return {"ok": False, "reason": "kill_switch"}

    night = load_night(state_dir)
    if night.get("halted"):
        return {"ok": False, "reason": "night_halted", "detail": night.get("halt_reason")}

    p = float(entry_price)
    # r1677: match paper must-fire band so dual does not skip whole windows
    band_lo, band_hi = float(MIN_ENTRY), float(MAX_ENTRY)
    try:
        from System.swarm_sifta_paper_loop import (
            MUST_FIRE_EVERY_WINDOW,
            MUST_FIRE_MIN_ENTRY,
            MUST_FIRE_MAX_ENTRY,
        )

        if MUST_FIRE_EVERY_WINDOW:
            band_lo, band_hi = float(MUST_FIRE_MIN_ENTRY), float(MUST_FIRE_MAX_ENTRY)
    except Exception:
        pass
    if p < band_lo - 1e-9 or p > band_hi + 1e-9:
        return {
            "ok": False,
            "reason": "band",
            "need": f"{band_lo}-{band_hi}",
            "price": p,
        }

    # r1696: rich + weak rainman veto (ETH NO @65¢ / score 0.577 stuck bag)
    try:
        from System.swarm_sifta_paper_loop import RICH_ENTRY_PRICE, RICH_MIN_RAINMAN

        _rich_px = float(RICH_ENTRY_PRICE)
        _rich_sc = float(RICH_MIN_RAINMAN)
    except Exception:
        _rich_px, _rich_sc = 0.58, 0.62
    try:
        _score = float(rainman_score) if rainman_score is not None else None
    except (TypeError, ValueError):
        _score = None
    if (
        _score is not None
        and p > _rich_px + 1e-9
        and _score < _rich_sc - 1e-9
    ):
        return {
            "ok": False,
            "reason": "rich_weak_rainman",
            "price": p,
            "rainman_score": _score,
            "need": f"entry<={_rich_px} or score>={_rich_sc}",
        }

    action = str(rainman_action or "fire").lower()
    # r1649 dual every paper: only SIT skips; FIRE+THIN place
    # r1677 must-fire: never sit the only ticket of the window on rainman
    # r1696: do NOT force-fire rich weak tickets
    if action in ("sit", "sit_out"):
        try:
            from System.swarm_sifta_paper_loop import MUST_FIRE_EVERY_WINDOW

            if MUST_FIRE_EVERY_WINDOW and p <= _rich_px + 1e-9:
                action = "fire"
            elif MUST_FIRE_EVERY_WINDOW and p > _rich_px:
                return {
                    "ok": False,
                    "reason": "rich_no_must_fire_override",
                    "price": p,
                    "need": f"entry<={_rich_px} for must-fire override",
                }
            else:
                return {"ok": False, "reason": "rainman_sit", "action": action}
        except Exception:
            return {"ok": False, "reason": "rainman_sit", "action": action}
    if FIRE_ONLY and action not in ("fire", "thin", ""):
        return {"ok": False, "reason": "not_fire", "action": action}

    if MIN_VOLUME > 0:
        if volume is None:
            return {"ok": False, "reason": "volume_unknown"}
        if float(volume) < MIN_VOLUME:
            return {"ok": False, "reason": "dust", "volume": volume}

    opens = list(night.get("open") or [])
    if len(opens) >= MAX_OPEN:
        return {"ok": False, "reason": "max_open", "n": len(opens)}

    side_l = str(side or "").lower()
    if side_l not in ("yes", "no"):
        return {"ok": False, "reason": "bad_side"}
    dirs = _dir_counts(opens)
    if dirs.get(side_l, 0) >= MAX_SAME_DIR:
        return {"ok": False, "reason": "max_same_dir", "side": side_l, "n": dirs[side_l]}

    # already open on ticker
    t = str(ticker or "")
    if t and any(str(o.get("ticker") or "") == t for o in opens):
        return {"ok": False, "reason": "already_open", "ticker": t}

    realized = float(night.get("realized_pnl_usd") or 0.0)
    if realized <= -MAX_NIGHT_LOSS:
        night["halted"] = True
        night["halt_reason"] = f"night_loss {realized}"
        save_night(night, state_dir=state_dir)
        return {"ok": False, "reason": "night_loss_stop", "pnl": realized}

    n_contracts = contracts_for_ammo(state_dir=state_dir)
    cost = round(p * n_contracts, 4)
    exposure = sum(float(o.get("cost_usd") or 0.0) for o in opens) + cost
    if exposure > MAX_BUDGET + 1e-9:
        return {"ok": False, "reason": "budget", "exposure": exposure}
    worst_case_after = round(realized - exposure, 4)
    if worst_case_after <= -MAX_NIGHT_LOSS:
        return {
            "ok": False,
            "reason": "night_loss_worst_case",
            "realized_pnl_usd": realized,
            "open_plus_new_exposure_usd": round(exposure, 4),
            "worst_case_after_usd": worst_case_after,
        }

    return {
        "ok": True,
        "reason": "pass",
        "price": p,
        "side": side_l,
        "cost_usd": cost,
        "count": n_contracts,
        "ammo_usd": get_ammo_usd(state_dir=state_dir),
        "asset": asset,
        "ticker": t,
    }


def _secs_left_for_usd(state_dir: Optional[Path | str] = None) -> Optional[float]:
    """Min seconds-to-close on live 15m board (US$ clock)."""
    root = _state(state_dir)
    path = root / "kalshi_15m_live.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        now = time.time()
        best: Optional[float] = None
        for m in data.get("markets") or []:
            if not isinstance(m, dict):
                continue
            secs = m.get("seconds_to_close")
            if secs is None and m.get("close_ts"):
                try:
                    secs = max(0.0, float(m["close_ts"]) - now)
                except Exception:
                    continue
            if secs is None:
                continue
            try:
                sf = float(secs)
            except (TypeError, ValueError):
                continue
            if best is None or sf < best:
                best = sf
        return best
    except Exception:
        return None


def _maybe_mirror_paper_bet_locked(
    bet: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """After a successful paper bet — optionally place parallel USD order.

    Never raises into paper path. Never pauses STGM.
    r1704: never dual into force-flat zone (STGM may still learn late).
    """
    try:
        rainman = bet.get("rainman") or {}
        action = str(rainman.get("action") or "")
        rainman_score = rainman.get("score")
        rainman_bucket = rainman.get("bucket")
        # entry price for the side bought
        side = str(bet.get("side") or "").lower()
        ky = float(bet.get("kalshi_yes") or 0.5)
        if side == "yes":
            entry_p = ky
        else:
            entry_p = 1.0 - ky
        # prefer explicit entry if present
        if bet.get("entry_price") is not None:
            try:
                entry_p = float(bet["entry_price"])
            except (TypeError, ValueError):
                pass

        # r1704: US$ hunt clock — STGM can place late; dual must not
        try:
            from System.swarm_sifta_paper_loop import DEFAULT_MIN_SECS, FORCE_FLAT_SECS

            usd_min = float(DEFAULT_MIN_SECS)
            flat_gate = float(FORCE_FLAT_SECS)
        except Exception:
            usd_min, flat_gate = 7 * 60.0 + 30.0, 7 * 60.0 + 30.0
        secs_left = _secs_left_for_usd(state_dir)
        if secs_left is not None and (
            secs_left < usd_min - 1e-9 or secs_left <= flat_gate + 1e-9
        ):
            row = {
                "event": "usd_skip",
                "ok": False,
                "reason": "usd_late_no_dual",
                "asset": bet.get("asset"),
                "ticker": bet.get("ticker"),
                "side": side,
                "secs_left": secs_left,
                "need": f">={usd_min}s and >{flat_gate}s force_flat",
                "note": "STGM may learn late; US$ dual only until 7:30 left",
            }
            _log(row, state_dir=state_dir)
            return row

        # r1709: cool-down after force-flat red cluster — dual sits too
        try:
            from System.alice_usd_must_scalp import _force_flat_red_cooldown

            cool = _force_flat_red_cooldown(_state(state_dir))
            if cool.get("cool"):
                row = {
                    "event": "usd_skip",
                    "ok": False,
                    "reason": "cooldown_after_force_flat_reds",
                    "asset": bet.get("asset"),
                    "n_red": cool.get("n_red"),
                    "until_ts": cool.get("until_ts"),
                }
                _log(row, state_dir=state_dir)
                return row
        except Exception:
            pass

        # r1704: same-dir lock vs existing USD opens
        night0 = load_night(state_dir)
        opens0 = list(night0.get("open") or [])
        if opens0:
            n_yes = sum(1 for o in opens0 if str(o.get("side") or "").lower() == "yes")
            n_no = sum(1 for o in opens0 if str(o.get("side") or "").lower() == "no")
            lock = "yes" if n_yes >= n_no else "no"
            if side in ("yes", "no") and side != lock:
                row = {
                    "event": "usd_skip",
                    "ok": False,
                    "reason": "usd_window_side_lock",
                    "asset": bet.get("asset"),
                    "side": side,
                    "lock": lock,
                    "note": "no opposite-side dual while bags open",
                }
                _log(row, state_dir=state_dir)
                return row

        vol = bet.get("volume")
        if vol is None:
            vol = bet.get("kalshi_volume")
        try:
            vol_f = float(vol) if vol is not None else None
        except (TypeError, ValueError):
            vol_f = None

        try:
            score_f = float(rainman_score)
        except (TypeError, ValueError):
            score_f = None
        if score_f is None:
            gate = {"ok": False, "reason": "rainman_score_unknown"}
        else:
            gate = evaluate_ticket(
                entry_price=entry_p,
                side=side,
                rainman_action=action,
                rainman_score=score_f,
                volume=vol_f,
                ticker=str(bet.get("ticker") or ""),
                asset=str(bet.get("asset") or ""),
                state_dir=state_dir,
            )
        if not gate.get("ok"):
            night = load_night(state_dir)
            night["n_skipped"] = int(night.get("n_skipped") or 0) + 1
            save_night(night, state_dir=state_dir)
            row = {
                "event": "usd_skip",
                "ok": False,
                "reason": gate.get("reason"),
                "asset": bet.get("asset"),
                "ticker": bet.get("ticker"),
                "side": side,
                "price": entry_p,
                "rainman_action": action,
                "rainman_score": rainman_score,
                "rainman_bucket": rainman_bucket,
                "gate": gate,
            }
            _log(row, state_dir=state_dir)
            return row

        from System.kalshi_prod_trade_client import (
            CapRejected,
            KalshiProdTradeClient,
            KillSwitchActive,
            NotProvisioned,
        )

        night = load_night(state_dir)
        client = KalshiProdTradeClient(
            state_dir=_state(state_dir),
            night_loss_usd=float(night.get("realized_pnl_usd") or 0.0),
            open_count=len(night.get("open") or []),
            open_exposure_usd=sum(
                float(o.get("cost_usd") or 0.0) for o in (night.get("open") or [])
            ),
        )
        # Owner take-next flag: aggressive fill on next paper tickets
        take_next = False
        take_path = _state(state_dir) / "kalshi_usd_take_next.json"
        try:
            if take_path.exists():
                tn = json.loads(take_path.read_text(encoding="utf-8"))
                take_next = bool(tn.get("armed"))
        except Exception:
            take_next = False

        # Live book price so dual FILLS (stale entry → usd_no_fill when mid runs)
        place_price = float(gate["price"])
        ticker = str(bet.get("ticker") or "")
        # r1686: scalp buy-low band (never rebid past this)
        lo, hi = float(MIN_ENTRY), float(MAX_ENTRY)
        try:
            from System.swarm_sifta_paper_loop import (
                MUST_FIRE_EVERY_WINDOW,
                MUST_FIRE_MIN_ENTRY,
                MUST_FIRE_MAX_ENTRY,
            )

            if MUST_FIRE_EVERY_WINDOW:
                lo, hi = float(MUST_FIRE_MIN_ENTRY), float(MUST_FIRE_MAX_ENTRY)
        except Exception:
            pass
        # take_next may nudge +2¢ for fill — still hard-cap at scalp max (no 90¢ chase)
        if take_next:
            # never widen past scalp ceiling (65¢)
            hi = min(float(hi), 0.65)

        try:
            mkt = client._request("GET", f"/markets/{ticker}")
            mk = mkt.get("market") if isinstance(mkt.get("market"), dict) else mkt
            yb = mk.get("yes_bid_dollars") or mk.get("yes_bid")
            ya = mk.get("yes_ask_dollars") or mk.get("yes_ask")
            if side == "yes" and ya is not None:
                place_price = float(ya)
            elif side == "no" and yb is not None:
                place_price = max(0.01, min(0.99, 1.0 - float(yb)))
            if place_price < lo - 1e-9 or place_price > hi + 1e-9:
                # At entry time, fall back to gate price if still in band
                gp = float(gate["price"])
                if lo - 1e-9 <= gp <= hi + 1e-9:
                    place_price = gp
                else:
                    row = {
                        "event": "usd_skip",
                        "ok": False,
                        "reason": "live_outside_band",
                        "asset": bet.get("asset"),
                        "ticker": ticker,
                        "side": side,
                        "entry_price": gp,
                        "live_price": place_price,
                        "need": f"{lo}-{hi}",
                        "take_next": take_next,
                        "truth_note": (
                            "r1686 buy-low: refuse chase above scalp band; "
                            "empty round better than high-on-drugs entry"
                        ),
                    }
                    _log(row, state_dir=state_dir)
                    return row
        except Exception:
            pass

        n_contracts = int(
            gate.get("count")
            or contracts_for_ammo(state_dir=state_dir)
        )

        def _place_once(px: float) -> dict:
            return client.place_limit_order(
                ticker=ticker,
                side=side,
                price=float(px),
                count=n_contracts,
                volume=vol_f if vol_f is not None else 10000.0,
                dry_run=bool(dry_run),
            )

        try:
            placed = _place_once(place_price)
            # r1686: at most ONE +1¢ rebid — never chase past scalp hi
            tries = 0
            rebid_hi = float(hi)
            while (
                not dry_run
                and float(placed.get("fill_count") or 0) <= 0
                and tries < 1
            ):
                tries += 1
                bump = min(rebid_hi, float(place_price) + 0.01)
                if bump <= float(place_price) + 1e-9:
                    break
                placed = _place_once(bump)
                place_price = bump
                _log(
                    {
                        "event": "usd_rebid",
                        "asset": bet.get("asset"),
                        "ticker": ticker,
                        "try": tries,
                        "price": bump,
                        "scalp_no_chase": True,
                        "fill_count": placed.get("fill_count"),
                        "take_next": take_next,
                    },
                    state_dir=state_dir,
                )
        except (CapRejected, KillSwitchActive, NotProvisioned) as exc:
            row = {
                "event": "usd_reject",
                "ok": False,
                "reason": f"{type(exc).__name__}:{exc}",
                "asset": bet.get("asset"),
                "ticker": bet.get("ticker"),
            }
            _log(row, state_dir=state_dir)
            return row
        except Exception as exc:
            row = {
                "event": "usd_error",
                "ok": False,
                "reason": f"{type(exc).__name__}:{exc}",
                "asset": bet.get("asset"),
                "ticker": bet.get("ticker"),
            }
            _log(row, state_dir=state_dir)
            return row

        fill_count = float(placed.get("fill_count") or 0.0)
        # Prefer side premium (NO = 1 − YES-book fill). Never book YES-book as NO cost.
        raw_price = placed.get("side_price")
        if raw_price is None:
            raw_price = placed.get("price")
        if raw_price is None:
            raw_price = placed.get("average_fill_price")
        if raw_price is None:
            raw_price = gate["price"]
        actual_price = float(raw_price)
        yes_fill = placed.get("yes_fill_price")
        if yes_fill is None and placed.get("average_fill_price") is not None:
            yes_fill = placed.get("average_fill_price")
        healed_no_premium = False
        side_p, yf_h, healed = _heal_no_side_premium(
            side=side,
            price=actual_price,
            limit_price=float(gate.get("price") or 0.0),
            yes_fill_price=yes_fill,
        )
        if healed:
            actual_price = side_p
            yes_fill = yf_h
            healed_no_premium = True
        elif side == "yes" and placed.get("side_price") is None and placed.get("average_fill_price") is not None:
            # YES: average_fill is already the premium
            actual_price = round(max(0.01, min(0.99, float(placed["average_fill_price"]))), 4)
        average_fee = float(placed.get("average_fee_paid") or 0.0)
        fee_paid = float(
            placed.get("fee_paid_usd")
            or round(max(0.0, fill_count) * max(0.0, average_fee), 4)
        )
        client_side_ok = (
            not healed_no_premium
            and (
                placed.get("side_price") is not None
                or placed.get("price_convention") == "side_premium_not_yes_book"
            )
        )
        if client_side_ok and placed.get("premium_usd") is not None:
            premium = float(placed.get("premium_usd") or 0.0)
        else:
            premium = round(max(0.0, fill_count) * actual_price, 4)
        if client_side_ok and placed.get("cost_usd") is not None:
            actual_cost = float(placed.get("cost_usd") or 0.0)
        else:
            actual_cost = round(premium + fee_paid, 4)

        if not placed.get("dry_run") and fill_count <= 0:
            row = {
                "event": "usd_no_fill",
                "ok": True,
                "filled": False,
                "asset": bet.get("asset"),
                "ticker": bet.get("ticker"),
                "side": side,
                "limit_price": float(gate["price"]),
                "client_order_id": placed.get("client_order_id"),
                "order_id": placed.get("order_id"),
                "fill_count": fill_count,
                "remaining_count": placed.get("remaining_count"),
                "rainman_action": action,
                "rainman_score": rainman_score,
                "rainman_bucket": rainman_bucket,
                "deal": "r1648",
                "truth_note": "IOC accepted but no exchange fill; no position or exposure booked",
            }
            _log(row, state_dir=state_dir)
            log_ev_row(row, state_dir=state_dir)
            return row

        open_row = {
            "ticker": bet.get("ticker"),
            "asset": bet.get("asset"),
            "side": side,
            "label": bet.get("label") or ("UP" if side == "yes" else "DOWN"),
            "price": actual_price,
            "side_price": actual_price,
            "yes_fill_price": (
                float(yes_fill) if yes_fill is not None else placed.get("yes_fill_price")
            ),
            "limit_price": float(gate["price"]),
            "count": fill_count,
            "premium_usd": premium,
            "fee_paid_usd": fee_paid,
            "cost_usd": actual_cost,
            "client_order_id": placed.get("client_order_id"),
            "order_id": placed.get("order_id"),
            "ts": time.time(),
            "dry_run": bool(placed.get("dry_run")),
            "fill_count": fill_count,
            "rainman_score": rainman_score,
            "rainman_bucket": rainman_bucket,
            "price_convention": "side_premium_not_yes_book",
        }
        if not placed.get("dry_run"):
            opens = list(night.get("open") or [])
            opens.append(open_row)
            night["open"] = opens
            night["n_placed"] = int(night.get("n_placed") or 0) + 1
            save_night(night, state_dir=state_dir)
            # Consume take-next after a real fill (owner one-shot demand met per ticket)
            if take_next:
                try:
                    take_path.write_text(
                        json.dumps(
                            {
                                "armed": True,
                                "ts": time.time(),
                                "last_fill_asset": bet.get("asset"),
                                "last_fill_order_id": placed.get("order_id"),
                                "note": "still armed until 3 open or owner clears",
                                "truth_label": "OWNER_TAKE_NEXT_USD_V1",
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    if len(opens) >= MAX_OPEN:
                        take_path.write_text(
                            json.dumps(
                                {
                                    "armed": False,
                                    "ts": time.time(),
                                    "reason": "max_open_filled",
                                    "truth_label": "OWNER_TAKE_NEXT_USD_V1",
                                },
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                except Exception:
                    pass

        row = {
            "event": "usd_place",
            "ok": True,
            "dry_run": bool(placed.get("dry_run")),
            "asset": bet.get("asset"),
            "ticker": bet.get("ticker"),
            "side": side,
            "price": actual_price,
            "limit_price": float(gate["price"]),
            "cost_usd": open_row["cost_usd"],
            "premium_usd": premium,
            "fee_paid_usd": fee_paid,
            "client_order_id": placed.get("client_order_id"),
            "order_id": placed.get("order_id"),
            "rainman_action": action,
            "rainman_score": rainman_score,
            "rainman_bucket": rainman_bucket,
            "fill_count": fill_count,
            "filled": bool(fill_count and float(fill_count) > 0),
            "deal": "r1648",
        }
        _log(row, state_dir=state_dir)
        try:
            log_ev_row(
                {
                    "event": "live_place",
                    "asset": bet.get("asset"),
                    "ticker": bet.get("ticker"),
                    "side": side,
                    "price": actual_price,
                    "limit_price": float(gate["price"]),
                    "cost_usd": open_row["cost_usd"],
                    "premium_usd": premium,
                    "fee_paid_usd": fee_paid,
                    "rainman_action": action,
                    "rainman_score": rainman_score,
                    "rainman_bucket": rainman_bucket,
                    "fill_count": fill_count,
                    "order_id": placed.get("order_id"),
                    "paper_stake": bet.get("stake"),
                },
                state_dir=state_dir,
            )
        except Exception:
            pass
        return row
    except Exception as exc:
        row = {"event": "usd_mirror_fault", "ok": False, "reason": f"{type(exc).__name__}:{exc}"}
        _log(row, state_dir=state_dir)
        return row


def maybe_mirror_paper_bet(
    bet: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Serialize the entire real-USD cap check and IOC bookkeeping."""
    # r1665: never mirror HYPE/ZEC (owner ban — uncorrelated / trash)
    try:
        from System.alice_15m_co_direction import is_banned_15m_asset

        if is_banned_15m_asset(str((bet or {}).get("asset") or "")):
            return {
                "ok": False,
                "reason": "banned_asset",
                "detail": "HYPE/ZEC removed from 15m trading (owner)",
                "asset": (bet or {}).get("asset"),
            }
    except Exception:
        a = str((bet or {}).get("asset") or "").upper()
        if a in ("HYPE", "ZEC"):
            return {"ok": False, "reason": "banned_asset", "asset": a}
    with _order_lock(state_dir=state_dir):
        return _maybe_mirror_paper_bet_locked(
            bet,
            state_dir=state_dir,
            dry_run=dry_run,
        )


def note_settle_from_paper(
    *,
    ticker: str,
    win: bool,
    entry_price: float,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """When paper settles a ticker we also hold live — book night PnL (1 contract model).

    Win: +(1-p) roughly Kalshi profit on $1 face; cost was p → profit 1-p.
    Lose: -p (lose the premium paid).
    For r1644 $1-ticket scoreboard we also track unit: win +(1/p-1)*cost? 
    Simple 1-contract: win +(1-p), lose -p.
    """
    night = load_night(state_dir)
    opens = list(night.get("open") or [])
    t = str(ticker or "")
    kept = []
    matched = None
    for o in opens:
        if str(o.get("ticker") or "") == t and matched is None:
            matched = o
        else:
            kept.append(o)
    if matched is None:
        return {"ok": False, "reason": "not_in_usd_open"}
    p = float(matched.get("price") or entry_price or 0.8)
    count = max(0.0, float(matched.get("count") or matched.get("fill_count") or 1.0))
    fee_paid = max(0.0, float(matched.get("fee_paid_usd") or 0.0))
    pnl_before_fee = float(live_contract_pnl(bool(win), p)) * count
    pnl = round(pnl_before_fee - fee_paid, 4)
    paper_pnl = float(paper_unit_pnl(bool(win), p))
    filled_cost = max(0.0, float(matched.get("cost_usd") or 0.0))
    live_unit_pnl = round(pnl / filled_cost, 4) if filled_cost > 0 else None
    night["open"] = kept
    night["realized_pnl_usd"] = round(float(night.get("realized_pnl_usd") or 0.0) + pnl, 4)
    night["n_settled"] = int(night.get("n_settled") or 0) + 1
    if night["realized_pnl_usd"] <= -MAX_NIGHT_LOSS:
        night["halted"] = True
        night["halt_reason"] = f"night_loss_stop {night['realized_pnl_usd']}"
        from System.kalshi_prod_trade_client import set_kill_switch

        set_kill_switch(True, reason=night["halt_reason"], state_dir=_state(state_dir))
    save_night(night, state_dir=state_dir)
    row = {
        "event": "usd_settle_book",
        "ok": True,
        "ticker": t,
        "win": win,
        "pnl_usd": pnl,
        "pnl_before_fee_usd": round(pnl_before_fee, 4),
        "fee_paid_usd": fee_paid,
        "fill_count": count,
        "paper_unit_pnl": paper_pnl,
        "live_unit_pnl": live_unit_pnl,
        "price": p,
        "night_pnl": night["realized_pnl_usd"],
        "halted": night.get("halted"),
        "deal": "r1648",
    }
    _log(row, state_dir=state_dir)
    try:
        log_ev_row(
            {
                "event": "live_vs_paper_settle",
                "ticker": t,
                "asset": matched.get("asset"),
                "win": win,
                "price": p,
                "live_pnl_usd": pnl,
                "pnl_before_fee_usd": round(pnl_before_fee, 4),
                "fee_paid_usd": fee_paid,
                "fill_count": count,
                "paper_unit_pnl": paper_pnl,
                "live_unit_pnl": live_unit_pnl,
                "delta_live_unit_minus_paper_unit": (
                    round(float(live_unit_pnl) - paper_pnl, 4)
                    if live_unit_pnl is not None
                    else None
                ),
                "night_pnl": night["realized_pnl_usd"],
            },
            state_dir=state_dir,
        )
    except Exception:
        pass
    return row


def _heal_no_side_premium(
    *,
    side: str,
    price: float,
    limit_price: float = 0.0,
    yes_fill_price: Any = None,
) -> tuple[float, Optional[float], bool]:
    """Return (side_premium, yes_fill, healed).

    Kalshi V2 average_fill is YES-book. Favorite NO fills were often stored as the
    YES residual (e.g. 13¢) while limit was 82¢ — real NO premium is 1 − yes_fill.
    """
    side_l = str(side or "").lower()
    p = float(price or 0.0)
    lim = float(limit_price or 0.0)
    yf: Optional[float] = None
    if yes_fill_price is not None:
        try:
            yf = float(yes_fill_price)
        except (TypeError, ValueError):
            yf = None
    if side_l != "no":
        return (round(max(0.01, min(0.99, p)), 4) if p > 0 else p, yf, False)
    if p <= 0:
        return (p, yf, False)
    # Already looks like a real NO premium (favorite band)
    if p >= 0.55:
        return (
            round(max(0.01, min(0.99, p)), 4),
            yf if yf is not None else round(1.0 - p, 4),
            False,
        )
    # YES residual only when we have a favorite-side limit (or explicit yes_fill)
    if yf is None and 0.01 <= p <= 0.50:
        yf = p
    if yf is not None and lim >= 0.55:
        side_p = round(max(0.01, min(0.99, 1.0 - float(yf))), 4)
        return side_p, round(float(yf), 4), True
    return (round(max(0.01, min(0.99, p)), 4) if p > 0 else p, yf, False)


def heal_open_no_premiums(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Rewrite open night rows so NO premium = 1 − YES fill (exposure truth)."""
    night = load_night(state_dir)
    opens = list(night.get("open") or [])
    fixed: list[dict[str, Any]] = []
    n_healed = 0
    for raw in opens:
        o = dict(raw)
        side_p, yf, healed = _heal_no_side_premium(
            side=str(o.get("side") or ""),
            price=float(o.get("price") or 0.0),
            limit_price=float(o.get("limit_price") or 0.0),
            yes_fill_price=o.get("yes_fill_price"),
        )
        if healed:
            cnt = max(0.0, float(o.get("fill_count") or o.get("count") or 1.0))
            fee = max(0.0, float(o.get("fee_paid_usd") or 0.0))
            o["yes_fill_price"] = yf
            o["price"] = side_p
            o["side_price"] = side_p
            o["premium_usd"] = round(cnt * side_p, 4)
            o["cost_usd"] = round(float(o["premium_usd"]) + fee, 4)
            o["healed_no_premium"] = True
            o["price_convention"] = "side_premium_not_yes_book"
            n_healed += 1
        fixed.append(o)
    night["open"] = fixed
    save_night(night, state_dir=state_dir)
    row = {
        "event": "usd_heal_open_no_premium",
        "ok": True,
        "n_open": len(fixed),
        "n_healed": n_healed,
        "open_premium_usd": round(sum(float(x.get("premium_usd") or 0) for x in fixed), 4),
        "open_cost_usd": round(sum(float(x.get("cost_usd") or 0) for x in fixed), 4),
    }
    _log(row, state_dir=state_dir)
    return row


def recompute_night_realized_no_premium(
    *, state_dir: Optional[Path | str] = None
) -> dict[str, Any]:
    """Rebuild night realized PnL from ledger places+settles with healed NO premiums."""
    root = _state(state_dir)
    path = root / LEDGER
    places: dict[str, dict[str, Any]] = {}
    settles: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(r, dict):
                continue
            ev = str(r.get("event") or "")
            if ev == "usd_place" and r.get("filled"):
                places[str(r.get("ticker") or "")] = r
            elif ev == "usd_settle_book":
                settles.append(r)
    corrected: list[dict[str, Any]] = []
    delta_sum = 0.0
    n_healed = 0
    for s in settles:
        t = str(s.get("ticker") or "")
        pl = places.get(t) or {}
        side = str(pl.get("side") or "")
        if not side:
            # Infer: tiny settle price + win was classic NO residual bug
            side = "no" if float(s.get("price") or 0) <= 0.45 else "yes"
        raw_p = float(pl.get("price") if pl.get("price") is not None else s.get("price") or 0)
        lim = float(pl.get("limit_price") or 0.0)
        side_p, _yf, healed = _heal_no_side_premium(
            side=side,
            price=raw_p,
            limit_price=lim,
            yes_fill_price=pl.get("yes_fill_price"),
        )
        fee = max(0.0, float(pl.get("fee_paid_usd") or s.get("fee_paid_usd") or 0.0))
        cnt = max(0.0, float(pl.get("fill_count") or s.get("fill_count") or 1.0))
        win = bool(s.get("win"))
        pnl_bf = float(live_contract_pnl(win, side_p)) * cnt
        pnl = round(pnl_bf - fee, 4)
        old_pnl = s.get("pnl_usd")
        try:
            old_f = float(old_pnl) if old_pnl is not None else pnl
        except (TypeError, ValueError):
            old_f = pnl
        d = round(pnl - old_f, 4)
        # Only adjust night realized when we actually healed a NO YES-book residual.
        # Skip orphan settles with missing price (would invent phantom +$0.99 wins).
        if not healed:
            continue
        n_healed += 1
        delta_sum += d
        corrected.append(
            {
                "ticker": t,
                "side": side,
                "win": win,
                "price_was": s.get("price"),
                "price_side": side_p,
                "healed": True,
                "pnl_was": old_pnl,
                "pnl_usd": pnl,
                "delta": d,
                "fee_paid_usd": fee,
            }
        )
    night = load_night(state_dir)
    old = float(night.get("realized_pnl_usd") or 0.0)
    night["realized_pnl_usd"] = round(old + delta_sum, 4)
    night["realized_pnl_source"] = "recompute_healed_no_premium_delta"
    night["realized_pnl_was"] = old
    save_night(night, state_dir=state_dir)
    row = {
        "event": "usd_recompute_realized_no_premium",
        "ok": True,
        "n_settles": len(settles),
        "n_corrected": len(corrected),
        "n_healed": n_healed,
        "realized_was": old,
        "realized_now": night["realized_pnl_usd"],
        "delta": round(delta_sum, 4),
        "tickets": corrected[-30:],
    }
    _log(row, state_dir=state_dir)
    return row


def halt_usd_accounting_fix(
    *,
    reason: str = "no_side_premium_bug_r1655",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Immediate USD halt: kill switch + disarm lane/hand; STGM untouched."""
    from System.kalshi_prod_trade_client import set_kill_switch
    from System.kalshi_usd_lane import set_usd_lane_armed

    root = _state(state_dir)
    set_kill_switch(True, reason=reason, state_dir=root)
    lane = set_usd_lane_armed(False, reason=reason, state_dir=state_dir)
    hand = set_hand_live(False, reason=reason, state_dir=state_dir)
    take_path = root / "kalshi_usd_take_next.json"
    try:
        take_path.write_text(
            json.dumps(
                {
                    "armed": False,
                    "ts": time.time(),
                    "reason": reason,
                    "truth_label": "OWNER_TAKE_NEXT_USD_V1",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    heal = heal_open_no_premiums(state_dir=state_dir)
    recompute = recompute_night_realized_no_premium(state_dir=state_dir)
    out = {
        "ok": True,
        "event": "usd_halt_accounting_fix",
        "reason": reason,
        "lane": lane,
        "hand": hand,
        "heal": heal,
        "recompute": {
            k: recompute.get(k)
            for k in ("realized_was", "realized_now", "delta", "n_settles")
        },
        "status": status_line(state_dir),
    }
    _log(out, state_dir=state_dir)
    return out


def arm_from_owner_go(
    *,
    owner_phrase: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Arm lane + live hand under r1644. Does not place orders by itself."""
    from System.kalshi_usd_lane import set_usd_lane_armed
    from System.kalshi_prod_trade_client import set_kill_switch

    set_kill_switch(False, reason="owner_arm_clear", state_dir=_state(state_dir))
    lane = set_usd_lane_armed(True, reason="owner_go_r1647", state_dir=state_dir)
    hand = set_hand_live(
        True,
        reason="owner_go_r1647",
        owner_phrase=owner_phrase,
        state_dir=state_dir,
    )
    # reset night book for session
    night = load_night(state_dir)
    # keep same day book if already trading; only init if empty day
    if not night.get("open") and int(night.get("n_placed") or 0) == 0:
        night = {
            "day": time.strftime("%Y-%m-%d"),
            "realized_pnl_usd": 0.0,
            "open": [],
            "n_placed": 0,
            "n_skipped": 0,
            "n_settled": 0,
            "halted": False,
            "halt_reason": "",
            "armed_phrase": owner_phrase[:200],
            "truth_label": TRUTH,
        }
        save_night(night, state_dir=state_dir)
    out = {
        "ok": True,
        "lane": lane,
        "hand": hand,
        "night": {k: night.get(k) for k in ("day", "realized_pnl_usd", "open", "halted")},
        "caps": hand.get("caps"),
        "truth_label": TRUTH,
    }
    _log({"event": "owner_arm", **out}, state_dir=state_dir)
    return out


__all__ = [
    "maybe_mirror_paper_bet",
    "evaluate_ticket",
    "arm_from_owner_go",
    "set_hand_live",
    "is_hand_live",
    "status_line",
    "note_settle_from_paper",
    "load_night",
    "MIN_ENTRY",
    "MAX_ENTRY",
    "MAX_OPEN",
    "TRUTH",
]
