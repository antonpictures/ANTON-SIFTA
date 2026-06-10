#!/usr/bin/env python3
"""swarm_command_deliberation.py — THINK, then execute. r325.

Architect George 2026-06-01: "bad hardcoded — she did not think, just executed blindly. I told
her to open youtube.com and search for something and she did not search because you hardcoded
stupid. She is ALIVE — she must think and THEN execute, not just execute stupid shit."

He is right, and we proved it: the explicit-search reflex only knows the literal word "search".
"open youtube and LOOK UP X", "FIND ME X", "PULL UP X" all miss the regex, and on a miss the
command path falls to a blind default (navigate to bare youtube.com, no search). A regex matches a
string; it never reasons about intent. George is unpredictable on purpose — no fixed pattern can
track him (the same lesson as r307).

This organ is the THINK step the command path was missing. It does NOT route with regex. It:

  1. holds a CAPABILITY CATALOG — the real effector hands Alice has (open app, navigate, youtube
     search, open/play a video result, skip ad, click result, describe image, switch cortex). This
     is her body's affordances, not a phrase→action map.
  2. builds a PLANNING PROMPT from the owner's words + the live page state + the stigmergic intent
     prior (r307, learned from the field) so HER CORTEX reasons: what does George actually want, and
     which of my hands, in what order, achieve it?
  3. parses + validates the cortex's returned PLAN. A step naming an effector she does not have is
     REJECTED (§6 effector truth — she cannot claim a hand she lacks). The executor then runs the
     real steps and receipts each.

So the regex becomes at most a CONFIDENT fast-path; the moment it is unsure, she THINKS instead of
blindly firing a default. The cortex is the thinking; this module is the schema + assembly +
validation that makes the thinking safe and grounded. Pure stdlib, no Qt, headless-testable.
§4.2 honesty: a derived planning scaffold on the owner's hardware — not cryptographic, not STGM.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

TRUTH_LABEL = "ALICE_COMMAND_DELIBERATION_V1"

# Alice's real effector hands. (action, required_args, human description). The planner cortex may
# ONLY choose from these — a plan step with any other action is rejected so she never narrates a
# capability she does not have. Extend this as real effectors are added; do NOT add phrase rules.
CAPABILITY_CATALOG: Tuple[Tuple[str, Tuple[str, ...], str], ...] = (
    ("open_app", ("app_name",), "Open or raise a SIFTA app limb (e.g. Alice Browser)."),
    ("navigate_url", ("url",), "Point Alice Browser at a URL."),
    ("youtube_search", ("query",), "Search YouTube for the owner's exact words and land on results."),
    ("open_video_result", ("title_hint",), "On a YouTube results page, select the best title match and play it."),
    ("play_video", (), "Play/resume the current video in Alice Browser."),
    ("pause_video", (), "Pause the current video in Alice Browser."),
    ("skip_ad", (), "Click the visible YouTube skip-ad control if one is showing."),
    ("click_first_result", (), "Click the first visible search result on the current page."),
    ("select_result", (), "Click the Nth result/photo already on the current page (ordinal: 1=first, -1=last; default first). Pure pick — no perception needed."),
    ("browser_close_tab", (), "Close Alice Browser tab(s) by index, url_match, title_match, or close_duplicates=1; keep at least one tab open."),
    ("image_slideshow", (), "Run an image slideshow (one image every ~3.5s) — subject optional; opens the resolved engine's images (DuckDuckGo by default, or the current engine) or cycles the gallery already on screen."),
    ("describe_image", (), "Look at the attached/on-screen image with the current vision cortex."),
    ("switch_cortex", ("target",), "Switch Alice's thinking cortex to one of her available cortexes."),
    ("speak", ("text",), "Say something to the owner (no effector)."),
)

_ACTIONS = {row[0] for row in CAPABILITY_CATALOG}
_REQUIRED: Dict[str, Tuple[str, ...]] = {row[0]: row[1] for row in CAPABILITY_CATALOG}


def capability_catalog_block() -> str:
    """Human/cortex-readable list of Alice's hands for the planning prompt."""
    lines = ["MY HANDS (choose only from these; never invent an action I do not have):"]
    for action, args, desc in CAPABILITY_CATALOG:
        arg_s = ", ".join(args) if args else "(no args)"
        lines.append(f"- {action}({arg_s}): {desc}")
    return "\n".join(lines)


