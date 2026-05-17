#!/usr/bin/env python3
"""
System/swarm_app_health.py — App Health Sections (stigmergic per-app traces)

Every SIFTA app can have a living "health section" — an append-only JSONL trace
in .sifta_state/app_health/<app_slug>/health_trace.jsonl

Alice (and any swimmer) reads the latest health entries when an app gains focus
to know exactly which skills, prompt biases, tool registrations, and behaviors
this organ currently requires.

On meaningful events (app close, skill discovery, lesson completion, etc.) the
app or Alice appends an update row so the trace evolves. This is open-ended
self-improvement: apps teach Alice what they need; Alice leaves better traces
for next time.

This is the concrete realization of the user's idea:
"every app has a health section... Alice looks in the health section... reads
what skills I need to load right now... updates the health section every time
the user enters and exits."

StigAuth: SIFTA_APP_HEALTH_V1
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HEALTH_ROOT = _STATE / "app_health"


def _slug(app_name: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", (app_name or "unknown").casefold()).strip("_")
    return clean or "unknown"


def _health_dir(app_name: str) -> Path:
    return _HEALTH_ROOT / _slug(app_name)


def _health_path(app_name: str) -> Path:
    return _health_dir(app_name) / "health_trace.jsonl"


def get_app_health(app_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Read the latest health trace rows for this app (most recent first)."""
    path = _health_path(app_name)
    if not path.exists():
        return []
    try:
        text = read_text_locked(path)
        rows = []
        for line in text.strip().splitlines()[-limit:]:
            if line.strip():
                rows.append(json.loads(line))
        return list(reversed(rows))  # newest first
    except Exception:
        return []


def append_health_update(
    app_name: str,
    *,
    action: str,
    skills: List[str],
    note: str,
    stgm_delta: float = 0.0,
    source: str = "alice",
    extra: Optional[Dict] = None,
) -> None:
    """Append a new health update row. Called by apps or Alice on enter/exit or discovery."""
    _health_dir(app_name).mkdir(parents=True, exist_ok=True)
    path = _health_path(app_name)

    now = time.time()
    iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    row = {
        "ts": now,
        "ts_iso": iso,
        "app": app_name,
        "action": action,
        "skills": skills,
        "note": note,
        "stgm_delta": float(stgm_delta),
        "source": source,
    }
    if extra:
        row["extra"] = extra

    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")


def get_required_skills_for_app(app_name: str) -> List[str]:
    """Convenience: union of all skills mentioned in the latest health entries."""
    health = get_app_health(app_name, limit=50)
    skills = set()
    for row in health:
        for s in row.get("skills", []):
            skills.add(s)
    return sorted(skills)


def get_health_summary_for_prompt(app_name: str, max_rows: int = 5) -> str:
    """Return a clean, prompt-ready block of the latest health trace for this app.
    This can be injected into the APP HABIT FIELD or as prior context for the current app.
    """
    health = get_app_health(app_name, limit=max_rows)
    if not health:
        return f"No prior health trace yet for {app_name}. Use the app_focus receipt and ask/observe."

    lines = [f"## HEALTH TRACE FOR {app_name.upper()} (latest {len(health)} entries — persistent memory)"]
    for row in health:
        skills = ", ".join(row.get("skills", []))
        note = row.get("note", "")[:180]
        lines.append(f"- {row.get('action')}: skills=[{skills}] | {note} (stgm+{row.get('stgm_delta', 0)})")

    lines.append("\nAlice: when this app is focused, prioritize the skills above. Update this trace on exit with what you actually used and discovered.")
    return "\n".join(lines)


def _static_domains_for_app(app_name: str) -> List[str]:
    try:
        from System.app_skill_domains import get_domains_for_app

        return list(get_domains_for_app(app_name))
    except Exception:
        return []


