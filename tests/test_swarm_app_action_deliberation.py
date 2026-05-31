#!/usr/bin/env python3
"""Tests for app-action deliberation diary."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_app_action_deliberation as appthink


def test_deliberate_open_existing_limb_raises_instead_of_duplicate():
    packet = appthink.deliberate_app_action(
        action="open_app",
        app_name="Alice Browser",
        before_state={"open_apps": ["Alice Browser"], "active_app": "Alice Browser"},
    )
    assert packet["decision"] == "raise_existing_limb"
    assert "already open" in packet["rationale"]


def test_record_diary_writes_before_and_after(tmp_path):
    before = {"open_apps": [], "active_app": "", "desktop_mode": "chat"}
    after = {"open_apps": ["Ace"], "active_app": "Ace", "desktop_mode": "launcher"}
    appthink.record_app_action_diary(
        phase="before_action",
        action="open_app",
        app_name="Ace",
        before_state=before,
        state_dir=tmp_path,
        now=1,
    )
    appthink.record_app_action_diary(
        phase="after_action",
        action="open_app",
        app_name="Ace",
        before_state=before,
        after_state=after,
        receipt_id="r-test",
        ok=True,
        state_dir=tmp_path,
        now=2,
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / ".sifta_state" / appthink.DIARY_NAME).read_text().splitlines()
    ]
    assert [r["phase"] for r in rows] == ["before_action", "after_action"]
    assert rows[-1]["after_open_apps"] == ["Ace"]
    assert rows[-1]["receipt_id"] == "r-test"


def test_context_block_reports_open_limb_and_recent_diary(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    (sd / "sifta_desktop_app_state.json").write_text(
        json.dumps({"desktop_mode": "launcher", "active_app": "Alice Browser", "open_apps": ["Alice Browser"]})
    )
    appthink.record_app_action_diary(
        phase="after_action",
        action="open_app",
        app_name="Alice Browser",
        after_state={"open_apps": ["Alice Browser"]},
        state_dir=sd,
        now=3,
    )
    block = appthink.current_app_action_context_block(state_dir=sd)
    assert "APP-LIMB CORTEX CONTEXT" in block
    assert "Alice Browser" in block
    assert "recent app action diary" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
