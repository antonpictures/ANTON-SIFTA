import json
from types import SimpleNamespace

from System.swarm_unified_stigmergic_field import (
    APP_HABIT_CHAIN_LEDGER,
    APP_HABIT_TRUTH_LABEL,
    TRUTH_LABEL,
    build_unified_field,
    format_unified_field_for_prompt,
)


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _write_json(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")


def test_unified_field_fuses_selected_shazam_and_media_receipts(tmp_path):
    state = tmp_path / ".sifta_state"
    now = 1_777_000_000.0
    _write_jsonl(
        state / "app_focus.jsonl",
        [
            {
                "ts": now - 5,
                "app": "Stigmergic Unified Shazam",
                "detail": "category=Gaming; conf=0.98; acoustic_scene=GAMING(36%)",
                "tab": "Co-watch guess",
                "selection": "Deep Sea gameplay stream",
                "metadata": {"primary_category": "Gaming", "confidence": 0.98},
            }
        ],
    )
    _write_jsonl(
        state / "active_window.jsonl",
        [
            {
                "ts": now - 7,
                "frontmost_app": "Safari",
                "frontmost_window": "YouTube - Deep Sea",
                "url": "https://www.youtube.com/watch?v=abc123",
                "youtube_video_id": "abc123",
            }
        ],
    )
    _write_json(
        state / "media_shazam_latest.json",
        {
            "ts": now - 4,
            "primary_category": "Gaming",
            "confidence": 0.98,
            "source_label": "gaming video",
            "title_guess": "Deep Sea",
            "acoustic_scene": "GAMING",
            "acoustic_scene_confidence": 0.36,
            "evidence_rows": 96,
            "source_ledgers": ["acoustic_scene_classifier", "media_ingress_gate"],
        },
    )
    _write_json(
        state / "youtube_context_latest.json",
        {
            "ts": now - 6,
            "title": "Deep Sea - YouTube",
            "video_id": "abc123",
            "reality_frame": "MEDIA_CONTEXT",
        },
    )

    row = build_unified_field(state_dir=state, now=now, write=True)

    assert row["truth_label"] == TRUTH_LABEL
    assert row["watching_together"] is True
    assert row["sifta_active_app"]["app"] == "Stigmergic Unified Shazam"
    assert row["hosted_os_focus"]["frontmost_app"] == "Safari"
    assert row["media_guess"]["primary_category"] == "Gaming"
    assert row["field_confidence"] > 0.8
    assert "co-watching media" in row["owner_activity"]
    assert (state / "unified_stigmergic_field.jsonl").exists()
    assert (state / "unified_stigmergic_field_latest.json").exists()


def test_prompt_block_prevents_no_video_context_when_receipts_exist(tmp_path):
    state = tmp_path / ".sifta_state"
    now = 1_777_000_000.0
    _write_jsonl(
        state / "app_focus.jsonl",
        [{"ts": now, "app": "Stigmergic Unified Shazam", "detail": "category=News & Politics"}],
    )
    _write_json(
        state / "media_shazam_latest.json",
        {
            "ts": now,
            "primary_category": "News & Politics",
            "confidence": 0.74,
            "source_label": "news network / politics",
            "title_guess": "ABC World News Tonight",
            "evidence_rows": 44,
        },
    )

    prompt = format_unified_field_for_prompt(state_dir=state, now=now, write=False)

    assert "UNIFIED STIGMERGIC FIELD" in prompt
    assert "Stigmergic Unified Shazam" in prompt
    assert "News & Politics" in prompt
    assert "do not say you have no video context" in prompt
    assert "state uncertainty" in prompt


def test_unified_field_carries_app_habits_behind_thermo_gate(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    now = 1_777_000_000.0
    _write_jsonl(
        state / "app_focus.jsonl",
        [
            {
                "ts": now - 2,
                "app": "Reading Lab",
                "detail": "word card open",
                "metadata": {"source": "sifta_os_desktop", "event": "subwindow_activated"},
            }
        ],
    )

    import System.swarm_app_help_skills as help_skills
    import System.swarm_capability_registry as capabilities
    import System.swarm_processing_thermodynamic_gate as thermo_gate

    monkeypatch.setattr(
        help_skills,
        "effective_skills_for_app",
        lambda app: SimpleNamespace(
            merged=["lesson_timing", "help_section_read"],
            stigmergic=["lesson_timing"],
            static_seed=["help_section_read"],
            last_seen_ts={"lesson_timing": now - 1},
        ),
    )
    monkeypatch.setattr(
        capabilities,
        "app_habit_field_summary",
        lambda app, limit=8: {
            "active_app": app,
            "returned": 1,
            "habits": [
                {
                    "score": 2.4,
                    "name": "reading_lab_coach",
                    "description": "Teach from the active word card",
                    "procedure_file": "reading_lab_coach.md",
                    "tag": "[skill]",
                }
            ],
        },
    )
    monkeypatch.setattr(
        thermo_gate,
        "request_processing_clearance",
        lambda *args, **kwargs: {
            "truth_label": "PROCESSING_THERMODYNAMIC_GATE_V1",
            "process_kind": "app_habit_unified_field_merge",
            "allowed": True,
            "action": "allow",
            "reasons": ["body_clearance_ok"],
            "rest_seconds": 0.0,
            "receipt_hash": "thermo1234567890",
            "body": {
                "thermal_warning_level": 0,
                "budget_multiplier": 0.9,
                "metabolic_mode": "GREEN_GROW",
            },
        },
    )

    row = build_unified_field(state_dir=state, now=now, write=True)
    packet = row["app_habit_field"]
    prompt = format_unified_field_for_prompt(state_dir=state, now=now, write=False)

    assert packet["truth_label"] == APP_HABIT_TRUTH_LABEL
    assert packet["active_app"] == "Reading Lab"
    assert packet["status"] == "allowed"
    assert packet["packet_sha256"]
    assert packet["thermodynamic_clearance"]["receipt_hash"] == "thermo1234567890"
    assert packet["help_skills"][0]["name"] == "lesson_timing"
    assert packet["capability_habits"][0]["name"] == "reading_lab_coach"
    assert (state / APP_HABIT_CHAIN_LEDGER).exists()
    assert "App habit lane" in prompt
    assert "lesson_timing" in prompt
    assert "reading_lab_coach" in prompt
    assert "thermo_receipt=thermo123456" in prompt


def test_unified_field_defers_app_habits_when_body_gate_defers(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    now = 1_777_000_000.0
    _write_jsonl(
        state / "app_focus.jsonl",
        [{"ts": now, "app": "Any App", "detail": "active"}],
    )

    import System.swarm_app_help_skills as help_skills
    import System.swarm_processing_thermodynamic_gate as thermo_gate

    def _should_not_read_help(_app):
        raise AssertionError("help skills should not be read when the body gate defers")

    monkeypatch.setattr(help_skills, "effective_skills_for_app", _should_not_read_help)
    monkeypatch.setattr(
        thermo_gate,
        "request_processing_clearance",
        lambda *args, **kwargs: {
            "truth_label": "PROCESSING_THERMODYNAMIC_GATE_V1",
            "process_kind": "app_habit_unified_field_merge",
            "allowed": False,
            "action": "defer",
            "reasons": ["thermal_critical"],
            "rest_seconds": 120.0,
            "receipt_hash": "hot123",
            "body": {"thermal_warning_level": 3},
        },
    )

    row = build_unified_field(state_dir=state, now=now, write=False)
    packet = row["app_habit_field"]

    assert packet["status"] == "deferred_by_thermodynamic_gate"
    assert packet["help_skills"] == []
    assert packet["capability_habits"] == []
    assert packet["thermodynamic_clearance"]["reasons"] == ["thermal_critical"]


def test_hosted_os_focus_cannot_shadow_selected_sifta_app(tmp_path):
    state = tmp_path / ".sifta_state"
    now = 1_777_000_000.0
    _write_jsonl(
        state / "app_focus.jsonl",
        [
            {
                "ts": now - 80,
                "app": "Stigmergic Unified Shazam",
                "detail": "category=Gaming; conf=0.98",
                "tab": "Co-watch guess",
                "metadata": {
                    "source": "sifta_os_desktop",
                    "event": "subwindow_activated",
                },
            },
            {
                "ts": now - 3,
                "app": "Python",
                "detail": "The Architect's frontmost macOS window is: SIFTA Python GUI OS",
                "selection": "SIFTA Python GUI OS",
                "metadata": {
                    "source": "swarm_active_window",
                    "bundle_id": "org.python.python",
                },
            },
        ],
    )
    _write_json(
        state / "media_shazam_latest.json",
        {
            "ts": now - 5,
            "primary_category": "Gaming",
            "confidence": 0.98,
            "source_label": "gaming video",
        },
    )

    row = build_unified_field(state_dir=state, now=now)

    assert row["sifta_active_app"]["app"] == "Stigmergic Unified Shazam"
    assert row["hosted_os_focus"]["app"] == "Python"
    assert "Stigmergic Unified Shazam" in row["owner_activity"]
    assert "co-watching media" in row["owner_activity"]


def test_empty_field_returns_honest_no_prompt_noise(tmp_path):
    state = tmp_path / ".sifta_state"

    row = build_unified_field(state_dir=state, now=1_777_000_000.0)
    prompt = format_unified_field_for_prompt(state_dir=state, now=1_777_000_000.0)

    assert row["watching_together"] is False
    assert row["field_confidence"] == 0.0
    assert row["owner_activity"].startswith("No fresh")
    assert prompt == ""
