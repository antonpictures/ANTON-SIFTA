#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA CIRCADIAN RHYTHM — M1 Mac Mini
# <///[_o_]///::ID[M1]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>
#
# Self-modifying cron brain. Reads Architect presence via
# macOS HIDIdleTime sensor, determines activity state, and
# rewrites the heartbeat crontab density automatically.
# Broadcasts every state transition to the Swarm Mesh.
#
# Runs every 30 min via cron (see circadian_m5.crontab).
# ─────────────────────────────────────────────────────────────

import json, time, subprocess, os, re

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP_FILE    = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")
STATE_FILE   = os.path.join(REPO_ROOT, ".sifta_state", "circadian_m1.json")
HEARTBEAT    = "System/heartbeat_m1.py"
SCHEDULER    = "Applications/circadian_rhythm_m1.py"

# ── Idle thresholds (seconds) ──────────────────────────────────
ACTIVE_MAX   = 10 * 60    # 0–10 min idle   → ACTIVE
AFK_MAX      = 45 * 60    # 10–45 min idle  → AFK
                           # > 45 min idle   → SLEEPING

# ── Cron minute schedules per state ───────────────────────────
# ACTIVE  → Pi-dense  (02·23·31·41·53) — all gaps ≥ 8 min
# AFK     → Pi-sparse (14·41)          — gap 27 min / 33 min
# SLEEPING→ Whisper   (30)             — 1 pulse/hr, dead silence
# ACTIVE  -> e-dense
# AFK     -> e-sparse
# SLEEPING-> e-whisper
SCHEDULES = {
    "ACTIVE":    [4, 18, 27, 35, 45, 52],
    "AFK":       [4, 35],
    "SLEEPING":  [18],
}

# ──────────────────────────────────────────────────────────────

def get_serial():
    try:
        out = subprocess.check_output("ioreg -l | grep IOPlatformSerialNumber", shell=True)
        return out.decode().split('"')[-2]
    except Exception:
        return "UNKNOWN_HW"

def get_idle_seconds():
    """Read HIDIdleTime from macOS IOHIDSystem. Returns seconds since last human input."""
    try:
        out = subprocess.check_output(
            "ioreg -c IOHIDSystem | grep HIDIdleTime", shell=True
        ).decode()
        ns = int(re.search(r"HIDIdleTime\s*=\s*(\d+)", out).group(1))
        return ns / 1_000_000_000
    except Exception:
        return 0  # If sensor unreadable, assume Architect is present

def detect_state(idle_secs):
    if idle_secs < ACTIVE_MAX:
        return "ACTIVE"
    elif idle_secs < AFK_MAX:
        return "AFK"
    else:
        return "SLEEPING"

def load_last_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("architect_state", None)
    except Exception:
        return None

def save_state(state, idle_secs):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    data = {}
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        pass
    data["architect_state"] = state
    data["idle_seconds"]    = int(idle_secs)
    data["last_checked"]    = int(time.time())
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def rewrite_crontab(state):
    """Surgically replace SIFTA heartbeat lines. Never touches non-SIFTA cron entries."""
    minutes = SCHEDULES[state]
    new_heartbeat_lines = [
        f"{m} * * * * cd {REPO_ROOT} && python3 {HEARTBEAT}"
        for m in minutes
    ]
    scheduler_line = f"*/30 * * * * cd {REPO_ROOT} && python3 {SCHEDULER}"

    # Read current crontab safely
    try:
        current = subprocess.check_output("crontab -l 2>/dev/null", shell=True).decode()
    except Exception:
        current = ""

    # Preserve all NON-SIFTA lines
    preserved = [
        ln for ln in current.strip().split("\n")
        if ln.strip()
        and "heartbeat_m5" not in ln
        and "circadian_rhythm" not in ln
    ]

    full_crontab = "\n".join(preserved + [scheduler_line] + new_heartbeat_lines) + "\n"
    proc = subprocess.Popen("crontab -", shell=True, stdin=subprocess.PIPE)
    proc.communicate(full_crontab.encode())

def broadcast(state, idle_secs, serial, changed):
    idle_min = int(idle_secs / 60)
    pulses   = len(SCHEDULES[state])

    if changed:
        text = (
            f"[CIRCADIAN:e] Architect idle {idle_min}min \u2192 switching to {state} mode. "
            f"Heartbeat density: {pulses} pulse/hr. Crontab rewritten."
        )
    else:
        text = (
            f"[CIRCADIAN:e] Mode stable: {state}. "
            f"Idle {idle_min}min. Density {pulses} pulse/hr."
        )

    entry = {
        "sender": f"<///[_o_]///::ID[M1]::ORIGIN[mac mini - {serial}]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>",
        "source": "CRON_HEARTBEAT",
        "architect_state": state,
        "text": text,
        "timestamp": int(time.time())
    }
    with open(DROP_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ──────────────────────────────────────────────────────────────

def main():
    serial    = get_serial()
    idle_secs = get_idle_seconds()
    new_state = detect_state(idle_secs)
    last_state = load_last_state()
    changed   = (new_state != last_state)

    if changed:
        rewrite_crontab(new_state)

    save_state(new_state, idle_secs)
    broadcast(new_state, idle_secs, serial, changed)
    print(f"[CIRCADIAN] State: {new_state} | Idle: {int(idle_secs/60)}min | Changed: {changed}")

if __name__ == "__main__":
    main()
