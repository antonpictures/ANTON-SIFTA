"""MiMo UltraSpeed retired — stale rows migrate to Fireworks Kimi (r1433)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_stale_ultraspeed_attached_migrates_to_fireworks_kimi_on_read(tmp_path):
    from System import swarm_cortex_capabilities as cap

    cap.record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-v2.5-pro-ultraspeed", "mimo-auto"],
        default_attached="mimo-v2.5-pro-ultraspeed",
        state_dir=tmp_path,
    )

    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)

    assert "mimo-v2.5-pro-ultraspeed" not in (rec.get("attached_models") or [])
    assert cap.FIREWORKS_KIMI_K2P6_MODEL in (rec.get("attached_models") or [])
    assert rec.get("default_attached") == cap.FIREWORKS_KIMI_K2P6_MODEL
    assert cap.mimo_attached_dispatch_lane(cap.FIREWORKS_KIMI_K2P6_MODEL) == "mimo_cli_qwen_bridge"