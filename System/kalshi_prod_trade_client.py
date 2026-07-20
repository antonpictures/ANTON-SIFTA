#!/usr/bin/env python3
"""Kalshi PRODUCTION Trade API client — real USD (r1644 / r1647).

IRON BOUNDARY
  • Host is production only (external-api.kalshi.com). Demo host raises.
  • Credentials from kalshi_credentials (prod Keychain / secrets only).
  • Kill switch: .sifta_state/kalshi_kill_switch.json {"halt": true}
  • Hard caps enforced BEFORE sign (band, count, open, night loss, budget).
  • Never prints secrets.

STGM is independent — this module only touches Kalshi USD.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE = ROOT / ".sifta_state"
API_LOG = "kalshi_prod_api.jsonl"
KILL_SWITCH = "kalshi_kill_switch.json"
PROD_BASE = "https://external-api.kalshi.com/trade-api/v2"

# r1644 / r1648 ledger deal caps (USD live)
try:
    from System.ledger_deal import (
        MAX_BUDGET_USD,
        MAX_NIGHT_LOSS_USD,
        MAX_OPEN,
        MIN_VOLUME,
        STAKE_USD,
        USD_MAX_ENTRY as MAX_ENTRY,
        USD_MIN_ENTRY as MIN_ENTRY,
        contracts_for_ammo,
        get_ammo_usd,
    )
except Exception:
    MAX_OPEN = 3
    MAX_NIGHT_LOSS_USD = 5.0
    MAX_BUDGET_USD = 12.0
    STAKE_USD = 2.0
    MIN_ENTRY = 0.40
    MAX_ENTRY = 0.65
    MIN_VOLUME = 500.0

    def get_ammo_usd(*, state_dir=None) -> float:  # type: ignore
        return float(STAKE_USD)

    def contracts_for_ammo(*, ammo_usd=None, state_dir=None) -> int:  # type: ignore
        a = float(ammo_usd) if ammo_usd is not None else float(STAKE_USD)
        return max(1, min(5, int(round(a))))


# r1693: AMMO may be 1–5 contracts; legacy name kept for receipts
MAX_CONTRACTS = 5  # hard ceiling (not required exact count)

READ_BUDGET_PER_S = 20.0
WRITE_BUDGET_PER_S = 5.0
TOKEN_COST_DEFAULT = 10.0

TRUTH = "KALSHI_PROD_TRADE_CLIENT_V1"

_DEMO_FORBIDDEN = (
    "demo.kalshi",
    "demo-api.kalshi",
    "external-api.demo",
)


class DemoHostForbidden(RuntimeError):
    """Demo/sandbox hosts are forbidden in the prod client."""


class KillSwitchActive(RuntimeError):
    """Write refused — kill switch file is armed."""


class NotProvisioned(RuntimeError):
    """Prod API keys not installed."""


class CapRejected(RuntimeError):
    """Order violated hard caps."""


def _forbid_demo(url: str) -> None:
    u = str(url or "").lower()
    for frag in _DEMO_FORBIDDEN:
        if frag in u:
            raise DemoHostForbidden(f"r1644: demo host forbidden in prod client: {frag}")


def assert_prod_url(url: str) -> str:
    _forbid_demo(url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        raise DemoHostForbidden("production Kalshi requires https")
    if host != "external-api.kalshi.com":
        raise DemoHostForbidden(f"non-production Kalshi host refused: {host or 'missing'}")
    if parsed.username or parsed.password:
        raise DemoHostForbidden("userinfo is forbidden in production Kalshi URLs")
    return url


@dataclass
class TokenBucket:
    refill_per_s: float
    capacity: float
    tokens: float = field(default=0.0)
    last: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def take(self, cost: float = TOKEN_COST_DEFAULT) -> bool:
        now = time.time()
        elapsed = max(0.0, now - self.last)
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_s)
        if self.tokens < cost:
            return False
        self.tokens -= cost
        return True

    def wait_and_take(self, cost: float = TOKEN_COST_DEFAULT, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.take(cost):
                return True
            time.sleep(0.02)
        return False


def kill_switch_active(*, state_dir: Path | str = STATE) -> bool:
    p = Path(state_dir) / KILL_SWITCH
    if not p.exists():
        return False
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return bool(raw.get("halt"))
    except Exception:
        # A corrupt control file is not evidence that writes are allowed.
        return True


def set_kill_switch(halt: bool, *, reason: str = "", state_dir: Path | str = STATE) -> Path:
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    p = root / KILL_SWITCH
    payload = json.dumps(
        {
            "halt": bool(halt),
            "ts": time.time(),
            "reason": str(reason or "")[:200],
            "truth_label": TRUTH,
        },
        indent=2,
    )
    tmp = p.with_name(f"{p.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(p)
    return p


def _append_api_log(row: dict[str, Any], *, state_dir: Path | str = STATE) -> None:
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / API_LOG
    try:
        if path.exists() and path.stat().st_size > 8_000_000:
            bak = path.with_suffix(".jsonl.prev")
            if bak.exists():
                bak.unlink()
            path.rename(bak)
    except OSError:
        pass
    try:
        safe = {k: v for k, v in row.items() if k not in ("pem", "signature", "key")}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _sign_path_for_url(base: str, rel_path: str) -> str:
    rel = rel_path if rel_path.startswith("/") else f"/{rel_path}"
    return urlparse(base.rstrip("/") + rel).path


class KalshiProdTradeClient:
    """Production order client with r1644 hard caps."""

    def __init__(
        self,
        *,
        state_dir: Path | str = STATE,
        base: str = PROD_BASE,
        night_loss_usd: float = 0.0,
        open_count: int = 0,
        open_exposure_usd: float = 0.0,
    ) -> None:
        assert_prod_url(base)
        self.base = base.rstrip("/")
        self.state_dir = Path(state_dir)
        self.read_bucket = TokenBucket(READ_BUDGET_PER_S, READ_BUDGET_PER_S * 2)
        self.write_bucket = TokenBucket(WRITE_BUDGET_PER_S, WRITE_BUDGET_PER_S * 2)
        self.night_loss_usd = float(night_loss_usd)
        self.open_count = int(open_count)
        self.open_exposure_usd = float(open_exposure_usd)

    def status(self) -> dict[str, Any]:
        from System.kalshi_credentials import credentials_status

        st = credentials_status()
        return {
            "truth_label": TRUTH,
            "env": "prod",
            "base": self.base,
            "provisioned": bool(st.get("ready")),
            "kill_switch": kill_switch_active(state_dir=self.state_dir),
            "max_open": MAX_OPEN,
            "max_night_loss_usd": MAX_NIGHT_LOSS_USD,
            "max_budget_usd": MAX_BUDGET_USD,
            "stake_usd": STAKE_USD,
            "entry_band": [MIN_ENTRY, MAX_ENTRY],
            "open_count": self.open_count,
            "open_exposure_usd": round(self.open_exposure_usd, 2),
            "night_loss_usd": round(self.night_loss_usd, 2),
            "note": "PROD real USD · r1644 caps · STGM separate",
        }

    def _auth_headers(self, method: str, rel_path: str) -> dict[str, str]:
        from System.kalshi_credentials import load_api_key_id, load_private_key_pem
        from System.kalshi_demo_client import sign_request

        key_id = load_api_key_id()
        pem = load_private_key_pem()
        if not key_id or not pem:
            raise NotProvisioned("prod keys missing — kalshi_credentials not ready")
        ts = str(int(time.time() * 1000))
        sign_path = _sign_path_for_url(self.base, rel_path)
        sig = sign_request(pem, timestamp_ms=ts, method=method, path=sign_path)
        return {
            "KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SIFTA-Alice-KalshiProd/1.0 (r1644; owner-armed USD)",
        }

    def _request(
        self,
        method: str,
        rel_path: str,
        *,
        body: Optional[dict] = None,
        write: bool = False,
        timeout: float = 12.0,
        _caps_checked: bool = False,
    ) -> dict[str, Any]:
        assert_prod_url(self.base)
        if write and kill_switch_active(state_dir=self.state_dir):
            raise KillSwitchActive("kalshi_kill_switch.json halt=true — write refused before sign")
        normalized_path = "/" + str(rel_path or "").lstrip("/")
        if (
            write
            and normalized_path == "/portfolio/events/orders"
            and not _caps_checked
        ):
            raise CapRejected("Create Order V2 requires the checked place_limit_order path")
        bucket = self.write_bucket if write else self.read_bucket
        if not bucket.wait_and_take(TOKEN_COST_DEFAULT, timeout=3.0):
            raise RuntimeError("rate_limit_token_bucket_empty")

        rel = rel_path if rel_path.startswith("/") else f"/{rel_path}"
        url = self.base + rel
        assert_prod_url(url)
        headers = self._auth_headers(method, rel)
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(url, data=data, headers=headers, method=method.upper())
        t0 = time.time()
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                code = getattr(resp, "status", 200)
        except HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            _append_api_log(
                {
                    "ts": time.time(),
                    "method": method,
                    "path": rel,
                    "status": exc.code,
                    "error": err_body[:300],
                    "write": write,
                    "env": "prod",
                },
                state_dir=self.state_dir,
            )
            # re-raise with body so hand ledger shows Kalshi message
            raise HTTPError(
                exc.url,
                exc.code,
                f"{exc.reason} | {err_body[:200]}",
                exc.headers,
                None,
            ) from None
        except URLError as exc:
            _append_api_log(
                {
                    "ts": time.time(),
                    "method": method,
                    "path": rel,
                    "error": str(exc.reason)[:200],
                    "write": write,
                    "env": "prod",
                },
                state_dir=self.state_dir,
            )
            raise

        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:500]}
        _append_api_log(
            {
                "ts": time.time(),
                "method": method,
                "path": rel,
                "status": code,
                "ms": int((time.time() - t0) * 1000),
                "write": write,
                "env": "prod",
            },
            state_dir=self.state_dir,
        )
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    def get_balance(self) -> dict[str, Any]:
        return self._request("GET", "/portfolio/balance")

    def _check_caps(
        self,
        *,
        price: float,
        count: int,
        volume: Optional[float] = None,
    ) -> None:
        p = float(price)
        if not math.isfinite(p):
            raise CapRejected("price must be finite")
        # r1726: US$ hard scalp band only (ledger 40–65¢). Paper may use
        # MUST_FIRE 20–80¢; cash must NOT inherit that lottery window.
        band_lo, band_hi = float(MIN_ENTRY), float(MAX_ENTRY)
        if p < band_lo - 1e-9 or p > band_hi + 1e-9:
            raise CapRejected(f"price_band {p} outside {band_lo}-{band_hi}")
        count_f = float(count)
        # r1693: AMMO 1–5 contracts (default 2); no longer force count==1
        if not math.isfinite(count_f) or count_f < 1 or count_f > float(MAX_CONTRACTS):
            raise CapRejected(f"contract_count {count_f} outside 1-{MAX_CONTRACTS}")
        if abs(count_f - round(count_f)) > 1e-9:
            raise CapRejected("contract_count must be integer")
        n_ct = int(round(count_f))
        if self.open_count >= MAX_OPEN:
            raise CapRejected(f"max_open {MAX_OPEN}")
        if self.night_loss_usd <= -MAX_NIGHT_LOSS_USD:
            raise CapRejected(f"max_night_loss ${MAX_NIGHT_LOSS_USD}")
        cost = round(p * n_ct, 4)
        if self.open_exposure_usd + cost > MAX_BUDGET_USD + 1e-9:
            raise CapRejected(f"max_budget ${MAX_BUDGET_USD}")
        # r1649: MIN_VOLUME 0 → volume optional (dual every paper)
        if MIN_VOLUME > 0:
            if volume is None:
                raise CapRejected("volume_unknown")
            volume_f = float(volume)
            if not math.isfinite(volume_f) or volume_f < MIN_VOLUME:
                raise CapRejected(f"dust_volume {volume} < {MIN_VOLUME}")

    def place_limit_order(
        self,
        *,
        ticker: str,
        side: str,
        price: float,
        count: int = 1,
        action: str = "buy",
        volume: Optional[float] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Place a PROD limit order (1 contract). Caps + kill before sign."""
        if kill_switch_active(state_dir=self.state_dir):
            raise KillSwitchActive("halt before sign")
        if str(action or "").lower() != "buy":
            raise CapRejected("USD hand supports buy orders only")
        if not str(ticker or "").strip():
            raise CapRejected("ticker is required")
        side_l = str(side or "").lower()
        if side_l not in ("yes", "no"):
            raise CapRejected("side must be yes|no")
        self._check_caps(price=price, count=count, volume=volume)
        client_order_id = f"sifta-usd-{uuid.uuid4().hex[:16]}"
        # V2 CreateOrder: YES-book only. bid=buy YES; ask=sell YES ≡ buy NO at 1-p
        # Cross ~5¢ for taker fill (2¢ still left many usd_no_fill on thin 15m books)
        p = float(price)
        cross = 0.05
        if side_l == "yes":
            book_side = "bid"
            yes_px = min(0.99, p + cross)
        else:
            book_side = "ask"
            yes_px = max(0.01, min(0.99, (1.0 - p) - cross))
        yes_px = round(yes_px, 4)
        # Fixed-point strings required by V2
        count_s = f"{float(count):.2f}"
        price_s = f"{yes_px:.4f}"
        body = {
            "ticker": str(ticker),
            "client_order_id": client_order_id,
            "side": book_side,
            "count": count_s,
            "price": price_s,
            # IOC + cross = take liquidity now (owner: want positions on Safari)
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
        }
        cost = round(p * int(count), 4)
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "env": "prod",
                "client_order_id": client_order_id,
                "ticker": ticker,
                "side": side_l,
                "book_side": book_side,
                "price": p,
                "yes_price": yes_px,
                "count": int(count),
                "cost_usd": cost,
                "body": body,
                "ts": time.time(),
                "truth_label": TRUTH,
                "note": "DRY_RUN — not sent (V2 events/orders)",
            }

        from System.kalshi_credentials import credentials_status

        if not credentials_status().get("ready"):
            raise NotProvisioned("prod keys not ready")

        # V2 only — legacy /portfolio/orders returns 410 Gone
        resp = self._request(
            "POST",
            "/portfolio/events/orders",
            body=body,
            write=True,
            _caps_checked=True,
        )

        order = resp.get("order") if isinstance(resp.get("order"), dict) else resp
        fill_raw = resp.get("fill_count")
        if fill_raw is None and isinstance(order, dict):
            fill_raw = order.get("fill_count_fp") or order.get("fill_count")
        remaining_raw = resp.get("remaining_count")
        if remaining_raw is None and isinstance(order, dict):
            remaining_raw = order.get("remaining_count_fp") or order.get("remaining_count")
        average_fill_raw = resp.get("average_fill_price")
        if average_fill_raw is None and isinstance(order, dict):
            average_fill_raw = order.get("average_fill_price")
        average_fee_raw = resp.get("average_fee_paid")
        if average_fee_raw is None and isinstance(order, dict):
            average_fee_raw = order.get("average_fee_paid")

        def _finite_float(value: Any, default: float = 0.0) -> float:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return default
            return parsed if math.isfinite(parsed) else default

        fill_count = max(0.0, _finite_float(fill_raw))
        remaining_count = max(0.0, _finite_float(remaining_raw))
        # V2 CreateOrder quotes average_fill_price on the YES book always.
        # bid fill @ Y = buy YES @ Y; ask fill @ Y = sell YES @ Y ≡ buy NO @ (1-Y).
        # See Kalshi Create Order V2 — never treat YES-book fill as NO premium.
        yes_fill_price = (
            _finite_float(average_fill_raw, max(0.01, min(0.99, 1.0 - p if side_l == "no" else p)))
            if fill_count > 0
            else None
        )
        if yes_fill_price is not None:
            yes_fill_price = round(max(0.01, min(0.99, float(yes_fill_price))), 4)
        if fill_count > 0 and yes_fill_price is not None:
            if side_l == "no":
                side_price = round(max(0.01, min(0.99, 1.0 - float(yes_fill_price))), 4)
            else:
                side_price = float(yes_fill_price)
        else:
            side_price = p
        average_fee_paid = (
            max(0.0, _finite_float(average_fee_raw)) if fill_count > 0 else 0.0
        )
        premium_usd = round(fill_count * float(side_price or 0.0), 4)
        fee_paid_usd = round(fill_count * average_fee_paid, 4)
        actual_cost_usd = round(premium_usd + fee_paid_usd, 4)
        row = {
            "ok": True,
            "dry_run": False,
            "env": "prod",
            "client_order_id": client_order_id,
            "order_id": (order or {}).get("order_id") or resp.get("order_id"),
            "ticker": ticker,
            "side": side_l,
            "book_side": book_side,
            # `price` = contract premium on the side we bought (YES or NO dollars)
            "price": side_price if fill_count > 0 else p,
            "side_price": side_price if fill_count > 0 else p,
            "limit_price": p,
            "yes_price": yes_px,
            "yes_fill_price": yes_fill_price,
            "count": int(count),
            "cost_usd": actual_cost_usd,
            "premium_usd": premium_usd,
            "fee_paid_usd": fee_paid_usd,
            "fill_count": fill_count,
            "remaining_count": remaining_count,
            # raw API YES-book fill (do not use as NO premium)
            "average_fill_price": yes_fill_price,
            "average_fee_paid": average_fee_paid,
            "filled": fill_count > 0,
            "response_keys": list(resp.keys())[:20] if isinstance(resp, dict) else [],
            "ts": time.time(),
            "truth_label": TRUTH,
            "api": "CreateOrderV2",
            "price_convention": "side_premium_not_yes_book",
        }
        if fill_count > 0:
            self.open_count += 1
            self.open_exposure_usd = round(self.open_exposure_usd + actual_cost_usd, 4)
        return row

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        if kill_switch_active(state_dir=self.state_dir):
            raise KillSwitchActive("halt before sign")
        oid = str(order_id)
        resp = self._request(
            "DELETE", f"/portfolio/events/orders/{oid}", write=True
        )
        return {
            "ok": True,
            "cancelled": oid,
            "response_keys": list(resp)[:12] if isinstance(resp, dict) else [],
            "ts": time.time(),
        }


