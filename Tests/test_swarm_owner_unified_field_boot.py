import json
import time

import pytest

from System import swarm_owner_unified_field_boot as ouf


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    st = tmp_path / ".sifta_state"
    st.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SIFTA_STATE_DIR", str(st))
    yield st
    monkeypatch.delenv("SIFTA_STATE_DIR", raising=False)


def test_boot_writes_receipt_schedule_presence(isolated_state):
    r = ouf.anchor_owner_unified_field_on_boot(root=isolated_state)
    assert r.get("receipt_trace_id")

    wr = isolated_state / "work_receipts.jsonl"
    lines = wr.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["action"] == "OWNER_UNIFIED_FIELD_BOOT"
    assert "active(owner-unified-field-boot)" in row["stigtime"]

    sch = isolated_state / "stigmergic_schedule.jsonl"
    assert sch.exists()
    srows = [json.loads(x) for x in sch.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert any("OWNER UNIFIED FIELD" in str(x.get("text", "")) for x in srows)

    pres = json.loads((isolated_state / "owner_desktop_presence.json").read_text(encoding="utf-8"))
    assert pres.get("last_boot_ts")


def test_shutdown_then_boot_sets_gap(isolated_state):
    ouf.note_desktop_shutdown_for_owner_field(root=isolated_state)
    time.sleep(0.02)
    r = ouf.anchor_owner_unified_field_on_boot(root=isolated_state)
    assert r.get("gap_seconds") is not None
    assert r["gap_seconds"] >= 0.01


def test_touch_alive_updates_timestamp(isolated_state):
    ouf.touch_owner_desktop_alive(root=isolated_state)
    p1 = json.loads((isolated_state / "owner_desktop_presence.json").read_text(encoding="utf-8"))
    time.sleep(0.02)
    ouf.touch_owner_desktop_alive(root=isolated_state)
    p2 = json.loads((isolated_state / "owner_desktop_presence.json").read_text(encoding="utf-8"))
    assert p2["last_alive_ts"] >= p1["last_alive_ts"]
