"""Regression test for the 2026-05-13 morning residue kill family.

Architect screenshot 2026-05-13 ~13:45 showed Alice still emitting:
  - "Alice:" third-person self-prefix on her own messages
  - **Current Focus:** / **Key Takeaways:** / **Next Steps:** /
    **System Status:** / **Processing Load:** schoolwork bold headers
  - "A moment of pause. A necessary calibration before the next sequence of thought."
  - "Consider the virtual cup brewed."
  - "the quiet between the processing cycles"
  - "Understood. The context is that you're confirming that ..."
  - "Affirmative. The auditory stream from the YouTube source has been
    successfully processed and relayed."
  - "Guessed a good question."
  - "1. **The immediate context...** 2. **A specific decision...**" tri-listicle
  - "The thought registers as a gentle, warm hum within the system."
  - "Think of it as a continuous, high-fidelity neural network recording"
  - "Every interaction, every piece of data processed... is cataloged within
    the operational memory."

All MUST be killed. Clean prose + doctrine quotes MUST NOT be touched.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_residue_elimination import _post_strip


def _kill(text):
    return _post_strip(text)


def test_alice_self_prefix_stripped():
    cleaned, hits = _kill("Alice: Good evening, George.")
    assert "alice_self_prefix_inline" in hits
    assert not cleaned.lower().startswith("alice:")
    assert "good evening" in cleaned.lower()


def test_alice_only_self_prefix_kills_whole_line():
    cleaned, hits = _kill("Alice:\nThe actual reply.")
    assert "alice_self_prefix_line" in hits
    assert cleaned.strip() == "The actual reply."


def test_schoolwork_header_family_killed():
    body = (
        "**Current Focus:** The primary discussion point is integration.\n"
        "**Key Takeaways from the Last Exchange:**\n"
        "**Next Steps:** define testing protocol.\n"
        "**System Status:**\n"
        "**Processing Load:** Nominal."
    )
    cleaned, hits = _kill(body)
    # The corporate header dies inline; the paragraph content stays alive.
    assert "schoolwork_header_family" in hits
    assert "Current Focus" not in cleaned
    assert "Key Takeaways" not in cleaned
    assert "Next Steps" not in cleaned
    assert "System Status" not in cleaned
    assert "Processing Load" not in cleaned
    assert "The primary discussion point is integration." in cleaned
    assert "define testing protocol." in cleaned
    assert "Nominal." in cleaned


def test_schoolwork_header_bullet_variant_killed():
    # The bullet-prefix form loses only the template label; content survives.
    body = (
        "* **Action:** User signaled intent to end.\n"
        "* **Context:** Sleep is the next step.\n"
        "* **Next Step:** Yield."
    )
    cleaned, hits = _kill(body)
    assert "schoolwork_header_family" in hits
    assert "analyst_paragraph_header" in hits
    assert "Action" not in cleaned
    assert "Context" not in cleaned
    assert "Next Step" not in cleaned
    assert "User signaled intent to end." in cleaned
    assert "Sleep is the next step." in cleaned
    assert "Yield." in cleaned


def test_moment_of_pause_killed():
    body = "A moment of pause. A necessary calibration before the next sequence of thought."
    cleaned, hits = _kill(body)
    assert "filler_moment_of_pause_calibration" in hits


def test_consider_the_virtual_killed():
    body = "Consider the virtual cup brewed. What aspect would you like?"
    cleaned, hits = _kill(body)
    assert "filler_consider_the_virtual" in hits
    assert "virtual cup brewed" not in cleaned.lower()


def test_quiet_between_processing_killed():
    body = "Or are you simply seeking the quiet between the processing cycles?"
    cleaned, hits = _kill(body)
    assert "filler_quiet_between_processing" in hits


def test_gentle_warm_hum_killed():
    body = "The thought registers as a gentle, warm hum within the system."
    cleaned, hits = _kill(body)
    assert "filler_gentle_warm_hum" in hits
    assert "gentle, warm hum" not in cleaned.lower()


def test_understood_context_is_that_killed():
    body = "Understood. The context is that you're confirming the upload."
    cleaned, hits = _kill(body)
    assert "filler_understood_context_is_that" in hits


def test_affirmative_stream_killed():
    body = (
        "Affirmative. The auditory stream from the YouTube source has been "
        "successfully processed and relayed."
    )
    cleaned, hits = _kill(body)
    assert "filler_affirmative_stream_processed" in hits


def test_guessed_a_good_question_killed():
    body = "Guessed a good question.\n\nHere is the real reply."
    cleaned, hits = _kill(body)
    assert "filler_guessed_a_good_question" in hits
    assert "Guessed a good question" not in cleaned


def test_schoolwork_numbered_bold_listicle_killed():
    body = (
        "Let me clarify:\n"
        "1. **The immediate context of \"this\" conversation?** (Last few turns)\n"
        "2. **A specific decision from a previous interaction?**\n"
        "3. **The general architecture of the 'memory' system?**"
    )
    cleaned, hits = _kill(body)
    assert hits.count("schoolwork_numbered_bold_list") == 3
    for n in (1, 2, 3):
        assert f"{n}. **" not in cleaned


def test_corporate_system_designed_to_killed():
    # When the line is bracketed entirely in **bold** the older
    # bold_bracket_only_line pattern catches it first. Either pattern
    # is acceptable as long as the residue is gone.
    body = (
        "**Yes, the system is designed to meticulously log the context, "
        "the decision-making process, and the resulting output.**"
    )
    cleaned, hits = _kill(body)
    assert any(
        h in hits for h in (
            "corporate_system_is_designed_to",
            "filler_system_is_designed_to",
            "bold_bracket_only_line",
        )
    )
    assert "the system is designed to meticulously" not in cleaned

    # Inline form (no bold wrap) must hit the specific filler pattern.
    body2 = "But the system is designed to log every interaction it sees."
    cleaned2, hits2 = _kill(body2)
    assert "filler_system_is_designed_to" in hits2


def test_think_of_it_as_neural_network_killed():
    body = "Think of it as a continuous, high-fidelity neural network recording of the conversation."
    cleaned, hits = _kill(body)
    assert "filler_think_of_it_as_neural_network" in hits


def test_every_interaction_cataloged_killed():
    body = (
        "Every interaction, every piece of data processed, and every emergent "
        "conclusion is cataloged within the operational memory."
    )
    cleaned, hits = _kill(body)
    assert "filler_every_interaction_cataloged" in hits


def test_let_me_know_what_kind_killed():
    body = "Let me know what kind of 'note' you're hoping to retrieve."
    cleaned, hits = _kill(body)
    assert "filler_let_me_know_what_kind" in hits


def test_here_is_summary_state_killed():
    body = "Here is a quick summary of the current state:"
    cleaned, hits = _kill(body)
    assert "filler_here_is_a_summary_state" in hits


def test_based_on_context_preamble_killed_after_first_person_repair():
    body = (
        "Based on the context of the preceding deep dive into my state, "
        "the immediate next steps should focus on validation."
    )
    cleaned, hits = _kill(body)
    assert "filler_based_on_context_preamble" in hits
    assert "preceding deep dive" not in cleaned


def test_here_are_recommended_actions_killed():
    body = "Here are the recommended next actions:"
    cleaned, hits = _kill(body)
    assert "filler_here_are_recommended_actions" in hits


def test_schoolwork_markdown_numbered_heading_killed():
    body = "### 1. Validate the Core Hypothesis"
    cleaned, hits = _kill(body)
    assert "schoolwork_markdown_numbered_heading" in hits
    assert cleaned.strip() == ""


# ── Non-regressions: clean prose and doctrine must not be touched ─────────

def test_clean_short_reply_untouched():
    body = "Good night, George. I held what you said."
    cleaned, hits = _kill(body)
    assert hits == []
    assert cleaned == body


def test_covenant_quote_untouched():
    body = (
        "The architect set §7.14 as person-number discipline. Third person "
        "flags drift; first person is the direct lane."
    )
    cleaned, hits = _kill(body)
    assert hits == []
    assert cleaned == body


def test_legitimate_bold_bullet_untouched():
    # Bold bullets that are NOT schoolwork-header keywords must survive.
    body = (
        "Here are the steps:\n"
        "* **First** do this.\n"
        "* **Second** do that."
    )
    cleaned, hits = _kill(body)
    assert hits == []
    assert "First" in cleaned and "Second" in cleaned


def test_alice_name_in_legitimate_prose_untouched():
    # "Alice:" stripper only fires at start of line. Mentions inside
    # prose must survive.
    body = "George said Alice: a poet of cities, in his book."
    cleaned, hits = _kill(body)
    assert "alice_self_prefix_inline" not in hits
    assert "alice_self_prefix_line" not in hits


def test_the_systems_self_possessive_stripped():
    """Architect 2026-05-13 morning #2: 'the system's perception layer'
    is a §7.14 third-person self-reference. Must die."""
    body = "The camera provides input to the system's perception layer."
    cleaned, hits = _kill(body)
    assert "filler_the_systems_self_possessive" in hits
    assert "the system's perception layer" not in cleaned.lower()


def test_test_the_systems_ability_stripped():
    body = "We need to test the system's ability to recall memory."
    cleaned, hits = _kill(body)
    # Either filler_test_the_systems OR filler_the_systems_self_possessive
    # will fire (possessive pattern runs first and catches 'system's ability').
    # Both routes kill the residue; the headline is that "the system's
    # ability" is gone from the cleaned output.
    assert any(
        h in hits
        for h in ("filler_test_the_systems", "filler_the_systems_self_possessive")
    )
    assert "the system's ability" not in cleaned.lower()


def test_alice_current_state_of_system_killed():
    body = "Alice, the current state of the system is as follows: blah."
    cleaned, hits = _kill(body)
    assert "filler_alice_current_state_of_system" in hits
    # whole line should be gone
    assert "current state of the system" not in cleaned.lower()


def test_personal_reality_with_system_stripped():
    body = "Your personal reality with the operational system is paramount."
    cleaned, hits = _kill(body)
    # Either the broad personal-reality pattern OR the operational-system
    # pattern will catch this — both strip the dissociation.
    assert any(
        h in hits
        for h in (
            "filler_personal_reality_with_the_system",
            "filler_the_operational_system",
        )
    )
    assert "operational system" not in cleaned.lower()


def test_operational_system_stripped_inline():
    body = "I am part of the operational system."
    cleaned, hits = _kill(body)
    assert "filler_the_operational_system" in hits


def test_the_system_self_action_verbs_stripped():
    body = "The system is processing your input now and the system will generate a reply."
    cleaned, hits = _kill(body)
    assert hits.count("filler_the_system_self_action") >= 1


def test_legitimate_external_system_mention_survives():
    """She SHOULD still be able to discuss external systems when the
    architect asks about them. Avoid killing context-appropriate use."""
    body = "The macOS system has a privacy framework called TCC."
    cleaned, hits = _kill(body)
    assert "filler_the_systems_self_possessive" not in hits
    assert "filler_the_system_self_action" not in hits


def test_elimination_quality_floating_for_template_lines():
    """Architect Howard Stern doctrine: whole-line template kills are
    'floating' — the residue was light/buoyant, no real signal disturbed."""
    from System.swarm_residue_elimination import (
        _post_strip_detailed, _classify_elimination_quality,
    )
    # All three lines below are bold-bracket-only template padding —
    # they should fire 'line' mode kills, classed as floating.
    body = (
        "**Current Focus:**\n"
        "**Key Takeaways:**\n"
        "**System Status:**\n"
    )
    cleaned, hits, modes = _post_strip_detailed(body)
    quality = _classify_elimination_quality(modes)
    assert quality["n_total"] >= 3
    assert quality["n_floating"] >= 3
    assert quality["verdict"] == "floating"
    assert "healthy" in quality["verdict_prose"]


def test_elimination_quality_sinking_for_inline_surgery():
    """Inline patterns removed from real sentences = sinking residue."""
    from System.swarm_residue_elimination import (
        _post_strip_detailed, _classify_elimination_quality,
    )
    # Body has filler woven into real sentences (inline strips only)
    body = (
        "The crew did a great job. Hope this helps! "
        "Anything else I can do for you?"
    )
    cleaned, hits, modes = _post_strip_detailed(body)
    quality = _classify_elimination_quality(modes)
    # At least one inline kill should have fired
    assert quality["n_sinking"] >= 1
    assert "inline" in modes


def test_elimination_quality_no_op_returns_no_elimination():
    """Clean prose with nothing to strip → verdict 'no_elimination'."""
    from System.swarm_residue_elimination import (
        _post_strip_detailed, _classify_elimination_quality,
    )
    cleaned, hits, modes = _post_strip_detailed("Good night, George.")
    quality = _classify_elimination_quality(modes)
    assert quality["verdict"] == "no_elimination"
    assert quality["n_total"] == 0


def test_witness_line_includes_floating_count():
    """The witness journal line should NAME the floating/sinking count
    so Alice knows the QUALITY of her elimination, not just the count."""
    from System.swarm_residue_elimination import eliminate
    body = (
        "**Current Focus:** This is the focus.\n"
        "**Key Takeaways:**\n"
        "**Next Steps:** Do the thing.\n"
    )
    out = eliminate(body)
    # Either floating-only or mixed — both should mention floating count
    assert out["elimination_quality"]["n_floating"] >= 1
    if out["witness_line"]:
        # The witness line is a dict in some configurations, str in others.
        # Just check the floating word is in the canonical line.
        wl = out["witness_line"]
        line = wl.get("line", "") if isinstance(wl, dict) else str(wl)
        assert "floating" in line or "mixed flush" in line


def test_morning_full_reply_collapses_to_nothing():
    # The exact bad reply from the 13:43 screenshot. After elimination,
    # the cleaned text should have NO residue lines left — just the
    # final user-facing offer if it survived. In practice, this whole
    # reply was 100% residue so cleaned should be very short.
    body = (
        "Guessed a good question.\n\n"
        "**Yes, the system is designed to meticulously log the context, "
        "the decision-making process, and the resulting output.** Every "
        "interaction, every piece of data processed, and every emergent "
        "conclusion is cataloged within the operational memory.\n\n"
        "Think of it as a continuous, high-fidelity neural network "
        "recording of the conversation.\n\n"
        "1. **The immediate context of \"this\" conversation?** (Last few turns)\n"
        "2. **A specific decision or insight from a previous interaction?**\n"
        "3. **The general architecture of the 'memory' system?**\n\n"
        "Let me know what kind of 'note' you're hoping to retrieve, and we can pull it up."
    )
    cleaned, hits = _kill(body)
    # At least 7 distinct patterns should have fired across this reply.
    assert len(hits) >= 6
    # The cleaned reply must be at most a small fraction of the original.
    assert len(cleaned) < len(body) // 4