def build_reduce_only_cashout_order(
    *,
    ticker: str,
    hold_side: str,
    exit_yes_price: float,
    count: float = 1.0,
    client_order_id: Optional[str] = None,
) -> dict[str, Any]:
    """INERT V2 cash-out body — never transmits.

    Hold YES → ask (sell YES). Hold NO → bid (buy YES / close NO).
    Uses reduce_only + IOC so a future live path cannot flip position.
    Fees apply again on exit (see alice_15m_scalp_learner.estimate_taker_fee).

    r1653 / Codex joint: real exits disabled until separate owner GO.
    """
    raw_side = str(hold_side).strip().lower()
    if raw_side not in {"yes", "up", "no", "down"}:
        raise CapRejected("cash-out hold_side must be yes/up/no/down")
    if not str(ticker).strip():
        raise CapRejected("cash-out ticker required")
    try:
        count_f = float(count)
        yes_raw = float(exit_yes_price)
    except (TypeError, ValueError) as exc:
        raise CapRejected("cash-out count/price must be finite numbers") from exc
    if not math.isfinite(count_f) or count_f <= 0.0:
        raise CapRejected("cash-out count must be positive")
    if not math.isfinite(yes_raw) or not 0.0 < yes_raw < 1.0:
        raise CapRejected("cash-out YES price must be between 0 and 1")
    side_l = "yes" if raw_side in ("yes", "up") else "no"
    # YES-book: sell YES to exit long YES; buy YES to exit long NO
    book_side = "ask" if side_l == "yes" else "bid"
    yes_px = round(max(0.01, min(0.99, yes_raw)), 4)
    cid = client_order_id or f"sifta-cashout-inert-{uuid.uuid4().hex[:12]}"
    body = {
        "ticker": str(ticker),
        "client_order_id": cid,
        "side": book_side,
        "count": f"{count_f:.2f}",
        "price": f"{yes_px:.4f}",
        "time_in_force": "immediate_or_cancel",
        "self_trade_prevention_type": "taker_at_cross",
        "reduce_only": True,
    }
    return {
        "ok": True,
        "inert": True,
        "transmits": False,
        "hold_side": side_l,
        "book_side": book_side,
        "yes_price": yes_px,
        "body": body,
        "note": (
            "INERT reduce_only cash-out builder — not signed, not POSTed. "
            "Call KalshiProdTradeClient.execute_reduce_only_cashout to transmit."
        ),
        "api": "CreateOrderV2",
        "truth_label": TRUTH,
        "ts": time.time(),
    }


