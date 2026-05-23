from __future__ import annotations

from pathlib import Path


def test_talk_prompt_injects_continuity_and_self_realization_context() -> None:
    source = (Path(__file__).resolve().parents[1] / "Applications" / "sifta_talk_to_alice_widget.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "continuity_summary_for_prompt" in source
    assert "sync_from_app_focus" in source
    assert "self_realization_prompt_block" in source
    assert "write_receipt=False" in source
    assert "sysprompt = sysprompt + \"\\n\\n\" + _continuity_context" in source
    assert "sysprompt = sysprompt + \"\\n\\n\" + _self_realization_context" in source
