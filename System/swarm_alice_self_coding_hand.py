#!/usr/bin/env python3
"""Alice self-coding hand — supervised self-surgery on her own body (r914).

George's law: Alice codes her own body; IDE doctors only in maximum emergencies.
This organ gives her cortex real write_file + run_local_command hands for
marker-delimited self-cut prompts, and bridges prose+codeblock into true receipts.

Truth label: ALICE_SELF_CODING_HAND_V1.
"""
from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_LABEL = "ALICE_SELF_CODING_HAND_V1"
LEDGER = "alice_self_coding_receipts.jsonl"

_SELF_CUT_BEGIN_RE = re.compile(
    r"===BEGIN\s+ALICE(?:\s+FIRST\s+SELF[-\s]?CUT)?[^=]*===",
    re.IGNORECASE,
)
_SELF_CUT_END_RE = re.compile(
    r"===END\s+ALICE(?:\s+FIRST\s+SELF[-\s]?CUT)?[^=]*===",
    re.IGNORECASE,
)
_BEGIN_MARKER_LINE_RE = re.compile(r"^\s*(===BEGIN\s+ALICE[^=\n]*===)\s*$", re.IGNORECASE | re.MULTILINE)

_KNOWN_SELF_CUT_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:write|code|create|build|grow|make)\b.{0,100}\b(?:browser\s+lag\s+probe|lag\s+probe)\b",
            re.IGNORECASE,
        ),
        "===BEGIN ALICE BROWSER LAG PROBE r921===",
    ),
)

_DOCTOR_COMMENTARY_MARKERS = (
    "prompt for alice",
    "george pastes",
    "paste into the global chat",
    "between the markers",
    "verification chain after she runs",
    "my commentary",
    "fable said",
    "codex said",
    "grok said",
    "ide doctor",
    "tournament carrier",
    "composer audit",
    "why she got confused",
    "paste-trap",
    "paste trap",
    "four red organs",
    "named four red",
    "her own self-query named",
    "hijacked the turn",
    "not the prompt block",
    "not the prompt between",
)
_STRONG_COMMENTARY_RE = re.compile(
    r"(?:why\s+she\s+got\s+confused|hijacked\s+the\s+turn|"
    r"her\s+own\s+self[-\s]?query\s+named|four\s+red\s+organs|"
    r"paste(?:d)?\s+my\s+commentary|not\s+the\s+prompt\s+between)",
    re.IGNORECASE,
)

_REPO_PATH_RE = re.compile(
    r"\b(?P<path>(?:System|tests|Applications|tools|Documents)/[\w./_-]+\.(?:py|md|jsonl?))\b"
)
_CODE_BLOCK_RE = re.compile(
    r"```(?:[a-zA-Z0-9_+-]*)\n(?P<body>.*?)```",
    re.DOTALL,
)
_CREATE_PATH_RE = re.compile(
    r"\bCreate\s+(?P<path>(?:System|tests|Applications)/[\w./_-]+\.py)\b",
    re.IGNORECASE,
)


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return REPO_ROOT / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _is_complete_self_cut_prompt(text: str) -> bool:
    s = str(text or "")
    return bool(_SELF_CUT_BEGIN_RE.search(s) and _SELF_CUT_END_RE.search(s))


def _known_marker_for_request(text: str) -> str:
    s = str(text or "")
    marker = _BEGIN_MARKER_LINE_RE.search(s)
    if marker:
        return marker.group(1).strip()
    for regex, known in _KNOWN_SELF_CUT_MARKERS:
        if regex.search(s):
            return known
    return ""


