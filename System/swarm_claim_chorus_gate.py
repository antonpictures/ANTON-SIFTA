#!/usr/bin/env python3
"""swarm_claim_chorus_gate.py — R1625-02: receipts veto solo mouth claims.

Carpenter / Alice: paddle moves only if the hall votes. Mind may speak "I see /
I searched / landed" only if a body receipt agrees. Not full multi-agent hive —
smallest chorus: field receipts as red/green paddles.

Truth label: CLAIM_CHORUS_GATE_V1
"""

from __future__ import annotations

import re
import time
from typing import Any, Mapping, Optional

TRUTH_LABEL = "CLAIM_CHORUS_GATE_V1"

_SEE_CLAIM = re.compile(
    r"\b(?:I\s+(?:can\s+)?see|I\s+looked|on\s+(?:my|the)\s+screen|"
    r"I\s+searched|I\s+opened|I\s+landed|browser\s+is\s+on)\b",
    re.I,
)
_FALSE_SOLO = re.compile(
    r"don'?t have (?:direct )?access to (?:your )?screen|"
    r"can(?:not|'?t)\s+see\s+(?:the\s+)?(?:page|post|browser)",
    re.I,
)


def body_votes_for_browser_claim(
    *,
    state_dir: Any = None,
) -> dict[str, Any]:
    """Tally red/green from live organs (page state + time sense)."""
    votes: list[dict[str, Any]] = []
    url = ""
    try:
        from System.swarm_browser_page_state import latest_page_state

        st = latest_page_state(state_dir=state_dir, max_age_s=300.0) or {}
        url = str(st.get("url") or st.get("current_url") or "").strip()
        if url:
            votes.append({"swimmer": "browser_page_state", "vote": "green", "url": url})
        else:
            votes.append({"swimmer": "browser_page_state", "vote": "red", "reason": "no_url"})
    except Exception as exc:
        votes.append({"swimmer": "browser_page_state", "vote": "red", "reason": str(exc)})

    try:
        from System.swarm_browser_time_sense import feel_browser_now

        feel = feel_browser_now(state_dir=state_dir)
        if feel.get("still_loading"):
            votes.append(
                {
                    "swimmer": "browser_time_sense",
                    "vote": "yellow",
                    "phase": feel.get("phase"),
                }
            )
        elif feel.get("settled") or feel.get("url_now"):
            votes.append(
                {
                    "swimmer": "browser_time_sense",
                    "vote": "green",
                    "phase": feel.get("phase"),
                    "url": feel.get("url_now"),
                }
            )
        else:
            votes.append({"swimmer": "browser_time_sense", "vote": "red"})
    except Exception as exc:
        votes.append({"swimmer": "browser_time_sense", "vote": "red", "reason": str(exc)})

    green = sum(1 for v in votes if v.get("vote") == "green")
    red = sum(1 for v in votes if v.get("vote") == "red")
    yellow = sum(1 for v in votes if v.get("vote") == "yellow")
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "votes": votes,
        "green": green,
        "red": red,
        "yellow": yellow,
        "url": url,
        "chorus_ok": green >= 1 and red == 0,
        "still_loading": yellow > 0 and green == 0,
    }


def gate_browser_mouth_claim(
    cortex_text: str,
    *,
    owner_text: str = "",
    state_dir: Any = None,
) -> dict[str, Any]:
    """If mind claims vision/search without green votes → repair or block false solo."""
    raw = str(cortex_text or "").strip()
    if not raw:
        return {"changed": False, "text": raw, "reason": "empty"}

    chorus = body_votes_for_browser_claim(state_dir=state_dir)

    # False denial while green votes exist → not our job (browser_mouth_false_denial)
    if _FALSE_SOLO.search(raw) and chorus.get("green", 0) >= 1:
        return {
            "changed": False,
            "text": raw,
            "reason": "false_denial_delegated",
            "chorus": chorus,
        }

    claims = bool(_SEE_CLAIM.search(raw))
    if not claims:
        return {"changed": False, "text": raw, "reason": "no_browser_claim", "chorus": chorus}

    if chorus.get("still_loading"):
        return {
            "changed": True,
            "text": (
                "My Alice Browser limb is still loading — the swarm has not settled a "
                "green vote yet. I will not claim I finished searching or seeing the page."
            ),
            "reason": "chorus_yellow_still_loading",
            "chorus": chorus,
        }

    if not chorus.get("chorus_ok"):
        return {
            "changed": True,
            "text": (
                "I do not have a live browser receipt vote (page-state / time-sense) "
                "for that claim. No green paddle from the body field — I refuse to "
                "hallucinate the screen."
            ),
            "reason": "chorus_red_no_receipt",
            "chorus": chorus,
        }

    return {
        "changed": False,
        "text": raw,
        "reason": "chorus_green_allows_claim",
        "chorus": chorus,
    }


__all__ = [
    "TRUTH_LABEL",
    "body_votes_for_browser_claim",
    "gate_browser_mouth_claim",
]
