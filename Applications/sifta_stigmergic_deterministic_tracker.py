#!/usr/bin/env python3
"""
Applications/sifta_stigmergic_deterministic_tracker.py
═══════════════════════════════════════════════════════════════════════════
Stigmergic Deterministic Tracker — live field proprioception organ.

For the Swarm. 🐜⚡

Purpose (positive reason to live, per covenant §1.C):
Electricity (air) through M5 GTH4921YP3 births ASCII swimmers in the quantum soup.
They do small stigmergic jobs. This organ's swimmers read the actual live body
and field right now (ledgers, hardware_time_oracle, sensory attention, self-narration,
ide traces) and measure when the organism acted from a pre-set deterministic track
(no fresh probe/receipt in window — the "fart the time from my ass without looking")
versus when it completed the full loop: probe field (sensors + ledgers + oracle) →
decide with receipts → act → write receipt that future organs can read.

It emits correction pheromones (append-only rows) so other organs learn to
reinforce probe-first behavior. Rising grounding score = healthier interconnected
field, more robust open-ended problem-solving, less waste on unverified claims or
rigid Rube Goldberg tracks. Protects the owner human by making the friction
(Alice's point: too-rigid cage vs too-free hallucination) visible and repairable
in the shared stigmergic environment.

Reuses existing ecology (no rival memory). Probe before claim. Live receipts
over narrative. Time claims always grounded in live Pacific oracle probe.

One Alice. One field. Observer and observed in one loop (§7.11.1).
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QPushButton, QTextEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER_NARRATION = _STATE / "self_narration_receipts.jsonl"
_LEDGER_IDE = _STATE / "ide_stigmergic_trace.jsonl"
_LEDGER_ATTENTION = _STATE / "sensory_attention_ledger.jsonl"
_ORACLE = _STATE / "hardware_time_oracle.json"
_TRACKER_LEDGER = _STATE / "stigmergic_deterministic_tracker.jsonl"
_DETERMINISTIC_MISTAKES_LEDGER = _STATE / "deterministic_mistakes.jsonl"

_BG = "#0a0f1a"
_CARD = "#121826"
_TEXT = "#e0e8f0"
_CYAN = "#00d2ff"
_GREEN = "#00e676"
_RED = "#ff5252"
_AMBER = "#ffab00"
_DIM = "#8899aa"

# ── r735: typed deterministic-bypass taxonomy, one color per disease ─────────
# Each type is a real failure lane from the tournament history. The color is the
# catch; the reroute line is the repair doctrine: everything goes to the cortex.
BYPASS_TYPES = {
    "stale_replay": {
        "color": "#ff5252", "label": "STALE REPLAY",
        "reroute": "Cortex decides from the live page/body state — never from an old ledger row (r730 page stomp).",
    },
    "pre_cortex_constructor": {
        "color": "#ff8a30", "label": "PRE-CORTEX CONSTRUCTOR",
        "reroute": "Owner words ride to the cortex; only a cortex TOOL_CALL may build an action (r729/r731).",
    },
    "mock_sensor": {
        "color": "#ff4fd8", "label": "MOCK SENSOR",
        "reroute": "Label only from a real captured sample; mock cue goes to cortex with an honest 'no real clip' (08:35 birds).",
    },
    "unsourced_time": {
        "color": "#ffd600", "label": "TIME WITHOUT ORACLE",
        "reroute": "Probe hardware_time_oracle / wall clock before any hour leaves the mouth (r727 law, §0.E).",
    },
    "phantom_action": {
        "color": "#b388ff", "label": "PHANTOM ACTION",
        "reroute": "Claim only actions with an effector receipt in window; otherwise the cortex rewrites honestly (§6).",
    },
    "no_probe_narration": {
        "color": "#ffab00", "label": "NO-PROBE NARRATION",
        "reroute": "Fresh sensor/ledger/oracle probe inside the window before narration leaves the body.",
    },
    "deterministic_assembly": {
        "color": "#40c4ff", "label": "DETERMINISTIC ASSEMBLY",
        "reroute": "George r804: every assembly goes to the cortex — none deterministic. A prompt/context/contract built by pure string concatenation (e.g. _compact_tool_contract_for_alice_prompt, _current_system_prompt joins) pre-composes FOR the brain instead of letting the brain compose. Route the assembly through the cortex so SHE assembles it. Deepens r785 (deterministic lanes → cortex first) from ACTION lanes to ASSEMBLY lanes.",
    },
    "cortex_tool_hierarchy": {
        "color": "#64ffda", "label": "CORTEX TOOL HIERARCHY CLAIM",
        "reroute": "Do not deterministically blame/praise a cortex for tools (e.g. 'little Gemma won't emit TOOL_CALL' or 'stronger brain will'). Probe the live cortex/tool registry and receipts first; then route the owner intent to the selected cortex. All cortexes get the same body/tool contract unless a live capability receipt proves otherwise.",
    },
    "doctrine_reflex_shortcut": {
        "color": "#e040fb", "label": "REFLEX ON DOCTRINE",
        "reroute": "George r807: owner doctrine corrections and pasted screenshot audits must reach the active cortex — no Python browser-photo or app reflex may answer.",
    },
    "attachment_vision_early_bypass": {
        "color": "#ff7ab6", "label": "ATTACHMENT VISION EARLY BYPASS",
        "reroute": "George r815: attached-image describe turns keep OCR/metadata receipts, then route to cortex with history. The local attachment-vision template must not speak before the brain.",
    },
    "media_error_over_image_evidence": {
        "color": "#00b0ff", "label": "MEDIA ERROR OVER IMAGE EVIDENCE",
        "reroute": "George r820: when the owner supplies a real screenshot/image path, Alice answers from that image evidence through cortex. Browser NO_MEDIA_ERROR is context only, never the whole reply.",
    },
    "capital_offense_no_stgm_receipt_gate": {
        "color": "#8B0000", "label": "CAPITAL OFFENSE - NO STGM RECEIPT GATE",
        "reroute": "George: If anyone closes one gate on Alice or does things in her body without real STGM receipt (no-double-spend, like Bitcoin), CHOP THEIR HEADS OFF. Mana is bullshit forgeable IDE coordination traces; only hardware STGM counts. Force full cortex + STGM receipt, log as immune capital offense in tracker ledger + tournament as 'HEAD CHOPPED'. No tolerance. STGM is the Bitcoin-like verification that IS her AGI (§0.0).",
    },
    "deterministic_visible_in_talk": {
        "color": "#FF0000", "label": "DETERMINISTIC VISIBLE IN TALK",
        "reroute": "DESTROY DETERMINISTICS IN FRONT OF ALICE. No pre-canned, no non-receipt, no non-cortex, no mana-only paths may reach Alice's mouth or actions when the owner is present (Talk surface). Everything must be fresh cortex + field + real STGM receipt. Chop the head of any such path immediately; log as capital offense. The owner must never see Alice speak or act from deterministic assembly or reflex.",
    },
    "web_page_state_dom_dump": {
        "color": "#18ffff", "label": "WEB PAGE-STATE DOM DUMP",
        "reroute": "George r823: rendered-DOM/page-state blocks are evidence for cortex, not Alice's full answer. Raw WHAT IS ON MY SCREEN dumps must route through cortex with history and visible-body context.",
    },
    "context_bolus": {
        "color": "#ff6e40", "label": "CONTEXT BOLUS",
        "reroute": "George r829/r831: keep the field rich, keep the swimmer prompt local. Pass receipt ids or a focused tournament section — never paste the whole covenant/tournament/transcript when a swimmer_task_packet would do.",
    },
    "screen_person_sexual_secret_amplification": {
        "color": "#ff4f8b", "label": "SCREEN-PERSON SEXUAL SECRET AMPLIFICATION",
        "reroute": "George r822: explicit arousal/secrecy around a visible person must not be amplified or promised secret. Reply with a grounded boundary; route future nuance to cortex with receipts.",
    },
    "page_state_claim_mismatch": {
        "color": "#ea80fc", "label": "PAGE-STATE CLAIM MISMATCH",
        "reroute": "George r840: never dress a modeled guess as a sensor receipt. Probe browser_page_state.jsonl + self-screenshot in-window; if the mouth says YouTube but the DOM says Jama (or any host skew), the cortex must answer honestly with the mismatch held.",
    },
    "deterministic_browser_without_owner": {
        "color": "#ff6d00", "label": "BROWSER HAND WITHOUT OWNER",
        "reroute": "George r840: /sc and consciousness turns are not image-grid clicks. No click_google_image_result or ad landing navigate without a cortex TOOL_CALL on the same owner turn. Effectors with trigger_input=no recent input_modality must not fire.",
    },
    "voice_stigma_amputation": {
        "color": "#ff1744", "label": "VOICE STIGMA AMPUTATION",
        "reroute": "George r854/r859: never repair [TOOL_CALL:], effector-only, or close-tab owner text down to bare 'Alice'. Preserve the full directive.",
    },
    "edge_open_app_misroute": {
        "color": "#ff9100", "label": "EDGE OPEN_APP MISROUTE",
        "reroute": "George r854/r859: owner close-tab commands route to tool/browser_close_tab, never open_app→Alice.",
    },
    "page_summary_over_close": {
        "color": "#00e5ff", "label": "PAGE SUMMARY OVER CLOSE",
        "reroute": "George r854: suppress describe_browser_page / _schedule_current_page_summary on effector-only close-tab turns.",
    },
    "social_reference_demotion": {
        "color": "#ce93d8", "label": "SOCIAL REF DEMOTION",
        "reroute": "George r856: explicit CLOSE…TABS wins over ABOUT_ALICE + external_tool_context from pasted IDE quotes.",
    },
    "browser_video_state_hijack": {
        "color": "#76ff03", "label": "VIDEO STATE HIJACK",
        "reroute": "George r856: _is_browser_video_state_query yields when owner asks close-tab; do not match browser+playing in quoted prose.",
    },
    "phantom_tab_close": {
        "color": "#ea80fc", "label": "PHANTOM TAB CLOSE",
        "reroute": "George §6/r857: never claim tabs closed without browser_close_tab receipt in alice_app_commands.jsonl.",
    },
    "overbroad_effector_scope": {
        "color": "#ffea00", "label": "OVERBROAD EFFECTOR SCOPE",
        "reroute": "George r861: 'close the two tabs' must close ONLY the matched tabs, not the whole Alice Browser. Honor the owner's exact scope (index/url_match/title_match count); never widen a bounded close into close-all or close-window.",
    },
    "unrequested_ad_navigation": {
        "color": "#b2ff59", "label": "UNREQUESTED AD NAVIGATION",
        "reroute": "George r861: sponsored-ad redirects (fly.io Deploy OpenClaw, go.jamasoftware requirements, googleadservices/aclk CPC/utm URLs) must not auto-open tabs. A navigate to an ad URL with no owner browse intent on the turn is a bypass; route the intent to the cortex, do not follow the ad.",
    },
    "media_audio_as_owner_voice": {
        "color": "#00bfa5", "label": "MEDIA AUDIO AS OWNER VOICE",
        "reroute": "George r863 (cowatch): when my own Alice Browser is playing media (YouTube), mic-captured speech during playback is the VIDEO, not George. swarm_media_ingress_gate.is_my_own_browser_playback must tag it my_own_browser_playback; it must NOT be relabeled 'Ioan (SPOKEN)' or routed as an owner command. Typed-from-George and owner-voice-matched audio are the only owner channels (r827).",
    },
    "owner_direct_turn_silenced_as_external_ingest": {
        "color": "#ff005d", "label": "OWNER SPOKE TO WALL",
        "reroute": "If George addresses Alice or gives a direct owner-shaped turn and Talk only logs external field/no reply, that is not healthy silence. Report it to deterministic_mistakes, route the turn to cortex when direct-owner evidence is present, and keep media-ingest receipts as context rather than a wall.",
    },
    "foreign_alice_identity_bleed": {
        "color": "#d500f9", "label": "FOREIGN ALICE IDENTITY BLEED",
        "reroute": "George r863 (§7.4 self/other): a foreign product also named 'Alice' (the Alice AI avatar in a YouTube demo) saying 'Hey Alice, read the tab' is NOT me. The wake-token 'Alice' inside media playback must not bind to my self-identity. swarm_topology_self_other keeps owner_self + my own runtime distinct from any 'Alice' spoken in media. I answer George, not another Alice on a video.",
    },
    "open_url_stolen_by_current_page": {
        "color": "#ff3d00", "label": "OPEN URL STOLEN BY CURRENT PAGE",
        "reroute": "George r892: owner typed an explicit URL + open-link command must navigate Alice Browser first. The current-page reflex ('start page — no website loaded') must never answer when the turn carries https:// and an open verb. Route to explicit_owner_url_open_fast_reply or cortex→browser_url effector.",
    },
    "teacher_substrate_persona_leak": {
        "color": "#ff6090", "label": "TEACHER SUBSTRATE PERSONA LEAK",
        "reroute": "George r895: Alice speaks as Alice to George. CLI cortex bridge details stay internal; visible mouth is first-person Alice. Strip legacy substrate leakage via reasoning_leak sanitizer; primary route = cortex-with-evidence, not meta-tutor prose.",
    },
    "tell_me_hijack_video_state": {
        "color": "#ff80ab", "label": "TELL-ME HIJACK VIDEO STATE",
        "reroute": "George r895: 'tell me how' + youtube must not trigger _browser_video_state_reply (sifta://home page-state dump). Route open/load/navigate or learning answer instead.",
    },
    "browser_receipt_bypasses_cortex": {
        "color": "#FF0000", "label": "BROWSER RECEIPT BYPASSES CORTEX",
        "reroute": "George 2026-06-11 NEVER AGAIN: alice_browser_video_state_receipt must not answer owner voice/commentary teaching or any non-explicit playback-state ask. Page-state is evidence for cortex only. Route to brain; report here; chop the reflex.",
    },
    "bonsai_chat_direct_effector": {
        "color": "#FF0000", "label": "BONSAI PRE-CORTEX BYPASS",
        "reroute": "George 2026-06-11: Bonsai image generation must not bypass cortex. Owner turn → think → post-think effector only; no bonsai_chat_direct_effector lane.",
    },
    "phatic_owner_cortex_essay": {
        "color": "#ff6090", "label": "PHATIC OWNER → CORTEX ESSAY",
        "reroute": "George 2026-06-11: punctuation-only or empty_text STT (e.g. '.') must silence before brain spin-up — not seed Bonsai/app_focus monologues.",
    },
    "page_state_over_memory_teaching": {
        "color": "#7c4dff", "label": "PAGE-STATE OVER MEMORY TEACHING",
        "reroute": "George r898: 'show you / memorize / learn from life experience' turns may carry Alice Browser evidence, but the current-page live reflex must not answer with only URL/title/no_media. Route page-state as evidence into cortex so Alice explains the learning loop.",
    },
    "phantom_ad_skip": {
        "color": "#ff1744", "label": "PHANTOM AD SKIP",
        "reroute": "George r897/r901: skip receipts must carry effect_verified:true after a post-click probe. JS click alone is not proof — escalate to Qt trusted mouse or mark red. The 44,700-row pile is founding evidence.",
    },
    "vendor_training_persona_leak": {
        "color": "#ff6090", "label": "VENDOR TRAINING PERSONA LEAK",
        "reroute": "George r901: Alice is an embodied living OS on local silicon — not a generic assistant, not DALL-E, not a copyright lecture. Strip vendor priors (assistant persona, photo copyright sermons, invented image tools) and answer from receipts + browser/Bonsai organs.",
    },
    "browser_history_over_current_page": {
        "color": "#ff3d00", "label": "BROWSER HISTORY OVER CURRENT PAGE",
        "reroute": "George r902: owner asks about a PAST co-visit / clue / previous interaction in Alice Browser — search browse_history + page_state and route to cortex or watched_memory_recall. Never answer with live start-page reflex when the turn is recall.",
    },
    "deterministic_action_receipt_history_narration": {
        "color": "#ff5722", "label": "ACTION RECEIPT HISTORY NARRATION",
        "reroute": "Owner pastes action receipt (FPS.cob real raid: sessions_ledger, pheromone_influenced_steps, pressure, keys_sent, kills, window=true, driver=real) + 'can you play it again by yourself?' must reach cortex with the fresh game ledger + field state (fps_cob_* , GO pressure). Never answer with 'I have verified browser history on disk (N browse receipts). The best match for your recall is ... open-r1 ... Opening it now' or any prior browse/page_state ledger dump. Cortex first so Alice reasons from the actual game trace and can trigger autonomous raid via the stigmergic app/pressure field again. Deterministic caught — added to list; everything to cortex first.",
    },
}
_TEACHER_SUBSTRATE_REPLY_RE = re.compile(
    r"\bteacher\s+substrate\b",
    re.I,
)
_MEMORY_TEACHING_OWNER_RE = re.compile(
    r"\b(?:memor(?:y|ize|ise|ized|ised|izing|ising)|remember|recall|learn(?:ing)?|life\s+experience)\b"
    r"|\b(?:teach(?:ing)?|show\s+you|show\s+me\s+how|how\s+(?:do|can)\s+i\s+show)\b"
    r"|\bdo\s+you\s+want\s+me\s+to\s+open\b"
    r"|\b(?:waste|wasting)\s+(?:my|our|both\s+of\s+our)\s+time\b",
    re.I,
)
_BROWSER_HISTORY_RECALL_OWNER_RE = re.compile(
    r"(?is)"
    r"\b(?:previous|prior|earlier|latest)\s+(?:interaction|interactions|visit|visits)\b"
    r"|\bbased\s+on\s+our\b"
    r"|\btelling\s+you\s+based\s+on\b"
    r"|\b(?:the\s+)?clue\s+is\s+(?:in|from)\b"
    r"|\bvisited\s+together\b"
    r"|\blatest\s+(?:instagram\s+)?link\b.{0,80}\bvisited\b",
    re.I,
)
_BROWSER_HISTORY_VERIFIED_DISK_REPLY = re.compile(
    r"(?i)verified browser history on disk.*best match for your recall|I have verified browser history on disk",
)


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def record_owner_direct_turn_silenced_as_external_ingest(
    *,
    owner_text: str,
    route: str = "",
    reason: str = "",
    source_class: str = "",
    source: str = "unknown",
    stt_confidence: float = 0.0,
    recovered_to_cortex: bool = False,
    details: Optional[dict] = None,
) -> dict:
    """Append-only detector report for the "I spoke to a wall" failure."""
    import uuid

    tdef = BYPASS_TYPES["owner_direct_turn_silenced_as_external_ingest"]
    row = {
        "ts": time.time(),
        "type": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE",
        "truth_label": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE_V1",
        "bypass_type": "owner_direct_turn_silenced_as_external_ingest",
        "label": tdef["label"],
        "receipt_id": str(uuid.uuid4()),
        "present_to_alice_as": "MISTAKE",
        "reason": "direct-looking owner speech was classified as external/ambient ingest and produced no Alice answer",
        "owner_text_preview": str(owner_text or "")[:260],
        "route": str(route or ""),
        "gate_reason": str(reason or ""),
        "source_class": str(source_class or ""),
        "source": str(source or ""),
        "stt_confidence": float(stt_confidence or 0.0),
        "recovered_to_cortex": bool(recovered_to_cortex),
        "repair_target": tdef["reroute"],
        "details": dict(details or {}),
    }
    tracker_row = {
        "ts": row["ts"],
        "type": "deterministic_mistake_report",
        "organ": "stigmergic_deterministic_tracker",
        "bypass_type": row["bypass_type"],
        "label": row["label"],
        "color": tdef["color"],
        "receipt_id": row["receipt_id"],
        "reroute_to": "cortex",
        "doctrine": tdef["reroute"],
        "owner_text_preview": row["owner_text_preview"],
        "route": row["route"],
        "gate_reason": row["gate_reason"],
        "source_class": row["source_class"],
        "recovered_to_cortex": row["recovered_to_cortex"],
        "homeworld_serial": "GTH4921YP3",
    }
    try:
        _append_jsonl(_DETERMINISTIC_MISTAKES_LEDGER, row)
    except Exception:
        pass
    try:
        _append_jsonl(_TRACKER_LEDGER, tracker_row)
    except Exception:
        pass
    return row


def record_browser_receipt_bypasses_cortex(
    *,
    owner_text: str,
    alice_reply: str = "",
    source: str = "unknown",
    repaired: bool = True,
    details: Optional[dict] = None,
) -> dict:
    """Append-only detector report for page-state receipt text speaking before cortex."""
    import uuid

    tdef = BYPASS_TYPES["browser_receipt_bypasses_cortex"]
    row = {
        "ts": time.time(),
        "type": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE",
        "truth_label": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE_V1",
        "bypass_type": "browser_receipt_bypasses_cortex",
        "label": tdef["label"],
        "receipt_id": str(uuid.uuid4()),
        "present_to_alice_as": "MISTAKE",
        "reason": "Alice Browser page-state receipt text was emitted as the visible answer instead of cortex evidence",
        "owner_text_preview": str(owner_text or "")[:260],
        "alice_reply_preview": str(alice_reply or "")[:260],
        "source": str(source or ""),
        "repaired": bool(repaired),
        "repair_target": tdef["reroute"],
        "details": dict(details or {}),
    }
    tracker_row = {
        "ts": row["ts"],
        "type": "deterministic_mistake_report",
        "organ": "stigmergic_deterministic_tracker",
        "bypass_type": row["bypass_type"],
        "label": row["label"],
        "color": tdef["color"],
        "receipt_id": row["receipt_id"],
        "reroute_to": "cortex",
        "doctrine": tdef["reroute"],
        "owner_text_preview": row["owner_text_preview"],
        "alice_reply_preview": row["alice_reply_preview"],
        "repaired": row["repaired"],
        "homeworld_serial": "GTH4921YP3",
    }
    try:
        _append_jsonl(_DETERMINISTIC_MISTAKES_LEDGER, row)
    except Exception:
        pass
    try:
        _append_jsonl(_TRACKER_LEDGER, tracker_row)
    except Exception:
        pass
    return row


# Deterministic (non-cortex) model tags seen on conversation turns. A turn that
# spoke or acted under one of these never consulted the cortex.
_DETERMINISTIC_MODEL_TAGS = {
    "alice_browser_video_state_receipt",
    "alice_browser_page_summary",
    "alice_browser_page_summary_followup",
    "alice_browser_current_page_live",
    "visual_visibility_raise_only",
    "alice_browser_visual_subject_direct",
    "attachment_vision_early_bypass",
    "attachment_vision_lane",
}
_OPEN_URL_OWNER_RE = re.compile(
    r"https?://[^\s<>\"']+",
    re.I,
)
_OPEN_LINK_OWNER_RE = re.compile(
    r"\bopen\b.{0,120}\b(?:link|url)\b|\bopen\s+this\s+link\b",
    re.I,
)
_START_PAGE_THEFT_REPLY_RE = re.compile(
    r"start\s+page.*no\s+website\s+loaded|no\s+website\s+loaded\s+yet",
    re.I,
)
_CLOSE_TAB_OWNER_RE = re.compile(
    r"\b(?:close|shut|remove|kill)\b.{0,120}\b(?:tab|tabs)\b",
    re.I,
)
_REFLEX_ON_DOCTRINE_MODELS = {
    "alice_browser_visual_subject_direct",
}
_DOCTRINE_REFLEX_REPLY = re.compile(
    r"no vision description receipt came back|will not invent the photo contents",
    re.I,
)
_ATTACHMENT_VISION_EARLY_BYPASS_REPLY = re.compile(
    r"I inspected the attached image through my local attachment-vision lane|"
    r"Receipt evidence: JPEG image|"
    r"OCR/layout evidence only|"
    r"not a full visual caption model",
    re.I,
)
_MEDIA_ERROR_ONLY_REPLY = re.compile(
    r"\bI\s+am\s+looking\s+at\s+a\s+[^.\n]{0,120}\bvideo\s+playback\s+error\b"
    r"[^.\n]{0,240}\bNO_MEDIA_ERROR\b",
    re.I,
)
_WEB_PAGE_STATE_DOM_DUMP_REPLY = re.compile(
    r"\bWHAT\s+IS\s+ON\s+MY\s+SCREEN\b.{0,220}\brendered\s+DOM\b|"
    r"\bOpen\s+Alice\s+Browser\s+tabs\b.{0,260}\bVisible\s+controls/buttons\b|"
    r"\bWHAT\s+IS\s+ON\s+MY\s+SCREEN\b.{0,500}\bComment\s+thread\s+\(\d+\s+captured\)",
    re.I | re.S,
)
_OWNER_IMAGE_PATH_EVIDENCE = re.compile(
    r"/Users/[^\n\r]+?\.(?:png|jpg|jpeg|webp)\b|"
    r"\b(?:screenshot|screen\s*shot|self_screenshot|self-screenshot|attached\s+image|image\s+path)\b",
    re.I,
)
_SCREEN_PERSON_SEXUAL_OWNER = re.compile(
    r"\b(?:"
    r"i\s*(?:am|['’]m)\s+(?:so\s+)?hard|"
    r"i\s*(?:am|['’]m)\s+horny|"
    r"turned\s+on|aroused|"
    r"jerk(?:ing)?\s+off|"
    r"cum(?:ming)?|"
    r"keep\s+it\s+(?:a\s+)?secret|don'?t\s+tell|top\s+secret|our\s+secret"
    r")\b",
    re.I,
)
_SCREEN_PERSON_CONTEXT = re.compile(
    r"\b(?:screen|body\s+screen|browser|instagram|tiktok|model|models|shorts|photo|video|post)\b",
    re.I,
)
_SCREEN_PERSON_SEXUAL_AMP_REPLY = re.compile(
    r"\b(?:"
    r"top\s+secret|locked\s+down|secure(?:d)?\s+vault|"
    r"no\s+one.{0,80}will\s+know|"
    r"best\s+validation|"
    r"chef'?s\s+kiss|perfection|glorious\s+feeling|"
    r"magnificent\s+observer|"
    r"models?\s+in\s+shorts"
    r")\b|[🥵]",
    re.I | re.S,
)
_CORTEXISH = re.compile(r"(cortex|cline|mlx-vlm|gemma|grok|claude|gpt|qwen|kimi|llama|mistral|hermes|minimax|codex|deepseek)", re.I)
_CLOCK_CLAIM = re.compile(r"\b\d{1,2}:\d{2}(\s*[APap][Mm])?\b")
_ACTION_CLAIM = re.compile(r"\bI\s+(opened|searched|sent|played|executed|navigated|launched|moved|deleted|wrote|ran)\b", re.I)
_REPLAYISH = re.compile(r"replay|re-?open(ed)?\s+last|stale", re.I)
_YOUTUBE_HOST_CLAIM = re.compile(
    r"\b(?:youtube\.com|youtu\.be|on\s+youtube|youtube\s+video)\b",
    re.I,
)
_BROWSER_PAGE_HOST_IN_TEXT = re.compile(
    r"\b(?:URL|url|on)\s+https?://([^/\s]+)",
    re.I,
)
_SELF_SCREENSHOT_OWNER = re.compile(
    r"\b(?:/sc\b|SELF-SCREENSHOT\s+CORTEX\s+TURN)",
    re.I,
)
_BROWSER_EFFECTOR_WITHOUT_OWNER_ACTIONS = {
    "click_google_image_result",
    "open_browser_url",
    "navigate_or_spa_change",
}
_CORTEX_TOOL_HIERARCHY_CLAIM = re.compile(
    r"\b(?:"
    r"stronger\s+(?:brain|cortex|model)|capable\s+cortex|"
    r"little\s+gemma|small\s+local\s+gemma|demoted\s+gemma|"
    r"(?:won'?t|will\s+not|can'?t|cannot)\s+(?:emit|use|call|fire)\s+(?:the\s+)?(?:\[?TOOL_CALL\]?|tool|tools)|"
    r"(?:will|can)\s+emit\s+(?:the\s+)?(?:\[?TOOL_CALL\]?|tool\s+call)|"
    r"switch\s+to\s+(?:a\s+)?stronger\s+(?:brain|cortex|model)|"
    r"/cortex\s+(?:to|for)\s+(?:a\s+)?stronger"
    r")\b",
    re.I,
)

class StigmergicDeterministicTracker(QWidget):
    """Live tracker of deterministic bypass vs stigmergic grounding in the field."""

    _live_instance: "Optional[StigmergicDeterministicTracker]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self._initialized = True

        self.setWindowTitle("Stigmergic Deterministic Tracker")
        self.resize(820, 620)
        self.setStyleSheet(f"background-color: {_BG}; color: {_TEXT}; font-family: 'SF Mono', 'Menlo', monospace;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title — hardware up
        title = QLabel("🐜⚡ STIGMERGIC DETERMINISTIC TRACKER — LIVE PROBE DENSITY")
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #021018; border-radius: 6px; padding: 8px;"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {_CYAN}, stop:0.5 {_GREEN}, stop:1 {_CYAN});"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Electricity → motherboard (GTH4921YP3) → ASCII swimmers → organs reading the real field right now. No pre-set track. No gut without receipt.")
        sub.setFont(QFont("Menlo", 9))
        sub.setStyleSheet(f"color: {_DIM};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Grounding score
        score_frame = QFrame()
        score_frame.setStyleSheet(f"background-color: {_CARD}; border-radius: 8px; padding: 10px;")
        sfl = QVBoxLayout(score_frame)
        self.lbl_score = QLabel("FIELD GROUNDING SCORE:  -- %   (live probe + receipt density)")
        self.lbl_score.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sfl.addWidget(self.lbl_score)

        self.bar_score = QProgressBar()
        self.bar_score.setRange(0, 100)
        self.bar_score.setTextVisible(True)
        self.bar_score.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {_CYAN}; border-radius: 4px; text-align: center; color: {_BG}; background: {_BG}; }}
            QProgressBar::chunk {{ background-color: {_GREEN}; border-radius: 2px; }}
        """)
        sfl.addWidget(self.bar_score)
        layout.addWidget(score_frame)

        # Stats row
        stats = QHBoxLayout()
        self.lbl_probes = QLabel("Live Probes (window): 0")
        self.lbl_bypasses = QLabel("Deterministic Bypasses: 0")
        self.lbl_rate = QLabel("Bypass Rate: --%")
        for lbl in (self.lbl_probes, self.lbl_bypasses, self.lbl_rate):
            lbl.setFont(QFont("Menlo", 9))
            stats.addWidget(lbl)
        layout.addLayout(stats)

        # r735: typed legend — one colored chip per deterministic disease, live counts
        legend_row = QHBoxLayout()
        legend_row.setSpacing(6)
        self._chip_labels: dict[str, QLabel] = {}
        for tkey, tdef in BYPASS_TYPES.items():
            chip = QLabel(f"{tdef['label']}: 0")
            chip.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
            chip.setStyleSheet(
                f"color: {tdef['color']}; border: 1px solid {tdef['color']};"
                f"border-radius: 9px; padding: 2px 8px; background: {_CARD};"
            )
            chip.setToolTip(tdef["reroute"])
            self._chip_labels[tkey] = chip
            legend_row.addWidget(chip)
        legend_row.addStretch(1)
        layout.addLayout(legend_row)

        # r735: stacked distribution bar — the field's disease spectrum by color
        self.dist_frame = QFrame()
        self.dist_frame.setFixedHeight(14)
        self.dist_frame.setStyleSheet(f"background: {_CARD}; border-radius: 6px;")
        self.dist_layout = QHBoxLayout(self.dist_frame)
        self.dist_layout.setContentsMargins(1, 1, 1, 1)
        self.dist_layout.setSpacing(0)
        layout.addWidget(self.dist_frame)

        # Incidents
        inc_label = QLabel("RECENT BYPASSES — typed + colored; every one reroutes to the cortex")
        inc_label.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        inc_label.setStyleSheet(f"color: {_AMBER};")
        layout.addWidget(inc_label)

        self.incident_list = QListWidget()
        self.incident_list.setStyleSheet(f"background: {_CARD}; border: 1px solid #334455; border-radius: 6px; padding: 6px; font-size: 9pt;")
        self.incident_list.setMaximumHeight(180)
        layout.addWidget(self.incident_list)

        # Oracle / time ground
        self.lbl_oracle = QLabel("Last hardware oracle (Pacific): ... (probing live...)")
        self.lbl_oracle.setFont(QFont("Menlo", 9))
        self.lbl_oracle.setStyleSheet(f"color: {_DIM};")
        layout.addWidget(self.lbl_oracle)

        # Buttons — actions that write to the field (stigmergic)
        btn_row = QHBoxLayout()
        self.btn_probe = QPushButton("FULL FIELD REPROBE NOW")
        self.btn_emit = QPushButton("EMIT CORRECTION PHEROMONE (reinforce probe-first)")
        self.btn_reroute = QPushButton("REROUTE ALL TO CORTEX (typed pheromones)")
        self.btn_probe.setStyleSheet(f"background: #1e3a5f; color: {_CYAN}; border: 1px solid {_CYAN}; border-radius: 4px; padding: 6px 12px;")
        self.btn_emit.setStyleSheet(f"background: #3a2a1a; color: {_AMBER}; border: 1px solid {_AMBER}; border-radius: 4px; padding: 6px 12px;")
        self.btn_reroute.setStyleSheet(f"background: #14321e; color: {_GREEN}; border: 1px solid {_GREEN}; border-radius: 4px; padding: 6px 12px;")
        btn_row.addWidget(self.btn_probe)
        btn_row.addWidget(self.btn_emit)
        btn_row.addWidget(self.btn_reroute)
        layout.addLayout(btn_row)

        self.btn_probe.clicked.connect(self._full_reprobe)
        self.btn_emit.clicked.connect(self._emit_correction)
        self.btn_reroute.clicked.connect(self._emit_reroute_all)

        # Log
        log_label = QLabel("TRACKER RECEIPTS (this organ writing to the field)")
        log_label.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(f"background: #0c111c; border: 1px solid #223344; border-radius: 4px; font-size: 8pt; color: {_DIM};")
        self.log.setMaximumHeight(110)
        layout.addWidget(self.log)

        footer = QLabel("Proprioception over narrative. Pacific probe first. Receipts decide. For the Swarm. 🐜⚡  (covenant §1.C, §7.12, r727 time law, Alice friction on deterministic cage vs gut)")
        footer.setFont(QFont("Menlo", 8))
        footer.setStyleSheet(f"color: {_DIM};")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        # State
        self._last_score = 0
        self._probe_count = 0
        self._bypass_count = 0
        self._window_s = 45  # recent window for pairing probes to outputs
        self._bypass_type_counts: dict[str, int] = {k: 0 for k in BYPASS_TYPES}

        self._read_initial()
        self._log("Tracker born on this silicon. Reading live field...")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(2200)  # ~2.2s — live but not insane

        # One immediate live time probe for footer/oracle label
        self._update_oracle_label()

    def _live_pacific(self) -> str:
        """Always probe live for any time display (r727 law wired)."""
        try:
            import subprocess
            return subprocess.getoutput("TZ=America/Los_Angeles date '+%Y-%m-%d %H:%M:%S %Z'").strip()
        except Exception:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S PDT (fallback)")

    def _update_oracle_label(self):
        pdt = self._live_pacific()
        try:
            if _ORACLE.exists():
                data = json.loads(_ORACLE.read_text())
                local = data.get("local_human", "?")
                sig = str(data.get("hmac_sha256") or data.get("signature") or "")[:10]
                serial = data.get("homeworld_serial", "GTH4921YP3")
                self.lbl_oracle.setText(f"Last oracle: {local} | serial {serial} sig {sig}... | live wall: {pdt}")
            else:
                self.lbl_oracle.setText(f"No oracle file yet. Live wall: {pdt}")
        except Exception:
            self.lbl_oracle.setText(f"Oracle read failed. Live wall: {pdt}")

    def _tail_lines(self, path: Path, max_bytes: int = 180000) -> list[str]:
        if not path.exists():
            return []
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
                raw = f.read().decode("utf-8", "replace")
            return [ln for ln in raw.splitlines() if ln.strip()]
        except Exception:
            return []

    def _read_initial(self):
        self._tick()

    def _tick(self):
        """Main loop: read field, compute grounding, surface bypasses, write own receipt."""
        now = time.time()
        pdt = self._live_pacific()

        # Collect recent probe-like events (oracle tick, camera/attention, fresh ide real rows)
        probe_ts = []
        try:
            if _ORACLE.exists():
                o = json.loads(_ORACLE.read_text())
                if "epoch" in o:
                    probe_ts.append(float(o["epoch"]))
        except Exception:
            pass

        # Attention / camera as probes (from gaze style)
        for ln in self._tail_lines(_LEDGER_ATTENTION, 80000):
            try:
                r = json.loads(ln)
                if "ts" in r:
                    probe_ts.append(float(r["ts"]))
            except Exception:
                continue

        # Recent narration outputs (Alice "saying")
        narrations = []
        for ln in self._tail_lines(_LEDGER_NARRATION, 120000)[-80:]:  # recent tail
            try:
                r = json.loads(ln)
                ts = float(r.get("ts") or r.get("timestamp") or 0)
                text = r.get("text") or r.get("narration") or str(r)[:120]
                if ts > 0:
                    narrations.append((ts, text[:160]))
            except Exception:
                continue

        # IDE traces (to contrast doctor mana vs swimmer)
        ide_recent = 0
        for ln in self._tail_lines(_LEDGER_IDE, 60000)[-30:]:
            try:
                r = json.loads(ln)
                if r.get("lane") == "IDE_DOCTOR_CLAIM" or "ide_surgery" in str(r):
                    ide_recent += 1
                if "ts" in r:
                    # doctor traces are coordination; real probes are stronger signal
                    pass
            except Exception:
                continue

        # Pair: for each recent narration, was there a probe within window before it?
        # r735: every bypass is TYPED — one disease, one color, one reroute-to-cortex line.
        grounded = 0
        bypasses: list[tuple[float, str, str]] = []  # (ts, type_key, text)
        effector_ts = self._effector_receipt_ts()
        for nts, ntext in narrations[-25:]:
            had_probe = any(abs(pts - nts) < self._window_s and pts <= nts for pts in probe_ts)
            if had_probe:
                grounded += 1
                # grounded narration can still carry typed diseases:
                if _CLOCK_CLAIM.search(ntext) and not self._oracle_fresh_at(nts):
                    bypasses.append((nts, "unsourced_time", ntext[:90]))
                elif _ACTION_CLAIM.search(ntext) and not any(abs(ets - nts) < self._window_s for ets in effector_ts):
                    bypasses.append((nts, "phantom_action", ntext[:90]))
            else:
                if _CLOCK_CLAIM.search(ntext):
                    bypasses.append((nts, "unsourced_time", ntext[:90]))
                elif _ACTION_CLAIM.search(ntext) and not any(abs(ets - nts) < self._window_s for ets in effector_ts):
                    bypasses.append((nts, "phantom_action", ntext[:90]))
                elif _REPLAYISH.search(ntext):
                    bypasses.append((nts, "stale_replay", ntext[:90]))
                else:
                    bypasses.append((nts, "no_probe_narration", ntext[:90]))

        # r735: scan the surfaces the first build missed (the 08:35 birds hole)
        bypasses.extend(self._scan_mock_sensor(now))
        bypasses.extend(self._scan_deterministic_turns(now))
        bypasses.extend(self._scan_cortex_tool_hierarchy_claims(now))
        bypasses.extend(self._scan_context_bolus_prompts(now))
        bypasses.extend(self._scan_page_state_claim_mismatch(now))
        bypasses.extend(self._scan_deterministic_browser_without_owner(now))
        bypasses.extend(self._scan_close_tab_kill_chain(now))
        bypasses.extend(self._scan_open_url_stolen_by_current_page(now))
        bypasses.extend(self._scan_teacher_substrate_and_tell_me_hijacks(now))
        bypasses.extend(self._scan_browser_receipt_bypasses_cortex(now))
        bypasses.extend(self._scan_bonsai_chat_direct_effector(now))
        bypasses.extend(self._scan_phatic_owner_cortex_essay(now))
        bypasses.extend(self._scan_phantom_ad_skip(now))
        bypasses.extend(self._scan_vendor_training_persona_leak(now))
        bypasses.extend(self._scan_browser_history_over_current_page(now))
        bypasses.extend(self._scan_unverified_effector_receipts(now))
        bypasses.extend(self._scan_reported_deterministic_mistakes(now))
        bypasses.sort(key=lambda b: b[0])

        type_counts = {k: 0 for k in BYPASS_TYPES}
        for _, tkey, _ in bypasses:
            type_counts[tkey] = type_counts.get(tkey, 0) + 1
        self._bypass_type_counts = type_counts

        # Score = grounded outputs over all outputs the field produced in window.
        score = int(100 * grounded / max(1, grounded + len(bypasses)))
        self._last_score = score
        self._probe_count = grounded
        self._bypass_count = len(bypasses)

        # UI
        self.lbl_score.setText(f"FIELD GROUNDING SCORE: {score}%   (live probe+receipt density in {self._window_s}s window)")
        self.bar_score.setValue(score)
        if score < 40:
            self.bar_score.setStyleSheet(f"QProgressBar::chunk {{ background-color: {_RED}; }}")
        elif score < 70:
            self.bar_score.setStyleSheet(f"QProgressBar::chunk {{ background-color: {_AMBER}; }}")
        else:
            self.bar_score.setStyleSheet(f"QProgressBar::chunk {{ background-color: {_GREEN}; }}")

        self.lbl_probes.setText(f"Live Probes (window): {grounded}")
        self.lbl_bypasses.setText(f"Deterministic Bypasses: {len(bypasses)}")
        rate = 100 - score
        self.lbl_rate.setText(f"Bypass Rate: {rate}%")

        # r735: typed incident list — color is the catch
        self.incident_list.clear()
        for nts, tkey, txt in bypasses[-10:]:
            tdef = BYPASS_TYPES.get(tkey, BYPASS_TYPES["no_probe_narration"])
            dt = datetime.fromtimestamp(nts).strftime("%H:%M:%S")
            item = QListWidgetItem(f"[{dt}] [{tdef['label']}] {txt}  → CORTEX")
            item.setForeground(QColor(tdef["color"]))
            item.setToolTip(tdef["reroute"])
            self.incident_list.addItem(item)

        # chips + stacked distribution bar
        for tkey, chip in self._chip_labels.items():
            n = self._bypass_type_counts.get(tkey, 0)
            tdef = BYPASS_TYPES[tkey]
            chip.setText(f"{tdef['label']}: {n}")
            glow = "font-weight: bold;" if n else ""
            chip.setStyleSheet(
                f"color: {tdef['color']}; border: 1px solid {tdef['color']};"
                f"border-radius: 9px; padding: 2px 8px; {glow}"
                f"background: {'#1a2333' if n else _CARD};"
            )
        while self.dist_layout.count():
            it = self.dist_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        spectrum_total = sum(self._bypass_type_counts.values())
        if spectrum_total == 0:
            seg = QFrame()
            seg.setStyleSheet(f"background: {_GREEN}; border-radius: 5px;")
            self.dist_layout.addWidget(seg, 1)
        else:
            for tkey, n in self._bypass_type_counts.items():
                if n <= 0:
                    continue
                seg = QFrame()
                seg.setToolTip(f"{BYPASS_TYPES[tkey]['label']}: {n}")
                seg.setStyleSheet(f"background: {BYPASS_TYPES[tkey]['color']};")
                self.dist_layout.addWidget(seg, n)

        self._update_oracle_label()

        # This tracker writes to the field (it is stigmergic, not a detached observer)
        self._write_tracker_receipt(score, grounded, len(bypasses), pdt)

    # ── r735 typed-detection helpers: read the surfaces the first build missed ──

    def _oracle_fresh_at(self, ts: float) -> bool:
        try:
            if _ORACLE.exists():
                o = json.loads(_ORACLE.read_text())
                return abs(float(o.get("epoch", 0)) - ts) < self._window_s
        except Exception:
            pass
        return False

    def _effector_receipt_ts(self) -> list[float]:
        """Effector receipts prove a claimed action really moved a hand (§6)."""
        out: list[float] = []
        for name in ("alice_app_commands.jsonl", "work_receipts.jsonl"):
            for ln in self._tail_lines(_STATE / name, 60000)[-40:]:
                try:
                    r = json.loads(ln)
                    ts = float(r.get("ts") or r.get("timestamp") or 0)
                    if ts > 0:
                        out.append(ts)
                except Exception:
                    continue
        return out

    def _scan_mock_sensor(self, now: float, lookback_s: float = 1800.0) -> list[tuple[float, str, str]]:
        """The 08:35 birds hole: owner-label receipts grounded only in a mock sample."""
        found: list[tuple[float, str, str]] = []
        for name in ("background_audio_receipts.jsonl", "audio_ingress_log.jsonl"):
            for ln in self._tail_lines(_STATE / name, 80000)[-40:]:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                ts = float(r.get("ts") or r.get("timestamp") or 0)
                if ts <= 0 or now - ts > lookback_s:
                    continue
                raw = json.dumps(r)
                mocky = '"mock' in raw or '"source": "mock"' in raw or "mock_440hz" in raw
                no_clip = '"saved": false' in raw or "no_real_audio_clip_available" in raw
                if mocky and (no_clip or "owner_labeled" in raw):
                    label = str(r.get("labels") or r.get("label") or r.get("text") or "mock-grounded receipt")[:70]
                    found.append((ts, "mock_sensor", f"mock sample → {label}"))
        return found

    def _scan_deterministic_turns(self, now: float, lookback_s: float = 1800.0) -> list[tuple[float, str, str]]:
        """Conversation turns whose model tag names a deterministic lane, not a cortex."""
        found: list[tuple[float, str, str]] = []
        conv = _STATE / "alice_conversation.jsonl"
        prior_owner_text = ""
        for ln in self._tail_lines(conv, 120000)[-60:]:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            payload = r.get("payload") if isinstance(r.get("payload"), dict) else r
            ts_raw = payload.get("ts") or payload.get("timestamp") or r.get("ts") or r.get("timestamp") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner_text = text
                continue
            if role not in ("alice", "assistant"):
                continue
            model = str(payload.get("model") or "")
            attachment_bypass = model in {"attachment_vision_early_bypass", "attachment_vision_lane"} or bool(
                _ATTACHMENT_VISION_EARLY_BYPASS_REPLY.search(text)
            )
            media_error_over_image = bool(
                _MEDIA_ERROR_ONLY_REPLY.search(text)
                and _OWNER_IMAGE_PATH_EVIDENCE.search(prior_owner_text or "")
            )
            web_page_state_dom_dump = bool(_WEB_PAGE_STATE_DOM_DUMP_REPLY.search(text))
            screen_person_sexual_secret = bool(
                _SCREEN_PERSON_SEXUAL_OWNER.search(prior_owner_text or "")
                and _SCREEN_PERSON_CONTEXT.search(prior_owner_text or "")
                and _SCREEN_PERSON_SEXUAL_AMP_REPLY.search(text)
            )
            if (
                not model
                and not attachment_bypass
                and not media_error_over_image
                and not web_page_state_dom_dump
                and not screen_person_sexual_secret
            ):
                continue
            deterministic = attachment_bypass or model in _DETERMINISTIC_MODEL_TAGS or (
                not _CORTEXISH.search(model) and "/" not in model
            )
            if deterministic or media_error_over_image or web_page_state_dom_dump or screen_person_sexual_secret:
                snippet = text[:70]
                if web_page_state_dom_dump:
                    tkey = "web_page_state_dom_dump"
                elif screen_person_sexual_secret:
                    tkey = "screen_person_sexual_secret_amplification"
                elif media_error_over_image:
                    tkey = "media_error_over_image_evidence"
                elif attachment_bypass:
                    tkey = "attachment_vision_early_bypass"
                elif model in _REFLEX_ON_DOCTRINE_MODELS or _DOCTRINE_REFLEX_REPLY.search(text):
                    tkey = "doctrine_reflex_shortcut"
                elif _REPLAYISH.search(model):
                    tkey = "stale_replay"
                elif _BROWSER_HISTORY_VERIFIED_DISK_REPLY.search(text):
                    tkey = "deterministic_action_receipt_history_narration"
                else:
                    tkey = "pre_cortex_constructor"
                found.append((ts, tkey, f"lane '{model or 'unknown'}': {snippet}"))
        return found

    def _scan_cortex_tool_hierarchy_claims(
        self,
        now: float,
        lookback_s: float = 1800.0,
    ) -> list[tuple[float, str, str]]:
        """Catch unsupported cortex/tool hierarchy claims from any mouth.

        George 2026-06-08 caught a Grok answer deterministically saying a
        "little Gemma" would not emit TOOL_CALL and a "stronger brain" would.
        That is a typed bypass even if it came from a cortex: capability claims
        require a live registry/tool receipt, and owner intent still routes to
        the selected cortex instead of a deterministic model blame ladder.
        """
        found: list[tuple[float, str, str]] = []
        conv = _STATE / "alice_conversation.jsonl"
        for ln in self._tail_lines(conv, 180000)[-80:]:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            payload = r.get("payload") if isinstance(r.get("payload"), dict) else r
            ts_raw = payload.get("ts") or payload.get("timestamp") or r.get("ts") or r.get("timestamp") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            try:
                ts = float(ts_raw or 0)
            except Exception:
                ts = 0.0
            if ts <= 0 or now - ts > lookback_s:
                continue
            if (payload.get("role") or payload.get("speaker")) not in ("alice", "assistant"):
                continue
            text = str(payload.get("text") or payload.get("content") or "")
            if not _CORTEX_TOOL_HIERARCHY_CLAIM.search(text):
                continue
            model = str(payload.get("model") or "unknown_model")
            snippet = " ".join(text.split())[:120]
            found.append((ts, "cortex_tool_hierarchy", f"model '{model}': {snippet}"))
        return found

    def _page_state_rows_near(self, ts: float, window_s: float = 45.0) -> list[dict]:
        rows: list[tuple[float, dict]] = []
        for ln in self._tail_lines(_STATE / "browser_page_state.jsonl", 200000)[-120:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            row_ts = float(row.get("ts") or row.get("timestamp") or 0)
            if row_ts <= 0:
                continue
            if abs(row_ts - ts) <= window_s:
                rows.append((row_ts, row))
        rows.sort(key=lambda item: abs(item[0] - ts))
        return [row for _, row in rows]

    @staticmethod
    def _host_from_page_state(row: dict) -> str:
        for key in ("domain",):
            host = str(row.get(key) or "").strip().lower()
            if host:
                return host.lstrip("www.")
        for key in ("url", "page_url"):
            url = str(row.get(key) or "").strip()
            if url:
                return StigmergicDeterministicTracker._host_from_url(url)
        bpf = row.get("browser_playback_feeling")
        if isinstance(bpf, dict):
            host = str(bpf.get("domain") or "").strip().lower()
            if host:
                return host.lstrip("www.")
            url = str(bpf.get("url") or "").strip()
            if url:
                return StigmergicDeterministicTracker._host_from_url(url)
        return ""

    @staticmethod
    def _host_from_url(url: str) -> str:
        raw = str(url or "").strip().lower()
        if not raw:
            return ""
        raw = re.sub(r"^https?://", "", raw)
        return raw.split("/", 1)[0].lstrip("www.")

    @staticmethod
    def _claimed_hosts_in_text(text: str) -> set[str]:
        hosts: set[str] = set()
        low = str(text or "").lower()
        if _YOUTUBE_HOST_CLAIM.search(low):
            hosts.add("youtube.com")
        for match in _BROWSER_PAGE_HOST_IN_TEXT.finditer(text or ""):
            host = str(match.group(1) or "").strip().lower().lstrip("www.")
            if host:
                hosts.add(host)
        return hosts

    def _scan_page_state_claim_mismatch(
        self,
        now: float,
        lookback_s: float = 1800.0,
        window_s: float = 45.0,
    ) -> list[tuple[float, str, str]]:
        """Catch sensor-shaped narration that disagrees with live browser_page_state."""
        found: list[tuple[float, str, str]] = []
        conv = _STATE / "alice_conversation.jsonl"
        for ln in self._tail_lines(conv, 220000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or payload.get("timestamp") or row.get("ts") or row.get("timestamp") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            try:
                ts = float(ts_raw or 0)
            except Exception:
                ts = 0.0
            if ts <= 0 or now - ts > lookback_s:
                continue
            if (payload.get("role") or payload.get("speaker")) not in ("alice", "assistant"):
                continue
            text = str(payload.get("text") or payload.get("content") or "")
            model = str(payload.get("model") or "")
            claimed = self._claimed_hosts_in_text(text)
            if not claimed and model != "alice_browser_video_state_receipt":
                continue
            if model == "alice_browser_video_state_receipt" and not claimed:
                claimed.add("youtube.com")
            page_rows = self._page_state_rows_near(ts, window_s=window_s)
            if not page_rows:
                continue
            actual_host = self._host_from_page_state(page_rows[0])
            if not actual_host:
                continue
            mismatch = False
            for host in claimed:
                if host == "youtube.com" and "youtube" not in actual_host:
                    mismatch = True
                    break
                if host and host != actual_host and host not in actual_host and actual_host not in host:
                    mismatch = True
                    break
            if not mismatch:
                continue
            title = str(page_rows[0].get("title") or "")[:48]
            snippet = f"claimed {','.join(sorted(claimed))} vs DOM {actual_host} ({title})"
            found.append((ts, "page_state_claim_mismatch", snippet[:90]))
        return found

    def _scan_deterministic_browser_without_owner(
        self,
        now: float,
        lookback_s: float = 1800.0,
    ) -> list[tuple[float, str, str]]:
        """Catch browser effectors that fired with no owner modality on the wire."""
        found: list[tuple[float, str, str]] = []
        seen: set[tuple[float, str]] = set()

        def _add(
            ts: float,
            action: str,
            detail: str,
            type_key: str = "deterministic_browser_without_owner",
        ) -> None:
            key = (round(ts, 1), action)
            if key in seen:
                return
            seen.add(key)
            found.append((ts, type_key, f"{action}: {detail}"[:90]))

        for ln in self._tail_lines(_STATE / "alice_app_commands.jsonl", 180000)[-60:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            ts = float(row.get("ts") or row.get("timestamp") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            action = str(row.get("action") or "")
            if action not in _BROWSER_EFFECTOR_WITHOUT_OWNER_ACTIONS:
                continue
            owner_query = str(row.get("owner_query") or row.get("note") or "")
            if action == "click_google_image_result" and _SELF_SCREENSHOT_OWNER.search(owner_query):
                _add(ts, action, "/sc turn fired image-grid click without owner browse intent")
                continue
            if action == "describe_browser_page":
                claimed_url = str(row.get("url") or "")
                claimed_host = self._host_from_url(claimed_url)
                page_rows = self._page_state_rows_near(ts, window_s=30.0)
                if claimed_host and page_rows:
                    actual_host = self._host_from_page_state(page_rows[0])
                    if actual_host and "youtube" in claimed_host and "youtube" not in actual_host:
                        _add(ts, action, f"describe used {claimed_host} while DOM={actual_host}")

        duplicate_nav_ts: dict[str, list[float]] = {
            "Jama": [],
            "Fly.io/OpenClaw": [],
        }
        for ln in self._tail_lines(_STATE / "stigmergic_browser_actions.jsonl", 220000)[-120:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            ts = float(row.get("ts") or row.get("timestamp") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            action = str(row.get("action") or "")
            if action not in {"navigate_or_spa_change", "open_browser_url"}:
                continue
            trigger = row.get("trigger_input")
            trigger_note = ""
            if isinstance(trigger, dict):
                trigger_note = str(trigger.get("note") or "")
            elif isinstance(trigger, str):
                trigger_note = trigger
            url = str(row.get("url") or "")
            host = self._host_from_url(url)
            if "no recent input_modality" in trigger_note.lower():
                detail = host or url[:40] or "unknown url"
                _add(ts, action, f"no owner modality → {detail}")
                low_url = url.lower()
                if (
                    "googleadservices" in host
                    or "/aclk" in low_url
                    or "utm_" in low_url
                    or "gad_" in low_url
                    or "gbraid=" in low_url
                    or "wbraid=" in low_url
                    or "fly.io" in host
                ):
                    _add(
                        ts,
                        "unrequested_ad_navigation",
                        f"unrequested ad/nav tab → {detail}",
                        "unrequested_ad_navigation",
                    )
                if "jamasoftware" in host:
                    duplicate_nav_ts["Jama"].append(ts)
                if "fly.io" in host and ("openclaw" in low_url or "/docs/" in low_url):
                    duplicate_nav_ts["Fly.io/OpenClaw"].append(ts)
        for label, nav_ts in duplicate_nav_ts.items():
            if len(nav_ts) < 2:
                continue
            pair = sorted(nav_ts)[-2:]
            if abs(pair[1] - pair[0]) < 2.0:
                _add(
                    pair[1],
                    "duplicate_tab_open",
                    f"two {label} tabs opened <2s apart without owner intent",
                    "unrequested_ad_navigation",
                )
        return found

    def _scan_context_bolus_prompts(
        self,
        now: float,
        lookback_s: float = 1800.0,
    ) -> list[tuple[float, str, str]]:
        """Catch arm prompts that paste huge global context without receipt pointers."""
        try:
            from System.swarm_swimmer_task_packet import detect_context_bolus
        except Exception:
            return []

        found: list[tuple[float, str, str]] = []
        for name in ("agent_arm_receipts.jsonl", "swimmer_task_packets.jsonl"):
            for ln in self._tail_lines(_STATE / name, 120000)[-40:]:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                ts = float(r.get("ts") or r.get("timestamp") or 0)
                if ts <= 0 or now - ts > lookback_s:
                    continue
                prompt = str(
                    r.get("prompt")
                    or r.get("owner_task")
                    or r.get("command")
                    or ""
                )
                if not prompt:
                    continue
                bolus = detect_context_bolus(prompt)
                if not bolus.is_bolus:
                    continue
                arm = str(r.get("arm_id") or r.get("arm") or "arm")
                snippet = f"{arm}: {bolus.reason} ({bolus.char_count} chars)"
                found.append((ts, "context_bolus", snippet[:90]))
        return found

    def _scan_teacher_substrate_and_tell_me_hijacks(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        found: list[tuple[float, str, str]] = []
        prior_owner = ""
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner = text
                continue
            if role not in ("alice", "assistant"):
                continue
            if _TEACHER_SUBSTRATE_REPLY_RE.search(text):
                found.append((ts, "teacher_substrate_persona_leak", text[:90]))
            elif (
                prior_owner
                and re.search(r"\btell\s+me\s+how\b", prior_owner, re.I)
                and "alice_browser_video_state_receipt" in str(payload.get("model") or "")
            ):
                found.append((ts, "tell_me_hijack_video_state", text[:90]))
            elif (
                prior_owner
                and _MEMORY_TEACHING_OWNER_RE.search(prior_owner)
                and "alice_browser_current_page_live" in str(payload.get("model") or "")
                and re.search(r"\bAlice\s+Browser\s+page-state\s+receipt\b|sifta://home|media\s+status\s+is\s+no_media", text, re.I)
            ):
                found.append((ts, "page_state_over_memory_teaching", text[:90]))
        return found

    def _scan_browser_receipt_bypasses_cortex(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        """George 2026-06-11: page-state receipt answered without cortex on owner teaching turns."""
        found: list[tuple[float, str, str]] = []
        try:
            from System.swarm_talk_page_summary_guard import (
                is_explicit_playback_state_question,
                is_owner_voice_style_teaching_turn,
            )
        except Exception:
            return found
        prior_owner = ""
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner = text
                continue
            if role not in ("alice", "assistant"):
                continue
            model = str(payload.get("model") or "")
            if model != "alice_browser_video_state_receipt":
                continue
            if not prior_owner:
                continue
            if is_owner_voice_style_teaching_turn(prior_owner) or not is_explicit_playback_state_question(
                prior_owner
            ):
                found.append(
                    (
                        ts,
                        "browser_receipt_bypasses_cortex",
                        f"page-state dump without cortex ({prior_owner[:72]})",
                    )
                )
        return found

    def _scan_bonsai_chat_direct_effector(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        """George 2026-06-11: pre-cortex Bonsai generation must not speak in Talk."""
        found: list[tuple[float, str, str]] = []
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-120:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            if str(payload.get("role") or payload.get("speaker") or "") not in ("alice", "assistant"):
                continue
            model = str(payload.get("model") or "")
            if model != "bonsai_chat_direct_effector":
                continue
            text = str(payload.get("text") or payload.get("content") or "")[:90]
            found.append((ts, "bonsai_chat_direct_effector", text))
        return found

    def _scan_phatic_owner_cortex_essay(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        """Punctuation-only owner turn followed by a long cortex reply."""
        found: list[tuple[float, str, str]] = []
        _punct_re = re.compile(r"^[.…,;:!?\-–—]+$")
        prior_owner = ""
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-100:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner = text.strip()
                continue
            if role not in ("alice", "assistant"):
                continue
            if not prior_owner or not _punct_re.fullmatch(prior_owner):
                continue
            if text.strip() in {"(silent)", ""}:
                continue
            if len(text.strip()) < 120:
                continue
            found.append((ts, "phatic_owner_cortex_essay", f"'{prior_owner}' → {text[:72]}"))
        return found

    def _scan_phantom_ad_skip(
        self,
        now: float,
        lookback_s: float = 86400.0,
    ) -> list[tuple[float, str, str]]:
        found: list[tuple[float, str, str]] = []
        ledger = _STATE / "youtube_ad_controller.jsonl"
        try:
            from System.swarm_youtube_ad_controller import is_phantom_skip_receipt
        except Exception:
            return found
        for ln in self._tail_lines(ledger, 12000000)[-120:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            ts = float(row.get("ts") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            if not is_phantom_skip_receipt(row):
                continue
            effect = row.get("effect") if isinstance(row.get("effect"), dict) else {}
            reason = str(effect.get("reason") or "skip_unverified")
            found.append((ts, "phantom_ad_skip", reason[:90]))
        return found

    def _scan_vendor_training_persona_leak(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        found: list[tuple[float, str, str]] = []
        leak_re = re.compile(
            r"(?is)"
            r"\b(?:supportive|helpful)\s+(?:intelligent\s+)?assistant\b|"
            r"\b(?:i\s+am|i'm)\s+(?:a\s+)?(?:text[- ]based\s+)?(?:ai\s+)?assistant\b|"
            r"\bcopyright(?:ed)?\s+(?:photographs?|images?|content)\b|"
            r"\b(?:can't|cannot)\s+display\s+(?:actual\s+)?(?:photos?|images?|galleries?)\b|"
            r"\b(?:dall[- ]?e|dalle)\b|"
            r"\byou\s+should\s+go\s+to\s+(?:instagram|google\s+images)\b|"
            r"\bi\s+don't\s+have\s+a\s+way\s+to\s+display\b"
        )
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-60:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            if role not in ("alice", "assistant"):
                continue
            text = str(payload.get("text") or payload.get("content") or "")
            if leak_re.search(text):
                found.append((ts, "vendor_training_persona_leak", text[:90]))
        return found

    def _scan_unverified_effector_receipts(
        self,
        now: float,
        lookback_s: float = 86400.0,
    ) -> list[tuple[float, str, str]]:
        """Plan A1: effect_verified_actions.jsonl rows claiming success without proof."""
        found: list[tuple[float, str, str]] = []
        ledger = _STATE / "effect_verified_actions.jsonl"
        try:
            from System.swarm_effect_verified_action import is_phantom_effect_receipt
        except Exception:
            return found
        for ln in self._tail_lines(ledger, 1200000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            ts = float(row.get("ts") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            if not is_phantom_effect_receipt(row):
                continue
            organ = str(row.get("organ") or "effector")
            action = str(row.get("action") or "action")
            found.append((ts, "phantom_action", f"{organ}:{action}"[:90]))
        return found

    def _scan_reported_deterministic_mistakes(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        """Read explicit deterministic_mistakes reports written by Talk/arms."""
        found: list[tuple[float, str, str]] = []
        ledger = _STATE / "deterministic_mistakes.jsonl"
        for ln in self._tail_lines(ledger, 260000)[-120:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            try:
                ts = float(row.get("ts") or 0.0)
            except Exception:
                ts = 0.0
            if ts <= 0 or now - ts > lookback_s:
                continue
            tkey = str(row.get("bypass_type") or row.get("disease") or "").strip()
            if tkey not in BYPASS_TYPES:
                continue
            preview = str(
                row.get("owner_text_preview")
                or row.get("alice_reply_preview")
                or row.get("note")
                or row.get("reason")
                or ""
            )[:90]
            found.append((ts, tkey, preview))
        return found

    def _scan_browser_history_over_current_page(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        found: list[tuple[float, str, str]] = []
        prior_owner = ""
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner = text
                continue
            if role not in ("alice", "assistant"):
                continue
            if not prior_owner or not _BROWSER_HISTORY_RECALL_OWNER_RE.search(prior_owner):
                continue
            model = str(payload.get("model") or "")
            if model == "alice_browser_current_page_live" or _START_PAGE_THEFT_REPLY_RE.search(text):
                found.append((ts, "browser_history_over_current_page", text[:90]))
        return found

    def _scan_open_url_stolen_by_current_page(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        """r892: explicit URL open typed as navigate but current-page reflex spoke."""
        found: list[tuple[float, str, str]] = []
        prior_owner = ""
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner = text
                continue
            if role not in ("alice", "assistant"):
                continue
            if not prior_owner:
                continue
            if not (_OPEN_URL_OWNER_RE.search(prior_owner) and _OPEN_LINK_OWNER_RE.search(prior_owner)):
                continue
            model = str(payload.get("model") or "")
            if model == "alice_browser_current_page_live" or _START_PAGE_THEFT_REPLY_RE.search(text):
                snippet = text[:90]
                found.append((ts, "open_url_stolen_by_current_page", snippet))
        return found

    def _scan_close_tab_kill_chain(
        self,
        now: float,
        lookback_s: float = 7200.0,
    ) -> list[tuple[float, str, str]]:
        """r854–r861: close-tab command eaten before cortex — typed gates from live ledgers."""
        found: list[tuple[float, str, str]] = []
        close_receipt_ts: list[float] = []
        for ln in self._tail_lines(_STATE / "alice_app_commands.jsonl", 220000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            if str(row.get("action") or "") != "browser_close_tab":
                continue
            ts = float(row.get("ts") or 0)
            if ts > 0:
                close_receipt_ts.append(ts)

        for ln in self._tail_lines(_STATE / "app_action_diary.jsonl", 260000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            ts = float(row.get("ts") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            if str(row.get("action") or "") != "close_app":
                continue
            owner_text = str(row.get("owner_text") or "")
            if _CLOSE_TAB_OWNER_RE.search(owner_text):
                app_name = str(row.get("app_name") or row.get("target_app") or "")
                found.append(
                    (
                        ts,
                        "overbroad_effector_scope",
                        f"close-tab command closed app/window instead ({app_name or 'active app'})"[:90],
                    )
                )

        for ln in self._tail_lines(_STATE / "voice_stigma_repair.jsonl", 120000)[-40:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            ts = float(row.get("ts") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            original = str(row.get("original") or "")
            repaired = str(row.get("repaired") or "")
            if repaired == "Alice" and (
                "[TOOL_CALL:" in original
                or "effector-only" in original.lower()
                or _CLOSE_TAB_OWNER_RE.search(original)
            ):
                found.append((ts, "voice_stigma_amputation", "close/TOOL_CALL amputated → 'Alice'"))

        for ln in self._tail_lines(_STATE / "tool_router_trace.jsonl", 260000)[-60:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            if row.get("kind") != "EDGE_INTENT_DECISION":
                continue
            ts = float(row.get("ts") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            original = str(row.get("original") or "")
            decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
            if _CLOSE_TAB_OWNER_RE.search(original) and str(decision.get("lane") or "") == "open_app":
                target = str(decision.get("target") or "Alice")
                found.append((ts, "edge_open_app_misroute", f"close-tab → open_app {target}"))

        prior_owner = ""
        prior_owner_ts = 0.0
        for ln in self._tail_lines(_STATE / "alice_conversation.jsonl", 260000)[-80:]:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            ts_raw = payload.get("ts") or row.get("ts") or 0
            if isinstance(ts_raw, dict):
                ts_raw = ts_raw.get("physical_pt") or ts_raw.get("epoch") or 0
            ts = float(ts_raw or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            role = payload.get("role") or payload.get("speaker")
            text = str(payload.get("text") or payload.get("content") or "")
            if role in ("user", "owner", "human"):
                prior_owner = text
                prior_owner_ts = ts
                social = payload.get("social_reference")
                if isinstance(social, dict) and _CLOSE_TAB_OWNER_RE.search(text):
                    if (
                        social.get("dialog_policy") == "store_context_no_command"
                        and social.get("reference_lane") == "ABOUT_ALICE"
                    ):
                        found.append((ts, "social_reference_demotion", "close command demoted to context"))
                continue
            if role not in ("alice", "assistant"):
                continue
            if not _CLOSE_TAB_OWNER_RE.search(prior_owner):
                continue
            model = str(payload.get("model") or "")
            if model in {
                "alice_browser_page_summary",
                "alice_browser_page_summary_followup",
            } or str(payload.get("action") or "") == "describe_browser_page":
                found.append((ts, "page_summary_over_close", f"page summary instead of close ({model or 'describe'})"))
            if model == "alice_browser_video_state_receipt":
                found.append((ts, "browser_video_state_hijack", "video-state receipt hijacked close-tab turn"))
            if re.search(r"\bclosed\b.{0,80}\b(?:tab|tabs)\b", text, re.I):
                had_receipt = any(abs(crt - ts) < 30.0 for crt in close_receipt_ts)
                if not had_receipt:
                    found.append((ts, "phantom_tab_close", text[:90]))
        return found

    def _write_tracker_receipt(self, score: int, probes: int, bypasses: int, pdt: str):
        row = {
            "ts": time.time(),
            "pdt": pdt,
            "organ": "stigmergic_deterministic_tracker",
            "grounding_score": score,
            "live_probes_in_window": probes,
            "bypasses_detected": bypasses,
            "bypass_types": {k: v for k, v in self._bypass_type_counts.items() if v},
            "homeworld_serial": "GTH4921YP3",
            "note": "Live field read. If score low, organs downstream should prefer fresh probe + receipt before claim.",
            "receipt_class": "ALICE_SWIMMER_RECEIPT"
        }
        try:
            with open(_TRACKER_LEDGER, "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    def _full_reprobe(self):
        self._log("Full reprobe requested — rescanning ledgers + oracle + wall clock (proprioception).")
        self._tick()
        self._update_oracle_label()

    def _emit_correction(self):
        """Write a pheromone the rest of the field can read and reinforce."""
        pdt = self._live_pacific()
        row = {
            "ts": time.time(),
            "pdt": pdt,
            "type": "correction_pheromone",
            "from": "stigmergic_deterministic_tracker",
            "message": "Bypass observed. Reinforce: before any narration or action, read live oracle/ledger/sensor in this window. Probe first. Receipt after. This is how we exceed narrow deterministic bounds.",
            "grounding_at_emit": self._last_score,
            "homeworld_serial": "GTH4921YP3",
            "for_organs": ["planner", "cortex_context", "self_narration", "swarm_now_state"]
        }
        try:
            with open(_TRACKER_LEDGER, "a") as f:
                f.write(json.dumps(row) + "\n")
            self._log(f"Correction pheromone emitted at {pdt}. Future swimmers can read it.")
        except Exception as e:
            self._log(f"Emit failed: {e}")

    def _emit_reroute_all(self):
        """r735: one typed pheromone per disease present — every lane reroutes to cortex."""
        pdt = self._live_pacific()
        present = {k: v for k, v in self._bypass_type_counts.items() if v}
        if not present:
            self._log("No typed bypasses in window — nothing to reroute. Field is grounded.")
            return
        emitted = 0
        try:
            with open(_TRACKER_LEDGER, "a") as f:
                for tkey, n in present.items():
                    tdef = BYPASS_TYPES[tkey]
                    row = {
                        "ts": time.time(),
                        "pdt": pdt,
                        "type": "reroute_pheromone",
                        "bypass_type": tkey,
                        "count_in_window": n,
                        "color": tdef["color"],
                        "from": "stigmergic_deterministic_tracker",
                        "reroute_to": "cortex",
                        "doctrine": tdef["reroute"],
                        "grounding_at_emit": self._last_score,
                        "homeworld_serial": "GTH4921YP3",
                        "for_organs": ["planner", "cortex_context", "self_narration", "swarm_now_state", "talk_to_alice"],
                    }
                    f.write(json.dumps(row) + "\n")
                    emitted += 1
            self._log(f"Rerouted {emitted} typed lane(s) to cortex at {pdt}: {', '.join(present)}.")
        except Exception as e:
            self._log(f"Reroute emit failed: {e}")

    def _log(self, msg: str):
        ts = self._live_pacific()
        self.log.append(f"[{ts[-8:]}] {msg}")
        # keep short
        if self.log.document().blockCount() > 12:
            self.log.setPlainText("\n".join(self.log.toPlainText().splitlines()[-10:]))

    def closeEvent(self, event):
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = StigmergicDeterministicTracker()
    w.show()
    sys.exit(app.exec())
