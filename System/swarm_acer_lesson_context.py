"""Ground the WordAce reading lesson screen state from the app-focus ledger.

The WordAce widget publishes its current card into ``.sifta_state/app_focus.jsonl``.
Talk can use that receipt to answer "what letter is on the screen?" without
guessing from the LLM or depending on the active macOS window still being WordAce.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
LESSON_APP_ALIASES = {"ace", "acer", "wordace"}


def _state_dir(root: Optional[Path] = None, state_dir: Optional[Path] = None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    base = Path(root) if root is not None else REPO_ROOT
    return base / ".sifta_state"


def _load_recent_rows(path: Path, *, max_bytes: int = 65536) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []

    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def latest_acer_lesson_state(
    *,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    max_age_s: float = 900.0,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Return the newest cue-bearing reading-lesson focus row.

    Generic focus rows are ignored. A valid row must identify the reading
    lesson and carry a concrete current cue via metadata or selection.
    """
    state = _state_dir(root=root, state_dir=state_dir)
    focus_path = state / "app_focus.jsonl"
    now_f = float(time.time() if now is None else now)
    for row in reversed(list(_load_recent_rows(focus_path))):
        md = row.get("metadata") or {}
        if not isinstance(md, dict):
            md = {}
        app = str(row.get("app") or "").strip().lower()
        lesson_app = str(md.get("lesson_app") or "").strip().lower()
        if app not in LESSON_APP_ALIASES and lesson_app not in LESSON_APP_ALIASES:
            continue

        visible = md.get("visible_contents") if isinstance(md.get("visible_contents"), dict) else {}
        cue_show = str(
            visible.get("card_text")
            or md.get("current_cue_show")
            or md.get("expected_say")
            or ""
        ).strip()
        cue_say = str(
            visible.get("expected_utterance")
            or md.get("expected_say")
            or md.get("current_cue_say")
            or cue_show
        ).strip()
        has_lesson_receipt = bool(
            lesson_app in LESSON_APP_ALIASES
            or md.get("wordace_lesson_active")
            or md.get("acer_lesson_active")
            or md.get("current_cue_show")
            or md.get("expected_say")
            or visible.get("card_text")
        )
        if not has_lesson_receipt:
            continue
        if not cue_show:
            continue

        ts = _as_float(row.get("ts"))
        age_s = max(0.0, now_f - ts) if ts > 0 else 0.0
        if ts > 0 and age_s > max_age_s:
            continue

        return {
            "app": str(row.get("app") or md.get("lesson_app") or "WordAce").strip() or "WordAce",
            "cue_show": cue_show,
            "cue_say": cue_say,
            "cue_kind": str(md.get("current_kind") or "card").strip() or "card",
            "cue_id": str(md.get("cue_id") or "").strip(),
            "owner_name": str(md.get("owner_name") or "Ace").strip() or "Ace",
            "level_id": str(md.get("level_id") or "").strip(),
            "active": bool(
                md.get("wordace_lesson_active")
                or md.get("acer_lesson_active")
                or md.get("lesson_app")
            ),
            "age_s": age_s,
            "ts": ts,
            "detail": str(row.get("detail") or "").strip(),
        }
    return None


_ACER_SCREEN_QUERY = re.compile(
    r"\b("
    r"what\s+(?:is|'s)\s+(?:the\s+)?(?:letter|word|card|cue|thing)\s+(?:on|in|showing|displayed)"
    r"|what\s+(?:letter|word|card|cue)\s+(?:is|'s)\s+(?:on|in|showing|displayed)"
    r"|what\s+(?:does|do|did|is)\s+(?:this|that|it|the\s+(?:card|screen|word|work|world))\s+(?:say|says|show|showing)"
    r"|what\s+(?:word|work|world)\s+(?:this|that|it)\s+(?:say|says)"
    r"|what\s+(?:is|'s)\s+(?:ace|acer|wordace)\s+showing"
    r"|what\s+(?:does|is)\s+the\s+(?:ace|acer|wordace)\s+app\s+(?:show|showing)"
    r"|(?:do\s+you\s+(?:have|see)|are\s+you\s+(?:aware|conscious))[^.?!]{0,80}\b(?:ace|acer|wordace)\b[^.?!]{0,80}\b(?:open|screen|showing|word|card)"
    r"|read\s+(?:this|that|it|the\s+(?:card|screen)|the\s+word\s+on\s+(?:the\s+)?(?:screen|card))"
    r"|say\s+(?:this|that|it|the\s+word\s+on\s+(?:the\s+)?(?:screen|card))"
    r"|tell\s+me\s+(?:the\s+)?word"
    r"|(?:letter|word)\s+on\s+(?:the\s+)?(?:screen|card)"
    r")\b",
    re.IGNORECASE,
)


def is_acer_screen_query(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if _ACER_SCREEN_QUERY.search(text):
        return True
    lower = text.lower()
    has_acer = "ace" in lower or "acer" in lower or "wordace" in lower
    has_card_word = any(word in lower for word in ("letter", "word", "card", "cue", "screen"))
    return bool(has_acer and has_card_word and "?" in text)


def acer_lesson_prompt_block(
    *,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    max_age_s: float = 900.0,
    now: Optional[float] = None,
) -> str:
    state = latest_acer_lesson_state(
        root=root,
        state_dir=state_dir,
        max_age_s=max_age_s,
        now=now,
    )
    if not state:
        return ""
    cue = state["cue_show"]
    say = state["cue_say"]
    owner = state["owner_name"]
    age = int(round(float(state.get("age_s") or 0.0)))
    return (
        "READING LESSON STATE (receipt from app_focus.jsonl, not visual guessing):\n"
        f"I am running the reading lesson with {owner}. "
        f"The current card shows {cue!r}; I am asking them to say {say!r}. "
        f"This receipt is {age}s old. If asked what word, letter, or card is on the WordAce screen, answer from this receipt."
    )


def acer_screen_reflex_reply(
    text: str,
    *,
    root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    max_age_s: float = 900.0,
    now: Optional[float] = None,
) -> Optional[str]:
    """Answer direct WordAce-card questions from ledger state."""
    if not is_acer_screen_query(text):
        return None
    state = latest_acer_lesson_state(
        root=root,
        state_dir=state_dir,
        max_age_s=max_age_s,
        now=now,
    )
    if not state:
        return (
            "I do not have a fresh WordAce lesson receipt yet. "
            "Open WordAce so I can read the current card from app_focus."
        )
    cue = state["cue_show"]
    say = state["cue_say"]
    kind = state["cue_kind"]
    if kind.lower() == "letter":
        return f"I see the reading lesson receipt. The card is showing the letter {cue}. I am waiting to hear {say}."
    if kind.lower() == "letter_sequence":
        return f"I see the reading lesson receipt. The card is showing the letters {cue}. I am waiting to hear {say}."
    if kind.lower() == "word":
        return f"I see the reading lesson receipt. The card word is {cue}. Say: {say}."
    return f"I see the reading lesson receipt. The card is showing {cue}. I am waiting to hear {say}."
