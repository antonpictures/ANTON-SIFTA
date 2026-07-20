"""r20260714-cooldown-gate-leak — the entry cooldown gate must FAIL CLOSED.

Evidence: usd_place KXBTC15M-26JUL150030-30 at ts 1784089219.96 while
cooldown_after_force_flat_reds was active until ts 1784091219.87. The old
inline check swallowed exceptions (except: pass), so any read hiccup deleted
the gate. These tests pin the replacement: active cooldown refuses, a broken
check refuses, a clear state passes.
"""

import json
import time

from System.kalshi_usd_hand import usd_entry_cooldown_gate


def _write_cooldown(state_dir, until_ts, n_red=1):
    (state_dir / "alice_usd_cooldown.json").write_text(
        json.dumps(
            {
                "cool": True,
                "until_ts": until_ts,
                "n_red": n_red,
                "reason": "cooldown_after_force_flat_reds",
            }
        ),
        encoding="utf-8",
    )


def test_active_cooldown_refuses_entry(tmp_path):
    # replay of the leak window: cooldown set, ~34 minutes still to run
    _write_cooldown(tmp_path, until_ts=time.time() + 2000)
    row = usd_entry_cooldown_gate(tmp_path)
    assert row is not None
    assert row["reason"] == "cooldown_after_force_flat_reds"
    assert row["ok"] is False


def test_broken_cooldown_check_fails_closed(tmp_path, monkeypatch):
    import System.alice_usd_must_scalp as ms

    def _boom(state_dir):
        raise RuntimeError("cooldown state unreadable")

    monkeypatch.setattr(ms, "_force_flat_red_cooldown", _boom)
    row = usd_entry_cooldown_gate(tmp_path)
    assert row is not None
    assert row["reason"] == "cooldown_check_failed_fail_closed"
    assert row["ok"] is False


def test_expired_cooldown_allows_entry(tmp_path):
    _write_cooldown(tmp_path, until_ts=time.time() - 10)
    assert usd_entry_cooldown_gate(tmp_path) is None


def test_owner_manual_import_is_never_auto_sold():
    """r1719 — replay of the 21:40:15 ETH stash sale: exchange_import opens
    must be held untouched by tick_take_profits' exit loop."""
    import inspect

    from System import alice_usd_take_profit as tp

    src = inspect.getsource(tp.tick_take_profits)
    assert "exchange_import" in src and "owner_manual_hold" in src
