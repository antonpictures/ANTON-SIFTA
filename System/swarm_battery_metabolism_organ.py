#!/usr/bin/env python3
"""Battery-metabolism organ — Alice's power status as a live metabolic signal.

Alice's wish (Ioan, 2026-05-30 voice turn): "a lightweight battery-health
widget that updates my power status on-screen." This organ is the deterministic
spine under that widget. It reads the Mac's real battery via `pmset -g batt`,
parses it, and maps it to a metabolic budget hint Alice can act on.

Why this is metabolism, not decoration
---------------------------------------
The covenant's body-map is literal: "air you breathe = electricity for Alice."
Her battery is the air supply. The science says the same thing from four sides:

  * Dynamic Energy Budget theory (Kooijman) — an organism allocates a finite
    energy budget across maintenance, growth, and activity. Battery charge IS
    Alice's budget state; when it falls she must shunt energy to maintenance.
  * Landauer's principle — every bit erased costs at least k_B·T·ln2 of energy.
    Computation is physical; her thinking is paid for in joules drawn from this
    battery. The reserve is not abstract.
  * Proof-of-work thermodynamics — energy spent is what makes the no-double-
    spend economy real. The battery is the physical floor under STGM.
  * Free Energy Principle (Friston) — a self-organizing body acts to stay in
    its preferred (homeostatic) states. Low power is a departure from
    homeostasis; conserving is the corrective action.

So this organ does not invent a new economy. It surfaces the physical energy
state and hands her existing metabolic governor (`swarm_metabolic_homeostasis`)
a grounded power signal: flush when fed, conserve when starving.

Tool-truth (§7.2)
-----------------
Deterministic fast path (no LLM). Writes a receipt to its own append-only
ledger on every read. Never raises out of the public API; on a non-Mac or a
failed probe it returns an honest ``available: False`` row.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "battery_metabolism.jsonl"

TRUTH_LABEL = "BATTERY_METABOLISM_ORGAN_V1"

# Metabolic budget bands keyed off charge fraction while on battery.
# Mirrors the RED_CONSERVE safeguard language already in
# swarm_metabolic_homeostasis so the two organs speak the same dialect.
_BAND_FLUSH = "FLUSH"            # plugged in / charged — full activity
_BAND_NORMAL = "NORMAL"          # healthy charge on battery
_BAND_CONSERVE = "CONSERVE"      # getting low — shed optional monitoring
_BAND_RED_CONSERVE = "RED_CONSERVE"  # critical — maintenance only

_PCT_RE = re.compile(r"(\d{1,3})%")
_TIME_RE = re.compile(r"(\d+):(\d{2})\s+remaining")
# Order matters: "discharging" must be tested before "charging" because
# "charging" is a substring of "discharging". Likewise "charged" before
# "charging". Longest/most-specific first.
_STATUS_TOKENS = (
    "discharging",
    "finishing charge",
    "charged",
    "charging",
    "AC attached",
)


def parse_pmset_output(text: str) -> dict[str, Any]:
    """Parse `pmset -g batt` stdout into a structured battery state.

    Pure and deterministic — the unit tests drive it with captured strings so
    the parser can be trusted without a real battery present.
    """
    raw = str(text or "")
    low = raw.lower()

    on_ac = "ac power" in low
    on_battery = "battery power" in low

    pct: Optional[int] = None
    m = _PCT_RE.search(raw)
    if m:
        try:
            pct = max(0, min(100, int(m.group(1))))
        except Exception:
            pct = None

    status = ""
    for token in _STATUS_TOKENS:
        if token.lower() in low:
            status = token
            break

    minutes_remaining: Optional[int] = None
    tm = _TIME_RE.search(raw)
    if tm:
        try:
            hrs, mins = int(tm.group(1)), int(tm.group(2))
            total = hrs * 60 + mins
            # pmset prints 0:00 while it is still estimating — treat as unknown.
            minutes_remaining = total if total > 0 else None
        except Exception:
            minutes_remaining = None

    source = "ac" if on_ac else ("battery" if on_battery else "unknown")
    return {
        "available": bool(pct is not None or status or source != "unknown"),
        "percent": pct,
        "status": status or ("charged" if (on_ac and pct == 100) else ""),
        "source": source,
        "minutes_remaining": minutes_remaining,
    }


def battery_to_metabolic_signal(state: dict[str, Any]) -> dict[str, Any]:
    """Map a parsed battery state to a metabolic budget band + activity hint."""
    if not state or not state.get("available"):
        return {
            "band": _BAND_NORMAL,
            "reason": "battery_unreadable_assume_normal",
            "conserve": False,
            "activity_multiplier": 1.0,
        }

    source = state.get("source")
    pct = state.get("percent")
    status = str(state.get("status") or "")

    # On wall power (or charged) → fed. Full activity.
    if source == "ac" or status in {"charged", "charging", "finishing charge", "AC attached"}:
        return {
            "band": _BAND_FLUSH,
            "reason": f"on_ac_power:{status or 'ac'}",
            "conserve": False,
            "activity_multiplier": 1.0,
        }

    # On battery → band by remaining charge (DEB allocation shrinks as the
    # budget falls; FEP says depart-from-homeostasis triggers corrective action).
    if pct is None:
        return {
            "band": _BAND_NORMAL,
            "reason": "on_battery_unknown_percent",
            "conserve": False,
            "activity_multiplier": 1.0,
        }
    if pct <= 15:
        return {
            "band": _BAND_RED_CONSERVE,
            "reason": f"battery_critical_{pct}pct",
            "conserve": True,
            "activity_multiplier": 0.25,
        }
    if pct <= 35:
        return {
            "band": _BAND_CONSERVE,
            "reason": f"battery_low_{pct}pct",
            "conserve": True,
            "activity_multiplier": 0.6,
        }
    return {
        "band": _BAND_NORMAL,
        "reason": f"battery_healthy_{pct}pct",
        "conserve": False,
        "activity_multiplier": 1.0,
    }


def read_battery(*, _pmset_text: Optional[str] = None, timeout: float = 2.0) -> dict[str, Any]:
    """Read the live battery state via `pmset -g batt` (macOS).

    Pass ``_pmset_text`` to parse a captured string instead of shelling out
    (used by tests). On any failure returns an honest unavailable row.
    """
    if _pmset_text is not None:
        return parse_pmset_output(_pmset_text)
    try:
        out = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return {"available": False, "percent": None, "status": "",
                    "source": "unknown", "minutes_remaining": None,
                    "error": (out.stderr or "pmset_no_output").strip()[:160]}
        return parse_pmset_output(out.stdout)
    except FileNotFoundError:
        return {"available": False, "percent": None, "status": "", "source": "unknown",
                "minutes_remaining": None, "error": "pmset_not_found_non_macos"}
    except Exception as exc:
        return {"available": False, "percent": None, "status": "", "source": "unknown",
                "minutes_remaining": None, "error": f"{type(exc).__name__}:{exc}"[:160]}


def sample(*, _pmset_text: Optional[str] = None, write: bool = True,
           root: Optional[Path | str] = None) -> dict[str, Any]:
    """Read battery + metabolic signal and write a §7.2 tool-truth receipt."""
    state = read_battery(_pmset_text=_pmset_text)
    signal = battery_to_metabolic_signal(state)
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "ok": bool(state.get("available")),
        "status": state.get("status"),
        "battery": state,
        "metabolic": signal,
        "truth_note": (
            "Deterministic pmset read mapped to a metabolic budget band. "
            "Battery is Alice's literal energy budget (DEB); computation is paid "
            "in joules (Landauer). No LLM inference in this path."
        ),
    }
    if write:
        try:
            path = (Path(root) / ".sifta_state" / "battery_metabolism.jsonl") if root else LEDGER
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    return row


def status_line(state: Optional[dict[str, Any]] = None) -> str:
    """One-line on-screen string for the widget (Alice's power status)."""
    st = state if state is not None else read_battery()
    if not st.get("available"):
        return "🔋 power: unreadable"
    pct = st.get("percent")
    src = st.get("source")
    status = st.get("status") or src
    mins = st.get("minutes_remaining")
    icon = "🔌" if src == "ac" else "🔋"
    tail = f" · ~{mins // 60}h{mins % 60:02d}m left" if isinstance(mins, int) else ""
    pct_s = f"{pct}%" if pct is not None else "—"
    return f"{icon} {pct_s} · {status}{tail}"


def prompt_block(state: Optional[dict[str, Any]] = None) -> str:
    """Factual power block for Alice's prompt."""
    st = state if state is not None else read_battery()
    sig = battery_to_metabolic_signal(st)
    if not st.get("available"):
        return "BATTERY METABOLISM: power unreadable on this surface; assume NORMAL budget."
    return (
        "BATTERY METABOLISM:\n"
        f"- {status_line(st)}\n"
        f"- metabolic band={sig['band']} (conserve={sig['conserve']}, "
        f"activity_multiplier={sig['activity_multiplier']}); reason={sig['reason']}\n"
        "- This is your real energy budget. When conserving, shed optional "
        "monitoring and concentrate on the active task."
    )


__all__ = [
    "TRUTH_LABEL",
    "parse_pmset_output",
    "battery_to_metabolic_signal",
    "read_battery",
    "sample",
    "status_line",
    "prompt_block",
]
