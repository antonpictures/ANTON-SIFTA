from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk


class FakeMatrixPane:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.traces: list[dict] = []

    def write_bytes(self, data: bytes) -> None:
        self.writes.append(data)

    def _append_process_trace(self, text: str, *, kind: str, action: str, payload: dict) -> None:
        self.traces.append(
            {
                "text": text,
                "kind": kind,
                "action": action,
                "payload": dict(payload),
            }
        )


def test_typed_press_enter_writes_real_pty_keystroke() -> None:
    pane = FakeMatrixPane()

    result = talk._typed_direct_key_command_to_matrix_pty(
        "Now press enter",
        typed_turn=True,
        pane=pane,
    )

    assert result["executed"] is True
    assert result["reason"] == "direct_key_written"
    assert pane.writes == [b"\n"]
    assert pane.traces[0]["kind"] == "direct_key"
    assert pane.traces[0]["action"] == "talk_direct_key_command"
    assert pane.traces[0]["payload"]["raw_input"] == "Now press enter"


def test_spoken_press_enter_does_not_fire_directly() -> None:
    pane = FakeMatrixPane()

    result = talk._typed_direct_key_command_to_matrix_pty(
        "press enter",
        typed_turn=False,
        pane=pane,
    )

    assert result["executed"] is False
    assert result["reason"] == "not_typed_turn"
    assert pane.writes == []
    assert pane.traces == []


def test_normal_conversation_reaches_cortex_path() -> None:
    pane = FakeMatrixPane()

    result = talk._typed_direct_key_command_to_matrix_pty(
        "Alice, what are we working on?",
        typed_turn=True,
        pane=pane,
    )

    assert result["executed"] is False
    assert result["reason"] == "not_direct_key_command"
    assert pane.writes == []
    assert pane.traces == []


def test_type_text_command_does_not_become_hidden_keystroke() -> None:
    pane = FakeMatrixPane()

    result = talk._typed_direct_key_command_to_matrix_pty(
        'type "hello"',
        typed_turn=True,
        pane=pane,
    )

    assert result["executed"] is False
    assert result["reason"] == "not_keystroke_command"
    assert pane.writes == []
    assert pane.traces == []
