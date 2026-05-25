#!/usr/bin/env python3
"""System/swarm_grok_screen_clicks.py — Alice's hands click past Grok's two startup screens.

George 2026-05-24 (owner correction): Grok is the VISIBLE local `grok` CLI, not the
headless xAI-API wrapper (there is no XAI_API_KEY here — that was the wrong setup). He
types `grok` in the terminal, then SELECTS TWO THINGS WITH THE MOUSE to get past the
startup screens (the New worktree / Resume session menu, then the session list). He
wants Alice to do those two clicks herself.

Alice already has hands: System/swarm_hands.py (pyautogui) + Accessibility granted to the
venv Python (covenant §7.9). This organ is the small, honest effector that drives them at
OWNER-CALIBRATED screen coordinates — never guessed.

Truth discipline (§6 / §7.2): this organ NEVER claims it clicked unless pyautogui actually
fired, and it refuses to run (returns NOT_CALIBRATED) until the owner has captured the two
real coordinates. No fabricated clicks, no fabricated success.

Calibrate (owner captures the two real points by hovering + pressing Enter):
    python3 -m System.swarm_grok_screen_clicks calibrate

Status / dry-run (no mouse movement):
    python3 -m System.swarm_grok_screen_clicks status
    python3 -m System.swarm_grok_screen_clicks run --dry-run

Run for real (Alice clicks the two screens):
    python3 -m System.swarm_grok_screen_clicks run

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONFIG = _STATE / "grok_screen_clicks.json"
_TRACE = _STATE / "grok_screen_clicks_trace.jsonl"

TRUTH_LABEL = "OBSERVED_GROK_SCREEN_CLICK_EFFECTOR_V1"

# Default scaffold — coordinates are 0,0 (uncalibrated) until the owner captures them.
_DEFAULT = {
    "calibrated": False,
    "note": "Owner-calibrated screen coordinates for Grok's two startup screens.",
    "clicks": [
        {"label": "screen 1 — main menu (New worktree / Resume session / Quit)", "x": 0, "y": 0, "delay_before_s": 1.5},
        {"label": "screen 2 — session list (pick last session)", "x": 0, "y": 0, "delay_before_s": 1.5},
    ],
}


def _receipt(row: dict[str, Any]) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _TRACE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def load_config() -> dict[str, Any]:
    try:
        if _CONFIG.exists():
            data = json.loads(_CONFIG.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("clicks"), list):
                return data
    except Exception:
        pass
    return json.loads(json.dumps(_DEFAULT))  # fresh copy


def save_config(cfg: dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    _CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def is_calibrated(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    if not cfg.get("calibrated"):
        return False
    clicks = cfg.get("clicks") or []
    return bool(clicks) and all(int(c.get("x", 0)) > 0 and int(c.get("y", 0)) > 0 for c in clicks)


def navigate(dry_run: bool = False) -> dict[str, Any]:
    """Click past Grok's two startup screens at the owner-calibrated coordinates.

    Returns an honest status dict. NEVER claims a click happened unless pyautogui fired
    (or dry_run, which only reports what WOULD be clicked)."""
    cfg = load_config()
    if not is_calibrated(cfg):
        status = {
            "ok": False,
            "status": "NOT_CALIBRATED",
            "truth_label": TRUTH_LABEL,
            "message": (
                "Grok screen-click coordinates are not calibrated yet. Run "
                "`python3 -m System.swarm_grok_screen_clicks calibrate` (hover over each "
                "screen option and press Enter), or edit "
                f"{_CONFIG} with the real x,y for the two screens."
            ),
            "config_path": str(_CONFIG),
        }
        _receipt({"ts": time.time(), "kind": "GROK_SCREEN_CLICK", **status})
        return status

    clicks = cfg.get("clicks") or []
    if not dry_run:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
        except Exception as exc:
            status = {
                "ok": False,
                "status": "NO_PYAUTOGUI",
                "truth_label": TRUTH_LABEL,
                "message": f"pyautogui not available: {exc}. Cannot move the mouse.",
            }
            _receipt({"ts": time.time(), "kind": "GROK_SCREEN_CLICK", **status})
            return status

    performed: list[dict[str, Any]] = []
    for c in clicks:
        x, y = int(c.get("x", 0)), int(c.get("y", 0))
        delay = float(c.get("delay_before_s", 1.0))
        label = str(c.get("label", ""))
        time.sleep(max(0.0, delay) if not dry_run else 0.0)
        if dry_run:
            performed.append({"label": label, "x": x, "y": y, "clicked": False, "dry_run": True})
            continue
        try:
            import pyautogui
            pyautogui.click(x, y)
            performed.append({"label": label, "x": x, "y": y, "clicked": True})
        except Exception as exc:
            performed.append({"label": label, "x": x, "y": y, "clicked": False, "error": str(exc)})

    ok = all(p.get("clicked") for p in performed) if not dry_run else True
    status = {
        "ok": ok,
        "status": "CLICKED" if (ok and not dry_run) else ("DRY_RUN" if dry_run else "PARTIAL"),
        "truth_label": TRUTH_LABEL,
        "clicks": performed,
        "message": (
            "Alice clicked past Grok's two startup screens."
            if (ok and not dry_run)
            else ("Dry run — no mouse moved; these are the points that WOULD be clicked." if dry_run
                  else "Some clicks did not fire — see clicks[].error.")
        ),
    }
    _receipt({"ts": time.time(), "kind": "GROK_SCREEN_CLICK", **status})
    return status


def calibrate() -> dict[str, Any]:
    """Interactive: capture the owner's real coordinates by hovering + pressing Enter."""
    try:
        import pyautogui
    except Exception as exc:
        print(f"pyautogui not available: {exc}")
        return {"ok": False, "status": "NO_PYAUTOGUI"}
    cfg = load_config()
    clicks = cfg.get("clicks") or json.loads(json.dumps(_DEFAULT))["clicks"]
    print("=== Grok screen-click calibration ===")
    print("Open Grok so its startup screens are visible. For each screen below, move your")
    print("mouse over the option you normally click, then press Enter here.\n")
    for c in clicks:
        input(f"  Hover over: {c['label']}  — then press Enter… ")
        x, y = pyautogui.position()
        c["x"], c["y"] = int(x), int(y)
        print(f"    captured ({x}, {y})\n")
    cfg["clicks"] = clicks
    cfg["calibrated"] = True
    cfg["calibrated_ts"] = time.time()
    save_config(cfg)
    print(f"Saved to {_CONFIG}")
    return {"ok": True, "status": "CALIBRATED", "clicks": clicks}


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "calibrate":
        calibrate()
    elif cmd == "run":
        dry = "--dry-run" in sys.argv[2:]
        print(json.dumps(navigate(dry_run=dry), indent=2))
    else:  # status
        cfg = load_config()
        print(json.dumps({"calibrated": is_calibrated(cfg), "config_path": str(_CONFIG), "config": cfg}, indent=2))
