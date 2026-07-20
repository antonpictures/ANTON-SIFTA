#!/usr/bin/env python3
"""Alice's 15m paper learning brain (GAME_STGM only — no real $).

The paper loop used to copy the Kalshi crowd favorite every window. No choice,
so nothing to learn. This organ gives Alice a real decision per asset:

    follow_crowd — bet the mid favorite (UP if kalshi_yes >= 0.5)
    fade_crowd   — bet against the mid favorite
    sit_out      — she learned this asset is bleeding her; skip the window

Each (asset, strategy) is a pheromone trail. Settled wins reinforce the trail
that made the pick; losses decay it; every update all trails evaporate toward
neutral (1.0) so no lesson becomes a permanent cage. Early windows explore
(deliberate mistakes are the tuition — same stance as swarm_action_prediction);
exploration anneals as her rolling win rate stabilizes. That is the body
stabilizing, and the monitor shows it so the owner can watch.

Truth: decisions learn on PAPER_UNIT; the loop may attach a separately bounded,
signed body-STGM micro-settlement. Not Kalshi USD.
Model:  .sifta_state/alice_15m_learner.json
Ledger: .sifta_state/alice_15m_learner.jsonl (append-only learn events)
"""

from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "SIFTA_PAPER_LEARNER_V1"
MODEL_NAME = "alice_15m_learner.json"
LEARN_LEDGER = "alice_15m_learner.jsonl"
DEDUPE_VERSION = "unique_ticker_v1"

STRATEGIES = ("follow_crowd", "fade_crowd")

# pheromone dynamics
BASE_STRENGTH = 1.0
MIN_STRENGTH = 0.05
MAX_STRENGTH = 5.0
LEARN_RATE = 0.30
EVAPORATION = 0.98  # every settle, strengths regress 2% toward neutral
SOFTMAX_TEMP = 0.45

# exploration schedule: start curious, calm down as the body stabilizes
EPSILON_START = 0.35
EPSILON_FLOOR = 0.05
ANNEAL_UPDATES = 60  # roughly 60 settled bets to reach the floor

# sit-out: both trails weak AND the asset has cost her real paper units
SIT_OUT_STRENGTH = 0.45
SIT_OUT_PNL = -5.0
# hard sit if an asset has been a paper black hole (overnight: DOGE ~-25)
SIT_OUT_HARD_PNL = -8.0  # DOGE/HYPE-class overnight bleeders
# overnight data: fade_crowd ~27% WR / -51u vs follow ~74% / +25u — gate fade hard
FADE_MIN_STRENGTH = 1.8
FADE_MIN_TRAIL_PNL = 1.0  # fade trail itself must be profitable
FOLLOW_EXPLORE_BIAS = 0.85  # when exploring, still prefer follow (mistakes, not suicide)

RECENT_WINDOW = 20


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _fresh_trail() -> dict[str, Any]:
    return {"strength": BASE_STRENGTH, "wins": 0, "losses": 0, "pnl": 0.0}


def _fresh_model() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "token": "PAPER_UNIT",
        "assets": {},
        "recent": [],
        "n_updates": 0,
        "n_explore": 0,
        "stability": "learning",
        "seen_tickers": [],
        "note": "pheromone trails per (asset, strategy); paper only",
    }


def load_model(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    path = _state_dir(state_dir) / MODEL_NAME
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("assets"), dict):
                return raw
        except Exception:
            pass
    return _fresh_model()


