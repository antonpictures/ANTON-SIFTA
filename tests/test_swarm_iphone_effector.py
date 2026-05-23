import json
from pathlib import Path

from System import swarm_iphone_effector as effector


def _ledger_rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_default_send_swimmer_is_dry_run_and_never_calls_osascript(monkeypatch, tmp_path):
    ledger = tmp_path / "iphone_effector_trace.jsonl"
    called = {"osascript": False}

    monkeypatch.setattr(effector, "_read_target_id", lambda: "+15551234567")
    monkeypatch.setattr(
        effector.subprocess,
        "check_output",
        lambda *_args, **_kwargs: called.__setitem__("osascript", True),
    )

    result = effector.send_swimmer(
        "FLASHLIGHT:ON",
        source="architect",
        ledger_path=ledger,
    )

    assert result["ok"] is True
    assert result["status"] == "DRY_RUN"
    assert result["dry_run"] is True
    assert called["osascript"] is False
    row = _ledger_rows(ledger)[0]
    assert row["event_kind"] == effector.EVENT_KIND
    assert row["schema"] == effector.SCHEMA
    assert row["receipt_hash"]


def test_actual_send_requires_authorized_source(monkeypatch, tmp_path):
    ledger = tmp_path / "iphone_effector_trace.jsonl"
    called = {"count": 0}

    monkeypatch.setattr(effector, "_read_target_id", lambda: "+15551234567")
    monkeypatch.setattr(
        effector.subprocess,
        "check_output",
        lambda *_args, **_kwargs: called.__setitem__("count", called["count"] + 1),
    )

    result = effector.send_swimmer(
        "FLASHLIGHT:ON",
        dry_run=False,
        allow_send=True,
        source="unknown-worker",
        ledger_path=ledger,
    )

    assert result["ok"] is False
    assert result["status"] == "BLOCKED_UNAUTHORIZED_SOURCE"
    assert called["count"] == 0


def test_non_allowlisted_swimmer_payload_is_rejected(monkeypatch, tmp_path):
    ledger = tmp_path / "iphone_effector_trace.jsonl"
    monkeypatch.setattr(effector, "_read_target_id", lambda: "+15551234567")

    result = effector.send_swimmer(
        "ERASE:PHONE",
        dry_run=False,
        allow_send=True,
        source="architect",
        ledger_path=ledger,
    )

    assert result["ok"] is False
    assert result["status"] == "BLOCKED_NOT_ALLOWLISTED"


def test_send_text_requires_plain_text_opt_in(monkeypatch, tmp_path):
    ledger = tmp_path / "iphone_effector_trace.jsonl"
    monkeypatch.setattr(effector, "_read_target_id", lambda: "+15551234567")

    blocked = effector.send_swimmer(
        "plain hello",
        prefix=False,
        dry_run=False,
        allow_send=True,
        source="architect",
        ledger_path=ledger,
    )
    allowed_dry = effector.send_swimmer(
        "plain hello",
        prefix=False,
        dry_run=True,
        allow_send=True,
        allow_plain_text=True,
        source="architect",
        ledger_path=ledger,
    )

    assert blocked["status"] == "BLOCKED_PLAIN_TEXT_REQUIRES_OPT_IN"
    assert allowed_dry["status"] == "DRY_RUN"


def test_actual_send_and_duplicate_suppression(monkeypatch, tmp_path):
    ledger = tmp_path / "iphone_effector_trace.jsonl"
    calls = {"count": 0}

    monkeypatch.setattr(effector, "_read_target_id", lambda: "+15551234567")

    def fake_check_output(args, **_kwargs):
        calls["count"] += 1
        assert args[0] == "osascript"
        assert 'send "SIFTA_SWIM:FLASHLIGHT:ON"' in args[2]
        return "sent"

    monkeypatch.setattr(effector.subprocess, "check_output", fake_check_output)

    first = effector.send_swimmer(
        "FLASHLIGHT:ON",
        dry_run=False,
        allow_send=True,
        source="architect",
        ledger_path=ledger,
    )
    second = effector.send_swimmer(
        "FLASHLIGHT:ON",
        dry_run=False,
        allow_send=True,
        source="architect",
        ledger_path=ledger,
    )

    assert first["status"] == "SENT"
    assert second["status"] == "DUPLICATE_SUPPRESSED"
    assert calls["count"] == 1


def test_govern_defaults_to_dry_run(monkeypatch, tmp_path):
    ledger = tmp_path / "iphone_effector_trace.jsonl"
    monkeypatch.setattr(effector, "_read_target_id", lambda: "+15551234567")
    monkeypatch.setattr(effector, "_deposit_trace", lambda row, **_kwargs: row)
    monkeypatch.setattr(
        effector.subprocess,
        "check_output",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not send")),
    )

    result = effector.govern(
        "send_swimmer",
        payload="FLASHLIGHT:ON",
        source="System.alice_body_autopilot",
    )

    assert result["status"] == "DRY_RUN"


def test_autopilot_forwards_dry_run_to_iphone_effector(monkeypatch):
    from System import alice_body_autopilot
    from System import swarm_iphone_effector

    captured = {}

    def fake_govern(verb, **kwargs):
        captured["verb"] = verb
        captured["kwargs"] = kwargs
        return {"ok": True, "status": "DRY_RUN"}

    monkeypatch.setattr(swarm_iphone_effector, "govern", fake_govern)

    result = alice_body_autopilot.govern(
        "iphone.send_swimmer",
        dry_run=True,
        hw_kwargs={"payload": "FLASHLIGHT:ON"},
    )

    assert result["ok"] is True
    assert captured["verb"] == "send_swimmer"
    assert captured["kwargs"]["dry_run"] is True
    assert captured["kwargs"]["source"] == "System.alice_body_autopilot"
