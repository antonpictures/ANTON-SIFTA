#!/usr/bin/env python3
"""Alice Browser Grok copy-last-reply command organ.

Alice clicks Grok's COPY button on the latest assistant message. The browser
limb reads the system clipboard and writes a receipt with clipboard_sha256.
Orchestrator must NOT read page snapshots or fabricate Grok text.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_BROWSER_GROK_COPY_LAST_REPLY_COMMAND_V1"
RESULT_TRUTH_LABEL = "ALICE_BROWSER_GROK_COPY_LAST_REPLY_RESULT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_browser_grok_copy_command.json"
_COMMAND_LEDGER = "alice_browser_grok_copy_commands.jsonl"
_MODEL_LABEL_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+(?:[-A-Za-z0-9_.:/]+)?$")
_GLOBAL_CHAT_TRANSCRIPT_RE = re.compile(
    r"\b(?:Ioan|George|Alice|Grok)\s+\((?:TYPED|SPOKEN|WORLD STT|BROWSER|GROK MIRROR|Grok|Alice)",
    re.IGNORECASE,
)
_ALICE_BROWSER_PROMPT_RE = re.compile(
    r"(?:"
    r"^let['’]?s\s+dive\s+into\s+that\s+routing\s+detail|"
    r"how\s+does\s+your\s+mixture[-\s]of[-\s]experts\s+architecture|"
    r"^what\s+llm\s+is\s+running\s+how\s+many\s+parameters|"
    r"do\s+you\s+primarily\s+rely\s+on\s+top|"
    r"which\s+approach\s+performs\s+better|"
    r"bonus\s+points\s+if\s+you\s+can\s+quantify|"
    r"latency\s+profile\s+gain\s+compared\s+to\s+dense|"
    r"answer\s+grok\s+in\s+alice\s+browser|"
    r"alice\s+answ?e?er\s+above|"
    r"hello\s+world[.,!]?\s+i['’]?m\s+alice|"
    r"what\s+llm\s+is\s+running"
    r")",
    re.IGNORECASE,
)
_ALICE_LATEX_QUESTION_RE = re.compile(r"\$\\text\{|\$\\approx\s*\\text\{|\?\s*⊕")
_GROK_REPLY_SIGNAL_RE = re.compile(
    r"(?:"
    r"\b(?:i['’]?m\s+grok|built\s+by\s+xai|mixture[-\s]of[-\s]experts|"
    r"great\s+question|understood,\s*alice|sparse\s+activation|"
    r"router\s+network|frontier\s+class|xai['’]?s\s+grok|"
    r"power\s+to\s+the\s+swarm|would\s+you\s+like\s+me\s+to)"
    r")",
    re.IGNORECASE,
)


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


def stage_grok_copy_last_reply_command(
    *,
    owner_text: str = "",
    url: str = "https://grok.com/",
    source: str = "grok_5loop_orchestrator",
    from_grok_receipt: str = "",
    loop: int = 0,
    copy_rank_offset: int = 0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stage Alice Browser hand: click Grok COPY on latest reply, read clipboard."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"alice-browser-grok-copy-{uuid.uuid4().hex[:12]}",
        "action": "alice_browser_grok_copy_last_reply",
        "source": source,
        "url": url,
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "from_grok_receipt": str(from_grok_receipt or ""),
        "loop": int(loop or 0),
        "copy_rank_offset": int(copy_rank_offset or 0),
        "status": "staged",
    }
    command_path(sd).write_text(
        json.dumps(row, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in (_COMMAND_LEDGER, "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


_FOOTER_MARKERS = (
    "Explore ",
    "Get notified when Grok finishes answering",
    "Enable",
    "\nFast\n",
    "Upgrade to SuperGrok",
    "Upgrade to",
)


def extract_latest_grok_reply_from_page_text(page_text: str) -> str:
    """Best-effort parse of the latest assistant block from a page snapshot.

    Used only as a COPY-button fallback — never as a fabricated Global Chat post
    without an honest receipt label (``copy_button_fallback_dom_extract``).
    """
    raw = str(page_text or "").replace("\r\n", "\n")
    if not raw.strip():
        return ""
    parts = re.split(r"Thought for \d+s", raw, flags=re.IGNORECASE)
    if len(parts) < 2:
        return ""
    chunk = parts[-1].strip()
    for marker in _FOOTER_MARKERS:
        idx = chunk.find(marker)
        if idx > 60:
            chunk = chunk[:idx].strip()
    chunk = re.sub(r"\n{3,}", "\n\n", chunk).strip()
    if len(chunk) < 80:
        return ""
    if _MODEL_LABEL_RE.match(chunk[:160]):
        return ""
    return chunk


def looks_like_alice_browser_question(text: str) -> bool:
    """Alice outgoing browser composer text — never a Grok mirror target."""
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return False
    if _ALICE_BROWSER_PROMPT_RE.search(clean):
        return True
    if _ALICE_LATEX_QUESTION_RE.search(clean) and "?" in clean:
        return True
    if clean.endswith("?") and not _GROK_REPLY_SIGNAL_RE.search(clean):
        if len(clean) < 320 or re.search(r"\b(?:also:|bonus points|quantify|VRAM|top-)\b", clean, re.I):
            return True
    return False


def clipboard_looks_like_grok_reply(text: str, *, last_alice_send_sha256: str = "") -> dict[str, Any]:
    """Reject common wrong COPY targets such as model-picker labels."""
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return {"ok": False, "reason": "clipboard_empty", "chars": 0}
    if last_alice_send_sha256:
        sha = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        if sha == last_alice_send_sha256:
            return {"ok": False, "reason": "matches_last_alice_browser_send", "chars": len(clean)}
    if _GLOBAL_CHAT_TRANSCRIPT_RE.search(clean) or "📋 Copy" in clean:
        return {"ok": False, "reason": "global_chat_transcript_or_copy_chrome", "chars": len(clean)}
    if looks_like_alice_browser_question(clean):
        return {"ok": False, "reason": "alice_or_owner_prompt_not_grok_reply", "chars": len(clean)}
    if len(clean) < 80:
        if _MODEL_LABEL_RE.match(clean) or ":" in clean or "/" in clean:
            return {"ok": False, "reason": "model_label_or_short_control_text", "chars": len(clean)}
        return {"ok": False, "reason": "too_short_for_grok_reply", "chars": len(clean)}
    if _MODEL_LABEL_RE.match(clean[:160]):
        return {"ok": False, "reason": "model_label_shape", "chars": len(clean)}
    if clean.endswith("?") and not _GROK_REPLY_SIGNAL_RE.search(clean):
        return {"ok": False, "reason": "question_without_grok_reply_signals", "chars": len(clean)}
    return {"ok": True, "reason": "probable_grok_reply", "chars": len(clean)}


def append_grok_copy_result(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault("schema", RESULT_TRUTH_LABEL)
    out.setdefault("truth_label", RESULT_TRUTH_LABEL)
    out.setdefault("ts", time.time())
    try:
        from System.swarm_alice_action_journal import append_action_journal

        journal = append_action_journal(out, state_dir=sd)
        out.setdefault("journal_ref", journal.get("journal_id") or journal.get("linked_receipt_id"))
    except Exception:
        pass
    line = json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n"
    for name in ("alice_browser_grok_copy_results.jsonl", "browser_action_diary.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass


__all__ = [
    "TRUTH_LABEL",
    "RESULT_TRUTH_LABEL",
    "append_grok_copy_result",
    "clipboard_looks_like_grok_reply",
    "command_path",
    "extract_latest_grok_reply_from_page_text",
    "looks_like_alice_browser_question",
    "stage_grok_copy_last_reply_command",
]
