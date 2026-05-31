from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import Applications.sifta_teach_ace_to_read as ace


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:
        self.text = value


class _FakeAce:
    _append_jsonl_receipt = ace.TeachAceToReadWidget._append_jsonl_receipt
    _seek_consent_ledgers_to_tail = ace.TeachAceToReadWidget._seek_consent_ledgers_to_tail
    _maybe_apply_direct_word_command_from_chat = (
        ace.TeachAceToReadWidget._maybe_apply_direct_word_command_from_chat
    )
    _apply_direct_word_command = ace.TeachAceToReadWidget._apply_direct_word_command

    def __init__(self, tmp_path: Path) -> None:
        self._current_word = "dolphin"
        self._heard_lbl = _Label()
        self._consent_ledger_proposal = tmp_path / "wordace_proposal.jsonl"
        self._consent_ledger_consent = tmp_path / "wordace_consent.jsonl"
        self._direct_word_command_ledger = tmp_path / "wordace_direct_word_command.jsonl"
        self._consent_proposal_offset = 0
        self._consent_consent_offset = 0
        self.swaps = []

    def _swap_word(self, new_word: str, *, pending: dict, consent: dict) -> None:
        self.swaps.append((new_word, pending, consent))
        self._current_word = new_word


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(
    "text",
    [
        "Let's pick the next word mirror and print it on a screen.",
        "The next word should be mirror.",
        "Let's set up the next work as mirror.",
        "Print mirror on the screen.",
    ],
)
def test_ace_extracts_explicit_next_word_commands(text):
    assert ace._extract_wordace_direct_word_command(text) == "mirror"


def test_ace_does_not_extract_discussion_as_word_command():
    text = "Can dolphins recognize themselves in a mirror?"

    assert ace._extract_wordace_direct_word_command(text) == ""


def test_ace_chat_word_command_swaps_card_and_writes_receipts(tmp_path):
    widget = _FakeAce(tmp_path)

    applied = widget._maybe_apply_direct_word_command_from_chat(
        "Let's pick the next word mirror and print it on a screen."
    )

    assert applied is True
    assert widget._current_word == "mirror"
    assert widget.swaps[0][0] == "mirror"
    proposal = _jsonl(widget._consent_ledger_proposal)[0]
    consent = _jsonl(widget._consent_ledger_consent)[0]
    direct = _jsonl(widget._direct_word_command_ledger)[0]
    assert proposal["schema"] == "WORDACE_PROPOSAL_V1"
    assert proposal["proposed_word"] == "mirror"
    assert consent["schema"] == "WORDACE_CONSENT_V1"
    assert consent["proposal_id"] == proposal["proposal_id"]
    assert direct["schema"] == "WORDACE_DIRECT_WORD_COMMAND_V1"
    assert direct["applied"] is True
    assert widget._consent_proposal_offset == widget._consent_ledger_proposal.stat().st_size
    assert widget._consent_consent_offset == widget._consent_ledger_consent.stat().st_size


def test_ace_chat_question_does_not_swap_card_or_write_receipts(tmp_path):
    widget = _FakeAce(tmp_path)

    applied = widget._maybe_apply_direct_word_command_from_chat(
        "Can dolphins recognize themselves in a mirror?"
    )

    assert applied is False
    assert widget._current_word == "dolphin"
    assert widget.swaps == []
    assert not widget._direct_word_command_ledger.exists()
