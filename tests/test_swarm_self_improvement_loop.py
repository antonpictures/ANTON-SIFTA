import json
from pathlib import Path

from System.swarm_self_improvement_loop import close_loop_once, self_improvement_snapshot


def test_self_improvement_keeps_current_cortex_when_lora_blocked(tmp_path: Path) -> None:
    snap = self_improvement_snapshot(
        state_dir=tmp_path,
        lora_status={
            "candidate_model": "sifta-gemma4-alice-lora:latest",
            "promotion_ready": False,
            "promotion_blockers": ["candidate_capabilities_regressed:vision,audio"],
        },
        primary_truth={"active_model": "alice-m5-cortex-8b-6.3gb:latest", "installed": True},
        policy_snapshot_data={"examples_raw": 12, "decisions_raw": 20, "buckets": {}},
        arm_summary={"available": True},
    )

    assert snap["promotion_status"] == "KEEP_CURRENT_CORTEX"
    assert "do not promote LoRA candidate until blockers clear" in snap["recommended_actions"]


def test_close_loop_once_writes_receipt_without_switching(tmp_path: Path, monkeypatch) -> None:
    import System.swarm_self_improvement_loop as loop

    monkeypatch.setattr(
        loop,
        "_safe_lora_status",
        lambda: {"candidate_model": "candidate:latest", "promotion_ready": False, "promotion_blockers": ["smoke"]},
    )
    monkeypatch.setattr(
        loop,
        "_safe_primary_truth",
        lambda: {"active_model": "alice-m5-cortex-8b-6.3gb:latest", "installed": True},
    )
    monkeypatch.setattr(loop, "_safe_policy_snapshot", lambda state_dir=None: {"examples_raw": 0, "decisions_raw": 0, "buckets": {}})

    row = close_loop_once(state_dir=tmp_path)

    assert row["switch_attempted"] is False
    stored = json.loads((tmp_path / "self_improvement_loop.jsonl").read_text().splitlines()[-1])
    assert stored["truth_label"] == "SIFTA_SELF_IMPROVEMENT_LOOP_V1"
    assert stored["receipt"] == row["receipt"]

