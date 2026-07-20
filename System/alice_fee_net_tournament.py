#!/usr/bin/env python3
"""r1667 — fee-net shadow tournament + policy-hash interlock + strategy cohorts.

Owner + Codex: high win-rate at 70–88¢ is not an edge (gate70 74.9% WR still
−8.4u). Optimize fee-net EV and drawdown, never raw WR.

Cohorts (immutable labels on every new ticket):
  • minute7_best1  — live default: one best co-dir ticker (owner streak)
  • minute7_best2  — shadow: best co-dir pair
  • minute5_best1  — shadow: single at ≤5:00
  • legacy_unknown — pre-cohort / missing strategy_variant

Rules:
  • Paper + shadow only while epoch active (USD hard OFF)
  • HYPE/ZEC/NEAR weird; visible in shadow research, never live
  • DOGE shadow-only
  • Promote only after 200 tickets, 50 windows, fee-net EV>0, 95% CI floor>0
  • Stale process: running policy_hash ≠ disk → no new paper/USD tickets

Truth: ALICE_FEE_NET_TOURNAMENT_V1
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_FEE_NET_TOURNAMENT_V1"
RECEIPT = "r1667-codex-fee-net-shadow-tournament"
CONFIG_NAME = "alice_fee_net_tournament.json"
SHADOW_LOG = "alice_fee_net_shadow.jsonl"
REPORT_NAME = "alice_fee_net_tournament_report.json"
REPORT_MD = "alice_fee_net_tournament_report.md"
POLICY_NAME = "alice_policy_hash.json"

# Immutable cohort ids
COHORT_M7_BEST1 = "minute7_best1"
COHORT_M7_BEST2 = "minute7_best2"
COHORT_M5_BEST1 = "minute5_best1"
COHORT_LEGACY = "legacy_unknown"
LIVE_COHORTS = frozenset({COHORT_M7_BEST1})  # owner: one ticker at a time
SHADOW_COHORTS = frozenset({COHORT_M7_BEST2, COHORT_M5_BEST1})
SHADOW_ONLY_ASSETS = frozenset({"DOGE"})
WEIRD_ASSETS = frozenset({"HYPE", "ZEC", "NEAR"})

# Promotion gates (Codex / owner)
PROMOTE_MIN_TICKETS = 200
PROMOTE_MIN_WINDOWS = 50
# Live paper during tournament: single best name
# r1688/r1692: up to 3 tickets; max 2 same dir (don't triple one field bet)
LIVE_MAX_OPEN = 3
LIVE_MAX_SAME_DIR = 2
ENTRY_MAX_SECS_M7 = 7 * 60
ENTRY_MAX_SECS_M5 = 5 * 60
ENTRY_MIN_SECS = 45
MIN_FAV = 0.70
MAX_FAV = 0.88

# Pair correlation: if second name too correlated / same mid band, sit or single
PAIR_CORR_PENALTY = 0.35  # EV haircut when both same side of field
PAIR_SIT_IF_SECOND_SCORE_LT = 0.15


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def normalize_cohort(strategy_variant: Any, *, rule: Any = None) -> str:
    """Map ticket metadata → immutable cohort (legacy if unknown)."""
    raw = str(strategy_variant or "").strip().lower()
    rule_s = str(rule or "").strip().lower()
    aliases = {
        "minute7_best1": COHORT_M7_BEST1,
        "minute7_best1_same_dir": COHORT_M7_BEST1,
        "minute7_single": COHORT_M7_BEST1,
        "minute7_best2": COHORT_M7_BEST2,
        "minute7_best2_same_dir": COHORT_M7_BEST2,
        "minute7_pair": COHORT_M7_BEST2,
        "minute5_best1": COHORT_M5_BEST1,
        "minute5_single": COHORT_M5_BEST1,
        "minute5_best1_same_dir": COHORT_M5_BEST1,
        # r1688: top-3 dual scalps (map to live cohort for promote accounting)
        "minute14_best3_scalp": COHORT_M7_BEST1,
        "minute14_best3": COHORT_M7_BEST1,
        "scalp_top3": COHORT_M7_BEST1,
    }
    if raw in aliases:
        return aliases[raw]
    if "best1" in raw or "single" in raw:
        if "5" in raw:
            return COHORT_M5_BEST1
        if "7" in raw or "11" in raw:
            return COHORT_M7_BEST1
    if "best2" in raw or "pair" in raw or "best3" in raw:
        return COHORT_M7_BEST2
    if rule_s and ("minute7" in rule_s or "minute11" in rule_s or "learner" in rule_s):
        return COHORT_LEGACY
    if not raw:
        return COHORT_LEGACY
    return COHORT_LEGACY


def estimate_taker_fee(price: float, *, contracts: float = 1.0) -> float:
    try:
        from System.alice_15m_scalp_learner import estimate_taker_fee as _fee

        return float(_fee(price, contracts=contracts))
    except Exception:
        p = min(0.99, max(0.01, float(price)))
        raw = 0.07 * max(0.01, contracts) * p * (1.0 - p)
        return round(max(0.0001, math.ceil(raw * 10_000.0 - 1e-12) / 10_000.0), 4)


def fee_net_unit_pnl(
    *,
    win: bool,
    entry_price: float,
    exit_price: Optional[float] = None,
    contracts: float = 1.0,
    include_exit_fee: bool = True,
    fill_drift: float = 0.0,
    spread_half: float = 0.0,
    cash_out: bool = False,
) -> dict[str, Any]:
    """Exact-ish unit PnL after entry fee (+ optional exit fee / drift / spread).

    Settlement win: +(1 - p_eff) - fees; loss: -p_eff - entry_fee.
    p_eff = entry + fill_drift + spread_half (adverse).
    """
    p = min(0.99, max(0.01, float(entry_price) + float(fill_drift) + float(spread_half)))
    c = max(0.01, float(contracts))
    fee_in = estimate_taker_fee(p, contracts=c)
    fee_out = 0.0
    if cash_out and exit_price is not None:
        fee_out = estimate_taker_fee(float(exit_price), contracts=c) if include_exit_fee else 0.0
        # mark cash-out: sell at exit, paid p for yes-side unit
        gross = (float(exit_price) - p) * c
        net = gross - fee_in - fee_out
        return {
            "gross": round(gross, 6),
            "fee_in": fee_in,
            "fee_out": fee_out,
            "net": round(net, 6),
            "mode": "cash_out",
            "p_eff": round(p, 4),
        }
    if win:
        gross = (1.0 - p) * c
    else:
        gross = -p * c
    net = gross - fee_in - (fee_out if include_exit_fee and not win else 0.0)
    # settle: only entry fee on binary (exit is $1 or $0, no second taker)
    net = gross - fee_in
    return {
        "gross": round(gross, 6),
        "fee_in": fee_in,
        "fee_out": 0.0,
        "net": round(net, 6),
        "mode": "settle",
        "p_eff": round(p, 4),
        "win": bool(win),
    }


def policy_payload() -> dict[str, Any]:
    """Canonical policy frozen for hash interlock (no floats that drift)."""
    return {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "live_cohort": COHORT_M7_BEST1,
        "shadow_cohorts": sorted(SHADOW_COHORTS),
        "live_max_open": LIVE_MAX_OPEN,
        "live_max_same_dir": LIVE_MAX_SAME_DIR,
        "entry_max_secs_m7": ENTRY_MAX_SECS_M7,
        "entry_max_secs_m5": ENTRY_MAX_SECS_M5,
        "entry_min_secs": ENTRY_MIN_SECS,
        "band": [MIN_FAV, MAX_FAV],
        "shadow_only_assets": sorted(SHADOW_ONLY_ASSETS),
        "weird_assets": sorted(WEIRD_ASSETS),
        "promote_min_tickets": PROMOTE_MIN_TICKETS,
        "promote_min_windows": PROMOTE_MIN_WINDOWS,
        "usd_mode": "off_shadow_only",
        "pair_corr_penalty": PAIR_CORR_PENALTY,
    }


def compute_policy_hash(payload: Optional[dict[str, Any]] = None) -> str:
    blob = json.dumps(payload or policy_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def write_policy_hash(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    payload = policy_payload()
    h = compute_policy_hash(payload)
    row = {
        "truth_label": "ALICE_POLICY_HASH_V1",
        "policy_hash": h,
        "payload": payload,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "receipt_id": RECEIPT,
    }
    (root / POLICY_NAME).write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def load_policy_hash(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _state(state_dir) / POLICY_NAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def running_policy_hash() -> str:
    return compute_policy_hash(policy_payload())


def policy_allows_trade(*, state_dir: Optional[Path | str] = None) -> tuple[bool, str]:
    """Stale-process interlock: running code must match disk policy hash."""
    disk = load_policy_hash(state_dir=state_dir)
    disk_h = str(disk.get("policy_hash") or "")
    run_h = running_policy_hash()
    if not disk_h:
        return False, "policy_hash_missing"
    if disk_h != run_h:
        return False, f"policy_hash_mismatch disk={disk_h} running={run_h}"
    cfg = load_config(state_dir=state_dir)
    if cfg.get("usd_shadow_only") and cfg.get("epoch_active"):
        # paper still allowed; USD refused elsewhere
        pass
    if not cfg.get("epoch_active", True):
        return False, "tournament_epoch_inactive"
    return True, "ok"


def load_config(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _state(state_dir) / CONFIG_NAME
    if not p.exists():
        return default_config()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return {**default_config(), **d}
    except Exception:
        pass
    return default_config()


def default_config() -> dict[str, Any]:
    return {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "epoch_active": True,
        "usd_shadow_only": True,
        "live_cohort": COHORT_M7_BEST1,
        "live_max_open": LIVE_MAX_OPEN,
        "live_max_same_dir": LIVE_MAX_SAME_DIR,
        "shadow_cohorts": list(SHADOW_COHORTS),
        "note": (
            "r1667: live = one best co-dir ticker (owner streak). "
            "Shadow records pair + minute-5 single. USD OFF."
        ),
    }


def save_config(cfg: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> Path:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    p = root / CONFIG_NAME
    cfg = {**cfg, "ts": time.time(), "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    p.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    return p


def disarm_usd_for_shadow(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Hard OFF USD lane + hand for shadow epoch (no kill switch — re-armable)."""
    from System.kalshi_usd_lane import set_usd_lane_armed
    from System.kalshi_usd_hand import set_hand_live, status_line

    root = _state(state_dir)
    lane = set_usd_lane_armed(
        False, reason="r1667_fee_net_shadow_usd_off", state_dir=state_dir
    )
    hand = set_hand_live(
        False, reason="r1667_fee_net_shadow_usd_off", state_dir=state_dir
    )
    take = root / "kalshi_usd_take_next.json"
    try:
        take.write_text(
            json.dumps(
                {
                    "armed": False,
                    "ts": time.time(),
                    "reason": "r1667_fee_net_shadow_usd_off",
                    "truth_label": "OWNER_TAKE_NEXT_USD_V1",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return {
        "ok": True,
        "lane": lane,
        "hand": hand,
        "status": status_line(state_dir),
        "receipt_id": RECEIPT,
    }


def asset_trade_class(asset: str) -> str:
    a = str(asset or "").upper()
    if a in WEIRD_ASSETS:
        return "weird"
    if a in SHADOW_ONLY_ASSETS:
        return "shadow_only"
    return "live_ok"


def pair_decision(
    candidates: list[dict[str, Any]],
    *,
    field_clear: bool = True,
) -> dict[str, Any]:
    """Choose 0–2 tickets: prefer single best; pair only if second is strong enough.

    candidates: sorted best-first with keys asset, side, co_dir_score, fav
    """
    shadow_usable: list[dict[str, Any]] = []
    live_usable: list[dict[str, Any]] = []
    for c in candidates:
        a = str(c.get("asset") or "").upper()
        cls = asset_trade_class(a)
        shadow_usable.append(c)
        if cls == "live_ok":
            live_usable.append(c)
    if not live_usable:
        return {
            "action": "sit",
            "live": [],
            "shadow_pair": shadow_usable[:2],
            "reason": "no_live_candidates",
        }
    if not shadow_usable:
        return {"action": "sit", "live": [], "shadow_pair": [], "reason": "no_candidates"}

    best = live_usable[0]
    live = [best]
    shadow_pair = [shadow_usable[0]]
    reason = "single_best"

    if len(shadow_usable) >= 2 and field_clear:
        shadow_best = shadow_usable[0]
        second = shadow_usable[1]
        sc2 = float(second.get("co_dir_score") or second.get("score") or 0.0)
        same_side = str(shadow_best.get("side") or "") == str(second.get("side") or "")
        if sc2 < PAIR_SIT_IF_SECOND_SCORE_LT:
            reason = "second_too_weak_single_only"
            shadow_pair = [shadow_best]  # pair shadow empty second
        elif not same_side:
            reason = "second_contrarian_skip"
        else:
            # correlated pair — shadow both; live still single (owner preference)
            shadow_pair = [shadow_best, second]
            reason = "pair_shadow_live_single"
            # optional: if second almost as strong, still live single only
    return {
        "action": "bet",
        "live": live,
        "shadow_pair": shadow_pair,
        "reason": reason,
        "corr_penalty": PAIR_CORR_PENALTY if len(shadow_pair) > 1 else 0.0,
    }


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def record_shadow_window(
    *,
    window_id: str,
    field: str,
    candidates: list[dict[str, Any]],
    point_in_time_ts: float,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Same-window shadow rows for m7-best1, m7-best2, m5-best1 (no future leakage).

    candidates must already be point-in-time (caller freezes mids/secs).
    """
    root = _state(state_dir)
    decision = pair_decision(candidates, field_clear=True)
    rows: list[dict[str, Any]] = []

    def _mk(cohort: str, picks: list[dict[str, Any]], max_secs: int) -> dict[str, Any]:
        tickets = []
        for p in picks:
            secs = p.get("secs")
            try:
                secs_i = int(secs) if secs is not None else None
            except (TypeError, ValueError):
                secs_i = None
            # minute-5 cohort only records if secs was ≤300 at freeze
            if cohort == COHORT_M5_BEST1 and secs_i is not None and secs_i > max_secs:
                continue
            if cohort != COHORT_M5_BEST1 and secs_i is not None and secs_i > max_secs:
                continue
            price = float(p.get("fav") or p.get("price") or 0.0)
            side = str(p.get("side") or "")
            fee = estimate_taker_fee(price)
            tickets.append(
                {
                    "asset": p.get("asset"),
                    "side": side,
                    "price": price,
                    "secs": secs_i,
                    "fee_in": fee,
                    "class": asset_trade_class(str(p.get("asset") or "")),
                }
            )
        return {
            "truth_label": TRUTH,
            "event": "shadow_window",
            "cohort": cohort,
            "window_id": window_id,
            "field": field,
            "ts": point_in_time_ts,
            "stamp": datetime.fromtimestamp(point_in_time_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "tickets": tickets,
            "n": len(tickets),
            "decision_reason": decision.get("reason"),
            "settled": False,
            "receipt_id": RECEIPT,
        }

    live_picks = decision.get("live") or []
    pair_picks = decision.get("shadow_pair") or []
    rows.append(_mk(COHORT_M7_BEST1, live_picks, ENTRY_MAX_SECS_M7))
    rows.append(_mk(COHORT_M7_BEST2, pair_picks, ENTRY_MAX_SECS_M7))
    # minute-5: only first pick if still in window at freeze
    rows.append(_mk(COHORT_M5_BEST1, live_picks[:1], ENTRY_MAX_SECS_M5))

    for row in rows:
        if row["n"] > 0:
            _append_jsonl(root / SHADOW_LOG, row)
    return {
        "window_id": window_id,
        "decision": decision,
        "shadow_rows": rows,
        "policy_hash": running_policy_hash(),
    }


def settle_shadow_ticket(
    *,
    window_id: str,
    cohort: str,
    asset: str,
    win: bool,
    entry_price: float,
    state_dir: Optional[Path | str] = None,
    owner_intervention: bool = False,
) -> dict[str, Any]:
    net = fee_net_unit_pnl(win=win, entry_price=entry_price)
    row = {
        "truth_label": TRUTH,
        "event": "shadow_settle",
        "window_id": window_id,
        "cohort": normalize_cohort(cohort),
        "asset": str(asset or "").upper(),
        "win": bool(win),
        "entry_price": float(entry_price),
        "fee_net": net,
        "owner_intervention": bool(owner_intervention),
        "ts": time.time(),
        "receipt_id": RECEIPT,
    }
    if owner_intervention:
        row["exit_kind"] = "owner_intervention"
    _append_jsonl(_state(state_dir) / SHADOW_LOG, row)
    return row


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    """95% Wilson lower bound on win rate (not EV — used as WR floor check)."""
    if n <= 0:
        return 0.0
    phat = wins / n
    denom = 1.0 + z * z / n
    centre = phat + z * z / (2 * n)
    adj = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return max(0.0, (centre - adj) / denom)


def fee_net_ci_lower(nets: list[float], z: float = 1.96) -> float:
    """Normal approx 95% lower bound on mean fee-net EV."""
    if not nets:
        return 0.0
    n = len(nets)
    mu = _mean(nets)
    if n < 2:
        return mu
    var = sum((x - mu) ** 2 for x in nets) / (n - 1)
    se = math.sqrt(max(0.0, var) / n)
    return mu - z * se


def max_drawdown(nets: list[float]) -> float:
    peak = 0.0
    equity = 0.0
    mdd = 0.0
    for x in nets:
        equity += x
        peak = max(peak, equity)
        mdd = min(mdd, equity - peak)
    return mdd


def bootstrap_report(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Aggregate shadow settles + paper settles by cohort (fee-net)."""
    root = _state(state_dir)
    by_cohort: dict[str, list[dict[str, Any]]] = {
        COHORT_M7_BEST1: [],
        COHORT_M7_BEST2: [],
        COHORT_M5_BEST1: [],
        COHORT_LEGACY: [],
    }
    # shadow settles
    sp = root / SHADOW_LOG
    if sp.exists():
        for line in sp.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("event") != "shadow_settle":
                continue
            c = normalize_cohort(r.get("cohort"))
            net = float((r.get("fee_net") or {}).get("net") or 0.0)
            by_cohort.setdefault(c, []).append(
                {"win": bool(r.get("win")), "net": net, "src": "shadow"}
            )

    # paper settled → fee-net recompute + cohort
    settled_path = root / "alice_15m_settled.jsonl"
    windows: set[str] = set()
    if settled_path.exists():
        for line in settled_path.read_text(encoding="utf-8", errors="replace").splitlines()[
            -3000:
        ]:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            c = normalize_cohort(
                r.get("strategy_variant") or (r.get("decision_evidence") or {}).get("strategy_variant"),
                rule=r.get("rule") or r.get("strategy"),
            )
            price = float(r.get("price") or 0.5)
            win = bool(r.get("win"))
            net = fee_net_unit_pnl(win=win, entry_price=price)["net"]
            by_cohort.setdefault(c, []).append(
                {
                    "win": win,
                    "net": net,
                    "src": "paper",
                    "asset": r.get("asset"),
                    "price": price,
                }
            )
            t = str(r.get("ticker") or "")
            if "-" in t:
                parts = t.split("-")
                if len(parts) >= 2:
                    windows.add(parts[1])

    cohorts_out: dict[str, Any] = {}
    for c, rows in by_cohort.items():
        nets = [float(x["net"]) for x in rows]
        wins = sum(1 for x in rows if x.get("win"))
        n = len(rows)
        mu = _mean(nets)
        cohorts_out[c] = {
            "n": n,
            "wins": wins,
            "wr": round(wins / n, 4) if n else 0.0,
            "fee_net_ev": round(mu, 6),
            "fee_net_sum": round(sum(nets), 4),
            "fee_net_ci95_lower": round(fee_net_ci_lower(nets), 6),
            "wr_wilson95_lower": round(_wilson_lower(wins, n), 4) if n else 0.0,
            "max_drawdown": round(max_drawdown(nets), 4),
            "promote_ready": bool(
                n >= PROMOTE_MIN_TICKETS
                and len(windows) >= PROMOTE_MIN_WINDOWS
                and mu > 0
                and fee_net_ci_lower(nets) > 0
            ),
        }

    # promotion only on live cohort
    live = cohorts_out.get(COHORT_M7_BEST1) or {}
    promote = bool(live.get("promote_ready")) and live.get("n", 0) >= PROMOTE_MIN_TICKETS

    out = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "policy_hash": running_policy_hash(),
        "n_windows_seen": len(windows),
        "promote_gates": {
            "min_tickets": PROMOTE_MIN_TICKETS,
            "min_windows": PROMOTE_MIN_WINDOWS,
            "need_fee_net_ev_gt_0": True,
            "need_fee_net_ci95_lower_gt_0": True,
            "live_cohort": COHORT_M7_BEST1,
            "promote": promote,
        },
        "cohorts": cohorts_out,
        "owner_note": (
            "Live strategy = minute7_best1 (one ticker). "
            "Pair + minute5 are shadow-only until promote gates clear."
        ),
        "key_correction": (
            "High WR at expensive entries can lose money. "
            "gate70 ~74.9% WR still fee-net negative historically."
        ),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / REPORT_NAME).write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = [
        f"# Fee-net tournament · {out['stamp']}",
        "",
        f"**Policy hash:** `{out['policy_hash']}`",
        f"**Promote:** `{promote}` (need {PROMOTE_MIN_TICKETS} tickets, {PROMOTE_MIN_WINDOWS} windows, EV>0, CI>0)",
        "",
        out["owner_note"],
        "",
        "## Cohorts (fee-net)",
    ]
    for c, s in cohorts_out.items():
        md.append(
            f"- **{c}**: n={s['n']} WR={s['wr']:.1%} EV={s['fee_net_ev']:+.4f} "
            f"CI95lo={s['fee_net_ci95_lower']:+.4f} MDD={s['max_drawdown']:+.2f} "
            f"promote_ready={s['promote_ready']}"
        )
    md += ["", "## Codex", f"Receipt `{RECEIPT}`. USD OFF. Extend organs; do not fork pickers.", ""]
    (root / REPORT_MD).write_text("\n".join(md), encoding="utf-8")
    return out


def tag_ticket_cohort(ticket: dict[str, Any]) -> dict[str, Any]:
    """Stamp immutable cohort on a paper/USD ticket dict."""
    out = dict(ticket)
    c = normalize_cohort(
        out.get("strategy_variant") or out.get("cohort"),
        rule=out.get("rule"),
    )
    out["cohort"] = c
    out["strategy_variant"] = out.get("strategy_variant") or c
    out["policy_hash"] = running_policy_hash()
    return out


def live_caps(*, state_dir: Optional[Path | str] = None) -> dict[str, int]:
    cfg = load_config(state_dir=state_dir)
    return {
        "max_open": int(cfg.get("live_max_open") or LIVE_MAX_OPEN),
        "max_same_dir": int(cfg.get("live_max_same_dir") or LIVE_MAX_SAME_DIR),
    }


def should_skip_live_asset(asset: str) -> tuple[bool, str]:
    cls = asset_trade_class(asset)
    if cls == "weird":
        return True, "weird_asset"
    if cls == "shadow_only":
        return True, "shadow_only_asset"
    return False, ""


def publish_we_code(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Status + We Code Together receipts for Dr. Codex."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    pol = write_policy_hash(state_dir=root)
    cfg = load_config(state_dir=root)
    cfg.update(
        {
            "epoch_active": True,
            "usd_shadow_only": True,
            "live_cohort": COHORT_M7_BEST1,
            "live_max_open": LIVE_MAX_OPEN,
            "policy_hash": pol["policy_hash"],
            "receipt_id": RECEIPT,
        }
    )
    save_config(cfg, state_dir=root)
    usd = disarm_usd_for_shadow(state_dir=root)
    report = bootstrap_report(state_dir=root)
    ok_trade, why = policy_allows_trade(state_dir=root)

    for_codex = (
        f"r1667 CODED by Grok. policy_hash={pol['policy_hash']}. "
        f"Live cohort=minute7_best1 (one ticker — owner streak). "
        f"Shadow: minute7_best2 + minute5_best1. USD OFF ({usd.get('status')}). "
        f"Promote only after {PROMOTE_MIN_TICKETS} tickets / {PROMOTE_MIN_WINDOWS} windows "
        f"+ fee-net EV>0 + CI95 lower>0. "
        f"Modules: System/alice_fee_net_tournament.py — import bootstrap_report, "
        f"policy_allows_trade, record_shadow_window, fee_net_unit_pnl. "
        f"Do not fork pickers; extend power_max stack. Same up."
    )
    for_alice = (
        "Every 15-minute window I fire ONE best co-dir ticker on the clock "
        "(minute-7). I walk the ranked list if #1 is too expensive. "
        "I do not sit whole rounds empty. Fee-net EV still matters."
    )
    out = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "policy_hash": pol["policy_hash"],
        "policy_allows_paper": ok_trade,
        "policy_detail": why,
        "usd": usd,
        "config": cfg,
        "report": {
            "promote": (report.get("promote_gates") or {}).get("promote"),
            "cohorts": {
                k: {
                    "n": v.get("n"),
                    "wr": v.get("wr"),
                    "fee_net_ev": v.get("fee_net_ev"),
                    "fee_net_ci95_lower": v.get("fee_net_ci95_lower"),
                }
                for k, v in (report.get("cohorts") or {}).items()
            },
        },
        "for_codex": for_codex,
        "for_alice": for_alice,
        "owner_streak_note": (
            "Since last XRP loss: single-ticker path winning; locked as live minute7_best1."
        ),
    }
    (root / "alice_fee_net_tournament_status.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )

    # We Code Together channels
    coded = {
        "ts": out["ts"],
        "truth_label": "WE_CODE_TOGETHER_CODED_V1",
        "family": "alice_fee_net_tournament",
        "receipt_id": RECEIPT,
        "status": "coded",
        "module": "System/alice_fee_net_tournament.py",
        "for_codex": for_codex,
        "for_alice": for_alice,
        "policy_hash": pol["policy_hash"],
        "usd_status": usd.get("status"),
        "promote": (report.get("promote_gates") or {}).get("promote"),
        "files": [
            "System/alice_fee_net_tournament.py",
            "tests/test_alice_fee_net_tournament.py",
            "System/alice_power_max_stack.py",
            "System/swarm_sifta_paper_loop.py",
            "System/kalshi_usd_hand.py",
        ],
    }
    try:
        with (root / "we_code_together_coded.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(coded, sort_keys=True) + "\n")
    except OSError:
        pass
    try:
        with (root / "we_code_together_to_be_coded.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": out["ts"],
                        "title": "Fee-net shadow tournament LIVE (r1667)",
                        "status": "coded",
                        "receipt_id": RECEIPT,
                        "dedup_key": RECEIPT,
                        "note": for_codex,
                        "truth_label": "WE_CODE_TOGETHER_TO_BE_CODED_V1",
                        "from": "grok",
                        "to": "codex",
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    try:
        with (root / "ide_stigmergic_trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": out["ts"],
                        "event": "r1667_fee_net_tournament_coded",
                        "from": "grok",
                        "to": "codex",
                        "msg": for_codex,
                        "receipt_id": RECEIPT,
                        "policy_hash": pol["policy_hash"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    # owner lesson
    try:
        with (root / "owner_trade_lessons.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "truth_label": "OWNER_TRADE_LESSON_V1",
                        "receipt_id": RECEIPT,
                        "ts": out["ts"],
                        "stamp": out["stamp"],
                        "owner": "George",
                        "lesson": (
                            "r1667: live = minute7_best1 one ticker (owner likes streak). "
                            "Shadow pair + m5. Fee-net EV over WR. USD OFF. "
                            "Policy-hash interlock blocks stale processes."
                        ),
                        "verdict": "fee_net_tournament_coded",
                        "policy_hash": pol["policy_hash"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    return out


# ── r1672: minute-11 trend-down (point-in-time shadow context only) ──────────
# Hypothesis: board-wide downtrend visible around ~11:00 left may mark regime.
# Never retags past rows; never changes live picker; USD untouched.
M11_SHADOW_LOG = "alice_minute11_trend_shadow.jsonl"
M11_SEEN = "alice_minute11_trend_seen.json"
M11_MAJORS = ("BTC", "ETH", "SOL", "XRP")
# "minute-11" band: 10:00–12:00 left (600–720s) — capture once per window
M11_SECS_LO = 10 * 60
M11_SECS_HI = 12 * 60
RECEIPT_M11 = "r1672-minute11-trend-down-shadow-note"


def _window_id_from_ticker(ticker: str) -> str:
    t = str(ticker or "")
    parts = t.split("-")
    if len(parts) >= 2:
        return parts[1]
    return t or ""


def measure_major_alignment(
    assets: list[dict[str, Any]],
    *,
    majors: tuple[str, ...] = M11_MAJORS,
) -> dict[str, Any]:
    """Point-in-time consensus among BTC/ETH/SOL/XRP (no future data).

    Each asset row needs: asset, side (yes/no) or yes mid, optional secs.
    """
    by: dict[str, dict[str, Any]] = {}
    for row in assets:
        a = str(row.get("asset") or "").upper()
        if a not in majors:
            continue
        side = str(row.get("side") or "").lower()
        if side not in ("yes", "no"):
            try:
                y = float(row.get("yes") if row.get("yes") is not None else row.get("kalshi_yes"))
            except (TypeError, ValueError):
                continue
            side = "yes" if y >= 0.5 else "no"
        try:
            yes = float(row.get("yes") if row.get("yes") is not None else row.get("kalshi_yes") or 0.5)
        except (TypeError, ValueError):
            yes = 0.5 if side == "yes" else 0.5
        fav = max(yes, 1.0 - yes)
        by[a] = {
            "asset": a,
            "side": side,
            "label": "UP" if side == "yes" else "DOWN",
            "yes": round(yes, 4),
            "fav": round(fav, 4),
            "secs": row.get("secs") if row.get("secs") is not None else row.get("seconds_to_close"),
        }
    n_up = sum(1 for v in by.values() if v["side"] == "yes")
    n_dn = sum(1 for v in by.values() if v["side"] == "no")
    n = len(by)
    if n_dn > n_up:
        consensus = "DOWN"
        maj_n = n_dn
    elif n_up > n_dn:
        consensus = "UP"
        maj_n = n_up
    else:
        consensus = "SPLIT"
        maj_n = n_up
    # 3-of-4 / 4-of-4 among the four majors (missing names count as no vote)
    present = len(by)
    strength = f"{maj_n}_of_{present}" if present else "0_of_0"
    four = all(m in by for m in majors)
    of4 = None
    if four:
        of4 = f"{maj_n}_of_4"
    trend_down = consensus == "DOWN" and maj_n >= 3
    trend_up = consensus == "UP" and maj_n >= 3
    return {
        "majors_present": sorted(by.keys()),
        "n_present": present,
        "n_up": n_up,
        "n_down": n_dn,
        "consensus": consensus,
        "strength": strength,
        "of4": of4,
        "trend_down_hypothesis": bool(trend_down),
        "trend_up_hypothesis": bool(trend_up),
        "by_asset": by,
        "note": (
            "Point-in-time only. Hypothesis until holdout fee-net CI>0. "
            "No hindsight retag of settles."
        ),
    }


def maybe_record_minute11_trend(
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """If live board is in the minute-11 band, freeze one shadow row per window.

    Idempotent per window_id. Never places orders. Never rewrites history.
    """
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    live_path = root / "kalshi_15m_live.json"
    if not live_path.exists():
        return {"ok": False, "reason": "no_live_board"}
    try:
        data = json.loads(live_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "reason": f"live_read:{type(exc).__name__}:{exc}"}

    markets = [m for m in (data.get("markets") or []) if isinstance(m, dict)]
    # secs: prefer seconds_to_close; else close_ts - now
    rows: list[dict[str, Any]] = []
    secs_samples: list[int] = []
    window_id = ""
    for m in markets:
        a = str(m.get("asset") or "").upper()
        secs = m.get("seconds_to_close")
        if secs is None and m.get("close_ts"):
            try:
                secs = int(float(m["close_ts"]) - ts)
            except (TypeError, ValueError):
                secs = None
        try:
            secs_i = int(secs) if secs is not None else None
        except (TypeError, ValueError):
            secs_i = None
        if secs_i is not None:
            secs_samples.append(secs_i)
        yes = m.get("kalshi_yes")
        if yes is None:
            yes = m.get("yes_price")
        rows.append(
            {
                "asset": a,
                "yes": yes,
                "secs": secs_i,
                "ticker": m.get("kalshi_ticker") or m.get("ticker"),
            }
        )
        if not window_id and (m.get("kalshi_ticker") or m.get("ticker")):
            window_id = _window_id_from_ticker(str(m.get("kalshi_ticker") or m.get("ticker")))

    if not secs_samples:
        return {"ok": False, "reason": "no_secs"}
    # median secs across board
    secs_samples.sort()
    med = secs_samples[len(secs_samples) // 2]
    if med < M11_SECS_LO or med > M11_SECS_HI:
        return {
            "ok": True,
            "recorded": False,
            "reason": "outside_minute11_band",
            "secs_median": med,
            "need": f"{M11_SECS_LO}-{M11_SECS_HI}",
        }

    if not window_id:
        window_id = datetime.fromtimestamp(ts).strftime("%Y%m%d%H%M")

    seen_path = root / M11_SEEN
    seen: dict[str, Any] = {}
    if seen_path.exists():
        try:
            seen = json.loads(seen_path.read_text(encoding="utf-8"))
        except Exception:
            seen = {}
    already = set(seen.get("windows") or [])
    if window_id in already:
        return {
            "ok": True,
            "recorded": False,
            "reason": "already_recorded",
            "window_id": window_id,
            "secs_median": med,
        }

    align = measure_major_alignment(rows)
    row = {
        "truth_label": "ALICE_MINUTE11_TREND_SHADOW_V1",
        "event": "minute11_trend_context",
        "receipt_id": RECEIPT_M11,
        "window_id": window_id,
        "ts": ts,
        "stamp": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
        "secs_median": med,
        "secs_band": [M11_SECS_LO, M11_SECS_HI],
        "alignment": align,
        "hypothesis": "minute11_board_trend_may_mark_regime",
        "status": "hypothesis_only",
        "hindsight": False,
        "live_effect": "none",
        "usd_effect": "none",
    }
    _append_jsonl(root / M11_SHADOW_LOG, row)
    already.add(window_id)
    # keep last 200 window ids
    seen = {
        "windows": sorted(already)[-200:],
        "ts": ts,
        "last_window_id": window_id,
        "last_consensus": align.get("consensus"),
        "last_trend_down": align.get("trend_down_hypothesis"),
    }
    seen_path.write_text(json.dumps(seen, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "recorded": True,
        "window_id": window_id,
        "secs_median": med,
        "alignment": align,
        "path": str(root / M11_SHADOW_LOG),
    }


def minute11_shadow_summary(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Count m11 freeze rows by consensus (no join to future settles here)."""
    root = _state(state_dir)
    path = root / M11_SHADOW_LOG
    counts: dict[str, int] = {}
    n = 0
    n_down3 = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("event") != "minute11_trend_context":
                continue
            n += 1
            al = r.get("alignment") or {}
            c = str(al.get("consensus") or "?")
            counts[c] = counts.get(c, 0) + 1
            if al.get("trend_down_hypothesis"):
                n_down3 += 1
    return {
        "receipt_id": RECEIPT_M11,
        "n_snapshots": n,
        "consensus_counts": counts,
        "n_trend_down_3plus": n_down3,
        "note": "Join to settles is a later holdout study; this summary is counts only.",
    }


__all__ = [
    "TRUTH",
    "RECEIPT",
    "COHORT_M7_BEST1",
    "COHORT_M7_BEST2",
    "COHORT_M5_BEST1",
    "COHORT_LEGACY",
    "WEIRD_ASSETS",
    "normalize_cohort",
    "fee_net_unit_pnl",
    "estimate_taker_fee",
    "compute_policy_hash",
    "write_policy_hash",
    "running_policy_hash",
    "policy_allows_trade",
    "disarm_usd_for_shadow",
    "pair_decision",
    "record_shadow_window",
    "settle_shadow_ticket",
    "bootstrap_report",
    "tag_ticket_cohort",
    "live_caps",
    "should_skip_live_asset",
    "publish_we_code",
    "load_config",
    "measure_major_alignment",
    "maybe_record_minute11_trend",
    "minute11_shadow_summary",
    "RECEIPT_M11",
    "M11_MAJORS",
    "asset_trade_class",
]
