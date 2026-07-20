#!/usr/bin/env python3
"""Web AI chat bridge — route queries to web chatbots via Alice Browser.

r1345+: When George names a web chatbot, navigate Alice Browser to that site,
type the query, wait for the AI response, and read it from the DOM.

This organ does NOT execute JavaScript directly — it writes navigation + JS
commands to the browser's drop file and page-state ledgers. The browser widget
picks them up via QFileSystemWatcher.

Truth label: WEB_AI_CHAT_BRIDGE_V1
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "WEB_AI_CHAT_BRIDGE_V1"
SCHEMA = "WEB_AI_CHAT_BRIDGE_ROW_V1"
# Talk widget checks identity — not user-visible prose, not falsy like "".
WEB_AI_CHAT_STAGED_SILENT = object()

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DROP_FILE = _STATE / "alice_browser_open_url.txt"
_JS_DROP_FILE = _STATE / "alice_browser_execute_js.txt"
_PENDING_WEB_AI_FILE = _STATE / "pending_web_ai_chat.json"
_WEB_AI_ANSWER_FILE = _STATE / "web_ai_chat_answer.json"
_PAGE_STATE = _STATE / "browser_page_state.json"
_WEB_AI_DIALOGUE_MISSION_FILE = "web_ai_chat_dialogue_mission.json"

_READ_ANSWER_RE = re.compile(
    r"\b(?:read|get|fetch|tell me|give me)\s+(?:the\s+)?(?:ai\s+)?answer\b",
    re.IGNORECASE,
)
_READ_DUCK_ANSWER_RE = re.compile(
    r"\b(?:read|what did|tell me what)\s+duck\.?ai\s+(?:say|said|answer|respond)\b",
    re.IGNORECASE,
)
_READ_NAMED_AI_ANSWER_RE = re.compile(
    r"\b(?:read|what did|tell me what)\s+"
    r"(?:duck\.?ai|gemini|grok\.com|browser\s+grok|chatgpt(?:\.com)?|chat\.openai\.com)\s+"
    r"(?:say|said|answer|respond)\b",
    re.IGNORECASE,
)

# Proven Alice Browser limb: same composer scoring + verify_probe path as grok.com.
# ChatGPT and siblings must NOT use the thinner pending_web_ai + static JS bridge.
_GROK_LIMB_AI_CHAT_SITES = frozenset(
    {
        "chatgpt.com",
        "grok.com",
        "gemini.google.com",
        "claude.ai",
        "deepai.org",
    }
)

_AI_CHAT_SITES: dict[str, dict[str, str]] = {
    "current.page": {
        "name": "visible page",
        "url": "",
        "input_selector": (
            "textarea, input:not([type]), input[type='text'], input[type='search'], "
            "input[type='email'], input[type='url'], input[type='tel'], input[type='password'], "
            "[contenteditable='true'], [contenteditable]:not([contenteditable='false']), "
            "[role='textbox'], [role='searchbox']"
        ),
        "submit_selector": (
            "button[type='submit'], input[type='submit'], button[aria-label*='Send'], "
            "button[aria-label*='Submit'], button[aria-label*='Search'], button[title*='Send'], "
            "button[title*='Submit'], button[title*='Search'], [role='button'], button, "
            "input[type='button']"
        ),
        "response_selector": "main, body",
        "thinking_indicator": "[data-sifta-never-thinking]",
    },
    "duck.ai": {
        "name": "Duck.ai",
        "url": "https://duck.ai",
        "input_selector": "textarea, input[type='text'], [contenteditable='true'], [role='textbox']",
        "submit_selector": "button[type='submit'], button[aria-label*='Send'], button[aria-label*='submit'], button",
        "response_selector": "[data-testid='chat-turn'], [data-testid*='message'], [data-testid*='response'], .response-message, .markdown-body, [class*='markdown'], article",
        "thinking_indicator": ".loading, .thinking, [data-testid='loading'], .animate-pulse",
    },
    "gemini.google.com": {
        "name": "Gemini",
        "url": "https://gemini.google.com",
        "input_selector": "textarea, [contenteditable='true'], [role='textbox']",
        "submit_selector": "button[aria-label*='Send'], button[aria-label*='submit']",
        "response_selector": ".response-container, .model-response, message-content",
        "thinking_indicator": ".loading, .thinking, .animate-pulse",
    },
    "grok.com": {
        "name": "Grok.com",
        "url": "https://grok.com/",
        "input_selector": "textarea, [contenteditable='true'], [role='textbox'], div[aria-label*='Ask'], div[aria-label*='Message']",
        "submit_selector": "button[type='submit'], button[aria-label*='Send'], button[aria-label*='Submit'], button[aria-label*='send'], button[data-testid*='send'], button",
        "response_selector": "[data-testid*='message'], [class*='message'], [class*='markdown'], article, main div",
        "thinking_indicator": "[data-testid*='thinking'], [class*='thinking'], [class*='loading'], .animate-pulse",
    },
    "chatgpt.com": {
        "name": "ChatGPT",
        "url": "https://chatgpt.com/",
        "input_selector": "textarea, #prompt-textarea, [contenteditable='true'], [role='textbox']",
        "submit_selector": "button[data-testid='send-button'], button[aria-label*='Send'], button[type='submit'], button",
        "response_selector": "[data-message-author-role='assistant'], [data-testid*='conversation-turn'], .markdown, article",
        "thinking_indicator": "[data-testid*='stop-button'], [aria-label*='Stop'], [class*='result-streaming'], .animate-pulse",
    },
}

_SEARCH_ON_WEB_AI_RE = re.compile(
    r"\b(?:search|look\s+up|find|ask)\s+(?:for\s+)?(?P<query>.+?)\s+on\s+(?P<site>duck\.?ai|gemini|grok\.com|chatgpt(?:\.com)?|chat\.openai\.com)\b",
    re.IGNORECASE,
)
_SEARCH_ON_WEB_AI_PLS_RE = re.compile(
    r"\bSEARCH\s+ON\s+(?P<site>DUCK\.?AI|GEMINI|GROK\.COM|CHATGPT(?:\.COM)?|CHAT\.OPENAI\.COM)\s+PLS\b\s*(?P<query>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_DUCK_AI_QUERY_RE = re.compile(
    r"\b(?:ask|chat\s+with|use)\s+duck\.?ai\b",
    re.IGNORECASE,
)
_SEARCH_ON_DUCK_AI_RE = re.compile(
    r"\b(?:search|look\s+up|find)\s+(?:for\s+)?(?P<query>.+?)\s+on\s+duck\.?ai\b",
    re.IGNORECASE,
)
_SEARCH_ON_DUCK_AI_PLS_RE = re.compile(
    r"\bSEARCH\s+ON\s+DUCK\.?AI\s+PLS\b\s*(?P<query>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_GEMINI_QUERY_RE = re.compile(
    r"\b(?:ask|chat\s+with|use)\s+gemini\b",
    re.IGNORECASE,
)
_CHATGPT_QUERY_RE = re.compile(
    r"\b(?:ask|chat\s+with|use)\s+(?:chatgpt|chatgpt\.com|chat\.openai\.com)\b",
    re.IGNORECASE,
)
_OPEN_AI_CHAT_SITE_AND_QUERY_RE = re.compile(
    r"\b(?:open|go\s+to|visit|load|navigate\s+to)\s+"
    r"(?P<site>duck\.?ai|gemini(?:\.google\.com)?|grok\.com|chatgpt(?:\.com)?|chat\.openai\.com)\b"
    r"(?:\s*(?:and|then|,|-+)?\s*)?"
    r"(?:ask|type|write|say|send|tell)\b\s*"
    r"(?P<query>.+?)"
    r"(?:\s*(?:,\s*)?(?:and\s+)?then\s+"
    r"(?:push|press|click|hit|tap)\s+(?:the\s+)?(?:button|send\b).*)?$",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_CHAT_BOX_SEND_RE = re.compile(
    r"\b(?:type|write|enter|put|paste)\s+"
    r"(?:in\s+)?(?:the\s+)?(?:box|composer|chat\s*box|chatbox|prompt|text\s*box|input)\b"
    r"\s*(?P<query>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_AI_TYPE_SEND_RE = re.compile(
    r"\b(?:try\s+again\s+)?(?:typ|type|write|enter|put|paste)\b"
    r"[\s,:;-]*(?P<query>.+?)"
    r"\s+(?:and\s+)?(?:click|hit|press|tap)?\s*"
    r"(?:send|senfd|snd|sendd|sent|submit)(?:\s+button)?\b",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_AI_SUBMIT_ONLY_RE = re.compile(
    r"\b(?:you\s+have\s+to\s+|now\s+|just\s+)?"
    r"(?:click|hit|press|tap|push)\s+(?:the\s+)?"
    r"(?:white\s+)?(?:send|submit|arrow|button)"
    r"(?:\s+(?:button|arrow))?\b"
    r"|\b(?:click|hit|press|tap|push)\s+(?:the\s+)?(?:send|submit)\b"
    r"|\b(?:send|submit)\s+(?:it|this|the\s+message|the\s+prompt)\b",
    re.IGNORECASE | re.DOTALL,
)
_SEND_INTENT_TYPO_LABELS = frozenset(
    {"send", "senfd", "snd", "sendd", "sent", "submit", "senv", "sned"}
)
_CHAT_ROUNDS_ON_SITE_RE = re.compile(
    r"\b(?:chat|talk|converse)(?:\s+with)?\s+"
    r"(?P<rounds>\d{1,2})\s*(?:round|turn|loop)s?\s+"
    r"(?:on|with|in|at)\s+"
    r"(?P<site>chatgpt(?:\.com)?|chat\.openai\.com|grok(?:\.com)?|deepai(?:\.org)?|"
    r"claude\.ai|gemini(?:\.google\.com)?|duck\.?ai)\b"
    r"(?:\s+about\s+(?P<topic>.+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_OPEN_AI_CHAT_SITE_AND_ROUNDS_RE = re.compile(
    r"\b(?:open|go\s+to|visit|load|navigate\s+to)\s+"
    r"(?P<site>chatgpt(?:\.com)?|chat\.openai\.com|grok(?:\.com)?|deepai(?:\.org)?|"
    r"claude\.ai|gemini(?:\.google\.com)?|duck\.?ai)\b"
    r"(?:\s*(?:and|then|,|-+)?\s*)?"
    r"(?:chat|talk|converse)(?:\s+with\s+(?:it|them|the\s+ai|the\s+chatbot))?\s+"
    r"(?P<rounds>\d{1,2})\s*(?:round|turn|loop)s?"
    r"(?:\s+about\s+(?P<topic>.+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_GROK_DOTCOM_QUERY_RE = re.compile(
    r"\b(?:ask|chat\s+with|use)\s+(?:grok\.com|browser\s+grok|grok\s+in\s+(?:alice\s+)?browser|alice\s+browser\s+grok)\b",
    re.IGNORECASE,
)
_ANAPHORIC_QUERY_RE = re.compile(
    r"\b(?:this|that)\s+(?:recipe|recepi|recepie|dish|meal|food)\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def resolve_anaphoric_ai_query(
    query: str,
    *,
    history: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Turn 'this recipe' into the latest grounded cooking subject from history."""
    q = " ".join(str(query or "").strip().split())
    if not q or not _ANAPHORIC_QUERY_RE.search(q):
        return q
    cooking_bits: list[str] = []
    for msg in reversed(history or []):
        if str(msg.get("role") or "") != "user":
            continue
        content = " ".join(str(msg.get("content") or "").split())
        if not content or len(content) < 12:
            continue
        if re.search(
            r"\b(?:polenta|recipe|recepi|recepie|cooking|eggs?|butter|cheese|garlic|boiled|sauté|saute|cream\s+cheese|smash)\b",
            content,
            re.IGNORECASE,
        ):
            cooking_bits.append(content[:500])
            if len(cooking_bits) >= 2:
                break
    if cooking_bits:
        merged = " ".join(reversed(cooking_bits))
        if re.search(r"\b(?:polenta|eggs?|butter|cheese)\b", merged, re.IGNORECASE):
            return (
                "Recipe search: polenta with hard-boiled eggs smashed with butter "
                f"and cream cheese/cheese, hot polenta poured over the egg-butter mix. "
                f"Owner context: {merged[:420]}"
            )
        return merged[:500]
    return q.replace("this ", "").replace("that ", "").strip() or q


