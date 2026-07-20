"""Romanian TTS routing — Alice must speak Romanian with the ro_RO voice.

George types Romanian in plain ASCII ("Vorbeste Romaneste cu mine"), so
detection cannot depend on diacritics. These tests pin both halves of the
contract: ASCII Romanian routes to Ioana, and English never does — a false
positive would put Alice's English in a Romanian accent mid-scalp.
"""

import pytest

from Applications.sifta_talk_to_alice_widget import (
    _detect_romanian,
    _tts_voice_for_text,
)
from System.swarm_broca_wernicke import _is_romanian as _broca_is_romanian

ROMANIAN_ASCII = [
    "Foarte bine alice, Vorbeste Romaneste cu mine",
    "Multumesc Alice",
    "Salut ce faci astazi",
    "Care este cea mai mare problema?",
    "Te rog spunemi ce vrei sa facem acum",
    "ne vom apuca de text",
    "Sunt aici pentru tine",
    "nu inteleg intrebarea",
    "da, vreau sa vorbim romaneste",
]

ROMANIAN_DIACRITICS = [
    "Sunt aici pentru asta! Dar să ne mai facem un pas înainte",
    "Mulțumesc! Îmi place foarte mult să vorbesc în română cu tine",
    "Care este cea mai mare problemă care le deranjează în prezent?",
]

# English that shares tokens with Romanian stopwords (care, mine, mai, la,
# am, are). These are the false-positive traps the word lists exclude.
ENGLISH = [
    "I care about the mine in la paz today",
    "we are here and we do care about it",
    "La la la, this is a song",
    "The regime gate blocked entry because implied probability was too high",
    "Keep scalping, keep the machine on",
    "I am not going to gamble, the scalp is automatic",
    "so what do you want to do now",
]


@pytest.mark.parametrize("text", ROMANIAN_ASCII)
def test_ascii_romanian_detected_without_diacritics(text):
    assert _detect_romanian(text) is True


@pytest.mark.parametrize("text", ROMANIAN_DIACRITICS)
def test_romanian_with_diacritics_detected(text):
    assert _detect_romanian(text) is True


@pytest.mark.parametrize("text", ENGLISH)
def test_english_never_routes_to_romanian_voice(text):
    assert _detect_romanian(text) is False
    assert _tts_voice_for_text(text, "Samantha") == "Samantha"


@pytest.mark.parametrize("text", ROMANIAN_ASCII + ROMANIAN_DIACRITICS)
def test_romanian_routes_to_ioana(text):
    assert _tts_voice_for_text(text, "Samantha") == "Ioana"


def test_empty_and_trivial_text_is_not_romanian():
    assert _detect_romanian("") is False
    assert _detect_romanian("   ") is False
    assert _detect_romanian("123 456") is False


@pytest.mark.parametrize(
    "text", ROMANIAN_ASCII + ROMANIAN_DIACRITICS + ENGLISH
)
def test_widget_and_broca_detectors_agree(text):
    """Both mouths must classify identically or Alice's voice flips between
    the Talk widget and swarm-level Broca speech for the same sentence."""
    assert _detect_romanian(text) == _broca_is_romanian(text)
