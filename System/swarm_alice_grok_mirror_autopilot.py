#!/usr/bin/env python3
"""Continuous Alice Browser Grok ↔ Global Chat mirror autopilot.

George law: Alice and website Grok chat in the browser without terminal Grok
interference. This organ only watches for new Grok replies and stages:
  COPY (browser hand) → paste clipboard (Talk mirror)

Talk owns Alice's reply composition. When a Grok mirror lands, Talk may claim
that mirror as a brain input, then copy Alice's delivered reply back to the
Alice Browser composer with receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_GROK_MIRROR_AUTOPILOT_V1"
FLAG_FILE = "alice_grok_mirror_autopilot.flag"
STATE_FILE = "alice_grok_mirror_autopilot_state.json"
PULSE_LEDGER = "alice_grok_mirror_autopilot_pulse.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PAGE_SNAPSHOT = "alice_browser_current_page.json"
_COPY_COMMAND = "alice_browser_grok_copy_command.json"
_PASTE_COMMAND = "alice_talk_paste_clipboard_command.json"
_COPY_RESULTS = "alice_browser_grok_copy_results.jsonl"
_PASTE_RESULTS = "alice_talk_paste_clipboard_results.jsonl"
_SELF_TYPE_COMMAND = "alice_browser_grok_self_type_command.json"
_SELF_TYPE_RESULTS = "alice_browser_grok_self_type_results.jsonl"

_STABLE_S = 3.0
_GROK_URL_NEEDLE = "grok.com/c/"
_DEFAULT_GROK_CHAT_URL = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b"
_COACHING_LINE_RE = re.compile(
    r"(website grok|alice browser|global chat|george sees|i will type|compose one|no coaching)",
    re.IGNORECASE,
)


def configured_grok_chat_url(state_dir: Optional[Path | str] = None) -> str:
    """Mission URL first, current Grok chat page second, old default last."""
    sd = state_dir_path(state_dir)
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if mission_path.exists():
        try:
            data = json.loads(mission_path.read_text(encoding="utf-8"))
            url = str(data.get("grok_url") or "").strip()
            if _GROK_URL_NEEDLE in url:
                return url
        except Exception:
            pass
    page = _page_snapshot(sd)
    url = str(page.get("url") or "").strip()
    if _GROK_URL_NEEDLE in url:
        return url
    return _DEFAULT_GROK_CHAT_URL


def _mission_thread_redirect_if_needed(sd: Path, current_url: str) -> Optional[dict[str, Any]]:
    # Never yank the forager off a non-Grok surface (e.g. deepai.org) back to grok.com.
    if _GROK_URL_NEEDLE not in str(current_url or ""):
        return None
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if not mission_path.exists():
        return None
    try:
        mission = json.loads(mission_path.read_text(encoding="utf-8"))
        target_url = str(mission.get("grok_url") or "").strip()
    except Exception:
        target_url = ""
    if _GROK_URL_NEEDLE not in target_url:
        return None
    try:
        from System.swarm_alice_browser_grok_paste_clipboard import (
            grok_thread_id,
            needs_target_thread_navigation,
        )

        current_thread = grok_thread_id(current_url)
        target_thread = grok_thread_id(target_url)
        if not target_thread:
            return None
        if current_thread and not needs_target_thread_navigation(current_url, target_url):
            return None
    except Exception:
        if target_url in str(current_url or ""):
            return None
    home_return: dict[str, Any] = {}
    try:
        from System.swarm_internet_forager_home_vector import request_return_home

        home_return = request_return_home(
            current_page={
                "url": str(current_url or ""),
                "title": "Alice Browser current page",
                "text": "mission thread redirect orientation",
            },
            state_dir=sd,
        )
    except Exception as exc:
        home_return = {"home_vector_error": f"{type(exc).__name__}: {exc}"}
    if home_return.get("return_command_written"):
        return {
            "action": "wrong_grok_thread_navigating_to_mission",
            "current_url": str(current_url or ""),
            "target_url": str(home_return.get("home_url") or target_url),
            "home_vector_status": home_return.get("status"),
            "home_vector_confidence": home_return.get("confidence"),
            "home_vector_receipt_id": home_return.get("receipt_id"),
            "return_mode": "internet_forager_home_vector",
        }
    try:
        (sd / "alice_browser_open_url.txt").write_text(target_url, encoding="utf-8")
    except Exception:
        pass
    return {
        "action": "wrong_grok_thread_navigating_to_mission",
        "current_url": str(current_url or ""),
        "target_url": target_url,
        "home_vector_status": home_return.get("status"),
        "home_vector_error": home_return.get("home_vector_error"),
        "return_mode": "mission_url_fallback",
    }


def extract_alice_browser_reply_text(cortex_raw: str) -> str:
    """First natural reply line from Alice cortex — for browser composer, not coaching."""
    raw = str(cortex_raw or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"\[SELF_[^\]]+\][\s\S]*?\[/SELF_[^\]]+\]", " ", raw)
    raw = re.sub(r"\[[A-Z0-9_]+:[^\]]*\]", " ", raw)
    raw = re.split(r"\n\s*After thinking,\s*I executed the real body action:", raw, maxsplit=1)[0].strip()
    raw = re.split(r"\n\s*No action receipt yet:", raw, maxsplit=1)[0].strip()
    raw = re.sub(r"\*\*", "", raw)
    lines: list[str] = []
    for ln in raw.splitlines():
        clean = " ".join(ln.split()).strip()
        if not clean or _COACHING_LINE_RE.search(clean):
            continue
        if clean.startswith("(") and clean.endswith(")"):
            continue
        lines.append(clean)
    if not lines:
        clean = " ".join(raw.split())
        return clean[:1200]
    return " ".join(lines[:3])[:1200]


def grok_mirror_reply_budget(state_dir: Optional[Path | str] = None) -> int:
    """How many Grok mirrors may trigger Alice browser replies (default 3)."""
    sd = state_dir_path(state_dir)
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if mission_path.exists():
        try:
            data = json.loads(mission_path.read_text(encoding="utf-8"))
            return int(data.get("target_rounds") or data.get("target_grok_replies") or 3)
        except Exception:
            pass
    return 3


def grok_dialogue_continuous_until_stopped(state_dir: Optional[Path | str] = None) -> bool:
    """True when the Browser Grok loop is owner-stopped rather than round-capped."""
    sd = state_dir_path(state_dir)
    state = _load_state(sd)
    if bool(state.get("continuous_until_stopped")):
        return True
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if mission_path.exists():
        try:
            data = json.loads(mission_path.read_text(encoding="utf-8"))
            if bool(data.get("continuous_until_stopped")):
                return True
            if str(data.get("stop_condition") or "").strip().lower() == "owner_stop":
                return True
        except Exception:
            pass
    return False


def latest_valid_grok_mirror_text(*, state_dir: Optional[Path | str] = None) -> str:
    """Most recent valid Grok COPY mirrored to Global — for arming browser reply."""
    sd = state_dir_path(state_dir)
    for row in reversed(_read_jsonl_tail(sd / _PASTE_RESULTS, limit=40)):
        if str(row.get("source") or "") != "talk_to_alice_widget":
            continue
        text = str(row.get("clipboard_text") or row.get("text_preview") or "").strip()
        if grok_mirror_text_valid_for_reply(text, state_dir=sd):
            return text
    return ""


def grok_mirror_text_valid_for_reply(text: str, *, state_dir: Optional[Path | str] = None) -> bool:
    """Reject junk mirrors (Ioan TYPED dumps, model labels, Alice questions) before prompting Alice."""
    try:
        from System.swarm_alice_browser_grok_copy import clipboard_looks_like_grok_reply

        sd = state_dir_path(state_dir)
        state = _load_state(sd)
        return bool(
            clipboard_looks_like_grok_reply(
                text,
                last_alice_send_sha256=str(state.get("last_alice_browser_send_sha256") or ""),
            ).get("ok")
        )
    except Exception:
        clean = " ".join((text or "").split()).strip()
        return len(clean) >= 80 and "Ioan  (TYPED)" not in clean


def page_has_fresh_grok_reply(*, page: dict[str, Any], state: dict[str, Any]) -> bool:
    """True only when Browser Grok has answered since Alice's last browser send."""
    text = str(page.get("text") or "")
    if not text.strip() or not re.search(r"Thought for \d+s", text, re.IGNORECASE):
        return False
    alice_preview = str(state.get("last_alice_browser_send_preview") or "").strip()
    if alice_preview:
        idx = text.rfind(alice_preview[:120])
        if idx >= 0:
            after_alice = text[idx + len(alice_preview[:120]) :]
            if not re.search(r"Thought for \d+s", after_alice, re.IGNORECASE):
                return False
    try:
        from System.swarm_alice_browser_grok_copy import (
            clipboard_looks_like_grok_reply,
            extract_latest_grok_reply_from_page_text,
        )

        block = extract_latest_grok_reply_from_page_text(text)
        if not block:
            return False
        quality = clipboard_looks_like_grok_reply(
            block,
            last_alice_send_sha256=str(state.get("last_alice_browser_send_sha256") or ""),
        )
        if not quality.get("ok"):
            return False
        block_sha = _clean_text_sha(block)
        if block_sha == str(state.get("last_mirrored_clipboard_sha256") or ""):
            return False
        if block_sha == str(state.get("last_alice_browser_send_sha256") or ""):
            return False
        return True
    except Exception:
        return False


