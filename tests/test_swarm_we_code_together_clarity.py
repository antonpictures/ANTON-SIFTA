from __future__ import annotations

import json
import time
from pathlib import Path


def test_wct_health_lines_surface_open_rounds_from_live_plan(tmp_path: Path) -> None:
    from System.swarm_we_code_together_clarity import (
        input_boundary_lines,
        matrix_and_gate_health_lines,
        open_round_lines,
    )

    plan = tmp_path / "WE_CODE_TOGETHER_PLAN.md"
    plan.write_text(
        "\n".join(
            [
                "# plan",
                "### GM1 — Hook seal_tail into the live body",
                "### GM2 — Multilingual ears",
                "### GM3 — We Code Together must know Alice",
                "### Chat with Alice about this process",
            ]
        ),
        encoding="utf-8",
    )
    state = tmp_path / ".sifta_state"
    state.mkdir()

    assert open_round_lines(limit=4, plan_path=plan) == [
        "GM1 — Hook seal_tail into the live body",
        "GM2 — Multilingual ears",
        "GM3 — We Code Together must know Alice",
    ]

    lines = matrix_and_gate_health_lines(limit=4, state_dir=state, plan_path=plan)

    assert any("We Code Together is Alice's shared code/body-health workbench" in line for line in lines)
    assert any("Operational liveness:" in line for line in lines)
    assert any("Sleep/quiet truth:" in line for line in lines)
    assert any("Vision:" in line for line in lines)
    assert any("Eval matrix verdict:" in line for line in lines)
    assert any("Lane contracts:" in line for line in lines)
    assert any("Field belief:" in line for line in lines)
    assert any("Grown organs:" in line for line in lines)
    assert any("INPUT BOUNDARY" in line for line in lines)
    assert any("Open rounds from live plan:" in line for line in lines)


def test_wct_input_boundary_surfaces_ambient_context_and_modality_receipts(tmp_path: Path) -> None:
    from System.swarm_we_code_together_clarity import input_boundary_lines

    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "ambient_media_context.json").write_text(
        json.dumps({
            "ts": time.time(),
            "source": "ambient_media_youtube",
            "note": "speaker/video STT is observed media, not typed owner text",
            "ttl_s": 3600,
        }),
        encoding="utf-8",
    )
    (state / "input_modality_receipts.jsonl").write_text(
        json.dumps({
            "classification": {
                "lane": "SPOKEN_STT_NOISY_OR_AMBIENT",
                "modality": "WORLD_STT",
                "owner_intent_weight": 0.22,
                "transcription_noise_risk": 0.55,
            },
            "text_head": "video audio picked up by STT",
        }) + "\n",
        encoding="utf-8",
    )

    lines = input_boundary_lines(state_dir=state)

    assert any("typed text is owner-authored intent" in line for line in lines)
    assert any("source=ambient_media_youtube" in line for line in lines)
    assert any("SPOKEN_STT_NOISY_OR_AMBIENT/WORLD_STT" in line for line in lines)
    # r1602 VA5 — voiceprint verdict surface
    assert any("Voice verdict:" in line for line in lines)
