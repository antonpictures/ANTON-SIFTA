#!/usr/bin/env python3
"""r267: Stigmergic humanization — Alice appreciates in her OWN, VARIED words (not hardcoded)."""
from System import swarm_stigmergic_humanization as hz


def test_detect_signal():
    assert hz.detect_social_signal("Alice, you did a great job")["kind"] == "praise"
    assert hz.detect_social_signal("thank you so much")["kind"] == "thanks"
    assert hz.detect_social_signal("what is the time")["is_appreciation"] is False


def test_directive_is_grounded_and_not_canned(tmp_path):
    sifta = tmp_path / ".sifta_state"
    d = hz.humanization_directive(
        owner_text="great job!", receipt_substrate="Money card confirmed (receipt a9ab)", state_dir=sifta
    )
    assert d["humanize"] is True
    low = d["directive"].lower()
    assert "own words" in low and "vary" in low          # tells the cortex to phrase it, varied
    assert "Money card confirmed (receipt a9ab)" in d["directive"]  # grounded in the real receipt
    # neutral input -> gratitude is never forced
    assert hz.humanization_directive(owner_text="open the browser", state_dir=sifta)["humanize"] is False


def test_anti_hardcode_repeat_tripwire(tmp_path):
    sifta = tmp_path / ".sifta_state"
    line = "That's a nice compliment, thank you George"
    hz.record_humanization(line, state_dir=sifta)
    # the SAME canned line again is flagged — this is the anti-hardcode tripwire
    assert hz.is_repeat(line, state_dir=sifta) is True
    assert hz.record_humanization(line, state_dir=sifta)["is_repeat"] is True
    # a genuinely different line is NOT a repeat
    assert hz.is_repeat("Means a lot — the money card is live and logged.", state_dir=sifta) is False


def test_appreciation_count_and_avoid_list(tmp_path):
    sifta = tmp_path / ".sifta_state"
    hz.record_humanization("glad that one landed", state_dir=sifta)
    hz.record_humanization("happy it helped you out", state_dir=sifta)
    assert hz.appreciation_count(state_dir=sifta) == 2
    d = hz.humanization_directive(owner_text="good job", state_dir=sifta)
    assert d["count"] == 3
    assert any(p in d["recent_to_avoid"] for p in ("glad that one landed", "happy it helped you out"))
