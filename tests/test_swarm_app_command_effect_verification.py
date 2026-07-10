#!/usr/bin/env python3
"""Tests for Plan A2 app-command effect verification."""

import json
import time

from System.swarm_app_command_effect_verification import (
    TOP5_ACTIONS,
    browser_urls_match,
    enrich_app_command_row,
    probe_open_app,
    probe_schedule_fire,
    record_schedule_fire_command,
    success_close_tab,
    success_open_browser_url,
    success_open_app,
    success_schedule_fire,
    verify_app_command_sync,
)


def test_top5_actions_include_live_effectors():
    assert "open_browser_url" in TOP5_ACTIONS
    assert "browser_close_tab" in TOP5_ACTIONS
    assert "youtube_ad_skip" in TOP5_ACTIONS
    assert "schedule_fire" in TOP5_ACTIONS
    assert "open_app" in TOP5_ACTIONS


def test_open_app_probe_detects_newly_open_app():
    probe = probe_open_app(
        app_name="Alice Browser",
        before_state={"open_apps": ["Talk to Alice"]},
        after_state={"open_apps": ["Talk to Alice", "Alice Browser"]},
    )
    assert probe["now_open"] is True
    assert success_open_app({"ok": True}, probe) is True


def test_close_tab_probe_counts_closed_tabs():
    probe = {"closed_count": 2, "remaining_tabs": 1, "before_tabs": 3}
    assert success_close_tab({"ok": True}, probe) is True


def test_open_browser_url_requires_requested_url_not_stale_home():
    probe = {
        "target_url": "https://web.whatsapp.com/",
        "observed_url": "sifta://home",
        "page_fresh": True,
        "open_tabs_count": 1,
    }

    assert success_open_browser_url({"ok": True, "url": "https://web.whatsapp.com/"}, probe) is False


def test_browser_url_match_allows_tracking_params_but_not_different_video():
    assert browser_urls_match(
        "https://duckduckgo.com/?q=maisie+williams+photos",
        "https://duckduckgo.com/?q=maisie+williams+photos&ia=web",
    )
    assert browser_urls_match("https://instagram.com", "https://www.instagram.com/")
    assert not browser_urls_match(
        "https://www.youtube.com/watch?v=one",
        "https://www.youtube.com/watch?v=two",
    )


def test_schedule_fire_probe_reads_fired_flag(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    row = {
        "schedule_id": "sched-1",
        "text": "pizza reminder",
        "due_ts": time.time() - 10,
        "fired": True,
        "fired_ts": time.time(),
    }
    with (state / "stigmergic_schedule.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    probe = probe_schedule_fire(schedule_id="sched-1", state_dir=state)
    assert probe["fired"] is True
    assert success_schedule_fire({"ok": True}, probe) is True


def test_enrich_app_command_row_writes_effect_verified(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    row = {
        "ts": time.time(),
        "receipt_id": "r1",
        "action": "open_app",
        "ok": True,
        "app_name": "Bonsai",
    }
    enriched = enrich_app_command_row(
        row,
        verify_context={
            "app_name": "Bonsai",
            "before_state": {"open_apps": []},
            "after_state": {"open_apps": ["Bonsai"]},
        },
        state_dir=state,
    )
    assert "effect_verified" in enriched
    assert enriched["effect_verified"] is True
    ledger = state / "effect_verified_actions.jsonl"
    assert ledger.exists()


def test_record_schedule_fire_command(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    sched = {
        "schedule_id": "sched-fire-1",
        "text": "class at 10am",
        "fired": True,
        "fired_ts": time.time(),
    }
    with (state / "stigmergic_schedule.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(sched) + "\n")
    row = record_schedule_fire_command(
        schedule_id="sched-fire-1",
        speech="George, class at 10am.",
        state_dir=state,
    )
    assert row["action"] == "schedule_fire"
    assert row["effect_verified"] is True
    app_cmds = (state / "alice_app_commands.jsonl").read_text(encoding="utf-8").strip()
    assert "schedule_fire" in app_cmds


def test_verify_sync_marks_phantom_when_probe_fails(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    result = verify_app_command_sync(
        action="open_app",
        ok=True,
        context={
            "app_name": "Missing App",
            "before_state": {"open_apps": []},
            "after_state": {"open_apps": []},
        },
        state_dir=state,
    )
    assert result["effect_verified"] is False


def test_verify_browser_open_marks_phantom_when_latest_page_is_home(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "browser_page_state_latest.json").write_text(
        json.dumps({
            "ts": time.time(),
            "truth_label": "BROWSER_PAGE_STATE_V1",
            "url": "sifta://home",
            "title": "Alice · SIFTA Browser",
            "open_tabs_count": 1,
        }),
        encoding="utf-8",
    )

    result = verify_app_command_sync(
        action="open_browser_url",
        ok=True,
        context={
            "url": "https://web.whatsapp.com/",
            "app_name": "Alice Browser",
        },
        state_dir=state,
    )

    assert result["effect_verified"] is False
    assert result["probe"]["observed_url"] == "sifta://home"
    assert result["probe"]["url_match"] is False


def test_verify_browser_open_rejects_stale_matching_page_state(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    target = "https://www.instagram.com/reels/DXK8SBYgJdG/"
    command_ts = time.time()
    (state / "browser_page_state_latest.json").write_text(
        json.dumps({
            "ts": command_ts - 240,
            "truth_label": "BROWSER_PAGE_STATE_V1",
            "url": target,
            "title": "(1) Instagram",
            "open_tabs_count": 1,
        }),
        encoding="utf-8",
    )

    result = verify_app_command_sync(
        action="open_browser_url",
        ok=True,
        context={
            "url": target,
            "app_name": "Alice Browser",
            "min_ts": command_ts,
        },
        state_dir=state,
    )

    assert result["effect_verified"] is False
    assert result["probe"]["url_match"] is True
    assert result["probe"]["page_fresh"] is False
    assert result["probe"]["after_command"] is False
