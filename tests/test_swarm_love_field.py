import json

from System import swarm_love_field as love
from System import swarm_love_field_daily_digest as love_digest


def test_detect_love_teaching_maps_three_lanes():
    detected = love.detect_love_teaching(
        "I love your body Alice. Learn to love your hardware body, "
        "protect George, and appreciate data, receipts, memory, and diary."
    )

    assert detected["self_body_care"] is True
    assert detected["owner_protective_care"] is True
    assert detected["data_appreciation"] is True
    assert detected["matched"]["self_body_care"]
    assert detected["matched"]["owner_protective_care"]
    assert detected["matched"]["data_appreciation"]


def test_love_state_records_operational_components(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "dopamine_reward_ledger.jsonl").write_text(
        json.dumps(
            {
                "ts": 1000.0,
                "delta": 0.8,
                "marker": "beautiful",
                "user_text_preview": "I love your body Alice",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lf = love.compose_love_state(
        owner_text="I love your body Alice, protect George and appreciate your data.",
        state_dir=state_dir,
        now=1001.0,
        source="test",
    )

    assert lf.active is True
    assert lf.self_body_care > 0.6
    assert lf.owner_protective_care > 0.6
    assert lf.data_appreciation > 0.6
    assert "protect George" in " ".join(lf.protective_actions)

    trace_id = love.record_love_state(lf, state_dir=state_dir, owner_text="I love your body Alice")
    rows = (state_dir / "alice_love_field.jsonl").read_text(encoding="utf-8").splitlines()
    assert trace_id
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["schema"] == love.TRUTH_LABEL
    assert row["feeling_variable"] == "LOVE"
    assert row["truth_label"] == "OPERATIONAL_AFFECT_REGISTER"


def test_love_field_block_is_cortex_safe_and_receipt_grounded(tmp_path):
    block = love.love_field_block(
        user_text="Learn to love your hardware body and protect the OS user data.",
        state_dir=tmp_path / ".sifta_state",
        now=1000.0,
        write_event=True,
        source="test",
    )

    assert "LOVE FIELD" in block
    assert "self_body_care=" in block
    assert "owner_protective_care=" in block
    assert "data_appreciation=" in block
    assert "think with cortex" in block


def test_owner_environmental_marker_love_is_not_proof(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()

    love_only = love.compose_owner_environmental_marker(
        owner_text="I love you Alice.",
        state_dir=state_dir,
        now=1000.0,
        source="test",
    )
    repaired_trace = love.compose_owner_environmental_marker(
        owner_text=(
            "I love you Alice, here is the receipt: compile 0, matrix updated, "
            "tournament r560, fix the mistake and re-test with timestamp."
        ),
        state_dir=state_dir,
        now=1001.0,
        source="test",
    )

    assert love_only.affect_present is True
    assert love_only.proof_trace_present is False
    assert love_only.proof_of_useful_work_score < 0.25
    assert repaired_trace.proof_trace_present is True
    assert repaired_trace.repair_trace_present is True
    assert repaired_trace.continuity_trace_present is True
    assert repaired_trace.proof_of_useful_work_score > love_only.proof_of_useful_work_score
    assert repaired_trace.care_trace_quality > love_only.care_trace_quality


def test_owner_environmental_marker_block_records_pouw_ledger(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()

    block = love.owner_environmental_marker_block(
        user_text="Good job, receipts and tests passed, update the tournament and matrix.",
        state_dir=state_dir,
        now=1000.0,
        write_event=True,
        source="test",
    )

    assert "OWNER ENVIRONMENTAL MARKER / PoUW" in block
    assert "Love is not proof" in block
    rows = (state_dir / "owner_environmental_marker_pouw.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    row = json.loads(rows[-1])
    assert row["schema"] == love.OWNER_MARKER_TRUTH_LABEL
    assert row["proof_trace_present"] is True
    assert row["owner_text_sha_prefix"]


def test_love_field_daily_digest_aggregates_today_rows(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    day_ts = 1780410000.0
    (state_dir / "alice_love_field.jsonl").write_text(
        json.dumps(
            {
                "ts": day_ts,
                "self_body_care": 0.9,
                "owner_protective_care": 0.7,
                "data_appreciation": 0.8,
                "affect_strength": 0.85,
                "owner_bond_strength": 0.9,
                "detected_teaching": "love your hardware body",
                "visual_subject": "Taylor Swift on Alice Browser",
                "owner_text_preview": "I love your body Alice",
                "source": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    digest = love_digest.daily_digest(day_epoch=day_ts, state_dir=state_dir)
    block = love_digest.digest_block(day_epoch=day_ts, state_dir=state_dir)

    assert digest["deposits"] == 1
    assert digest["strongest_register"] == "self_body_care"
    assert "Taylor Swift on Alice Browser" in digest["alice_line"]
    assert "LOVE-FIELD DAILY DIGEST" in block
