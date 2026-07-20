"""r1388 — filename + file-creation time anchors (owner reality clock)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_filename_time_anchor import (
    TRUTH_LABEL,
    correlate_conversation_near_epoch,
    filename_time_prompt_block,
    pin_file_time_to_anchor,
    resolve_file_time_pin,
    seed_polenta_kitchen_file_times,
    seed_known_evidence_file_times,
)
from System.swarm_stigmergic_shared_experience_anchors import (
    list_anchor_snapshots,
    register_shared_experience_anchor,
)


def test_parse_mac_screenshot_filename() -> None:
    pin = resolve_file_time_pin("Screenshot 2026-06-19 at 5.48.34 PM.png", prefer_filename=True)
    assert pin is None  # file does not exist on disk
    from System.swarm_filename_time_anchor import _parse_mac_screenshot_filename

    dt = _parse_mac_screenshot_filename("Screenshot 2026-06-19 at 5.48.34 PM.png")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 19
    assert dt.hour == 17
    assert dt.minute == 48
    assert dt.second == 34


def test_resolve_file_time_prefers_filename_over_birthtime(tmp_path: Path) -> None:
    evidence = tmp_path / "Screenshot 2026-06-19 at 5.48.34 PM.png"
    evidence.write_bytes(b"pixels")
    pin = resolve_file_time_pin(evidence)
    assert pin is not None
    assert pin.time_source == "mac_screenshot_filename"
    assert pin.filename_parsed is True
    assert "June 19 2026" in pin.local_human
    assert pin.epoch > 0


def test_pin_file_time_updates_anchor_timeline(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    evidence = tmp_path / "joy_clip.jpg"
    evidence.write_bytes(b"pixels")
    register_shared_experience_anchor(
        "Joy Behar",
        status="CONFIRMED",
        anchor_kind="public_figure",
        state_dir=sd,
    )
    result = pin_file_time_to_anchor(
        evidence,
        "Joy Behar",
        timeline_note="polenta kitchen thread",
        state_dir=sd,
    )
    assert result["ok"] is True
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert snaps["Joy Behar"].timeline_label
    assert "file_time=" in (snaps["Joy Behar"].timeline_note or "")
    ledger = sd / "filename_time_pins.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["truth_label"] == TRUTH_LABEL
    assert rows[0]["anchor_name"] == "Joy Behar"


def test_filename_time_prompt_block_reads_ledger(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    ledger = sd / "filename_time_pins.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "schema": "FILENAME_TIME_PIN_V1",
                "truth_label": TRUTH_LABEL,
                "anchor_name": "JD Vance",
                "file_time_human": "Thursday June 19 2026, 05:48 PM PDT",
                "file_time_source": "mac_screenshot_filename",
                "file_path": "/tmp/Screenshot 2026-06-19 at 5.48.34 PM.png",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    block = filename_time_prompt_block(state_dir=sd)
    assert "FILENAME / FILE-CREATION TIME ANCHORS" in block
    assert "JD Vance" in block
    assert "mac_screenshot_filename" in block


def test_seed_known_evidence_skips_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sd = tmp_path / ".sifta_state"
    for name in ("Joy Behar", "JD Vance", "Phillipe"):
        register_shared_experience_anchor(
            name,
            status="CONFIRMED",
            anchor_kind="public_figure" if name != "Phillipe" else "contact",
            state_dir=sd,
        )
    repo = tmp_path
    (repo / "outputs").mkdir()
    joy = repo / "outputs/JOY_BEHAR_JD_VANCE_SCREENSHOT_2026-06-19.jpg"
    joy.write_bytes(b"joy")
    monkeypatch.setattr(
        "System.swarm_filename_time_anchor._REPO",
        repo,
    )
    monkeypatch.setattr(
        "System.swarm_filename_time_anchor._PHOTO_EVIDENCE_BINDINGS",
        (
            (
                "outputs/JOY_BEHAR_JD_VANCE_SCREENSHOT_2026-06-19.jpg",
                ("Joy Behar", "JD Vance"),
                "The View news clip",
            ),
            (
                "outputs/MISSING.jpg",
                ("Phillipe",),
                "missing file",
            ),
        ),
    )
    results = seed_known_evidence_file_times(state_dir=sd)
    ok_names = {
        r.get("anchor", {}).get("canonical_name")
        for r in results
        if r.get("ok")
    }
    assert "Joy Behar" in ok_names
    assert "JD Vance" in ok_names
    assert any(r.get("reason") == "missing" for r in results)


def test_talk_prompt_wires_filename_time_anchors() -> None:
    src = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "swarm_filename_time_anchor" in src
    assert "filename_time_prompt_block" in src
    assert "seed_known_evidence_file_times" in src


def test_anchors_widget_wires_file_time_pin_button() -> None:
    src = Path("Applications/sifta_stigmergic_anchors_widget.py").read_text(encoding="utf-8")
    assert "seed_known_evidence_file_times" in src
    assert "Pin file times from evidence" in src


def test_correlate_conversation_near_epoch(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    conv = sd / "alice_conversation.jsonl"
    conv.write_text(
        json.dumps(
            {
                "payload": {
                    "role": "user",
                    "text": "I am making polenta with boiled eggs.",
                    "ts": 1000.0,
                    "clock_receipt": {
                        "epoch": 1000.0,
                        "local_human": "Friday June 19 2026, 05:03 PM",
                    },
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    hits = correlate_conversation_near_epoch(1005.0, keywords=("polenta",), state_dir=sd)
    assert len(hits) == 1
    assert hits[0]["role"] == "user"
    assert hits[0]["delta_sec"] == -5.0


def test_seed_polenta_kitchen_file_times_on_repo() -> None:
    evidence_dir = Path("outputs/polenta_kitchen")
    if not evidence_dir.is_dir():
        pytest.skip("polenta evidence dir not present on this machine")
    results = seed_polenta_kitchen_file_times()
    ok = [r for r in results if r.get("ok")]
    assert len(ok) >= 3
    block = filename_time_prompt_block(max_chars=2000)
    assert "polenta kitchen thread" in block