def browser_reply_prompts_used(state_dir: Optional[Path | str] = None) -> int:
    """How many valid Grok mirrors already triggered an Alice browser-reply prompt."""
    sd = state_dir_path(state_dir)
    state = _load_state(sd)
    return int(state.get("browser_reply_prompts") or 0)


def record_browser_reply_prompt(*, state_dir: Optional[Path | str] = None) -> int:
    sd = state_dir_path(state_dir)
    state = _load_state(sd)
    used = int(state.get("browser_reply_prompts") or 0) + 1
    state["browser_reply_prompts"] = used
    _save_state(sd, state)
    return used


def _clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _clean_text_sha(text: str) -> str:
    return hashlib.sha256(_clean_text(text).encode("utf-8")).hexdigest()


def should_prompt_alice_browser_reply(
    *,
    grok_text: str = "",
    state_dir: Optional[Path | str] = None,
) -> bool:
    """Budget by dialogue reply rounds — not raw mirror_turn (includes bad COPY retries)."""
    if not autopilot_enabled(state_dir):
        return False
    if grok_text and not grok_mirror_text_valid_for_reply(grok_text, state_dir=state_dir):
        return False
    if grok_dialogue_continuous_until_stopped(state_dir):
        return True
    return browser_reply_prompts_used(state_dir) < grok_mirror_reply_budget(state_dir)


