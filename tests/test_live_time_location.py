from datetime import datetime
import json

import pytest

from System import swarm_hardware_time_oracle as clock
from System import swarm_gps_sensor as gps
from System import swarm_web_global_chat_night_worker as web


def instant(value):
    return datetime.fromisoformat(value).timestamp()


def test_local_clock_offset_and_date(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Bucharest")
    data = clock.live_clock_snapshot(epoch=instant("2026-09-08T21:30:00+00:00"))
    assert data["local_iso"] == "2026-09-09T00:30:00+03:00"
    assert data["timezone"] == "Europe/Bucharest"
    assert data["utc_offset_seconds"] == 10800


@pytest.mark.parametrize("utc, expected", [
    ("2026-03-29T00:30:00+00:00", "01:30:00"),
    ("2026-03-29T01:30:00+00:00", "03:30:00"),
    ("2026-10-25T00:30:00+00:00", "02:30:00"),
    ("2026-10-25T01:30:00+00:00", "02:30:00"),
])
def test_paris_dst(utc, expected):
    answer = clock.direct_clock_answer("What time is it in Paris?", epoch=instant(utc))
    assert expected in answer and "Europe/Paris" in answer


def test_romania_and_paris_same_instant():
    prompt = clock.live_time_prompt("Paris and Romania", epoch=instant("2026-09-08T18:45:00+00:00"))
    assert "Europe/Paris=2026-09-08T20:45:00+02:00" in prompt
    assert "Europe/Bucharest=2026-09-08T21:45:00+03:00" in prompt


def test_clock_advances_and_timezone_changes(monkeypatch):
    monkeypatch.setattr(clock.time, "time", lambda: instant("2026-09-08T18:45:00+00:00"))
    monkeypatch.setenv("TZ", "Europe/Paris")
    assert "20:45:00" in clock.live_time_prompt()
    monkeypatch.setenv("TZ", "Europe/Bucharest")
    monkeypatch.setattr(clock.time, "time", lambda: instant("2026-09-08T18:46:00+00:00"))
    assert "21:46:00" in clock.live_time_prompt()


def test_direct_clock_does_not_take_other_tasks():
    assert clock.direct_clock_answer("/create a photo in Paris") == ""
    assert clock.direct_clock_answer("What time is it in Paris and create a photo?") == ""
    assert "IANA" in clock.direct_clock_answer("What time is it in Unknowncity?")
    assert "Europe/Paris" in clock.direct_clock_answer("Ce ora este in Paris?")


def test_public_clock_bypasses_model(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "choose_local_model", lambda: pytest.fail("clock must not need Ollama"))
    monkeypatch.setattr(web, "_ollama_turn", lambda *a, **k: pytest.fail("no inference for clock"))
    reply, model, stamp, reason = web.answer_web_turn(
        {"text": "What time is it in Paris?"}, ingress_path=tmp_path / "in", replies_path=tmp_path / "out")
    assert "Europe/Paris" in reply
    assert (model, stamp, reason) == ("os_clock", {}, "STOP")


def test_public_dispatch_has_clock_without_private_location(monkeypatch):
    monkeypatch.setattr(gps, "read_location_snapshot", lambda **kw: pytest.fail("visitor accessed location"))
    messages = [{"role": "system", "content": "Alice"}, {"role": "user", "content": "Paris"}]
    updated = clock.with_live_awareness(messages)
    assert "Europe/Paris=" in updated[0]["content"]
    assert "private" in updated[0]["content"]
    assert messages[0]["content"] == "Alice"
    again = clock.with_live_awareness(updated)
    assert again[0]["content"].count("[SIFTA_LIVE_AWARENESS]") == 1


def fix(tmp_path, **changes):
    data = dict(status="SUCCESS", source="macos_corelocation", latitude=44.4,
                longitude=26.1, accuracy=80, observed_at=1000)
    (tmp_path / "mac_location_latest.json").write_text(json.dumps({**data, **changes}))


@pytest.mark.parametrize("changes,status", [
    ({}, "SUCCESS"), ({"observed_at": 100}, "STALE"),
    ({"observed_at": 2000}, "STALE"), ({"accuracy": -1}, "INVALID"),
    ({"latitude": 91}, "INVALID"), ({"longitude": float("nan")}, "INVALID"),
    ({"source": "timezone"}, "INVALID"), ({"status": "TIMEOUT"}, "TIMEOUT"),
])
def test_location_validation(tmp_path, changes, status):
    fix(tmp_path, **changes)
    assert gps.read_location_snapshot(state_dir=tmp_path, now=1100)["status"] == status


def test_owner_location_age_and_unavailable(tmp_path):
    assert "UNAVAILABLE" in gps.location_prompt_block(state_dir=tmp_path)
    fix(tmp_path)
    text = gps.location_prompt_block(state_dir=tmp_path, now=1100)
    assert "age_seconds=100" in text and "accuracy_radius_m=80" in text
    assert "44.40000" in text
    assert "44.40000" not in gps.location_prompt_block(public=True, state_dir=tmp_path, now=1100)


def test_failed_refresh_replaces_old_fix(tmp_path, monkeypatch):
    fix(tmp_path)
    class Unavailable:
        def __init__(self, **kwargs):
            pass
        def get_current_location(self):
            return {"status": "TIMEOUT"}
    monkeypatch.setattr(gps, "SwarmGPSSensor", Unavailable)
    gps.refresh_location(state_dir=tmp_path)
    assert gps.read_location_snapshot(state_dir=tmp_path)["status"] == "TIMEOUT"


def test_web_transport_injects_clock(monkeypatch):
    captured = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b'{"message":{"content":"OK."}}'
    def urlopen(request, **kwargs):
        captured.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr(web.urllib.request, "urlopen", urlopen)
    web._ollama_turn("test", [{"role": "user", "content": "Paris"}], timeout_s=1)
    assert "LIVE CLOCK AT DISPATCH" in captured[0]["messages"][0]["content"]

