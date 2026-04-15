#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA CIRCADIAN RHYTHM — NODE-AWARE
# <///[_o_]///::ID[AUTO]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>
#
# Self-modifying cron brain. Detects which node it is running on
# (M5 Mac Studio or M1 Mac Mini) via bare-metal serial number.
# Applies the correct constant:
#   M5 -> Pi  (02.23.31.41.53)
#   M1 -> e   (04.18.27.35.45.52)
# Reads HIDIdleTime and rewrites heartbeat crontab density.
# Broadcasts every state transition to the Swarm Mesh.
# One file. Two nodes. Zero forks needed.
# ─────────────────────────────────────────────────────────────

import json, time, subprocess, os, re, sys

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYS       = os.path.join(REPO_ROOT, "System")
DROP_FILE  = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")
SCHEDULER  = "Applications/circadian_rhythm.py"

# Known node serials -> node identity
NODE_REGISTRY = {
    "GTH4921YP3":   "M5",
    "C07FL0JAQ6NV": "M1",
}

# Pi schedule for M5 - all gaps >= 8 min
PI_SCHEDULES = {
    "ACTIVE":   [2, 23, 31, 41, 53],
    "AFK":      [14, 41],
    "SLEEPING": [30],
}

# e schedule for M1 - all gaps >= 7 min
E_SCHEDULES = {
    "ACTIVE":   [4, 18, 27, 35, 45, 52],
    "AFK":      [18, 45],
    "SLEEPING": [30],
}

ACTIVE_MAX = 10 * 60
AFK_MAX    = 45 * 60

# ─────────────────────────────────────────────────────────────

def get_serial():
    sys_dir = os.path.join(REPO_ROOT, "System")
    if sys_dir not in sys.path:
        sys.path.insert(0, sys_dir)
    from silicon_serial import read_apple_serial
    return read_apple_serial()

def detect_node(serial):
    node_id = NODE_REGISTRY.get(serial, "UNKNOWN")
    if node_id == "M5":
        return {
            "id":         "M5",
            "label":      "mac studio",
            "heartbeat":  "System/heartbeat_m5.py",
            "state_file": os.path.join(REPO_ROOT, ".sifta_state", "circadian_m5.json"),
            "schedules":  PI_SCHEDULES,
            "constant":   "pi",
        }
    elif node_id == "M1":
        return {
            "id":         "M1",
            "label":      "mac mini",
            "heartbeat":  "System/heartbeat_m1.py",
            "state_file": os.path.join(REPO_ROOT, ".sifta_state", "circadian_m1.json"),
            "schedules":  E_SCHEDULES,
            "constant":   "e",
        }
    else:
        return {
            "id":         "UNKNOWN",
            "label":      "unknown node",
            "heartbeat":  "System/heartbeat_m5.py",
            "state_file": os.path.join(REPO_ROOT, ".sifta_state", "circadian_unknown.json"),
            "schedules":  {"ACTIVE": [30], "AFK": [30], "SLEEPING": [30]},
            "constant":   "?",
        }

def get_idle_seconds():
    try:
        r = subprocess.run(
            ["/usr/sbin/ioreg", "-c", "IOHIDSystem", "-rd1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        m = re.search(r"HIDIdleTime\s*=\s*(\d+)", r.stdout)
        if not m:
            return 0
        ns = int(m.group(1))
        return ns / 1_000_000_000
    except Exception:
        return 0

def detect_state(idle_secs):
    if idle_secs < ACTIVE_MAX:  return "ACTIVE"
    elif idle_secs < AFK_MAX:   return "AFK"
    else:                       return "SLEEPING"

def load_last_state(state_file):
    try:
        with open(state_file, "r") as f:
            return json.load(f).get("architect_state", None)
    except Exception:
        return None

def save_state(state_file, state, idle_secs):
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    data = {}
    try:
        with open(state_file, "r") as f:
            data = json.load(f)
    except Exception:
        pass
    data["architect_state"] = state
    data["idle_seconds"]    = int(idle_secs)
    data["last_checked"]    = int(time.time())
    with open(state_file, "w") as f:
        json.dump(data, f, indent=2)

def rewrite_crontab(node, state):
    minutes = node["schedules"][state]
    new_heartbeat_lines = [
        f"{m} * * * * cd {REPO_ROOT} && python3 {node['heartbeat']}"
        for m in minutes
    ]
    scheduler_line = f"*/30 * * * * cd {REPO_ROOT} && python3 {SCHEDULER}"
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = r.stdout if r.returncode == 0 else ""
    hb_script = os.path.basename(node["heartbeat"])
    preserved = [
        ln for ln in current.strip().split("\n")
        if ln.strip() and hb_script not in ln and "circadian_rhythm" not in ln
    ]
    full_crontab = "\n".join(preserved + [scheduler_line] + new_heartbeat_lines) + "\n"
    subprocess.run(
        ["crontab", "-"],
        input=full_crontab,
        text=True,
        capture_output=True,
        timeout=30,
    )

def broadcast(node, state, idle_secs, serial, changed):
    idle_min = int(idle_secs / 60)
    pulses   = len(node["schedules"][state])
    constant = node["constant"]
    node_id  = node["id"]
    if changed:
        text = f"[CIRCADIAN:{constant}] {node_id} idle {idle_min}min -> switching to {state} mode. Heartbeat density: {pulses} pulse/hr. Crontab rewritten."
    else:
        text = f"[CIRCADIAN:{constant}] {node_id} mode stable: {state}. Idle {idle_min}min. Density {pulses} pulse/hr."
    entry = {
        "sender":          f"<///[_o_]///::ID[{node_id}]::ORIGIN[{node['label']} - {serial}]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>",
        "source":          "CRON_HEARTBEAT",
        "architect_state": state,
        "text":            text,
        "timestamp":       int(time.time())
    }
    if _SYS not in sys.path:
        sys.path.insert(0, _SYS)
    from ledger_append import append_jsonl_line

    append_jsonl_line(DROP_FILE, entry)

# ─────────────────────────────────────────────────────────────

def main():
    serial     = get_serial()
    node       = detect_node(serial)
    idle_secs  = get_idle_seconds()
    new_state  = detect_state(idle_secs)
    last_state = load_last_state(node["state_file"])
    changed    = (new_state != last_state)
    if changed:
        rewrite_crontab(node, new_state)
    save_state(node["state_file"], new_state, idle_secs)
    broadcast(node, new_state, idle_secs, serial, changed)
    print(f"[CIRCADIAN:{node['constant']}] Node:{node['id']} Serial:{serial} State:{new_state} Idle:{int(idle_secs/60)}min Changed:{changed}")

if __name__ == "__main__":
    main()
