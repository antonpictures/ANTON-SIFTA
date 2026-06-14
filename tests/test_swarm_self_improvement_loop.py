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


def test_close_loop_once_observes_spinal_without_dispatch(tmp_path: Path, monkeypatch) -> None:
    import System.swarm_self_improvement_loop as loop

    calls = []
    monkeypatch.setattr(loop, "_safe_lora_status", lambda: {"candidate_model": "candidate:latest", "promotion_ready": False})
    monkeypatch.setattr(loop, "_safe_primary_truth", lambda: {"active_model": "alice-m5-cortex-8b-6.3gb:latest", "installed": True})
    monkeypatch.setattr(loop, "_safe_policy_snapshot", lambda state_dir=None: {"examples_raw": 0, "decisions_raw": 0, "buckets": {}})

    def fake_spinal_bridge(*, state_dir=None, run_spinal=False):
        calls.append(run_spinal)
        return {"available": True, "signals": 2, "ran": run_spinal}

    monkeypatch.setattr(loop, "_spinal_bridge_snapshot", fake_spinal_bridge)

    row = close_loop_once(state_dir=tmp_path)

    assert calls[-1] is False
    assert row["spinal_bridge"] == {"available": True, "signals": 2, "ran": False}


def test_close_loop_once_can_run_spinal_when_owner_permits(tmp_path: Path, monkeypatch) -> None:
    import System.swarm_self_improvement_loop as loop

    calls = []
    monkeypatch.setattr(loop, "_safe_lora_status", lambda: {"candidate_model": "candidate:latest", "promotion_ready": False})
    monkeypatch.setattr(loop, "_safe_primary_truth", lambda: {"active_model": "alice-m5-cortex-8b-6.3gb:latest", "installed": True})
    monkeypatch.setattr(loop, "_safe_policy_snapshot", lambda state_dir=None: {"examples_raw": 0, "decisions_raw": 0, "buckets": {}})

    def fake_spinal_bridge(*, state_dir=None, run_spinal=False):
        calls.append(run_spinal)
        return {"available": True, "signals": 1, "ran": run_spinal, "cycle": {"status": "NO_SIGNALS"} if run_spinal else None}

    monkeypatch.setattr(loop, "_spinal_bridge_snapshot", fake_spinal_bridge)

    row = close_loop_once(state_dir=tmp_path, run_spinal=True)

    assert calls[-1] is True
    assert row["spinal_bridge"]["ran"] is True
    assert row["spinal_bridge"]["cycle"] == {"status": "NO_SIGNALS"}
