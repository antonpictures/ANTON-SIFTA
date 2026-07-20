#!/usr/bin/env python3
"""Alice Browser Grok self-type command organ.

This is the Alice-owned command path for owner turns such as:

    Alice, type "Hello world" to Grok in your Alice Browser and press Enter.

Talk stages a small JSON command; Alice Browser consumes it inside the
QWebEngine limb and writes the result receipt. Codex/other IDEs may inspect the
receipts, but the command is not a manual Codex screen drive.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_BROWSER_GROK_SELF_TYPE_COMMAND_V1"
RESULT_TRUTH_LABEL = "ALICE_BROWSER_GROK_SELF_TYPE_RESULT_V1"
ROUTE_KILL_TRUTH_LABEL = "ALICE_BROWSER_GROK_ROUTE_KILL_HANDOFF_V1"

# Old loose regex that hijacked "tell grok in alice browser" into mirror-reply cortex.
_LEGACY_MIRROR_REPLY_HIJACK_RE = re.compile(
    r"\bgrok\b.{0,50}\b(?:in\s+)?(?:alice\s+)?browser\b",
    re.IGNORECASE,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_browser_grok_self_type_command.json"
_COMMAND_LEDGER = "alice_browser_grok_self_type_commands.jsonl"

_DOUBLE_QUOTED_TEXT_RE = re.compile(r"[\"“]([^\"”]{1,500})[\"”]")
_SINGLE_QUOTED_TEXT_RE = re.compile(r"(?<!\w)['‘]([^'’]{1,500})['’](?!\w)")
_GROK_SELF_TYPE_RE = re.compile(
    r"\b(?:alice|she)\b.{0,120}\b(?:type|write|put|enter)\b"
    r".{0,260}\b(?:grok|alice\s+browser|browser)\b",
    re.IGNORECASE | re.DOTALL,
)
_CONTINUOUS_GROK_DIALOGUE_RE = re.compile(
    r"\b(?:infinit(?:e|ely)|infinately|forever|open[-\s]?ended|unbounded|no\s+(?:round|turn)\s+limit)\b|"
    r"\bunti?ll?\s+(?:i|george|owner|you)\s+stop(?:\s+it)?\b|"
    r"\bunti?ll?\s+stopped\b|"
    r"\bkeep\s+(?:going|chat(?:ting)?|talking|the\s+conversation\s+going)\b",
    re.IGNORECASE,
)
_STOP_GROK_DIALOGUE_RE = re.compile(
    r"\b(?:stop|halt|pause|disable|end)\b.{0,90}\b(?:grok|browser\s+grok|grok\s+(?:loop|autopilot|dialogue|conversation)|conversation\s+with\s+grok)\b|"
    r"\b(?:grok|browser\s+grok)\b.{0,90}\b(?:stop|halt|pause|disable|end)\b",
    re.IGNORECASE,
)


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


_INSTRUCTION_PLACEHOLDER_RE = re.compile(
    r"^(?:your own(?:\s+opening)?\s*line|opening line|a line|something|.+ yourself)\s*$",
    re.IGNORECASE,
)


def parse_grok_dialogue_target_rounds(text: str, *, default: int = 3) -> int:
    """Owner '7 rounds with Grok' → mission budget (not hardcoded 3)."""
    clean = " ".join((text or "").strip().split())
    if not clean:
        return default
    m = re.search(
        r"\b(\d{1,2})\s*[- ]?(?:round|turn|loop|sound|time|exchange|message|reply|response)s?\b",
        clean,
        re.IGNORECASE,
    )
    if m:
        return max(1, min(30, int(m.group(1))))
    return default


def wants_continuous_grok_dialogue(text: str) -> bool:
    """Owner wants the Browser Grok dialogue to continue until an explicit stop."""
    clean = " ".join((text or "").strip().split())
    if not clean:
        return False
    return bool(_CONTINUOUS_GROK_DIALOGUE_RE.search(clean))


def wants_stop_grok_dialogue(text: str) -> bool:
    """Owner-facing brake for the continuous Browser Grok dialogue."""
    clean = " ".join((text or "").strip().split())
    if not clean:
        return False
    return bool(_STOP_GROK_DIALOGUE_RE.search(clean))


_GROK_ATTACHMENT_SEP_RE = re.compile(
    r"----\s*:?\s*\"?\s*grok\b|"
    r"\n\s*Grok\s*\(\s*Grok\s*\(\s*BROWSER",
    re.IGNORECASE,
)


def split_owner_grok_dialogue_turn(text: str) -> tuple[str, str]:
    """Split owner control instruction from an optional attached Grok mirror paste."""
    raw = (text or "").strip()
    if not raw:
        return "", ""
    m = _GROK_ATTACHMENT_SEP_RE.search(raw)
    if m and m.start() >= 15:
        control = raw[: m.start()].strip().rstrip("-:")
        attachment = raw[m.start() :].strip()
        if len(control) >= 10:
            return control, attachment
    if len(raw) > 500:
        head = raw[: min(500, len(raw))]
        if re.search(
            r"\b(?:pls?|please)\s+continue\b|\banother\s+\d{1,2}\s*(?:more\s+)?(?:round|turn|loop)s?\b",
            head,
            re.IGNORECASE,
        ):
            m2 = re.search(
                r"\*\*Alice,|\b```python\b|\bPASTE REPLAY\b|\bknown_content_replay\b",
                raw,
                re.IGNORECASE,
            )
            if m2 and m2.start() > 30:
                return raw[: m2.start()].strip().rstrip("-:"), raw[m2.start() :].strip()
    return raw, ""


def extract_grok_continue_context(text: str) -> str:
    """Owner-provided Grok answer attached to a continue command.

    This text is S5 input for Alice's cortex. It is never the opening question
    to paste into the browser composer.
    """
    control, attachment = split_owner_grok_dialogue_turn(text)
    raw = (attachment or "").strip()
    if not raw:
        control_clean = " ".join((control or text or "").strip().split()).lower()
        if not (
            re.search(r"\b(?:pls?|please)\s+continue\b", control_clean)
            or re.search(r"\banother\s+\d{1,2}\s*(?:more\s+)?(?:round|turn|loop)s?\b", control_clean)
            or re.search(r"\bsame\s+thread\b", control_clean)
            or re.search(
                r"\bpaste\s+(?:your\s+)?(?:response|answer|reply)\s+back\s+to\s+grok\b",
                control_clean,
            )
        ):
            return ""
        markers = [
            r"(?:^|\s)(?:[-–—]{2,}\s*)?(?::\s*)?grok\s*[:：]?\s*[\"“]",
            r"\bgrok\s+said\s*[:：]\s*[\"“]?",
            r"\bfrom\s+grok\s*[:：]\s*[\"“]?",
        ]
        last: Optional[re.Match[str]] = None
        for pattern in markers:
            for match in re.finditer(pattern, text or "", re.IGNORECASE | re.DOTALL):
                last = match
        if last is not None:
            raw = (text or "")[last.end() :].strip()
    if not raw:
        return ""
    context = re.sub(r"^\s*[-–—]{2,}\s*:?\s*", "", raw).strip()
    context = re.sub(r"^\s*grok\s*[:：]?\s*", "", context, flags=re.IGNORECASE).strip()
    context = context.lstrip("\"“”'‘’").strip()
    context = re.sub(r"\s*📋\s*Copy\s*$", "", context).strip()
    context = context.rstrip("\"”'’").strip()
    context = re.sub(r"\s+", " ", context).strip()
    if len(context) < 40:
        return ""
    return context[:12000]


def looks_like_grok_continue_context_mission(text: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """Continuation command with attached Grok answer that should run Alice cortex now."""
    control, _attachment = split_owner_grok_dialogue_turn(text)
    route = control or text
    if not extract_grok_continue_context(text):
        return False
    return looks_like_grok_dialogue_continue(route, state_dir=state_dir)


def looks_like_grok_dialogue_continue(text: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """Owner extends an in-flight Grok browser thread (not a fresh mission brief)."""
    control, _attachment = split_owner_grok_dialogue_turn(text)
    clean = " ".join((control or text or "").strip().split())
    if not clean:
        return False
    lower = clean.lower()
    has_round_budget = parse_grok_dialogue_target_rounds(clean, default=0) > 0
    has_continuous_budget = wants_continuous_grok_dialogue(clean)
    continue_markers = (
        re.search(r"\b(?:pls?|please)\s+continue\b", lower),
        re.search(r"\bcontinue\b.{0,100}\b(?:paste|round|thread|grok|chat)\b", lower),
        re.search(r"\banother\s+\d{1,2}\s*(?:more\s+)?(?:round|turn|loop)s?\b", lower),
        re.search(
            r"\bpaste\s+(?:your\s+)?(?:response|answer|reply)\s+back\s+to\s+grok\b",
            lower,
        ),
        re.search(r"\bsame\s+thread\b", lower),
    )
    if not any(continue_markers):
        if has_continuous_budget and grok_dialogue_active(state_dir):
            return True
        return False
    if grok_dialogue_active(state_dir) or "grok" in lower or has_round_budget or has_continuous_budget:
        return True
    return False


def grok_dialogue_active(state_dir: Optional[Path | str] = None) -> bool:
    """True when continuous Grok mirror autopilot or an active dialogue mission is armed."""
    sd = state_dir_path(state_dir)
    try:
        from System.swarm_alice_grok_mirror_autopilot import autopilot_enabled

        if autopilot_enabled(sd):
            return True
    except Exception:
        pass
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if mission_path.exists():
        try:
            data = json.loads(mission_path.read_text(encoding="utf-8"))
            if str(data.get("status") or "").lower() == "active":
                return True
        except Exception:
            pass
    return False


def looks_like_grok_mirror_paste(text: str) -> bool:
    """Long mirrored Grok/Global prose must not trigger browser select_result reflexes."""
    clean = " ".join((text or "").strip().split())
    if len(clean) < 180:
        return False
    lower = clean.lower()
    score = 0
    if "typed ingress repair" in lower or re.search(r"\bioan\s*\(\s*typed\s*\)", lower):
        score += 2
    if "thought for" in lower or "top-k" in lower or "moe routing" in lower:
        score += 1
    if re.search(r"\b(?:pheromone|qualia|stigmergic silicon|expert layers?)\b", lower):
        score += 1
    if re.search(r"\b(?:grok mirror|copy each grok|website grok)\b", lower):
        score += 1
    return score >= 2


def owner_turn_blocks_browser_reflex(text: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """Grok dialogue turns are cortex-only — never select_result on mirror prose."""
    if looks_like_grok_mirror_paste(text):
        return True
    clean = " ".join((text or "").strip().split())
    if grok_dialogue_active(state_dir) and len(clean) >= 120:
        return True
    return False


_NON_GROK_CHAT_URL_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?"
    r"(?:deepai\.org|chatgpt\.com|chat\.openai\.com|claude\.ai|gemini\.google\.com|"
    r"perplexity\.ai|poe\.com|character\.ai|you\.com|huggingface\.co/chat)\b",
    re.IGNORECASE,
)


def owner_targets_non_grok_browser_chat(text: str) -> bool:
    """Owner is on (or means) a non-Grok chat page — Grok autopilot must not arm or redirect."""
    control, _attachment = split_owner_grok_dialogue_turn(text)
    clean = " ".join((control or text or "").strip().split())
    if not clean:
        return False
    lower = clean.lower()
    if _NON_GROK_CHAT_URL_RE.search(clean):
        return True
    on_current_page = bool(
        re.search(
            r"\b(?:new\s+page|this\s+page|on\s+this\s+(?:new\s+)?page|page\s+we\s+just\s+open(?:ed)?)\b",
            lower,
        )
    )
    if on_current_page and re.search(r"\b(?:chat|chatbot|ask\s+the)\b", lower):
        return True
    if re.search(r"\bask\s+the\s+chatbot\b", lower):
        return True
    if re.search(r"\bthe\s+same\b", lower) and "grok" in lower and on_current_page:
        return True
    if re.search(r"\bintroduce\s+yourself\s+as\s+alice\b", lower) and re.search(
        r"\b(?:new\s+page|this\s+page|chatbot|deepai|identify\s+itself)\b",
        lower,
    ):
        return True
    return False


def looks_like_grok_mission_brief(text: str) -> bool:
    """Multi-step mission text must not auto-type a fragment or stall in empty cortex."""
    control, _attachment = split_owner_grok_dialogue_turn(text)
    clean = " ".join((control or text or "").strip().split())
    if not clean:
        return False
    if owner_targets_non_grok_browser_chat(text):
        return False
    lower = clean.lower()
    continuous_grok_mission = bool(
        wants_continuous_grok_dialogue(clean)
        and re.search(r"\b(?:grok|browser)\b", lower)
        and re.search(r"\b(?:chat(?:ting)?|talk(?:ing)?|conversation|converse|reply|copy)\b", lower)
    )
    if looks_like_grok_dialogue_continue(clean) and not continuous_grok_mission:
        return False
    if continuous_grok_mission:
        if re.search(r"\b(?:chat(?:ting)?|talk(?:ing)?|conversation|converse|reply|copy)\b", lower):
            return True
    if re.search(r"\b\d{1,2}\s*(?:round|turn|loop|sound)s?\b", lower) and "grok" in lower:
        return True
    if re.search(r"\b(?:ask|tell)\s+(?:website\s+)?grok\b", lower) and "chat" in lower:
        return True
    if "round 1" in lower and "round 2" in lower:
        return True
    # A numbered multi-step brief only counts as a Grok mission if it actually
    # names Grok. Without this anchor any pasted numbered list (status updates,
    # plans, changelogs) armed a browser mission and drove Alice to grok.com.
    if (
        "grok" in lower
        and re.search(r"\b\d[\).:-]\s", clean)
        and re.search(r"\b\d[\).:-]\s", clean[clean.find("2") :])
    ):
        return True
    if "george wants" in lower and ("round" in lower or "conversation" in lower):
        return True
    if "natural" in lower and "round" in lower and "grok" in lower and "browser" in lower:
        return True
    if "copy each grok reply" in lower or "copy each grok" in lower:
        return True
    if len(clean) >= 120:
        return False
    return False


def looks_like_instruction_placeholder_payload(payload: str) -> bool:
    """Reject coach placeholders mistaken for words Alice should type in Grok."""
    clean = " ".join((payload or "").strip().split())
    if not clean:
        return True
    if _INSTRUCTION_PLACEHOLDER_RE.match(clean):
        return True
    if re.search(r"\byour own\b", clean, re.IGNORECASE) and len(clean) < 80:
        return True
    return False


_ASK_GROK_RE = re.compile(
    r"\b(?:ask|tell)\s+(?:website\s+)?grok\b[,:]?\s*(?P<q>.+)$",
    re.IGNORECASE,
)

_ANSWER_GROK_IN_BROWSER_RE = re.compile(
    r"\b(?:answer|reply|respond(?:\s+to)?)\b.{0,50}\bgrok\b"
    r"(?:.{0,40}\b(?:in\s+)?(?:alice\s+)?browser\b)?",
    re.IGNORECASE,
)


def would_legacy_mirror_reply_hijack(text: str) -> bool:
    """True when the pre-fix route would steal a tell/ask grok send into mirror-reply cortex."""
    clean = " ".join((text or "").strip().split())
    if not clean:
        return False
    if not re.search(r"\b(?:tell|ask)\s+grok\b", clean, re.IGNORECASE):
        return False
    return bool(_LEGACY_MIRROR_REPLY_HIJACK_RE.search(clean))


def emit_route_kill_handoff_receipt(
    owner_text: str,
    *,
    payload_preview: str = "",
    handoff_swimmer: str = TRUTH_LABEL,
    handoff_receipt_id: str = "",
    killed_route: str = "grok_mirror_reply_cortex",
    killed_swimmer: str = "self_narration_skip_cortex_empty",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Kill the dead mirror-reply route; receipt handoff to browser self-type swimmer."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": ROUTE_KILL_TRUTH_LABEL,
        "truth_label": ROUTE_KILL_TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"route-kill-{uuid.uuid4().hex[:12]}",
        "action": "route_kill_handoff",
        "decision": "kill_route_do_not_use",
        "killed_route": killed_route,
        "killed_swimmer": killed_swimmer,
        "killed_reason": "tell_ask_grok_in_browser_is_new_send_not_mirror_reply",
        "handoff_swimmer": handoff_swimmer,
        "handoff_receipt_id": handoff_receipt_id,
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "payload_preview": " ".join((payload_preview or "").split())[:240],
        "stigmergic": True,
        "heal_not_ban": True,
    }
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in ("work_receipts.jsonl", "alice_browser_grok_route_kills.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    try:
        from System.ide_stigmergic_bridge import deposit

        deposit(
            "alice_browser_hand",
            (
                f"ROUTE_KILL {killed_route} → {handoff_swimmer}; "
                f"owner={row['owner_text_preview'][:120]}"
            ),
            kind="route_kill_handoff",
            extra={
                "receipt_id": row["receipt_id"],
                "handoff_receipt_id": handoff_receipt_id,
                "payload_preview": row["payload_preview"],
            },
        )
    except Exception:
        pass
    try:
        from System.swarm_stigmergic_browser_world_model import record_stigmergic_browser_action

        record_stigmergic_browser_action(
            url="https://grok.com/",
            action="route_kill_handoff",
            source="swarm_alice_browser_grok_self_type",
            owner_input=True,
            extra={
                "route_kill_receipt_id": row["receipt_id"],
                "killed_route": killed_route,
                "handoff_swimmer": handoff_swimmer,
            },
            state_dir=sd,
        )
    except Exception:
        pass
    return row


def wants_answer_grok_in_browser(text: str) -> bool:
    """Owner wants Alice to compose + send a reply in the Alice Browser Grok tab.

    Must be phrased as "answer/reply/respond to grok" (optionally "... in browser").
    Commands like "tell grok in alice browser about X" are for *sending new content*,
    not replying to an existing mirror, and must NOT match here.
    """
    clean = " ".join((text or "").strip().split())
    if not clean:
        return False
    lower = clean.lower()
    if re.search(r"\b(?:tell|ask)\s+grok\b", lower):
        return False
    return bool(_ANSWER_GROK_IN_BROWSER_RE.search(clean))


def extract_grok_ask_payload(text: str) -> str:
    """Owner: 'ask grok what llm...' or 'tell grok in alice browser about X' → text for Alice Browser composer."""
    clean = " ".join((text or "").strip().split())
    if not clean or looks_like_grok_mission_brief(clean):
        return ""
    # Special handling for "tell/ask grok in (alice) browser about <topic>"
    # so the command stages a real send of the topic, not hijacked to "reply to mirror".
    m_browser = re.search(
        r"\b(?:tell|ask)\s+grok\b.{0,30}\b(?:in\s+)?(?:alice\s+)?browser\b\s+(?:about\s+)?(?P<topic>.+)",
        clean,
        re.IGNORECASE,
    )
    if m_browser:
        topic = m_browser.group("topic").strip().rstrip(".")
        # Turn the topic into a natural statement Alice can send.
        # Owner intent "tell grok about your ability..." becomes something sendable.
        if re.search(r"\bability to code (your)?self\b", topic, re.IGNORECASE):
            payload = "I can code myself via We Code Together, MiMo as cortex, and receipt-driven patches in the SIFTA swarm."
        elif looks_like_instruction_placeholder_payload(topic):
            return ""
        else:
            payload = topic
        return payload[:500]

    m = _ASK_GROK_RE.search(clean)
    if not m:
        return ""
    payload = m.group("q").strip().rstrip(".")
    if looks_like_instruction_placeholder_payload(payload):
        return ""
    return payload[:500]


def extract_grok_mission_first_question(text: str) -> str:
    """From a multi-round mission brief, extract the one opening question for Grok browser."""
    clean = " ".join((text or "").strip().split())
    if looks_like_grok_continue_context_mission(text):
        return ""
    if not clean or not looks_like_grok_mission_brief(clean):
        return ""

    def _clean_payload(payload: str) -> str:
        out = " ".join((payload or "").strip().split())
        out = out.strip(" .,:;")
        out = re.sub(r"\s*(?:={2,}|[-–—]+)\s*$", "", out).strip()
        return out.strip(" .,:;")

    m_quoted = re.search(
        r'\b(?:ask|tell)\s+(?:website\s+)?grok\b[^"“]*["“]([^"”]{3,500})["”]',
        clean,
        re.IGNORECASE,
    )
    if m_quoted:
        payload = _clean_payload(m_quoted.group(1))
        if not looks_like_instruction_placeholder_payload(payload):
            return payload[:500]
    for m in _DOUBLE_QUOTED_TEXT_RE.finditer(clean):
        payload = _clean_payload(m.group(1))
        if len(payload) >= 3 and not looks_like_instruction_placeholder_payload(payload):
            return payload[:500]
    for m in _SINGLE_QUOTED_TEXT_RE.finditer(clean):
        payload = _clean_payload(m.group(1))
        if len(payload) >= 3 and not looks_like_instruction_placeholder_payload(payload):
            return payload[:500]
    m_about = re.search(
        r"\babout:\s*(.+?)(?:\.\s+(?:you choose|copy)|\.\s+follow|$)",
        clean,
        re.IGNORECASE,
    )
    if m_about:
        payload = _clean_payload(m_about.group(1))
        if payload and not looks_like_instruction_placeholder_payload(payload):
            return payload[:500]
    m_topic = re.search(
        r"\b(?:ask|tell)\s+(?:website\s+)?grok\b\s+(?:about\s+)?(?P<topic>.+?)"
        r"(?:\s+and\s+chat|\s+for\s+\d|\s+\d\s*[- ]?(?:round|turn|loop|sound)s?\b|$)",
        clean,
        re.IGNORECASE,
    )
    if m_topic:
        payload = _clean_payload(m_topic.group("topic"))
        if payload and not looks_like_instruction_placeholder_payload(payload):
            return payload[:500]
    return ""


def extract_grok_browser_payload(text: str) -> str:
    """Any owner command that should become text in the Grok browser composer."""
    control, _attachment = split_owner_grok_dialogue_turn(text)
    route = control or text
    if looks_like_grok_dialogue_continue(route):
        return ""
    return extract_grok_self_type_payload(route) or extract_grok_ask_payload(route)


def extract_grok_self_type_payload(text: str) -> str:
    """Extract text Alice should type into Grok from a natural owner command."""
    clean = " ".join((text or "").strip().split())
    if not clean or not _GROK_SELF_TYPE_RE.search(clean):
        return ""
    if looks_like_grok_mission_brief(clean):
        return ""
    quoted = [m.group(1).strip() for m in _DOUBLE_QUOTED_TEXT_RE.finditer(clean) if m.group(1).strip()]
    if not quoted:
        quoted = [m.group(1).strip() for m in _SINGLE_QUOTED_TEXT_RE.finditer(clean) if m.group(1).strip()]
    if quoted:
        payload = quoted[-1][:500]
        if looks_like_instruction_placeholder_payload(payload):
            return ""
        return payload
    m = re.search(
        r"\b(?:type|write|put|enter)\b\s+(?P<payload>.+?)"
        r"(?:\s+(?:to|into|in|inside)\s+(?:the\s+)?(?:grok|alice\s+browser|browser|box|composer)\b|$)",
        clean,
        re.IGNORECASE,
    )
    if not m:
        return ""
    payload = re.sub(
        r"\s*(?:herself|yourself|and\s+(?:push|press|click)\s+enter|and\s+click\s+send|and\s+send(?:\s+it)?|then\s+send(?:\s+it)?)\s*$",
        "",
        m.group("payload").strip(),
        flags=re.IGNORECASE,
    )
    payload = payload.strip(" .:;")[:500]
    if looks_like_instruction_placeholder_payload(payload):
        return ""
    return payload


def wants_enter(text: str) -> bool:
    clean = (text or "").lower()
    if _ASK_GROK_RE.search(clean):
        return True
    return bool(re.search(r"\b(?:press|push|hit|send|submit|click)\s+(?:enter|return|send)\b|\band\s+enter\b", clean))


def _normalized_text(value: str) -> str:
    return " ".join((value or "").split())


def grok_send_verdict(
    text: str,
    *,
    url: str = "",
    page_text: str = "",
    draft_texts: Optional[list[str]] = None,
    press_enter: bool = True,
) -> dict[str, Any]:
    """Classify a Grok self-type result without mistaking an unsent draft for send.

    Grok pages can contain the payload in two places: a real chat bubble or the
    still-open composer draft. A green send receipt requires the payload on the
    conversation page and no visible composer draft still holding the same text.
    """
    payload = _normalized_text(text)
    page = _normalized_text(page_text)
    drafts = [_normalized_text(d) for d in (draft_texts or []) if _normalized_text(d)]
    page_contains = bool(payload and payload in page)
    if not page_contains and len(payload) > 280:
        prefix = payload[:280]
        page_contains = prefix in page
    draft_contains = any(payload in d for d in drafts) if payload else False
    if not draft_contains and len(payload) > 280:
        prefix = payload[:280]
        draft_contains = any(prefix in d for d in drafts) if prefix else False
    url_l = (url or "").lower()
    on_chat_page = (
        "/c/" in url_l
        or "chatgpt.com" in url_l
        or "chat.openai.com" in url_l
        or "duck.ai" in url_l
        or "gemini.google.com" in url_l
        or "grok.com" in url_l
    )
    if press_enter:
        if on_chat_page and page_contains and not draft_contains:
            return {
                "ok": True,
                "status": "sent",
                "reason": "payload_on_chat_page_and_composer_clear",
                "page_contains_payload": page_contains,
                "draft_contains_payload": draft_contains,
            }
        if draft_contains:
            return {
                "ok": False,
                "status": "draft_still_in_composer",
                "reason": "payload_still_visible_in_grok_composer",
                "page_contains_payload": page_contains,
                "draft_contains_payload": draft_contains,
            }
        if page_contains:
            return {
                "ok": False,
                "status": "unverified",
                "reason": "payload_on_page_without_composer_clear_proof",
                "page_contains_payload": page_contains,
                "draft_contains_payload": draft_contains,
            }
        return {
            "ok": False,
            "status": "unverified",
            "reason": "payload_not_found_after_submit",
            "page_contains_payload": page_contains,
            "draft_contains_payload": draft_contains,
        }
    if page_contains or draft_contains:
        return {
            "ok": True,
            "status": "filled",
            "reason": "press_enter_false_payload_visible",
            "page_contains_payload": page_contains,
            "draft_contains_payload": draft_contains,
        }
    return {
        "ok": False,
        "status": "unverified",
        "reason": "press_enter_false_payload_not_found",
        "page_contains_payload": page_contains,
        "draft_contains_payload": draft_contains,
    }


def _current_browser_page_url(state_dir: Optional[Path | str]) -> str:
    """URL of the page currently open in Alice Browser, or '' if unknown.

    This is what makes the self-type generic: the fill+enter+verify mechanism is
    already site-agnostic (her grok success receipt found the box by element score,
    method=js_native_fill_enter_submit, verified payload_on_chat_page). We just
    point it at whatever page is actually open — we do NOT enumerate chatbot domains.
    """
    try:
        from System.swarm_browser_page_state import latest_page_state

        st = latest_page_state(now=time.time(), max_age_s=900.0, state_dir=state_dir)
        return str((st or {}).get("url") or "").strip()
    except Exception:
        return ""


def stage_grok_self_type_command(
    text: str,
    *,
    owner_text: str = "",
    press_enter: bool = True,
    url: Optional[str] = None,
    source: str = "talk_to_alice_widget",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Write the Alice Browser command file and append command ledgers.

    url=None (default) targets the CURRENT open Alice Browser page, so the same
    generic mechanism George proved on grok.com drives any chat site (chatgpt.com,
    deepai.org, ...) — same move, different host. Falls back to grok.com only when
    no current page is known. No domain enumeration: the hand reads the live page.
    """
    payload = " ".join((text or "").split())
    if not payload:
        raise ValueError("stage_grok_self_type_command requires non-empty text")
    sd = state_dir_path(state_dir)
    if not url:
        url = _current_browser_page_url(sd) or "https://grok.com/"
    sd.mkdir(parents=True, exist_ok=True)
    owner_clean = " ".join((owner_text or "").split())
    receipt_id = f"alice-browser-grok-self-type-{uuid.uuid4().hex[:12]}"
    if owner_clean and would_legacy_mirror_reply_hijack(owner_clean):
        emit_route_kill_handoff_receipt(
            owner_clean,
            payload_preview=payload,
            handoff_swimmer=TRUTH_LABEL,
            handoff_receipt_id=receipt_id,
            state_dir=sd,
        )
    now_ts = time.time()
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": now_ts,
        "start_ts": now_ts,
        "receipt_id": receipt_id,
        "action": "alice_browser_grok_self_type",
        "source": source,
        "url": url,
        "press_enter": bool(press_enter),
        "text_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "text_preview": payload[:240],
        "owner_text_preview": owner_clean[:300],
        "status": "staged",
    }
    if owner_clean and would_legacy_mirror_reply_hijack(owner_clean):
        row["route_kill"] = True
        row["route_kill_reason"] = "mirror_reply_cortex_bypassed_for_browser_self_type"

    # GM6: known_content_replay detector (same payload hash to same surface)
    text_hash = row["text_sha256"]
    prior_receipt = None
    for ledger_name in ("alice_browser_grok_self_type_commands.jsonl", "alice_browser_grok_self_type_results.jsonl", "browser_action_diary.jsonl"):
        lp = sd / ledger_name
        if lp.exists():
            for line in reversed(lp.read_text(errors="replace").splitlines()[-30:]):
                if not line.strip(): continue
                try:
                    r = json.loads(line)
                    if r.get("url") == url and r.get("text_sha256") == text_hash:
                        prior_receipt = r.get("receipt_id") or r.get("result_receipt_id") or r.get("trace_id")
                        break
                except:
                    pass
            if prior_receipt: break
    if prior_receipt:
        row["known_content_replay"] = True
        row["prior_receipt_id"] = prior_receipt

    command = dict(row)
    command["text"] = payload
    command_path(sd).write_text(json.dumps(command, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in (_COMMAND_LEDGER, "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


def predecessor_receipt_exists(predecessor_receipt_id: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """GM8: gate next step on predecessor receipt existing in the journal ledgers."""
    if not predecessor_receipt_id:
        return True
    sd = state_dir_path(state_dir)
    for ln in ("alice_browser_grok_self_type_results.jsonl", "work_receipts.jsonl", "browser_action_diary.jsonl", "alice_first_person_journal.jsonl"):
        p = sd / ln
        if p.exists():
            try:
                for line in p.read_text(errors="replace").splitlines()[-100:]:
                    if predecessor_receipt_id in line:
                        return True
            except Exception:
                pass
    return False


def append_grok_self_type_result(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault("schema", RESULT_TRUTH_LABEL)
    out.setdefault("truth_label", RESULT_TRUTH_LABEL)
    now2 = time.time()
    out.setdefault("ts", now2)
    out.setdefault("end_ts", now2)
    if "start_ts" in out:
        out["elapsed_s"] = round(out["end_ts"] - out["start_ts"], 3)
    try:
        from System.swarm_alice_action_journal import append_action_journal

        journal = append_action_journal(out, state_dir=sd)
        out.setdefault("journal_ref", journal.get("journal_id") or journal.get("linked_receipt_id"))
    except Exception:
        pass
    line = json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n"
    for name in ("alice_browser_grok_self_type_results.jsonl", "browser_action_diary.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    try:
        from System.swarm_web_ai_chat_bridge import mirror_grok_self_type_to_web_ai_bridge

        mirror_grok_self_type_to_web_ai_bridge(out, state_dir=sd)
    except Exception:
        pass


def compute_attention_vector(
    state_dir: Optional[Path | str] = None,
    mission_target: str = "",
    window_s: float = 3600.0,
) -> dict[str, Any]:
    """GM7: surfaces × frequency × recency from recent browser hand actions vs mission."""
    sd = state_dir_path(state_dir)
    now = time.time()
    attention: dict[str, float] = {}
    for ledger_name in ("browser_action_diary.jsonl", "alice_browser_grok_self_type_results.jsonl", "alice_self_type_to_talk_box.jsonl"):
        p = sd / ledger_name
        if not p.exists():
            continue
        try:
            for line in p.read_text(errors="replace").splitlines()[-200:]:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ts = float(r.get("ts") or r.get("created") or 0)
                if now - ts > window_s:
                    continue
                surf = str(r.get("url") or r.get("surface") or r.get("action") or "unknown")
                age = max(1.0, now - ts)
                attention[surf] = attention.get(surf, 0.0) + (1.0 / age)
        except Exception:
            pass
    total = sum(attention.values()) or 1.0
    drift = 0.0
    if mission_target:
        mw = attention.get(mission_target, 0.0)
        drift = 1.0 - (mw / total)
    return {
        "attention": {k: round(v, 4) for k, v in sorted(attention.items(), key=lambda x: -x[1])[:10]},
        "drift_from_mission": round(max(0.0, min(1.0, drift)), 4),
        "mission_target": mission_target,
    }


__all__ = [
    "TRUTH_LABEL",
    "RESULT_TRUTH_LABEL",
    "ROUTE_KILL_TRUTH_LABEL",
    "append_grok_self_type_result",
    "command_path",
    "emit_route_kill_handoff_receipt",
    "extract_grok_ask_payload",
    "extract_grok_continue_context",
    "extract_grok_mission_first_question",
    "wants_answer_grok_in_browser",
    "extract_grok_browser_payload",
    "extract_grok_self_type_payload",
    "grok_send_verdict",
    "stage_grok_self_type_command",
    "wants_enter",
    "would_legacy_mirror_reply_hijack",
    "parse_grok_dialogue_target_rounds",
    "wants_continuous_grok_dialogue",
    "wants_stop_grok_dialogue",
    "split_owner_grok_dialogue_turn",
    "looks_like_grok_continue_context_mission",
    "looks_like_grok_dialogue_continue",
    "grok_dialogue_active",
    "looks_like_grok_mirror_paste",
    "owner_targets_non_grok_browser_chat",
    "owner_turn_blocks_browser_reflex",
]
