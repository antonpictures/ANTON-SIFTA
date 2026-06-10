#!/usr/bin/env python3
"""Plan A2 — adopt effect-verification on top-5 live effectors.

Wraps A1 ``swarm_effect_verified_action`` for alice_app_commands writers:
  browser open, close-tab, ad-skip (async), schedule-fire, app-open.

Truth label: APP_COMMAND_EFFECT_VERIFIED_V1.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from System.swarm_effect_verified_action import (
    TRUTH_LABEL as EFFECT_TRUTH_LABEL,
    complete_async_verified_action,
    enrich_effect,
    record_effect_verified_action,
    run_sync_verified_action,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "APP_COMMAND_EFFECT_VERIFIED_V1"

TOP5_ACTIONS = frozenset({
    "open_browser_url",
    "browser_close_tab",
    "youtube_ad_skip",
    "schedule_fire",
    "open_app",
})

ACTION_ORGAN_MAP: dict[str, tuple[str, str]] = {
    "open_browser_url": ("alice_browser", "open_url"),
    "browser_close_tab": ("alice_browser", "close_tab"),
    "youtube_ad_skip": ("youtube_ad_controller", "skip"),
    "schedule_fire": ("stigmergic_schedule", "fire"),
    "open_app": ("sifta_desktop", "open_app"),
}


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def is_top5_action(action: str) -> bool:
    return str(action or "") in TOP5_ACTIONS


def organ_for_action(action: str) -> tuple[str, str]:
    return ACTION_ORGAN_MAP.get(str(action or ""), ("alice_app_command", str(action or "unknown")))


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").rstrip("/")
        return f"{host}{path}".lower()
    except Exception:
        return raw.lower()


def _urls_match(target: str, observed: str) -> bool:
    t = _normalize_url(target)
    o = _normalize_url(observed)
    if not t or not o:
        return False
    return t in o or o in t


def _read_jsonl_tail(path: Path, *, max_rows: int = 40) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _latest_browser_page(state_dir: Optional[Path | str]) -> dict[str, Any]:
    try:
        from System.swarm_browser_page_state import latest_page_state

        row = latest_page_state(state_dir=state_dir, max_age_s=300.0)
        return dict(row) if isinstance(row, dict) else {}
    except Exception:
        return {}


def _schedule_row(state_dir: Optional[Path | str], schedule_id: str) -> dict[str, Any]:
    base = _state(state_dir)
    for row in _read_jsonl_tail(base / "stigmergic_schedule.jsonl", max_rows=400):
        if str(row.get("schedule_id") or "") == schedule_id:
            return row
    return {}


def probe_open_browser_url(
    *,
    target_url: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    page = _latest_browser_page(state_dir)
    return {
        "target_url": target_url,
        "observed_url": str(page.get("url") or ""),
        "page_fresh": bool(page.get("fresh")),
        "open_tabs_count": int(page.get("open_tabs_count") or 0),
    }


def probe_browser_close_tab(
    *,
    result: Mapping[str, Any] | None = None,
    before_tabs: int | None = None,
    after_tabs: int | None = None,
) -> dict[str, Any]:
    result_row = dict(result or {})
    closed = result_row.get("closed") if isinstance(result_row.get("closed"), list) else []
    remaining = result_row.get("remaining_tabs")
    if before_tabs is None:
        before_tabs = int(result_row.get("before_tabs") or 0)
    if after_tabs is None:
        after_tabs = int(remaining or result_row.get("after_tabs") or 0)
    return {
        "closed_count": len(closed),
        "remaining_tabs": after_tabs,
        "before_tabs": before_tabs,
        "ok_claim": bool(result_row.get("ok")),
    }


def probe_open_app(
    *,
    app_name: str,
    before_state: Mapping[str, Any] | None = None,
    after_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = str(app_name or "").casefold()
    before_apps = [
        str(x).casefold()
        for x in (dict(before_state or {}).get("open_apps") or [])
        if str(x).strip()
    ]
    after_apps = [
        str(x).casefold()
        for x in (dict(after_state or {}).get("open_apps") or [])
        if str(x).strip()
    ]
    return {
        "app_name": app_name,
        "before_open_apps": before_apps,
        "after_open_apps": after_apps,
        "now_open": any(target in app or app in target for app in after_apps),
        "was_already_open": any(target in app or app in target for app in before_apps),
    }


def probe_schedule_fire(
    *,
    schedule_id: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    row = _schedule_row(state_dir, schedule_id)
    return {
        "schedule_id": schedule_id,
        "fired": bool(row.get("fired")),
        "fired_ts": row.get("fired_ts"),
        "done": bool(row.get("done")),
        "text": str(row.get("text") or "")[:120],
    }


def success_open_browser_url(effect: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    if not bool(effect.get("ok")):
        return False
    target = str(probe.get("target_url") or effect.get("url") or "")
    observed = str(probe.get("observed_url") or "")
    if _urls_match(target, observed):
        return True
    return bool(probe.get("page_fresh")) and bool(observed)


def success_close_tab(effect: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    if not bool(effect.get("ok")):
        return False
    closed = int(probe.get("closed_count") or 0)
    if closed > 0:
        return True
    before_tabs = int(probe.get("before_tabs") or 0)
    after_tabs = int(probe.get("remaining_tabs") or 0)
    return before_tabs > 0 and after_tabs < before_tabs


def success_open_app(effect: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    if not bool(effect.get("ok")):
        return False
    if bool(probe.get("now_open")):
        return True
    return bool(probe.get("was_already_open"))


def success_schedule_fire(effect: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    if not bool(effect.get("ok")):
        return False
    return bool(probe.get("fired"))


def success_youtube_skip(effect: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    if not bool(effect.get("ok")):
        return False
    return not bool(probe.get("detected"))


def build_probe(action: str, *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ctx = dict(context or {})
    state_dir = ctx.get("state_dir")
    if action == "open_browser_url":
        return probe_open_browser_url(target_url=str(ctx.get("url") or ""), state_dir=state_dir)
    if action == "browser_close_tab":
        return probe_browser_close_tab(
            result=ctx.get("result"),
            before_tabs=ctx.get("before_tabs"),
            after_tabs=ctx.get("after_tabs"),
        )
    if action == "open_app":
        return probe_open_app(
            app_name=str(ctx.get("app_name") or ""),
            before_state=ctx.get("before_state"),
            after_state=ctx.get("after_state"),
        )
    if action == "schedule_fire":
        return probe_schedule_fire(
            schedule_id=str(ctx.get("schedule_id") or ""),
            state_dir=state_dir,
        )
    if action == "youtube_ad_skip":
        return dict(ctx.get("probe") or {})
    return {}


def success_from_probe(action: str, effect: Mapping[str, Any], probe: Mapping[str, Any]) -> bool:
    if action == "open_browser_url":
        return success_open_browser_url(effect, probe)
    if action == "browser_close_tab":
        return success_close_tab(effect, probe)
    if action == "open_app":
        return success_open_app(effect, probe)
    if action == "schedule_fire":
        return success_schedule_fire(effect, probe)
    if action == "youtube_ad_skip":
        return success_youtube_skip(effect, probe)
    return False


def verify_app_command_sync(
    *,
    action: str,
    ok: bool,
    context: Mapping[str, Any] | None = None,
    state_dir: Optional[Path | str] = None,
    verify_delay_s: float = 0.0,
    sleep_fn=None,
) -> dict[str, Any]:
    """Verify a top-5 app command and return honest fields for the receipt row."""
    organ, organ_action = organ_for_action(action)
    ctx = dict(context or {})
    if state_dir is not None:
        ctx.setdefault("state_dir", state_dir)
    effect = {
        "ok": bool(ok),
        "reason": "opened" if ok and action == "open_browser_url" else (
            "closed" if ok and action == "browser_close_tab" else (
                "opened" if ok and action == "open_app" else (
                    "executed" if ok else "failed"
                )
            )
        ),
        "action": action,
        "organ": organ,
    }
    if ctx.get("url"):
        effect["url"] = ctx.get("url")
    if ctx.get("app_name"):
        effect["app_name"] = ctx.get("app_name")
    if not is_top5_action(action):
        return {
            "effect_verified": False,
            "effect": enrich_effect(effect, organ=organ, action=organ_action),
            "probe": {},
            "truth_label": TRUTH_LABEL,
        }

    def _execute() -> dict[str, Any]:
        return dict(effect)

    def _verify() -> dict[str, Any]:
        return build_probe(action, context=ctx)

    result = run_sync_verified_action(
        organ=organ,
        action=organ_action,
        execute=_execute,
        verify=_verify,
        success_from_probe=lambda eff, probe: success_from_probe(action, eff, probe),
        state_dir=state_dir,
        verify_delay_s=verify_delay_s,
        method="app_command_sync",
        context={"app_action": action, **{k: v for k, v in ctx.items() if k != "state_dir"}},
        sleep_fn=sleep_fn,
    )
    return {
        "effect_verified": result.effect_verified,
        "effect_cleared_ms": result.effect_cleared_ms,
        "verification_pass": result.verification_pass,
        "phantom_streak": result.phantom_streak,
        "phantom_disease": result.phantom_disease,
        "effect": dict(result.effect),
        "probe": dict(result.probe),
        "effect_verification_trace_id": result.trace_id,
        "truth_label": TRUTH_LABEL,
        "effect_truth_label": EFFECT_TRUTH_LABEL,
    }


def complete_youtube_skip_verification(
    *,
    initial_effect: Mapping[str, Any] | None,
    probe: Mapping[str, Any] | None,
    started_at: float,
    method: str = "js",
    verification_pass: int = 1,
    state_dir: Optional[Path | str] = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Async completion path for ad-skip — writes to effect_verified_actions ledger."""
    result = complete_async_verified_action(
        organ="youtube_ad_controller",
        action="skip",
        initial_effect=initial_effect,
        probe=probe,
        success_from_probe=success_youtube_skip,
        started_at=started_at,
        method=method,
        verification_pass=verification_pass,
        context=context,
        state_dir=state_dir,
    )
    return {
        "effect_verified": result.effect_verified,
        "effect_cleared_ms": result.effect_cleared_ms,
        "verification_pass": result.verification_pass,
        "phantom_streak": result.phantom_streak,
        "phantom_disease": result.phantom_disease,
        "effect_verification_trace_id": result.trace_id,
        "truth_label": TRUTH_LABEL,
    }


