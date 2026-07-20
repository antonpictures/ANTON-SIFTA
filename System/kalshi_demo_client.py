#!/usr/bin/env python3
"""Kalshi DEMO Trade API client — mock money only (r1632 R1/R2).

IRON BOUNDARY
  • BASE is hardcoded to the Kalshi DEMO host.
  • Any URL containing production hosts raises RuntimeError before network.
  • Real $10 (R4) is NOT in this module. George arms that later, alone.
  • Private keys: macOS Keychain service ``sifta.kalshi.demo`` only.
  • Kill switch: ``.sifta_state/kalshi_kill_switch.json`` ``{"halt": true}``.

Usage:
  python3 System/kalshi_demo_client.py --status
  python3 System/kalshi_demo_client.py --self-test
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE = ROOT / ".sifta_state"
API_LOG = "kalshi_demo_api.jsonl"
KILL_SWITCH = "kalshi_kill_switch.json"
DEMO_LEDGER = "kalshi_demo_ledger.jsonl"

# ── Environment lock (DEMO ONLY) ──────────────────────────────────────
ENV = "demo"
DEMO_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"
# Legacy demo host still documented — never use as default, but allow list for tests
_ALLOWED_HOST_FRAGMENTS = (
    "external-api.demo.kalshi.co",
    "demo-api.kalshi.co",
)
_PROD_FORBIDDEN = (
    "external-api.kalshi.com",
    "api.elections.kalshi.com",
    "trading-api.kalshi.com",
    "api.kalshi.com",
)

KEYCHAIN_SERVICE = "sifta.kalshi.demo"
KEYCHAIN_ACCOUNT_KEY_ID = "api_key_id"
KEYCHAIN_ACCOUNT_PEM = "private_key_pem"

# Hard caps (client boundary — not caller-trust)
MAX_OPEN = 3
MAX_DAILY_LOSS_MOCK_USD = 5.0
STAKE_MOCK_USD = 1.0
MIN_ENTRY = 0.70
MAX_ENTRY = 0.88
MAX_CONTRACTS = 1

# Token bucket (Basic tier-ish: conservative)
READ_BUDGET_PER_S = 20.0   # soft client cap (far below Basic 200)
WRITE_BUDGET_PER_S = 5.0
TOKEN_COST_DEFAULT = 10.0

TRUTH = "KALSHI_DEMO_CLIENT_V1"


class ProdHostForbidden(RuntimeError):
    """Production Kalshi hosts are forbidden in the demo client."""


class KillSwitchActive(RuntimeError):
    """Write refused — kill switch file is armed."""


class NotProvisioned(RuntimeError):
    """Demo API keys not installed in Keychain."""


class CapRejected(RuntimeError):
    """Order violated hard caps (price band, size, open, loss)."""


def _forbid_prod(url: str) -> None:
    u = str(url or "").lower()
    for frag in _PROD_FORBIDDEN:
        if frag in u:
            raise ProdHostForbidden(
                f"r1632 iron boundary: production host forbidden in demo client: {frag}"
            )


def assert_demo_url(url: str) -> str:
    _forbid_prod(url)
    host = (urlparse(url).hostname or "").lower()
    if not any(a in host for a in ("demo.kalshi", "demo-api.kalshi")):
        # absolute demo path under DEMO_BASE is fine
        if not str(url).startswith(DEMO_BASE) and "demo" not in host:
            raise ProdHostForbidden(f"non-demo host refused: {host or url}")
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
        return False


def set_kill_switch(halt: bool, *, reason: str = "", state_dir: Path | str = STATE) -> Path:
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    p = root / KILL_SWITCH
    p.write_text(
        json.dumps(
            {"halt": bool(halt), "ts": time.time(), "reason": reason, "truth_label": TRUTH},
            indent=2,
        ),
        encoding="utf-8",
    )
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
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _keychain_get(account: str) -> Optional[str]:
    """Read a generic password from macOS Keychain. Returns None if missing."""
    if sys.platform != "darwin":
        return os.environ.get(f"SIFTA_KALSHI_DEMO_{account.upper()}")
    try:
        out = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return os.environ.get(f"SIFTA_KALSHI_DEMO_{account.upper()}")
        return (out.stdout or "").strip() or None
    except Exception:
        return os.environ.get(f"SIFTA_KALSHI_DEMO_{account.upper()}")


def load_demo_credentials() -> tuple[Optional[str], Optional[str]]:
    """Return (api_key_id, private_key_pem) or (None, None) if not provisioned."""
    key_id = _keychain_get(KEYCHAIN_ACCOUNT_KEY_ID)
    pem = _keychain_get(KEYCHAIN_ACCOUNT_PEM)
    # Also allow explicit env for CI (still never prod)
    key_id = key_id or os.environ.get("SIFTA_KALSHI_DEMO_API_KEY_ID")
    pem = pem or os.environ.get("SIFTA_KALSHI_DEMO_PRIVATE_KEY_PEM")
    if key_id and pem:
        return key_id.strip(), pem.strip()
    return None, None


def is_provisioned() -> bool:
    k, p = load_demo_credentials()
    return bool(k and p and "BEGIN" in p)


def sign_request(
    private_key_pem: str,
    *,
    timestamp_ms: str,
    method: str,
    path: str,
) -> str:
    """RSA-PSS SHA256 sign of ``timestamp + method + path`` (no query)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    # Strip query from path per Kalshi docs
    path_only = path.split("?", 1)[0]
    if not path_only.startswith("/"):
        path_only = "/" + path_only
    message = f"{timestamp_ms}{method.upper()}{path_only}".encode("utf-8")
    key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    sig = key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("ascii")


