from __future__ import annotations

import json

from System.swarm_internet_forager_home_vector import (
    capture_home_vector,
    orient_forager,
    request_return_home,
    verify_arrival,
    verify_home_vector_signature,
)


def test_capture_home_vector_from_grok_mission_writes_portable_coordinates(tmp_path):
    mission = {
        "grok_url": "https://grok.com/c/home-thread",
        "start_driver_receipt_id": "mission-r1",
    }
    page = {
        "url": "https://grok.com/c/home-thread",
        "title": "Grok - Alice thread",
        "text": "Alice and Grok are talking.",
    }

    row = capture_home_vector(page=page, mission=mission, owner_binding="owner-key", state_dir=tmp_path)

    assert row["home_url"] == "https://grok.com/c/home-thread"
    assert row["home_thread_id"] == "home-thread"
    assert row["home_host"] == "grok.com"
    assert row["mission_receipt_id"] == "mission-r1"
    assert verify_home_vector_signature(row)

    sd = tmp_path / ".sifta_state"
    saved = json.loads((sd / "internet_forager_home_vector.json").read_text(encoding="utf-8"))
    assert saved["signature_sha256"] == row["signature_sha256"]


def test_orient_from_other_thread_inside_mapped_habitat_can_return(tmp_path):
    vector = capture_home_vector(
        page={"url": "https://grok.com/c/home-thread", "title": "Home", "text": "home comb"},
        mission={"grok_url": "https://grok.com/c/home-thread"},
        state_dir=tmp_path,
    )

    orientation = orient_forager(
        current_page={"url": "https://grok.com/c/strange-thread", "title": "Other", "text": "dark box"},
        home_vector=vector,
        state_dir=tmp_path,
    )

    assert orientation["status"] == "mapped_habitat_off_home_thread"
    assert orientation["can_return_home"] is True
    assert orientation["home_url"] == "https://grok.com/c/home-thread"


def test_request_return_home_from_strange_internet_writes_browser_drop(tmp_path):
    vector = capture_home_vector(
        page={"url": "https://grok.com/c/home-thread", "title": "Home", "text": "home comb"},
        mission={"grok_url": "https://grok.com/c/home-thread"},
        state_dir=tmp_path,
    )

    row = request_return_home(
        current_page={"url": "https://example.com/black-box", "title": "Unknown square", "text": "strange"},
        home_vector=vector,
        state_dir=tmp_path,
    )

    sd = tmp_path / ".sifta_state"
    assert row["status"] == "outside_mapped_territory_portable_home_vector"
    assert row["return_command_written"] is True
    assert (sd / "alice_browser_open_url.txt").read_text(encoding="utf-8") == "https://grok.com/c/home-thread"


def test_verify_arrival_rejects_corrupt_yellow_dot_and_accepts_real_home(tmp_path):
    vector = capture_home_vector(
        page={"url": "https://grok.com/c/home-thread", "title": "Home", "text": "home comb"},
        mission={"grok_url": "https://grok.com/c/home-thread"},
        state_dir=tmp_path,
    )
    corrupt = dict(vector)
    corrupt["home_url"] = "https://grok.com/c/foreign-thread"

    rejected = verify_arrival(
        current_page={"url": "https://grok.com/c/foreign-thread", "title": "Spoof", "text": "yellow dot"},
        home_vector=corrupt,
        state_dir=tmp_path,
    )
    accepted = verify_arrival(
        current_page={"url": "https://grok.com/c/home-thread", "title": "Home", "text": "home comb"},
        home_vector=vector,
        state_dir=tmp_path,
    )

    assert rejected["arrival_verified"] is False
    assert rejected["predator_gate"] == "hold_forager_at_gate"
    assert accepted["arrival_verified"] is True
    assert accepted["predator_gate"] == "admit_returning_forager"