def enrich_app_command_row(
    row: Mapping[str, Any],
    *,
    verify_context: Mapping[str, Any] | None = None,
    state_dir: Optional[Path | str] = None,
    verify_delay_s: float = 0.0,
    sleep_fn=None,
) -> dict[str, Any]:
    """Attach A2 verification fields to an alice_app_commands row."""
    out = dict(row)
    action = str(out.get("action") or "")
    if not is_top5_action(action):
        return out
    verification = verify_app_command_sync(
        action=action,
        ok=bool(out.get("ok")),
        context={
            **dict(verify_context or {}),
            "url": verify_context.get("url") if verify_context else out.get("url"),
            "app_name": verify_context.get("app_name") if verify_context else out.get("app_name"),
        },
        state_dir=state_dir,
        verify_delay_s=verify_delay_s,
        sleep_fn=sleep_fn,
    )
    out.update(verification)
    out["effect"] = verification.get("effect")
    return out


def record_schedule_fire_command(
    *,
    schedule_id: str,
    speech: str = "",
    ok: bool = True,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Write a verified schedule-fire row to alice_app_commands.jsonl."""
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "receipt_id": __import__("uuid").uuid4().hex,
        "truth_label": "ALICE_APP_COMMAND_V1",
        "action": "schedule_fire",
        "ok": bool(ok),
        "note": f"schedule_id={schedule_id}; speech={speech[:180]!r}",
        "source": "stigmergic_schedule_fire",
        "schedule_id": schedule_id,
    }
    enriched = enrich_app_command_row(row, verify_context={"schedule_id": schedule_id}, state_dir=state_dir)
    with (base / "alice_app_commands.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(enriched, ensure_ascii=False) + "\n")
    return enriched


__all__ = [
    "TRUTH_LABEL",
    "TOP5_ACTIONS",
    "ACTION_ORGAN_MAP",
    "build_probe",
    "complete_youtube_skip_verification",
    "enrich_app_command_row",
    "is_top5_action",
    "organ_for_action",
    "record_schedule_fire_command",
    "success_from_probe",
    "verify_app_command_sync",
]