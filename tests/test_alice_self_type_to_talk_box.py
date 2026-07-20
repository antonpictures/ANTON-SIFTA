from __future__ import annotations

import json

import pytest

try:
    from Applications import sifta_talk_to_alice_widget as talk
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"Skipping Alice self-type tests: talk widget import failed "
        f"({type(exc).__name__}: {exc}).",
        allow_module_level=True,
    )


def test_write_alice_self_type_receipt_fans_to_ledgers(tmp_path):
    row = talk._write_alice_self_type_receipt(
        text="Hello World",
        source="test",
        sent=True,
        reason="owner_requested",
        state_dir=tmp_path,
    )

    assert row["truth_label"] == "ALICE_SELF_TYPE_TO_TALK_BOX_V1"
    assert row["action"] == "alice_self_type_to_talk_box"
    assert row["sent"] is True
    assert row["text_preview"] == "Hello World"

    for name in ("alice_self_type_to_talk_box.jsonl", "work_receipts.jsonl"):
        rows = [
            json.loads(line)
            for line in (tmp_path / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows[-1]["receipt_id"] == row["receipt_id"]


def test_alice_type_in_own_box_sets_input_and_sends(monkeypatch, tmp_path):
    class FakeInput:
        def __init__(self) -> None:
            self.value = ""
            self.focused = False

        def setText(self, value: str) -> None:
            self.value = value

        def setFocus(self) -> None:
            self.focused = True

    pane = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    pane._text_input = FakeInput()
    pane.sent = False
    pane.observable = []

    def fake_submit() -> None:
        pane.sent = True

    def fake_observable(line: str, *, reset: bool = False) -> None:
        pane.observable.append((line, reset))

    pane._submit_text_input = fake_submit
    pane._append_observable_processing = fake_observable
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)

    row = talk.TalkToAliceWidget.alice_type_in_own_box(
        pane,
        "Hello World",
        send=True,
    )

    assert pane._text_input.value == "Hello World"
    assert pane._text_input.focused is True
    assert pane.sent is True
    assert row["sent"] is True
    assert row["receipt_id"] in pane.observable[-1][0]


def test_extract_alice_self_type_payload_from_owner_request():
    assert (
        talk._extract_alice_self_type_box_payload(
            'Alice has to type "Hello World" in the box herself and click send'
        )
        == "Hello World"
    )
    assert (
        talk._extract_alice_self_type_box_payload(
            "she must put Hello World into the chat box"
        )
        == "Hello World"
    )
    assert talk._extract_alice_self_type_box_payload("Hello World") == ""