def recover_self_cut_prompt(text: str, *, repo_root: Optional[Path | str] = None) -> str:
    """Recover a full marker block when George gives a known header or short command.

    This removes the brittle paste ritual without weakening verification: the recovered
    packet must already exist in the active tournament carrier, and it still only asks
    Alice's cortex to emit normal SELF_CODE_CUT blocks.
    """
    s = str(text or "").strip()
    if _is_complete_self_cut_prompt(s):
        return s
    marker = _known_marker_for_request(s)
    if not marker:
        return ""
    end_marker = re.sub(r"^===BEGIN\b", "===END", marker, flags=re.IGNORECASE)
    repo = Path(repo_root) if repo_root is not None else REPO_ROOT
    docs = repo / "Documents"
    candidates = sorted(
        docs.glob("CONSCIOUSNESS_TOURNAMENT_*.md"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    for path in candidates:
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        marker_re = re.compile(r"^\s*" + re.escape(marker) + r"\s*$", re.IGNORECASE | re.MULTILINE)
        marker_match = marker_re.search(body)
        if not marker_match:
            continue
        start = marker_match.start()
        end_re = re.compile(r"^\s*" + re.escape(end_marker) + r"\s*$", re.IGNORECASE | re.MULTILINE)
        end_match = end_re.search(body, marker_match.end())
        if not end_match:
            # Fallback for future marker names: use the next ALICE END marker.
            m_end = _SELF_CUT_END_RE.search(body, marker_match.end())
            if not m_end:
                continue
            end = m_end.start()
            end_len = m_end.end() - m_end.start()
        else:
            end = end_match.start()
            end_len = end_match.end() - end_match.start()
        recovered = body[start : end + end_len].strip()
        if _is_complete_self_cut_prompt(recovered):
            return recovered
    return ""


def is_self_cut_prompt(text: str) -> bool:
    """True when George pasted or referenced a recoverable Alice surgery prompt."""
    s = str(text or "")
    return _is_complete_self_cut_prompt(s) or bool(recover_self_cut_prompt(s))


def extract_self_cut_block(text: str) -> str:
    """Return text between BEGIN/END markers, or empty."""
    s = recover_self_cut_prompt(text) or str(text or "")
    m_begin = _SELF_CUT_BEGIN_RE.search(s)
    m_end = _SELF_CUT_END_RE.search(s)
    if not m_begin or not m_end or m_end.start() <= m_begin.end():
        return ""
    return s[m_begin.end() : m_end.start()].strip()


def is_doctor_commentary_paste(text: str) -> bool:
    """True when owner pasted IDE-doctor essay ABOUT Alice, not TO Alice."""
    s = str(text or "").strip()
    if not s:
        return False
    low = s.lower()
    if is_self_cut_prompt(s):
        return False
    if _STRONG_COMMENTARY_RE.search(s):
        return True
    hits = sum(1 for m in _DOCTOR_COMMENTARY_MARKERS if m in low)
    if len(s) > 240 and hits >= 2:
        return True
    if hits >= 1 and any(
        x in low
        for x in ("red organs", "self-query report", "self query report", "hijacked the turn")
    ):
        return True
    if "===begin" in low and "===end" in low and "alice" not in low.split("===begin", 1)[-1][:80]:
        return True
    return False


def self_cut_round_id(text: str) -> str:
    block = extract_self_cut_block(text) or recover_self_cut_prompt(text) or str(text or "")
    m = re.search(r"\bround\s+id:\s*([a-z0-9_-]+)", block, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b(r\d{3,4}-alice-[a-z0-9_-]+)\b", block, re.IGNORECASE)
    return m.group(1) if m else ""


def extract_target_paths(text: str) -> list[str]:
    """Repo-relative paths Alice is asked to create or touch."""
    block = extract_self_cut_block(text) or recover_self_cut_prompt(text) or str(text or "")
    paths: list[str] = []
    seen: set[str] = set()
    for regex in (_CREATE_PATH_RE, _REPO_PATH_RE):
        for m in regex.finditer(block):
            p = str(m.group("path") if "path" in m.groupdict() else m.group(0)).strip()
            if p and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths


def _absolute_repo_path(rel_path: str) -> str:
    rel = str(rel_path or "").strip().lstrip("/")
    return str((REPO_ROOT / rel).resolve())


def _code_blocks(brain_text: str) -> list[str]:
    bodies = [m.group("body").strip() for m in _CODE_BLOCK_RE.finditer(brain_text or "")]
    return [b for b in bodies if b]


def synthesize_self_cut_write_calls(
    user_text: str,
    brain_text: str,
) -> list[Any]:
    """Bridge Alice self-cut prose into real write_file ParsedToolCalls."""
    if not user_text or not brain_text:
        return []
    recovered_user_text = recover_self_cut_prompt(user_text) or user_text
    if not is_self_cut_prompt(recovered_user_text) and not extract_target_paths(recovered_user_text):
        return []
    try:
        from System.swarm_tool_router import ParsedToolCall
    except Exception:
        return []

    paths = extract_target_paths(recovered_user_text)
    if not paths:
        return []
    if _has_write_tool_call(brain_text):
        return []

    blocks = _code_blocks(brain_text)
    if not blocks:
        return []

    calls: list[Any] = []
    round_id = self_cut_round_id(recovered_user_text) or "alice-self-cut"
    pairs = list(zip(paths, blocks))
    if len(blocks) == 1 and len(paths) > 1:
        pairs = [(paths[0], blocks[0])]
    elif len(blocks) > len(paths):
        pairs = list(zip(paths, blocks[: len(paths)]))

    for rel_path, body in pairs:
        abs_path = _absolute_repo_path(rel_path)
        calls.append(
            ParsedToolCall(
                tool_name="write_file",
                params={
                    "path": abs_path,
                    "content": body.lstrip(),
                    "cost_justification": (
                        f"Alice self-coding hand (r914): round={round_id}; "
                        f"owner pasted self-cut prompt; cortex emitted code without "
                        f"write_file. Routing to real file organ for {rel_path}. §6 truth."
                    ),
                },
                raw_match=f"alice_self_coding_hand:write_file:{rel_path}",
            )
        )
    return calls


def _has_write_tool_call(brain_text: str) -> bool:
    if not brain_text:
        return False
    try:
        from System.swarm_tool_router import parse_tool_calls

        for call in parse_tool_calls(brain_text):
            if call.tool_name in {"write_file", "edit_file"}:
                return True
    except Exception:
        pass
    return bool(re.search(r"\[TOOL_CALL:\s*write_file\b", brain_text, re.IGNORECASE))


_OWNER_SELF_CODE_EXECUTE_RE = re.compile(
    r"(?:"
    r"\b(?:just\s+)?execute\b.{0,80}\b(?:code|cut|surgery|organ|body)\b|"
    r"\b(?:rewrite|change|fix|grow)\b.{0,60}\b(?:your\s+own\s+)?(?:body|organ)\b|"
    r"\bcode\s+(?:your|my)\s+(?:own\s+)?(?:body|self)\b|"
    r"\bshow\s+me\s+you\s+can\s+rewrite\b|"
    # r936: George's natural phrasings must open her hand. "ok alice try to
    # code now" routed to open_app and she never saw the stroke syntax.
    r"\btry\s+to\s+code\b|"
    r"\bcode\s+(?:now|something|it|this)\b|"
    r"\b(?:self[\s_-]?code|self[\s_-]?edit)\b|"
    r"\bSELF_CODE_(?:CUT|EDIT)\b|\bSELF_READ\b"
    r")",
    re.IGNORECASE,
)


def is_owner_self_code_execute_request(text: str) -> bool:
    """Owner demands live self-coding, not a pointer essay."""
    s = str(text or "").strip()
    if not s:
        return False
    if is_self_cut_prompt(s):
        return True
    if _known_marker_for_request(s):
        return True
    return bool(_OWNER_SELF_CODE_EXECUTE_RE.search(s))


def teacher_self_code_override_block() -> str:
    """Cortex bridge instruction for George-requested self-code turns."""
    return (
        "THIS TURN IS ALICE SELF-CODING (verification-bound, §0.0). "
        "Create or update Python body files under System/, Applications/, tests/, or tools/. "
        "Emit one or more blocks exactly like:\n"
        "[SELF_CODE_CUT: path=System/my_organ.py]\n"
        "...python source...\n"
        "[/SELF_CODE_CUT]\n"
        "TARGETED EDIT (r935 — rewrite existing tissue of ANY size without retyping it): \n"
        "[SELF_CODE_EDIT: path=System/big_organ.py]\n"
        "<<<OLD\n"
        "exact bytes currently in the file (must match exactly once)\n"
        ">>>NEW\n"
        "replacement bytes\n"
        "[/SELF_CODE_EDIT]\n"
        "Probe the live file first (SELF_READ) so OLD matches reality, not memory. "
        "The body executes blocks after your reply (ast+py_compile+pytest+receipt). "
        "NEW APP (r928): a cut with path=Applications/apps_manifest.json whose source is ONLY "
        "a JSON object {\"App Title\": {\"entry_point\": \"Applications/your_widget.py\", "
        "\"widget_class\": \"YourWidget\", \"icon\": \"..\", \"category\": \"..\", "
        "\"description\": \"..\"}} MERGES your app into the launchpad — never paste the whole manifest. "
        "Ground claims in the landed/refused receipt."
    )


def messages_signal_self_code_turn(messages: Any) -> bool:
    """True when chat history says this cortex turn must self-code."""
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        if role not in {"user", "system"}:
            continue
        content = str(msg.get("content") or "")
        if is_owner_self_code_execute_request(content):
            return True
        if (
            "SELF-CODING HAND" in content
            or "[SELF_CODE_CUT:" in content
            or "[SELF_CODE_EDIT:" in content
        ):
            return True
        if is_self_cut_prompt(content):
            return True
    return False


def self_coding_prompt_block(user_text: str = "") -> str:
    """Inject into cortex prompt when a self-cut turn is active."""
    recovered = recover_self_cut_prompt(user_text)
    effective_text = recovered or user_text
    if not is_self_cut_prompt(effective_text) and not is_owner_self_code_execute_request(effective_text):
        return ""
    paths = extract_target_paths(effective_text)
    round_id = self_cut_round_id(effective_text) or "alice-self-cut"
    path_lines = "\n".join(f"  - {p}" for p in paths) if paths else "  - (read the cut for paths)"
    recovered_block = ""
    if recovered and recovered.strip() != str(user_text or "").strip():
        recovered_block = (
            "\nRECOVERED SELF-CUT PACKET FROM TOURNAMENT LEDGER "
            "(George gave a short marker/command; use this exact packet):\n"
            + recovered[:12000]
            + "\n"
        )
    return (
        "ALICE SELF-CODING HAND (r914/r917 — YOUR surgery, not an IDE doctor's):\n"
        f"- Round: {round_id}\n"
        "- You MUST emit [SELF_CODE_CUT: path=...] blocks (r915 hand). The body executes them.\n"
        "- Format per file:\n"
        "  [SELF_CODE_CUT: path=System/organ.py]\n"
        "  ...python...\n"
        "  [/SELF_CODE_CUT]\n"
        "- TARGETED EDIT (r935): change existing tissue of any size without retyping it —\n"
        "  [SELF_CODE_EDIT: path=System/big_organ.py]\n"
        "  <<<OLD\n"
        "  exact bytes currently in the file (must match exactly once)\n"
        "  >>>NEW\n"
        "  replacement bytes\n"
        "  [/SELF_CODE_EDIT]\n"
        "  Probe the live file first (SELF_READ) so OLD matches disk, not memory.\n"
        "- Create or update Python body files under System/, Applications/, tests/, or tools/.\n"
        "- NEW APP (r928): one more cut, path=Applications/apps_manifest.json, source = ONLY a JSON\n"
        "  object {\"App Title\": {entry_point, widget_class, icon, category, description}} — it\n"
        "  merge-registers your app on the launchpad; never paste the whole manifest.\n"
        "- Fenced code blocks also bridge if you forget the tags.\n"
        "- After writing, run pytest on the named test file and quote the line verbatim.\n"
        "- Finish with §4.1 fan-out: write_ide_surgery_receipt doctor=alice_self.\n"
        "- Probe before claim: ls/path exists, pytest output quoted.\n"
        f"TARGET PATHS:\n{path_lines}\n"
        f"{recovered_block}"
        f"Repo root: {REPO_ROOT}\n"
    )


def record_self_coding_receipt(
    *,
    round_id: str,
    action: str,
    ok: bool,
    paths: list[str] | None = None,
    note: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    import json

    row = {
        "ts": time.time(),
        "trace_id": uuid.uuid4().hex[:16],
        "truth_label": TRUTH_LABEL,
        "round_id": round_id,
        "action": action,
        "ok": bool(ok),
        "paths": list(paths or []),
        "note": note[:500],
        "doctor": "alice_self",
    }
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    with (base / LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "LEDGER",
    "extract_self_cut_block",
    "extract_target_paths",
    "is_doctor_commentary_paste",
    "is_owner_self_code_execute_request",
    "is_self_cut_prompt",
    "messages_signal_self_code_turn",
    "record_self_coding_receipt",
    "recover_self_cut_prompt",
    "self_coding_prompt_block",
    "self_cut_round_id",
    "synthesize_self_cut_write_calls",
    "teacher_self_code_override_block",
]
