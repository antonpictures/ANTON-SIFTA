import json

from System.swarm_hermes_desktop_nuggets import (
    LEDGER_NAME,
    OFFICIAL_LINKS,
    append_hermes_desktop_nuggets,
    format_hermes_desktop_nuggets,
)


def test_append_hermes_desktop_nuggets_receipts_shared_core(tmp_path):
    row = append_hermes_desktop_nuggets(state_dir=tmp_path, now=123.0, source="test")

    assert row["truth_label"] == "HERMES_DESKTOP_NUGGETS_V1"
    assert row["links"]["desktop_docs"] == OFFICIAL_LINKS["desktop_docs"]
    assert any(n["name"] == "shared_core_many_surfaces" for n in row["nuggets"])

    ledger = tmp_path / LEDGER_NAME
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["organ"] == "Hermes Desktop / External Agent Body Nuggets"


def test_format_hermes_desktop_nuggets_surfaces_sifta_upgrades(tmp_path):
    append_hermes_desktop_nuggets(state_dir=tmp_path, now=123.0, source="test")

    text = format_hermes_desktop_nuggets(state_dir=tmp_path, max_items=2)

    assert "shared_core_many_surfaces" in text
    assert "One Alice" in text
