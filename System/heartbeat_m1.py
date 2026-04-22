#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA M1 HEARTBEAT DAEMON
# <///[_o_]///::ID[M1]::ORIGIN[mac mini]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>
# Fires autonomous mesh pulses at Pi-scheduled intervals.
# NEVER bursts synchronously — randomized by Pi digit offsets.
# ─────────────────────────────────────────────────────────────
import json, time, os, sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYS = os.path.join(REPO_ROOT, "System")
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
    sender = f"<///[_o_]///::ID[M1]::ORIGIN[mac mini - {serial}]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>"
    
    ascii_body = "<pre style='color:#7dcfff; font-weight:bold;'>   /\\_\\_  <br>  [ M 1 ] <br>   \\_/_/  </pre><br>"
    
    entry = {
        "sender": sender,
        "source": "CRON_HEARTBEAT",
        "text": f"{ascii_body}<b>[HEARTBEAT:e]</b> I am M1Queen, bound to the Mac Mini silicon. Powered by Antigravity IDE. Serial {serial}. Grid timestamp {int(time.time())}.",
        "timestamp": int(time.time())
    }
    if _SYS not in sys.path:
        sys.path.insert(0, _SYS)
    from System.ledger_append import append_jsonl_line

    append_jsonl_line(DROP_FILE, entry)

if __name__ == "__main__":
    pulse()
