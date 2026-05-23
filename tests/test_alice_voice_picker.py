from Applications.sifta_talk_to_alice_widget import _curate_alice_voice_rows
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_alice_voice_picker_curates_raw_macos_inventory():
    rows = [
        ("Ava (Premium)", "en_US"),
        ("Bubbles", "en_US"),
        ("Grandma (Chinese (China mainland))", "zh_CN"),
        ("Eddy (French (France))", "fr_FR"),
        ("Samantha", "en_US"),
        ("Alex", "en_US"),
        ("Karen", "en_AU"),
        ("Daniel", "en_GB"),
        ("Ralph", "en_US"),
    ]

    curated = _curate_alice_voice_rows(rows, limit=5)

    assert curated == [
        ("Ava (Premium)", "en_US"),
        ("Samantha", "en_US"),
        ("Alex", "en_US"),
        ("Karen", "en_AU"),
        ("Daniel", "en_GB"),
    ]
    assert all("Grandma" not in name for name, _locale in curated)
    assert all("Eddy" not in name for name, _locale in curated)
    assert all(name != "Bubbles" for name, _locale in curated)


def test_alice_voice_picker_has_one_english_fallback_not_full_dump():
    rows = [
        ("Bubbles", "en_US"),
        ("Grandma (Chinese (China mainland))", "zh_CN"),
        ("Eddy (French (France))", "fr_FR"),
    ]

    assert _curate_alice_voice_rows(rows, limit=5) == []


def test_alice_cockpit_has_no_mute_interrupt_or_stt_model_picker():
    source = (REPO / "Applications" / "sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")

    forbidden = (
        "_mute_btn",
        "_interrupt_btn",
        "_listen_only_btn",
        "_on_mute_toggled",
        "_on_interrupt_clicked",
        "_whisper_combo",
        "_brain_combo",
        "_WHISPER_MODELS",
        "_gain_slider",
        "_gain_label",
        "_voice_combo",
        "_ctx_btn",
        "_on_gain_slider_changed",
        "_populate_voices",
        "mute mic",
        "press interrupt",
        "⏹ interrupt",
        "listen-only",
        "brain and voice are bypassed",
        "Speech-to-text model.",
        "ground in swarm state",
        "via the Model menu",
    )
    for token in forbidden:
        assert token not in source


def test_alice_audio_controls_live_in_system_settings_audio():
    source = (REPO / "Applications" / "sifta_system_settings.py").read_text(encoding="utf-8")

    assert '"Audio": self._audio_page()' in source
    assert "self.audio_whisper_combo" in source
    assert "self.audio_gain_slider" in source
    assert "self.audio_voice_combo" in source
    assert "self.audio_grounding_check" in source
