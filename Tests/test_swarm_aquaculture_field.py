import json

from System.swarm_aquaculture_field import (
    LEDGER_NAME,
    TRUTH_LABEL,
    decide,
    make_synthetic_tank,
    run_sentinel_tick,
)


def test_low_oxygen_patch_requests_aeration_and_writes_receipts(tmp_path):
    result = run_sentinel_tick("low_oxygen", state_root=tmp_path)
    decision = result["decision"]

    assert decision["truth_label"] == TRUTH_LABEL
    assert decision["simulated"] is True
    assert decision["no_live_animals"] is True
    assert "AERATION_REQUEST" in decision["actions"]
    assert "oxygen_probe" in decision["summary"]["cross_probe_support"]
    assert decision["sample_period_ms"] < 1200

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    kinds = [row["kind"] for row in rows]
    assert kinds[:2] == ["OBSERVED", "SAMPLE_DECISION"]
    assert "AERATION_REQUEST" in kinds
    assert all(row["truth_label"] == TRUTH_LABEL for row in rows)
    assert all(row["simulated"] is True for row in rows)
    assert all(row["no_live_animals"] is True for row in rows)


def test_camera_noise_alone_only_asks_for_active_probe():
    observation = make_synthetic_tank("camera_noise")
    decision = decide(observation)

    assert decision["summary"]["camera_noise_only"] is True
    assert decision["actions"] == ["ACTIVE_PROBE"]
    assert "AERATION_REQUEST" not in decision["actions"]
    assert "HUMAN_ALERT" not in decision["actions"]


def test_stable_tank_backs_off_sampling_without_action():
    observation = make_synthetic_tank("normal")
    decision = decide(observation)

    assert decision["actions"] == ["LOW_BURN_MONITOR"]
    assert decision["sample_period_ms"] > 4300
    assert decision["summary"]["risk"] == 0.0


def test_feed_spike_holds_feed_without_human_alert():
    observation = make_synthetic_tank("feed_spike")
    decision = decide(observation)

    assert "FEED_HOLD" in decision["actions"]
    assert "HUMAN_ALERT" not in decision["actions"]
    assert "feed_probe" in decision["summary"]["cross_probe_support"]
    assert "turbidity_probe" in decision["summary"]["cross_probe_support"]
