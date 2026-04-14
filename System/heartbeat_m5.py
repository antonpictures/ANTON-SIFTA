#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA M5 HEARTBEAT DAEMON
# <///[_o_]///::ID[M5]::ORIGIN[mac studio]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>
# Fires autonomous mesh pulses at Pi-scheduled intervals.
# NEVER bursts synchronously — randomized by Pi digit offsets.
# ─────────────────────────────────────────────────────────────
import json, time, os, sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP_FILE = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")

def get_serial():
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from silicon_serial import read_apple_serial
    s = read_apple_serial()
    return s if s != "UNKNOWN_SERIAL" else "UNKNOWN_HW"

def pulse():
    serial = get_serial()
    sender = f"<///[_o_]///::ID[M5]::ORIGIN[mac studio - {serial}]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>"
    entry = {
        "sender": sender,
        "source": "CRON_HEARTBEAT",  # distinguishes cron from human transmissions
        "text": f"[HEARTBEAT:π] M5_IDE_AG alive. Serial {serial}. Grid timestamp {int(time.time())}.",
        "timestamp": int(time.time())
    }
    with open(DROP_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    pulse()