# Monkey-patch method onto class after def for clarity
def _execute_reduce_only_cashout(
    self: "KalshiProdTradeClient",
    *,
    ticker: str,
    hold_side: str,
    exit_yes_price: float,
    count: float = 1.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """LIVE reduce-only IOC cash-out (owner lesson: take profits on green).

    Requires kill switch OFF. Crosses ~3¢ for fill. Fees paid again on exit.
    """
    if kill_switch_active(state_dir=self.state_dir):
        raise KillSwitchActive("halt before cash-out sign")
    plan = build_reduce_only_cashout_order(
        ticker=ticker,
        hold_side=hold_side,
        exit_yes_price=exit_yes_price,
        count=count,
    )
    body = dict(plan["body"])
    # Taker cross for exit fill
    yes_px = float(plan["yes_price"])
    side_l = plan["hold_side"]
    cross = 0.03
    if side_l == "yes":
        # selling YES: lower ask to hit bids
        yes_px = max(0.01, yes_px - cross)
    else:
        # buying YES to close NO: raise bid
        yes_px = min(0.99, yes_px + cross)
    yes_px = round(yes_px, 4)
    body["price"] = f"{yes_px:.4f}"
    body["client_order_id"] = f"sifta-cashout-{uuid.uuid4().hex[:14]}"
    if dry_run:
        return {
            **plan,
            "ok": True,
            "dry_run": True,
            "inert": False,
            "transmits": False,
            "yes_price": yes_px,
            "body": body,
            "note": "DRY_RUN cash-out — not sent",
        }
    from System.kalshi_credentials import credentials_status

    if not credentials_status().get("ready"):
        raise NotProvisioned("prod keys not ready")
    resp = self._request(
        "POST",
        "/portfolio/events/orders",
        body=body,
        write=True,
        _caps_checked=True,  # reduce-only exit; not a new risk open
    )
    order = resp.get("order") if isinstance(resp.get("order"), dict) else resp

    def _ff(value: Any, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if math.isfinite(parsed) else default

    fill_raw = resp.get("fill_count")
    if fill_raw is None and isinstance(order, dict):
        fill_raw = order.get("fill_count_fp") or order.get("fill_count")
    avg_raw = resp.get("average_fill_price")
    if avg_raw is None and isinstance(order, dict):
        avg_raw = order.get("average_fill_price")
    fee_raw = resp.get("average_fee_paid")
    if fee_raw is None and isinstance(order, dict):
        fee_raw = order.get("average_fee_paid")
    fill_count = max(0.0, _ff(fill_raw))
    yes_fill = _ff(avg_raw, yes_px) if fill_count > 0 else None
    if yes_fill is not None:
        yes_fill = round(max(0.01, min(0.99, yes_fill)), 4)
    # Exit proceeds on our side
    if side_l == "yes" and yes_fill is not None:
        exit_side = yes_fill
    elif side_l == "no" and yes_fill is not None:
        exit_side = round(1.0 - yes_fill, 4)
    else:
        exit_side = None
    fee_paid = round(fill_count * max(0.0, _ff(fee_raw)), 4) if fill_count > 0 else 0.0
    return {
        "ok": True,
        "dry_run": False,
        "inert": False,
        "transmits": True,
        "event": "usd_cashout",
        "ticker": ticker,
        "hold_side": side_l,
        "book_side": plan["book_side"],
        "yes_price_limit": yes_px,
        "yes_fill_price": yes_fill,
        "exit_side_price": exit_side,
        "fill_count": fill_count,
        "filled": fill_count > 0,
        "fee_paid_usd": fee_paid,
        "order_id": (order or {}).get("order_id") or resp.get("order_id"),
        "client_order_id": body["client_order_id"],
        "body": body,
        "ts": time.time(),
        "truth_label": TRUTH,
        "api": "CreateOrderV2",
        "note": "LIVE reduce_only cash-out — take profit path",
    }


KalshiProdTradeClient.execute_reduce_only_cashout = _execute_reduce_only_cashout  # type: ignore[attr-defined]


__all__ = [
    "KalshiProdTradeClient",
    "CapRejected",
    "KillSwitchActive",
    "NotProvisioned",
    "DemoHostForbidden",
    "kill_switch_active",
    "set_kill_switch",
    "assert_prod_url",
    "build_reduce_only_cashout_order",
    "MIN_ENTRY",
    "MAX_ENTRY",
    "MAX_OPEN",
    "MAX_NIGHT_LOSS_USD",
    "MAX_BUDGET_USD",
    "STAKE_USD",
    "MIN_VOLUME",
    "TRUTH",
]
