import json
from pathlib import Path

from System.swarm_global_segment_index import (
    TRUTH_LABEL,
    build_global_segment_index,
    summary_for_prompt,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")


def test_global_segment_index_counts_cross_ledger_sources(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "memory_ledger.jsonl",
        [
            {
                "timestamp": 1000.0,
                "app_context": "talk_to_alice",
                "raw_text": "Alice, I am teaching you my voice and camera commands.",
                "semantic_tags": ["voice", "camera"],
            }
        ],
    )
    _write_jsonl(
        state / "youtube_watch_memory.jsonl",
        [
            {
                "ts": 1010.0,
                "title": "OpenClaw agentic loop - YouTube",
                "video_id": "abc123",
                "content_category": "AI Engineering",
            }
        ],
    )
    _write_jsonl(
        state / "media_ingress_gate.jsonl",
        [
            {
                "ts": 1020.0,
                "route": "observed_media",
                "reason": "media_focus_default_to_observed",
                "text_preview": "OpenClaw agents and tool use",
                "confidence": 0.8,
                "acoustic_fingerprint": {"channel_cue": "speaker_likely"},
            }
        ],
    )
    _write_jsonl(
        state / "voice_identity_ledger.jsonl",
        [
            {
                "ts": 1030.0,
                "source_label": "phone",
                "display": "Phone Speaker",
                "note": "phone speaker youtube",
                "features": {"duration_s": 12.0},
            }
        ],
    )
    _write_json(
        state / "iphone_gps_latest.json",
        {
            "ts": 1040.0,
            "carrier": "iphone",
            "channel": "ios_shortcut_http_post",
            "payload": {"latitude": 32.0, "longitude": -115.0, "accuracy": 12.5},
        },
    )
    _write_jsonl(
        state / "architect_physical_substrate.jsonl",
        [
            {
                "ts": 1035.0,
                "truth_label": "OBSERVED",
                "kind": "ARCHITECT_PHYSICAL_SUBSTRATE_SNAPSHOT",
                "homeworld_serial": "GTH4921YP3",
                "input_channel": "typed_turn",
                "ollama_model": "alice-m5-cortex-8b-6.3gb:latest",
                "iphone_gps_latest": {"age_s": 5.0, "latitude": 32.0},
                "frontmost_app_focus": {"app": "Safari", "detail": "GitHub"},
            }
        ],
    )

    row = build_global_segment_index(state_dir=state, write=True)

    assert row["truth_label"] == TRUTH_LABEL
    assert row["source_counts"]["owner_dialogue"] == 1
    assert row["source_counts"]["youtube_watch"] == 1
    assert row["source_counts"]["audio_media_gate"] == 1
    assert row["source_counts"]["physical_substrate"] == 1
    assert row["voice_label_counts"]["phone"] == 1
    assert row["latest_location"]["source_kind"] == "location_latest"
    assert "phone_contact_identity_not_wired" in row["unknowns"]
    assert "physical_substrate_ledger_absent" not in row["unknowns"]
    assert (state / "global_segment_index.jsonl").exists()
    assert (state / "global_segment_index_latest.json").exists()


def test_global_segment_summary_names_counts_and_unknowns(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "voice_identity_ledger.jsonl",
        [
            {"ts": 1000.0, "source_label": "george", "display": "George Voice"},
            {"ts": 1001.0, "source_label": "phone", "display": "Phone Speaker"},
        ],
    )
    _write_jsonl(
        state / "youtube_context.jsonl",
        [
            {
                "ts": 1002.0,
                "title": "Top Story with Tom Llamas - YouTube",
                "video_id": "news1",
                "content_category": "News",
            }
        ],
    )

    prompt = summary_for_prompt(state_dir=state, write=False)

    assert "GLOBAL STIGMERGIC SEGMENT INDEX" in prompt
    assert "voice_exemplar=2" in prompt
    assert "voice_labels: george=1, phone=1" in prompt
    assert "Top Story with Tom Llamas" in prompt
    assert "phone contact identity" not in prompt
    assert "phone_contact_identity_not_wired" in prompt


def test_empty_global_segment_index_is_silent(tmp_path):
    assert summary_for_prompt(state_dir=tmp_path / ".sifta_state", write=False) == ""
