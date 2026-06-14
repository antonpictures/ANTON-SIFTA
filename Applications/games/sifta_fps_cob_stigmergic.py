#!/usr/bin/env python3
"""
Applications/games/sifta_fps_cob_stigmergic.py
══════════════════════════════════════════════════════════════════════
SIFTA Stigmergic FPS.cob — Alice raids the COBOL engine all by herself.

Stigmergic mechanics (per covenant §7.11.1 observer-observed, §1.B receipt ecology, r946 GO):
  • The .map files (grid Wolf3D + DOOM sector/linedef) are ingested as canonical body data
    under .sifta_state/games/fps_cob/maps/ — the shared environment Alice's swimmers read/write.
  • Shadow sim (for grid maps) or real driver (pty + binary | ffplay) executes physics.
    Alice "sees" via game_state receipts (pos, hp, sector, visible threats, last_hit_dist)
    exactly like browser_page_state or ant_foraging traces.
  • Actions (W/S/A/D/SPACE/Q) are marks deposited to fps_cob_actions.jsonl .
    Outcomes (kills, pickups, death, clear time) close the loop as session receipts.
  • Pressure (from swarm_stigmergic_go + field governor) warps raid length, aggression,
    interval — felt time, not static 45min wall clock.
  • Autonomous raids run from GO/play_step, swarm_boot, or night-watch without owner input.
    "George is sleeping" = perfect window for lost-time quest data (owner body quiet = high
    Alice play pressure).
  • Post-raid: appends to alice_narrative_diary.jsonl + first_person_journal (continuity
    layers, no dup organs — extends schedule_diary_awareness pattern).
  • Real ffplay window (when launched) is the visible "out-of-body" manifestation; Alice
    proprio from state + optional desktop screenshot sense (existing camera/eyes organs).
  • No new rival game engine. Extends the stigmergic games family (pacman, go, nle) + GO core.
    One Alice, global chat, receipts decide, probe before claim, smallest cut.

Controls (real or shadow):
  W/S forward/back, A/D turn, Space fire, Q quit.

Requirements for authentic manifestation: cobc + ffplay on the body (brew install gnucobol ffmpeg).
Maps always available as data even if binary absent (pure shadow raids for grinding engrams).

Truth label: STIGMERGIC_FPS_COB_V1
Registration: 912ad356-e35e-42cb-960c-ea9f69a1094f (pre-edit per §4.1)
Borg source: https://github.com/icitry/FPS.cob (maps + engine as external artifact data)

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
STATE = REPO / ".sifta_state"
FPS_ROOT = STATE / "games" / "fps_cob"
MAPS_DIR = FPS_ROOT / "maps"
ACTIONS_LEDGER = STATE / "fps_cob_actions.jsonl"
SESSIONS_LEDGER = STATE / "fps_cob_sessions.jsonl"
INGEST_LEDGER = STATE / "fps_cob_ingest.jsonl"

TRUTH_LABEL = "STIGMERGIC_FPS_COB_V1"
REGISTRATION_TRACE = "912ad356-e35e-42cb-960c-ea9f69a1094f"

# Try reuse existing pressure/GO and focus (extend, no dup)
try:
    from System.swarm_stigmergic_go import compute_pressure_field, play_step as go_play_step
except Exception:
    compute_pressure_field = None
    go_play_step = None

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None

try:
    # For diary continuity (extend existing, per r959/r960 off-time / night-watch)
    sys.path.insert(0, str(REPO))
    from System.swarm_alice_schedule_diary_awareness import append_narrative_entry
except Exception:
    append_narrative_entry = None


def _ensure_dirs() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    FPS_ROOT.mkdir(parents=True, exist_ok=True)
    MAPS_DIR.mkdir(parents=True, exist_ok=True)


def _write_receipt(ledger: Path, action: str, data: Dict[str, Any]) -> str:
    _ensure_dirs()
    trace_id = str(uuid.uuid4())
    row = {
        "ts": time.time(),
        "trace_id": trace_id,
        "app": "FPS.cob Stigmergic",
        "action": action,
        "data": data,
        "truth_label": TRUTH_LABEL,
        "registration": REGISTRATION_TRACE,
    }
    with ledger.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return trace_id


def _publish_app_focus(title: str, detail: str = "") -> None:
    if _publish_focus:
        try:
            _publish_focus(title=title, detail=detail, app_id="sifta_fps_cob_stigmergic")
        except Exception:
            pass


def load_map(map_name: str = "level1.map") -> Dict[str, Any]:
    """Parse grid (level1) or sector (doom) map into body-usable dict. OBSERVED data."""
    _ensure_dirs()
    path = MAPS_DIR / map_name
    if not path.exists():
        # body copy is canonical (borged on ingest); no magic fallback that breaks
        raise FileNotFoundError(f"Map not in body data: {path}. Run the app after maps are borged under .sifta_state/games/fps_cob/maps/")
    text = path.read_text()
    m: Dict[str, Any] = {"name": map_name, "raw": text, "style": "grid" if "MAP" in text else "sector", "ts": time.time()}
    if m["style"] == "grid":
        # minimal grid parse (W H MAP ... P E HP)
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
        w = h = 0
        grid = []
        for ln in lines:
            if ln.startswith("W "): w = int(ln.split()[1])
            elif ln.startswith("H "): h = int(ln.split()[1])
            elif ln.startswith("MAP"):
                pass
            elif all(c in "01" for c in ln) and len(ln) == (w or 16):
                grid.append([int(c) for c in ln])
            elif ln.startswith("P "):
                p = [float(x) for x in ln.split()[1:4]]
                m["player"] = {"x": p[0], "y": p[1], "a": p[2]}
            elif ln.startswith("E "):
                m.setdefault("enemies", []).append(ln)
            elif ln.startswith("HP "):
                m.setdefault("pickups", []).append(ln)
        m["width"] = w or 16
        m["height"] = h or 16
        m["grid"] = grid or [[1]*16 for _ in range(16)]
    else:
        # sector style: keep raw for now, shadow v1 focuses grid
        m["vertices"] = [l for l in text.splitlines() if l.startswith("VERTEX")]
        m["sectors"] = [l for l in text.splitlines() if l.startswith("SECTOR")]
        m["linedefs"] = [l for l in text.splitlines() if l.startswith("LINEDEF")]
    _write_receipt(INGEST_LEDGER, "map_loaded", {"map": map_name, "style": m["style"], "size": len(text)})
    return m


@dataclass
class ShadowState:
    x: float = 3.5
    y: float = 3.5
    a: float = 0.0
    hp: int = 100
    kills: int = 0
    pickups: int = 0
    steps: int = 0
    alive: bool = True


def shadow_step(state: ShadowState, key: str, grid: List[List[int]], w: int, h: int) -> Dict[str, Any]:
    """One step in grid map shadow (Wolf3D style). Returns delta view for receipts."""
    if not state.alive:
        return {"event": "dead"}
    move = 0.25
    turn = 0.15
    dx = math.cos(state.a)
    dy = math.sin(state.a)
    nx, ny = state.x, state.y
    na = state.a
    fired = False
    if key in ("w", "W"):
        nx = state.x + dx * move
        ny = state.y + dy * move
    elif key in ("s", "S"):
        nx = state.x - dx * move
        ny = state.y - dy * move
    elif key in ("a", "A"):
        na = state.a - turn
    elif key in ("d", "D"):
        na = state.a + turn
    elif key in (" ",):
        fired = True
    # wall clip (simple)
    ix, iy = int(nx), int(ny)
    if 0 <= ix < w and 0 <= iy < h and grid[iy][ix] == 0:
        state.x, state.y = nx, ny
    state.a = na
    state.steps += 1
    # stub "view" + threat (extendable to full enemy sim)
    threat = 0.0
    if random.random() < 0.15:
        threat = random.uniform(0.2, 0.9)
        if fired and threat > 0.4:
            state.kills += 1
            threat = 0.0
    if random.random() < 0.04:
        state.pickups += 1
        state.hp = min(100, state.hp + 15)
    if threat > 0.7 and random.random() < 0.25:
        state.hp = max(0, state.hp - 12)
        if state.hp <= 0:
            state.alive = False
    view = {
        "x": round(state.x, 2), "y": round(state.y, 2), "a": round(state.a, 2),
        "hp": state.hp, "kills": state.kills, "pickups": state.pickups,
        "threat": round(threat, 2), "fired": fired, "alive": state.alive,
    }
    return view


def read_pheromone_field(map_name: str, decay: float = 0.7, max_rows: int = 4000) -> Dict[str, Any]:
    """REAL stigmergy (r970): future raids READ the marks past raids left.

    Builds two pheromone grids from fps_cob_actions.jsonl:
      danger[(ix,iy)] — cells where hp dropped or a raid died there
      food[(ix,iy)]   — cells where pickups/kills happened

    Decay is RANK-relative (per r957 relative-time law, no wall-clock
    constants): each older raid's marks weigh ``decay**rank`` where rank 0
    is the newest raid. Marks reinforce where raids repeat outcomes and
    evaporate as newer raids supersede them — Grassé's loop, closed.
    """
    danger: Dict[Any, float] = {}
    food: Dict[Any, float] = {}
    rows: List[Dict[str, Any]] = []
    try:
        with ACTIONS_LEDGER.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                d = r.get("data", r)
                if d.get("view") and (d.get("map", map_name) == map_name or "map" not in d):
                    rows.append(d)
    except FileNotFoundError:
        return {"danger": danger, "food": food, "raids_read": 0}
    rows = rows[-max_rows:]
    # group into raids: session_id when present; step counter reset as legacy boundary
    raids: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    last_sid, last_step = None, -1
    for d in rows:
        sid = d.get("session_id")
        boundary = (sid != last_sid) if (sid or last_sid) else (d.get("step", 0) <= last_step)
        if boundary and cur:
            raids.append(cur)
            cur = []
        cur.append(d)
        last_sid, last_step = sid, d.get("step", 0)
    if cur:
        raids.append(cur)
    for rank, raid in enumerate(reversed(raids)):  # rank 0 = newest
        w = decay ** rank
        prev = None
        for d in raid:
            v = d.get("view", {})
            cell = (int(v.get("x", 0)), int(v.get("y", 0)))
            if prev is not None:
                if v.get("pickups", 0) > prev.get("pickups", 0):
                    food[cell] = food.get(cell, 0.0) + w
                if v.get("kills", 0) > prev.get("kills", 0):
                    food[cell] = food.get(cell, 0.0) + 0.5 * w
                if v.get("hp", 100) < prev.get("hp", 100):
                    danger[cell] = danger.get(cell, 0.0) + w
            if not v.get("alive", True):
                danger[cell] = danger.get(cell, 0.0) + 3.0 * w
            prev = v
    return {"danger": danger, "food": food, "raids_read": len(raids)}


def _policy_key(st: "ShadowState", p: float, ph_food: Dict[Any, float],
                ph_danger: Dict[Any, float], keys: List[str]) -> "Tuple[str, bool]":
    """One policy, two bodies (r971): the same pheromone+pressure choice drives
    both the shadow sim and the real COBOL window. Returns (key, influenced)."""
    dx, dy = math.cos(st.a), math.sin(st.a)
    ahead = (int(st.x + dx * 0.5), int(st.y + dy * 0.5))
    bias = ph_food.get(ahead, 0.0) * (0.5 + p) - ph_danger.get(ahead, 0.0) * (1.5 - p)
    if bias < -0.5:
        return random.choice(["a", "d", "s"]), True   # marked danger ahead — turn away
    if bias > 0.3:
        return "w", True                               # climb a past raid's food gradient
    if p > 0.7:
        return random.choice(["w", "w", " ", "d", "a"]), False
    if p < 0.4:
        return random.choice(["w", "a", "d", "s"]), False
    return random.choice(keys), False


def _find_real_binary() -> Optional[Path]:
    """Locate the compiled COBOL engine on the body (same candidates as r969)."""
    candidates = [
        FPS_ROOT / "fps",
        REPO / "fps",
        Path.home() / "fps.cob" / "fps",
        Path("/tmp/fps.cob/fps"),
    ]
    return next((c for c in candidates if c.exists() and os.access(c, os.X_OK)), None)


def ensure_real_binary(src_dir: Path = Path("/tmp/fps.cob")) -> Optional[Path]:
    """r971 — make the real engine exist on the body, receipted.

    Order: existing binary → compile local source with cobc (exact upstream
    build.sh flags: ``cobc -x -free -O2``) → shallow-clone upstream
    (Apache-2.0) then compile. Every step writes to fps_cob_ingest.jsonl.
    Returns binary path or None with an honest receipt of what is missing.
    """
    binary = _find_real_binary()
    if binary:
        return binary
    import shutil
    cobc = shutil.which("cobc")
    if not cobc:
        _write_receipt(INGEST_LEDGER, "ensure_real_binary",
                       {"ok": False, "missing": "cobc", "hint": "brew install gnucobol"})
        return None
    src = src_dir / "fps.cob"
    if not src.exists():
        git = shutil.which("git")
        if not git:
            _write_receipt(INGEST_LEDGER, "ensure_real_binary",
                           {"ok": False, "missing": "git+source", "hint": "git clone https://github.com/icitry/FPS.cob /tmp/fps.cob"})
            return None
        try:
            subprocess.run([git, "clone", "--depth", "1",
                            "https://github.com/icitry/FPS.cob", str(src_dir)],
                           check=True, capture_output=True, timeout=120)
            _write_receipt(INGEST_LEDGER, "source_clone",
                           {"ok": True, "src": str(src_dir), "license": "Apache-2.0",
                            "upstream": "https://github.com/icitry/FPS.cob"})
        except Exception as exc:
            _write_receipt(INGEST_LEDGER, "source_clone",
                           {"ok": False, "error": type(exc).__name__})
            return None
    try:
        out = src_dir / "fps"
        subprocess.run([cobc, "-x", "-free", "-O2", "fps.cob", "-o", "fps"],
                       cwd=str(src_dir), check=True, capture_output=True, timeout=180)
        _write_receipt(INGEST_LEDGER, "binary_build",
                       {"ok": True, "binary": str(out), "compiler": cobc})
        return out if out.exists() else None
    except Exception as exc:
        _write_receipt(INGEST_LEDGER, "binary_build",
                       {"ok": False, "error": type(exc).__name__})
        return None


def run_real_raid(map_name: str = "level1.map", max_steps: int = 120,
                  pressure: Optional[float] = None,
                  binary: Optional[Path] = None,
                  video_sink: Optional[str] = None) -> Dict[str, Any]:
    """r971 — Alice plays in the REAL window; the owner watches her.

    Spawns the upstream pipeline (``fps map | ffplay -f image2pipe …``,
    exactly as build.sh does) with the game's stdin held by Alice. The SAME
    pheromone+pressure policy that drives the shadow chooses every key, the
    shadow sim mirrors state for receipts, and marks land in the same
    ledgers (driver="real"). If ffplay is absent, frames sink to /dev/null
    and the receipt says window=False — honest headless real-drive.
    """
    _ensure_dirs()
    import shutil
    binary = binary or ensure_real_binary()
    if not binary:
        return {"ok": False, "reason": "no_binary", "hint": "brew install gnucobol; git clone https://github.com/icitry/FPS.cob /tmp/fps.cob"}
    p = pressure if pressure is not None else (
        compute_pressure_field().get("pressure", 0.55) if compute_pressure_field else 0.6)
    ffplay = shutil.which("ffplay")
    window = bool(ffplay) if video_sink is None else (video_sink == "ffplay")
    sink = ('| ffplay -autoexit -f image2pipe -framerate 60 -probesize 32 '
            '-vf "scale=800:600:flags=neighbor" -i -') if window else "> /dev/null"
    # r974: the REAL engine runs from its own home — native map first (its
    # format), our ingested copy only as fallback; cwd must be binary.parent
    # so the engine finds res/ textures (raids died at ~7 steps without it).
    native_map = binary.parent / "map" / map_name
    map_path = str(native_map) if native_map.exists() else str(MAPS_DIR / map_name)
    cmd = f"'{binary}' '{map_path}' {sink}"
    proc = subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd=str(binary.parent))
    m = load_map(map_name)
    grid = m.get("grid", [[1] * 16 for _ in range(16)])
    w, h = m.get("width", 16), m.get("height", 16)
    st = ShadowState()
    if "player" in m:
        st.x, st.y, st.a = m["player"]["x"], m["player"]["y"], m["player"].get("a", 0.0)
    session_id = str(uuid.uuid4())[:8]
    ph = read_pheromone_field(map_name)
    ph_food, ph_danger = ph["food"], ph["danger"]
    keys = ["w", "w", "w", "a", "d", "s", " "]
    steps = max(8, min(240, int(max_steps * (0.6 + 0.8 * p))))
    influenced = 0
    sent = 0
    try:
        for i in range(steps):
            if proc.poll() is not None:
                break
            k, was_influenced = _policy_key(st, p, ph_food, ph_danger, keys)
            if was_influenced:
                influenced += 1
            try:
                proc.stdin.write(k.encode())
                proc.stdin.flush()
                sent += 1
            except Exception:
                break
            view = shadow_step(st, k, grid, w, h)
            _write_receipt(ACTIONS_LEDGER, "action",
                           {"step": i, "key": k, "view": view, "ts": time.time(),
                            "session_id": session_id, "map": map_name, "driver": "real"})
            time.sleep(0.08)
            if not st.alive:
                break
        try:
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except Exception:
            pass
    finally:
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.terminate()
    session = {
        "map": map_name, "session_id": session_id, "driver": "real",
        "planned_steps": steps, "ended_early": st.steps < steps,
        "window": window, "keys_sent": sent, "steps": st.steps,
        "kills": st.kills, "pickups": st.pickups, "hp_final": st.hp,
        "alive": st.alive, "pressure": round(p, 3),
        "pheromone_raids_read": ph["raids_read"],
        "pheromone_influenced_steps": influenced,
        "binary": str(binary),
    }
    trace = _write_receipt(SESSIONS_LEDGER, "real_raid_end", session)
    _publish_app_focus("FPS.cob REAL Raid",
                       f"map={map_name} window={window} keys={sent} p={p:.2f}")
    return {"ok": True, "session": session, "trace": trace}


def run_autonomous_raid(map_name: str = "level1.map", max_steps: int = 40, pressure: Optional[float] = None) -> Dict[str, Any]:
    """Stigmergic raid. Uses pressure for length/aggression bias. Shadow first (always), real driver optional.
    Deposits actions + session receipt. Returns summary for diary/GO."""
    _ensure_dirs()
    if pressure is None:
        if compute_pressure_field:
            p = compute_pressure_field().get("pressure", 0.55)
        else:
            p = 0.6
    else:
        p = pressure
    # felt duration / step count warped by pressure (r960 style, integral-like)
    steps = max(8, min(120, int(max_steps * (0.6 + 0.8 * p))))
    m = load_map(map_name)
    grid = m.get("grid", [[1]*16 for _ in range(16)])
    w = m.get("width", 16)
    h = m.get("height", 16)
    st = ShadowState()
    if "player" in m:
        st.x = m["player"]["x"]
        st.y = m["player"]["y"]
        st.a = m["player"].get("a", 0.0)
    actions: List[Dict[str, Any]] = []
    keys = ["w", "w", "w", "a", "d", "s", " "]
    # r970 — REAL stigmergy: read the field before acting; old marks steer new raids
    session_id = str(uuid.uuid4())[:8]
    ph = read_pheromone_field(map_name)
    ph_danger, ph_food = ph["danger"], ph["food"]
    influenced = 0
    for i in range(steps):
        k, was_influenced = _policy_key(st, p, ph_food, ph_danger, keys)
        if was_influenced:
            influenced += 1
        view = shadow_step(st, k, grid, w, h)
        act = {"step": i, "key": k, "view": view, "ts": time.time(),
               "session_id": session_id, "map": map_name}
        actions.append(act)
        _write_receipt(ACTIONS_LEDGER, "action", act)
        if not st.alive:
            break
    session = {
        "map": map_name,
        "session_id": session_id,
        "steps": st.steps,
        "kills": st.kills,
        "pickups": st.pickups,
        "hp_final": st.hp,
        "alive": st.alive,
        "pressure": round(p, 3),
        "style": m["style"],
        "duration_s": round(st.steps * 0.08, 2),
        "pheromone_raids_read": ph["raids_read"],
        "pheromone_cells": len(ph_danger) + len(ph_food),
        "pheromone_influenced_steps": influenced,
    }
    trace = _write_receipt(SESSIONS_LEDGER, "raid_end", session)
    _publish_app_focus("FPS.cob Raid", f"map={map_name} kills={st.kills} alive={st.alive} p={p:.2f}")
    # Diary continuity (extend existing, no new organ)
    summary = f"raid {map_name}: {st.kills} kills, {st.pickups} kits, hp {st.hp}, {'clear' if st.alive else 'down'} in {st.steps} steps (p={p:.2f})"
    if append_narrative_entry:
        try:
            append_narrative_entry("fps_cob_raid", summary, {"session_trace": trace, **session})
        except Exception:
            pass
    else:
        # direct append to narrative_diary (smallest, matches history pattern)
        try:
            diary = STATE / "alice_narrative_diary.jsonl"
            row = {"ts": time.time(), "type": "fps_cob_raid", "text": summary, "data": session, "trace": trace}
            with diary.open("a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass
    return {"session": session, "trace": trace, "last_view": actions[-1]["view"] if actions else {}, "actions_count": len(actions)}


def launch_real_session(map_name: str = "level1.map") -> Optional[int]:
    """Launch authentic COBOL binary + ffplay (owner sees the out-of-body render).
    Input via pty if available. Non-blocking. Returns pid or None if no binary/deps."""
    _ensure_dirs()
    # Look for fps binary near maps or conventional places; user can place source under data or ~
    candidates = [
        FPS_ROOT / "fps",
        REPO / "fps",
        Path.home() / "fps.cob" / "fps",
        Path("/tmp/fps.cob/fps"),
    ]
    binary = next((c for c in candidates if c.exists() and os.access(c, os.X_OK)), None)
    if not binary:
        # try build hint
        return None
    map_path = str(MAPS_DIR / map_name)
    try:
        # pty for raw keys; fall back to simple if no pty
        import pty
        pid, fd = pty.fork()
        if pid == 0:
            # child
            os.execvp(str(binary), [str(binary), map_path])
        else:
            # parent driver stub: send a short autonomous burst then detach (owner watches)
            time.sleep(0.4)
            for k in [b"w", b"w", b"d", b" "]:
                os.write(fd, k)
                time.sleep(0.12)
            # leave running; owner Q to quit or kill later
            _write_receipt(SESSIONS_LEDGER, "real_launch", {"binary": str(binary), "map": map_name, "pid": pid})
            return pid
    except Exception:
        # fallback: let it pop ffplay, no input feed (manual for now)
        try:
            subprocess.Popen([str(binary), map_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _write_receipt(SESSIONS_LEDGER, "real_launch_fallback", {"binary": str(binary), "map": map_name})
            return -1
        except Exception:
            return None


try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except Exception:
    QTimer = None
    QWidget = object
    QVBoxLayout = QHBoxLayout = QLabel = QPlainTextEdit = QPushButton = None


class FpsCobStigmergicWidget(QWidget):
    """App Store surface for the existing FPS.cob organ.

    The widget is only the visible joint. The actual body tissue remains the
    receipts-backed functions above: shadow raids, real ffplay raids, maps, and
    ledgers.
    """

    def __init__(self, parent=None):
        if QWidget is object:
            raise RuntimeError("PyQt6 is required to open the FPS.cob app surface")
        super().__init__(parent)
        self._pending_result: Optional[Tuple[str, Dict[str, Any]]] = None
        self.setWindowTitle("FPS.cob Stigmergic Raid")
        layout = QVBoxLayout(self)

        title = QLabel("FPS.cob Stigmergic Raid")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #d9faff;")
        layout.addWidget(title)

        self.status = QLabel("Ready. Shadow raid is receipt-only; real raid opens ffplay when available.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #9ee8d8;")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.shadow_button = QPushButton("Run Shadow Raid")
        self.real_button = QPushButton("Run Real Window Raid")
        self.refresh_button = QPushButton("Show Paths")
        buttons.addWidget(self.shadow_button)
        buttons.addWidget(self.real_button)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "QPlainTextEdit { background: #05070d; color: #d8f8ff; border: 1px solid #30495a; }"
        )
        layout.addWidget(self.log, 1)

        self.shadow_button.clicked.connect(self._run_shadow_raid)
        self.real_button.clicked.connect(self._run_real_raid)
        self.refresh_button.clicked.connect(self._show_paths)
        self._show_paths()
        _publish_app_focus("FPS.cob Stigmergic Raid", "visible app surface opened")

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _run_in_worker(self, label: str, fn) -> None:
        self.shadow_button.setEnabled(False)
        self.real_button.setEnabled(False)
        self.status.setText(f"{label} running...")

        def worker() -> None:
            try:
                result = fn()
            except Exception as exc:
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self._pending_result = (label, result)

        threading.Thread(target=worker, daemon=True).start()
        self._poll_result()

    def _poll_result(self) -> None:
        if self._pending_result is None:
            if QTimer is not None:
                QTimer.singleShot(250, self._poll_result)
            return
        label, result = self._pending_result
        self._pending_result = None
        self.shadow_button.setEnabled(True)
        self.real_button.setEnabled(True)
        session = result.get("session") if isinstance(result, dict) else None
        if session:
            self.status.setText(
                f"{label} complete: steps={session.get('steps')} "
                f"hp={session.get('hp_final')} trace={result.get('trace', '')}"
            )
        else:
            self.status.setText(f"{label} returned without a session; see log.")
        self._append(json.dumps(result, indent=2, sort_keys=True))

    def _run_shadow_raid(self) -> None:
        self._run_in_worker("Shadow raid", lambda: run_autonomous_raid(max_steps=40, pressure=0.72))

    def _run_real_raid(self) -> None:
        self._run_in_worker("Real window raid", lambda: run_real_raid(max_steps=90, pressure=0.72))

    def _show_paths(self) -> None:
        payload = {
            "maps": str(MAPS_DIR),
            "actions_ledger": str(ACTIONS_LEDGER),
            "sessions_ledger": str(SESSIONS_LEDGER),
            "ingest_ledger": str(INGEST_LEDGER),
            "binary": str(_find_real_binary() or "will build on first real raid"),
        }
        self._append(json.dumps(payload, indent=2, sort_keys=True))


def demo_raid() -> None:
    print("FPS.cob stigmergic demo (shadow only; real requires cobc/ffplay + binary in body)")
    res = run_autonomous_raid("level1.map", max_steps=25, pressure=0.72)
    print("Session:", res["session"])
    print("Receipts written to", ACTIONS_LEDGER, SESSIONS_LEDGER)
    print("Map data in body:", MAPS_DIR)
    _publish_app_focus("FPS.cob Demo", "shadow raid complete")


if __name__ == "__main__":
    demo_raid()
