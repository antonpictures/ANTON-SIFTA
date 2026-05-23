import json
from pathlib import Path

from System import swarm_local_voice_pipeline as pipeline


def test_pipeline_prefers_sherpa_and_cosyvoice_command_when_configured(tmp_path):
    sherpa_model = tmp_path / "sherpa"
    sherpa_model.mkdir()

    report = pipeline.build_voice_pipeline_report(
        faster_whisper_model="tiny.en",
        env={
            pipeline.SHERPA_MODEL_DIR_ENV: str(sherpa_model),
            pipeline.COSYVOICE_COMMAND_ENV: (
                "python cosy_say.py --text-file {text_file} --out {wav_path}"
            ),
        },
        module_available=lambda name: name in {"sherpa_onnx", "faster_whisper"},
        path_exists=lambda value: Path(value).exists(),
        command_available=lambda name: name == "say",
        platform_name="Darwin",
    )

    assert report["selected_asr"]["id"] == "sherpa_onnx_streaming"
    assert report["selected_tts"]["id"] == "cosyvoice2_streaming"
    assert report["text_ledger_boundary"] is True
    assert report["raw_audio_stored"] is False
    assert report["direct_s2s"]["default_enabled"] is False
    assert report["direct_s2s"]["production_allowed"] is False
    assert report["stages"] == [
        "mic_vad",
        "local_asr",
        "wake_social_rlhs_gates",
        "alice_text_brain",
        "local_tts",
        "vocal_cords_receipt",
    ]


def test_pipeline_falls_back_to_faster_whisper_and_macos_say_on_this_shape():
    report = pipeline.build_voice_pipeline_report(
        faster_whisper_model="base.en",
        env={},
        module_available=lambda name: name == "faster_whisper",
        path_exists=lambda _value: False,
        command_available=lambda name: name == "say",
        platform_name="Darwin",
    )

    assert report["selected_asr"]["id"] == "faster_whisper"
    assert report["selected_asr"]["model_path"] == "base.en"
    assert report["selected_tts"]["id"] == "macos_say"
    assert report["fallbacks"] == {"asr": "faster_whisper", "tts": "macos_say"}


def test_direct_s2s_stays_out_of_production_even_when_research_flag_is_on():
    report = pipeline.build_voice_pipeline_report(
        env={pipeline.DIRECT_S2S_ENV: "1"},
        module_available=lambda name: name == "faster_whisper",
        path_exists=lambda _value: False,
        command_available=lambda name: name == "say",
        platform_name="Darwin",
    )

    assert report["direct_s2s"]["experiment_enabled"] is True
    assert report["direct_s2s"]["default_enabled"] is False
    assert report["direct_s2s"]["production_allowed"] is False


def test_voice_pipeline_receipt_omits_audio_and_transcript(monkeypatch, tmp_path):
    ledger = tmp_path / "voice_pipeline.jsonl"
    monkeypatch.setattr(pipeline, "PIPELINE_LEDGER", ledger)
    report = pipeline.build_voice_pipeline_report(
        env={},
        module_available=lambda name: name == "faster_whisper",
        path_exists=lambda _value: False,
        command_available=lambda name: name == "say",
        platform_name="Darwin",
    )

    row = pipeline.write_voice_pipeline_receipt(
        report,
        kind="VOICE_PIPELINE_TEST",
        extra={"audio_samples": 16000, "raw_audio_stored": False},
    )

    saved = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert saved["receipt_id"] == row["receipt_id"]
    assert saved["text_ledger_boundary"] is True
    assert saved["direct_s2s_default_enabled"] is False
    assert saved["raw_audio_stored"] is False
    assert "text" not in saved
    assert "transcript" not in saved
    assert "audio" not in saved


def test_vocal_cords_auto_prefers_configured_cosyvoice_command(monkeypatch):
    from System.swarm_vocal_cords import get_default_backend, reset_default_backend

    monkeypatch.setenv("SIFTA_COSYVOICE2_COMMAND", "python cosy_say.py")
    monkeypatch.delenv("SIFTA_VOICE_BACKEND", raising=False)
    reset_default_backend()
    try:
        assert get_default_backend().name == "cosyvoice2"
    finally:
        reset_default_backend()
