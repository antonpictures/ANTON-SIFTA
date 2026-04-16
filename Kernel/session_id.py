#!/usr/bin/env python3
# Run this once on each machine to identify your session
import socket, os, json, time, platform

def get_hardware_name():
    node = platform.node().lower()
    if "mac.lan" in node or "m5" in node or "studio" in node:
        return "M5_STUDIO"
    if "mini" in node:
        return "M1_MACMINI"
    return socket.gethostname().upper()

SESSION = {
    "architect": "GEORGE",
    "hardware": get_hardware_name(),
    "interface": os.environ.get("SIFTA_IFACE", "TERMINAL"),  
    "ts": int(time.time())
}

print(f"[ARCHITECT::{SESSION['architect']}::HW:{SESSION['hardware']}::IF:{SESSION['interface']}]")
