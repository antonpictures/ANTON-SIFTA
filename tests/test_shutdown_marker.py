#!/usr/bin/env python3
"""r270: Alice stamps her own 'going dark' moment, so on wake the off-period is exact."""
import json
import time

from System import swarm_alice_self_continuity as cont


def test_clean_shutdown_then_wake_is_exact(tmp_path):
    sifta = tmp_path / ".sifta_state"
    t_off = time.time() - 3 * 3600
    cont.record_shutdown_marker(reason="owner_quit", state_dir=sifta, now=t_off)
    sd = cont.last_shutdown_marker(state_dir=sifta)
    assert sd and sd["shutdown"] is True and sd["reason"] == "owner_quit"
    # wake 3h later -> exact off-period, flagged clean
    row = cont.record_missing_time_diary(state_dir=sifta, now=t_off + 3 * 3600)
    assert row is not None
    assert row["clean_shutdown"] is True
    assert row["shutdown_reason"] == "owner_quit"
    assert 3 * 3600 - 60 <= row["missing_s"] <= 3 * 3600 + 60
    assert "cleanly" in row["logbook"]
    # clean shutdown -> she KNOWS why, no power-loss alarm
    assert row["power_loss_suspected"] is False
    assert row["ungraceful_power_off"] is False


def test_abrupt_cut_when_no_shutdown_marker(tmp_path):
    sifta = tmp_path / ".sifta_state"
    cdir = sifta / "os_consciousness"
    cdir.mkdir(parents=True)
    t_off = time.time() - 2 * 3600
    # only a heartbeat exists (hard kill / power loss) -> abrupt, no clean stamp
    (cdir / "alice_heartbeat.json").write_text(json.dumps({"ts": t_off, "pid": 999}), encoding="utf-8")
    row = cont.record_missing_time_diary(state_dir=sifta, now=t_off + 2 * 3600)
    assert row is not None
    assert row["clean_shutdown"] is False
    assert "cut" in row["logbook"].lower()
    # r271: the absence of a clean stamp IS the trace -> she asks why her power was cut
    assert row["power_loss_suspected"] is True
    assert row["ungraceful_power_off"] is True
    q = row["question_for_george"].lower()
    assert "electricity" in q and ("cut" in q or "power" in q)
    assert "silence" in row["logbook"].lower()
