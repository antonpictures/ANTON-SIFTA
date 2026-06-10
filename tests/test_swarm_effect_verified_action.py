#!/usr/bin/env python3
"""Tests for Plan A1 effect-verification wrapper (r909)."""

import json
import time

from System.swarm_effect_verified_action import (
    complete_async_verified_action,
    count_consecutive_unverified,
    effect_claimed_success,
    enrich_effect,
    is_phantom_effect_receipt,
    record_effect_verified_action,
    run_sync_verified_action,
)


def test_enrich_effect_adds_verification_fields():
    effect = enrich_effect(
        {"ok": True, "reason": "opened"},
        method="sync",
        effect_verified=True,
        effect_cleared_ms=1200.0,
        verification_pass=1,
        organ="alice_browser",
        action="open_url",
    )
    assert effect["effect_verified"] is True
    assert effect["organ"] == "alice_browser"
    assert effect["effect_cleared_ms"] == 1200.0


def test_phantom_receipt_detects_unverified_success():
    row = {
        "organ": "youtube_ad_controller",
        "action": "skip",
        "effect": {"ok": True, "reason": "clicked_visible_skip_control"},
    }
    assert is_phantom_effect_receipt(row) is True
    row["effect"]["effect_verified"] = True
    assert is_phantom_effect_receipt(row) is False


def test_sync_verified_action_writes_honest_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    calls = {"verify": 0}

    def execute():
        return {"ok": True, "reason": "tab_closed"}

    def verify():
        calls["verify"] += 1
        return {"tabs_open": 0}

    def success(effect, probe):
        return probe.get("tabs_open") == 0

    result = run_sync_verified_action(
        organ="alice_browser",
        action="close_tab",
        execute=execute,
        verify=verify,
        success_from_probe=success,
        state_dir=state,
        verify_delay_s=0.0,
        sleep_fn=lambda _s: None,
    )
    assert result.effect_verified is True
    assert calls["verify"] == 1
    ledger = state / "effect_verified_actions.jsonl"
    row = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["effect_verified"] is True


def test_sync_verified_action_marks_phantom_on_failed_probe(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()

    def execute():
        return {"ok": True, "reason": "tab_closed"}

    def verify():
        return {"tabs_open": 2}

    def success(_effect, probe):
        return probe.get("tabs_open") == 0

    for _ in range(2):
        result = run_sync_verified_action(
            organ="alice_browser",
            action="close_tab",
            execute=execute,
            verify=verify,
            success_from_probe=success,
            state_dir=state,
            verify_delay_s=0.0,
            sleep_fn=lambda _s: None,
        )
    assert result.effect_verified is False
    assert result.phantom_disease is True
    assert count_consecutive_unverified(
        organ="alice_browser",
        action="close_tab",
        state_dir=state,
    ) == 2


def test_async_completion_records_verified_skip(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    started = time.time() - 1.5

    def success(_effect, probe):
        return not probe.get("detected")

    result = complete_async_verified_action(
        organ="youtube_ad_controller",
        action="skip",
        initial_effect={"ok": True, "reason": "clicked_visible_skip_control", "method": "js"},
        probe={"detected": False, "platform": "youtube"},
        success_from_probe=success,
        started_at=started,
        method="js",
        state_dir=state,
    )
    assert result.effect_verified is True
    assert effect_claimed_success(result.effect)


def test_record_resets_streak_after_verified_success(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    record_effect_verified_action(
        organ="test",
        action="act",
        effect={"ok": True, "reason": "clicked_visible_skip_control"},
        probe={},
        effect_verified=False,
        state_dir=state,
        now=1000.0,
    )
    record_effect_verified_action(
        organ="test",
        action="act",
        effect={"ok": True, "reason": "clicked_visible_skip_control"},
        probe={"cleared": True},
        effect_verified=True,
        state_dir=state,
        now=1001.0,
    )
    assert count_consecutive_unverified(organ="test", action="act", state_dir=state, before_ts=1002.0) == 0