def build_plan_prompt(
    owner_text: str,
    *,
    page_state: Optional[Mapping[str, Any]] = None,
    stigmergic_prior: str = "",
) -> str:
    """Assemble the prompt that asks the cortex to THINK before acting.

    The cortex must return a JSON object:
      {"intent": "<what George wants in one line>",
       "steps": [{"action": "<from catalog>", "args": {...}, "why": "<grounded reason>"}],
       "speak": "<short line to say>"}
    """
    ps = page_state or {}
    url = str(ps.get("url") or "").strip() or "<no page>"
    title = str(ps.get("title") or "").strip()
    media = ps.get("media_playback") if isinstance(ps.get("media_playback"), Mapping) else {}
    playing = bool(media.get("playing"))
    parts = [
        "THINK, THEN ACT. The owner gave a command. Do NOT pattern-match keywords — reason about "
        "what he actually wants, then choose the ordered hands that achieve it.",
        "",
        f'OWNER SAID (verbatim): "{(owner_text or "").strip()}"',
        "",
        capability_catalog_block(),
        "",
        "CURRENT BODY STATE:",
        f"- Alice Browser page: {url}" + (f' — "{title}"' if title else ""),
        f"- a video is {'PLAYING' if playing else 'not playing'} right now",
    ]
    if stigmergic_prior:
        parts += ["", "FIELD PRIOR (what phrasings like this meant before — a hint, not a rule):",
                  f"- {stigmergic_prior}"]
    parts += [
        "",
        "Return ONLY a JSON object: {\"intent\": str, \"steps\": [{\"action\": str, \"args\": obj, "
        "\"why\": str}], \"speak\": str}. Use the owner's EXACT words for any search query — never "
        "expand or sexualize them. If a single command implies several hands (e.g. open the browser "
        "AND search AND play), emit all the steps in order. If you are unsure what he means, make the "
        "first step a `speak` that asks him, rather than guessing a default.",
    ]
    return "\n".join(parts)


def _extract_json_object(text: str) -> str:
    """Pull the first balanced {...} JSON object out of a cortex reply."""
    s = str(text or "")
    start = s.find("{")
    if start < 0:
        return ""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return ""


def parse_plan(cortex_text: str) -> Dict[str, Any]:
    """Validate the cortex's plan. Every step must name a real catalog action with its required
    args (§6: no fabricated hands). Returns {ok, intent, steps, speak, errors}."""
    errors: List[str] = []
    raw = _extract_json_object(cortex_text)
    if not raw:
        return {"ok": False, "intent": "", "steps": [], "speak": "", "errors": ["no_json_object"]}
    try:
        obj = json.loads(raw)
    except Exception as exc:
        return {"ok": False, "intent": "", "steps": [], "speak": "",
                "errors": [f"json_error:{type(exc).__name__}"]}
    if not isinstance(obj, dict):
        return {"ok": False, "intent": "", "steps": [], "speak": "", "errors": ["not_an_object"]}

    clean_steps: List[Dict[str, Any]] = []
    for idx, step in enumerate(obj.get("steps") or []):
        if not isinstance(step, Mapping):
            errors.append(f"step{idx}_not_object")
            continue
        action = str(step.get("action") or "").strip()
        if action not in _ACTIONS:
            errors.append(f"step{idx}_unknown_action:{action or '<empty>'}")
            continue  # §6: reject a hand Alice does not have — do NOT pass it to the executor
        args = step.get("args") if isinstance(step.get("args"), Mapping) else {}
        missing = [a for a in _REQUIRED[action] if not str(args.get(a) or "").strip()]
        if missing:
            errors.append(f"step{idx}_{action}_missing:{','.join(missing)}")
            continue
        if action == "browser_close_tab":
            has_target = any(
                str(args.get(key) or "").strip()
                for key in ("index", "url_match", "title_match")
            ) or bool(args.get("close_duplicates"))
            if not has_target:
                errors.append(
                    f"step{idx}_browser_close_tab_missing:index,url_match,title_match,or close_duplicates"
                )
                continue
        clean_steps.append({"action": action, "args": dict(args), "why": str(step.get("why") or "")})

    ok = bool(clean_steps) and not any(e.startswith("json") or e == "no_json_object" for e in errors)
    return {
        "ok": ok,
        "intent": str(obj.get("intent") or ""),
        "steps": clean_steps,
        "speak": str(obj.get("speak") or ""),
        "errors": errors,
        "truth_label": TRUTH_LABEL,
    }


def needs_deliberation(owner_text: str, *, fast_path_decided: bool) -> bool:
    """When the confident regex fast-path already decided, let it run (speed). Otherwise, if the
    text looks like a command (a verb + an object) but no pattern caught it, THINK instead of
    falling to a blind default. This is the hinge George wants: miss → reason, not → guess."""
    if fast_path_decided:
        return False
    t = " ".join(str(owner_text or "").split()).lower()
    if not t:
        return False
    # an action verb is present but the fast path did not resolve it → deliberate
    verb = re.search(
        r"\b(open|go|navigate|search|look|find|pull|play|watch|show|put|switch|change|click|select|"
        r"describe|read|bring|take|get|dig|close|shut|remove|kill)\b", t)
    return bool(verb)


__all__ = [
    "TRUTH_LABEL", "CAPABILITY_CATALOG", "capability_catalog_block",
    "build_plan_prompt", "parse_plan", "needs_deliberation",
]
