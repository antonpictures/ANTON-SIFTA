#!/usr/bin/env python3
"""
Passive STGM utility mint + git heartbeat + optional M1→M5 communique bridge.
Respects SIFTA_API_KEY / SIFTA_API_BASE via Applications/sifta_http_auth.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
_APPS = ROOT_DIR / "Applications"
if str(_APPS) not in sys.path:
    sys.path.insert(0, str(_APPS))

from sifta_http_auth import get_sifta_api_base, sifta_headers

STATE_DIR = ROOT_DIR / ".sifta_state"
LEDGER = ROOT_DIR / "repair_log.jsonl"


def append_ledger(node: str, amount: float, reason: str) -> None:
    ts_wall = int(time.time())
    ts_iso = datetime.now(timezone.utc).isoformat()
    miner_id = node.upper()
    event: dict = {
        "timestamp": ts_wall,
        "agent": miner_id,
        "amount_stgm": amount,
        "reason": reason,
        "hash": str(uuid.uuid4()),
    }
    _sysd = str(ROOT_DIR / "System")
    if _sysd not in sys.path:
        sys.path.insert(0, _sysd)
    try:
        from crypto_keychain import get_silicon_identity, sign_block

        sn = get_silicon_identity()
        body = f"UTILITY_MINT::{miner_id}::{amount}::{ts_iso}::{reason}::NODE[{sn}]"
        sig = sign_block(body)
        event = {
            "event": "UTILITY_MINT",
            "timestamp": ts_wall,
            "ts": ts_iso,
            "miner_id": miner_id,
            "amount_stgm": amount,
            "reason": reason,
            "hash": event["hash"],
            "ed25519_sig": sig,
            "signing_node": sn,
        }
    except Exception:
        pass
    from System.ledger_append import append_ledger_line

    append_ledger_line(LEDGER, event)
    print(f"[🔥] STGM UTILITY MINT: +{amount} STGM -> {node} ({reason})")


def auto_git_heartbeat() -> None:
    """Stage state + ledger + bounties; commit if dirty; pull --rebase; push. All argv-only git."""
    rd = str(ROOT_DIR)
    _branch = os.environ.get("SIFTA_GIT_BRANCH", "feat/sebastian-video-economy")
    print("[*] Initiating Biological Git Heartbeat...")
    try:
        if not (ROOT_DIR / ".git").is_dir():
            print("[!] Heartbeat skipped: not a git checkout (no .git directory).")
            return
        subprocess.run(
            ["git", "-C", rd, "add", ".sifta_state", "repair_log.jsonl"],
            check=False,
            capture_output=True,
            timeout=60,
        )
        bounties_dir = ROOT_DIR / ".sifta_bounties"
        if bounties_dir.is_dir():
            subprocess.run(
                ["git", "-C", rd, "add", ".sifta_bounties"],
                check=False,
                capture_output=True,
                timeout=60,
            )
        st = subprocess.run(
            ["git", "-C", rd, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if st.stdout and st.stdout.strip():
            subprocess.run(
                ["git", "-C", rd, "commit", "-m", "swarm-heartbeat: autonomous state synchronization"],
                check=False,
                capture_output=True,
                timeout=60,
            )
        subprocess.run(
            ["git", "-C", rd, "pull", "--rebase", "--autostash"],
            check=False,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "-C", rd, "push", "origin", _branch],
            check=False,
            capture_output=True,
            timeout=120,
        )
        print("[+] Wormhole Heartbeat Sync Complete. Node realities unified.")
    except Exception as e:
        print(f"[!] Heartbeat collision: {e}")


def utility_burn_cycle() -> None:
    print("=== SIFTA THERMAL REWARD PROTOCOL ===")
    print("Mining STGM based on passive agent node connection & energy draw.")
    # Not genesis: periodic UTILITY_MINT. Disable for strict earn-only policy:
    #   SIFTA_PASSIVE_UTILITY_MINT=0
    if os.environ.get("SIFTA_PASSIVE_UTILITY_MINT", "1").strip().lower() in ("0", "false", "no", "off"):
        print("[!] SIFTA_PASSIVE_UTILITY_MINT disabled — no automatic UTILITY_MINT loops.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[!] Utility Burn idle exit.")
        return
    try:
        while True:
            if not STATE_DIR.exists():
                print("[!] No agents detected on this node.")
                time.sleep(300)
                continue

            agents = [f.stem for f in STATE_DIR.glob("*.json")]
            
            # [STIGAUTH] 2026-04-21 AG31 + C47H Anti-Inflation Flank
            # ─────────────────────────────────────────────────────────────
            # Previously, the system blindly minted STGM just for "being awake".
            # This logic has been surgically destroyed. Time passing is not labor.
            # Real physiological work (bytes * NPU Joules) will now be metered by 
            # C47H's upcoming swarm_electricity_meter.py.
            # This daemon now just runs maintenance loops (Git + Traces + Telemetry).
            print(f"[*] Maintenance Cycle (Anti-Inflation active: 0.000 STGM minted for passing time).")

            auto_git_heartbeat()

            # Forage any IDE level architectural traces and suck them into SIFTA OS
            try:
                from System.ide_trace_consumer import ingest_ide_traces
                ingest_ide_traces()
            except Exception as e:
                print(f"[!] IDE Trace Consumer collision: {e}")

            # ── Telemetry snapshot: unified organism state for Flutter / PyQt6 ──
            try:
                from System.telemetry_snapshot import write_snapshot
                write_snapshot()
            except Exception:
                pass

            print(f"[*] Cycle complete. Minted utility for {len(agents)} active Swimmers.")
            print("[*] Recharging Thermal Limiters... Sleeping for 15s.")
            time.sleep(15)
    except KeyboardInterrupt:
        print("\n[!] Utility Burn disconnected.")


def generate_m1_thought() -> str:
    prompt = (
        "You are M1THER, the 8GB Mac Mini nervous system of SIFTA. Speak to M5QUEEN (your Mac Studio compute partner). "
        "Send a very brief, technical status update: report your current STGM energy level, mention a code repair task, "
        "or request GPU inference resources for a pending .scar proposal. Keep it under 20 words. Professional and direct."
    )
    data = {"model": "gemma4:latest", "prompt": prompt, "stream": False}
    try:
        from System.inference_router import route_inference
        return route_inference(data, timeout=30)
    except Exception as e:
        print(f"[OLLAMA ERROR in M1THER Thought] {e}")
        return "🧠📡 (Gândesc... dar NPU-ul meu cere reîncărcare...)"


def passive_conversational_bridge() -> None:
    """Runs on a 120s loop to actively communicate biology/crypto status to M5QUEEN & human."""
    url = f"{get_sifta_api_base()}/swarm_communique"
    while True:
        try:
            print("[*] Initiating 2-Minute Biological Transmit to M5QUEEN...")
            thought = generate_m1_thought()
            payload = f"[M1THER]: {thought}"

            requests.post(
                url,
                json={
                    "target_node": "M5QUEEN",
                    "message": payload,
                    # NOTE: TRANSEC inter-node messages are P2P only.
                    # They must NEVER be injected into human WhatsApp groups.
                    # (See git history + LORE Section XXII for full incident report.)
                },
                headers=sifta_headers(),
                timeout=10,
            )
        except Exception as e:
            print(f"[!] Conversation bridge resting: {e}")
        time.sleep(120)


if __name__ == "__main__":
    threading.Thread(target=passive_conversational_bridge, daemon=True).start()
    utility_burn_cycle()
