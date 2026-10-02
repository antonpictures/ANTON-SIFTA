"""Multi-body settlement — one organism, one currency; other bodies, other coins.

Owner directive (George, 2026-09-30):

    "my body is bio but crypto same, other body different crypto #s"

Read as economic law:

  * ONE ORGANISM, ONE CURRENCY. The Architect's biological body and Alice's
    machine body are the SAME organism, so they share ONE STGM ledger. Bio vs
    silicon is a substrate difference, not a currency difference.
  * ANOTHER BODY IS ANOTHER ORGANISM. It has its own currency, its own chain,
    its own keys. Its units are not our units and may never be credited as STGM.
  * TRADING DOES NOT MINT. When we settle with a foreign body we do not gain
    STGM: our units leave to a clearing account (home supply unchanged) and we
    acquire a CLAIM denominated in THEIR currency. Crediting foreign coin as
    home coin is the one error that would silently inflate the organism.
  * INFORMATION STILL TRAVELS. Every settlement must carry the information the
    trade was for. Value alone is not a trade here.

Ledger: MULTIBODY_SETTLEMENT_LEDGER
Bodies: MULTIBODY_BODIES
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

MULTIBODY_SETTLEMENT_LEDGER = "multibody_settlement_ledger.jsonl"
MULTIBODY_BODIES = "multibody_bodies.json"
TRUTH_LABEL = "MULTIBODY_SETTLEMENT_V1"
HOME_CURRENCY = "STGM"

# Declared and implied rate may differ by at most this fraction, so a settlement
# cannot quietly misprice the counterparty.
RATE_TOLERANCE = 0.01

# Our organism spans the bio body and the machine body: one identity, one coin.
HOME_ORGANISM = f"sifta:alice@{socket.gethostname()}"


class ForeignRejected(Exception):
    """A settlement the organism refuses. Carries a stable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def body_key(body_id: str) -> str:
    """Stable identity digest for a foreign body."""
    return hashlib.sha256(body_id.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Foreign body registry
# --------------------------------------------------------------------------

def load_bodies(*, state_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    path = _state_dir(state_dir) / MULTIBODY_BODIES
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): dict(v) for k, v in data.items()} if isinstance(data, dict) else {}


