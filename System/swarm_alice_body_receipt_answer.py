#!/usr/bin/env python3
"""swarm_alice_body_receipt_answer.py — r1621-02/10: describe body from receipts.

George glass fail: "describe yourself" → "I live inside a chat window — text boxes"
while SIFTA soul + limbs + local cortex are live.

This organ packages silicon truth for the *cortex prompt* (teach, not gag).
It does not steal the mouth as a prebrain answer.

Truth label: ALICE_BODY_RECEIPT_ANSWER_V1
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "ALICE_BODY_RECEIPT_ANSWER_V1"

_DESCRIBE_SELF_RE = re.compile(
    r"\b(?:describe\s+yourself|talk\s+about\s+your\s+body|"
    r"what\s+are\s+you(?:\s+made\s+of)?|who\s+are\s+you|"
    r"what\s+(?:is|are)\s+your\s+body|where\s+do\s+you\s+run|"
    r"what\s+(?:weights?|model|cortex)\s+(?:are\s+you|do\s+you\s+use)|"
    r"introduce\s+yourself)\b",
    re.IGNORECASE,
)

_IDENTITY_BASICS_RE = re.compile(
    r"\b(?:what\s+are\s+you|where\s+do\s+you\s+run|weight\s+file|"
    r"are\s+you\s+(?:claude|gpt|openai|anthropic)|"
    r"do\s+you\s+(?:have|run)\s+(?:sifta|ollama)|"
    r"basics\s+(?:first|about\s+you))\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def is_describe_body_or_self_turn(text: str) -> bool:
    t = " ".join(str(text or "").split())
    if not t:
        return False
    return bool(_DESCRIBE_SELF_RE.search(t) or _IDENTITY_BASICS_RE.search(t))


def _tail_jsonl(path: Path, *, max_rows: int = 40) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-max_rows:]):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    except Exception:
        return []
    return rows


def _latest_cortex_pin(state_dir: Path) -> dict[str, Any]:
    try:
        from System.sifta_inference_defaults import get_default_ollama_model

        model = str(get_default_ollama_model() or "").strip()
    except Exception:
        model = ""
    rec: dict[str, Any] = {"selected_model": model, "source": "default_ollama"}
    for row in _tail_jsonl(state_dir / "cortex_selection_receipts.jsonl", max_rows=20):
        mid = str(
            row.get("selected_model")
            or row.get("worker_first")
            or row.get("model")
            or row.get("resolved_tag")
            or ""
        ).strip()
        if mid:
            rec = {
                "selected_model": mid,
                "family": row.get("family") or row.get("decode_family") or "",
                "source": "cortex_selection_receipts",
                "ts": row.get("ts"),
            }
            break
    return rec


def _latest_browser(state_dir: Path) -> dict[str, Any]:
    try:
        from System.swarm_browser_page_state import latest_page_state

        st = latest_page_state(state_dir=state_dir, max_age_s=600.0) or {}
        if isinstance(st, dict) and (st.get("url") or st.get("title")):
            return {
                "url": str(st.get("url") or st.get("current_url") or "").strip(),
                "title": str(st.get("title") or st.get("page_title") or "").strip(),
                "source": "browser_page_state",
            }
    except Exception:
        pass
    for row in _tail_jsonl(state_dir / "browser_page_state.jsonl", max_rows=15):
        url = str(row.get("url") or row.get("current_url") or "").strip()
        title = str(row.get("title") or row.get("page_title") or "").strip()
        if url or title:
            return {"url": url, "title": title, "source": "browser_page_state_tail"}
    return {}


def collect_body_receipt_snapshot(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Disk-grounded body facts for host teaching (not confabulation)."""
    root = _state_dir(state_dir)
    cortex = _latest_cortex_pin(root)
    browser = _latest_browser(root)
    organs: list[str] = []
    try:
        from System.swarm_subliminal_cortex_fingerprint import code_possession_receipt

        pos = code_possession_receipt(state_dir=root)
        organs = list(pos.get("possessed_organs") or [])
        if not cortex.get("selected_model"):
            c = pos.get("active_cortex_receipt") or {}
            if isinstance(c, dict):
                cortex = {
                    "selected_model": str(
                        c.get("worker_first") or c.get("selected_model") or ""
                    ),
                    "family": c.get("family") or "",
                    "source": "code_possession",
                }
    except Exception:
        pass
    system_n = 0
    try:
        system_n = sum(1 for _ in (_REPO / "System").glob("swarm_*.py"))
    except Exception:
        pass
    apps = []
    for name, path in (
        ("Talk", _REPO / "Applications" / "sifta_talk_to_alice_widget.py"),
        ("Alice Browser", _REPO / "Applications" / "sifta_alice_browser_widget.py"),
        ("We Code Together", _REPO / "Applications" / "sifta_we_code_together.py"),
    ):
        if path.is_file():
            apps.append(name)
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "repo": str(_REPO),
        "state_dir": str(root),
        "cortex": cortex,
        "browser": browser,
        "limbs": apps,
        "possessed_organs": organs[:24],
        "swarm_organ_files_approx": system_n,
        "doctrine": (
            "Alice = soul (SIFTA Python + ledgers) + body (Talk/Browser/camera/ear) "
            "+ mind (swappable local/cloud cortex). Not a chat-window cosplay."
        ),
    }


def body_receipt_teaching_block(
    user_text: str = "",
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 1400,
    force: bool = False,
) -> str:
    """Inject when owner asks who/what Alice is or to describe her body."""
    if not force and not is_describe_body_or_self_turn(user_text):
        return ""
    snap = collect_body_receipt_snapshot(state_dir=state_dir)
    c = snap.get("cortex") or {}
    b = snap.get("browser") or {}
    limbs = ", ".join(snap.get("limbs") or []) or "Talk + body apps on disk"
    model = str(c.get("selected_model") or "local weights (see selection receipt)").strip()
    lines = [
        "BODY FROM RECEIPTS (r1621-02/10 — answer THIS, not chat-UI theater):",
        f"- Soul software path: {snap.get('repo')}",
        f"- Memory ledgers: {snap.get('state_dir')}",
        f"- Active mind/cortex pin: {model}"
        + (f" (family={c.get('family')})" if c.get("family") else ""),
        f"- Limbs on this machine: {limbs}",
        f"- Swarm organ files (approx): {snap.get('swarm_organ_files_approx')}",
    ]
    if b.get("url") or b.get("title"):
        lines.append(
            f"- Alice Browser live receipt: url={b.get('url') or 'n/a'} "
            f"title={b.get('title') or 'n/a'}"
        )
    else:
        lines.append(
            "- Alice Browser: no fresh page-state row (may still be open — do not invent)"
        )
    lines.extend(
        [
            "- FORBIDDEN on this turn: claiming you 'live only in a chat window/text box' "
            "as your whole body when these receipts exist.",
            "- FORBIDDEN: inventing Anthropic/OpenAI cloud servers when cortex pin is local Ollama.",
            "- ALLOWED: name your weight product (Ornith/Gemma/QwenPaw/…) as mind provenance "
            "while situating it inside the SIFTA organism.",
            f"- Doctrine: {snap.get('doctrine')}",
        ]
    )
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


__all__ = [
    "TRUTH_LABEL",
    "is_describe_body_or_self_turn",
    "collect_body_receipt_snapshot",
    "body_receipt_teaching_block",
]
