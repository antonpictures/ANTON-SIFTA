# tests/test_swarm_reset_recovery_immunity.py

from System.swarm_reset_recovery_immunity import compute_reset_recovery


def test_reset_recovery_immunity_bounded():
    row = compute_reset_recovery()
    assert row["truth_label"] == "POST_RESET_IMMUNE_RECOVERY"
    assert 0.0 <= row["warmth"] <= 1.0
    assert row["phase"] in {"READY", "REHYDRATE", "WOUND_REPAIR"}
    assert row["autonomy_gate"] in {"ALLOW", "LIMITED", "BLOCK"}
