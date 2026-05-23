"""Tests for the pre-cortex RELATIONAL_ACK / CO_PRESENT routes.

These pin:
  - Short ack utterances ("ok", "yes", "thanks", "mhm") all classify
    as RELATIONAL_ACK.
  - Empty text + co-presence flag classifies as CO_PRESENT.
  - Empty text without co-presence returns None (cortex runs).
  - Substantive text returns None (cortex runs).
  - propose_relational_reply varies placement of the owner name.
  - The check writes a receipt to relational_steering.jsonl.
  - The check honors a custom state_dir_root.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_relational_steering import (  # noqa: E402
    RELATIONAL_LEDGER,
    TRUTH_LABEL,
    classify_relational_intent,
    make_steering_decision,
    propose_relational_reply,
    relational_steering_check,
)


# ── classification ────────────────────────────────────────────────────────


def test_short_acks_classify_as_relational_ack():
    for text in ("ok", "yes", "yeah", "mhm", "thanks", "got it", "alright",
                 "thank you", "fair", "for sure"):
        assert classify_relational_intent(text) == "RELATIONAL_ACK", text


def test_empty_text_with_face_present_classifies_co_present():
    assert classify_relational_intent("", signals={"owner_face_present": True}) == "CO_PRESENT"
    assert classify_relational_intent("   ", signals={"owner_face_present": True}) == "CO_PRESENT"


def test_empty_text_without_co_presence_returns_none():
    assert classify_relational_intent("", signals={"owner_face_present": False}) is None
    assert classify_relational_intent("") is None


def test_co_presence_text_only_fires_with_signal():
    assert classify_relational_intent("here", signals={"owner_face_present": True}) == "CO_PRESENT"
    # Without signal, "here" is too ambiguous; routes to None
    assert classify_relational_intent("here") is None


def test_substantive_text_returns_none():
    assert classify_relational_intent("Alice, what time is it?") is None
    assert classify_relational_intent("Send a message to George") is None
    assert classify_relational_intent("Explain stigmergy") is None


def test_acks_strip_trailing_punctuation():
    assert classify_relational_intent("OK.") == "RELATIONAL_ACK"
    assert classify_relational_intent("yes!") == "RELATIONAL_ACK"
    assert classify_relational_intent("Got it.") == "RELATIONAL_ACK"


def test_ack_does_not_match_when_substring_inside_larger_utterance():
    """'ok i will send it' is not an ack — it's an action utterance."""
    assert classify_relational_intent("ok i will send it") is None
    assert classify_relational_intent("yes please do that") is None


# ── reply generation ──────────────────────────────────────────────────────


def test_reply_pool_uses_owner_name_when_provided():
    rng = random.Random(0)
    seen = set()
    for _ in range(50):
        r = propose_relational_reply("RELATIONAL_ACK", owner_name="George Anton", rng=rng)
        seen.add(r)
    # At least some replies should include the owner's first name
    assert any("George" in r for r in seen)
    # All replies should be short (no >40 chars sermons)
    for r in seen:
        assert len(r) <= 40


def test_reply_pool_drops_name_template_when_no_name():
    rng = random.Random(0)
    for _ in range(20):
        r = propose_relational_reply("RELATIONAL_ACK", owner_name=None, rng=rng)
        # No raw template placeholders should leak through
        assert "{name}" not in r
        assert "{}" not in r


def test_co_present_reply_includes_silence_option():
    rng = random.Random(42)
    replies = {propose_relational_reply("CO_PRESENT", rng=rng) for _ in range(30)}
    # An empty string is allowed in the CO_PRESENT pool
    assert "" in replies


# ── full check + receipt ──────────────────────────────────────────────────


def test_check_returns_result_with_reply_and_writes_receipt(tmp_path):
    result = relational_steering_check(
        "ok",
        owner_name="George",
        state_dir_root=tmp_path,
        write=True,
        rng=random.Random(0),
    )
    assert result is not None
    assert result.route == "RELATIONAL_ACK"
    assert result.matched_pattern == "ack_pattern"
    assert result.reply
    assert result.trace_id
    # Receipt is on disk
    ledger = tmp_path / RELATIONAL_LEDGER
    assert ledger.exists()
    row = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert row["route"] == "RELATIONAL_ACK"
    assert row["truth_label"] == TRUTH_LABEL
    assert row["reply"] == result.reply
    assert row["input_sha12"]


def test_check_returns_none_when_no_relational_intent(tmp_path):
    result = relational_steering_check(
        "Alice, what time is it?",
        state_dir_root=tmp_path,
        write=True,
    )
    assert result is None
    # No receipt should be written
    ledger = tmp_path / RELATIONAL_LEDGER
    assert not ledger.exists()


def test_make_steering_decision_returns_compatible_route():
    decision = make_steering_decision("RELATIONAL_ACK")
    if decision is None:
        # SteeringDecision not importable in this bootstrap — skip
        return
    assert decision.route == "RELATIONAL_ACK"
    assert decision.priority < 0.5
    assert decision.should_write_memory is False
    assert decision.should_verify_tools is False