def save_model(model: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    model = dict(model)
    model["truth_label"] = TRUTH_LABEL
    model["ts"] = time.time()
    (root / MODEL_NAME).write_text(
        json.dumps(model, indent=2, sort_keys=True), encoding="utf-8"
    )


def _append_learn_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with (root / LEARN_LEDGER).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _asset_trails(model: dict[str, Any], asset: str) -> dict[str, Any]:
    assets = model.setdefault("assets", {})
    trails = assets.setdefault(str(asset or "?"), {})
    for s in STRATEGIES:
        if not isinstance(trails.get(s), dict):
            trails[s] = _fresh_trail()
    return trails


def _rolling_win_rate(model: dict[str, Any]) -> tuple[float, int]:
    recent = [int(x) for x in (model.get("recent") or [])][-RECENT_WINDOW:]
    n = len(recent)
    return ((sum(recent) / n) if n else 0.0, n)


def _stability(model: dict[str, Any]) -> str:
    wr, n = _rolling_win_rate(model)
    if n < 10:
        return "learning"
    if n >= RECENT_WINDOW and wr >= 0.55:
        return "stable"
    if wr >= 0.50:
        return "stabilizing"
    return "wobbling"


def epsilon(model: dict[str, Any]) -> float:
    n = int(model.get("n_updates") or 0)
    eps = max(EPSILON_FLOOR, EPSILON_START * (1.0 - n / float(ANNEAL_UPDATES)))
    if _stability(model) == "stable":
        eps = EPSILON_FLOOR
    return round(eps, 4)


def choose(
    asset: str,
    kalshi_yes: float,
    *,
    model: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
    rng: Optional[random.Random] = None,
) -> dict[str, Any]:
    """Pick a side for one 15m clock from the pheromone trails.

    Returns side/label/strategy plus why — the why is what the monitor shows.
    Does not mutate the model file (learning happens only at settle).
    """
    owns_model = model is None
    if owns_model:
        model = load_model(state_dir)
    rng = rng or random
    ky = min(0.99, max(0.01, float(kalshi_yes)))
    fav_side = "yes" if ky >= 0.5 else "no"
    other_side = "no" if fav_side == "yes" else "yes"

    trails = _asset_trails(model, asset)
    s_follow = float(trails["follow_crowd"]["strength"])
    s_fade = float(trails["fade_crowd"]["strength"])
    follow_pnl = float(trails["follow_crowd"].get("pnl") or 0.0)
    fade_pnl = float(trails["fade_crowd"].get("pnl") or 0.0)
    asset_pnl = follow_pnl + fade_pnl

    # hard sit: chronic paper bleeders (overnight DOGE-class)
    if asset_pnl <= SIT_OUT_HARD_PNL:
        return {
            "action": "sit_out",
            "asset": asset,
            "reason": "hard_sit_asset_pnl",
            "s_follow": round(s_follow, 3),
            "s_fade": round(s_fade, 3),
            "asset_pnl": round(asset_pnl, 2),
            "epsilon": epsilon(model),
        }

    if max(s_follow, s_fade) < SIT_OUT_STRENGTH and asset_pnl <= SIT_OUT_PNL:
        return {
            "action": "sit_out",
            "asset": asset,
            "reason": "both_trails_weak",
            "s_follow": round(s_follow, 3),
            "s_fade": round(s_fade, 3),
            "asset_pnl": round(asset_pnl, 2),
            "epsilon": epsilon(model),
        }

    # fade is gated: only if trail is strong AND already profitable
    fade_allowed = s_fade >= FADE_MIN_STRENGTH and fade_pnl >= FADE_MIN_TRAIL_PNL

    # softmax preference (fade mass collapsed if not allowed)
    zf = math.exp(s_follow / SOFTMAX_TEMP)
    zd = math.exp(s_fade / SOFTMAX_TEMP) if fade_allowed else 0.0
    p_follow = zf / (zf + zd) if (zf + zd) > 0 else 1.0

    eps = epsilon(model)
    explored = rng.random() < eps
    if explored:
        # deliberate mistakes still mostly follow — overnight fade exploration was catastrophic
        if fade_allowed and rng.random() > FOLLOW_EXPLORE_BIAS:
            strategy = "fade_crowd"
        else:
            strategy = "follow_crowd"
    else:
        strategy = "follow_crowd" if rng.random() < p_follow else "fade_crowd"
        if strategy == "fade_crowd" and not fade_allowed:
            strategy = "follow_crowd"

    side = fav_side if strategy == "follow_crowd" else other_side
    return {
        "action": "bet",
        "asset": asset,
        "side": side,
        "label": "UP" if side == "yes" else "DOWN",
        "strategy": strategy,
        "explored": explored,
        "p_follow": round(p_follow, 3),
        "epsilon": eps,
        "s_follow": round(s_follow, 3),
        "s_fade": round(s_fade, 3),
        "fade_allowed": fade_allowed,
        "asset_pnl": round(asset_pnl, 2),
        "stability": _stability(model),
    }


def _apply_lesson(
    model: dict[str, Any],
    *,
    asset: str,
    strategy: str,
    win: bool,
    pnl: float,
    explored: bool,
) -> dict[str, Any]:
    """Pure-in-memory trail update shared by live learning and canonical replay."""
    strategy = strategy if strategy in STRATEGIES else "follow_crowd"
    trails = _asset_trails(model, asset)
    trail = trails[strategy]

    reward = min(2.0, max(-1.0, float(pnl)))
    before = float(trail["strength"])
    after = before + LEARN_RATE * reward
    trail["strength"] = round(min(MAX_STRENGTH, max(MIN_STRENGTH, after)), 4)
    trail["wins"] = int(trail.get("wins") or 0) + (1 if win else 0)
    trail["losses"] = int(trail.get("losses") or 0) + (0 if win else 1)
    trail["pnl"] = round(float(trail.get("pnl") or 0.0) + float(pnl), 4)

    # evaporation: every trail on every asset drifts back toward neutral
    for a_trails in (model.get("assets") or {}).values():
        for s in STRATEGIES:
            t = a_trails.get(s)
            if isinstance(t, dict):
                s_now = float(t.get("strength") or BASE_STRENGTH)
                t["strength"] = round(
                    BASE_STRENGTH + (s_now - BASE_STRENGTH) * EVAPORATION, 4
                )

    recent = [int(x) for x in (model.get("recent") or [])]
    recent.append(1 if win else 0)
    model["recent"] = recent[-(RECENT_WINDOW * 3):]
    model["n_updates"] = int(model.get("n_updates") or 0) + 1
    if explored:
        model["n_explore"] = int(model.get("n_explore") or 0) + 1
    model["stability"] = _stability(model)
    return {
        "strategy": strategy,
        "strength_before": round(before, 4),
        "strength_after": trail["strength"],
    }


def learn(
    asset: str,
    strategy: str,
    win: bool,
    pnl: float,
    *,
    explored: bool = False,
    ticker: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Feed one unique settled outcome back into the trails."""
    model = load_model(state_dir)
    ticker_s = str(ticker or "").strip()
    seen = {str(value) for value in (model.get("seen_tickers") or [])}
    if ticker_s and ticker_s in seen:
        row = {
            "truth_label": TRUTH_LABEL,
            "event": "duplicate_ticker_ignored",
            "ts": time.time(),
            "asset": asset,
            "ticker": ticker_s,
            "n_updates": int(model.get("n_updates") or 0),
        }
        _append_learn_row(row, state_dir=state_dir)
        return row

    applied = _apply_lesson(
        model,
        asset=asset,
        strategy=strategy,
        win=win,
        pnl=pnl,
        explored=explored,
    )
    if ticker_s:
        seen.add(ticker_s)
        model["seen_tickers"] = sorted(seen)
    save_model(model, state_dir=state_dir)

    row = {
        "truth_label": TRUTH_LABEL,
        "event": "learn",
        "ts": time.time(),
        "asset": asset,
        "strategy": applied["strategy"],
        "win": bool(win),
        "pnl": round(float(pnl), 4),
        "explored": bool(explored),
        "ticker": ticker,
        "strength_before": applied["strength_before"],
        "strength_after": applied["strength_after"],
        "epsilon": epsilon(model),
        "stability": model["stability"],
        "n_updates": model["n_updates"],
    }
    _append_learn_row(row, state_dir=state_dir)
    return row


def rebuild_from_unique_settlements(
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Replay the append-only settle ledger once per ticker into a clean model."""
    root = _state_dir(state_dir)
    path = root / "alice_15m_settled.jsonl"
    raw_rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                raw_rows.append(row)
    except Exception:
        pass

    by_ticker: dict[str, dict[str, Any]] = {}
    no_ticker: list[dict[str, Any]] = []
    for row in raw_rows:
        ticker = str(row.get("ticker") or "").strip()
        if ticker:
            by_ticker[ticker] = row
        else:
            no_ticker.append(row)
    rows = sorted(
        [*no_ticker, *by_ticker.values()],
        key=lambda row: float(row.get("ts") or 0.0),
    )
    model = _fresh_model()
    seen: set[str] = set()
    for row in rows:
        win = row.get("win")
        if win is None:
            side = str(row.get("owner_side") or row.get("side") or "")
            result = str(row.get("result") or "")
            if side and result in ("yes", "no"):
                win = side == result
        if win is None:
            continue
        _apply_lesson(
            model,
            asset=str(row.get("asset") or "?"),
            strategy=str(row.get("strategy") or "follow_crowd"),
            win=bool(win),
            pnl=float(row.get("pnl") or 0.0),
            explored=bool(row.get("explored")),
        )
        ticker = str(row.get("ticker") or "").strip()
        if ticker:
            seen.add(ticker)
    model["seen_tickers"] = sorted(seen)
    model["dedupe_version"] = DEDUPE_VERSION
    model["rebuild_raw_rows"] = len(raw_rows)
    model["rebuild_unique_rows"] = len(rows)
    model["rebuild_duplicates_ignored"] = max(0, len(raw_rows) - len(rows))
    model["rebuilt_ts"] = time.time()

    root.mkdir(parents=True, exist_ok=True)
    current = root / MODEL_NAME
    backup = root / "alice_15m_learner_pre_dedupe.json"
    if current.exists() and not backup.exists():
        try:
            backup.write_text(current.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    save_model(model, state_dir=root)
    receipt = {
        "truth_label": TRUTH_LABEL,
        "event": "canonical_unique_ticker_rebuild",
        "ts": time.time(),
        "dedupe_version": DEDUPE_VERSION,
        "raw_rows": len(raw_rows),
        "unique_rows": len(rows),
        "duplicates_ignored": max(0, len(raw_rows) - len(rows)),
        "n_updates": int(model.get("n_updates") or 0),
        "note": "analytics/model repair only; no wallet or STGM mutation",
    }
    _append_learn_row(receipt, state_dir=root)
    return receipt


def learn_status(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Summary for the app UI and the owner monitor."""
    model = load_model(state_dir)
    wr, n = _rolling_win_rate(model)
    per_asset: list[dict[str, Any]] = []
    for asset, trails in sorted((model.get("assets") or {}).items()):
        tf = trails.get("follow_crowd") or _fresh_trail()
        td = trails.get("fade_crowd") or _fresh_trail()
        lean = "follow" if float(tf["strength"]) >= float(td["strength"]) else "fade"
        per_asset.append(
            {
                "asset": asset,
                "lean": lean,
                "s_follow": round(float(tf["strength"]), 2),
                "s_fade": round(float(td["strength"]), 2),
                "wins": int(tf.get("wins") or 0) + int(td.get("wins") or 0),
                "losses": int(tf.get("losses") or 0) + int(td.get("losses") or 0),
                "pnl": round(float(tf.get("pnl") or 0.0) + float(td.get("pnl") or 0.0), 2),
            }
        )
    return {
        "truth_label": TRUTH_LABEL,
        "stability": model.get("stability") or _stability(model),
        "epsilon": epsilon(model),
        "rolling_win_rate": round(wr, 3),
        "rolling_n": n,
        "n_updates": int(model.get("n_updates") or 0),
        "n_explore": int(model.get("n_explore") or 0),
        "assets": per_asset,
    }


__all__ = [
    "TRUTH_LABEL",
    "STRATEGIES",
    "load_model",
    "save_model",
    "choose",
    "learn",
    "learn_status",
    "rebuild_from_unique_settlements",
    "epsilon",
]
