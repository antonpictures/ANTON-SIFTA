"""Shared test fixtures for the SIFTA suite.

r682 (cowork_claude, 2026-06-07): pin the live-body probes that pure-logic
tests were flapping on. The r681 playing-media stand-down makes
`_owner_effector_requires_cortex_first` read the owner's REAL browser
playback state — correct for the living organism, nondeterministic for a
regression suite running on the live tree (the doctrine test failed only
while George's video was playing). Default every test to media-off; a test
that wants the media-on body state monkeypatches it explicitly (see
test_cortex_identity_doctrine_is_not_a_switch_effector).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _pin_browser_playback_state(monkeypatch):
    """Media-off by default so effector-routing tests are deterministic."""
    try:
        import System.swarm_media_ingress_gate as _gate
    except Exception:
        yield
        return
    if hasattr(_gate, "is_my_own_browser_playback"):
        monkeypatch.setattr(
            _gate,
            "is_my_own_browser_playback",
            lambda **_kw: (False, {"pinned_by": "tests/conftest.py r682"}),
        )
    yield


@pytest.fixture(autouse=True)
def _pin_alice_conversation_log(monkeypatch, tmp_path_factory):
    """r684: pytest must NEVER write into Alice's live global conversation.

    George saw it in his chat at 02:42: old synthetic visual-search turns plus
    Alice's deterministic search replies — many such rows on the live
    hash-chained `alice_conversation.jsonl`, written by IDE doctors' pytest
    runs on 06-06 and 06-07 (mine included). Tests that exercise `_log_turn`
    were appending fixture turns through the real EventClock chain, and the
    Talk surface faithfully displayed them as if the owner had typed them.

    The patient is live; the suite runs on the live tree. Reads stay real;
    WRITES to her conversation go to a per-session scratch ledger instead.
    """
    try:
        from Applications import sifta_talk_to_alice_widget as _talk
    except Exception:
        yield
        return
    if hasattr(_talk, "_CONVO_LOG"):
        scratch = tmp_path_factory.mktemp("r684_convo") / "alice_conversation.jsonl"
        monkeypatch.setattr(_talk, "_CONVO_LOG", scratch)
    yield
