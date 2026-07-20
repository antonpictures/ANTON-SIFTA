#!/usr/bin/env python3
"""swarm_free_self_code_path.py — free self-code proving path (doctor barrier removal).

George: doctors must not steal go-code turns. This organ packages the prompt
scaffold so a free self-code turn always gets:
  - active or campaign plan files
  - SELF_CODE_CUT syntax
  - cortex_first doctrine
  - recommended live coder tag

Truth label: FREE_SELF_CODE_PATH_V1
"""

from __future__ import annotations

import re
from typing import Any, Optional

TRUTH_LABEL = "FREE_SELF_CODE_PATH_V1"

_ROUND_RE = re.compile(r"\b(R\d{4}-\d{2})\b", re.I)


def extract_round_id(text: str) -> str:
    m = _ROUND_RE.search(str(text or ""))
    return m.group(1).upper() if m else ""


def free_self_code_teaching_block(
    user_text: str = "",
    *,
    state_dir: Optional[str] = None,
) -> str:
    """Inject on go-code / SELF_CODE turns so cortex emits cuts, not switch refuse."""
    try:
        from System.swarm_alice_self_coding_hand import is_owner_self_code_execute_request
    except Exception:
        return ""
    if not is_owner_self_code_execute_request(user_text or ""):
        low = str(user_text or "").lower()
        if "self_code" not in low and "self-code" not in low and "code r" not in low:
            return ""

    round_id = extract_round_id(user_text)
    files: list[str] = []
    goal = ""
    title = ""
    try:
        from System.swarm_alice_self_plan_rounds import (
            CAMPAIGN_R1621,
            load_active_plan,
            template_plan_for_round,
        )

        active = load_active_plan(state_dir=state_dir)
        if active.get("round_id"):
            round_id = round_id or str(active.get("round_id"))
            files = list(active.get("files_to_touch") or [])
            goal = str(active.get("goal") or "")[:200]
            title = str(active.get("title") or "")
        if round_id and not files:
            for row in CAMPAIGN_R1621:
                if str(row.get("round_id")).upper() == round_id.upper():
                    files = list(row.get("files_to_touch") or [])
                    goal = str(row.get("goal") or "")[:200]
                    title = str(row.get("title") or "")
                    break
        _ = template_plan_for_round  # kept for Alice follow-up
    except Exception:
        pass

    try:
        from System.swarm_ornith35_coder_eval import recommended_coder_cortex

        coder = recommended_coder_cortex()
    except Exception:
        coder = "satgeze/qwenpaw-9b-heretic-1m:latest"

    lines = [
        "FREE SELF-CODE PATH (doctor barriers off — r1621-06 / free path):",
        "- THIS TURN you MUST emit [SELF_CODE_CUT: path=...] or [SELF_CODE_EDIT: path=...].",
        "- Do NOT call a cortex switch. SELF_CODE_CUT is not a model name.",
        f"- Preferred live coder mind: {coder}",
    ]
    if round_id:
        lines.append(f"- Round: {round_id} {title}".rstrip())
    if goal:
        lines.append(f"- Goal: {goal}")
    if files:
        lines.append("- Touch ONLY these paths unless owner expands list:")
        for f in files[:12]:
            lines.append(f"  - {f}")
        lines.append(
            f"Example:\n[SELF_CODE_CUT: path={files[0]}]\n"
            f"# minimal real patch\n[/SELF_CODE_CUT]"
        )
    else:
        lines.append(
            "Example:\n[SELF_CODE_CUT: path=System/swarm_example_organ.py]\n"
            "# real python\n[/SELF_CODE_CUT]"
        )
    lines.append(
        "- After blocks, body runs ast+compile+tests and writes doctor=alice_self receipts."
    )
    return "\n".join(lines)


def should_force_cortex_first(user_text: str) -> bool:
    try:
        from System.swarm_alice_self_coding_hand import is_owner_self_code_execute_request

        return bool(is_owner_self_code_execute_request(user_text))
    except Exception:
        return False


def path_status() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "switch_steals_self_code": False,
        "doctrine": "go-code reaches cortex; SELF_CODE blocks execute after reply",
    }


__all__ = [
    "TRUTH_LABEL",
    "extract_round_id",
    "free_self_code_teaching_block",
    "should_force_cortex_first",
    "path_status",
]
