#!/usr/bin/env python3
"""WhatsApp location ingress — the coordinates must survive the row, or not be claimed.

The Architect sent a live location from his iPhone SE while walking the lake and Alice
answered about the words only: `bridge.js` captured the share, the HTTP handler never read
the `location` field, and `build_inbox_row` had no slot for it. Measured 2026-10-05 over the
whole inbox: 365 rows, zero carrying coordinates.

These tests pin the three things that failure needs: coordinates survive into a signed row,
a location-only share is not rejected as empty text, and a position that is stale or tampered
is never reported as current.

Every ledger path is redirected into `tmp_path`. A test that writes the real
`whatsapp_location_latest.json` can make Alice state a position the Architect never occupied,
so the isolation is a correctness requirement, not tidiness: it was a real leak, caught by
the live ingress check on 2026-10-05.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import System.swarm_whatsapp_receptor as receptor  # noqa: E402
from System.swarm_whatsapp_receptor import (  # noqa: E402
    LOCATION_FRESH_WINDOW_S,
    build_inbox_row,
    latest_location,
    record_location_trace,
    validate_inbox_row,
)

LIVE_SHARE = {"lat": 32.98861, "lon": -115.53033, "live": True, "name": "", "expires": 1791219999}
PIN_SHARE = {"lat": 32.98861, "lon": -115.53033, "live": False, "name": "Apartamentul"}


@pytest.fixture(autouse=True)
def isolate_position_ledgers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect both position ledgers into `tmp_path` for every test in this module."""
    monkeypatch.setattr(receptor, "LOCATION_TRACES_FILE", tmp_path / "traces.jsonl")
    monkeypatch.setattr(receptor, "LOCATION_LATEST_FILE", tmp_path / "latest.json")


def test_ledger_isolation_guard_is_actually_redirecting() -> None:
    """Prove the fixture points away from production before trusting any test below."""
    assert receptor.LOCATION_LATEST_FILE.parent.name != ".sifta_state"
    assert receptor.LOCATION_TRACES_FILE.parent.name != ".sifta_state"


def test_location_only_share_is_not_rejected_as_empty_text() -> None:
    """A live share with no words must still produce a valid row, marked legibly."""
    row = build_inbox_row(
        "", from_jid="211338915749903@lid", name="Georgica", location=LIVE_SHARE,
    )
    assert row["text"] == "[live location]"
    assert row["location"]["lat"] == 32.98861
    assert row["location"]["live"] is True
    assert validate_inbox_row(row) == (True, "ok")


def test_static_pin_gets_its_own_marker_and_label() -> None:
    """A one-shot pin is distinguishable from a live follow."""
    row = build_inbox_row("", from_jid="211338915749903@lid", location=PIN_SHARE)
    assert row["text"] == "[location]"
    assert row["location"]["name"] == "Apartamentul"
    assert row["location"]["live"] is False
    assert validate_inbox_row(row) == (True, "ok")


def test_words_are_never_replaced_by_the_location_marker() -> None:
    """When he writes and shares at once, both survive."""
    row = build_inbox_row(
        "I sent you a live location", from_jid="211338915749903@lid", location=LIVE_SHARE,
    )
    assert row["text"] == "I sent you a live location"
    assert row["location"]["lat"] == 32.98861


def test_coordinates_are_covered_by_the_signature() -> None:
    """A tampered position fails validation, exactly as a tampered message does."""
    row = build_inbox_row("", from_jid="211338915749903@lid", location=LIVE_SHARE)
    assert validate_inbox_row(row)[0] is True
    row["location"]["lat"] = 0.0
    ok, reason = validate_inbox_row(row)
    assert ok is False
    assert reason == "signature_mismatch"


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"lat": 32.98},
        {"lat": "32.98", "lon": "-115.5"},
        {"lat": 91.0, "lon": 0.0},
        {"lat": 0.0, "lon": 181.0},
        {"lat": True, "lon": 12.0},
    ],
)
def test_a_share_without_usable_numbers_never_invents_a_position(bad: object) -> None:
    """Malformed or absurd payloads produce no location field at all."""
    row = build_inbox_row("hello", from_jid="211338915749903@lid", location=bad)
    assert "location" not in row
    assert validate_inbox_row(row) == (True, "ok")


