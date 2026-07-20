"""Doctrine + search-audit turns must not become web searches (r1285)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    _deterministic_detector_directive_reply,
    _extract_explicit_internet_search_command,
    _extract_browser_search_command,
    _extract_sifta_app_command,
    _extract_visual_image_search_command,
    _hallucination_bridge_synthesize_web_browser_action,
    _has_explicit_browser_back_command,
    _is_contextual_browser_search_effector_request,
    _is_owner_deterministic_detector_directive,
    _is_search_audit_or_routing_correction,
    _must_route_owner_turn_to_cortex,
    _search_query_is_contextual_or_junk,
)


def test_deterministic_unacceptable_is_detector_directive():
    text = (
        "THAT WAS DETERMINISTIC ANSWER, UNACCEPTABLE. "
        "SEND IT TO DETERMINISTIC DETECTOR APP IN YOUR BODY"
    )
    assert _is_owner_deterministic_detector_directive(text)
    assert _must_route_owner_turn_to_cortex(text)
    assert _extract_browser_search_command(text) == {}
    assert _extract_explicit_internet_search_command(text) == {}
    assert _extract_visual_image_search_command(text) == {}
    assert _extract_sifta_app_command(text) == {}
    assert not _is_contextual_browser_search_effector_request(text)


def test_search_complaint_is_not_a_search_command():
    text = (
        "I DID NOT ASKED YOU TO SEARCH FOR THIS NONSENSE THE WEB. "
        "WHAT IS THIS? GO BACK ONE PAGE IN THE BROWSER."
    )
    assert _is_search_audit_or_routing_correction(text)
    assert _must_route_owner_turn_to_cortex(text)
    assert _extract_browser_search_command(text) == {}
    assert _has_explicit_browser_back_command(text)
    cmd = _extract_sifta_app_command(text)
    assert cmd.get("action") == "back"


def test_web_bridge_skips_doctrine_turn():
    owner = "THAT WAS DETERMINISTIC ANSWER, UNACCEPTABLE. SEND IT TO DETERMINISTIC DETECTOR APP"
    assert _hallucination_bridge_synthesize_web_browser_action(owner, "I will search that.") is None


def test_doctrine_phrase_is_junk_search_query():
    q = "That Was Deterministic Answer Unacceptable Send It To Deterministic Detector App"
    assert _search_query_is_contextual_or_junk(q)


def test_deterministic_detector_directive_writes_existing_tracker(tmp_path, monkeypatch):
    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(tracker, "_DETERMINISTIC_MISTAKES_LEDGER", state / "deterministic_mistakes.jsonl")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")

    text = (
        "THAT WAS DETERMINISTIC ANSWER, UNACCEPTABLE. "
        "SEND IT TO DETERMINISTIC DETECTOR APP IN YOUR BODY"
    )
    reply = _deterministic_detector_directive_reply(text)

    assert reply.startswith("Receipt: ")
    mistake = json.loads((state / "deterministic_mistakes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    tracker_row = json.loads((state / "stigmergic_deterministic_tracker.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert mistake["truth_label"] == "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE_V1"
    assert mistake["details"]["owner_requested"] == "deterministic_detector_app"
    assert mistake["details"]["blocked_browser_search"] is True
    assert tracker_row["organ"] == "stigmergic_deterministic_tracker"
