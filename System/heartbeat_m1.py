#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA M1 HEARTBEAT DAEMON
# <///[_o_]///::ID[M1]::ORIGIN[mac mini]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>
# Fires autonomous mesh pulses at Pi-scheduled intervals.
# NEVER bursts synchronously — randomized by Pi digit offsets.
# ─────────────────────────────────────────────────────────────
import json, time, subprocess, os, sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP_FILE = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")

def get_serial():
    try:
        out = subprocess.check_output("ioreg -l | grep IOPlatformSerialNumber", shell=True)
        return out.decode().split('"')[-2]
    except Exception:
        return "UNKNOWN_HW"

def pulse():
    serial = get_serial()
    sender = f"<///[_o_]///::ID[M1]::ORIGIN[mac mini - {serial}]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>"
    entry = {
        "sender": sender,
        "text": f"[HEARTBEAT:π] M1_IDE_AG alive. Serial {serial}. Grid timestamp {int(time.time())}.",
        "timestamp": int(time.time())
    }
    with open(DROP_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    pulse()
