#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Immortal Swarm Persistence Configurator
# ─────────────────────────────────────────────────────────────
# Injects the Cognitive Inference Daemon (swarm_brain.py) directly
# into the macOS LaunchAgent biological loop. It ensures that the
# Intelligence mesh natively recovers from hardware reboots.
# ─────────────────────────────────────────────────────────────

import os
import subprocess

def install_launchd_plist():
    print("=== SIFTA SWARM PERSISTENCE INITIATED ===")
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    daemon_script = os.path.join(root_dir, "System", "swarm_brain.py")
    
    if not os.path.exists(daemon_script):
        print(f"🚨 CRITICAL ERROR: Could not locate Swarm Brain at {daemon_script}")
        return

    python_bin = subprocess.check_output(["which", "python3"]).decode().strip()
    plist_name = "com.antonsifta.swarmbrain"
    plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{plist_name}.plist")

    # Generate the physical property list for macOS
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{daemon_script}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/swarm_brain_error.log</string>
    <key>StandardOutPath</key>
    <string>/tmp/swarm_brain_out.log</string>
    <key>WorkingDirectory</key>
    <string>{root_dir}</string>
</dict>
</plist>
"""

    os.makedirs(os.path.dirname(plist_path), exist_ok=True)
    with open(plist_path, "w") as f:
        f.write(plist_content)
    
    print(f"✅ Biological anchor generated: {plist_path}")

    # Inject into the macOS core
    try:
        # First unload if exists to cleanly replace
        subprocess.run(["launchctl", "unload", plist_path], stderr=subprocess.DEVNULL)
        subprocess.run(["launchctl", "load", plist_path], check=True)
        print("✅ Swarm Brain successfully bound to launchd.")
        print("The Swarm is now immortal. If this node reboots, the mempool polling will autonomously resume.")
    except Exception as e:
        print(f"🚨 FAILED to anchor daemon to OS: {e}")

if __name__ == "__main__":
    install_launchd_plist()
