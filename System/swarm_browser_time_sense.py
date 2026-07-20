#!/usr/bin/env python3
"""swarm_browser_time_sense.py — Alice feels browser time (loading → settled).

George (2026-07-11 glass): search mercedes sedan *did* land, but mouth said
"did not land… still at old URL" — no sense of still-loading vs finished.

Doctrine: Alice Browser is a limb. She must know:
  - ordered navigation at t0
  - load started / still loading (age since start)
  - load finished (duration of that load)
  - settled URL *now* vs target ordered
  - do NOT claim land fail from a stale URL while a load is in flight
  - do NOT claim "I searched X" as finished until load_finished for that order

Truth label: BROWSER_TIME_SENSE_V1
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

TRUTH_LABEL = "BROWSER_TIME_SENSE_V1"
_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SNAPSHOT = "browser_time_sense.json"
_LEDGER = "browser_time_sense.jsonl"

# Phases of one navigation cycle
PHASE_IDLE = "idle"
PHASE_ORDERED = "ordered"  # Talk ordered navigate; may not have started yet
PHASE_LOADING = "loading"  # loadStarted
PHASE_SETTLED = "settled"  # loadFinished ok
PHASE_FAILED = "failed"  # loadFinished not ok
PHASE_STALE_MISMATCH = "stale_or_mismatch"  # observed ≠ target after settle


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _now() -> float:
    return time.time()


def _write_snapshot(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / _SNAPSHOT).write_text(
            json.dumps(row, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with (root / _LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_time_sense(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    path = _state_dir(state_dir) / _SNAPSHOT
    if not path.is_file():
        return {
            "truth_label": TRUTH_LABEL,
            "phase": PHASE_IDLE,
            "url": "",
            "target_url": "",
        }
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        return row if isinstance(row, dict) else {}
    except Exception:
        return {"truth_label": TRUTH_LABEL, "phase": PHASE_IDLE}


def note_navigation_ordered(
    target_url: str,
    *,
    owner_text: str = "",
    state_dir: Optional[Path | str] = None,
    source: str = "talk_order",
) -> dict[str, Any]:
    """Call when Talk/effector orders a navigate/search — before claiming done."""
    now = _now()
    row = {
        "truth_label": TRUTH_LABEL,
        "ts": now,
        "event": "navigation_ordered",
        "phase": PHASE_ORDERED,
        "target_url": str(target_url or "").strip(),
        "url": "",
        "ordered_at": now,
        "load_started_at": None,
        "load_finished_at": None,
        "load_duration_s": None,
        "load_ok": None,
        "owner_preview": str(owner_text or "")[:160],
        "source": source,
    }
    _write_snapshot(row, state_dir=state_dir)
    return row


def note_load_started(
    url: str = "",
    *,
    title: str = "",
    state_dir: Optional[Path | str] = None,
    source: str = "load_started",
) -> dict[str, Any]:
    prev = load_time_sense(state_dir=state_dir)
    now = _now()
    ordered_at = float(prev.get("ordered_at") or now)
    row = {
        **prev,
        "truth_label": TRUTH_LABEL,
        "ts": now,
        "event": "load_started",
        "phase": PHASE_LOADING,
        "url": str(url or prev.get("url") or "").strip(),
        "title": str(title or prev.get("title") or "").strip(),
        "load_started_at": now,
        "load_finished_at": None,
        "load_duration_s": None,
        "load_ok": None,
        "source": source,
        "age_since_order_s": round(now - ordered_at, 2) if ordered_at else None,
    }
    if not row.get("target_url") and row.get("url"):
        row["target_url"] = row["url"]
    if not row.get("ordered_at"):
        row["ordered_at"] = now
    _write_snapshot(row, state_dir=state_dir)
    return row


def note_load_finished(
    url: str = "",
    *,
    title: str = "",
    ok: bool = True,
    duration_s: float | None = None,
    state_dir: Optional[Path | str] = None,
    source: str = "load_finished",
) -> dict[str, Any]:
    prev = load_time_sense(state_dir=state_dir)
    now = _now()
    started = float(prev.get("load_started_at") or prev.get("ordered_at") or now)
    dur = duration_s
    if dur is None:
        dur = max(0.0, now - started)
    target = str(prev.get("target_url") or "").strip()
    final_url = str(url or "").strip()
    phase = PHASE_SETTLED if ok else PHASE_FAILED
    row = {
        **prev,
        "truth_label": TRUTH_LABEL,
        "ts": now,
        "event": "load_finished",
        "phase": phase,
        "url": final_url,
        "title": str(title or prev.get("title") or "").strip(),
        "load_finished_at": now,
        "load_duration_s": round(float(dur), 2),
        "load_ok": bool(ok),
        "source": source,
        "age_since_order_s": (
            round(now - float(prev["ordered_at"]), 2)
            if prev.get("ordered_at")
            else None
        ),
    }
    if target and final_url and not urls_roughly_match(target, final_url):
        # Settled on something else — still settled, flag mismatch for mouth
        row["url_matches_target"] = False
        row["mismatch_note"] = "settled_url_differs_from_ordered_target"
    else:
        row["url_matches_target"] = True if (target and final_url) else None
    _write_snapshot(row, state_dir=state_dir)
    return row


def urls_roughly_match(a: str, b: str) -> bool:
    """Loose match for DDG query params (order/extra ia= ok)."""
    try:
        from System.swarm_app_command_effect_verification import browser_urls_match

        if browser_urls_match(a, b):
            return True
    except Exception:
        pass
    sa, sb = str(a or "").strip().rstrip("/"), str(b or "").strip().rstrip("/")
    if not sa or not sb:
        return False
    if sa == sb:
        return True
    # Compare host + path + q= if present
    try:
        pa, pb = urlparse(sa), urlparse(sb)
        if pa.netloc.lower().removeprefix("www.") != pb.netloc.lower().removeprefix("www."):
            return False
        if pa.path.rstrip("/") != pb.path.rstrip("/"):
            # duckduckgo / vs /html ok
            if {pa.path.rstrip("/"), pb.path.rstrip("/")} - {"", "/"}:
                if pa.path.rstrip("/") not in ("", "/") or pb.path.rstrip("/") not in ("", "/"):
                    if pa.path.rstrip("/") != pb.path.rstrip("/"):
                        return False
        qa = parse_qs(pa.query)
        qb = parse_qs(pb.query)
        if "q" in qa and "q" in qb:
            return unquote(qa["q"][0]).lower().replace("+", " ") == unquote(
                qb["q"][0]
            ).lower().replace("+", " ")
        # host-only same path without q
        return pa.netloc.lower() == pb.netloc.lower() and (
            not qa.get("q") or not qb.get("q")
        )
    except Exception:
        return sa in sb or sb in sa


def feel_browser_now(
    *,
    observed_url: str = "",
    state_dir: Optional[Path | str] = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Live proprioception snapshot for Talk/mouth."""
    t = now if now is not None else _now()
    sense = load_time_sense(state_dir=state_dir)
    phase = str(sense.get("phase") or PHASE_IDLE)
    load_started = sense.get("load_started_at")
    load_finished = sense.get("load_finished_at")
    ordered_at = sense.get("ordered_at")
    age_load = None
    if phase == PHASE_LOADING and load_started:
        age_load = round(t - float(load_started), 2)
    elif load_finished and load_started:
        age_load = float(sense.get("load_duration_s") or 0)

    # Enrich with freshest page state if observed empty
    obs = str(observed_url or sense.get("url") or "").strip()
    if not obs:
        try:
            from System.swarm_browser_page_state import latest_page_state

            st = latest_page_state(state_dir=state_dir, max_age_s=120.0) or {}
            obs = str(st.get("url") or st.get("current_url") or "").strip()
        except Exception:
            pass

    target = str(sense.get("target_url") or "").strip()
    matches = None
    if target and obs:
        matches = urls_roughly_match(target, obs)

    still_loading = phase in {PHASE_ORDERED, PHASE_LOADING}
    # If ordered long ago but never finished, still loading
    if phase == PHASE_ORDERED and ordered_at and (t - float(ordered_at)) < 25.0:
        still_loading = True

    return {
        "truth_label": TRUTH_LABEL,
        "ts": t,
        "phase": phase,
        "still_loading": still_loading,
        "settled": phase == PHASE_SETTLED,
        "load_ok": sense.get("load_ok"),
        "target_url": target,
        "url_now": obs,
        "title": sense.get("title") or "",
        "ordered_at": ordered_at,
        "load_started_at": load_started,
        "load_finished_at": load_finished,
        "load_duration_s": sense.get("load_duration_s"),
        "loading_for_s": age_load,
        "url_matches_target": matches if matches is not None else sense.get("url_matches_target"),
        "owner_line": _owner_line(
            phase=phase,
            still_loading=still_loading,
            target=target,
            obs=obs,
            matches=matches,
            duration_s=sense.get("load_duration_s"),
            loading_for_s=age_load,
        ),
    }


