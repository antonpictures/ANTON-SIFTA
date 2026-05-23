from __future__ import annotations

from typing import Any

import System.swarm_phone_call_tracker as tracker


def _capture_writes(monkeypatch: Any) -> list[tuple[str, dict[str, Any]]]:
    writes: list[tuple[str, dict[str, Any]]] = []

    def fake_event(**kwargs: Any) -> str:
        writes.append(("event", kwargs))
        return "fake-event"

    def fake_schedule(note: str, ts: float | None = None) -> None:
        writes.append(("schedule", {"note": note, "ts": ts}))

    monkeypatch.setattr(tracker, "_write_phone_event", fake_event)
    monkeypatch.setattr(tracker, "_write_schedule_entry", fake_schedule)
    return writes


def test_call_end_does_not_log_false_active_start(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration("I just got off the phone.", stt_conf=0.8)
    end_reply = tracker.handle_call_end("I just got off the phone.")

    assert event_type is None
    assert reply is None
    assert end_reply and end_reply.startswith("Call ended.")
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_end"]


def test_phone_call_ended_phrase_logs_only_end(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration("The phone call ended.", stt_conf=0.8)
    end_reply = tracker.handle_call_end("The phone call ended.")

    assert event_type is None
    assert reply is None
    assert end_reply and end_reply.startswith("Call ended.")
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_end"]


def test_just_hang_up_logs_only_call_end(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration(
        "Thank you Alice, I was on a phone and I just hang up.",
        stt_conf=0.8,
    )
    end_reply = tracker.handle_call_end("Thank you Alice, I was on a phone and I just hang up.")

    assert event_type is None
    assert reply is None
    assert end_reply and end_reply.startswith("Call ended.")
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_end"]


def test_active_phone_log_request_writes_start_and_schedule(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration(
        "I'm on the phone, please track my phone calls.",
        stt_conf=0.8,
    )

    assert event_type == "phone_call_active"
    assert reply and "Phone call logged" in reply
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_active"]
    assert [kind for kind, _row in writes].count("schedule") == 1


def test_active_phone_declaration_writes_schedule_even_without_reply(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration("I'm on the phone.", stt_conf=0.8)

    assert event_type == "phone_call_active"
    assert reply is None
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_active"]
    assert [kind for kind, _row in writes].count("schedule") == 1


def test_retroactive_phone_call_writes_observed_schedule(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration(
        "That was a phone conversation that you just heard.",
        stt_conf=0.8,
    )

    assert event_type == "phone_call_retroactive"
    assert reply and "Logged:" in reply
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_retroactive"]
    assert [kind for kind, _row in writes].count("schedule") == 1


def test_business_meeting_on_phone_is_retroactive_context(monkeypatch: Any) -> None:
    writes = _capture_writes(monkeypatch)

    event_type, reply = tracker.handle_phone_declaration(
        "Today I just found out the news on a phone. I had just had the business meeting today on a phone.",
        stt_conf=0.71,
    )

    assert event_type == "phone_call_retroactive"
    assert reply and "Logged:" in reply
    assert [row["event_type"] for kind, row in writes if kind == "event"] == ["phone_call_retroactive"]
    assert [kind for kind, _row in writes].count("schedule") == 1


def test_append_jsonl_supplies_terminal_newline(monkeypatch: Any, tmp_path: Any) -> None:
    lines: list[str] = []

    def fake_append(_path: Any, line: str) -> None:
        lines.append(line)

    monkeypatch.setattr(tracker, "append_line_locked", fake_append)
    tracker._append_jsonl(tmp_path / "phone.jsonl", {"event_type": "phone_call_end"})

    assert lines == ['{"event_type": "phone_call_end"}\n']