def test_trace_ledger_and_hot_cache_carry_the_fix() -> None:
    """An accepted row reaches both the stream and the latest-position cache."""
    row = build_inbox_row("", from_jid="211338915749903@lid", name="Georgica", location=LIVE_SHARE)
    entry = record_location_trace(row)
    assert entry is not None
    assert entry["lat"] == 32.98861
    assert entry["lon"] == -115.53033
    assert entry["live"] is True
    assert entry["transaction_type"] == "WHATSAPP_LOCATION_FIX"

    tail = receptor.LOCATION_TRACES_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert json.loads(tail)["lat"] == 32.98861
    cached = json.loads(receptor.LOCATION_LATEST_FILE.read_text(encoding="utf-8"))
    assert cached["lon"] == -115.53033


def test_a_row_without_location_writes_no_trace() -> None:
    """Text-only traffic must not pollute the position ledger."""
    row = build_inbox_row("just words", from_jid="211338915749903@lid")
    assert record_location_trace(row) is None
    assert receptor.LOCATION_TRACES_FILE.exists() is False
    assert receptor.LOCATION_LATEST_FILE.exists() is False


def test_a_stale_fix_is_refused_rather_than_spoken_as_current() -> None:
    """Past the freshness window the answer is None, never a stale 'you are here'."""
    receptor.LOCATION_LATEST_FILE.write_text(
        json.dumps({
            "transaction_type": "WHATSAPP_LOCATION_FIX",
            "lat": 32.98861, "lon": -115.53033,
            "recorded_ts": time.time() - (LOCATION_FRESH_WINDOW_S + 60.0),
        }),
        encoding="utf-8",
    )
    assert latest_location() is None
    assert latest_location(max_age_s=LOCATION_FRESH_WINDOW_S * 10) is not None


def test_a_fresh_fix_is_returned_with_its_age() -> None:
    """A live walk share answers 'where is he now', with the age attached."""
    receptor.LOCATION_LATEST_FILE.write_text(
        json.dumps({
            "transaction_type": "WHATSAPP_LOCATION_FIX",
            "lat": 32.98861, "lon": -115.53033,
            "recorded_ts": time.time() - 12.0,
        }),
        encoding="utf-8",
    )
    fix = latest_location()
    assert fix is not None
    assert fix["lat"] == 32.98861
    assert 10.0 < fix["age_s"] < 30.0


def test_missing_ledgers_are_absence_not_error() -> None:
    """With nothing recorded the body says it does not know, and does not throw."""
    assert receptor.LOCATION_LATEST_FILE.exists() is False
    assert latest_location() is None


def _load_server_module():
    """Load scripts/whatsapp_alice_server.py without starting its HTTP server."""
    path = REPO / "scripts" / "whatsapp_alice_server.py"
    spec = importlib.util.spec_from_file_location("whatsapp_alice_server_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_http_ingress_path_keeps_the_coordinates(tmp_path: Path, monkeypatch) -> None:
    """The link that actually dropped them: handler -> _deposit_inbox -> inbox row.

    Runs against a scratch inbox, so the Architect's real conversation log is never seeded
    with a test position.
    """
    server = _load_server_module()
    monkeypatch.setattr(server, "INBOX_FILE", tmp_path / "inbox.jsonl")

    server._deposit_inbox(
        "", "211338915749903@lid", "Georgica",
        from_me=False, chat_type="direct", location=LIVE_SHARE,
    )

    written = json.loads(server.INBOX_FILE.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert written["text"] == "[live location]"
    assert written["location"]["lat"] == 32.98861
    assert written["location"]["lon"] == -115.53033
    assert validate_inbox_row(written) == (True, "ok")

    traced = json.loads(receptor.LOCATION_TRACES_FILE.read_text(encoding="utf-8").strip())
    assert traced["lat"] == 32.98861
    assert traced["live"] is True
    cached = json.loads(receptor.LOCATION_LATEST_FILE.read_text(encoding="utf-8"))
    assert cached["lon"] == -115.53033


def test_the_http_ingress_path_still_queues_plain_text(tmp_path: Path, monkeypatch) -> None:
    """Text-only traffic keeps working and writes no position."""
    server = _load_server_module()
    monkeypatch.setattr(server, "INBOX_FILE", tmp_path / "inbox.jsonl")

    server._deposit_inbox("buna", "211338915749903@lid", "Georgica", chat_type="direct")

    written = json.loads(server.INBOX_FILE.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert written["text"] == "buna"
    assert "location" not in written
    assert receptor.LOCATION_TRACES_FILE.exists() is False
