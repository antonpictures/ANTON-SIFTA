import json

from System.canonical_schemas import BODY_SCHEMA, LEDGER_SCHEMAS
from System.swarm_stigmergic_video_resolution import (
    LEDGER_NAME,
    SwarmStigmergicResolution,
    cli_playbook_text,
    proof_of_property,
)


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_event90_schema_is_registered_as_ledger_not_body_field():
    assert LEDGER_NAME in LEDGER_SCHEMAS
    assert LEDGER_NAME not in BODY_SCHEMA


def test_calculate_and_log_frame_uses_schema_and_locked_ledger(tmp_path):
    retina = SwarmStigmergicResolution(
        state_dir=tmp_path,
        camera_width=1920,
        camera_height=1080,
        grid_size=(22, 22),
    )

    row = retina.calculate_and_log_frame(
        frame_id=1,
        active_cells=15,
        unified_field_payload=[{"cell": [10, 11], "val": 0.8}],
    )

    assert set(row) == LEDGER_SCHEMAS[LEDGER_NAME]
    assert row["schema"] == "SIFTA_STIGMERGIC_VIDEO_RESOLUTION_V1"
    assert row["total_stig_cells"] == 484
    assert row["pixels_per_stig_cell"] == round((1920 * 1080) / 484, 2)
    assert row["salience_density"] == round(15 / 484, 6)
    written = _read_jsonl(tmp_path / LEDGER_NAME)
    assert written == [row]


def test_derives_resolution_from_visual_stigmergy_row_without_raw_frame(tmp_path):
    retina = SwarmStigmergicResolution(state_dir=tmp_path)
    visual_row = {
        "ts": 1777652378.0,
        "sha8": "abc12345",
        "w": 1920,
        "h": 1080,
        "entropy_bits": 6.73,
        "saliency_peak": 0.327,
        "motion_mean": 0.005,
        "hue_deg": 297.6,
        "saliency_q": "0111" * 121,  # 484 cells, 363 non-zero
        "motion_q": "0001" * 121,    # 484 cells, 121 non-zero
    }

    row = retina.calculate_from_visual_stigmergy_row(visual_row)

    assert row["source_ledger"] == "visual_stigmergy.jsonl"
    assert row["source_sha8"] == "abc12345"
    assert row["source_frame_ts"] == visual_row["ts"]
    assert row["camera_size"] == [1920, 1080]
    assert row["stigmergic_grid"] == [22, 22]
    assert row["active_salient_cells"] == 363
    assert row["unified_field_payload"][0]["saliency_active_cells"] == 363


def test_log_latest_visual_stigmergy_appends_summary(tmp_path):
    visual = tmp_path / "visual_stigmergy.jsonl"
    visual.write_text(
        json.dumps(
            {
                "ts": 1.0,
                "sha8": "old",
                "w": 4,
                "h": 4,
                "saliency_q": "0000",
                "motion_q": "0000",
            }
        )
        + "\n"
        + json.dumps(
            {
                "ts": 2.0,
                "sha8": "new",
                "w": 8,
                "h": 8,
                "saliency_q": "1111",
                "motion_q": "0000",
            }
        )
        + "\n"
    )
    retina = SwarmStigmergicResolution(state_dir=tmp_path)

    row = retina.log_latest_visual_stigmergy()

    assert row is not None
    assert row["source_sha8"] == "new"
    assert row["camera_pixels_total"] == 64
    assert _read_jsonl(tmp_path / LEDGER_NAME)[0]["source_sha8"] == "new"


def test_proof_of_property_is_green():
    assert all(proof_of_property().values())


def test_cli_playbook_mentions_docling_stack():
    text = cli_playbook_text()
    assert "docling" in text.casefold()
    assert "yt-dlp" in text.casefold()
    assert "ibm.biz/BdpSA8" in text
