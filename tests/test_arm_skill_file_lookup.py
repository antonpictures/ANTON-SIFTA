from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from Applications import sifta_talk_to_alice_widget as talk
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"Skipping arm-skill lookup tests: widget import failed ({type(exc).__name__}: {exc})",
        allow_module_level=True,
    )


def test_resolve_named_arm_skill_path_for_grok_dispatch():
    arm_id, skill_path = talk._resolve_named_arm_skill_path(
        "Alice, dispatch Grok inside the SIFTA matrix-terminal PTY now."
    )
    assert arm_id == "grok_pty"
    assert skill_path is not None
    assert skill_path.as_posix().endswith("/skills/grok_pty_arm.md")


def test_current_system_prompt_surfaces_grok_arm_skill_path():
    prompt = talk._current_system_prompt(
        user_active=True,
        user_text="Alice, dispatch Grok now and write work_receipt.",
    )
    assert "ARM SKILL FILE DOCTRINE" in prompt
    assert "skills/grok_pty_arm.md" in prompt
