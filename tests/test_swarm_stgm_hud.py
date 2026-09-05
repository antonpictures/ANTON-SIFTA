import json
import threading

import pytest

from System import swarm_stgm_hud as hud


def sources(sd, *, now=1000, status="FAULT"):
    (sd / "hardware_heart.jsonl").write_text(json.dumps({"ts": now, "receipt_id": "h1",
        "schema": "SIFTA_HARDWARE_HEART_V1"}) + "\n")
    (sd / "heartbeat_economy_latest.json").write_text(json.dumps({"ts": now,
        "event_id": "e1", "status": status, "delta_stgm": -.0001,
        "ed25519_sig": "test", "faults": ["supervisor"]}))
    (sd / "stgm_economy_cache.json").write_text(json.dumps({"cache_generated_at": now,
        "spendable_total_stgm": 12.0}))


def test_hud_reads_real_evidence_not_synthetic_balance(tmp_path, monkeypatch):
    sources(tmp_path)
    monkeypatch.setattr(hud, "signature_valid", lambda row: True)
    row = hud.hud_evidence(tmp_path, now=1001)
    assert row["state"] == "FAULT"
    assert row["delta"] == -.0001
    assert "-0.00010000" in row["detail"]
    assert row["heart_age"] == 1
    assert not row["cache_stale"]
    old = hud.hud_evidence(tmp_path, now=1400)
    assert old["state"] == "STALE"
    assert not old["heart_id"]
    assert old["cache_stale"]


def test_hud_unknown_unsigned_and_corrupt_data(tmp_path, monkeypatch):
    assert hud.hud_evidence(tmp_path, now=1000)["state"] == "STALE"
    sources(tmp_path)
    monkeypatch.setattr(hud, "signature_valid", lambda row: False)
    row = hud.hud_evidence(tmp_path, now=1000)
    assert row["delta"] is None
    assert row["event_id"] is None
    (tmp_path / "heartbeat_economy_latest.json").write_text("broken")
    assert hud.hud_evidence(tmp_path)["state"] == "UNAVAILABLE"
    (tmp_path / "heartbeat_economy_latest.json").write_text("[]")
    assert hud.hud_evidence(tmp_path)["state"] == "UNAVAILABLE"


def test_new_cache_version_bypasses_display_delay(tmp_path, monkeypatch):
    import sifta_os_desktop as desktop
    from types import SimpleNamespace
    import os
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    cache = sd / "stgm_economy_cache.json"
    cache.write_text("{}")
    monkeypatch.setattr(desktop, "_REPO", tmp_path)
    monkeypatch.setattr(desktop, "_economy_hud_full_scan_enabled", lambda: False)
    amounts = iter([(12.0, "cache"), (12.00001, "cache")])
    monkeypatch.setattr(desktop, "_cached_stgm_balance_for_topbar", lambda: next(amounts))
    window = SimpleNamespace()
    update = desktop.SiftaDesktop._topbar_stgm_balance
    assert update(window)[0] == 12.0
    assert update(window)[0] == 12.0
    stamp = cache.stat().st_mtime_ns + 1_000_000
    os.utime(cache, ns=(stamp, stamp))
    assert update(window)[0] == 12.00001


def test_fresh_heart_cannot_relabel_old_settlement_healthy(tmp_path, monkeypatch):
    sources(tmp_path, status="HEALTHY")
    monkeypatch.setattr(hud, "signature_valid", lambda row: True)
    (tmp_path / "hardware_heart.jsonl").write_text(json.dumps({"ts": 1400, "receipt_id": "h2",
        "schema": "SIFTA_HARDWARE_HEART_V1"}))
    assert hud.hud_evidence(tmp_path, now=1401)["state"] == "AWAITING"


def test_refresh_is_off_thread_singleflight_and_throttled(tmp_path, monkeypatch):
    from System import stgm_economy
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    threads = []

    def refresh(**kwargs):
        threads.append(threading.get_ident())
        entered.set()
        release.wait(5)
        done.set()

    monkeypatch.setattr(stgm_economy, "refresh_stgm_economy_cache", refresh)
    monkeypatch.setattr(hud, "_last_attempt", 0)
    monkeypatch.setattr(hud, "_busy", False)
    try:
        assert hud.request_cache_refresh(tmp_path)
        assert entered.wait(2)
        assert not hud.request_cache_refresh(tmp_path)
        assert threads == [threads[0]] and threads[0] != threading.get_ident()
    finally:
        release.set()
        assert done.wait(2)


def test_failed_cache_replace_preserves_last_valid_balance(tmp_path, monkeypatch):
    from System import stgm_economy
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"spendable_total_stgm": 12}))

    def fail_replace(*args):
        raise OSError("interrupted")

    monkeypatch.setattr(stgm_economy.os, "replace", fail_replace)
    result = stgm_economy._write_stgm_economy_cache({"spendable_total_stgm": 13}, cache)
    assert result["warnings"]
    assert json.loads(cache.read_text())["spendable_total_stgm"] == 12
    assert list(tmp_path.iterdir()) == [cache]


def test_widget_receipt_driven_animation_and_compact_fit(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QAbstractAnimation
    from Applications.stgm_heartbeat_hud import StgmHeartbeatHud
    app = QApplication.instance() or QApplication([])
    widget = StgmHeartbeatHud()
    widget.resize(330, 42)
    data = {"state": "FAULT", "detail": "Ultima -0.00010000 STGM | FAULT",
            "heart_id": "h1", "event_id": "e1", "heart_age": 0, "faults": ["supervisor"]}
    widget.show_observation("STGM 1,144.663804717", data)
    assert widget._animation.state() == QAbstractAnimation.State.Running
    widget._animation.stop()
    widget.show_observation("STGM 1,144.663804717", data)
    assert widget._animation.state() == QAbstractAnimation.State.Stopped
    widget.show_observation("STGM 1,144.663804717", {**data, "heart_id": None, "state": "STALE"})
    assert widget._pulse == 0
    assert widget.minimumSizeHint().width() <= 330
    assert widget.height() == 42
    assert "1,144.663804717" in widget.text()
    widget.close()