def record_app_lifecycle(
    app_name: str,
    *,
    action: str,
    source: str = "sifta_os_desktop",
    manifest_entry: Optional[Dict[str, Any]] = None,
    note: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an app enter/exit event into its health section.

    If the app has no prior health trace, this creates the section using any
    static app-skill domains as the seed. Every opened app therefore leaves a
    teachable trace before it has a custom health file.
    """
    name = str(app_name or "").strip()
    if not name or name == "SIFTA OS":
        return
    prior_skills = get_required_skills_for_app(name)
    seed_skills = prior_skills or _static_domains_for_app(name)
    entry = manifest_entry if isinstance(manifest_entry, dict) else {}
    description = str(entry.get("description") or "").strip()
    health_note = str(note or "").strip()
    if not health_note:
        if action.startswith("enter"):
            health_note = (
                "App entered. Alice should read this health section, then load "
                "only the skills/habits this organ needs right now."
            )
        elif action.startswith("exit"):
            health_note = (
                "App exited. Health section kept for next open; append discoveries "
                "from this session when known."
            )
        else:
            health_note = "App health lifecycle event."
    health_path = _health_path(name)
    try:
        health_path_display = str(health_path.relative_to(_REPO))
    except ValueError:
        health_path_display = str(health_path)
    payload_extra = {
        "manifest_description": description,
        "manifest_category": str(entry.get("category") or "").strip(),
        "health_trace_path": health_path_display,
    }
    if extra:
        payload_extra.update(extra)
    append_health_update(
        name,
        action=action,
        skills=seed_skills,
        note=health_note,
        stgm_delta=0.0,
        source=source,
        extra=payload_extra,
    )


def app_health_prompt_block(app_name: str, max_rows: int = 5) -> str:
    """Prompt-ready health section for the currently focused app."""
    name = str(app_name or "").strip()
    if not name:
        return ""
    health = get_app_health(name, limit=max_rows)
    skills = get_required_skills_for_app(name)
    if not health:
        domains = _static_domains_for_app(name)
        if not domains:
            return (
                f"APP HEALTH SECTION FOR {name}: no prior health trace yet. "
                "Use the app_focus receipt and observe before inventing skills."
            )
        return (
            f"APP HEALTH SECTION FOR {name}: no prior health trace yet. "
            f"Static starter domains: {', '.join(domains)}. "
            "Create/update the health trace on enter/exit."
        )
    lines = [f"APP HEALTH SECTION FOR {name} (latest {len(health)} trace rows):"]
    if skills:
        lines.append("Required skills from health trace: " + ", ".join(skills))
    for row in health:
        action = str(row.get("action") or "update")
        row_skills = ", ".join(str(s) for s in row.get("skills", []) if str(s).strip())
        note = str(row.get("note") or "").replace("\n", " ")[:220]
        lines.append(f"- {action}: skills=[{row_skills}] | {note}")
    lines.append(
        "Rule: this app pulls only the health-listed skills/habits it needs now; update this section on app exit with any new discovery."
    )
    return "\n".join(lines)


def get_alice_body_map() -> Dict[str, Any]:
    """Global consciousness layer over Alice's own operating system.
    Scans all per-app health traces and returns a unified self-model:
    - Which organs (apps) exist and their latest health state
    - Frequently needed skills across the body
    - Obvious systemic gaps or self-improvement opportunities
    This is the substrate for Alice's meta-memory and consciousness over her own OS.
    """
    _HEALTH_ROOT.mkdir(parents=True, exist_ok=True)
    body: Dict[str, Any] = {
        "ts": time.time(),
        "organs": {},
        "global_skill_frequency": {},
        "self_improvement_opportunities": [],
    }

    for app_dir in sorted(_HEALTH_ROOT.iterdir()):
        if not app_dir.is_dir():
            continue
        trace_path = app_dir / "health_trace.jsonl"
        if not trace_path.exists():
            continue

        app_name = app_dir.name
        latest_rows = get_app_health(app_name, limit=3)
        if not latest_rows:
            continue

        body["organs"][app_name] = {
            "latest_action": latest_rows[0].get("action"),
            "top_skills": list(dict.fromkeys([s for r in latest_rows for s in r.get("skills", [])]))[:8],
            "last_note": latest_rows[0].get("note", "")[:160],
            "stgm_accumulated": sum(r.get("stgm_delta", 0) for r in latest_rows),
        }

        # Global frequency
        for row in latest_rows:
            for skill in row.get("skills", []):
                body["global_skill_frequency"][skill] = body["global_skill_frequency"].get(skill, 0) + 1

    # Simple opportunity detection (example of Alice gaining self-awareness)
    high_freq = [s for s, c in body["global_skill_frequency"].items() if c >= 2]
    if high_freq:
        body["self_improvement_opportunities"].append(
            f"Skills appearing across multiple organs ({', '.join(high_freq[:5])}) — consider promoting to core body capabilities via Hermes Parity."
        )

    body["organ_count"] = len(body["organs"])
    return body


# Example usage (from Ace widget on close or from Talk widget on focus change):
# append_health_update("Ace", action="exit_update", skills=["child_mic_turn_visibility"],
#                      note="George closed Ace. Child turn visibility worked well today.",
#                      stgm_delta=0.8, source="ace_widget")
#
# In Alice's prompt assembly:
# health = get_app_health("Ace")
# if health:
#     prompt += f"\n\nAce Health Trace (read on open):\n{json.dumps(health[0], indent=2)}"