def _sign_path_for_url(base: str, rel_path: str) -> str:
    """Full path from API root for signing, e.g. /trade-api/v2/portfolio/balance."""
    rel = rel_path if rel_path.startswith("/") else f"/{rel_path}"
    # DEMO_BASE already ends with /trade-api/v2
    full = urlparse(base.rstrip("/") + rel).path
    return full


class KalshiDemoClient:
    """Read/write client locked to Kalshi DEMO."""

    def __init__(self, *, state_dir: Path | str = STATE, base: str = DEMO_BASE) -> None:
        assert_demo_url(base)
        self.base = base.rstrip("/")
        self.state_dir = Path(state_dir)
        self.read_bucket = TokenBucket(READ_BUDGET_PER_S, READ_BUDGET_PER_S * 2)
        self.write_bucket = TokenBucket(WRITE_BUDGET_PER_S, WRITE_BUDGET_PER_S * 2)
        self._open_orders: dict[str, dict[str, Any]] = {}
        self._daily_pnl_mock = 0.0
        self._day_key = time.strftime("%Y-%m-%d")

    def status(self) -> dict[str, Any]:
        prov = is_provisioned()
        return {
            "truth_label": TRUTH,
            "env": ENV,
            "base": self.base,
            "provisioned": prov,
            "kill_switch": kill_switch_active(state_dir=self.state_dir),
            "max_open": MAX_OPEN,
            "max_daily_loss_mock_usd": MAX_DAILY_LOSS_MOCK_USD,
            "stake_mock_usd": STAKE_MOCK_USD,
            "entry_band": [MIN_ENTRY, MAX_ENTRY],
            "open_orders": len(self._open_orders),
            "daily_pnl_mock": self._daily_pnl_mock,
            "note": "DEMO mock money only · Kalshi production USD OFF · R4 not in this client",
        }

    def _auth_headers(self, method: str, rel_path: str) -> dict[str, str]:
        key_id, pem = load_demo_credentials()
        if not key_id or not pem:
            raise NotProvisioned(
                "Install demo keys in Keychain service "
                f"'{KEYCHAIN_SERVICE}' (api_key_id + private_key_pem) "
                "or set SIFTA_KALSHI_DEMO_API_KEY_ID / SIFTA_KALSHI_DEMO_PRIVATE_KEY_PEM"
            )
        ts = str(int(time.time() * 1000))
        sign_path = _sign_path_for_url(self.base, rel_path)
        sig = sign_request(pem, timestamp_ms=ts, method=method, path=sign_path)
        return {
            "KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SIFTA-Alice-KalshiDemo/1.0 (r1632; mock-only)",
        }

    def _request(
        self,
        method: str,
        rel_path: str,
        *,
        body: Optional[dict] = None,
        write: bool = False,
        timeout: float = 12.0,
    ) -> dict[str, Any]:
        assert_demo_url(self.base)
        if write and kill_switch_active(state_dir=self.state_dir):
            raise KillSwitchActive("kalshi_kill_switch.json halt=true — write refused before sign")
        bucket = self.write_bucket if write else self.read_bucket
        if not bucket.wait_and_take(TOKEN_COST_DEFAULT, timeout=3.0):
            raise RuntimeError("rate_limit_token_bucket_empty")

        rel = rel_path if rel_path.startswith("/") else f"/{rel_path}"
        url = self.base + rel
        assert_demo_url(url)
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
                    "env": ENV,
                },
                state_dir=self.state_dir,
            )
            if exc.code == 429:
                time.sleep(0.05)
            raise
        except URLError as exc:
            _append_api_log(
                {
                    "ts": time.time(),
                    "method": method,
                    "path": rel,
                    "error": str(exc.reason)[:200],
                    "write": write,
                    "env": ENV,
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
                "env": ENV,
            },
            state_dir=self.state_dir,
        )
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    # ── Reads ─────────────────────────────────────────────────────────
    def get_balance(self) -> dict[str, Any]:
        return self._request("GET", "/portfolio/balance")

    def get_positions(self) -> dict[str, Any]:
        return self._request("GET", "/portfolio/positions")

    def get_fills(self, *, limit: int = 20) -> dict[str, Any]:
        return self._request("GET", f"/portfolio/fills?limit={int(limit)}")

    def get_market(self, ticker: str) -> dict[str, Any]:
        t = str(ticker or "").strip()
        return self._request("GET", f"/markets/{t}")

    # ── Writes (demo) ─────────────────────────────────────────────────
    def _roll_day(self) -> None:
        k = time.strftime("%Y-%m-%d")
        if k != self._day_key:
            self._day_key = k
            self._daily_pnl_mock = 0.0

    def _check_caps(self, *, price: float, side: str, count: int) -> None:
        self._roll_day()
        p = float(price)
        if p < MIN_ENTRY - 1e-9 or p > MAX_ENTRY + 1e-9:
            raise CapRejected(f"price_band {p} outside {MIN_ENTRY}-{MAX_ENTRY}")
        if int(count) > MAX_CONTRACTS:
            raise CapRejected(f"max_contracts {MAX_CONTRACTS}")
        if len(self._open_orders) >= MAX_OPEN:
            raise CapRejected(f"max_open {MAX_OPEN}")
        if self._daily_pnl_mock <= -MAX_DAILY_LOSS_MOCK_USD:
            raise CapRejected(f"max_daily_loss_mock ${MAX_DAILY_LOSS_MOCK_USD}")

    def place_limit_order(
        self,
        *,
        ticker: str,
        side: str,
        price: float,
        count: int = 1,
        action: str = "buy",
    ) -> dict[str, Any]:
        """Place a DEMO limit order (1 contract). Refuses if kill switch / caps."""
        if kill_switch_active(state_dir=self.state_dir):
            raise KillSwitchActive("halt before sign")
        side_l = str(side or "").lower()
        if side_l not in ("yes", "no"):
            raise CapRejected("side must be yes|no")
        self._check_caps(price=price, side=side_l, count=count)
        client_order_id = f"sifta-{uuid.uuid4().hex[:16]}"
        # Kalshi price is in cents integer for many order APIs
        yes_price = int(round(float(price) * 100)) if side_l == "yes" else int(round((1.0 - float(price)) * 100))
        body = {
            "ticker": str(ticker),
            "client_order_id": client_order_id,
            "side": side_l,
            "action": action,
            "count": int(count),
            "type": "limit",
            "yes_price": yes_price if side_l == "yes" else None,
            "no_price": yes_price if side_l == "no" else None,
        }
        # Clean nulls
        body = {k: v for k, v in body.items() if v is not None}
        if not is_provisioned():
            # Shadow receipt without network — still enforces caps/kill
            row = {
                "ok": True,
                "shadow": True,
                "env": ENV,
                "client_order_id": client_order_id,
                "ticker": ticker,
                "side": side_l,
                "price": float(price),
                "count": int(count),
                "ts": time.time(),
                "truth_label": TRUTH,
                "note": "NOT_PROVISIONED — order not sent; caps/kill checked",
            }
            self._open_orders[client_order_id] = row
            self._ledger(row)
            return row
        try:
            resp = self._request("POST", "/portfolio/orders", body=body, write=True)
        except Exception as exc:
            # V2 path fallback documented in changelog
            try:
                resp = self._request(
                    "POST", "/portfolio/events/orders", body=body, write=True
                )
            except Exception:
                raise exc
        row = {
            "ok": True,
            "shadow": False,
            "env": ENV,
            "client_order_id": client_order_id,
            "ticker": ticker,
            "side": side_l,
            "price": float(price),
            "count": int(count),
            "response": {k: resp.get(k) for k in list(resp)[:12]} if isinstance(resp, dict) else {},
            "ts": time.time(),
            "truth_label": TRUTH,
        }
        self._open_orders[client_order_id] = row
        self._ledger(row)
        return row

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        if kill_switch_active(state_dir=self.state_dir):
            raise KillSwitchActive("halt before sign")
        oid = str(order_id)
        if oid in self._open_orders and self._open_orders[oid].get("shadow"):
            self._open_orders.pop(oid, None)
            row = {"ok": True, "shadow": True, "cancelled": oid, "ts": time.time()}
            self._ledger(row)
            return row
        if not is_provisioned():
            return {"ok": False, "reason": "NOT_PROVISIONED"}
        resp = self._request("DELETE", f"/portfolio/orders/{oid}", write=True)
        self._open_orders.pop(oid, None)
        row = {"ok": True, "cancelled": oid, "response": resp, "ts": time.time()}
        self._ledger(row)
        return row

    def _ledger(self, row: dict[str, Any]) -> None:
        root = self.state_dir
        root.mkdir(parents=True, exist_ok=True)
        with (root / DEMO_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_self_test() -> dict[str, Any]:
    """Offline unit-style checks — no real keys required."""
    results: dict[str, Any] = {"truth_label": TRUTH, "tests": {}}

    # 1) prod URL raises
    try:
        assert_demo_url("https://external-api.kalshi.com/trade-api/v2/portfolio/balance")
        results["tests"]["prod_forbidden"] = "FAIL_no_raise"
    except ProdHostForbidden:
        results["tests"]["prod_forbidden"] = "PASS"

    # 2) demo URL ok
    try:
        assert_demo_url(DEMO_BASE)
        results["tests"]["demo_allowed"] = "PASS"
    except Exception as exc:
        results["tests"]["demo_allowed"] = f"FAIL_{exc}"

    # 3) kill switch blocks write
    import tempfile

    td = Path(tempfile.mkdtemp())
    set_kill_switch(True, reason="self_test", state_dir=td)
    c = KalshiDemoClient(state_dir=td)
    try:
        c.place_limit_order(ticker="TEST-1", side="yes", price=0.75)
        results["tests"]["kill_switch"] = "FAIL_no_raise"
    except KillSwitchActive:
        results["tests"]["kill_switch"] = "PASS"
    set_kill_switch(False, reason="clear", state_dir=td)

    # 4) price band cap
    c2 = KalshiDemoClient(state_dir=td)
    try:
        c2.place_limit_order(ticker="TEST-2", side="yes", price=0.55)
        results["tests"]["price_band"] = "FAIL_no_raise"
    except CapRejected:
        results["tests"]["price_band"] = "PASS"

    # 5) RSA sign round-trip with ephemeral key
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        ts = "1700000000000"
        method = "GET"
        path = "/trade-api/v2/portfolio/balance"
        sig_b64 = sign_request(pem, timestamp_ms=ts, method=method, path=path)
        # verify
        pub = key.public_key()
        pub.verify(
            base64.b64decode(sig_b64),
            f"{ts}{method}{path}".encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256(),
        )
        results["tests"]["rsa_sign_verify"] = "PASS"
    except Exception as exc:
        results["tests"]["rsa_sign_verify"] = f"FAIL_{type(exc).__name__}:{exc}"

    # 6) shadow order when not provisioned + in band
    try:
        r = c2.place_limit_order(ticker="KXTEST", side="yes", price=0.74)
        results["tests"]["shadow_order"] = "PASS" if r.get("shadow") and r.get("ok") else f"FAIL_{r}"
        c2.cancel_order(r["client_order_id"])
    except Exception as exc:
        results["tests"]["shadow_order"] = f"FAIL_{exc}"

    results["all_pass"] = all(v == "PASS" for v in results["tests"].values())
    results["provisioned"] = is_provisioned()
    results["status"] = KalshiDemoClient().status()
    return results


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        out = run_self_test()
        print(json.dumps(out, indent=2))
        return 0 if out.get("all_pass") else 1
    if "--kill" in argv:
        set_kill_switch(True, reason="cli")
        print("kill switch ARMED")
        return 0
    if "--unkill" in argv:
        set_kill_switch(False, reason="cli")
        print("kill switch cleared")
        return 0
    # default --status
    c = KalshiDemoClient()
    st = c.status()
    print(json.dumps(st, indent=2))
    if st["provisioned"] and not st["kill_switch"]:
        try:
            bal = c.get_balance()
            print("--- demo balance ---")
            print(json.dumps(bal, indent=2)[:800])
        except Exception as exc:
            print(f"balance read: {type(exc).__name__}: {exc}")
    elif not st["provisioned"]:
        print(
            "\nNOT_PROVISIONED: install demo API key in Keychain:\n"
            f"  security add-generic-password -s {KEYCHAIN_SERVICE} "
            f"-a {KEYCHAIN_ACCOUNT_KEY_ID} -w '<api-key-id>'\n"
            f"  security add-generic-password -s {KEYCHAIN_SERVICE} "
            f"-a {KEYCHAIN_ACCOUNT_PEM} -w \"$(cat demo.pem)\"\n"
            "Kalshi USD production remains OFF."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
