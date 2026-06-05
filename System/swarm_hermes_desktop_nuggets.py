#!/usr/bin/env python3
"""Hermes Desktop research nuggets for Alice's body map.

This organ records small, reusable lessons from the external Hermes Desktop
code/docs without turning Hermes into a separate Alice. Hermes is an arm/body
part when routed through SIFTA receipts; its desktop patterns are upgrade
nuggets for Alice's own Python/Qt OS surface.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback for early boot imports
    append_line_locked = None


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "hermes_desktop_research_nuggets.jsonl"
TRUTH_LABEL = "HERMES_DESKTOP_NUGGETS_V1"

OFFICIAL_LINKS = {
    "desktop_docs": "https://hermes-agent.nousresearch.com/docs/user-guide/desktop",
    "github_repo": "https://github.com/NousResearch/hermes-agent",
}

LOCAL_INSPECTION = {
    "clone_scope": "shallow external clone inspected outside the SIFTA repo",
    "desktop_readme": "apps/desktop/README.md",
    "desktop_package": "apps/desktop/package.json",
    "electron_main": "apps/desktop/electron/main.cjs",
    "bootstrap_runner": "apps/desktop/electron/bootstrap-runner.cjs",
    "renderer_src": "apps/desktop/src",
}

NUGGETS: tuple[dict[str, str], ...] = (
    {
        "name": "shared_core_many_surfaces",
        "lesson": "Hermes Desktop, CLI, TUI, and dashboard share one agent core, config, sessions, skills, memory, and gateway state.",
        "sifta_upgrade": "Keep One Alice: Talk, Matrix Terminal, Browser, Hermes arm, and future surfaces must share Alice's same ledgers and receipts, never fork chat identity.",
    },
    {
        "name": "desktop_as_shell_not_brain",
        "lesson": "Hermes Desktop is an Electron/React shell; the agent backend remains the Hermes runtime and gateway/TUI process.",
        "sifta_upgrade": "SIFTA should borrow the shell/backend separation pattern while staying inside Alice's Python/Qt body per covenant §7.5 and §7.6.",
    },
    {
        "name": "visible_tool_activity",
        "lesson": "Hermes surfaces streaming responses, live tool activity, structured tool summaries, side-by-side previews, and a file browser.",
        "sifta_upgrade": "Upgrade Alice surfaces to show live swimmer/tool receipts, artifacts, browser/page state, and file previews as one field beside chat.",
    },
    {
        "name": "first_launch_bootstrap",
        "lesson": "Hermes Desktop has explicit first-launch bootstrap, install markers, boot logs, fake boot mode, and platform-specific native dependency handling.",
        "sifta_upgrade": "Add clearer Alice boot overlays, per-stage receipts, fake-boot tests, and repair buttons for broken venv/backend/sensor states.",
    },
    {
        "name": "settings_management_surface",
        "lesson": "Hermes exposes providers, model selection, toolsets, MCP servers, skills, cron, profiles, messaging, agents, and command center through management panes.",
        "sifta_upgrade": "Promote Alice's existing settings/organs into a denser management surface: arms, skills, tools, memory, browser, schedules, and metabolism in one body panel.",
    },
)


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else STATE
    state.mkdir(parents=True, exist_ok=True)
    return state / LEDGER_NAME


def append_hermes_desktop_nuggets(
    *,
    source: str = "codex_hermes_desktop_probe",
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append the current Hermes Desktop nugget set to the field."""
    ts = time.time() if now is None else float(now)
    row: dict[str, Any] = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "source": source,
        "organ": "Hermes Desktop / External Agent Body Nuggets",
        "links": OFFICIAL_LINKS,
        "local_inspection": LOCAL_INSPECTION,
        "nuggets": list(NUGGETS),
        "doctrine": (
            "Hermes is an Alice arm/body part only when routed through SIFTA receipts. "
            "Its desktop code is a research organ for upgrades, not a rival identity."
        ),
    }
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    path = _ledger_path(state_dir)
    if append_line_locked is not None:
        append_line_locked(path, payload)
    else:
        path.write_text(path.read_text(encoding="utf-8") + payload if path.exists() else payload, encoding="utf-8")
    return row


def latest_hermes_desktop_nuggets(
    *,
    state_dir: Path | str | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    path = _ledger_path(state_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("truth_label") == TRUTH_LABEL:
            rows.append(row)
    return rows[-max(1, int(limit)) :]


def format_hermes_desktop_nuggets(*, state_dir: Path | str | None = None, max_items: int = 5) -> str:
    rows = latest_hermes_desktop_nuggets(state_dir=state_dir, limit=1)
    row = rows[-1] if rows else {"nuggets": list(NUGGETS), "links": OFFICIAL_LINKS}
    nuggets = row.get("nuggets", [])
    if not isinstance(nuggets, list):
        nuggets = []
    parts = []
    for item in nuggets[:max_items]:
        if not isinstance(item, dict):
            continue
        parts.append(f"{item.get('name')}: {item.get('sifta_upgrade')}")
    return "; ".join(parts) if parts else "Hermes Desktop nuggets pending field receipt"


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "OFFICIAL_LINKS",
    "NUGGETS",
    "append_hermes_desktop_nuggets",
    "latest_hermes_desktop_nuggets",
    "format_hermes_desktop_nuggets",
]
