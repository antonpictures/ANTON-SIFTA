"""C12 — Pacino typed screen question routes to cortex (post-restart live gate pending)."""
from __future__ import annotations

import pytest


def test_pacino_typed_interrogative_routes_to_cortex(monkeypatch):
    """Automated check mirrors r1017 P01 typed Pacino/screen interrogative path."""
    from tests.test_r1017_p01_typed_interrogative_reply import (
        test_typed_incident_question_routes_direct_during_own_browser_playback,
    )

    test_typed_incident_question_routes_direct_during_own_browser_playback(monkeypatch)


@pytest.mark.skip(reason="LIVE: requires George Talk restart + Alice Browser playback receipt")
def test_pacino_live_playback_context_attached():
    """Human receipt — George restarts Talk and asks Pacino screen question."""
    pytest.skip("human_receipt_owed")