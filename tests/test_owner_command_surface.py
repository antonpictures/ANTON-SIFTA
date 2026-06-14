"""C10 — owner command surface regression: misbind, typed-gag, UUID-leak wounds."""
from __future__ import annotations

from pathlib import Path


def test_owner_command_surface_modules_on_disk():
    """Permanent suite files for three wound directions."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "tests/test_r1018_p1_cortex_llm_list_binding.py").exists()
    assert (root / "tests/test_r1017_p01_typed_interrogative_reply.py").exists()
    assert (root / "System/swarm_cortex_llm_list_binding.py").exists()