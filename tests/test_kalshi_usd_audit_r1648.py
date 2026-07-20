from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import System.kalshi_usd_lane as lane
import System.ledger_deal as ledger_deal
from System.kalshi_usd_audit import (
    MIN_VERIFIED_FILLS,
    audit,
    maybe_write_periodic_audit,
)


def _state(tmp_path: Path, *, deal_epoch: float = 100.0) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "ledger_deal.json").write_text(
        json.dumps(
            {
                "ts": deal_epoch,
                "receipt_id": "r1648-ledger-deal-test",
                "truth_label": "LEDGER_DEAL_V1",
            }
        ),
        encoding="utf-8",
    )
    (state / "alice_fee_net_tournament.json").write_text(
        json.dumps(
            {"epoch_active": True, "usd_shadow_only": False, "usd_owner_override": True}
        ),
        encoding="utf-8",
    )
    from System.alice_fee_net_tournament import write_policy_hash
    write_policy_hash(state_dir=state)
    return state


def _place(
    ticker: str,
    *,
    ts: float = 101.0,
    price: float = 0.58,
    filled: bool = True,
    fill_count: float = 1.0,
    score: float | None = 0.91,
) -> dict[str, object]:
    row: dict[str, object] = {
        "event": "usd_place",
        "ticker": ticker,
        "order_id": f"order-{ticker}",
        "ts": ts,
        "price": price,
        "rainman_action": "fire",
        "filled": filled,
        "fill_count": fill_count,
    }
    if score is not None:
        row["rainman_score"] = score
    return row


def test_predeal_missing_fill_proof_is_historical_not_live_evidence(tmp_path: Path) -> None:
    state = _state(tmp_path)
    old = {
        "event": "usd_place",
        "ticker": "KXBTC15M-26JUL130015-15",
        "ts": 99.0,
        "price": 0.75,
    }

    result = audit(rows=[old], state_dir=state)

    assert result["verdict"] == "UNDERPOWERED"
    assert result["n_predeal_placements"] == 1
    assert result["n_postdeal_placements"] == 0
    assert result["n_unverified_predeal_placements"] == 1
    assert result["n_verified_postdeal_fills"] == 0
    assert result["findings"] == []


def test_postdeal_expensive_placement_fails_scalp_band(tmp_path: Path) -> None:
    """r1686 scalp band 40–68¢; 80¢ is high-on-drugs out-of-band."""
    state = _state(tmp_path)
    result = audit(
        rows=[_place("KXBTC15M-26JUL130015-15", price=0.80)],
        state_dir=state,
    )

    assert result["verdict"] == "FAIL"
    assert any(item["check"] == "price_band" for item in result["findings"])


def test_explicit_zero_fill_is_not_verified_evidence(tmp_path: Path) -> None:
    state = _state(tmp_path)
    result = audit(
        rows=[
            _place(
                "KXBTC15M-26JUL130015-15",
                filled=False,
                fill_count=0.0,
            )
        ],
        state_dir=state,
    )

    assert result["verdict"] == "UNDERPOWERED"
    assert result["n_explicit_zero_fills"] == 1
    assert result["n_verified_postdeal_fills"] == 0
    assert result["findings"] == []


def test_postdeal_missing_rainman_score_fails(tmp_path: Path) -> None:
    state = _state(tmp_path)
    result = audit(
        rows=[_place("KXBTC15M-26JUL130015-15", score=None)],
        state_dir=state,
    )

    assert result["verdict"] == "FAIL"
    assert any(item["check"] == "rainman_score" for item in result["findings"])


def test_three_max_uses_complete_cross_asset_window_key(tmp_path: Path) -> None:
    """r1726: max_open lock is ledger MAX_OPEN (4) — 5 fills in one window FAIL."""
    state = _state(tmp_path)
    assets = ("BTC", "ETH", "SOL", "BNB", "XRP")  # MAX_OPEN+1
    rows = [
        _place(f"KX{asset}15M-26JUL130015-15", ts=101.0 + index)
        for index, asset in enumerate(assets)
    ]

    result = audit(rows=rows, state_dir=state)

    assert result["max_open_seen_per_window"] == 5
    assert result["window_fill_counts"] == {"26JUL130015-15": 5}
    assert result["verdict"] == "FAIL"
    assert any(item["check"] == "max_open_lock" for item in result["findings"])