def claim_grok_mirror_for_alice_reply(
    *,
    grok_text: str,
    from_grok_copy_receipt: str = "",
    mirror_paste_receipt: str = "",
    loop: int = 0,
    url: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Claim a mirrored Grok answer as Alice's next browser-reply input."""
    sd = state_dir_path(state_dir)
    if not autopilot_enabled(sd):
        return {"ok": False, "status": "disabled"}
    if not should_prompt_alice_browser_reply(grok_text=grok_text, state_dir=sd):
        return {
            "ok": False,
            "status": "reply_budget_or_quality_blocked",
            "used": browser_reply_prompts_used(sd),
            "budget": grok_mirror_reply_budget(sd),
        }
    clean = _clean_text(grok_text)
    sha = _clean_text_sha(clean)
    state = _load_state(sd)
    if sha in {
        str(state.get("pending_alice_reply_grok_sha256") or ""),
        str(state.get("last_alice_reply_grok_sha256") or ""),
    }:
        return {"ok": False, "status": "duplicate_grok_mirror", "grok_sha256": sha}
    used = record_browser_reply_prompt(state_dir=sd)
    state = _load_state(sd)
    ctx = {
        "grok_sha256": sha,
        "grok_preview": clean[:400],
        "from_grok_copy_receipt": str(from_grok_copy_receipt or ""),
        "mirror_paste_receipt": str(mirror_paste_receipt or ""),
        "loop": int(loop or used),
        "url": str(url or configured_grok_chat_url(sd)),
        "claimed_ts": time.time(),
        "browser_reply_prompt_index": used,
    }
    state["pending_alice_reply_grok_sha256"] = sha
    state["pending_alice_reply_context"] = ctx
    _save_state(sd, state)
    try:
        from System.swarm_grok_browser_round_state import record_round_transition

        record_round_transition(
            state="S5_ALICE_CORTEX_REPLY_ARMED",
            event="grok_global_mirror_consumed_by_alice_cortex",
            round_number=int(loop or used),
            predecessor_receipts=[
                str(mirror_paste_receipt or ""),
                str(from_grok_copy_receipt or ""),
            ],
            spend_receipts=[str(mirror_paste_receipt or "")],
            payload_text=clean,
            details={"browser_reply_prompt_index": used, "url": str(url or configured_grok_chat_url(sd))},
            state_dir=sd,
        )
    except Exception:
        pass
    row = {
        "active": True,
        "action": "claimed_grok_mirror_for_alice_reply",
        "ok": True,
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        **ctx,
    }
    _append_pulse(row, state_dir=sd)
    return {"ok": True, "status": "claimed", "context": ctx}


def enqueue_grok_mirror_brain_reply(
    *,
    grok_text: str,
    from_grok_copy_receipt: str = "",
    mirror_paste_receipt: str = "",
    loop: int = 0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Persist a Grok mirror for cortex→Global→browser paste when Talk is still busy."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "ts": time.time(),
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "action": "enqueue_grok_mirror_brain_reply",
        "grok_text": _clean_text(grok_text)[:12000],
        "from_grok_copy_receipt": str(from_grok_copy_receipt or ""),
        "receipt_id": str(mirror_paste_receipt or ""),
        "loop": int(loop or 0),
        "source": "grok_mirror_autopilot",
    }
    try:
        (sd / "alice_grok_browser_reply_retry.json").write_text(
            json.dumps(row, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        pass
    _append_pulse({**row, "active": True, "ok": True}, state_dir=sd)
    return row


def mark_alice_autoreply_staged(
    *,
    context: dict[str, Any],
    alice_reply: str,
    talk_copy_receipt: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Close the pending Grok mirror claim after Alice queued browser send."""
    sd = state_dir_path(state_dir)
    state = _load_state(sd)
    grok_sha = str((context or {}).get("grok_sha256") or "")
    row = {
        "active": True,
        "action": "staged_alice_reply_back_to_grok",
        "ok": True,
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "grok_sha256": grok_sha,
        "alice_reply_sha256": _clean_text_sha(alice_reply),
        "alice_reply_preview": _clean_text(alice_reply)[:300],
        "talk_copy_receipt": str(talk_copy_receipt or ""),
        "loop": int((context or {}).get("loop") or 0),
    }
    if grok_sha:
        state["last_alice_reply_grok_sha256"] = grok_sha
    state["last_alice_reply_sha256"] = row["alice_reply_sha256"]
    state["last_alice_reply_talk_copy_receipt"] = row["talk_copy_receipt"]
    state.pop("pending_alice_reply_grok_sha256", None)
    state.pop("pending_alice_reply_context", None)
    _save_state(sd, state)
    try:
        from System.swarm_grok_browser_round_state import record_round_transition

        record_round_transition(
            state="S6_ALICE_REPLY_TO_GROK_STAGED",
            event="alice_cortex_reply_payload_frozen_for_browser",
            round_number=int((context or {}).get("loop") or 0),
            predecessor_receipts=[
                str((context or {}).get("mirror_paste_receipt") or ""),
                str(talk_copy_receipt or ""),
            ],
            spend_receipts=[str(talk_copy_receipt or "")],
            payload_text=alice_reply,
            details={"grok_sha256": grok_sha},
            state_dir=sd,
        )
    except Exception:
        pass
    _append_pulse(row, state_dir=sd)
    return row


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def flag_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / FLAG_FILE


def autopilot_enabled(state_dir: Optional[Path | str] = None) -> bool:
    return flag_path(state_dir).exists()


def enable_autopilot(*, owner_note: str = "", state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "action": "enable",
        "owner_note": " ".join((owner_note or "").split())[:300],
    }
    flag_path(sd).write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    _append_pulse(row, state_dir=sd)
    return row


def extend_grok_dialogue_target_rounds(
    *,
    add_rounds: int = 0,
    continuous_until_stopped: bool = False,
    owner_note: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Extend an in-flight Grok dialogue without resetting mirror/reply counters."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    continuous = bool(continuous_until_stopped)
    add = max(0, min(30, int(add_rounds or 0)))
    if add <= 0 and not continuous:
        return {"ok": False, "action": "extend_target_rounds", "reason": "add_rounds_zero"}
    state = _load_state(sd)
    current_target = int(state.get("target_rounds") or 0)
    completed = int(state.get("browser_reply_prompts") or 0)
    prior_target = current_target if current_target > 0 else completed or 3
    new_target = max(prior_target, completed) + add if add > 0 else max(prior_target, completed)
    new_target = max(1, min(30, new_target))
    state["target_rounds"] = new_target
    if continuous:
        state["continuous_until_stopped"] = True
        state["stop_condition"] = "owner_stop"
    _save_state(sd, state)
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if mission_path.exists():
        try:
            mission = json.loads(mission_path.read_text(encoding="utf-8"))
            mission["target_rounds"] = new_target
            mission["status"] = "active"
            if continuous:
                mission["continuous_until_stopped"] = True
                mission["stop_condition"] = "owner_stop"
            if owner_note:
                mission["law"] = " ".join(owner_note.split())[:1000]
            mission["continue_note"] = " ".join((owner_note or "").split())[:500]
            mission_path.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "action": "extend_target_rounds",
        "ok": True,
        "add_rounds": add,
        "prior_target_rounds": prior_target,
        "completed_rounds": completed,
        "target_rounds": new_target,
        "continuous_until_stopped": continuous or bool(state.get("continuous_until_stopped")),
        "stop_condition": "owner_stop" if continuous or bool(state.get("continuous_until_stopped")) else "",
        "owner_note": " ".join((owner_note or "").split())[:300],
    }
    _append_pulse(row, state_dir=sd)
    return row


def reset_dialogue_mission_state(
    *,
    target_rounds: int = 3,
    continuous_until_stopped: bool = False,
    owner_note: str = "",
    mission_receipt_id: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Start a new Grok dialogue mission with clean per-mission counters."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    target = max(1, min(30, int(target_rounds or 3)))
    continuous = bool(continuous_until_stopped)
    owner_clean = _clean_text(owner_note)
    state: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "mission_start_receipt_id": str(mission_receipt_id or ""),
        "mission_owner_sha256": _clean_text_sha(owner_clean) if owner_clean else "",
        "mission_owner_preview": owner_clean[:300],
        "target_rounds": target,
        "continuous_until_stopped": continuous,
        "stop_condition": "owner_stop" if continuous else "",
        "browser_reply_prompts": 0,
        "mirror_turn": 0,
        "alice_mirror_turn": 0,
        "pending_copy_receipt": "",
        "pending_paste_receipt": "",
        "pending_alice_reply_grok_sha256": "",
        "pending_alice_reply_context": {},
        "pending_stable_since": 0.0,
        "last_page_hash": "",
        "page_hash_at_mirror": "",
        "page_hash_at_alice_send": "",
        "last_mirrored_clipboard_sha256": "",
        "last_alice_browser_send_sha256": "",
        "last_alice_browser_send_preview": "",
        "last_alice_browser_send_receipt": "",
        "last_alice_browser_send_source": "",
        "last_alice_reply_grok_sha256": "",
        "last_alice_reply_sha256": "",
        "last_alice_reply_talk_copy_receipt": "",
    }
    _save_state(sd, state)
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "action": "reset_dialogue_mission_state",
        "ok": True,
        "target_rounds": target,
        "continuous_until_stopped": continuous,
        "stop_condition": "owner_stop" if continuous else "",
        "mission_start_receipt_id": str(mission_receipt_id or ""),
    }
    _append_pulse(row, state_dir=sd)
    return row


def disable_autopilot(*, owner_note: str = "", state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    clean = " ".join((owner_note or "").split())[:300]
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "action": "disable",
        "owner_note": clean,
    }
    flag_path(sd).unlink(missing_ok=True)
    state = _load_state(sd)
    state["continuous_until_stopped"] = False
    state["stopped_ts"] = row["ts"]
    state["stopped_reason"] = clean or "autopilot_disabled"
    _save_state(sd, state)
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if mission_path.exists():
        try:
            mission = json.loads(mission_path.read_text(encoding="utf-8"))
            if isinstance(mission, dict):
                mission["status"] = "stopped"
                mission["stopped_ts"] = row["ts"]
                mission["stopped_reason"] = clean or "autopilot_disabled"
                mission["continuous_until_stopped"] = False
                mission_path.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    _append_pulse(row, state_dir=sd)
    return row


def _append_pulse(row: dict[str, Any], *, state_dir: Path) -> None:
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with (state_dir / PULSE_LEDGER).open("a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass


def _load_state(sd: Path) -> dict[str, Any]:
    path = sd / STATE_FILE
    if not path.exists():
        return {"schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL}


def _save_state(sd: Path, state: dict[str, Any]) -> None:
    state["ts"] = time.time()
    (sd / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _read_jsonl_tail(path: Path, limit: int = 40) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _page_snapshot(sd: Path) -> dict[str, Any]:
    path = sd / _PAGE_SNAPSHOT
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _page_text_hash(page: dict[str, Any]) -> str:
    text = str(page.get("text") or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _pending_command(sd: Path, name: str) -> bool:
    return (sd / name).exists()


def _find_copy_result(sd: Path, receipt_id: str) -> Optional[dict[str, Any]]:
    for row in reversed(_read_jsonl_tail(sd / _COPY_RESULTS, limit=80)):
        if str(row.get("receipt_id") or "") != receipt_id:
            continue
        if str(row.get("source") or "") != "alice_browser_widget":
            continue
        return row
    return None


def _find_paste_result(sd: Path, receipt_id: str) -> Optional[dict[str, Any]]:
    for row in reversed(_read_jsonl_tail(sd / _PASTE_RESULTS, limit=80)):
        if str(row.get("receipt_id") or "") != receipt_id:
            continue
        if str(row.get("source") or "") != "talk_to_alice_widget":
            continue
        return row
    return None


def _find_self_type_result(sd: Path, receipt_id: str) -> Optional[dict[str, Any]]:
    for row in reversed(_read_jsonl_tail(sd / _SELF_TYPE_RESULTS, limit=80)):
        if str(row.get("receipt_id") or "") != receipt_id:
            continue
        if str(row.get("source") or "") != "alice_browser_widget":
            continue
        return row
    return None


def _first_question_send_gate(sd: Path, state: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Block stale COPY loops until a new mission's opening browser send is proven."""
    mission_path = sd / "visible_grok_dialogue_mission.json"
    if not mission_path.exists():
        return None
    try:
        mission = json.loads(mission_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    first_question = _clean_text(str(mission.get("first_question") or ""))
    receipt_id = str(mission.get("self_type_receipt_id") or "")
    if not first_question or not receipt_id:
        return None
    if (
        str(state.get("first_question_send_receipt") or "") == receipt_id
        and str(state.get("first_question_send_status") or "") == "sent"
    ):
        return None
    cmd_path = sd / _SELF_TYPE_COMMAND
    if cmd_path.exists():
        try:
            cmd = json.loads(cmd_path.read_text(encoding="utf-8", errors="replace"))
            if str(cmd.get("receipt_id") or "") == receipt_id:
                return {
                    "active": True,
                    "action": "waiting_first_question_browser_command",
                    "self_type_receipt_id": receipt_id,
                }
        except Exception:
            pass
    result = _find_self_type_result(sd, receipt_id)
    if result is None or str(result.get("status") or "") == "started":
        return {
            "active": True,
            "action": "waiting_first_question_send_result",
            "self_type_receipt_id": receipt_id,
        }
    status = str(result.get("status") or "")
    if result.get("ok") and status == "sent":
        state["first_question_send_receipt"] = receipt_id
        state["first_question_send_status"] = "sent"
        state["last_alice_browser_send_sha256"] = _clean_text_sha(first_question)
        state["last_alice_browser_send_preview"] = first_question[:300]
        state["last_alice_browser_send_receipt"] = receipt_id
        state["last_alice_browser_send_source"] = "mission_first_question"
        state["page_hash_at_alice_send"] = str(state.get("last_page_hash") or "")
        state.pop("pending_stable_since", None)
        _save_state(sd, state)
        return None
    if str(state.get("first_question_retry_for") or "") != receipt_id:
        try:
            from System.swarm_alice_browser_grok_self_type import stage_grok_self_type_command

            retry = stage_grok_self_type_command(
                first_question,
                owner_text="autopilot retry: first Grok mission question was not proven sent",
                press_enter=True,
                url=str(mission.get("grok_url") or configured_grok_chat_url(sd)),
                source="grok_mirror_autopilot.first_question_retry",
                state_dir=sd,
            )
            new_receipt = str(retry.get("receipt_id") or "")
            if new_receipt:
                mission["self_type_receipt_id"] = new_receipt
                mission["first_question_retry_of"] = receipt_id
                mission_path.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
                state["first_question_retry_for"] = receipt_id
                state["first_question_retry_receipt"] = new_receipt
                _save_state(sd, state)
            return {
                "active": True,
                "action": "first_question_send_retry_staged",
                "prior_self_type_receipt_id": receipt_id,
                "self_type_receipt_id": new_receipt,
                "prior_status": status,
            }
        except Exception as exc:
            state["first_question_send_status"] = f"retry_failed:{type(exc).__name__}"
            _save_state(sd, state)
            return {
                "active": True,
                "action": "first_question_send_retry_failed",
                "self_type_receipt_id": receipt_id,
                "prior_status": status,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return {
        "active": True,
        "action": "first_question_send_unverified",
        "self_type_receipt_id": receipt_id,
        "status": status,
        "reason": str(result.get("reason") or result.get("status") or "unverified"),
    }


def tick_grok_mirror_autopilot(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """One autopilot tick — safe to call from Talk widget timer."""
    sd = state_dir_path(state_dir)
    if not autopilot_enabled(sd):
        return {"active": False, "action": "disabled"}

    state = _load_state(sd)
    now = time.time()
    out: dict[str, Any] = {"active": True, "action": "idle"}

    pending_paste = str(state.get("pending_paste_receipt") or "")
    if pending_paste:
        paste_result = _find_paste_result(sd, pending_paste)
        if paste_result is not None and str(paste_result.get("status") or "") == "pasted":
            state["pending_paste_receipt"] = ""
            _save_state(sd, state)
            _append_pulse(
                {
                    "schema": TRUTH_LABEL,
                    "truth_label": TRUTH_LABEL,
                    "ts": now,
                    "action": "cleared_completed_talk_paste_latch",
                    "paste_receipt_id": pending_paste,
                },
                state_dir=sd,
            )

    first_question_gate = _first_question_send_gate(sd, state)
    if first_question_gate:
        _append_pulse({**first_question_gate, "schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "ts": now}, state_dir=sd)
        return first_question_gate

    pending_copy = str(state.get("pending_copy_receipt") or "")
    if pending_copy:
        result = _find_copy_result(sd, pending_copy)
        if result is None:
            out["action"] = "waiting_copy_result"
            out["pending_copy_receipt"] = pending_copy
            return out
        status = str(result.get("status") or "")
        if status == "copied" and result.get("ok"):
            from System.swarm_alice_browser_grok_copy import clipboard_looks_like_grok_reply
            from System.swarm_alice_talk_paste_clipboard import stage_talk_paste_clipboard_command

            clip_text = str(
                result.get("clipboard_text")
                or result.get("clipboard_preview")
                or ""
            ).strip()
            clip_sha = str(result.get("clipboard_sha256") or "")
            if clip_text and not clip_sha:
                clip_sha = _clean_text_sha(clip_text)
            quality = clipboard_looks_like_grok_reply(
                clip_text,
                last_alice_send_sha256=str(state.get("last_alice_browser_send_sha256") or ""),
            )
            if not quality.get("ok"):
                state["pending_copy_receipt"] = ""
                state.pop("pending_stable_since", None)
                _save_state(sd, state)
                out.update(
                    {
                        "action": "copy_rejected_not_grok",
                        "clipboard_quality": quality,
                        "clipboard_preview": clip_text[:200],
                    }
                )
                _append_pulse({**out, "schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "ts": now}, state_dir=sd)
                return out
            paste = stage_talk_paste_clipboard_command(
                owner_text="autopilot: mirror Grok COPY to Global Chat",
                from_grok_copy_receipt=pending_copy,
                expected_clipboard_sha256=clip_sha,
                clipboard_text=clip_text,
                loop=int(state.get("mirror_turn") or 0) + 1,
                source="grok_mirror_autopilot",
                state_dir=sd,
            )
            try:
                from System.swarm_grok_browser_round_state import record_round_transition

                record_round_transition(
                    state="S4_GROK_COPY_TO_GLOBAL_STAGED",
                    event="browser_copy_payload_frozen_for_global",
                    round_number=int(state.get("mirror_turn") or 0) + 1,
                    predecessor_receipts=[pending_copy],
                    spend_receipts=[pending_copy],
                    payload_text=clip_text,
                    details={
                        "paste_receipt_id": str(paste.get("receipt_id") or ""),
                        "clipboard_quality": quality,
                    },
                    state_dir=sd,
                )
            except Exception:
                pass
            state["pending_copy_receipt"] = ""
            state["pending_paste_receipt"] = str(paste.get("receipt_id") or "")
            state["last_mirrored_clipboard_sha256"] = clip_sha
            state["mirror_turn"] = int(state.get("mirror_turn") or 0) + 1
            state["page_hash_at_mirror"] = state.get("last_page_hash") or ""
            state.pop("pending_stable_since", None)
            _save_state(sd, state)
            out.update(
                {
                    "action": "staged_talk_paste",
                    "from_copy_receipt": pending_copy,
                    "paste_receipt_id": paste.get("receipt_id"),
                }
            )
            _append_pulse({**out, "schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "ts": now}, state_dir=sd)
            return out
        if status in {"wrong_clipboard_target", "copy_click_failed", "clipboard_empty", "copy_js_failed"}:
            state["pending_copy_receipt"] = ""
            state.pop("pending_stable_since", None)
            _save_state(sd, state)
            out.update({"action": "copy_failed", "copy_status": status, "copy_result": result})
            _append_pulse({**out, "schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "ts": now}, state_dir=sd)
            return out
        out["action"] = "waiting_copy_result"
        return out

    if _pending_command(sd, _COPY_COMMAND) or _pending_command(sd, _PASTE_COMMAND):
        out["action"] = "pending_limb_command"
        return out

    budget = grok_mirror_reply_budget(sd)
    continuous = grok_dialogue_continuous_until_stopped(sd)
    if (
        not continuous
        and int(state.get("mirror_turn") or 0) >= budget
        and int(state.get("browser_reply_prompts") or 0) >= budget
    ):
        out.update(
            {
                "action": "target_rounds_complete",
                "target_rounds": budget,
                "mirror_turn": int(state.get("mirror_turn") or 0),
                "browser_reply_prompts": int(state.get("browser_reply_prompts") or 0),
            }
        )
        try:
            mission_path = sd / "visible_grok_dialogue_mission.json"
            if mission_path.exists():
                mission = json.loads(mission_path.read_text(encoding="utf-8"))
                if isinstance(mission, dict):
                    mission["status"] = "complete"
                    mission["completed_ts"] = now
                    mission["completed_reason"] = "target_rounds_reached"
                    mission_path.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            flag_path(sd).unlink(missing_ok=True)
        except Exception:
            pass
        _append_pulse({**out, "schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "ts": now}, state_dir=sd)
        return out
    if continuous:
        out["continuous_until_stopped"] = True

    page = _page_snapshot(sd)
    url = str(page.get("url") or "")
    if _GROK_URL_NEEDLE not in url:
        redirect = _mission_thread_redirect_if_needed(sd, url)
        if redirect:
            out.update(redirect)
        else:
            out["action"] = "not_on_grok_chat"
        return out
    redirect = _mission_thread_redirect_if_needed(sd, url)
    if redirect:
        out.update(redirect)
        return out

    page_hash = _page_text_hash(page)
    last_hash = str(state.get("last_page_hash") or "")
    last_mirror_hash = str(state.get("page_hash_at_mirror") or "")

    if page_hash == last_hash:
        stable_since = float(state.get("pending_stable_since") or 0.0)
        if not stable_since and page_hash != last_mirror_hash and page_has_fresh_grok_reply(
            page=page, state=state
        ):
            # Fresh kickoff: page already stable (e.g. after reset) — start stability clock.
            state["pending_stable_since"] = now - _STABLE_S
            _save_state(sd, state)
            stable_since = state["pending_stable_since"]
        if stable_since and (now - stable_since) >= _STABLE_S:
            if page_hash != last_mirror_hash and page_has_fresh_grok_reply(page=page, state=state):
                from System.swarm_alice_browser_grok_copy import stage_grok_copy_last_reply_command

                cmd = stage_grok_copy_last_reply_command(
                    owner_text="autopilot: COPY latest Grok reply for Global mirror",
                    url=url,
                    source="grok_mirror_autopilot",
                    loop=int(state.get("mirror_turn") or 0) + 1,
                    state_dir=sd,
                )
                rid = str(cmd.get("receipt_id") or "")
                state["pending_copy_receipt"] = rid
                state.pop("pending_stable_since", None)
                _save_state(sd, state)
                out.update({"action": "staged_grok_copy", "copy_receipt_id": rid})
                _append_pulse({**out, "schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "ts": now}, state_dir=sd)
                return out
        out["action"] = "page_stable"
        return out

    state["last_page_hash"] = page_hash
    state["pending_stable_since"] = now
    _save_state(sd, state)
    out.update({"action": "page_changed", "page_hash": page_hash})
    return out


def maybe_mirror_alice_browser_send(
    *,
    text: str,
    browser_receipt_id: str,
    source: str = "",
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Mirror Alice's browser send to Global when autopilot is on."""
    sd = state_dir_path(state_dir)
    if not autopilot_enabled(sd):
        return None
    blocked_sources = {
        "visible_grok_dialogue",
        "visible_grok_dialogue_orchestrator",
        "grok_5loop_orchestrator",
    }
    if str(source or "") in blocked_sources:
        return None
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return None
    try:
        from System.swarm_alice_browser_grok_self_type import looks_like_instruction_placeholder_payload

        if looks_like_instruction_placeholder_payload(clean):
            return None
    except Exception:
        pass
    from System.swarm_alice_talk_mirror_line import stage_talk_mirror_line_command

    state = _load_state(sd)
    turn = int(state.get("alice_mirror_turn") or 0) + 1
    cmd = stage_talk_mirror_line_command(
        clean,
        turn=turn,
        from_browser_receipt=browser_receipt_id,
        owner_text="autopilot: mirror Alice browser line to Global Chat",
        source="grok_mirror_autopilot",
        state_dir=sd,
    )
    state["alice_mirror_turn"] = turn
    state["last_alice_browser_send_sha256"] = _clean_text_sha(clean)
    state["last_alice_browser_send_preview"] = clean[:300]
    state["page_hash_at_alice_send"] = str(state.get("last_page_hash") or "")
    state.pop("pending_stable_since", None)
    _save_state(sd, state)
    return cmd


def note_alice_browser_send(
    *,
    text: str,
    browser_receipt_id: str = "",
    source: str = "",
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Record Alice's browser send state without posting a duplicate Global row."""
    sd = state_dir_path(state_dir)
    if not autopilot_enabled(sd):
        return None
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return None
    state = _load_state(sd)
    state["last_alice_browser_send_sha256"] = _clean_text_sha(clean)
    state["last_alice_browser_send_preview"] = clean[:300]
    state["last_alice_browser_send_receipt"] = str(browser_receipt_id or "")
    state["last_alice_browser_send_source"] = str(source or "")
    state["page_hash_at_alice_send"] = str(state.get("last_page_hash") or "")
    state.pop("pending_stable_since", None)
    _save_state(sd, state)
    try:
        from System.swarm_grok_browser_round_state import record_round_transition

        record_round_transition(
            state="S7_ALICE_BROWSER_SEND_CONFIRMED",
            event="alice_reply_sent_to_browser_grok",
            round_number=int(state.get("mirror_turn") or 0),
            predecessor_receipts=[str(browser_receipt_id or "")],
            spend_receipts=[str(browser_receipt_id or "")],
            payload_text=clean,
            details={"source": str(source or "")},
            state_dir=sd,
        )
    except Exception:
        pass
    row = {
        "active": True,
        "action": "noted_alice_browser_send",
        "ok": True,
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "browser_receipt_id": str(browser_receipt_id or ""),
        "source": str(source or ""),
        "text_preview": clean[:300],
        "text_sha256": _clean_text_sha(clean),
    }
    _append_pulse(row, state_dir=sd)
    return row


__all__ = [
    "TRUTH_LABEL",
    "autopilot_enabled",
    "browser_reply_prompts_used",
    "claim_grok_mirror_for_alice_reply",
    "configured_grok_chat_url",
    "disable_autopilot",
    "enable_autopilot",
    "extend_grok_dialogue_target_rounds",
    "enqueue_grok_mirror_brain_reply",
    "extract_alice_browser_reply_text",
    "flag_path",
    "grok_mirror_reply_budget",
    "grok_dialogue_continuous_until_stopped",
    "latest_valid_grok_mirror_text",
    "grok_mirror_text_valid_for_reply",
    "mark_alice_autoreply_staged",
    "page_has_fresh_grok_reply",
    "maybe_mirror_alice_browser_send",
    "note_alice_browser_send",
    "record_browser_reply_prompt",
    "reset_dialogue_mission_state",
    "should_prompt_alice_browser_reply",
    "tick_grok_mirror_autopilot",
]