def _owner_line(
    *,
    phase: str,
    still_loading: bool,
    target: str,
    obs: str,
    matches: bool | None,
    duration_s: Any,
    loading_for_s: Any,
) -> str:
    if still_loading:
        age = loading_for_s if loading_for_s is not None else "?"
        return (
            f"My Alice Browser is still loading"
            f"{f' (about {age}s so far)' if age != '?' else ''}. "
            f"I will not claim land or fail yet."
            + (f" Target: {target}." if target else "")
        )
    if phase == PHASE_SETTLED and matches:
        d = duration_s if duration_s is not None else "?"
        return (
            f"My Alice Browser finished loading in ~{d}s and is on the ordered page. "
            f"Now: {obs or target}."
        )
    if phase == PHASE_SETTLED and matches is False:
        return (
            f"My Alice Browser finished a load, but the live URL is not the one I ordered. "
            f"Ordered: {target or 'unknown'}. Now: {obs or 'unknown'}."
        )
    if phase == PHASE_FAILED:
        return "My Alice Browser load finished with a failure signal — not a clean land."
    if obs:
        return f"My Alice Browser is currently at {obs}."
    return "I do not yet have a fresh browser time-sense receipt."


def judge_land_claim(
    target_url: str,
    observed_url: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """What mouth may say after verify delay — never false fail while loading."""
    feel = feel_browser_now(observed_url=observed_url, state_dir=state_dir)
    target = str(target_url or feel.get("target_url") or "").strip()
    obs = str(observed_url or feel.get("url_now") or "").strip()
    match = urls_roughly_match(target, obs) if (target and obs) else False

    if feel.get("still_loading") and not match:
        return {
            "ok": None,  # unknown yet
            "action": "wait_still_loading",
            "speak_fail": False,
            "speak_success": False,
            "reason": "still_loading_do_not_claim_land_fail",
            "feel": feel,
            "system_line": feel.get("owner_line"),
        }
    if match:
        return {
            "ok": True,
            "action": "landed",
            "speak_fail": False,
            "speak_success": True,
            "reason": "url_matches_target",
            "feel": feel,
            "system_line": (
                "Landed: browser is on the ordered page"
                + (
                    f" after ~{feel.get('load_duration_s')}s."
                    if feel.get("load_duration_s") is not None
                    else "."
                )
            ),
        }
    # Settled mismatch — real fail only if not loading
    if feel.get("still_loading"):
        return {
            "ok": None,
            "action": "wait_still_loading",
            "speak_fail": False,
            "speak_success": False,
            "reason": "mismatch_but_still_loading",
            "feel": feel,
            "system_line": feel.get("owner_line"),
        }
    return {
        "ok": False,
        "action": "mismatch_after_settle",
        "speak_fail": True,
        "speak_success": False,
        "reason": "settled_on_different_url",
        "feel": feel,
        "system_line": (
            f"My browser did not settle on {target}; it is at {obs or 'unknown'}. "
            f"(phase={feel.get('phase')}, load_duration_s={feel.get('load_duration_s')})"
        ),
    }


def time_sense_prompt_block(
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 700,
) -> str:
    feel = feel_browser_now(state_dir=state_dir)
    lines = [
        "BROWSER TIME SENSE (limb proprioception — not optional):",
        f"- phase={feel.get('phase')} still_loading={feel.get('still_loading')} "
        f"settled={feel.get('settled')}",
        f"- url_now={feel.get('url_now') or 'unknown'}",
        f"- target_ordered={feel.get('target_url') or 'none'}",
        f"- load_duration_s={feel.get('load_duration_s')} "
        f"loading_for_s={feel.get('loading_for_s')}",
        f"- body_line: {feel.get('owner_line')}",
        "Rules: If still_loading, do NOT claim 'I searched/opened and finished' "
        "and do NOT claim permanent fail from an old URL. Wait for settled.",
        "If settled and url matches order, say what is on screen from receipts.",
    ]
    block = "\n".join(lines)
    return block[:max_chars]


__all__ = [
    "TRUTH_LABEL",
    "PHASE_IDLE",
    "PHASE_ORDERED",
    "PHASE_LOADING",
    "PHASE_SETTLED",
    "PHASE_FAILED",
    "note_navigation_ordered",
    "note_load_started",
    "note_load_finished",
    "load_time_sense",
    "feel_browser_now",
    "judge_land_claim",
    "urls_roughly_match",
    "time_sense_prompt_block",
]