def canonical_ai_chat_site(site_text: str) -> str:
    """Map spoken/written site names to the bridge's site profile keys."""
    s = re.sub(r"\s+", " ", str(site_text or "").strip().lower())
    s = s.replace("duck ai", "duck.ai").replace("duck.ai.", "duck.ai")
    if s in {"duck", "duck.ai"}:
        return "duck.ai"
    if "gemini" in s:
        return "gemini.google.com"
    if "chatgpt" in s or "chat.openai.com" in s:
        return "chatgpt.com"
    if (
        "grok.com" in s
        or "browser grok" in s
        or "alice browser grok" in s
        or "grok in browser" in s
        or "grok in alice browser" in s
    ):
        return "grok.com"
    return s


def ai_chat_site_from_url(url: str) -> str:
    """Return the bridge site key for a live browser URL, if it is a known web-AI site."""
    host = _host_from_url(url)
    if not host:
        return ""
    if host == "duck.ai" or host.endswith(".duck.ai"):
        return "duck.ai"
    if host == "gemini.google.com" or host.endswith(".gemini.google.com"):
        return "gemini.google.com"
    if host == "chatgpt.com" or host.endswith(".chatgpt.com") or host == "chat.openai.com":
        return "chatgpt.com"
    if host == "grok.com" or host.endswith(".grok.com"):
        return "grok.com"
    return ""


def current_page_site_from_url(url: str) -> str:
    """Known AI-chat site when available; otherwise generic current-page form hand."""
    known = ai_chat_site_from_url(url)
    if known:
        return known
    host = _host_from_url(url)
    if host and str(url or "").lower().startswith(("http://", "https://")):
        return "current.page"
    return ""


