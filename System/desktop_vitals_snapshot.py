#!/usr/bin/env python3
"""Single source of truth for desktop HUD vitals (menu bar + body panel)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def _tail_jsonl(path: Path) -> dict[str, Any]:
    last = ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        return json.loads(last) if last else {}
    except Exception:
        return {}


def _dir_mb(path: Path) -> float:
    try:
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / (1024 * 1024)
    except Exception:
        return 0.0


def read_desktop_vitals(repo_root: Path) -> Mapping[str, Any]:
    """
    Read latest health / metabolism / economy slice used by the OS chrome.

    Returns a dict with ok (bool), optional error (str), and display fields.
    """
    state = repo_root / ".sifta_state"
    try:
        health = _tail_jsonl(state / "health_scores.jsonl")
        metabolic = _tail_jsonl(state / "metabolic_homeostasis.jsonl")
        raw = health.get("raw", {}) if isinstance(health.get("raw"), dict) else {}
        econ = raw.get("economic", {}) if isinstance(raw.get("economic"), dict) else {}
        score = int(health.get("score", 0) or 0)
        if score >= 80:
            grade = "HEALTHY"
        elif score >= 60:
            grade = "NOMINAL"
        elif score >= 40:
            grade = "DEGRADING"
        else:
            grade = "CRITICAL"
        state_mb = _dir_mb(state)
        iris_mb = _dir_mb(state / "iris_frames")
        mode = str(metabolic.get("mode", "UNKNOWN"))
        budget = float(metabolic.get("budget_multiplier", 0.0) or 0.0)
        net = float(econ.get("net_stgm", 0.0) or 0.0)
        if score >= 60:
            color = "#9ece6a"
        elif score >= 40:
            color = "#e0af68"
        else:
            color = "#f7768e"
        short = f"Vitals  {score}/100  {grade}  ·  {mode}  ×{budget:.2f}"
        return {
            "ok": True,
            "score": score,
            "grade": grade,
            "metabolism_mode": mode,
            "budget_multiplier": budget,
            "state_mb": state_mb,
            "iris_mb": iris_mb,
            "net_stgm": net,
            "score_color": color,
            "menubar_text": short,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "score": 0,
            "grade": "—",
            "metabolism_mode": "—",
            "budget_multiplier": 0.0,
            "state_mb": 0.0,
            "iris_mb": 0.0,
            "net_stgm": 0.0,
            "score_color": "#565f89",
            "menubar_text": f"Vitals  unavailable  ({type(exc).__name__})",
        }
