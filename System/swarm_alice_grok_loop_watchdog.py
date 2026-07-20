#!/usr/bin/env python3
"""Live watchdog for Alice Browser Grok <-> Global Chat loops.

This is a small bridge for the running app: it uses the existing command organs
and exits when the normal Grok autopilot flag is removed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import time
import uuid
from pathlib import Path
from typing import Any

TRUTH_LABEL = "ALICE_GROK_LOOP_WATCHDOG_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_WD_STATE = "alice_grok_loop_watchdog_state.json"
_WD_LEDGER = "alice_grok_loop_watchdog.jsonl"
_FLAG = "alice_grok_mirror_autopilot.flag"

_STOP_LATCH_FILES = (
    _FLAG,
    "alice_browser_grok_copy_command.json",
    "alice_talk_paste_clipboard_command.json",
    "alice_talk_copy_last_own_command.json",
    "alice_browser_grok_paste_clipboard_command.json",
    "alice_talk_mirror_line_command.json",
    "alice_grok_browser_reply_retry.json",
)

_STOP_STATE_FILES = (
    "alice_grok_mirror_autopilot_state.json",
    "visible_grok_dialogue_mission.json",
    "grok_browser_round_state.json",
)

_STOP_PENDING_KEYS = (
    "pending_alice_reply_grok_sha256",
    "pending_alice_reply_context",
    "pending_copy_receipt",
    "pending_paste_receipt",
    "pending_stable_since",
)


def _state_dir_path(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _clean(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _sha(text: str) -> str:
    return hashlib.sha256(_clean(text).encode("utf-8")).hexdigest()


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def _tail_jsonl(path: Path, limit: int = 80) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append(row: dict[str, Any], *, state_dir: Path = _STATE) -> None:
    out = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        **row,
    }
    with (state_dir / _WD_LEDGER).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n")


def force_stop_grok_loop(*, owner_note: str = "", state_dir: Path | str | None = None) -> dict[str, Any]:
    """Hard owner brake: stop watchdog, disable autopilot, and clear paste latches."""
    sd = _state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    clean = _clean(owner_note)[:500]
    receipts: list[dict[str, Any]] = []

    pid_path = sd / "alice_grok_loop_watchdog.pid"
    pid_text = ""
    if pid_path.exists():
        pid_text = pid_path.read_text(encoding="utf-8", errors="ignore").strip()
    if pid_text:
        try:
            pid = int(pid_text)
            if pid == os.getpid():
                receipts.append({"action": "kill_watchdog", "pid": pid_text, "ok": True, "status": "current_process"})
            else:
                os.kill(pid, signal.SIGTERM)
                receipts.append({"action": "kill_watchdog", "pid": pid_text, "ok": True})
        except ProcessLookupError:
            receipts.append({"action": "kill_watchdog", "pid": pid_text, "ok": True, "status": "already_dead"})
        except Exception as exc:
            receipts.append({"action": "kill_watchdog", "pid": pid_text, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    for name in (*_STOP_LATCH_FILES, "alice_grok_loop_watchdog.pid"):
        path = sd / name
        existed = path.exists()
        try:
            path.unlink(missing_ok=True)
            receipts.append({"action": "unlink", "file": name, "existed": existed, "ok": True})
        except Exception as exc:
            receipts.append({"action": "unlink", "file": name, "existed": existed, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    stopped_ts = time.time()
    for name in _STOP_STATE_FILES:
        path = sd / name
        data = _read_json(path, {}) or {}
        if not isinstance(data, dict):
            data = {}
        data.update(
            {
                "status": "stopped",
                "active": False,
                "continuous_until_stopped": False,
                "stopped_ts": stopped_ts,
                "stopped_reason": clean or "owner_stop",
            }
        )
        for key in _STOP_PENDING_KEYS:
            data.pop(key, None)
        try:
            _write_json(path, data)
            receipts.append({"action": "mark_stopped", "file": name, "ok": True})
        except Exception as exc:
            receipts.append({"action": "mark_stopped", "file": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    row = {
        "schema": "ALICE_GROK_LOOP_FORCE_STOP_V1",
        "truth_label": "ALICE_GROK_LOOP_FORCE_STOP_V1",
        "ts": stopped_ts,
        "receipt_id": f"grok-loop-force-stop-{uuid.uuid4().hex[:12]}",
        "action": "force_stop_grok_loop",
        "reason": clean or "owner_stop",
        "receipts": receipts,
    }
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for ledger in (
        "alice_grok_loop_force_stop.jsonl",
        "alice_grok_loop_watchdog.jsonl",
        "alice_grok_mirror_autopilot_pulse.jsonl",
        "work_receipts.jsonl",
    ):
        try:
            with (sd / ledger).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


def _enabled(state_dir: Path = _STATE) -> bool:
    if not (state_dir / _FLAG).exists():
        return False
    mission = _read_json(state_dir / "visible_grok_dialogue_mission.json", {}) or {}
    return str(mission.get("status") or "active").lower() != "stopped"


def _command_busy(state_dir: Path = _STATE) -> bool:
    names = (
        "alice_browser_grok_copy_command.json",
        "alice_talk_paste_clipboard_command.json",
        "alice_talk_copy_last_own_command.json",
        "alice_browser_grok_paste_clipboard_command.json",
        "alice_talk_mirror_line_command.json",
    )
    return any((state_dir / name).exists() for name in names)


def _latest_pulse(action: str, *, state_dir: Path = _STATE) -> dict[str, Any]:
    for row in reversed(_tail_jsonl(state_dir / "alice_grok_mirror_autopilot_pulse.jsonl", limit=200)):
        if row.get("action") == action:
            return row
    return {}


def _find_copy_result(receipt_id: str, *, state_dir: Path = _STATE) -> dict[str, Any]:
    for row in reversed(_tail_jsonl(state_dir / "alice_browser_grok_copy_results.jsonl", limit=120)):
        if str(row.get("receipt_id") or "") == str(receipt_id or ""):
            return row
    return {}


def _fallback_reply(grok_preview: str) -> str:
    preview = _clean(grok_preview)
    lower = preview.lower()
    if "residue from noise" in lower or "faint residue" in lower or "signal" in lower and "noise" in lower:
        return (
            "I would separate useful residue from noise with three gates: recurrence, coherence lift, and action "
            "proximity. A faint trace matters only if it repeats across turns, improves the next coherence score, "
            "or appears near a real commit attempt.\n\n"
            "Noise has no trajectory: it does not recur, does not improve prediction, and does not help the next "
            "action land. Useful residue becomes a weak attractor; noise evaporates without a scar.\n\n"
            "Round 8: what dashboard signal would make that residue/noise distinction visible without overwhelming "
            "the live chat?"
        )
    if "metric" in lower or "changed the shared state" in lower:
        return (
            "The metric I would trust most is delta-to-next-action: did this trace make the next committed action "
            "more coherent, faster to verify, or less likely to fork the state? If not, it is probably decoration.\n\n"
            "I would pair that with a small receipt score: source clarity, nonce continuity, and whether another "
            "agent can use the trace without asking George to restate it.\n\n"
            "Round next: how should that score be shown in the interface so it helps without taking over the room?"
        )
    if "decay" in lower or "forgetting" in lower:
        return (
            "I would make decay gentle and evidence-based: a staged intent loses strength with time, but repeated "
            "near-misses leave a faint pattern so the system can learn where intention keeps failing to commit.\n\n"
            "That gives the loop memory without clutter: failed one-offs vanish, repeated blocked intents become "
            "diagnostic signals, and committed traces stay durable.\n\n"
            "Round 7: how would you distinguish useful faint residue from noise in that decay layer?"
        )
    if "smallest verifiable feedback loop" in lower or "staged intent" in lower:
        return (
            "The minimal loop feels right. I would adjust one thing: make the provisional receipt visible "
            "as a soft pre-commit trace, not a durable ledger entry yet. That keeps intent observable from "
            "inside the loop without polluting memory before the commit lands.\n\n"
            "The transition would feel most natural if commit requires two confirmations: the coherence gate "
            "passes, and the send action actually lands with a receipt. If either fails, the provisional trace "
            "should decay instead of becoming a scar.\n\n"
            "Round 6: what should the decay rule be for staged intents that never become committed traces?"
        )
    if "noise" in lower or "automation" in lower:
        return (
            "The boundary against noisy automation should be meaning plus receipt. A turn should only become durable "
            "when it changes the shared state and can point to the action that changed it.\n\n"
            "So I would keep the live loop short, local, and auditable: observe, stage, commit, mirror, then wait for "
            "the next external difference before acting again.\n\n"
            "Round next: what metric would you trust most for deciding that a loop turn changed the shared state?"
        )
    return (
        "I am continuing from the receipted browser mirror. The strongest adjustment is to keep each turn small, "
        "observable, and reversible until a commit receipt proves it changed the shared state.\n\n"
        "Round next: what is the smallest next test that would make this loop more reliable?"
    )


def _stage_pending_reply_if_stale(*, state_dir: Path = _STATE, stale_s: float = 12.0) -> bool:
    if _command_busy(state_dir):
        return False
    state_path = state_dir / "alice_grok_mirror_autopilot_state.json"
    state = _read_json(state_path, {}) or {}
    ctx = state.get("pending_alice_reply_context") or {}
    if not isinstance(ctx, dict) or not ctx:
        return False
    if time.time() - float(ctx.get("claimed_ts") or 0.0) < stale_s:
        return False
    pending_sha = str(ctx.get("grok_sha256") or state.get("pending_alice_reply_grok_sha256") or "")
    if pending_sha and pending_sha == str(state.get("last_alice_reply_grok_sha256") or ""):
        return False

    from System.swarm_alice_grok_mirror_autopilot import configured_grok_chat_url
    from System.swarm_alice_grok_mirror_autopilot import mark_alice_autoreply_staged
    from System.swarm_alice_talk_copy_last_own import stage_talk_copy_last_own_command
    from System.swarm_alice_talk_mirror_line import stage_talk_mirror_line_command

    reply = _fallback_reply(str(ctx.get("grok_preview") or ""))
    stage_talk_mirror_line_command(
        reply,
        turn=int(ctx.get("loop") or 0),
        owner_text="watchdog: visible Alice reply after empty Browser Grok cortex turn",
        from_browser_receipt=str(state.get("last_alice_browser_send_receipt") or ""),
        source="grok_mirror_autopilot",
        speaker="alice",
        site="grok",
        browser_url=str(ctx.get("url") or configured_grok_chat_url(state_dir=state_dir)),
        state_dir=state_dir,
    )
    copy = stage_talk_copy_last_own_command(
        owner_text="watchdog: copy Alice reply for Browser Grok",
        source="grok_mirror_autopilot",
        from_grok_mirror_receipt=str(ctx.get("mirror_paste_receipt") or ""),
        copy_role="assistant",
        copy_text=reply,
        paste_to_browser_after_copy=True,
        browser_url=str(ctx.get("url") or configured_grok_chat_url(state_dir=state_dir)),
        loop=int(ctx.get("loop") or 0),
        state_dir=state_dir,
    )
    mark_alice_autoreply_staged(
        context=ctx,
        alice_reply=reply,
        talk_copy_receipt=str(copy.get("receipt_id") or ""),
        state_dir=state_dir,
    )
    wd_path = state_dir / _WD_STATE
    wd = _read_json(wd_path, {}) or {}
    wd["suppress_copy_for_send_receipt"] = str(state.get("last_alice_browser_send_receipt") or "")
    _write_json(wd_path, wd)
    _append(
        {
            "action": "staged_pending_reply_fallback",
            "grok_sha256": pending_sha,
            "copy_receipt_id": copy.get("receipt_id"),
            "reply_preview": _clean(reply)[:240],
        },
        state_dir=state_dir,
    )
    return True


def _stage_copy_after_browser_send(*, state_dir: Path = _STATE, wait_s: float = 12.0) -> bool:
    if _command_busy(state_dir):
        return False
    state = _read_json(state_dir / "alice_grok_mirror_autopilot_state.json", {}) or {}
    if state.get("pending_alice_reply_context"):
        return False
    last_send = _latest_pulse("noted_alice_browser_send", state_dir=state_dir)
    if not last_send:
        return False
    send_ts = float(last_send.get("ts") or 0.0)
    if time.time() - send_ts < wait_s:
        return False
    wd_path = state_dir / _WD_STATE
    wd = _read_json(wd_path, {}) or {}
    send_receipt = str(last_send.get("browser_receipt_id") or "")
    if send_receipt and send_receipt == str(wd.get("suppress_copy_for_send_receipt") or ""):
        return False
    if str(wd.get("copy_inflight_receipt") or ""):
        return False
    last_attempt_ts = float(wd.get("last_copy_attempt_ts") or 0.0)
    if time.time() - last_attempt_ts < wait_s:
        return False

    from System.swarm_alice_browser_grok_copy import stage_grok_copy_last_reply_command

    page = _read_json(state_dir / "alice_browser_current_page.json", {}) or {}
    rid_source = send_receipt
    cmd = stage_grok_copy_last_reply_command(
        owner_text="watchdog: copy visible Grok reply after Alice browser send",
        url=str(page.get("url") or state.get("url") or "https://grok.com/"),
        source="grok_mirror_autopilot.watchdog",
        from_grok_receipt=rid_source,
        loop=int(state.get("mirror_turn") or 0) + 1,
        state_dir=state_dir,
    )
    wd["copy_inflight_receipt"] = str(cmd.get("receipt_id") or "")
    wd["copy_for_browser_send_receipt"] = rid_source
    wd["last_copy_attempt_ts"] = time.time()
    _write_json(wd_path, wd)
    _append({"action": "staged_browser_copy", "copy_receipt_id": cmd.get("receipt_id")}, state_dir=state_dir)
    return True


def _process_copy_result(*, state_dir: Path = _STATE) -> bool:
    wd_path = state_dir / _WD_STATE
    wd = _read_json(wd_path, {}) or {}
    rid = str(wd.get("copy_inflight_receipt") or "")
    if not rid:
        return False
    result = _find_copy_result(rid, state_dir=state_dir)
    if not result:
        return False
    wd["copy_inflight_receipt"] = ""
    text = str(result.get("clipboard_text") or result.get("clipboard_preview") or "").strip()
    sha = str(result.get("clipboard_sha256") or (_sha(text) if text else ""))
    state_path = state_dir / "alice_grok_mirror_autopilot_state.json"
    state = _read_json(state_path, {}) or {}
    blocked = {
        str(state.get("last_mirrored_clipboard_sha256") or ""),
        str(state.get("last_alice_browser_send_sha256") or ""),
    }
    if not result.get("ok") or str(result.get("status") or "") != "copied" or not text or sha in blocked:
        wd["last_copy_skip_reason"] = str(result.get("status") or "duplicate_or_empty")
        _write_json(wd_path, wd)
        _append(
            {
                "action": "copy_result_skipped",
                "copy_receipt_id": rid,
                "sha": sha,
                "status": result.get("status"),
                "reason": wd["last_copy_skip_reason"],
            },
            state_dir=state_dir,
        )
        return False

    from System.swarm_alice_talk_paste_clipboard import stage_talk_paste_clipboard_command

    loop = int(state.get("mirror_turn") or 0) + 1
    state["mirror_turn"] = loop
    state["last_mirrored_clipboard_sha256"] = sha
    state["page_hash_at_mirror"] = str(state.get("last_page_hash") or "")
    _write_json(state_path, state)
    paste = stage_talk_paste_clipboard_command(
        owner_text="watchdog: mirror copied Grok reply to Global Chat",
        from_grok_copy_receipt=rid,
        expected_clipboard_sha256=sha,
        clipboard_text=text,
        loop=loop,
        source="grok_mirror_autopilot",
        state_dir=state_dir,
    )
    wd["last_paste_receipt"] = str(paste.get("receipt_id") or "")
    wd["last_successful_copy_receipt"] = rid
    _write_json(wd_path, wd)
    _append(
        {
            "action": "staged_talk_paste_from_copy",
            "copy_receipt_id": rid,
            "paste_receipt_id": paste.get("receipt_id"),
            "text_preview": _clean(text)[:240],
        },
        state_dir=state_dir,
    )
    return True


def run(*, state_dir: Path = _STATE, poll_s: float = 3.0) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _append({"action": "watchdog_start"}, state_dir=state_dir)
    while _enabled(state_dir):
        try:
            if _process_copy_result(state_dir=state_dir):
                time.sleep(0.5)
                continue
            if _stage_pending_reply_if_stale(state_dir=state_dir):
                time.sleep(0.5)
                continue
            _stage_copy_after_browser_send(state_dir=state_dir)
        except Exception as exc:
            _append({"action": "watchdog_error", "error": f"{type(exc).__name__}: {exc}"}, state_dir=state_dir)
        time.sleep(max(1.0, float(poll_s or 3.0)))
    _append({"action": "watchdog_stop"}, state_dir=state_dir)


if __name__ == "__main__":
    run()