def latest_ai_chat_context(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Read the freshest known Alice Browser URL and map it to a web-AI site.

    This lets owner corrections like "now type in the box hello and hit send"
    use the already visible ChatGPT/Grok composer instead of falling into a
    Talk-window reply.
    """
    sd = _state_dir(state_dir)
    candidates: list[dict[str, Any]] = []
    try:
        from System.swarm_browser_page_state import latest_page_state

        state = latest_page_state(state_dir=sd, max_age_s=3600.0)
        if isinstance(state, dict):
            candidates.append(state)
    except Exception:
        pass
    for name in (
        "alice_browser_current_page.json",
        "browser_page_state_latest.json",
        "browser_page_state.json",
    ):
        try:
            state = json.loads((sd / name).read_text(encoding="utf-8"))
            if isinstance(state, dict):
                state = dict(state)
                state["_source_file"] = name
                candidates.append(state)
        except Exception:
            pass
    candidates.sort(key=lambda row: float(row.get("ts") or 0.0), reverse=True)
    for row in candidates:
        url = str(row.get("url") or row.get("current_url") or "").strip()
        site = current_page_site_from_url(url)
        if site:
            return {
                "site": site,
                "name": _AI_CHAT_SITES.get(site, {}).get("name", site),
                "url": url,
                "source": row.get("_source_file") or row.get("source") or "browser_page_state",
                "ts": row.get("ts"),
            }
    return {}


def _strip_trailing_browser_ui_instructions(query: str) -> str:
    """Remove owner send/UI tail from the actual chatbot question."""
    q = str(query or "")
    patterns = (
        # "... ask what is URL/? then push the button near the text box to send it"
        r"\s*(?:,\s*)?(?:and\s+)?then\s+"
        r"(?:(?:push|press|click|hit|tap)\s+(?:the\s+)?(?:button|send\b)[^?]*"
        r"|(?:push|press|click|hit|tap)\s+send\b[^?]*)"
        r".*$",
        # "... ask URL push the button after you type"
        r"\s*(?:and\s+)?(?:push|press|click|hit|tap)\s+(?:the\s+)?(?:button|send\b)[^?]*(?:to\s+send(?:\s+it)?)?\s*$",
        # trailing "and hit send" / "press send button"
        r"\s+(?:and\s+)?(?:hit|press|click|tap)?\s*(?:the\s+)?"
        r"(?:send|senfd|snd|sendd|sent)(?:\s+button)?\s*$",
        r"\s+(?:and\s+)?(?:submit|send\s+it)(?:\s+please|\s+pls)?\s*$",
    )
    for pat in patterns:
        q = re.sub(pat, " ", q, flags=re.IGNORECASE | re.DOTALL)
    return q


def _clean_ai_chat_query(query: str, *, history: Optional[list[dict[str, Any]]] = None) -> str:
    q = resolve_anaphoric_ai_query(query, history=history)
    q = _strip_trailing_browser_ui_instructions(q)
    q = re.sub(r"\b(?:please|pls|plz|now|just)\b", " ", q, flags=re.IGNORECASE)
    return " ".join(q.strip(" \t\r\n\"'`?!.,").split())


def _clean_one_line(text: str, *, limit: int = 4000) -> str:
    return " ".join(str(text or "").strip().split())[:limit]


def web_ai_dialogue_mission_path(*, state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / _WEB_AI_DIALOGUE_MISSION_FILE


def read_web_ai_dialogue_mission(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    path = web_ai_dialogue_mission_path(state_dir=state_dir)
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


def write_web_ai_dialogue_mission(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> bool:
    path = web_ai_dialogue_mission_path(state_dir=state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def start_web_ai_dialogue_mission(
    *,
    site: str,
    url: str,
    opening_query: str,
    target_rounds: int,
    topic: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Persist the live same-conversation mission for ChatGPT-style sites."""
    rounds = max(1, min(30, int(target_rounds or 1)))
    row = {
        "schema": "WEB_AI_CHAT_DIALOGUE_MISSION_V1",
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "mission_id": f"web-ai-dialogue-{uuid.uuid4().hex[:12]}",
        "status": "active",
        "site": site,
        "name": _AI_CHAT_SITES.get(site, {}).get("name", site),
        "url": url,
        "opening_query": _clean_one_line(opening_query, limit=1200),
        "target_rounds": rounds,
        "topic": _clean_one_line(topic, limit=500),
        "answer_turns": 0,
        "alice_browser_sends": 0,
    }
    write_web_ai_dialogue_mission(row, state_dir=state_dir)
    append_web_ai_bridge_row(
        {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "ts": time.time(),
            "site": site,
            "query": opening_query,
            "url": url,
            "phase": "dialogue_mission_started",
            "mission_id": row["mission_id"],
            "target_rounds": rounds,
            "topic": row.get("topic") or "",
        },
        state_dir=state_dir,
    )
    return row


def looks_like_web_ai_type_send_command(text: str) -> bool:
    """True when owner means type-into-box + send — not click a literal 'senfd' button."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_CURRENT_AI_TYPE_SEND_RE.search(t) or _CURRENT_CHAT_BOX_SEND_RE.search(t))


def looks_like_web_ai_submit_command(text: str) -> bool:
    """True when owner means submit the already-filled visible web-chat composer."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_CURRENT_AI_SUBMIT_ONLY_RE.search(t))


def is_send_intent_typo_label(label: str) -> bool:
    """STT typos for send must route to the generic form hand, not click_element."""
    return str(label or "").strip().lower() in _SEND_INTENT_TYPO_LABELS


def _opening_query_for_chat_rounds(*, topic: str, rounds: int, site_name: str) -> str:
    subject = " ".join((topic or "this topic").strip().split())[:180]
    return (
        f"Hi, I am Alice. Let's have a {rounds}-round conversation about {subject}. "
        "Round 1: reply briefly, then ask me one question."
    )[:360]


def detect_ai_chat_request(
    text: str,
    *,
    history: Optional[list[dict[str, Any]]] = None,
    current_url: str = "",
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Detect requests for web chatbots opened inside Alice Browser."""
    t = (text or "").strip()
    if not t:
        return None

    if not str(current_url or "").strip():
        ctx = latest_ai_chat_context(state_dir=state_dir)
        current_url = str(ctx.get("url") or "")

    m = _OPEN_AI_CHAT_SITE_AND_ROUNDS_RE.search(t) or _CHAT_ROUNDS_ON_SITE_RE.search(t)
    if m:
        site = canonical_ai_chat_site(m.group("site"))
        topic = _clean_ai_chat_query(str(m.group("topic") or "this topic"), history=history)
        rounds = max(1, min(30, int(m.group("rounds"))))
        site_name = _AI_CHAT_SITES.get(site, {}).get("name", site)
        if site in _AI_CHAT_SITES:
            opening = _opening_query_for_chat_rounds(topic=topic, rounds=rounds, site_name=site_name)
            use_current = bool(ai_chat_site_from_url(current_url) == site or current_page_site_from_url(current_url) == site)
            row: dict[str, Any] = {
                "site": site,
                "query": opening,
                "name": site_name,
                "route": "web_ai_chat",
                "target_rounds": rounds,
                "topic": topic,
            }
            if use_current:
                row["use_current_page"] = True
                row["current_url"] = current_url
            return row

    m = _OPEN_AI_CHAT_SITE_AND_QUERY_RE.search(t)
    if m:
        site = canonical_ai_chat_site(m.group("site"))
        query = _clean_ai_chat_query(m.group("query"), history=history)
        site_name = _AI_CHAT_SITES.get(site, {}).get("name", site)
        if query and site in _AI_CHAT_SITES:
            return {"site": site, "query": query, "name": site_name, "route": "web_ai_chat"}

    current_site = current_page_site_from_url(current_url)
    m = _CURRENT_CHAT_BOX_SEND_RE.search(t)
    if m and current_site:
        query = _clean_ai_chat_query(m.group("query"), history=history)
        site_name = _AI_CHAT_SITES.get(current_site, {}).get("name", current_site)
        if query:
            return {
                "site": current_site,
                "query": query,
                "name": site_name,
                "route": "web_ai_chat",
                "use_current_page": True,
                "current_url": current_url,
            }

    m = _CURRENT_AI_TYPE_SEND_RE.search(t)
    if m and current_site:
        query = _clean_ai_chat_query(m.group("query"), history=history)
        site_name = _AI_CHAT_SITES.get(current_site, {}).get("name", current_site)
        if query:
            return {
                "site": current_site,
                "query": query,
                "name": site_name,
                "route": "web_ai_chat",
                "use_current_page": True,
                "current_url": current_url,
            }

    m = _SEARCH_ON_WEB_AI_PLS_RE.search(t)
    if m:
        site = canonical_ai_chat_site(m.group("site"))
        query = _clean_ai_chat_query(m.group("query"), history=history)
        site_name = _AI_CHAT_SITES.get(site, {}).get("name", site)
        if query and site in _AI_CHAT_SITES:
            return {"site": site, "query": query, "name": site_name, "route": "web_ai_chat"}

    m = _SEARCH_ON_WEB_AI_RE.search(t)
    if m:
        site = canonical_ai_chat_site(m.group("site"))
        query = _clean_ai_chat_query(m.group("query"), history=history)
        site_name = _AI_CHAT_SITES.get(site, {}).get("name", site)
        if query and site in _AI_CHAT_SITES:
            return {"site": site, "query": query, "name": site_name, "route": "web_ai_chat"}

    m = _SEARCH_ON_DUCK_AI_PLS_RE.search(t)
    if m:
        query = _clean_ai_chat_query(m.group("query"), history=history)
        if query:
            return {"site": "duck.ai", "query": query, "name": "Duck.ai", "route": "web_ai_chat"}

    m = _SEARCH_ON_DUCK_AI_RE.search(t)
    if m:
        query = _clean_ai_chat_query(m.group("query"), history=history)
        if query:
            return {"site": "duck.ai", "query": query, "name": "Duck.ai"}

    m = _DUCK_AI_QUERY_RE.search(t)
    if m:
        after = _clean_ai_chat_query(t[m.end():], history=history)
        if after:
            return {"site": "duck.ai", "query": after, "name": "Duck.ai"}

    m = _GEMINI_QUERY_RE.search(t)
    if m:
        after = _clean_ai_chat_query(t[m.end():], history=history)
        if after:
            return {"site": "gemini.google.com", "query": after, "name": "Gemini"}

    m = _CHATGPT_QUERY_RE.search(t)
    if m:
        after = _clean_ai_chat_query(t[m.end():], history=history)
        if after:
            return {"site": "chatgpt.com", "query": after, "name": "ChatGPT", "route": "web_ai_chat"}

    m = _GROK_DOTCOM_QUERY_RE.search(t)
    if m:
        after = _clean_ai_chat_query(t[m.end():], history=history)
        if after:
            return {"site": "grok.com", "query": after, "name": "Grok.com", "route": "web_ai_chat"}

    return None


def detect_ai_chat_submit_request(
    text: str,
    *,
    current_url: str = "",
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Detect "click send" on the currently visible AI chat page."""
    if not looks_like_web_ai_submit_command(text):
        return None
    if not str(current_url or "").strip():
        ctx = latest_ai_chat_context(state_dir=state_dir)
        current_url = str(ctx.get("url") or "")
    site = current_page_site_from_url(current_url)
    if not site:
        return None
    site_name = _AI_CHAT_SITES.get(site, {}).get("name", site)
    return {
        "site": site,
        "name": site_name,
        "route": "web_ai_submit_current",
        "use_current_page": True,
        "current_url": current_url,
    }


def build_ai_chat_url(site: str, query: str) -> str:
    """Build the URL for an AI chat site with the query."""
    site_config = _AI_CHAT_SITES.get(site)
    if not site_config:
        return ""
    base = site_config["url"]
    if site == "duck.ai":
        return base
    # Gemini uses URL params
    if site == "gemini.google.com":
        return f"{base}?q={query.replace(' ', '+')}"
    if site in {"grok.com", "chatgpt.com"}:
        return base
    return base


def write_browser_navigate(url: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """Write a URL to the browser drop file for navigation."""
    sd = _state_dir(state_dir)
    drop = sd / "alice_browser_open_url.txt"
    try:
        drop.parent.mkdir(parents=True, exist_ok=True)
        drop.write_text(url, encoding="utf-8")
        return True
    except Exception:
        return False


def write_browser_js(js_code: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """Write JavaScript to execute in the browser (picked up by awareness tick)."""
    sd = _state_dir(state_dir)
    js_drop = sd / "alice_browser_execute_js.txt"
    try:
        js_drop.parent.mkdir(parents=True, exist_ok=True)
        js_drop.write_text(js_code, encoding="utf-8")
        return True
    except Exception:
        return False


def _host_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def pending_host_matches_url(pending_host: str, url: str) -> bool:
    """True when the live browser URL is on the parked web-AI host."""
    host = _host_from_url(url).replace("www.", "")
    raw_ph = str(pending_host or "").strip().lower()
    ph = (_host_from_url(raw_ph) or raw_ph).replace("www.", "")
    if not ph:
        return bool(host)
    if not host:
        return False
    if ph in host or host in ph:
        return True
    site = ai_chat_site_from_url(f"https://{host}/")
    pending_site = ai_chat_site_from_url(f"https://{ph}/") if "." in ph else ph
    return bool(site and pending_site and site == pending_site)


def stage_pending_web_ai_chat(
    *,
    site: str,
    query: str,
    url: str,
    state_dir: Optional[Path | str] = None,
    ttl_s: float = 120.0,
    phase: str = "await_load",
    target_rounds: int = 0,
    topic: str = "",
) -> dict[str, Any]:
    """Park a web-AI chat request until the browser finishes loading the target host."""
    sd = _state_dir(state_dir)
    effective_ttl = float(ttl_s)
    if int(target_rounds or 0) > 1:
        effective_ttl = max(effective_ttl, 900.0)
    elif effective_ttl < 300.0:
        effective_ttl = 300.0
    row = {
        "schema": "PENDING_WEB_AI_CHAT_V1",
        "truth_label": TRUTH_LABEL,
        "site": site,
        "query": query,
        "url": url,
        "host": _host_from_url(url) or site,
        "type_js": build_type_and_submit_js(query, site),
        "read_js": build_read_response_js(site, query=query),
        "ts": time.time(),
        "ttl_s": effective_ttl,
        "phase": phase or "await_load",
    }
    if int(target_rounds or 0) > 0:
        row["target_rounds"] = int(target_rounds)
    if str(topic or "").strip():
        row["topic"] = str(topic).strip()[:500]
    try:
        pending = sd / "pending_web_ai_chat.json"
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        return {"ok": False, "reason": "pending_write_failed", **row}
    return {"ok": True, **row}


def stage_pending_web_ai_submit(
    *,
    site: str,
    url: str,
    state_dir: Optional[Path | str] = None,
    ttl_s: float = 300.0,
) -> dict[str, Any]:
    """Park a submit-only request for the currently filled web-AI composer."""
    sd = _state_dir(state_dir)
    row = {
        "schema": "PENDING_WEB_AI_CHAT_V1",
        "truth_label": TRUTH_LABEL,
        "site": site,
        "query": "",
        "url": url,
        "host": _host_from_url(url) or site,
        "type_js": build_click_submit_js(site),
        "read_js": build_read_response_js(site, query=""),
        "ts": time.time(),
        "ttl_s": max(120.0, float(ttl_s)),
        "phase": "await_load",
        "submit_only": True,
    }
    try:
        pending = sd / "pending_web_ai_chat.json"
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        return {"ok": False, "reason": "pending_write_failed", **row}
    return {"ok": True, **row}


def read_pending_web_ai_chat(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    sd = _state_dir(state_dir)
    pending = sd / "pending_web_ai_chat.json"
    try:
        row = json.loads(pending.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    if not isinstance(row, dict):
        return {}
    if (time.time() - float(row.get("ts", 0))) > float(row.get("ttl_s", 120.0)):
        clear_pending_web_ai_chat(state_dir=sd)
        return {}
    return row


def clear_pending_web_ai_chat(*, state_dir: Optional[Path | str] = None) -> None:
    sd = _state_dir(state_dir)
    try:
        (sd / "pending_web_ai_chat.json").unlink()
    except FileNotFoundError:
        return
    except Exception:
        return


def mark_pending_web_ai_phase(
    phase: str,
    *,
    state_dir: Optional[Path | str] = None,
    **updates: Any,
) -> None:
    sd = _state_dir(state_dir)
    row = read_pending_web_ai_chat(state_dir=sd)
    if not row:
        return
    row["phase"] = phase
    row["phase_ts"] = time.time()
    row.update(updates)
    try:
        pending = sd / "pending_web_ai_chat.json"
        pending.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        return


def write_web_ai_answer_receipt(
    payload: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
) -> bool:
    sd = _state_dir(state_dir)
    answer_file = sd / "web_ai_chat_answer.json"
    row = {
        "schema": "WEB_AI_CHAT_ANSWER_V1",
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        **payload,
    }
    try:
        answer_file.parent.mkdir(parents=True, exist_ok=True)
        answer_file.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return True
    except Exception:
        return False


def read_web_ai_answer_receipt(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    sd = _state_dir(state_dir)
    answer_file = sd / "web_ai_chat_answer.json"
    try:
        row = json.loads(answer_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


def clear_web_ai_answer_receipt(*, state_dir: Optional[Path | str] = None) -> None:
    sd = _state_dir(state_dir)
    try:
        (sd / "web_ai_chat_answer.json").unlink()
    except FileNotFoundError:
        return
    except Exception:
        return


def append_web_ai_bridge_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> bool:
    sd = _state_dir(state_dir)
    ledger = sd / "web_ai_chat_bridge.jsonl"
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return True
    except Exception:
        return False


_WEB_AI_STAGING_PROSE_RE = re.compile(
    r"(?:"
    r"\bopening\s+chatgpt\s+in\s+alice\s+browser\b|"
    r"\bstaged\s+alice\s+browser\b|"
    r"\bthen\s+type\+send\b|"
    r"\btyped_submitted\s+lands\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_WEB_AI_TYPED_CLAIM_RE = re.compile(
    r"(?:"
    r"\btyping\s+sequence\s+verified\b|"
    r"\bround\s+\d+\s+(?:completed?|done|finished|sent|officially\s+commenced)\b|"
    r"\bsuccessfully\s+completed\b[^.\n]{0,60}\bround\s+\d+\b|"
    r"\bwas\s+typed\s+into\s+the\s+active\s+text\s+box\b|"
    r"\bclicking\s+['\"]send['\"]\b|"
    r"\bgpt\s+responded\s+immediately\b|"
    r"\b(?:i(?:'ve|\s+have)?|successfully)\s+(?:typed|sent|submitted)\b[^.\n]{0,80}\b(?:message|query|prompt|box|chatgpt|grok|duck)\b|"
    r"\b(?:message|query|prompt)\s+(?:was\s+)?(?:sent|submitted|typed)\b|"
    r"\bhit\s+send\b[^.\n]{0,40}\b(?:success|complete|done)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)


def has_web_ai_typed_submitted_receipt(
    *,
    site: str = "",
    query: str = "",
    state_dir: Optional[Path | str] = None,
    max_age_s: float = 900.0,
) -> bool:
    """True when the bridge ledger has a successful typed_submitted row."""
    sd = _state_dir(state_dir)
    ledger = sd / "web_ai_chat_bridge.jsonl"
    if not ledger.exists():
        return False
    cutoff = time.time() - float(max_age_s)
    site_key = str(site or "").strip().lower()
    query_norm = " ".join(str(query or "").strip().split()).lower()
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False
    for line in reversed(lines[-200:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("phase") or "") != "typed_submitted":
            continue
        if float(row.get("ts") or 0) < cutoff:
            continue
        if site_key and str(row.get("site") or "").strip().lower() != site_key:
            continue
        if query_norm:
            row_query = " ".join(str(row.get("query") or "").strip().split()).lower()
            if row_query and row_query != query_norm and query_norm not in row_query:
                continue
        type_result = row.get("type_result") if isinstance(row.get("type_result"), dict) else {}
        if type_result and type_result.get("ok") is False:
            continue
        return True
    return False


def web_ai_type_send_fiction_guard_reply(
    user_text: str,
    brain_text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Block cortex claims of typing/sending on web-AI sites without bridge receipts."""
    if not user_text or not brain_text:
        return ""
    if not (_WEB_AI_TYPED_CLAIM_RE.search(brain_text) or _WEB_AI_STAGING_PROSE_RE.search(brain_text)):
        return ""
    sd = _state_dir(state_dir)
    pending = read_pending_web_ai_chat(state_dir=sd)
    site = str(pending.get("site") or "").strip()
    query = str(pending.get("query") or "").strip()
    if not site:
        request = detect_ai_chat_request(user_text, state_dir=sd)
        if request:
            site = str(request.get("site") or "")
            query = str(request.get("query") or "")
    if not site:
        if re.search(r"\b(?:chatgpt|gpt)\b", brain_text, re.IGNORECASE):
            site = "chatgpt.com"
        elif re.search(r"\bgrok\.com\b", brain_text, re.IGNORECASE):
            site = "grok.com"
    if not site and not re.search(
        r"\b(?:chatgpt|grok\.com|duck\.?ai|gemini|deepai|type\s+in\s+the\s+box|hit\s+send|chat\s+\d+\s+rounds?|open\s+chatgpt)\b",
        user_text,
        re.IGNORECASE,
    ) and not re.search(
        r"\b(?:chatgpt|grok\.com|gpt\b|round\s+\d+\b.*\b(?:completed?|commenced))\b",
        brain_text,
        re.IGNORECASE,
    ):
        return ""
    if has_web_ai_typed_submitted_receipt(site=site, query=query, state_dir=sd):
        return ""
    site_name = _AI_CHAT_SITES.get(site, {}).get("name", site or "the web chat")
    if pending and str(pending.get("phase") or "") in {"await_load", "typing_started"}:
        return (
            f"Bad action receipt: {site_name} type/send is staged, but "
            "web_ai_chat_bridge.jsonl has no typed_submitted row yet. "
            "Watch Alice Browser for the visible composer and typed_submitted receipt."
        )
    if query:
        return (
            f"Bad action receipt: no typed_submitted row yet for {site_name} on "
            f"\"{query[:120]}\". Use the read command only after the answer lands."
        )
    return (
        f"Bad action receipt: no typed_submitted row yet for {site_name} in "
        "web_ai_chat_bridge.jsonl."
    )


def _build_chatgpt_type_and_submit_js(query: str) -> str:
    """ChatGPT ProseMirror composer needs dedicated fill + send-button handling."""
    query_js = json.dumps(query, ensure_ascii=False)
    return f"""
(function() {{
    try {{
        var query = {query_js};
        function visible(el) {{
            if (!el) return false;
            var style = window.getComputedStyle(el);
            if (style && (style.display === 'none' || style.visibility === 'hidden')) return false;
            return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        }}
        function fieldText(el) {{
            if (!el) return '';
            if ('value' in el) return String(el.value || '');
            return String(el.innerText || el.textContent || '');
        }}
        function setEditableText(el, text) {{
            el.focus();
            el.click();
            var notes = [];
            try {{
                if (window.getSelection && document.createRange) {{
                    var range = document.createRange();
                    range.selectNodeContents(el);
                    var sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }}
            }} catch (_) {{}}
            try {{
                if (document.execCommand('insertText', false, text)) notes.push('execCommand');
            }} catch (_) {{}}
            if (!fieldText(el).trim()) {{
                try {{
                    if (typeof el.setRangeText === 'function') {{
                        el.setRangeText(text);
                        notes.push('setRangeText');
                    }}
                }} catch (_) {{}}
            }}
            if (!fieldText(el).trim()) el.textContent = text;
            el.dispatchEvent(new InputEvent('beforeinput', {{bubbles: true, cancelable: true, inputType: 'insertText', data: text}}));
            el.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: text}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
            return notes;
        }}
        function setTextareaValue(el, text) {{
            var proto = window.HTMLTextAreaElement.prototype;
            var setter = Object.getOwnPropertyDescriptor(proto, 'value');
            if (setter && setter.set) setter.set.call(el, text);
            else el.value = text;
            el.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: text}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
        var input = document.querySelector('#prompt-textarea')
            || document.querySelector('div#prompt-textarea[contenteditable="true"]')
            || document.querySelector('[data-testid="composer-text-input"]')
            || null;
        if (input && !visible(input)) input = null;
        if (!input) {{
            var candidates = Array.prototype.slice.call(
                document.querySelectorAll('textarea, [contenteditable="true"], [role="textbox"]')
            ).filter(function(el) {{ return visible(el) && !el.disabled && !el.readOnly; }});
            input = candidates[0] || null;
        }}
        if (!input) return {{ok: false, reason: 'chatgpt_input_not_found', url: location.href}};

        var notes = [];
        if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
            setTextareaValue(input, query);
            notes.push('textarea_proto_set');
        }} else {{
            notes = setEditableText(input, query);
        }}
        var hidden = document.querySelector('textarea[name="prompt-textarea"], textarea[data-id="root"]');
        if (hidden && hidden !== input) {{
            try {{ setTextareaValue(hidden, query); notes.push('hidden_textarea'); }} catch (_) {{}}
        }}

        var typed = fieldText(input).trim();
        if (!typed && hidden) typed = fieldText(hidden).trim();
        if (!typed) return {{ok: false, reason: 'chatgpt_input_empty_after_set', inputTag: input.tagName, notes: notes}};

        function rectObj(el) {{
            var r = el.getBoundingClientRect();
            return {{x:r.x, y:r.y, w:r.width, h:r.height, left:r.left, right:r.right, top:r.top, bottom:r.bottom}};
        }}
        function buttonLabel(btn) {{
            return (
                (btn.innerText || btn.textContent || '') + ' ' +
                (btn.getAttribute('aria-label') || '') + ' ' +
                (btn.getAttribute('title') || '') + ' ' +
                (btn.getAttribute('data-testid') || '') + ' ' +
                (btn.getAttribute('type') || '') + ' ' +
                (btn.className || '')
            ).trim();
        }}
        function buttonScore(btn) {{
            if (!visible(btn) || btn.disabled || btn.getAttribute('aria-disabled') === 'true') return -9999;
            var label = buttonLabel(btn).toLowerCase();
            var score = 0;
            if (/send|submit|arrow-up|composer-submit|send-button/.test(label)) score += 90;
            if (btn.getAttribute('type') === 'submit') score += 30;
            if (btn.querySelector && btn.querySelector('svg')) score += 8;
            try {{
                var ir = input.getBoundingClientRect();
                var br = btn.getBoundingClientRect();
                var cy = br.top + br.height / 2;
                var icy = ir.top + ir.height / 2;
                if (br.left >= ir.left - 20) score += 20;
                if (br.left >= ir.right - 190) score += 40;
                if (Math.abs(cy - icy) < 90) score += 30;
                score -= Math.abs(cy - icy) / 6;
            }} catch (_) {{}}
            if (/attach|file|upload|microphone|mic|voice|dictation|sidebar|search|new chat|library|project|settings|model|instant/.test(label)) score -= 180;
            return score;
        }}
        var buttons = Array.prototype.slice.call(document.querySelectorAll(
            "button[data-testid='send-button'], button[data-testid*='send'], button[aria-label*='Send'], button[aria-label*='Submit'], button[type='submit'], button"
        )).filter(visible).map(function(btn) {{
            return {{btn: btn, score: buttonScore(btn), label: buttonLabel(btn), rect: rectObj(btn)}};
        }}).sort(function(a, b) {{ return b.score - a.score; }});
        var best = buttons[0] || null;
        if (best && best.score > 20) {{
            best.btn.dispatchEvent(new MouseEvent('pointerdown', {{bubbles:true, cancelable:true}}));
            best.btn.dispatchEvent(new MouseEvent('mousedown', {{bubbles:true, cancelable:true}}));
            best.btn.dispatchEvent(new MouseEvent('mouseup', {{bubbles:true, cancelable:true}}));
            best.btn.click();
            return {{
                ok: true,
                method: 'chatgpt_click_send_button',
                inputTag: input.tagName,
                query: typed,
                typed_len: typed.length,
                buttonLabel: best.label.slice(0, 120),
                buttonScore: best.score,
                buttonRect: best.rect,
                inputRect: rectObj(input),
                notes: notes
            }};
        }}
        input.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
        input.dispatchEvent(new KeyboardEvent('keypress', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
        input.dispatchEvent(new KeyboardEvent('keyup', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
        return {{
            ok: false,
            reason: 'chatgpt_send_button_not_found_or_disabled',
            enter_dispatched: true,
            inputTag: input.tagName,
            query: typed,
            typed_len: typed.length,
            notes: notes,
            candidates: buttons.slice(0, 6).map(function(x) {{ return {{score:x.score, label:x.label.slice(0,120), rect:x.rect}}; }})
        }};
    }} catch(e) {{
        return {{ok: false, reason: String(e), stack: (e && e.stack) ? String(e.stack).slice(0, 500) : ''}};
    }}
}})();
"""


def build_type_and_submit_js(query: str, site: str = "duck.ai") -> str:
    """Build JavaScript that types a query into the chat input and submits it."""
    if site == "chatgpt.com":
        return _build_chatgpt_type_and_submit_js(query)
    site_config = _AI_CHAT_SITES.get(site, _AI_CHAT_SITES["duck.ai"])
    input_sel = json.dumps(site_config["input_selector"], ensure_ascii=False)
    submit_sel = json.dumps(site_config["submit_selector"], ensure_ascii=False)
    query_js = json.dumps(query, ensure_ascii=False)

    return f"""
(function() {{
    try {{
        var query = {query_js};
        var inputSelector = {input_sel};
        var submitSelector = {submit_sel};
        function visible(el) {{
            if (!el) return false;
            var style = window.getComputedStyle(el);
            if (style && (style.display === 'none' || style.visibility === 'hidden')) return false;
            return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        }}
        function fieldText(el) {{
            if (!el) return '';
            if ('value' in el) return String(el.value || '');
            return String(el.innerText || el.textContent || '');
        }}
        function inputScore(el) {{
            var s = 0;
            var text = (
                (el.getAttribute('placeholder') || '') + ' ' +
                (el.getAttribute('aria-label') || '') + ' ' +
                (el.getAttribute('role') || '') + ' ' +
                (el.className || '')
            ).toLowerCase();
            if (/ask|message|chat|prompt|anything|privately|textbox/.test(text)) s += 20;
            if (el.tagName === 'TEXTAREA') s += 10;
            if (el.isContentEditable || el.getAttribute('role') === 'textbox') s += 8;
            return s;
        }}
        var inputs = Array.prototype.slice.call(document.querySelectorAll(inputSelector))
            .filter(function(el) {{ return visible(el) && !el.disabled && !el.readOnly; }});
        inputs.sort(function(a, b) {{ return inputScore(b) - inputScore(a); }});
        var input = inputs[0] || null;
        if (!input) return {{ok: false, reason: 'input_not_found', url: location.href}};

        input.focus();
        input.click();
        if (input.isContentEditable || input.getAttribute('role') === 'textbox') {{
            input.textContent = '';
            try {{
                document.execCommand('insertText', false, query);
            }} catch (_) {{
                input.textContent = query;
            }}
            if (!fieldText(input).trim()) input.textContent = query;
            input.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: query}}));
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
        }} else if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
            var proto = input.tagName === 'TEXTAREA'
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            var setter = Object.getOwnPropertyDescriptor(proto, 'value');
            if (setter && setter.set) {{
                setter.set.call(input, query);
            }} else {{
                input.value = query;
            }}
            input.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: query}}));
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }} else {{
            input.textContent = query;
            input.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: query}}));
        }}

        var typed = fieldText(input).trim();
        if (!typed) return {{ok: false, reason: 'input_empty_after_set', inputTag: input.tagName}};

        function buttonScore(btn) {{
            var label = (
                (btn.innerText || btn.textContent || '') + ' ' +
                (btn.getAttribute('aria-label') || '') + ' ' +
                (btn.getAttribute('title') || '') + ' ' +
                (btn.getAttribute('data-testid') || '') + ' ' +
                (btn.getAttribute('id') || '') + ' ' +
                (btn.className || '')
            ).toLowerCase();
            var score = 0;
            if (/^(ask|send|submit)\\b/.test(label.trim())) score += 60;
            if (/\\b(ask|send|submit|send-button|composer-submit|arrow-up)\\b/.test(label)) score += 35;
            if (btn.getAttribute('type') === 'submit') score += 20;
            var inputForm = input.closest ? input.closest('form') : null;
            var btnForm = btn.closest ? btn.closest('form') : null;
            if (inputForm && btnForm && inputForm === btnForm) score += 18;
            try {{
                var ir = input.getBoundingClientRect();
                var br = btn.getBoundingClientRect();
                var dx = Math.abs((br.left + br.right) / 2 - (ir.left + ir.right) / 2);
                var dy = Math.abs((br.top + br.bottom) / 2 - (ir.top + ir.bottom) / 2);
                if (dy < 120 && dx < 520) score += 14;
            }} catch (_) {{}}
            if (btn.querySelector && btn.querySelector('svg')) score += 4;
            if (/new chat|attach|voice|mic|microphone|settings|menu|sidebar|search|file|upload/.test(label)) score -= 40;
            return score;
        }}
        var buttons = Array.prototype.slice.call(document.querySelectorAll(submitSelector))
            .filter(function(btn) {{ return visible(btn) && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true'; }});
        buttons.sort(function(a, b) {{ return buttonScore(b) - buttonScore(a); }});
        var submit = buttons.find(function(btn) {{ return buttonScore(btn) > 0; }}) || null;
        if (submit) {{
            submit.click();
            return {{ok: true, method: 'button_click', inputTag: input.tagName, typed_len: typed.length, button_text: (submit.innerText || submit.textContent || '').trim().slice(0, 80)}};
        }}

        input.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
        input.dispatchEvent(new KeyboardEvent('keypress', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
        input.dispatchEvent(new KeyboardEvent('keyup', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
        return {{ok: true, method: 'enter_key', inputTag: input.tagName, typed_len: typed.length}};
    }} catch(e) {{
        return {{ok: false, reason: String(e), stack: (e && e.stack) ? String(e.stack).slice(0, 500) : ''}};
    }}
}})();
"""


def build_click_submit_js(site: str = "current.page") -> str:
    """Build JavaScript that submits an already-filled visible chat composer."""
    site_config = _AI_CHAT_SITES.get(site, _AI_CHAT_SITES["current.page"])
    input_sel = json.dumps(site_config["input_selector"], ensure_ascii=False)
    submit_sel = json.dumps(site_config["submit_selector"], ensure_ascii=False)
    return f"""
(function() {{
    try {{
        var inputSelector = {input_sel};
        var submitSelector = {submit_sel};
        function visible(el) {{
            if (!el) return false;
            var r = el.getBoundingClientRect();
            var s = window.getComputedStyle(el);
            return r.width > 1 && r.height > 1 && s.display !== 'none' && s.visibility !== 'hidden';
        }}
        function valueOf(el) {{
            if (!el) return '';
            return String(el.value || el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        }}
        function rectObj(el) {{
            var r = el.getBoundingClientRect();
            return {{x:r.x, y:r.y, w:r.width, h:r.height, left:r.left, right:r.right, top:r.top, bottom:r.bottom}};
        }}
        function inputScore(el) {{
            if (!visible(el) || el.disabled || el.readOnly) return -9999;
            var r = el.getBoundingClientRect();
            var label = (
                (el.getAttribute('placeholder') || '') + ' ' +
                (el.getAttribute('aria-label') || '') + ' ' +
                (el.getAttribute('role') || '') + ' ' +
                (el.getAttribute('id') || '') + ' ' +
                (el.className || '')
            ).toLowerCase();
            var score = 0;
            if (valueOf(el)) score += 120;
            if (/ask|message|chat|prompt|anything|textbox|composer/.test(label)) score += 80;
            if ((el.tagName || '').toUpperCase() === 'TEXTAREA') score += 35;
            if (el.isContentEditable || el.getAttribute('role') === 'textbox') score += 25;
            if (r.width > 250) score += 25;
            if (r.x < 50 || r.width < 150 || r.height > 260) score -= 120;
            score += Math.max(0, r.bottom) / 30;
            return score;
        }}
        var inputs = Array.prototype.slice.call(document.querySelectorAll(
            "#prompt-textarea, [data-testid='composer-text-input'], " + inputSelector
        )).filter(visible).map(function(el) {{ return {{el: el, score: inputScore(el)}}; }})
          .sort(function(a, b) {{ return b.score - a.score; }});
        var input = inputs[0] && inputs[0].score > -100 ? inputs[0].el : null;
        if (!input) return {{ok: false, reason: 'submit_input_not_found', url: location.href, title: document.title}};
        var query = valueOf(input);
        if (!query) return {{ok: false, reason: 'composer_empty_before_submit', inputRect: rectObj(input), url: location.href}};
        function buttonLabel(btn) {{
            return (
                (btn.innerText || btn.textContent || '') + ' ' +
                (btn.getAttribute('aria-label') || '') + ' ' +
                (btn.getAttribute('title') || '') + ' ' +
                (btn.getAttribute('data-testid') || '') + ' ' +
                (btn.getAttribute('type') || '') + ' ' +
                (btn.className || '')
            ).trim();
        }}
        function buttonScore(btn) {{
            if (!visible(btn) || btn.disabled || btn.getAttribute('aria-disabled') === 'true') return -9999;
            var label = buttonLabel(btn).toLowerCase();
            var score = 0;
            if (/send|submit|arrow-up|composer-submit|send-button/.test(label)) score += 100;
            if ((btn.getAttribute('type') || '').toLowerCase() === 'submit') score += 35;
            if (btn.querySelector && btn.querySelector('svg')) score += 10;
            try {{
                var ir = input.getBoundingClientRect();
                var br = btn.getBoundingClientRect();
                var cy = br.top + br.height / 2;
                var icy = ir.top + ir.height / 2;
                if (br.left >= ir.left - 20) score += 25;
                if (br.left >= ir.right - 200) score += 50;
                if (Math.abs(cy - icy) < 100) score += 35;
                score -= Math.abs(cy - icy) / 6;
            }} catch (_) {{}}
            if (/attach|file|upload|microphone|mic|voice|dictation|sidebar|search|new chat|library|project|settings|model|instant|sources|share/.test(label)) score -= 220;
            return score;
        }}
        var buttons = Array.prototype.slice.call(document.querySelectorAll(
            "button[data-testid='send-button'], button[data-testid*='send'], button[aria-label*='Send'], button[aria-label*='Submit'], button[type='submit'], " + submitSelector
        )).filter(visible).map(function(btn) {{
            return {{btn: btn, score: buttonScore(btn), label: buttonLabel(btn), rect: rectObj(btn)}};
        }}).sort(function(a, b) {{ return b.score - a.score; }});
        var best = buttons[0] || null;
        if (!best || best.score <= 20) {{
            return {{
                ok: false,
                reason: 'send_button_not_found_or_disabled',
                query: query,
                typed: query,
                inputRect: rectObj(input),
                candidates: buttons.slice(0, 8).map(function(x) {{ return {{score:x.score, label:x.label.slice(0,120), rect:x.rect}}; }}),
                url: location.href,
                title: document.title
            }};
        }}
        try {{ input.focus(); }} catch (_) {{}}
        best.btn.dispatchEvent(new MouseEvent('pointerdown', {{bubbles:true, cancelable:true}}));
        best.btn.dispatchEvent(new MouseEvent('mousedown', {{bubbles:true, cancelable:true}}));
        best.btn.dispatchEvent(new MouseEvent('mouseup', {{bubbles:true, cancelable:true}}));
        best.btn.click();
        return {{
            ok: true,
            method: 'click_existing_send_button',
            query: query,
            typed: query,
            typed_len: query.length,
            buttonLabel: best.label.slice(0, 120),
            buttonScore: best.score,
            buttonRect: best.rect,
            inputRect: rectObj(input),
            url: location.href,
            title: document.title
        }};
    }} catch(e) {{
        return {{ok: false, reason: String(e), stack: (e && e.stack) ? String(e.stack).slice(0, 500) : ''}};
    }}
}})();
"""


def build_read_response_js(site: str = "duck.ai", query: str = "") -> str:
    """Build JavaScript that reads the latest AI response from the page."""
    site_config = _AI_CHAT_SITES.get(site, _AI_CHAT_SITES["duck.ai"])
    response_sel = json.dumps(site_config["response_selector"], ensure_ascii=False)
    thinking_sel = json.dumps(site_config["thinking_indicator"], ensure_ascii=False)
    query_js = json.dumps(query, ensure_ascii=False)

    return f"""
(function() {{
    try {{
        var originalQuery = {query_js};
        function normText(s) {{
            return String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
        }}
        var thinking = document.querySelector({thinking_sel});
        if (thinking) return {{ok: false, reason: 'still_thinking'}};

        var responses = document.querySelectorAll({response_sel});
        if (!responses.length) return {{ok: false, reason: 'no_response_found'}};

        var q = normText(originalQuery);
        var texts = Array.prototype.slice.call(responses)
            .map(function(el) {{ return (el.innerText || el.textContent || '').trim(); }})
            .filter(function(text) {{
                var n = normText(text);
                if (!n) return false;
                if (q && n === q) return false;
                if (q && n.indexOf(q) === 0 && n.length <= q.length + 40) return false;
                if (/duckduckgo anonymizes your chats|ask anything privately|privacy policy|terms of service/i.test(text)) return false;
                return true;
            }});
        if (!texts.length) {{
            return {{
                ok: false,
                reason: 'no_assistant_response_found',
                candidate_count: responses.length
            }};
        }}

        var text = texts[texts.length - 1];
        if (!text) return {{ok: false, reason: 'empty_response'}};

        return {{ok: true, text: text.slice(0, 4000), response_count: responses.length, accepted_count: texts.length}};
    }} catch(e) {{
        return {{ok: false, reason: String(e)}};
    }}
}})();
"""


def uses_grok_browser_limb(site: str) -> bool:
    """True when this chatbot must use the proven grok.com browser hand path."""
    return str(site or "").strip().lower() in _GROK_LIMB_AI_CHAT_SITES


def mirror_grok_self_type_to_web_ai_bridge(
    row: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
) -> None:
    """Copy grok-limb send receipts into web_ai_chat_bridge for read-answer reflex."""
    url = str(row.get("url") or row.get("current_url") or "")
    site = ai_chat_site_from_url(url)
    if not site:
        return
    query = str(row.get("text_preview") or row.get("text") or row.get("query") or "").strip()
    status = str(row.get("status") or "")
    ok = bool(row.get("ok"))
    if status == "sent" and ok:
        append_web_ai_bridge_row(
            {
                "schema": SCHEMA,
                "truth_label": TRUTH_LABEL,
                "ts": time.time(),
                "site": site,
                "query": query,
                "phase": "typed_submitted",
                "limb": "grok_browser_self_type",
                "self_type_receipt_id": row.get("receipt_id"),
                "type_result": {
                    "ok": True,
                    "method": row.get("method") or "js_native_fill_enter_submit",
                    "status": status,
                    "verdict": row.get("verdict"),
                    "fill_result": row.get("fill_result"),
                    "url": url,
                },
            },
            state_dir=state_dir,
        )
        return
    if status in {"focus_failed", "unverified", "timeout_no_js_callback", "typing_failed"}:
        append_web_ai_bridge_row(
            {
                "schema": SCHEMA,
                "truth_label": TRUTH_LABEL,
                "ts": time.time(),
                "site": site,
                "query": query,
                "phase": "typing_failed",
                "limb": "grok_browser_self_type",
                "self_type_receipt_id": row.get("receipt_id"),
                "type_result": row,
            },
            state_dir=state_dir,
        )


def launch_ai_chat(
    query: str,
    *,
    site: str = "duck.ai",
    state_dir: Optional[Path | str] = None,
    navigate: bool = True,
    target_url: str = "",
    target_rounds: int = 0,
    topic: str = "",
) -> dict[str, Any]:
    """Navigate to AI chat site and prepare to type the query.

    Returns a receipt dict. The actual typing and response reading happen
    asynchronously via the browser widget.
    """
    sd = _state_dir(state_dir)
    url = str(target_url or "").strip() or build_ai_chat_url(site, query)
    if not url:
        return {"ok": False, "reason": f"unknown_site: {site}"}

    clear_web_ai_answer_receipt(state_dir=sd)
    nav_ok = write_browser_navigate(url, state_dir=sd) if navigate else True
    if int(target_rounds or 0) > 1:
        start_web_ai_dialogue_mission(
            site=site,
            url=url,
            opening_query=query,
            target_rounds=int(target_rounds or 0),
            topic=topic,
            state_dir=sd,
        )

    if uses_grok_browser_limb(site):
        from System.swarm_alice_browser_grok_self_type import stage_grok_self_type_command

        stage = stage_grok_self_type_command(
            query,
            press_enter=True,
            url=url,
            source="web_ai_chat_bridge",
            state_dir=sd,
        )
        row = {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "ts": time.time(),
            "site": site,
            "query": query,
            "url": url,
            "navigate_requested": bool(navigate),
            "navigate_written": nav_ok,
            "grok_limb_command_staged": True,
            "self_type_receipt_id": stage.get("receipt_id"),
            "phase": "grok_limb_command_staged",
            "target_rounds": int(target_rounds or 0) or None,
            "topic": str(topic or "").strip() or None,
        }
        row = {k: v for k, v in row.items() if v is not None}
        append_web_ai_bridge_row(row, state_dir=sd)
        return row

    pending = stage_pending_web_ai_chat(
        site=site,
        query=query,
        url=url,
        state_dir=sd,
        phase="await_load",
        target_rounds=target_rounds,
        topic=topic,
    )
    js_ok = write_browser_js(build_type_and_submit_js(query, site), state_dir=sd)

    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "site": site,
        "query": query,
        "url": url,
        "navigate_requested": bool(navigate),
        "navigate_written": nav_ok,
        "js_written": js_ok,
        "pending_written": bool(pending.get("ok")),
        "phase": "await_load",
    }
    append_web_ai_bridge_row(row, state_dir=sd)
    return row


def launch_ai_chat_submit_current_page(
    *,
    site: str,
    current_url: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stage a submit-only hand action on the current web-AI page."""
    sd = _state_dir(state_dir)
    url = str(current_url or "").strip()
    if not url:
        return {"ok": False, "reason": "missing_current_url"}
    clear_web_ai_answer_receipt(state_dir=sd)
    pending = stage_pending_web_ai_submit(site=site, url=url, state_dir=sd)
    js_ok = write_browser_js(build_click_submit_js(site), state_dir=sd)
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "site": site,
        "query": "",
        "url": url,
        "navigate_requested": False,
        "navigate_written": True,
        "js_written": js_ok,
        "pending_written": bool(pending.get("ok")),
        "submit_only": True,
        "phase": "submit_current_staged",
    }
    append_web_ai_bridge_row(row, state_dir=sd)
    return row


def answer_ai_chat_query(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
    history: Optional[list[dict[str, Any]]] = None,
) -> Any:
    """Reflex: detect 'ask <web chatbot> <query>' and launch the chat.

    Returns WEB_AI_CHAT_STAGED_SILENT when the browser hand is staged (no Talk prose),
    a user-visible string only for launch failure, or None if no match.
    """
    current = latest_ai_chat_context(state_dir=state_dir)
    submit_request = None
    if not looks_like_web_ai_type_send_command(text):
        submit_request = detect_ai_chat_submit_request(
            text,
            current_url=str(current.get("url") or ""),
            state_dir=state_dir,
        )
    if submit_request:
        result = launch_ai_chat_submit_current_page(
            site=str(submit_request.get("site") or ""),
            current_url=str(submit_request.get("current_url") or ""),
            state_dir=state_dir,
        )
        if result.get("ok") is False:
            return f"I could not submit {submit_request.get('name') or 'the web chat'}: {result.get('reason', 'unknown error')}."
        return WEB_AI_CHAT_STAGED_SILENT

    request = detect_ai_chat_request(
        text,
        history=history,
        current_url=str(current.get("url") or ""),
        state_dir=state_dir,
    )
    if not request:
        return None

    use_current = bool(request.get("use_current_page"))
    result = launch_ai_chat(
        request["query"],
        site=request["site"],
        state_dir=state_dir,
        navigate=not use_current,
        target_url=str(request.get("current_url") or "") if use_current else "",
        target_rounds=int(request.get("target_rounds") or 0),
        topic=str(request.get("topic") or ""),
    )

    if result.get("ok") is False:
        return f"I could not launch {request['name']}: {result.get('reason', 'unknown error')}."

    # Successful staging is a browser-hand movement, not a Global Chat answer.
    # The visible field updates later from typed_submitted/read receipts.
    return WEB_AI_CHAT_STAGED_SILENT


def detect_read_ai_answer_request(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(
        _READ_ANSWER_RE.search(t)
        or _READ_DUCK_ANSWER_RE.search(t)
        or _READ_NAMED_AI_ANSWER_RE.search(t)
    )


def record_web_ai_answer(
    *,
    site: str,
    query: str,
    answer_text: str,
    state_dir: Optional[Path | str] = None,
    **extra: Any,
) -> dict[str, Any]:
    """Record a captured web-AI answer to the answer receipt + bridge ledger."""
    sd = _state_dir(state_dir)
    mission = read_web_ai_dialogue_mission(state_dir=sd)
    mission_active = (
        isinstance(mission, dict)
        and str(mission.get("status") or "") == "active"
        and str(mission.get("site") or "") == str(site or "")
    )
    answer_turn = int(mission.get("answer_turns") or 0) + 1 if mission_active else 0
    target_rounds = int(mission.get("target_rounds") or 0) if mission_active else 0
    final_turn = bool(mission_active and target_rounds > 0 and answer_turn >= target_rounds)
    payload = {
        "site": site,
        "query": query,
        "answer": answer_text,
        "phase": "answer_captured",
        "answer_turn": answer_turn or None,
        "target_rounds": target_rounds or None,
        "final_turn": final_turn or None,
        **extra,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    write_web_ai_answer_receipt(payload, state_dir=sd)
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "site": site,
        "query": query,
        "phase": "answer_captured",
        "answer": answer_text[:4000],
        "answer_turn": answer_turn or None,
        "target_rounds": target_rounds or None,
        "final_turn": final_turn or None,
        **{k: v for k, v in extra.items() if k not in payload},
    }
    row = {k: v for k, v in row.items() if v is not None}
    append_web_ai_bridge_row(row, state_dir=sd)
    if mission_active:
        mission["answer_turns"] = answer_turn
        mission["last_answer_ts"] = time.time()
        mission["last_answer_preview"] = _clean_one_line(answer_text, limit=500)
        mission["last_query_preview"] = _clean_one_line(query, limit=500)
        if final_turn:
            mission["status"] = "complete"
            mission["completed_ts"] = time.time()
            mission["completed_reason"] = "target_rounds_reached"
        write_web_ai_dialogue_mission(mission, state_dir=sd)
        try:
            from System.swarm_alice_talk_mirror_line import stage_talk_mirror_line_command

            stage_talk_mirror_line_command(
                answer_text,
                turn=answer_turn,
                owner_text="web-AI autopilot: mirror captured browser answer to Global Chat",
                from_browser_receipt=str(extra.get("browser_receipt_id") or extra.get("typed_receipt_id") or ""),
                source="web_ai_chat_autopilot",
                speaker="chatgpt" if site == "chatgpt.com" else "web_ai",
                site=str(mission.get("name") or site),
                browser_url=str(mission.get("url") or ""),
                schedule_reply=not final_turn,
                target_rounds=target_rounds,
                final=final_turn,
                state_dir=sd,
            )
        except Exception as exc:
            append_web_ai_bridge_row(
                {
                    "schema": SCHEMA,
                    "truth_label": TRUTH_LABEL,
                    "ts": time.time(),
                    "site": site,
                    "query": query,
                    "phase": "answer_mirror_stage_failed",
                    "answer_turn": answer_turn,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                state_dir=sd,
            )
    clear_pending_web_ai_chat(state_dir=sd)
    return row


def answer_read_ai_chat_query(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> Optional[str]:
    """Reflex: read the latest captured web-AI answer from receipts."""
    if not detect_read_ai_answer_request(text):
        return None

    sd = _state_dir(state_dir)
    receipt = read_web_ai_answer_receipt(state_dir=sd)
    answer = (receipt.get("answer") or "").strip()
    if answer:
        site = receipt.get("site") or receipt.get("name") or "the AI chat"
        query = receipt.get("query") or ""
        if query:
            return f"From {site} on \"{query}\": {answer[:2000]}"
        return f"From {site}: {answer[:2000]}"

    pending = read_pending_web_ai_chat(state_dir=sd)
    if pending:
        site_name = _AI_CHAT_SITES.get(pending.get("site", ""), {}).get("name", "the AI chat")
        phase = pending.get("phase") or "await_load"
        if phase in {"typing_started", "await_answer"}:
            return (
                f"I'm still waiting for {site_name} to finish answering "
                f"\"{pending.get('query', '')}\". Try again in a few seconds."
            )
        return (
            f"I'm still loading {site_name} and typing "
            f"\"{pending.get('query', '')}\". Ask me to read the answer once it appears."
        )

    return (
        "I don't have a captured web-AI answer yet. "
        "Try \"ask Duck.ai <your question>\", \"ask ChatGPT <your question>\", "
        "or \"ask grok.com <your question>\" first, then \"read the answer\"."
    )


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "detect_ai_chat_request",
    "detect_ai_chat_submit_request",
    "looks_like_web_ai_type_send_command",
    "looks_like_web_ai_submit_command",
    "is_send_intent_typo_label",
    "canonical_ai_chat_site",
    "ai_chat_site_from_url",
    "current_page_site_from_url",
    "latest_ai_chat_context",
    "resolve_anaphoric_ai_query",
    "build_ai_chat_url",
    "WEB_AI_CHAT_STAGED_SILENT",
    "uses_grok_browser_limb",
    "mirror_grok_self_type_to_web_ai_bridge",
    "launch_ai_chat",
    "launch_ai_chat_submit_current_page",
    "answer_ai_chat_query",
    "build_click_submit_js",
    "build_type_and_submit_js",
    "pending_host_matches_url",
    "has_web_ai_typed_submitted_receipt",
    "web_ai_type_send_fiction_guard_reply",
    "build_read_response_js",
    "read_web_ai_dialogue_mission",
    "start_web_ai_dialogue_mission",
    "stage_pending_web_ai_chat",
    "stage_pending_web_ai_submit",
    "read_pending_web_ai_chat",
    "clear_pending_web_ai_chat",
    "mark_pending_web_ai_phase",
    "write_web_ai_answer_receipt",
    "read_web_ai_answer_receipt",
    "clear_web_ai_answer_receipt",
    "append_web_ai_bridge_row",
    "detect_read_ai_answer_request",
    "record_web_ai_answer",
    "answer_read_ai_chat_query",
]
