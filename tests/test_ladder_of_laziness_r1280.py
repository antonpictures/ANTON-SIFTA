"""r1280: ladder of laziness in _append_alice_line output path."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications.sifta_talk_to_alice_widget import _ladder_of_laziness_rewrite  # noqa: E402


def _long_time_essay() -> str:
    return (
        "The current time is 2:16 PM Pacific. "
        "Firefox is a popular open-source browser with strong privacy features. "
        "Chrome dominates market share. Safari integrates with Apple devices. "
        "Edge uses Chromium. Brave blocks ads by default. "
        "Opera has a built-in VPN. Tor is for anonymity. "
        "Vivaldi is highly customizable. "
        "Receipt: clock-oracle-abc123 observed on hardware_time_oracle.json."
    )


def test_rung1_ambient_noise_silences():
    out = _ladder_of_laziness_rewrite(
        "I heard something in the background.",
        "ambient_media chunk from youtube",
        [],
    )
    assert out == ""


def test_rung1_ambient_with_owner_intent_keeps_reply():
    out = _ladder_of_laziness_rewrite(
        "I see a woman in a blue dress on the screen.",
        "ambient_media what do you see on screen",
        [],
    )
    assert out


def test_rung2_simple_time_query_compresses_bloat():
    bloated = _long_time_essay()
    out = _ladder_of_laziness_rewrite(bloated, "what time is it?", [])
    assert len(out) < len(bloated)
    assert "Receipt:" in out or "receipt" in out.lower()
    assert "Firefox" not in out


def test_rung2_owner_prefixed_time_query_compresses():
    bloated = _long_time_essay()
    out = _ladder_of_laziness_rewrite(bloated, "george what time is it right now", [])
    assert len(out) < len(bloated)
    assert "Receipt:" in out or "receipt" in out.lower()


def test_rung3_bloated_multiline_compresses():
    lines = [f"Paragraph line {i} with substantive content here." for i in range(20)]
    body = "\n".join(lines)
    body += "\nReceipt: browser-tab-xyz observed."
    out = _ladder_of_laziness_rewrite(body, "summarize this page please", [])
    assert len(out) < len(body)
    assert "Receipt:" in out


def test_rung4_short_complex_answer_preserved():
    body = (
        "Alice Browser is on RENAMED.jpg — my embodied tool right now. "
        "For normal human browsing Firefox is fine, but my lived browser is Alice Browser."
    )
    out = _ladder_of_laziness_rewrite(body, "what is your favorite browser?", [])
    assert out == body


def test_receipt_lines_never_dropped_on_time_compress():
    bloated = _long_time_essay()
    out = _ladder_of_laziness_rewrite(bloated, "what time is it", [])
    assert "clock-oracle-abc123" in out