def test_same_last_suffix_does_not_merge_distinct_windows(tmp_path: Path) -> None:
    state = _state(tmp_path)
    rows = [
        _place("KXBTC15M-26JUL130015-15", ts=101.0),
        _place("KXETH15M-26JUL130015-15", ts=102.0),
        _place("KXSOL15M-26JUL130115-15", ts=103.0),
        _place("KXBNB15M-26JUL130115-15", ts=104.0),
    ]

    result = audit(rows=rows, state_dir=state)

    assert result["max_open_seen_per_window"] == 2
    assert result["verdict"] == "UNDERPOWERED"


def test_verdict_stays_underpowered_until_50_verified_fills(tmp_path: Path) -> None:
    state = _state(tmp_path)
    rows = [
        _place(
            f"KXBTC15M-26JUL13{i:04d}-{i % 60:02d}",
            ts=101.0 + i,
        )
        for i in range(MIN_VERIFIED_FILLS - 1)
    ]
    for index, row in enumerate(rows):
        row["order_id"] = f"order-{index}"

    assert audit(rows=rows, state_dir=state)["verdict"] == "UNDERPOWERED"

    final = _place("KXBTC15M-26JUL140000-00", ts=200.0)
    final["order_id"] = "order-final"
    assert audit(rows=[*rows, final], state_dir=state)["verdict"] == "CLEAN"


def test_lane_only_literal_true_arms_and_snapshot_replace_is_atomic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(tmp_path)
    lane_path = state / lane.LANE_FILE
    lane_path.write_text('{"armed": "false"}', encoding="utf-8")
    assert lane.is_usd_lane_armed(state) is False
    lane_path.write_text('{"armed": 1}', encoding="utf-8")
    assert lane.is_usd_lane_armed(state) is False

    replacements: list[tuple[Path, Path]] = []
    real_replace = lane.os.replace

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(lane.os, "replace", recording_replace)
    assert lane.set_usd_lane_armed("true", state_dir=state)["armed"] is False
    assert lane.set_usd_lane_armed(True, state_dir=state)["armed"] is True
    assert lane.is_usd_lane_armed(state) is True
    assert len(replacements) == 2
    assert all(source.parent == destination.parent == state for source, destination in replacements)
    assert not list(state.glob("*.tmp"))
    assert json.loads(lane_path.read_text(encoding="utf-8"))["armed"] is True


def test_periodic_audit_appends_exactly_once_per_local_am_pm(tmp_path: Path) -> None:
    state = _state(tmp_path, deal_epoch=1.0)
    ledger = state / "kalshi_usd_live_ledger.jsonl"
    ledger.write_text("", encoding="utf-8")
    am = datetime(2026, 7, 13, 9, 0, 0).timestamp()
    pm = datetime(2026, 7, 13, 15, 0, 0).timestamp()

    first_am = maybe_write_periodic_audit(state_dir=state, now=am)
    second_am = maybe_write_periodic_audit(state_dir=state, now=am + 60.0)
    first_pm = maybe_write_periodic_audit(state_dir=state, now=pm)
    second_pm = maybe_write_periodic_audit(state_dir=state, now=pm + 60.0)

    assert first_am["written"] is True
    assert second_am["written"] is False
    assert first_pm["written"] is True
    assert second_pm["written"] is False
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    evidence = [row for row in rows if row.get("event") == "evidence_audit"]
    assert [row["audit_period"] for row in evidence] == ["AM", "PM"]
    assert len(evidence) == 2
    assert all(row["verdict"] == "UNDERPOWERED" for row in evidence)
    assert all(row["verified_fills"] == 0 for row in evidence)
    # r1726: eligible stake tracks ledger STAKE_USD / ammo default ($2)
    assert all(
        row["eligible_stake_usd"] == float(ledger_deal.STAKE_USD) for row in evidence
    )
    assert all(row["evidence_threshold_fills"] == 50 for row in evidence)
    assert all(row["explicit_owner_next_tier_required"] is True for row in evidence)
    assert (state / "kalshi_usd_audit.md").exists()


def test_ledger_deal_periodic_audit_forwarder_is_lazy(tmp_path: Path, monkeypatch) -> None:
    state = _state(tmp_path)
    calls: list[tuple[Path | str, float | None]] = []

    def fake_write(*, state_dir: Path | str, now: float | None = None):
        calls.append((state_dir, now))
        return {"written": True, "segment": "2026-07-13:AM"}

    monkeypatch.setattr("System.kalshi_usd_audit.maybe_write_periodic_audit", fake_write)

    result = ledger_deal.maybe_write_periodic_audit(state_dir=state, now=123.0)

    assert result == {"written": True, "segment": "2026-07-13:AM"}
    assert calls == [(state, 123.0)]
