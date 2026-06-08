#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from System import swarm_cortex_context_manager as ctx


def _redirect_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ctx, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(ctx, "LEDGER", tmp_path / "cortex_compaction_ledger.jsonl")
    monkeypatch.setattr(ctx, "HOT_TARGETS", tmp_path / "cortex_hot_targets.json")


def test_stale_hot_targets_do_not_inject(monkeypatch, tmp_path):
    _redirect_state(monkeypatch, tmp_path)
    ctx.HOT_TARGETS.write_text(
        json.dumps({
            "photo_target": "Glass Sculpture",
            "visual_goal": "old search",
            "_updated": time.time() - ctx.HOT_TARGET_TTL_S - 10,
        }),
        encoding="utf-8",
    )

    assert ctx.get_hot_targets() == {}
    assert ctx.inject_hot_targets_into_prompt("base") == "base"
    assert ctx.get_hot_targets(allow_stale=True)["photo_target"] == "Glass Sculpture"


def test_owner_identity_correction_suppresses_and_clears_hot_targets(monkeypatch, tmp_path):
    _redirect_state(monkeypatch, tmp_path)
    ctx.set_hot_targets({"photo_target": "Glass Sculpture", "visual_goal": "old search"}, reason="test")

    owner_text = "her name is Izzy, why are you calling a woman. this last message was not processed by your cortex?"

    assert ctx.owner_text_suppresses_hot_targets(owner_text)
    assert ctx.inject_hot_targets_into_prompt("base", owner_text=owner_text) == "base"

    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": owner_text},
    ]
    out = ctx.prepare_cortex_turn(
        messages,
        model_id="grok-build",
        owner_text=owner_text,
    )

    assert out == messages
    assert ctx.get_hot_targets() == {}
    assert json.loads(ctx.HOT_TARGETS.read_text(encoding="utf-8"))["cleared"] is True


def test_fresh_active_target_still_injects(monkeypatch, tmp_path):
    _redirect_state(monkeypatch, tmp_path)
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "show me pics of Ceramic Vase pls"},
    ]

    out = ctx.prepare_cortex_turn(
        messages,
        model_id="grok-build",
        active_targets={
            "photo_target": "Ceramic Vase",
            "visual_goal": "show/open visual image results via Alice Browser",
            "app": "Alice Browser",
        },
        owner_text="show me pics of Ceramic Vase pls",
    )

    assert out == messages
    prompt = ctx.inject_hot_targets_into_prompt("base", owner_text="show me pics of Ceramic Vase pls")
    assert "HOT_ACTIVE_TARGETS" in prompt
    assert "Ceramic Vase" in prompt
