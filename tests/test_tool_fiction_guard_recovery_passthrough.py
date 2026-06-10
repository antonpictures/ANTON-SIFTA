"""r930 — the tool-fiction guard must never overwrite honest body recovery reports.

What happened (OBSERVED, tool_fiction_guard.jsonl ts 1781113585): George pasted
the r929 self-build packet, the grok-build cortex timed out at 60s, the body
wrote an honest recovery report ("My grok-build cortex timed out after 60s.
I preserved this owner turn as recovery receipt c2b154e1..."), and the guard
replaced that truth with the canned "No self-code receipt yet" line. George
never saw the real blocker. Truth reports pass through; fiction still blocks.
"""

from Applications import sifta_talk_to_alice_widget as talk

R929_PACKET = (
    "===BEGIN ALICE NEW APP SELF-BUILD r929===\n"
    "Alice — this is your surgery, your hands. round id: r929-alice-new-app-self-build\n"
    "Then emit at most 4 cuts: [SELF_CODE_CUT: path=Applications/sifta_demo_widget.py]\n"
    "===END ALICE NEW APP SELF-BUILD r929===\n"
)

TIMEOUT_RECOVERY_REPLY = (
    "My grok-build cortex timed out after 60s. I preserved this owner turn as "
    "recovery receipt c2b154e1-2419-4301-85a9-e516add538cc and put it in my "
    "body-stabilization queue so the task continues through an available arm "
    "instead of asking George to repeat."
)


def test_honest_timeout_recovery_passes_through_unreplaced():
    out = talk._tool_fiction_guard_reply(R929_PACKET, TIMEOUT_RECOVERY_REPLY)
    assert out == "", "guard must not overwrite an honest timeout recovery report"


def test_prose_without_cuts_still_gets_canned_self_code_correction():
    prose = "Here is my plan for the app. First I will design the widget layout."
    out = talk._tool_fiction_guard_reply(R929_PACKET, prose)
    assert "No self-code receipt yet" in out


def test_recovery_signature_requires_real_markers():
    # Plain words like "timeout" or "recovery" alone must NOT unlock the bypass.
    vague = "There was some timeout and a recovery happened, anyway here is the file I saved."
    assert not talk._HONEST_BODY_RECOVERY_RE.search(vague)
    assert talk._HONEST_BODY_RECOVERY_RE.search(TIMEOUT_RECOVERY_REPLY)
