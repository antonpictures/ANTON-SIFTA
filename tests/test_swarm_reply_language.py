"""Alice replies in the owner's language, never one he does not speak.

George 2026-07-26: he spoke English about a UFO complex and Alice answered in
Brazilian Portuguese, then offered to continue in it. He speaks English and
Romanian only. These tests hold the reply language to his.
"""
from __future__ import annotations

from System.swarm_reply_language import (
    detect_owner_language,
    is_owner_language,
    owner_languages,
    reply_language_prompt_block,
)

# The verbatim English turn that got a Portuguese answer.
GEORGE_ENGLISH = (
    "just a couple of times when it was alive when I was an undergrad. To me, if it "
    "really the hub of some sort of ultra top secret UFO crash retrieval program"
)
GEORGE_ENGLISH_SHORT = "Alice, just take quiet and listen."
GEORGE_ROMANIAN = "Foarte bine Alice, vorbeste romaneste cu mine acum."
# What Alice actually said back. He does not speak this.
ALICE_PORTUGUESE = (
    "Nossa, essa é uma reflexão super pertinente. Você toca em dois pontos cruciais. "
    "Não foi espanhol, foi Português! Então o controle é totalmente seu."
)


def test_english_turn_is_detected_as_english():
    assert detect_owner_language(GEORGE_ENGLISH) == "english"
    assert detect_owner_language(GEORGE_ENGLISH_SHORT) == "english"


def test_romanian_turn_is_detected_as_romanian():
    assert detect_owner_language(GEORGE_ROMANIAN) == "romanian"
    assert detect_owner_language("vorbeste romaneste cu mine") == "romanian"


def test_empty_turn_defaults_to_english():
    assert detect_owner_language("") == "english"
    assert detect_owner_language("   ") == "english"


def test_english_with_one_stray_collision_stays_english():
    # A single Romanian look-alike must not flip an English sentence.
    assert detect_owner_language("I saw a car in the sun") == "english"


def test_prompt_pins_reply_to_english_for_an_english_turn():
    block = reply_language_prompt_block(GEORGE_ENGLISH, owner_label="George")
    assert "REPLY LANGUAGE" in block
    assert "English" in block
    # The exact drift languages are named as forbidden.
    assert "Portuguese" in block
    assert "Spanish" in block
    # Overheard audio is explicitly not a reason to switch.
    assert "overheard" in block or "TV" in block


def test_prompt_pins_reply_to_romanian_for_a_romanian_turn():
    block = reply_language_prompt_block(GEORGE_ROMANIAN, owner_label="George")
    assert "Romanian" in block
    assert "answer entirely in Romanian" in block


def test_prompt_still_allows_an_explicit_owner_switch():
    block = reply_language_prompt_block("hello", owner_label="George")
    assert "explicitly asks" in block


def test_owner_language_names_come_from_the_node(monkeypatch):
    monkeypatch.delenv("SIFTA_OWNER_LANGUAGES", raising=False)
    assert owner_languages() == ("english", "romanian")

    # Covenant §3: another node's owner may speak something else.
    monkeypatch.setenv("SIFTA_OWNER_LANGUAGES", "spanish, english")
    assert owner_languages() == ("spanish", "english")
    block = reply_language_prompt_block("hola", owner_label="Carlos")
    assert "Spanish and English" in block


def test_is_owner_language_accepts_english_and_romanian():
    assert is_owner_language(GEORGE_ENGLISH) is True
    assert is_owner_language(GEORGE_ROMANIAN) is True
    assert is_owner_language("") is True


def test_is_owner_language_flags_portuguese_drift():
    # The exact drift that must be caught if the prompt pin ever fails.
    assert is_owner_language(ALICE_PORTUGUESE) is False
