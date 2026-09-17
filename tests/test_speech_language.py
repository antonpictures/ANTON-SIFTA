"""Speech-language routing — one voice decision for every Alice mouth.

Root cause this suite pins: macOS reports this Mac's Romanian voice as
"Ioana (Romanian (Romania))", while three call sites compared the exact string
"Ioana". The check never matched, so Romanian replies were handed to the
English default voice and read with English phonetics. The public web mouth had
no detection at all.
"""

import pytest

from System import swarm_speech_language as sl


RO_LOCALE = "ro_RO"
REAL_ROMANIAN_VOICE = "Ioana (Romanian (Romania))"

FAKE_INVENTORY = {
    "Samantha": "en_US",
    REAL_ROMANIAN_VOICE: RO_LOCALE,
}

ROMANIAN = [
    "Multumesc Alice",
    "Vorbeste romaneste cu mine",
    "Sunt aici pentru tine",
    "Mulțumesc! Îmi place să vorbesc în română",
]

ENGLISH = [
    "Thanks Alice, keep going",
    "so what do you want to do now",
    "The regime gate blocked entry because implied probability was too high",
]


@pytest.mark.parametrize("text", ROMANIAN)
def test_romanian_detected(text):
    assert sl.detect_language(text) == "romanian"
    assert sl.is_romanian(text) is True


@pytest.mark.parametrize("text", ENGLISH)
def test_english_detected(text):
    assert sl.detect_language(text) == "english"
    assert sl.is_romanian(text) is False


@pytest.mark.parametrize("text", ROMANIAN)
def test_romanian_routes_to_locale_matched_voice(text):
    """The regression: a locale-qualified name must still match."""
    voice = sl.voice_for_text(text, "Samantha", available=FAKE_INVENTORY)
    assert voice == REAL_ROMANIAN_VOICE
    assert voice != "Samantha"


@pytest.mark.parametrize("text", ENGLISH)
def test_english_keeps_the_owner_voice(text):
    assert sl.voice_for_text(text, "Samantha", available=FAKE_INVENTORY) == "Samantha"


def test_missing_romanian_voice_degrades_to_default_not_silence():
    only_english = {"Samantha": "en_US"}
    assert sl.voice_for_text("Multumesc Alice", "Samantha", available=only_english) == "Samantha"


def test_bare_legacy_name_still_matches():
    """Older installs may expose a bare 'Ioana'; both spellings must work."""
    legacy = {"Ioana": RO_LOCALE, "Samantha": "en_US"}
    assert sl.voice_for_text("Multumesc Alice", "Samantha", available=legacy) == "Ioana"


def test_exact_locale_beats_partial_family():
    inventory = {
        "Other Romanian": "ro_MD",
        REAL_ROMANIAN_VOICE: RO_LOCALE,
    }
    assert sl.macos_voice_for_locale("ro_RO", available=inventory) == REAL_ROMANIAN_VOICE
    assert sl.macos_voice_for_locale("zz", available=inventory) == ""


def test_empty_text_defaults_to_english():
    assert sl.detect_language("") == "english"
    assert sl.detect_language("   ") == "english"
    assert sl.voice_for_text("", "Samantha", available=FAKE_INVENTORY) == "Samantha"
