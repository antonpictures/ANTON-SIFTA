#!/usr/bin/env python3
"""Crypto market swimmers — carry signed market packets into the Rainman field.

r1637: Alice's crypto swimmers transport *verified* mid/volume/BTC-regime
snapshots (not rumors). Teeth/mouth metaphor = payload + signature.

Ledger: .sifta_state/alice_15m_crypto_swimmer_packets.jsonl
Latest:  .sifta_state/alice_15m_crypto_swimmer_latest.json

Does not place bets. Paper loop / Rainman *read* kalshi_15m_live.json;
this module *signs* what they saw so doctors can audit "what the swarm knew."
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
PACKET_LOG = "alice_15m_crypto_swimmer_packets.jsonl"
LATEST = "alice_15m_crypto_swimmer_latest.json"
TRUTH = "ALICE_CRYPTO_MARKET_SWIMMER_V1"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _sign_payload(payload: dict[str, Any]) -> str:
    """HMAC-less local integrity: sha256 of canonical JSON (swimmer tooth mark).

    Full ed25519 optional if swarm_swimmer_crypto available.
    """
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    try:
        from System import swarm_swimmer_crypto as sc

        if hasattr(sc, "sign_message"):
            return str(sc.sign_message(digest) or digest)
    except Exception:
        pass
    return digest


def swim_market_snapshot(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Read live 15m board, attach volume ranks + BTC regime, sign, append ledger."""
    root = _state(state_dir)
    live_p = root / "kalshi_15m_live.json"
    markets: list[dict[str, Any]] = []
    if live_p.exists():
        try:
            data = json.loads(live_p.read_text(encoding="utf-8"))
            markets = [m for m in (data.get("markets") or []) if isinstance(m, dict)]
        except Exception:
            markets = []

    rows = []
    btc_yes = None
    for m in markets:
        asset = str(m.get("asset") or "").upper()
        ky = m.get("kalshi_yes")
        if ky is None:
            ky = m.get("yes_price") or m.get("kalshi_chance_yes")
        try:
            ky_f = float(ky) if ky is not None else None
        except (TypeError, ValueError):
            ky_f = None
        vol = m.get("kalshi_volume_24h")
        if vol is None:
            vol = m.get("volume_24h") or m.get("volume") or 0
        try:
            vol_f = float(vol)
        except (TypeError, ValueError):
            vol_f = 0.0
        if asset == "BTC" and ky_f is not None:
            btc_yes = ky_f
        fav = max(ky_f, 1.0 - ky_f) if ky_f is not None else 0.0
        rows.append(
            {
                "asset": asset,
                "kalshi_yes": ky_f,
                "favorite": round(fav, 4),
                "fav_side": (
                    "UP" if ky_f is not None and ky_f >= 0.5 else "DOWN" if ky_f is not None else "?"
                ),
                "volume": round(vol_f, 2),
                "dust": vol_f < 500.0,
                "in_band": 0.70 <= fav <= 0.88 if fav else False,
            }
        )

    rows.sort(key=lambda r: -float(r.get("volume") or 0))
    packet_body = {
        "ts": time.time(),
        "truth_label": TRUTH,
        "n_markets": len(rows),
        "btc_yes": btc_yes,
        "btc_regime": (
            "UP"
            if btc_yes is not None and btc_yes >= 0.58
            else "DOWN"
            if btc_yes is not None and btc_yes <= 0.42
            else "CHOP"
        ),
        "dust_assets": [r["asset"] for r in rows if r.get("dust")],
        "band_assets": [r["asset"] for r in rows if r.get("in_band")],
        "markets": rows,
        "note": "swimmer packet — mid/volume for Rainman V9/V10; not a bet",
    }
    tooth = _sign_payload(packet_body)
    packet = {**packet_body, "tooth": tooth, "mouth": "crypto_market_swimmer"}

    root.mkdir(parents=True, exist_ok=True)
    with (root / PACKET_LOG).open("a", encoding="utf-8") as f:
        f.write(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n")
    (root / LATEST).write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return packet


def main() -> None:
    p = swim_market_snapshot()
    print(
        json.dumps(
            {
                "n": p.get("n_markets"),
                "btc_regime": p.get("btc_regime"),
                "dust": p.get("dust_assets"),
                "band": p.get("band_assets"),
                "tooth": str(p.get("tooth") or "")[:16] + "…",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
