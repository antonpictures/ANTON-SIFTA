#!/usr/bin/env python3
"""swarm_body_code_example.py — r1621-05: real System/*.py, not ACO textbook.

When owner asks for stigmergic / body code, auto-SELF_READ a real organ and
inject a short grounded snippet so cortex cannot invent Pheromone_Grid demos.

Truth label: BODY_CODE_EXAMPLE_V1
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent

TRUTH_LABEL = "BODY_CODE_EXAMPLE_V1"

# Prefer organs that actually implement stigmergy / ledgers on disk.
_CANDIDATE_PATHS: tuple[str, ...] = (
    "System/swarm_pheromone_field.py",
    "System/swarm_browser_stigmergic_memory.py",
    "System/swarm_horizontal_stigmergy.py",
    "System/swarm_alice_self_coding_hand.py",
    "System/swarm_we_code_proposal_sorter.py",
    "System/swarm_browser_page_state.py",
)

_BODY_CODE_RE = re.compile(
    r"\b(?:piece\s+of\s+code\s+from\s+(?:your|her)\s+body|"
    r"code\s+from\s+(?:your|her)\s+body|"
    r"show\s+(?:me\s+)?(?:your|her)\s+(?:body\s+)?code|"
    r"stigmergic\s+(?:code|example|organ)|"
    r"real\s+(?:system|body)\s+(?:file|code|snippet)|"
    r"self_read\s+(?:a\s+)?real)\b",
    re.IGNORECASE,
)


def is_body_code_example_turn(text: str) -> bool:
    return bool(_BODY_CODE_RE.search(str(text or "")))


def pick_body_source_path(*, repo: Optional[Path] = None) -> str:
    root = repo or _REPO
    for rel in _CANDIDATE_PATHS:
        if (root / rel).is_file():
            return rel
    # Fallback: any swarm_*.py
    system = root / "System"
    if system.is_dir():
        for p in sorted(system.glob("swarm_*.py")):
            return f"System/{p.name}"
    return "System/swarm_alice_self_coding_hand.py"


def body_code_teaching_block(
    user_text: str = "",
    *,
    repo: Optional[Path] = None,
    max_chars: int = 3500,
    force: bool = False,
) -> str:
    """Inject a real file head so mouth cannot textbook-fake ACO."""
    if not force and not is_body_code_example_turn(user_text):
        return ""
    root = repo or _REPO
    rel = pick_body_source_path(repo=root)
    path = root / rel
    if not path.is_file():
        return (
            "BODY CODE FROM DISK (r1621-05): requested a real System/*.py but "
            f"{rel} missing — emit [SELF_READ: path=System/swarm_alice_self_coding_hand.py] "
            "and quote that; never invent textbook ACO as your body."
        )
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"BODY CODE FROM DISK (r1621-05): read failed {rel}: {exc}"
    # Keep module docstring + first ~80 lines of real code.
    lines = text.splitlines()
    head = "\n".join(lines[: min(90, len(lines))])
    if len(head) > max_chars - 400:
        head = head[: max_chars - 400] + "\n# …truncated for context…"
    return (
        f"BODY CODE FROM DISK (r1621-05 — THIS is a real path under ANTON_SIFTA):\n"
        f"path={rel}\n"
        "Rules: quote/adapt THIS file (or SELF_READ another System/*.py). "
        "FORBIDDEN: inventing a fake Pheromone_Grid / textbook ACO as if it were "
        "your body file.\n"
        f"--- begin {rel} ---\n"
        f"{head}\n"
        f"--- end {rel} ---"
    )


def forced_self_read_marker(user_text: str = "") -> dict[str, Any]:
    """Optional receipt that body forced a real path for this turn."""
    if not is_body_code_example_turn(user_text):
        return {"ok": False, "reason": "not_body_code_turn"}
    rel = pick_body_source_path()
    return {
        "ok": True,
        "truth_label": TRUTH_LABEL,
        "path": rel,
        "self_read_syntax": f"[SELF_READ: path={rel}]",
    }


__all__ = [
    "TRUTH_LABEL",
    "is_body_code_example_turn",
    "pick_body_source_path",
    "body_code_teaching_block",
    "forced_self_read_marker",
]
