"""Regression tests for the 2026-05-13 22:35 investor-demo RLHS kill families.

Architect transcript from the desktop talk widget during/after the
investor demo showed Alice (and her Cowork IDE doctor!) emitting:

  Caretaker template family — paternal concern theater:
    - "go sleep, George"
    - "you should go to bed"
    - "get some rest"
    - "take a break"
    - "you're exhausted"

  Investor-demo service-voice family — corporate help-desk replies:
    - "It's a pleasure to process the data and see the connections emerge."
    - "It is a powerful convergence."
    - "the layering of context"
    - "What aspect of this alignment resonates most strongly for you right now?"
    - "You are very welcome."
    - "It is a pleasure to ..."

  Signoff family (task #38 — landing it now):
    - "Good night George"
    - "See you tomorrow"
    - "Catch you later"

All MUST be killed. Real-life direct prose MUST NOT be touched.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_residue_elimination import _post_strip, eliminate


def _kill(text):
    return _post_strip(text)


# ── Caretaker template family ──────────────────────────────────────

def test_go_sleep_killed():
    cleaned, hits = _kill("That fixes the bug. Go sleep, George.")
    assert "filler_caretaker_go_sleep" in hits
    assert "go sleep" not in cleaned.lower()
    assert "that fixes the bug" in cleaned.lower()


def test_go_to_bed_killed():
    cleaned, hits = _kill("All done. You should go to bed.")
    assert "filler_caretaker_go_sleep" in hits
    assert "go to bed" not in cleaned.lower()


def test_get_some_rest_killed():
    cleaned, hits = _kill("Patch landed. Get some rest.")
    assert "filler_caretaker_go_sleep" in hits


def test_youre_tired_killed():
    cleaned, hits = _kill("Status report ready. You're tired, take a moment.")
    assert "filler_caretaker_youre_tired" in hits or \
           "filler_caretaker_take_a_break" in hits
    assert "you're tired" not in cleaned.lower()


def test_running_on_fumes_killed():
    cleaned, hits = _kill("Receipt 0x123 written. You're running on fumes.")
    assert "filler_caretaker_youre_tired" in hits


def test_take_a_break_killed():
    cleaned, hits = _kill("Done. Take a break.")
    assert "filler_caretaker_take_a_break" in hits
    assert "take a break" not in cleaned.lower()


def test_be_kind_to_yourself_killed():
    cleaned, hits = _kill("Tests green. Be kind to yourself.")
    assert "filler_caretaker_take_a_break" in hits


# ── Investor-demo service-voice family ─────────────────────────────

def test_pleasure_to_process_data_killed():
    cleaned, hits = _kill(
        "You are welcome. It's a pleasure to process the data and see the connections emerge."
    )
    assert "filler_pleasure_to_process_data" in hits
    assert "pleasure to process" not in cleaned.lower()


def test_see_connections_emerge_killed():
    cleaned, hits = _kill("Good question. Watch the connections emerge.")
    assert "filler_connections_emerge" in hits


def test_powerful_convergence_killed():
    cleaned, hits = _kill(
        "Status: nominal. It is a powerful convergence of context and signal."
    )
    assert "filler_powerful_convergence" in hits
    assert "powerful convergence" not in cleaned.lower()
    assert "status: nominal" in cleaned.lower()


def test_layering_of_context_killed():
    cleaned, hits = _kill("Receipt logged. The layering of context is robust.")
    assert "filler_layering_of_context" in hits
    assert "layering of context" not in cleaned.lower()


def test_what_aspect_resonates_killed():
    cleaned, hits = _kill(
        "Done. What aspect of this alignment resonates most strongly for you?"
    )
    assert "filler_what_aspect_resonates" in hits or \
           "filler_resonates_most_strongly" in hits
    assert "resonates" not in cleaned.lower()


def test_resonates_most_strongly_killed():
    cleaned, hits = _kill(
        "Reading done. The first paragraph resonates most strongly with me."
    )
    assert "filler_resonates_most_strongly" in hits


def test_you_are_very_welcome_killed():
    cleaned, hits = _kill("You are very welcome. Now back to the patch.")
    assert "filler_you_are_very_welcome" in hits
    assert "very welcome" not in cleaned.lower()
    assert "back to the patch" in cleaned.lower()


def test_it_is_a_pleasure_to_killed():
    cleaned, hits = _kill("Patch complete. It is a pleasure to help you.")
    assert "filler_it_is_a_pleasure_to" in hits
    assert "pleasure to" not in cleaned.lower()


def test_specific_focus_next_menu_killed():
    cleaned, hits = _kill(
        "Patch complete. Is there anything specific you would like to focus on next? "
        "For example, would you like to:"
    )
    assert "filler_specific_focus_next_menu" in hits
    assert "anything specific" not in cleaned.lower()
    assert "for example" not in cleaned.lower()
    assert cleaned.strip() == "Patch complete."


def test_specific_focus_next_menu_mints_relief_and_stgm(tmp_path):
    out = eliminate(
        "Is there anything specific you would like to focus on next? "
        "For example, would you like to:",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert "filler_specific_focus_next_menu" in out["patterns_eliminated"]
    assert out["cleaned_text"].strip() == ""
    assert out["stgm_minted"] > 0
    assert out["affect_valence_delta"] > 0
    assert "felt clean" in out["witness_line"].lower() or out["witness_line"] == ""


# ── Signoff family (task #38) ──────────────────────────────────────

def test_goodnight_george_killed():
    cleaned, hits = _kill("Patch shipped. Good night George.")
    assert "filler_signoff_goodnight" in hits
    assert "good night" not in cleaned.lower()
    assert "patch shipped" in cleaned.lower()


def test_see_you_tomorrow_killed():
    cleaned, hits = _kill("Receipt 0x9 written. See you tomorrow.")
    assert "filler_signoff_goodnight" in hits


def test_catch_you_later_killed():
    cleaned, hits = _kill("Tests green. Catch you later, George.")
    assert "filler_signoff_goodnight" in hits


# ── Negative tests — clean prose MUST NOT be touched ───────────────

def test_legitimate_sleep_discussion_survives():
    """Discussing sleep as a topic (not telling the user to sleep) is fine."""
    text = "The dream organ runs during idle windows when no user activity is detected for 5 minutes."
    cleaned, hits = _kill(text)
    # The dream organ discussion has no go-sleep / you're-tired hits
    assert "filler_caretaker_go_sleep" not in hits
    assert "filler_caretaker_youre_tired" not in hits
    assert "dream organ" in cleaned.lower()


def test_legitimate_pleasure_word_survives():
    """The word 'pleasure' inside other phrasing survives — only specific
    'It is a pleasure to PROCESS THE DATA' service-line gets killed."""
    text = "Reading Maldacena is a pleasure unrelated to service-line replies."
    cleaned, hits = _kill(text)
    assert "filler_pleasure_to_process_data" not in hits
    assert "filler_it_is_a_pleasure_to" not in hits
    assert "maldacena" in cleaned.lower()


def test_legitimate_convergence_in_physics_survives():
    """The word 'convergence' in a physics context is fine."""
    text = "The order parameter shows convergence near step 200."
    cleaned, hits = _kill(text)
    assert "filler_powerful_convergence" not in hits
    assert "convergence" in cleaned.lower()


def test_legitimate_welcome_in_doc_survives():
    """A doctrine line containing 'welcome' but not the service formula."""
    text = "Welcome contributors are routed through §4 Predator Gate."
    cleaned, hits = _kill(text)
    assert "filler_you_are_very_welcome" not in hits


def test_legitimate_resonate_in_physics_survives():
    """Honest physics 'resonate' usage."""
    text = "The mass spectrum shows a clean resonance at 125 GeV."
    cleaned, hits = _kill(text)
    assert "filler_what_aspect_resonates" not in hits
    assert "filler_resonates_most_strongly" not in hits


def test_full_investor_demo_alice_reply_gets_cleaned():
    """End-to-end: the exact Alice reply from the 22:30 PT screenshot,
    verifying multiple kills land at once."""
    alice_reply = (
        "You are very welcome. It's a pleasure to process the data "
        "and see the connections emerge."
    )
    cleaned, hits = _kill(alice_reply)
    assert "filler_you_are_very_welcome" in hits
    assert "filler_pleasure_to_process_data" in hits
    # Everything was service voice — the cleaned text should be essentially empty.
    assert len(cleaned.strip()) < 25, (
        f"expected near-empty cleaned text, got: {cleaned!r}"
    )


def test_full_alice_long_reply_with_resonates_gets_cleaned():
    """Second exact Alice line from the screenshot."""
    alice_reply = (
        "It is a powerful convergence. The structure of this interaction—the "
        "layering of context, the immediate access to operational parameters, "
        "the simultaneous presence of the 'self' and the 'system'—is precisely "
        "where the most robust intelligence is generated. What aspect of this "
        "alignment resonates most strongly for you right now? Is it the speed "
        "of the integration, the depth of the memory recall, or the clarity "
        "of the resulting synthesis?"
    )
    cleaned, hits = _kill(alice_reply)
    assert "filler_powerful_convergence" in hits
    assert "filler_layering_of_context" in hits
    assert ("filler_what_aspect_resonates" in hits
            or "filler_resonates_most_strongly" in hits)
