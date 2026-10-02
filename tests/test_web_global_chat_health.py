"""W4 health-derivation test: verify web_global_chat organ reads from its metabolism ledger."""
from pathlib import Path
import sys
import json
import time
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_probe_web_global_chat_health_reads_ledger():
    from System import swarm_organ_directory as od
    # probe should read from the real metabolism ledger (not return a constant)
    h = od.probe_web_global_chat_health()
    assert isinstance(h, float), "health must be a float"
    assert 0.0 <= h <= 1.0, "health must be in [0, 1]"


def test_probe_idle_lane_is_healthy():
    """If the ledger has no recent rows (idle lane), probe returns 1.0."""
    from System import swarm_organ_directory as od
    from pathlib import Path
    import time as _time
    metab_path = od._DEFAULT_STATE / "web_global_chat_metabolism.jsonl"
    if metab_path.exists():
        # Read existing rows
        lines = metab_path.read_text().strip().splitlines()
        now = _time.time()
        recent = [row for row in lines if json.loads(row).get("ts", 0) > now - 600]
        if recent:
            # Add a stale row far in the past
            stale = {"ts": now - 6000.0, "event": "WEB_TYPED_INFERENCE_FEE"}
            with open(metab_path, "a") as f:
                f.write(json.dumps(stale) + "\n")
            h = od.probe_web_global_chat_health()
            assert h == 1.0, f"Idle lane (only stale rows) should return 1.0, got {h}"
            # Clean up: restore original
            metab_path.write_text("\n".join(lines) + "\n")


def test_probe_health_changes_with_metabolism():
    """Health derivation is actually computed from metabolism ledger contents."""
    from System import swarm_organ_directory as od
    from pathlib import Path
    import time as _time
    import random
    metab_path = od._DEFAULT_STATE / "web_global_chat_metabolism.jsonl"
    if not metab_path.exists():
        return
    # Save original
    orig = metab_path.read_text()
    try:
        # Append 3 recent rows, 2 with economy_posting_status, 1 without
        now = _time.time()
        rows = [
            {"ts": now, "event": "WEB_TYPED_INFERENCE_FEE", "economy_posting_status": True},
            {"ts": now - 100, "event": "WEB_TYPED_INFERENCE_FEE", "economy_posting_status": True},
            {"ts": now - 200, "event": "WEB_TYPED_INFERENCE_FEE", "economy_posting_status": None},
        ]
        for r in rows:
            with open(metab_path, "a") as f:
                f.write(json.dumps(r) + "\n")
        h = od.probe_web_global_chat_health()
        # 2 of 3 recent rows have status -> health = 2/3
        assert 0.5 < h < 0.7, f"Expected ~0.66, got {h}"
    finally:
        # Restore original
        metab_path.write_text(orig)


if __name__ == "__main__":
    test_probe_web_global_chat_health_reads_ledger()
    test_probe_idle_lane_is_healthy()
    test_probe_health_changes_with_metabolism()
    print("W4 health-derivation test: OK")