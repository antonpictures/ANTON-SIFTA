#!/usr/bin/env python3
"""
ANTON-SIFTA — Anton Traversal Oriented Network
agent.py — The physical courier layer.
"""

import hashlib
import json
import time
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime, timezone

from body_state import SwarmBody, parse_body_state

# ─── NETWORK CONFIG ───────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        NODES = config.get("nodes", {})
else:
    NODES = {"m1ther_public": "https://googlemapscoin.com/api/articles"}

API_KEY = os.environ.get("SIFTA_API_KEY", "")

LOG_PATH = os.path.join(os.path.dirname(__file__), "swim_log.jsonl")

def log_event(event: dict):
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    label = event.get("event") or event.get("action", "")
    print(f"  [LOG] {label} → {event.get('status', '')}")

def build_payload(article_path: str, body_obj: SwarmBody) -> dict:
    with open(article_path, "r") as f:
        content = f.read()

    ts = int(time.time())
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    article_id = f"sifta_{ts}"
    
    # Use the SwarmBody class directly
    ascii_body = body_obj.generate_body("M5", "M1THER", content_hash[:16])

    return {
        "article_id":  article_id,
        "title":       "ANTON-SIFTA: Clean Architecture Validation",
        "content":     content,
        "category":    "Tech and AI",
        "byline":      "By George Anton",
        "agent_id":    body_obj.agent_id,
        "ascii_body":  ascii_body,
        "payload_hash": content_hash,
        "timestamp":   ts,
        "from":        "M5",
        "to":          "M1THER",
        "swim_ts":     datetime.now(timezone.utc).isoformat(),
    }

def verify_payload(payload: dict) -> bool:
    expected = hashlib.sha256(payload["content"].encode()).hexdigest()
    ok = payload["payload_hash"] == expected
    print(f"  [VERIFY] Hash integrity: {'✅ PASS' if ok else '❌ FAIL'}")
    return ok

def swim(payload: dict) -> bool:
    body_stamp = (
        f"\n\n---\n"
        f"**SWIMMER BODY:** `{payload['ascii_body']}`  \n"
        f"**AGENT:** {payload['agent_id']}  \n"
        f"**FROM:** {payload['from']} → **TO:** {payload['to']}  \n"
        f"**HASH:** `{payload['payload_hash'][:32]}...`  \n"
        f"**SWIM_TS:** {payload['swim_ts']}"
    )

    wire_payload = {
        "title":    payload["title"],
        "content":  payload["content"] + body_stamp,
        "category": payload["category"],
        "byline":   payload["byline"],
    }

    data = json.dumps(wire_payload).encode("utf-8")
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    for node_name, url in NODES.items():
        print(f"\n  [SWIM] Attempting artery: {node_name} → {url}")
        log_event({
            "event":      "depart",
            "agent_id":   payload["agent_id"],
            "ascii_body": payload["ascii_body"],
            "from":       payload["from"],
            "to":         payload["to"],
            "node":       node_name,
            "hash":       payload["payload_hash"][:16],
            "status":     "DEPARTING"
        })

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                print(f"  [✅] Delivered. HTTP {resp.status}.")
                log_event({
                    "event":      "arrive",
                    "agent_id":   payload["agent_id"],
                    "ascii_body": payload["ascii_body"],
                    "to":         payload["to"],
                    "node":       node_name,
                    "http_status": resp.status,
                    "status":     "ARRIVED"
                })
                return True
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            print(f"  [HTTP ERROR] {e.code}: {err[:200]}")
            log_event({"event": "fail", "node": node_name, "error": f"HTTP {e.code}", "status": "FAILED"})
        except Exception as e:
            print(f"  [NET ERROR] {e}")
            log_event({"event": "fail", "node": node_name, "error": str(e), "status": "FAILED"})

    return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ANTON-SIFTA File Traversal & Delivery Layer")
    parser.add_argument("--payload", type=str, required=False, help="Payload file to transmit")
    args = parser.parse_args()

    print("━" * 60)
    print("  ANTON-SIFTA File Traversal & Delivery Layer")
    print("━" * 60)

    if not args.payload or not os.path.exists(args.payload):
        print(f"  [ERROR] Source payload not found or not provided.")
        # Make a dummy payload for testing
        print(f"  [TEST] Running in isolated clean directory test mode.")
        alice = SwarmBody("ANTIALICE")
        body = alice.generate_body("M5", "M1THER", "DUMMY_PAYLOAD")
        print(f"    {body}")
    else:
        alice = SwarmBody("ANTIALICE")
        print("\n[1] Building embodied payload...")
        payload = build_payload(args.payload, alice)
        print(f"    agent_id:   {payload['agent_id']}")
        print(f"    ascii_body: {payload['ascii_body']}")
        
        print("\n[2] Verifying integrity...")
        if not verify_payload(payload):
            log_event({"action": "verify_fail", "status": "ABORTED"})
            sys.exit(1)
            
        print("\n[3] Swimmer departing M5 → M1ther...")
        delivered = swim(payload)
        
        if delivered:
            print("  ✅ SWIM COMPLETE. Body arrived.")
        else:
            print("  ❌ SWIM FAILED.")

if __name__ == "__main__":
    main()
