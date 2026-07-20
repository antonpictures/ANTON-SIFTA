#!/usr/bin/env python3
"""Generic "click <free text>" target extractor — click ANY element by visible text.

Gap (George live 2026-06-20): the Talk widget's `_extract_named_click_button_label`
only matches `click <label> button|link|tab|control` (requires the trailing control
word) and its label class excludes '.' and ':'. So owner turns like:
    "click article: epoll vs. io_uring in linux"
    "click on 'Astrophysics' on your body"
miss the deterministic fast-path and fall through to the (often wedged) cortex.

This extractor catches the general case and returns the target TEXT to feed the
existing effector `AliceBrowserWidget.click_visible_control_matching_text(text)`.
Drop-in for Codex's click router: as the LAST resort in
`_extract_browser_action_command(text)` (after back/forward/enlarge/named-button),
when a browser is open and `_has_current_browser_click_instruction(text)`:

    t = extract_click_text_target(clean)
    if t:
        return {"kind": "browser_action", "app_name": "Alice Browser",
                "action": "click_element", "labels": [t], "visible_text_affordance": "1"}

Pure stdlib. Never raises.
"""
from __future__ import annotations
import re

_CTRL = r"(?:article|story|result|headline|link|post|item|tab|button|control|row|tile|option|entry|card|thread)"
_PLACEHOLDERS = {
    "another", "a different", "some other", "other", "different", "some", "a", "the",
    "new", "any", "it", "this", "that", "there", "here", "ok", "now",
}
# historical reference, not a live command: "the photo I told you to click"
_HISTORICAL = re.compile(r"\b(?:told|asked|said|wanted|supposed)\s+(?:you\s+)?to\s+(?:click|press|tap|open|select)\b", re.I)
_TAIL = re.compile(
    r"\b(?:please|pls|now|thanks?|thank you|do you understand|on your body|on the page|"
    r"on your screen|on your alice browser|in the browser|for me|ok|okay|somehow|"
    r"you\s+have\s+to|realize|stay\s+in\s+the\s+present|not\s+past|i\s+mean|"
    r"how\s+can\s+i\s+put\s+it|your\s+job)\b.*$",
    re.I,
)
_CLICK = re.compile(
    r"\b(?:click|press|tap|open|select)\b\s*(?:on\s+)?(?:the\s+)?"
    r"(?:" + _CTRL + r"\b\s*)?:?\s*"
    r"(?P<text>.+)$",
    re.I,
)


def extract_click_text_target(text: str) -> str:
    """Return the visible-text target of a free-form click command, or ''."""
    clean = " ".join((text or "").strip().split())
    if not clean or _HISTORICAL.search(clean):
        return ""
    # take from the LAST click verb (owners revise mid-turn)
    last = None
    for m in re.finditer(r"\b(?:click|press|tap|open|select)\b", clean, re.I):
        verb = m.group(0).lower()
        prefix = clean[max(0, m.start() - 14):m.start()].lower()
        if verb == "open" and re.search(r"\bpage\s+$", prefix):
            continue
        last = m
    if last is None:
        return ""
    seg = clean[last.start():]

    quoted = re.search(
        r"\b(?:click|press|tap|open|select)\b\s*(?:on\s+)?(?:the\s+)?"
        r"(?:" + _CTRL + r"\b\s*)?:?\s*[\"'“”‘’](?P<text>[^\"'“”‘’]{2,120})[\"'“”‘’]",
        seg,
        re.I,
    )
    if quoted:
        t = " ".join(quoted.group("text").split()).strip(" \"'“”‘’:.,;!?-—")
        return "" if t.lower() in _PLACEHOLDERS else t

    m = _CLICK.search(seg)
    if not m:
        return ""
    t = m.group("text").strip()
    t = _TAIL.sub("", t).strip()                       # cut conversational tail
    t = t.strip(" \"'“”‘’:.,;!?-—")                    # outer quotes/punct
    t = re.sub(r"\s+" + _CTRL + r"$", "", t, flags=re.I).strip()  # trailing "link"/"button"
    if re.match(
        r"^(?:one|a|the|this|that|any)?\s*(?:button|control|link|thing|item)\b(?:\s+on\s+(?:this|the)\s+page\b.*)?$",
        t,
        re.I,
    ):
        return ""
    if not t or t.lower() in _PLACEHOLDERS or len(t) < 2:
        return ""
    return t


if __name__ == "__main__":
    cases = [
        ("fine, click article: epoll vs. io_uring in linux", "epoll vs. io_uring in linux"),
        ("you don't know whats going on do you? --- click on 'Astrophysics' on your body", "Astrophysics"),
        ("click the Login link", "Login"),
        ("please click Renting a sewing machine", "Renting a sewing machine"),
        ('select "install candidate skill" somehow your heartbeats are behind real world time', "install candidate skill"),
        ("yes, pls click on Sign In, you have to execute", "Sign In"),
        ("all u have to do is click one button on this page", ""),
        ("the photo I told you to click", ""),       # historical -> no live command
        ("click another", ""),                        # placeholder -> none
        ("press Show HN: TownSquare", "Show HN: TownSquare"),
    ]
    ok = True
    for inp, want in cases:
        got = extract_click_text_target(inp)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"{flag} {got!r:40} (want {want!r})  <- {inp!r}")
    raise SystemExit(0 if ok else 1)
