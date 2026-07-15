#!/usr/bin/env python3
"""swarm_sifta_market.py — SIFTA prediction market engine (Kalshi-style sandbox).

Not Kalshi.com. Not real USD. Not body STGM spend.

Law (R1626):
  - Markets: YES / NO shares funded by GAME_STGM stakes
  - Field: evaporating pheromone on YES and NO (swarm heat)
  - Swarm: many unique swimmers auto-deposit + vote with stake
  - Signatures: deterministic Ed25519 ballot identity + rolling market digest
  - Settlement: owner resolves; winners share the losing side's pot

Truth label: SIFTA_PREDICTION_MARKET_V3
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
import uuid
from dataclasses import replace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from System.swimmer_pheromone_identity import SwimmerIdentity, verify_trace

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "sifta_market_receipts.jsonl"
_SNAPSHOT = "sifta_market_state.json"

TRUTH_LABEL = "SIFTA_PREDICTION_MARKET_V3"
TOKEN = "GAME_STGM"
Side = Literal["yes", "no"]

OWNER_ID = "owner:george"
OWNER_DISPLAY = "GeorgeAnton"  # Kalshi social handle (owner glass 2026-07-11)
SWARM_PREFIX = "swarm"
GENESIS_OWNER = 10.0
GENESIS_SWIMMER = 25.0
SWARM_SIZE = 32
MIN_STAKE = 0.5
MAX_STAKE = 10.0

# Cute swarm display names (not real Kalshi users — sandboxed hive creatures)
_SWARM_NAME_POOL = (
    "field.wren",
    "stigmergic.bee",
    "pheromone.fox",
    "ballot.otter",
    "hive.moth",
    "ledger.lynx",
    "digest.crane",
    "vote.sparrow",
    "pool.badger",
    "trace.heron",
    "yes.newt",
    "no.kestrel",
    "market.vole",
    "swarm.ibis",
    "crypto.tern",
    "receipt.elk",
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _append(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        with (root / _LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _parse_close_ts(close_time: str) -> float:
    """Parse Kalshi ISO close_time → unix seconds (best-effort)."""
    s = str(close_time or "").strip()
    if not s:
        return 0.0
    try:
        from datetime import datetime, timezone

        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return 0.0


# Stigmergic swarm learning (GAME_STGM sandbox — not real Kalshi PnL)
_LEARN_FILE = "sifta_market_learn.json"
_DEFAULT_LEARN = {
    "kalshi_weight": 0.25,  # how much public mid pulls swarm P(yes)
    "field_weight": 0.50,
    "bias_weight": 0.20,
    "noise_weight": 0.05,
    "prefer_15m": 0.75,  # probability pick ending-soon 15m over random
    "n_settled": 0,
    "n_local_correct": 0,
    "n_kalshi_correct": 0,
    "n_swarm_side_correct": 0,
    "last_lesson": "",
}


def _load_learn(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    root = _state_dir(state_dir)
    path = root / _LEARN_FILE
    out = dict(_DEFAULT_LEARN)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in out:
                        out[k] = v
        except Exception:
            pass
    return out


def _save_learn(learn: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / _LEARN_FILE).write_text(
            json.dumps(learn, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception:
        pass



def seed_markets() -> list[dict[str, Any]]:
    """Demo markets people understand (not live Kalshi API)."""
    return [
        {
            "id": "m-btc-up",
            "title": "BTC ends the day green?",
            "subtitle": "Demo market — resolve YES if you call it up",
            "category": "Crypto",
            "bias_yes": 0.52,
        },
        {
            "id": "m-alice-land",
            "title": "Alice Browser lands next open URL cleanly?",
            "subtitle": "Body market — settle from your glass, not Kalshi",
            "category": "Alice body",
            "bias_yes": 0.45,
        },
        {
            "id": "m-rain",
            "title": "Rain in Brawley this week?",
            "subtitle": "Local life demo market",
            "category": "Climate",
            "bias_yes": 0.35,
        },
        {
            "id": "m-fed",
            "title": "Next Fed move is a cut?",
            "subtitle": "Macro demo — owner resolves",
            "category": "Economics",
            "bias_yes": 0.48,
        },
        {
            "id": "m-swarm",
            "title": "Swarm majority beats owner pick this match?",
            "subtitle": "Meta market on the hive itself",
            "category": "SIFTA",
            "bias_yes": 0.50,
        },
        {
            "id": "m-btc-hour",
            "title": "BTC above $63,700 by next hour?",
            "subtitle": "Glass dirt: owner traded similar strikes on Kalshi (wins + losses)",
            "category": "Crypto",
            "bias_yes": 0.48,
        },
        {
            "id": "m-btc-15m",
            "title": "BTC 15-min target hits?",
            "subtitle": "Demo short-horizon — resolve yourself",
            "category": "Crypto",
            "bias_yes": 0.50,
        },
        # Owner glass paste 2026-07-11 (Kalshi titles George pasted by hand —
        # the "manual paste, no scrape" lane from the R1626 contract). bias_yes
        # mirrors the implied odds on his glass at paste time; George resolves.
        {
            "id": "m-wc-eng-nor",
            "title": "World Cup QF: England advances past Norway?",
            "subtitle": "Owner glass paste 2026-07-11 · was 89% in OT — George resolves",
            "category": "Sports",
            "bias_yes": 0.89,
        },
        {
            "id": "m-wc-arg-sui",
            "title": "World Cup QF: Argentina advances past Switzerland?",
            "subtitle": "Owner glass paste 2026-07-11 · was 74% — George resolves",
            "category": "Sports",
            "bias_yes": 0.74,
        },
        {
            "id": "m-wc-france",
            "title": "FIFA World Cup winner: France?",
            "subtitle": "Owner glass paste 2026-07-11 · was 38% — George resolves",
            "category": "Sports",
            "bias_yes": 0.38,
        },
        {
            "id": "m-mma-holloway",
            "title": "McGregor vs Holloway 2: Holloway wins?",
            "subtitle": "Owner glass paste 2026-07-11 · was 72% — George resolves",
            "category": "Sports",
            "bias_yes": 0.72,
        },
        {
            "id": "m-btc-63900",
            "title": "BTC at or above $63,900 today 8pm EDT?",
            "subtitle": "Owner glass paste 2026-07-11 · was ~55% — George resolves",
            "category": "Crypto",
            "bias_yes": 0.55,
        },
        {
            "id": "m-btc-july-67500",
            "title": "BTC above $67,500 at any point in July?",
            "subtitle": "Owner glass paste 2026-07-11 · was 47% — George resolves",
            "category": "Crypto",
            "bias_yes": 0.47,
        },
        {
            "id": "m-eth-1790",
            "title": "ETH at or above $1,790 today 8pm EDT?",
            "subtitle": "Owner glass paste 2026-07-11 · was 85% — George resolves",
            "category": "Crypto",
            "bias_yes": 0.85,
        },
        {
            "id": "m-maine-jackson",
            "title": "Maine Dem Senate nominee: Troy Jackson?",
            "subtitle": "Owner glass paste 2026-07-11 · was 67% — George resolves",
            "category": "Elections",
            "bias_yes": 0.67,
        },
        {
            "id": "m-newsom-2028",
            "title": "2028 Democratic presidential nominee: Gavin Newsom?",
            "subtitle": "Owner glass paste 2026-07-11 · was 20% — George resolves",
            "category": "Elections",
            "bias_yes": 0.20,
        },
    ]


@dataclass
class Market:
    id: str
    title: str
    subtitle: str = ""
    category: str = "Demo"
    yes_pool: float = 10.0
    no_pool: float = 10.0
    field_yes: float = 1.0
    field_no: float = 1.0
    status: str = "open"  # open | resolved
    outcome: Optional[str] = None  # yes | no
    bias_yes: float = 0.5
    trades: int = 0
    ballot_digest: str = "0" * 16
    verified_ballots: int = 0
    rejected_ballots: int = 0
    positions: dict[str, dict[str, float]] = field(default_factory=dict)
    # positions[agent_id] = {"yes": shares, "no": shares, "cost": total_staked}
    # Optional Kalshi public feed overlay (read-only display — not real trading)
    kalshi_ticker: str = ""
    kalshi_yes: Optional[float] = None
    kalshi_volume_24h: float = 0.0
    kalshi_synced_ts: float = 0.0
    # Kalshi Crypto-style nav (same buckets as kalshi.com sidebar)
    nav_section: str = ""
    timeframe: str = ""
    asset: str = ""
    product: str = "Predictions"
    close_time: str = ""  # ISO from Kalshi public feed (for ending-soon watch)
    close_ts: float = 0.0
    target_price: float = 0.0  # Kalshi TO BEAT / floor_strike when present
    yes_bid: float = 0.0
    yes_ask: float = 0.0

    def total_pool(self) -> float:
        return max(1e-9, self.yes_pool + self.no_pool)

    def yes_price(self) -> float:
        """Implied probability from pools (simple LMSR-ish share of pot)."""
        return self.yes_pool / self.total_pool()

    def no_price(self) -> float:
        return self.no_pool / self.total_pool()

    def field_yes_share(self) -> float:
        t = self.field_yes + self.field_no
        return self.field_yes / t if t > 1e-9 else 0.5

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "category": self.category,
            "yes_pool": round(self.yes_pool, 4),
            "no_pool": round(self.no_pool, 4),
            "yes_price": round(self.yes_price(), 4),
            "no_price": round(self.no_price(), 4),
            "field_yes": round(self.field_yes, 4),
            "field_no": round(self.field_no, 4),
            "field_yes_share": round(self.field_yes_share(), 4),
            "status": self.status,
            "outcome": self.outcome,
            "trades": self.trades,
            "ballot_digest": self.ballot_digest,
            "verified_ballots": self.verified_ballots,
            "rejected_ballots": self.rejected_ballots,
            "bias_yes": self.bias_yes,
            # getattr: survives hot-reload when Alice keeps an older Market class in memory
            "kalshi_ticker": str(getattr(self, "kalshi_ticker", "") or ""),
            "kalshi_yes": (
                None
                if getattr(self, "kalshi_yes", None) is None
                else round(float(self.kalshi_yes), 4)  # type: ignore[arg-type]
            ),
            "kalshi_volume_24h": round(float(getattr(self, "kalshi_volume_24h", 0.0) or 0.0), 2),
            "kalshi_synced_ts": float(getattr(self, "kalshi_synced_ts", 0.0) or 0.0),
            "nav_section": str(getattr(self, "nav_section", "") or ""),
            "timeframe": str(getattr(self, "timeframe", "") or ""),
            "asset": str(getattr(self, "asset", "") or ""),
            "product": str(getattr(self, "product", "Predictions") or "Predictions"),
            "close_time": str(getattr(self, "close_time", "") or ""),
            "close_ts": float(getattr(self, "close_ts", 0.0) or 0.0),
            "target_price": float(getattr(self, "target_price", 0.0) or 0.0),
            "yes_bid": float(getattr(self, "yes_bid", 0.0) or 0.0),
            "yes_ask": float(getattr(self, "yes_ask", 0.0) or 0.0),
            "up_cents": int(round(self.yes_price() * 100)),
            "kalshi_up_cents": (
                None
                if getattr(self, "kalshi_yes", None) is None
                else int(round(float(self.kalshi_yes) * 100))
            ),
            "kalshi_down_cents": (
                None
                if getattr(self, "kalshi_yes", None) is None
                else int(round((1.0 - float(self.kalshi_yes)) * 100))
            ),
            "seconds_to_close": (
                max(0, int(float(getattr(self, "close_ts", 0.0) or 0.0) - time.time()))
                if float(getattr(self, "close_ts", 0.0) or 0.0) > 0
                else None
            ),
        }

    def ensure_kalshi_fields(self) -> None:
        """Patch older Market instances created before kalshi_* fields existed."""
        if not hasattr(self, "kalshi_ticker"):
            self.kalshi_ticker = ""
        if not hasattr(self, "kalshi_yes"):
            self.kalshi_yes = None
        if not hasattr(self, "kalshi_volume_24h"):
            self.kalshi_volume_24h = 0.0
        if not hasattr(self, "kalshi_synced_ts"):
            self.kalshi_synced_ts = 0.0
        if not hasattr(self, "nav_section"):
            self.nav_section = ""
        if not hasattr(self, "timeframe"):
            self.timeframe = ""
        if not hasattr(self, "asset"):
            self.asset = ""
        if not hasattr(self, "product"):
            self.product = "Predictions"
        if not hasattr(self, "close_time"):
            self.close_time = ""
        if not hasattr(self, "close_ts"):
            self.close_ts = 0.0


class SiftaMarketEngine:
    """Headless prediction market + stigmergic swarm."""

    def __init__(
        self,
        *,
        seed: int = 1626,
        swarm_size: int = SWARM_SIZE,
        state_dir: Optional[Path | str] = None,
    ) -> None:
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.state_dir = state_dir
        self.swarm_size = max(8, min(64, int(swarm_size)))
        self.tick = 0
        self.balances: dict[str, float] = {OWNER_ID: GENESIS_OWNER}
        self.identities: dict[str, SwimmerIdentity] = {
            OWNER_ID: SwimmerIdentity(f"sifta-market:{self.seed}:{OWNER_ID}")
        }
        self.display_names: dict[str, str] = {OWNER_ID: OWNER_DISPLAY}
        # Kalshi SOCIAL-style stats (Profit / Volume / Predictions) — GAME_STGM units
        self.volume: dict[str, float] = {OWNER_ID: 0.0}
        self.realized_pnl: dict[str, float] = {OWNER_ID: 0.0}
        self.predictions: dict[str, int] = {OWNER_ID: 0}
        self.swimmer_ids: list[str] = []
        for i in range(self.swarm_size):
            uid = hashlib.sha256(
                f"sifta-market:{self.seed}:{i}".encode("ascii")
            ).hexdigest()[:16]
            sid = f"{SWARM_PREFIX}:{uid}"
            self.swimmer_ids.append(sid)
            self.balances[sid] = GENESIS_SWIMMER
            self.identities[sid] = SwimmerIdentity(f"sifta-market:{self.seed}:{sid}")
            name = _SWARM_NAME_POOL[i % len(_SWARM_NAME_POOL)]
            if i >= len(_SWARM_NAME_POOL):
                name = f"{name}{i}"
            self.display_names[sid] = name
            self.volume[sid] = 0.0
            self.realized_pnl[sid] = 0.0
            self.predictions[sid] = 0
        self.history: list[dict[str, Any]] = []
        self.last_event: dict[str, Any] = {}
        self.learn = _load_learn(self.state_dir)
        self.last_lesson: str = str(self.learn.get("last_lesson") or "")
        self.markets: dict[str, Market] = {}
        for raw in seed_markets():
            bias_yes = _clamp(float(raw.get("bias_yes", 0.5)), 0.05, 0.95)
            seed_liquidity = 20.0
            m = Market(
                id=raw["id"],
                title=raw["title"],
                subtitle=raw.get("subtitle", ""),
                category=raw.get("category", "Demo"),
                bias_yes=bias_yes,
                yes_pool=seed_liquidity * bias_yes,
                no_pool=seed_liquidity * (1.0 - bias_yes),
                field_yes=0.5 + 2.0 * bias_yes,
                field_no=0.5 + 2.0 * (1.0 - bias_yes),
            )
            self.markets[m.id] = m
        # Closed trade log for Portfolio HISTORY (Kalshi POSITIONS/HISTORY dirt)
        _append(
            {
                "truth_label": TRUTH_LABEL,
                "event": "engine_boot",
                "ts": time.time(),
                "seed": self.seed,
                "swarm_size": self.swarm_size,
                "token": TOKEN,
                "owner_display": OWNER_DISPLAY,
                "dirt": (
                    "Kalshi SOCIAL + Portfolio HISTORY glass 2026-07-11 (owner paste, no scrape). "
                    "GeorgeAnton: mixed BTC prediction wins/losses (e.g. +$7.49, +$2.44, -$4.58, -$14.99); "
                    "perps portfolio ~$37; cash small. SIFTA mirrors structure only in GAME_STGM."
                ),
                "note": "sandbox GAME_STGM — not Kalshi USD, not body wallet spend",
            },
            state_dir=self.state_dir,
        )

    def owner_balance(self) -> float:
        return float(self.balances.get(OWNER_ID, 0.0))

    def list_markets(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in self.markets.values():
            if hasattr(m, "ensure_kalshi_fields"):
                try:
                    m.ensure_kalshi_fields()
                except Exception:
                    pass
            else:
                for k, v in (
                    ("kalshi_ticker", ""),
                    ("kalshi_yes", None),
                    ("kalshi_volume_24h", 0.0),
                    ("kalshi_synced_ts", 0.0),
                ):
                    if not hasattr(m, k):
                        setattr(m, k, v)
            if hasattr(m, "to_row"):
                try:
                    out.append(m.to_row())
                    continue
                except Exception:
                    pass
            # minimal fallback row if instance is from a half-reloaded class
            yp = 0.5
            try:
                yp = float(m.yes_price())  # type: ignore[operator]
            except Exception:
                pass
            out.append(
                {
                    "id": getattr(m, "id", "?"),
                    "title": getattr(m, "title", "?"),
                    "subtitle": getattr(m, "subtitle", ""),
                    "category": getattr(m, "category", "Demo"),
                    "yes_pool": float(getattr(m, "yes_pool", 0) or 0),
                    "no_pool": float(getattr(m, "no_pool", 0) or 0),
                    "yes_price": yp,
                    "no_price": 1.0 - yp,
                    "field_yes": float(getattr(m, "field_yes", 1) or 1),
                    "field_no": float(getattr(m, "field_no", 1) or 1),
                    "field_yes_share": 0.5,
                    "status": getattr(m, "status", "open"),
                    "outcome": getattr(m, "outcome", None),
                    "trades": int(getattr(m, "trades", 0) or 0),
                    "ballot_digest": str(getattr(m, "ballot_digest", "") or ""),
                    "verified_ballots": int(getattr(m, "verified_ballots", 0) or 0),
                    "rejected_ballots": int(getattr(m, "rejected_ballots", 0) or 0),
                    "bias_yes": float(getattr(m, "bias_yes", 0.5) or 0.5),
                    "kalshi_ticker": str(getattr(m, "kalshi_ticker", "") or ""),
                    "kalshi_yes": getattr(m, "kalshi_yes", None),
                    "kalshi_volume_24h": float(getattr(m, "kalshi_volume_24h", 0) or 0),
                    "kalshi_synced_ts": float(getattr(m, "kalshi_synced_ts", 0) or 0),
                }
            )
        return out

    @staticmethod
    def _pools_for_yes_price(yes: float, pot: float = 40.0) -> tuple[float, float]:
        y = _clamp(float(yes), 0.02, 0.98)
        return round(pot * y, 4), round(pot * (1.0 - y), 4)

    def sync_kalshi_public(
        self,
        *,
        limit: int = 80,
        min_volume: float = 30.0,
        replace: bool = True,
    ) -> dict[str, Any]:
        """Pull Kalshi public open markets into the board (read-only feed).

        GAME_STGM trading remains sandbox. Kalshi odds are stored on each market
        and used to seed local pools so the board opens near live prices; swarm
        can still drift local price after that.
        Categories mirror Kalshi Crypto glass: timeframe + asset nav.
        """
        try:
            from System.swarm_kalshi_public_feed import classify_market, fetch_open_markets
        except Exception as exc:
            return {"ok": False, "reason": f"import_feed:{type(exc).__name__}: {exc}"}

        feed = fetch_open_markets(limit=limit, min_volume=min_volume, pages=4)
        rows = feed.get("markets") or []
        if not rows:
            return {
                "ok": False,
                "reason": "no_markets",
                "errors": feed.get("errors") or [],
                "feed": feed,
            }

        if replace:
            # keep resolved history rows; replace open board with live feed
            self.markets = {
                mid: m for mid, m in self.markets.items() if m.status == "resolved"
            }

        now = time.time()
        imported = 0
        for row in rows:
            ticker = str(row.get("ticker") or "").strip()
            if not ticker:
                continue
            mid = f"kalshi:{ticker}"
            yes = float(row.get("yes_price") or 0.5)
            yes_pool, no_pool = self._pools_for_yes_price(yes)
            title = str(row.get("title") or ticker)[:160]
            vol = float(row.get("volume_24h") or 0.0)
            close_time = str(row.get("close_time") or "")
            close_ts = _parse_close_ts(close_time)
            target_price = float(row.get("target_price") or row.get("floor_strike") or 0.0)
            yes_bid = float(row.get("yes_bid") or 0.0)
            yes_ask = float(row.get("yes_ask") or 0.0)
            nav = {
                "nav_section": str(row.get("nav_section") or ""),
                "timeframe": str(row.get("timeframe") or ""),
                "asset": str(row.get("asset") or ""),
                "product": str(row.get("product") or "Predictions"),
                "category": str(row.get("category") or "Kalshi LIVE"),
            }
            if not nav["nav_section"]:
                nav.update(
                    classify_market(ticker, title, str(row.get("event_ticker") or ""))
                )
            subtitle = (
                f"{nav['category']} · vol24h≈{vol:.0f} · "
                f"{ticker} · sandbox stakes only (not real Kalshi $)"
            )
            if mid in self.markets and self.markets[mid].status == "open":
                m = self.markets[mid]
                m.title = title
                m.subtitle = subtitle
                m.category = nav["category"]
                m.nav_section = nav["nav_section"]
                m.timeframe = nav["timeframe"]
                m.asset = nav["asset"]
                m.product = nav["product"]
                m.close_time = close_time
                m.close_ts = close_ts
                m.target_price = target_price
                m.yes_bid = yes_bid
                m.yes_ask = yes_ask
                m.kalshi_yes = yes
                m.kalshi_volume_24h = vol
                m.kalshi_synced_ts = now
                m.kalshi_ticker = ticker
                # gently pull local display pools toward Kalshi mid (don't wipe positions)
                if not m.positions:
                    m.yes_pool, m.no_pool = yes_pool, no_pool
                    m.bias_yes = yes
                    m.field_yes = max(0.2, yes * 3.0)
                    m.field_no = max(0.2, (1.0 - yes) * 3.0)
            else:
                self.markets[mid] = Market(
                    id=mid,
                    title=title,
                    subtitle=subtitle,
                    category=nav["category"],
                    yes_pool=yes_pool,
                    no_pool=no_pool,
                    field_yes=max(0.2, yes * 3.0),
                    field_no=max(0.2, (1.0 - yes) * 3.0),
                    bias_yes=yes,
                    kalshi_ticker=ticker,
                    kalshi_yes=yes,
                    kalshi_volume_24h=vol,
                    kalshi_synced_ts=now,
                    nav_section=nav["nav_section"],
                    timeframe=nav["timeframe"],
                    asset=nav["asset"],
                    product=nav["product"],
                    close_time=close_time,
                    close_ts=close_ts,
                    target_price=target_price,
                    yes_bid=yes_bid,
                    yes_ask=yes_ask,
                )
            imported += 1

        result = {
            "ok": True,
            "truth_label": TRUTH_LABEL,
            "event": "kalshi_public_sync",
            "ts": now,
            "imported": imported,
            "feed_fetched": feed.get("fetched_raw"),
            "errors": feed.get("errors") or [],
            "note": (
                "read-only public API sync — does not trade on Kalshi; "
                "GAME_STGM remains sandbox"
            ),
        }
        _append(result, state_dir=self.state_dir)
        self.last_event = result
        return result

    def refresh_kalshi_prices(self) -> dict[str, Any]:
        """Refresh prices for markets that already have kalshi_ticker.

        Also rolls 15m crypto clocks to the *current* open window so the app
        matches Safari Kalshi (dead 8:45 tickers → live 9:00 tickers).
        """
        # Always try to roll 15m first — expired boards were stuck at 0¢
        roll = self.rollover_15m_clocks()
        for m in self.markets.values():
            if hasattr(m, "ensure_kalshi_fields"):
                m.ensure_kalshi_fields()
            elif not hasattr(m, "kalshi_ticker"):
                setattr(m, "kalshi_ticker", "")
                setattr(m, "kalshi_yes", None)
                setattr(m, "kalshi_volume_24h", 0.0)
                setattr(m, "kalshi_synced_ts", 0.0)
        tickers = [
            str(getattr(m, "kalshi_ticker", "") or "")
            for m in self.markets.values()
            if getattr(m, "kalshi_ticker", "") and m.status == "open"
        ]
        if not tickers and not roll.get("imported"):
            return {"ok": False, "reason": "no_kalshi_markets_loaded", "rollover": roll}
        try:
            from System.swarm_kalshi_public_feed import fetch_by_tickers
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "rollover": roll}
        feed = fetch_by_tickers(tickers[:50]) if tickers else {"markets": [], "errors": []}
        now = time.time()
        updated = 0
        by_t = {r["ticker"]: r for r in (feed.get("markets") or [])}
        for m in self.markets.values():
            kt = str(getattr(m, "kalshi_ticker", "") or "")
            if m.status != "open" or not kt:
                continue
            row = by_t.get(kt)
            if not row:
                continue
            yes = float(row.get("yes_price") or getattr(m, "kalshi_yes", None) or 0.5)
            m.kalshi_yes = yes
            m.kalshi_volume_24h = float(row.get("volume_24h") or 0.0)
            m.kalshi_synced_ts = now
            if row.get("title"):
                m.title = str(row["title"])[:160]
            if row.get("close_time"):
                m.close_time = str(row["close_time"])
                m.close_ts = _parse_close_ts(m.close_time)
            if row.get("target_price") or row.get("floor_strike"):
                m.target_price = float(row.get("target_price") or row.get("floor_strike") or 0.0)
            if row.get("yes_bid") is not None:
                m.yes_bid = float(row.get("yes_bid") or 0.0)
            if row.get("yes_ask") is not None:
                m.yes_ask = float(row.get("yes_ask") or 0.0)
            # re-classify if empty
            if not getattr(m, "timeframe", "") and row.get("timeframe"):
                m.timeframe = str(row.get("timeframe") or "")
                m.nav_section = str(row.get("nav_section") or m.nav_section)
                m.asset = str(row.get("asset") or m.asset)
                m.category = str(row.get("category") or m.category)
            # Keep empty-position 15m pools glued to Kalshi mid so glass ≈ Safari
            if (
                not m.positions
                and str(getattr(m, "timeframe", "") or "") == "15 Minute"
            ):
                yp, np_ = self._pools_for_yes_price(yes)
                m.yes_pool, m.no_pool = yp, np_
                m.bias_yes = yes
            updated += 1
        out = {
            "ok": updated > 0 or bool(roll.get("imported")),
            "updated": updated,
            "errors": feed.get("errors") or [],
            "ts": now,
            "rollover": roll,
        }
        self.last_event = {"event": "kalshi_price_refresh", **out}
        # publish live 15m board for Alice / WCT
        try:
            self.publish_live_watch()
        except Exception:
            pass
        return out

    def rollover_15m_clocks(self) -> dict[str, Any]:
        """Replace expired 15m sandboxes with the live Kalshi window (Safari parity).

        Old tickers (e.g. …2045) stay at 0¢ after close while Safari shows the
        next window (…2100) at 68% UP — this imports the new series and retires
        dead clocks that have no open positions.
        """
        try:
            from System.swarm_kalshi_public_feed import fetch_15m_clocks
        except Exception as exc:
            return {"ok": False, "reason": f"import:{type(exc).__name__}: {exc}"}

        feed = fetch_15m_clocks()
        clocks = feed.get("clocks") or []
        if not clocks:
            return {
                "ok": False,
                "reason": "no_live_15m",
                "errors": feed.get("errors") or [],
            }

        now = time.time()
        live_tickers = {str(c.get("ticker") or "") for c in clocks if c.get("ticker")}
        retired = 0
        # retire expired 15m boards with no positions (keep if user has stake)
        for mid, m in list(self.markets.items()):
            if m.status != "open":
                continue
            is_15 = (
                str(getattr(m, "timeframe", "") or "") == "15 Minute"
                or "15M" in str(getattr(m, "kalshi_ticker", "") or "").upper()
            )
            if not is_15:
                continue
            kt = str(getattr(m, "kalshi_ticker", "") or "")
            expired = float(getattr(m, "close_ts", 0.0) or 0.0) > 0 and m.close_ts < now - 5
            not_live = kt and kt not in live_tickers
            if (expired or not_live) and not m.positions:
                del self.markets[mid]
                retired += 1
            elif (expired or not_live) and m.positions:
                # Paper-only dead clocks block the board (0:00 @ 100%) and already_in.
                # Drop stakes so the next live window can bet; real settle is Kalshi Safari.
                m.positions.clear()
                del self.markets[mid]
                retired += 1

        imported = 0
        for row in clocks:
            ticker = str(row.get("ticker") or "").strip()
            if not ticker:
                continue
            mid = f"kalshi:{ticker}"
            yes = float(row.get("yes_price") or 0.5)
            yes_pool, no_pool = self._pools_for_yes_price(yes)
            title = str(row.get("title") or ticker)[:160]
            vol = float(row.get("volume_24h") or 0.0)
            close_time = str(row.get("close_time") or "")
            close_ts = _parse_close_ts(close_time)
            target_price = float(row.get("target_price") or row.get("floor_strike") or 0.0)
            cat = str(row.get("category") or "Crypto · 15 Minute")
            nav_section = str(row.get("nav_section") or "Crypto")
            timeframe = str(row.get("timeframe") or "15 Minute")
            asset = str(row.get("asset") or "")
            subtitle = (
                f"{cat} · vol24h≈{vol:.0f} · {ticker} · sandbox only (not Kalshi $)"
            )
            if mid in self.markets and self.markets[mid].status == "open":
                m = self.markets[mid]
                m.title = title
                m.subtitle = subtitle
                m.category = cat
                m.nav_section = nav_section
                m.timeframe = timeframe
                m.asset = asset
                m.close_time = close_time
                m.close_ts = close_ts
                m.target_price = target_price
                m.yes_bid = float(row.get("yes_bid") or 0.0)
                m.yes_ask = float(row.get("yes_ask") or 0.0)
                m.kalshi_yes = yes
                m.kalshi_volume_24h = vol
                m.kalshi_synced_ts = now
                m.kalshi_ticker = ticker
                # No owner stake → keep local pool glued to Kalshi mid (Safari parity glass)
                # Swarm may still nudge field; pools re-seed each rollover/refresh if empty pos
                if not m.positions:
                    m.yes_pool, m.no_pool = yes_pool, no_pool
                    m.bias_yes = yes
                    m.field_yes = max(0.2, yes * 3.0)
                    m.field_no = max(0.2, (1.0 - yes) * 3.0)
                    m.trades = 0  # clear swarm-only trade noise on fresh mid
            else:
                self.markets[mid] = Market(
                    id=mid,
                    title=title,
                    subtitle=subtitle,
                    category=cat,
                    yes_pool=yes_pool,
                    no_pool=no_pool,
                    field_yes=max(0.2, yes * 3.0),
                    field_no=max(0.2, (1.0 - yes) * 3.0),
                    bias_yes=yes,
                    kalshi_ticker=ticker,
                    kalshi_yes=yes,
                    kalshi_volume_24h=vol,
                    kalshi_synced_ts=now,
                    nav_section=nav_section,
                    timeframe=timeframe,
                    asset=asset,
                    product="Predictions",
                    close_time=close_time,
                    close_ts=close_ts,
                    target_price=target_price,
                    yes_bid=float(row.get("yes_bid") or 0.0),
                    yes_ask=float(row.get("yes_ask") or 0.0),
                )
            imported += 1

        # Safari order: BTC ETH SOL ZEC XRP NEAR HYPE DOGE BNB (then rest)
        _ASSET_ORDER = {
            a: i
            for i, a in enumerate(
                ("BTC", "ETH", "SOL", "ZEC", "XRP", "NEAR", "HYPE", "DOGE", "BNB", "SUI")
            )
        }

        out = {
            "ok": imported > 0,
            "imported": imported,
            "retired": retired,
            "live_tickers": sorted(live_tickers),
            "assets": sorted(
                {
                    str(getattr(m, "asset", "") or "")
                    for m in self.markets.values()
                    if m.status == "open"
                    and str(getattr(m, "timeframe", "") or "") == "15 Minute"
                }
            ),
            "n_15m": sum(
                1
                for m in self.markets.values()
                if m.status == "open"
                and str(getattr(m, "timeframe", "") or "") == "15 Minute"
            ),
            "ts": now,
            "note": "15m window rollover — match Safari open clocks (all assets)",
        }
        _append({"event": "kalshi_15m_rollover", **out}, state_dir=self.state_dir)
        return out

    def publish_live_watch(self) -> dict[str, Any]:
        """Write real-time 15m watch snapshot Alice / Talk / WCT can read."""
        rows = self.watch_15m(limit=12)
        payload = {
            "truth_label": TRUTH_LABEL,
            "event": "kalshi_15m_live_watch",
            "ts": time.time(),
            "n": len(rows),
            "markets": rows,
            "learn": {
                k: self.learn.get(k)
                for k in (
                    "n_settled",
                    "n_local_correct",
                    "n_kalshi_correct",
                    "kalshi_weight",
                    "field_weight",
                    "last_lesson",
                )
            },
            "note": (
                "read-only public Trade API mid/target/countdown — not CF Benchmarks spot stream; "
                "not real Kalshi account; GAME_STGM sandbox only"
            ),
        }
        root = _state_dir(self.state_dir)
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / "kalshi_15m_live.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            with (root / "kalshi_15m_live.jsonl").open("a", encoding="utf-8") as f:
                # compact line for Alice sense bus
                slim = {
                    "ts": payload["ts"],
                    "n": payload["n"],
                    "rows": [
                        {
                            "asset": r.get("asset"),
                            "title": r.get("title"),
                            "kalshi_yes": r.get("kalshi_chance_yes"),
                            "our_yes": r.get("our_chance_yes"),
                            "up_cents": r.get("kalshi_up_cents"),
                            "down_cents": r.get("kalshi_down_cents"),
                            "target": r.get("target_price"),
                            "secs": r.get("seconds_to_close"),
                            "ticker": r.get("kalshi_ticker"),
                        }
                        for r in rows[:9]
                    ],
                }
                f.write(json.dumps(slim, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return payload

    def _charge(self, agent_id: str, amount: float) -> bool:
        bal = float(self.balances.get(agent_id, 0.0))
        if bal + 1e-12 < amount:
            return False
        self.balances[agent_id] = round(bal - amount, 6)
        return True

    def _credit(self, agent_id: str, amount: float) -> None:
        self.balances[agent_id] = round(
            float(self.balances.get(agent_id, 0.0)) + amount, 6
        )

    def _sign_ballot(self, market: Market, agent_id: str, side: Side, stake: float) -> dict[str, Any]:
        identity = self.identities.get(agent_id)
        if identity is None:
            identity = SwimmerIdentity(f"sifta-market:{self.seed}:{agent_id}")
            self.identities[agent_id] = identity
        payload = json.dumps(
            {
                "domain": "SIFTA-PREDICTION-MARKET-BALLOT-V1",
                "previous_digest": market.ballot_digest,
                "market_id": market.id,
                "agent_id": agent_id,
                "side": side,
                "stake": round(stake, 4),
                "tick": self.tick,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        trace = identity.deposit("sifta-market/ballot", payload)
        verified = verify_trace(trace)
        if verified:
            market.verified_ballots += 1
        else:
            market.rejected_ballots += 1
        market.ballot_digest = hashlib.sha256(
            f"{market.ballot_digest}|{trace.signature_hex}".encode("ascii")
        ).hexdigest()[:16]
        return {
            "ballot_digest": market.ballot_digest,
            "crypto_swimmer_id": trace.swimmer_id,
            "public_key_hex": trace.public_key_hex,
            "ed25519_signature": trace.signature_hex,
            "signature_verified": verified,
        }

    def buy(
        self,
        market_id: str,
        side: Side,
        stake: float,
        *,
        agent_id: str = OWNER_ID,
    ) -> dict[str, Any]:
        m = self.markets.get(market_id)
        if not m:
            return {"ok": False, "reason": "no_market"}
        if m.status != "open":
            return {"ok": False, "reason": "market_resolved"}
        stake = _clamp(stake, MIN_STAKE, MAX_STAKE)
        if not self._charge(agent_id, stake):
            return {
                "ok": False,
                "reason": "insufficient_game_stgm",
                "balance": self.balances.get(agent_id, 0.0),
            }
        side = "yes" if side == "yes" else "no"
        # shares = stake (1:1 simple parimutuel entry)
        pos = m.positions.setdefault(agent_id, {"yes": 0.0, "no": 0.0, "cost": 0.0})
        pos[side] = round(float(pos[side]) + stake, 6)
        pos["cost"] = round(float(pos["cost"]) + stake, 6)
        if side == "yes":
            m.yes_pool = round(m.yes_pool + stake, 6)
            m.field_yes = round(m.field_yes + 0.35 * stake, 6)
        else:
            m.no_pool = round(m.no_pool + stake, 6)
            m.field_no = round(m.field_no + 0.35 * stake, 6)
        m.trades += 1
        self.volume[agent_id] = round(float(self.volume.get(agent_id, 0.0)) + stake, 6)
        self.predictions[agent_id] = int(self.predictions.get(agent_id, 0)) + 1
        ballot = self._sign_ballot(m, agent_id, side, stake)
        row = {
            "truth_label": TRUTH_LABEL,
            "event": "buy",
            "ts": time.time(),
            "receipt_id": str(uuid.uuid4()),
            "market_id": market_id,
            "agent_id": agent_id,
            "display_name": self.display_names.get(agent_id, agent_id),
            "side": side,
            "stake": stake,
            "token": TOKEN,
            **ballot,
            "yes_price": round(m.yes_price(), 4),
        }
        _append(row, state_dir=self.state_dir)
        self.last_event = row
        # open-order style history line
        self.history.append(
            {
                "kind": "open",
                "ts": time.time(),
                "agent_id": agent_id,
                "display_name": self.display_names.get(agent_id, agent_id),
                "market_id": market_id,
                "title": m.title,
                "side": side,
                "stake": stake,
                "status": "open",
                "pnl": None,
            }
        )
        return {"ok": True, **row, "market": m.to_row(), "balance": self.balances.get(agent_id)}

    def resolve(self, market_id: str, outcome: Side) -> dict[str, Any]:
        m = self.markets.get(market_id)
        if not m:
            return {"ok": False, "reason": "no_market"}
        if m.status != "open":
            return {"ok": False, "reason": "already_resolved"}
        outcome = "yes" if outcome == "yes" else "no"
        m.status = "resolved"
        m.outcome = outcome
        # Winners share the full pot proportional to winning shares
        pot = m.total_pool()
        win_key = outcome
        total_win_shares = 0.0
        for agent, pos in m.positions.items():
            total_win_shares += float(pos.get(win_key) or 0.0)
        payouts: dict[str, float] = {}
        if total_win_shares > 1e-9:
            for agent, pos in m.positions.items():
                shares = float(pos.get(win_key) or 0.0)
                cost = float(pos.get("cost") or 0.0)
                if shares <= 0:
                    # full loss of cost for pure losers
                    self.realized_pnl[agent] = round(
                        float(self.realized_pnl.get(agent, 0.0)) - cost, 6
                    )
                    self.history.append(
                        {
                            "kind": "closed",
                            "ts": time.time(),
                            "agent_id": agent,
                            "display_name": self.display_names.get(agent, agent),
                            "market_id": market_id,
                            "title": m.title,
                            "side": "yes" if float(pos.get("yes") or 0) > 0 else "no",
                            "stake": cost,
                            "status": "paid_out" if False else "lost",
                            "pnl": round(-cost, 4),
                            "outcome": outcome,
                        }
                    )
                    continue
                pay = pot * (shares / total_win_shares)
                self._credit(agent, pay)
                payouts[agent] = round(pay, 4)
                pnl = round(pay - cost, 4)
                # profit ≈ payout − cost (simple; ignores partial hedges)
                self.realized_pnl[agent] = round(
                    float(self.realized_pnl.get(agent, 0.0)) + (pay - cost), 6
                )
                self.history.append(
                    {
                        "kind": "closed",
                        "ts": time.time(),
                        "agent_id": agent,
                        "display_name": self.display_names.get(agent, agent),
                        "market_id": market_id,
                        "title": m.title,
                        "side": win_key,
                        "stake": cost,
                        "status": "paid_out",
                        "pnl": pnl,
                        "payout": round(pay, 4),
                        "outcome": outcome,
                    }
                )
        else:
            # no winners — return pools to owner bank as demo dust
            self._credit(OWNER_ID, pot * 0.1)
        # mark open history rows for this market closed for display
        for h in self.history:
            if h.get("kind") == "open" and h.get("market_id") == market_id:
                h["kind"] = "settled_open"
                h["status"] = f"resolved_{outcome}"
        row = {
            "truth_label": TRUTH_LABEL,
            "event": "resolve",
            "ts": time.time(),
            "receipt_id": str(uuid.uuid4()),
            "market_id": market_id,
            "outcome": outcome,
            "pot": round(pot, 4),
            "payouts": payouts,
            "token": TOKEN,
            "ballot_digest": m.ballot_digest,
        }
        lesson = self._learn_from_resolve(m, outcome)
        row["lesson"] = lesson
        row["learn"] = dict(self.learn)
        _append(row, state_dir=self.state_dir)
        self.last_event = row
        return {"ok": True, **row, "market": m.to_row()}

    def _learn_from_resolve(self, m: Market, outcome: Side) -> str:
        """Update stigmergic swarm weights after a settlement (sandbox learn)."""
        learn = dict(self.learn)
        learn["n_settled"] = int(learn.get("n_settled") or 0) + 1
        local_yes = float(m.yes_price())
        # use pools before resolve still available
        kalshi_yes = m.kalshi_yes
        local_pred = "yes" if local_yes >= 0.5 else "no"
        local_ok = local_pred == outcome
        if local_ok:
            learn["n_local_correct"] = int(learn.get("n_local_correct") or 0) + 1
        kalshi_ok = None
        if kalshi_yes is not None:
            kalshi_pred = "yes" if float(kalshi_yes) >= 0.5 else "no"
            kalshi_ok = kalshi_pred == outcome
            if kalshi_ok:
                learn["n_kalshi_correct"] = int(learn.get("n_kalshi_correct") or 0) + 1
        # field heat prediction
        field_pred = "yes" if m.field_yes_share() >= 0.5 else "no"
        field_ok = field_pred == outcome
        if field_ok:
            learn["n_swarm_side_correct"] = int(learn.get("n_swarm_side_correct") or 0) + 1

        # adapt weights: if kalshi mid beat local pool, trust mid more next time
        kw = float(learn.get("kalshi_weight") or 0.25)
        fw = float(learn.get("field_weight") or 0.50)
        bw = float(learn.get("bias_weight") or 0.20)
        if kalshi_ok is True and not local_ok:
            kw = min(0.55, kw + 0.03)
            bw = max(0.10, bw - 0.02)
            lesson = (
                f"Kalshi mid was right, local pool wrong on {m.asset or m.id[:20]} "
                f"→ trust public mid more (kw={kw:.2f})"
            )
        elif local_ok and kalshi_ok is False:
            kw = max(0.05, kw - 0.03)
            fw = min(0.70, fw + 0.02)
            lesson = (
                f"Local field/pool beat Kalshi mid on {m.asset or m.id[:20]} "
                f"→ trust field more (fw={fw:.2f})"
            )
        elif field_ok:
            fw = min(0.70, fw + 0.01)
            lesson = f"Field heat matched outcome ({outcome}) — slight field boost"
        else:
            # noise down a touch, widen exploration slightly
            nw = float(learn.get("noise_weight") or 0.05)
            nw = min(0.15, nw + 0.01)
            learn["noise_weight"] = nw
            lesson = f"Miss on {outcome} — noise up to {nw:.2f} (exploration)"

        # renormalize weights so they roughly sum to 1
        total = kw + fw + bw + float(learn.get("noise_weight") or 0.05)
        if total > 1e-9:
            learn["kalshi_weight"] = round(kw / total, 4)
            learn["field_weight"] = round(fw / total, 4)
            learn["bias_weight"] = round(bw / total, 4)
            learn["noise_weight"] = round(float(learn.get("noise_weight") or 0.05) / total, 4)
        learn["prefer_15m"] = float(learn.get("prefer_15m") or 0.75)
        learn["last_lesson"] = lesson
        learn["ts"] = time.time()
        self.learn = learn
        self.last_lesson = lesson
        _save_learn(learn, state_dir=self.state_dir)
        _append(
            {
                "truth_label": TRUTH_LABEL,
                "event": "market_learn",
                "ts": time.time(),
                "market_id": m.id,
                "outcome": outcome,
                "local_yes": round(local_yes, 4),
                "kalshi_yes": None if kalshi_yes is None else round(float(kalshi_yes), 4),
                "local_ok": local_ok,
                "kalshi_ok": kalshi_ok,
                "field_ok": field_ok,
                "lesson": lesson,
                "weights": {
                    k: learn[k]
                    for k in (
                        "kalshi_weight",
                        "field_weight",
                        "bias_weight",
                        "noise_weight",
                        "n_settled",
                        "n_local_correct",
                        "n_kalshi_correct",
                    )
                },
            },
            state_dir=self.state_dir,
        )
        return lesson

    def watch_15m(self, *, limit: int = 12) -> list[dict[str, Any]]:
        """Ending-soon 15-minute clocks with dual odds (owner watch strip)."""
        now = time.time()
        rows: list[tuple[float, dict[str, Any]]] = []
        for m in self.markets.values():
            if m.status != "open":
                continue
            is_15 = (
                str(getattr(m, "timeframe", "") or "") == "15 Minute"
                or "15M" in str(getattr(m, "kalshi_ticker", "") or "").upper()
                or "15 min" in m.title.lower()
            )
            if not is_15:
                continue
            close_ts = float(getattr(m, "close_ts", 0.0) or 0.0)
            # hide dead windows (Safari already moved to next 15m)
            if close_ts > 0 and close_ts < now - 2:
                continue
            urgency = close_ts if close_ts > 0 else now + 900
            row = m.to_row()
            row["our_chance_yes"] = round(m.yes_price(), 4)
            row["kalshi_chance_yes"] = (
                None if m.kalshi_yes is None else round(float(m.kalshi_yes), 4)
            )
            row["edge"] = (
                None
                if m.kalshi_yes is None
                else round(m.yes_price() - float(m.kalshi_yes), 4)
            )
            row["target_price"] = float(getattr(m, "target_price", 0.0) or 0.0)
            row["kalshi_up_cents"] = (
                None
                if m.kalshi_yes is None
                else int(round(float(m.kalshi_yes) * 100))
            )
            row["kalshi_down_cents"] = (
                None
                if m.kalshi_yes is None
                else int(round((1.0 - float(m.kalshi_yes)) * 100))
            )
            row["ending_soon"] = bool(close_ts and 0 < close_ts - now < 600)
            rows.append((urgency, row))
        # Safari-ish asset order, then soonest close
        _ord = {
            a: i
            for i, a in enumerate(
                ("BTC", "ETH", "SOL", "ZEC", "XRP", "NEAR", "HYPE", "DOGE", "BNB", "SUI")
            )
        }

        def _key(item: tuple[float, dict[str, Any]]) -> tuple:
            urg, row = item
            asset = str(row.get("asset") or "")
            return (_ord.get(asset, 99), urg)

        rows.sort(key=_key)
        return [r for _, r in rows[: max(1, limit)]]

    def portfolio(self, agent_id: str = OWNER_ID) -> dict[str, Any]:
        """Kalshi-style portfolio strip: open positions + closed history for one agent."""
        open_pos: list[dict[str, Any]] = []
        for m in self.markets.values():
            if m.status != "open":
                continue
            pos = m.positions.get(agent_id) or {}
            yes_s = float(pos.get("yes") or 0.0)
            no_s = float(pos.get("no") or 0.0)
            cost = float(pos.get("cost") or 0.0)
            if yes_s <= 0 and no_s <= 0:
                continue
            open_pos.append(
                {
                    "market_id": m.id,
                    "title": m.title,
                    "yes": yes_s,
                    "no": no_s,
                    "cost": cost,
                    "yes_price": round(m.yes_price(), 4),
                    "max_payout_yes": round(yes_s * (m.total_pool() / max(1e-9, m.yes_pool)), 4)
                    if yes_s > 0
                    else 0.0,
                    "status": "open",
                }
            )
        closed = [
            h
            for h in self.history
            if h.get("agent_id") == agent_id and h.get("kind") == "closed"
        ]
        closed = list(reversed(closed[-40:]))
        pnl = float(self.realized_pnl.get(agent_id, 0.0))
        return {
            "agent_id": agent_id,
            "display_name": self.display_names.get(agent_id, agent_id),
            "balance": round(float(self.balances.get(agent_id, 0.0)), 4),
            "cash": round(float(self.balances.get(agent_id, 0.0)), 4),
            "predictions_pnl": round(pnl, 4),
            "volume": round(float(self.volume.get(agent_id, 0.0)), 4),
            "predictions": int(self.predictions.get(agent_id, 0)),
            "open_positions": open_pos,
            "history": closed,
            "token": TOKEN,
            "note": "sandbox portfolio — not Kalshi USD positions",
        }

    def leaderboard(
        self,
        *,
        metric: Literal["profit", "volume", "predictions"] = "profit",
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        """Kalshi SOCIAL-style ranks: Profit / Volume / Predictions (GAME_STGM)."""
        agents = set(self.balances) | set(self.volume) | set(self.predictions)
        rows: list[dict[str, Any]] = []
        for agent in agents:
            rows.append(
                {
                    "agent_id": agent,
                    "display_name": self.display_names.get(
                        agent, agent.replace("swarm:", "swarm.")[:18]
                    ),
                    "profit": round(float(self.realized_pnl.get(agent, 0.0)), 4),
                    "volume": round(float(self.volume.get(agent, 0.0)), 4),
                    "predictions": int(self.predictions.get(agent, 0)),
                    "balance": round(float(self.balances.get(agent, 0.0)), 4),
                    "is_owner": agent == OWNER_ID,
                }
            )
        key = {
            "profit": lambda r: r["profit"],
            "volume": lambda r: r["volume"],
            "predictions": lambda r: r["predictions"],
        }.get(metric, lambda r: r["profit"])
        rows.sort(key=key, reverse=True)
        out = []
        for rank, row in enumerate(rows[: max(1, limit)], start=1):
            out.append({**row, "rank": rank})
        return out

    def evaporate_fields(self) -> None:
        for m in self.markets.values():
            if m.status != "open":
                continue
            m.field_yes = max(0.15, m.field_yes * 0.992)
            m.field_no = max(0.15, m.field_no * 0.992)

    def swarm_step(self) -> dict[str, Any]:
        """One auto tick: swimmers stake GAME_STGM — prefer 15m clocks ending soon."""
        self.tick += 1
        self.evaporate_fields()
        open_markets = [m for m in self.markets.values() if m.status == "open"]
        if not open_markets:
            return {"ok": False, "reason": "no_open_markets"}

        now = time.time()
        fifteen = [
            m
            for m in open_markets
            if str(getattr(m, "timeframe", "") or "") == "15 Minute"
            or "15M" in str(getattr(m, "kalshi_ticker", "") or "").upper()
        ]
        # prefer ending-soon 15m (Kalshi ~9 clocks) so owner can watch stigmergy
        prefer = float(self.learn.get("prefer_15m") or 0.75)
        if fifteen and self.rng.random() < prefer:
            fifteen.sort(
                key=lambda x: float(getattr(x, "close_ts", 0.0) or 0.0) or (now + 9999)
            )
            # weight toward soonest close
            m = fifteen[0] if len(fifteen) == 1 else self.rng.choice(fifteen[: max(3, len(fifteen) // 2)])
            focus = "15m"
        else:
            m = self.rng.choice(open_markets)
            focus = "board"

        learn = self.learn
        fw = float(learn.get("field_weight") or 0.50)
        bw = float(learn.get("bias_weight") or 0.20)
        kw = float(learn.get("kalshi_weight") or 0.25)
        nw = float(learn.get("noise_weight") or 0.05)
        kalshi = float(m.kalshi_yes) if m.kalshi_yes is not None else float(m.bias_yes)
        # stigmergic blend: field heat + seed bias + public mid + noise
        p_yes = (
            fw * m.field_yes_share()
            + bw * float(m.bias_yes)
            + kw * kalshi
            + nw * self.rng.random()
        )
        p_yes = _clamp(p_yes, 0.08, 0.92)
        n_voters = self.rng.randint(2, min(6, len(self.swimmer_ids)))
        agents = self.rng.sample(self.swimmer_ids, n_voters)
        buys = []
        for agent in agents:
            side: Side = "yes" if self.rng.random() < p_yes else "no"
            stake = round(self.rng.uniform(0.5, 2.5), 2)
            if side == "yes":
                m.field_yes += 0.08
            else:
                m.field_no += 0.08
            r = self.buy(m.id, side, stake, agent_id=agent)
            if r.get("ok"):
                buys.append(
                    {
                        "agent": self.display_names.get(agent, agent)[:16],
                        "side": side,
                        "stake": stake,
                    }
                )
        return {
            "ok": True,
            "tick": self.tick,
            "market_id": m.id,
            "title": m.title,
            "focus": focus,
            "timeframe": getattr(m, "timeframe", ""),
            "asset": getattr(m, "asset", ""),
            "p_yes": round(p_yes, 3),
            "our_chance": round(m.yes_price(), 3),
            "kalshi_chance": None if m.kalshi_yes is None else round(float(m.kalshi_yes), 3),
            "seconds_to_close": (
                max(0, int(m.close_ts - now)) if m.close_ts > 0 else None
            ),
            "buys": buys,
            "learn_weights": {
                "field": fw,
                "bias": bw,
                "kalshi": kw,
                "noise": nw,
            },
            "market": m.to_row(),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "truth_label": TRUTH_LABEL,
            "token": TOKEN,
            "seed": self.seed,
            "tick": self.tick,
            "owner_balance": round(self.owner_balance(), 4),
            "owner_display": OWNER_DISPLAY,
            "swarm_size": self.swarm_size,
            "swarm_treasury": round(
                sum(self.balances.get(s, 0.0) for s in self.swimmer_ids), 4
            ),
            "markets": self.list_markets(),
            "leaderboard_profit": self.leaderboard(metric="profit", limit=12),
            "leaderboard_volume": self.leaderboard(metric="volume", limit=12),
            "leaderboard_predictions": self.leaderboard(metric="predictions", limit=12),
            "portfolio_owner": self.portfolio(OWNER_ID),
            "last_event": self.last_event,
            "note": (
                "SIFTA sandbox prediction market — not Kalshi.com, not USD, "
                "not body repair_log wallet. SOCIAL ranks from owner glass dirt."
            ),
        }

    def save_snapshot(self) -> None:
        root = _state_dir(self.state_dir)
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / _SNAPSHOT).write_text(
                json.dumps(self.snapshot(), indent=2), encoding="utf-8"
            )
        except Exception:
            pass


def run_pheromone_ablation(
    *,
    seed: int = 1626,
    trials: int = 400,
    ticks: int = 18,
    swarm_size: int = 32,
    state_dir: Optional[Path | str] = None,
    write_receipt: bool = False,
) -> dict[str, Any]:
    """Paired test of field memory versus no field on identical evidence.

    A private latent probability generates noisy local measurements. The
    no-field lane may use only the final tick; the field lane accumulates the
    same measurements through an evaporating YES/NO trace. We score expected
    Brier loss against the known synthetic data-generating probability. This
    demonstrates the mechanism under controlled conditions, not real-world
    forecasting skill.
    """
    rng = random.Random(int(seed))
    count = max(20, int(trials))
    steps = max(2, int(ticks))
    agents = max(4, int(swarm_size))
    field_loss = plain_loss = field_error = plain_error = 0.0

    for _ in range(count):
        latent = rng.uniform(0.08, 0.92)
        field_yes = field_no = 1.0
        plain_estimate = 0.5
        for _tick in range(steps):
            signals = [_clamp(rng.gauss(latent, 0.24), 0.0, 1.0) for _ in range(agents)]
            plain_estimate = sum(signals) / len(signals)
            field_yes *= 0.94
            field_no *= 0.94
            for signal in signals:
                field_yes += signal
                field_no += 1.0 - signal
        field_estimate = field_yes / (field_yes + field_no)

        # Expected Brier score for Bernoulli(outcome | latent).
        field_loss += latent * (1.0 - field_estimate) ** 2 + (1.0 - latent) * field_estimate ** 2
        plain_loss += latent * (1.0 - plain_estimate) ** 2 + (1.0 - latent) * plain_estimate ** 2
        field_error += (field_estimate - latent) ** 2
        plain_error += (plain_estimate - latent) ** 2

    field_brier = field_loss / count
    plain_brier = plain_loss / count
    improvement = (plain_brier - field_brier) / max(1e-12, plain_brier)

    # Real cryptographic ablation: valid ballots pass; altered payloads fail.
    tamper_trials = min(64, agents)
    valid_verified = tamper_rejected = 0
    for index in range(tamper_trials):
        identity = SwimmerIdentity(f"market-ablation:{seed}:{index}")
        trace = identity.deposit(
            "sifta-market/ablation-ballot",
            json.dumps({"trial": index, "vote": index % 2}, sort_keys=True),
            ts=1_700_000_000.0 + index,
        )
        valid_verified += int(verify_trace(trace))
        altered = replace(trace, payload=trace.payload + "-tampered")
        tamper_rejected += int(not verify_trace(altered))

    row = {
        "truth_label": "SIFTA_MARKET_PHEROMONE_ABLATION_V1",
        "event": "pheromone_ablation",
        "seed": int(seed),
        "trials": count,
        "ticks_per_trial": steps,
        "swarm_size": agents,
        "field_expected_brier": round(field_brier, 8),
        "no_field_expected_brier": round(plain_brier, 8),
        "field_probability_mse": round(field_error / count, 8),
        "no_field_probability_mse": round(plain_error / count, 8),
        "relative_brier_improvement": round(improvement, 6),
        "field_helped": field_brier < plain_brier,
        "valid_signatures_verified": valid_verified,
        "tampered_signatures_rejected": tamper_rejected,
        "crypto_trials": tamper_trials,
        "conclusion_scope": "controlled_synthetic_evidence_only_not_real_world_forecasting_proof",
    }
    if write_receipt:
        _append({**row, "ts": time.time()}, state_dir=state_dir)
    return row


__all__ = [
    "TRUTH_LABEL",
    "TOKEN",
    "OWNER_ID",
    "OWNER_DISPLAY",
    "SiftaMarketEngine",
    "Market",
    "seed_markets",
    "run_pheromone_ablation",
]