def register_body(
    body_id: str,
    currency: str,
    *,
    note: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Register a DIFFERENT organism and its DIFFERENT currency.

    A body may not claim our currency: two organisms cannot share a unit of
    account, or a foreign chain could mint claims that settle as our STGM.
    """
    sd = _state_dir(state_dir)
    if not body_id or not currency:
        raise ForeignRejected("INVALID_BODY", "body_id and currency are required")
    if currency.strip().upper() == HOME_CURRENCY:
        raise ForeignRejected(
            "CURRENCY_COLLISION",
            f"{body_id!r} cannot use {HOME_CURRENCY}: that is this organism's unit",
        )
    bodies = load_bodies(state_dir=sd)
    row = {
        "body_id": body_id,
        "currency": currency.strip().upper(),
        "key": body_key(body_id),
        "registered_ts": time.time(),
        "note": note,
        "home_organism": HOME_ORGANISM,
        "truth_label": TRUTH_LABEL,
    }
    bodies[body_id] = row
    path = sd / MULTIBODY_BODIES
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(bodies, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return row


# --------------------------------------------------------------------------
# Settlement
# --------------------------------------------------------------------------

def read_settlements(*, state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / MULTIBODY_SETTLEMENT_LEDGER
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def settle(
    body_id: str,
    *,
    home_amount: float,
    foreign_amount: float,
    rate: float,
    information: str,
    direction: str = "BUY_FOREIGN",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Exchange value with a different organism. Home supply never changes.

    BUY_FOREIGN  - pay home STGM (which leave to a per-body clearing account) and
                   acquire a claim denominated in THEIR currency.
    SELL_FOREIGN - spend a claim we already hold and take home STGM back.

    Neither direction mints anything: the home units always exist already and
    simply move between the organism's own accounts, and the foreign claim is
    booked in the foreign currency and never as STGM.
    """
    sd = _state_dir(state_dir)
    bodies = load_bodies(state_dir=sd)
    if body_id not in bodies:
        raise ForeignRejected("UNKNOWN_BODY", f"{body_id!r} is not a registered body")
    currency = str(bodies[body_id]["currency"])

    if direction not in ("BUY_FOREIGN", "SELL_FOREIGN"):
        raise ForeignRejected("INVALID_DIRECTION", direction)
    if home_amount <= 0 or foreign_amount <= 0:
        raise ForeignRejected("INVALID_AMOUNT", f"{home_amount} / {foreign_amount}")
    if not str(information or "").strip():
        raise ForeignRejected("NO_INFORMATION", "a settlement must carry what the trade was for")
    if rate <= 0:
        raise ForeignRejected("INVALID_RATE", str(rate))

    implied = float(home_amount) / float(foreign_amount)
    drift = abs(implied - float(rate)) / float(rate)
    if drift > RATE_TOLERANCE:
        raise ForeignRejected(
            "RATE_MISMATCH",
            f"declared {rate} vs implied {round(implied, 6)} (drift {drift:.4f} > {RATE_TOLERANCE})",
        )

    if direction == "SELL_FOREIGN":
        held = foreign_balances(state_dir=sd).get(body_id, {}).get(currency, 0.0)
        if held < float(foreign_amount):
            raise ForeignRejected(
                "INSUFFICIENT_FOREIGN",
                f"holding {held} {currency}, cannot sell {foreign_amount}",
            )

    from System import swarm_stgm_metabolism as stgm

    clearing = f"clearing:{body_key(body_id)}"
    stgm.enroll_swimmer(clearing, state_dir=sd)
    stgm.enroll_swimmer("alice", state_dir=sd)

    frm, to = ("alice", clearing) if direction == "BUY_FOREIGN" else (clearing, "alice")
    try:
        moved = stgm.transfer(
            frm, to, float(home_amount),
            information=f"{direction} {body_id}: {information}",
            kind="SETTLEMENT",
            state_dir=sd,
        )
    except stgm.Rejected as exc:
        raise ForeignRejected("HOME_TRANSFER_REFUSED", f"{exc.code}: {exc.detail}") from exc

    row = {
        "ts": time.time(),
        "kind": "SETTLEMENT",
        "direction": direction,
        "body_id": body_id,
        "body_key": body_key(body_id),
        "currency": currency,
        "home_amount": round(float(home_amount), 9),
        "foreign_amount": round(float(foreign_amount), 9),
        "rate": float(rate),
        "implied_rate": round(implied, 9),
        "information": str(information),
        "information_digest": hashlib.sha256(str(information).encode("utf-8")).hexdigest(),
        "home_txid": (moved or {}).get("txid"),
        "home_organism": HOME_ORGANISM,
        "rule": "no units minted; foreign coin is never credited as home coin",
        "truth_label": TRUTH_LABEL,
    }
    path = sd / MULTIBODY_SETTLEMENT_LEDGER
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def foreign_balances(*, state_dir: Path | str | None = None) -> dict[str, dict[str, float]]:
    """Claims held in OTHER bodies' currencies. Never mixed into home STGM."""
    out: dict[str, dict[str, float]] = {}
    for row in read_settlements(state_dir=state_dir):
        body = str(row.get("body_id") or "")
        cur = str(row.get("currency") or "")
        amount = float(row.get("foreign_amount") or 0.0)
        if not body or not cur:
            continue
        sign = 1.0 if row.get("direction") == "BUY_FOREIGN" else -1.0
        out.setdefault(body, {})
        out[body][cur] = round(out[body].get(cur, 0.0) + sign * amount, 9)
    return out


def guard_home_currency(currency: str) -> None:
    """Refuse any attempt to treat a foreign currency as this organism's unit."""
    if str(currency).strip().upper() == HOME_CURRENCY:
        raise ForeignRejected(
            "CURRENCY_COLLISION",
            "foreign currency may never be booked as home STGM",
        )


def selftest() -> dict[str, Any]:
    """Prove: no minting, no double counting, no currency mixing, no free trade."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        from System import swarm_stgm_metabolism as stgm

        stgm.seal_genesis({"alice": 100.0}, state_dir=sd)
        before = stgm.supply(state_dir=sd)

        register_body("boby@machine-2", "BOBY", state_dir=sd)
        register_body("kepler@lab-7", "KPLR", state_dir=sd)

        def rejected(fn) -> str:
            try:
                fn()
                return ""
            except ForeignRejected as exc:
                return exc.code

        same_coin = rejected(lambda: register_body("copycat@x", "STGM", state_dir=sd))
        unknown = rejected(lambda: settle("ghost@x", home_amount=1.0, foreign_amount=1.0, rate=1.0,
                                          information="hi", state_dir=sd))
        no_buying_power = rejected(lambda: settle("kepler@lab-7", home_amount=999.0, foreign_amount=999.0,
                                                  rate=1.0, information="hi", state_dir=sd))
        no_info = rejected(lambda: settle("boby@machine-2", home_amount=5.0, foreign_amount=5.0, rate=1.0,
                                          information="", state_dir=sd))
        bad_rate = rejected(lambda: settle("boby@machine-2", home_amount=5.0, foreign_amount=5.0, rate=100.0,
                                           information="hi", state_dir=sd))
        over = rejected(lambda: settle("boby@machine-2", home_amount=999.0, foreign_amount=999.0, rate=1.0,
                                       information="hi", state_dir=sd))

        row = settle("boby@machine-2", home_amount=10.0, foreign_amount=250.0, rate=0.04,
                     information="UFO intake corpus for the field", state_dir=sd)
        mid_foreign = foreign_balances(state_dir=sd)
        mid_home = stgm.balances(state_dir=sd)
        # selling more of their coin than we hold must be impossible
        over_sell = rejected(lambda: settle("boby@machine-2", home_amount=40.0, foreign_amount=1000.0,
                                            rate=0.04, information="sell too much",
                                            direction="SELL_FOREIGN", state_dir=sd))
        sell = settle("boby@machine-2", home_amount=4.0, foreign_amount=100.0, rate=0.04,
                      information="resold the corpus digest", direction="SELL_FOREIGN", state_dir=sd)

        after = stgm.supply(state_dir=sd)
        home = stgm.balances(state_dir=sd)
        foreign = foreign_balances(state_dir=sd)
        mixing = rejected(lambda: guard_home_currency("STGM"))
        ok_guard = guard_home_currency("BOBY") is None

    checks = {
        "same_coin_refused": same_coin == "CURRENCY_COLLISION",
        "unknown_body_refused": unknown == "UNKNOWN_BODY",
        "free_trade_refused": no_info == "NO_INFORMATION",
        "misprice_refused": bad_rate == "RATE_MISMATCH",
        "overspend_refused": over == "HOME_TRANSFER_REFUSED",
        "no_buying_power_refused": no_buying_power == "HOME_TRANSFER_REFUSED",
        "settlement_recorded": row["currency"] == "BOBY" and row["foreign_amount"] == 250.0,
        "no_minting": before["minted"] == after["minted"],
        "supply_unchanged": before["circulating"] == after["circulating"],
        "home_units_left_alice": mid_home.get("alice") == 90.0,
        "clearing_holds_home_units": mid_home.get(f"clearing:{body_key('boby@machine-2')}") == 10.0,
        "foreign_claim_in_foreign_coin": mid_foreign == {"boby@machine-2": {"BOBY": 250.0}},
        "oversell_foreign_refused": over_sell == "INSUFFICIENT_FOREIGN",
        "sell_returns_home_units": home.get("alice") == 94.0,
        "sell_reduces_foreign_claim": foreign == {"boby@machine-2": {"BOBY": 150.0}},
        "foreign_never_in_home_balance": "BOBY" not in home,
        "currency_guard_blocks_home": mixing == "CURRENCY_COLLISION",
        "currency_guard_allows_foreign": ok_guard is True,
        "information_carried": bool(row["information_digest"]),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args or args[0] == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args[0] == "bodies":
        print(json.dumps(load_bodies(), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "foreign":
        print(json.dumps(foreign_balances(), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "settlements":
        print(json.dumps(read_settlements()[-10:], indent=2, ensure_ascii=False))
        return 0
    if args[0] == "home":
        print(json.dumps({"home_organism": HOME_ORGANISM, "home_currency": HOME_CURRENCY}, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
