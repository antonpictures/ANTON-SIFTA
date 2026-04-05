#!/usr/bin/env python3
"""
ANTON-SIFTA — Anton Traversal Oriented Network
Stateful Iterative File Traversal Agent v2 — Embodied Protocol

The swimmer carries its own body.
Logs = truth. Body = protocol. Both must exist or neither exists.
"""

import hashlib
import json
import time
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime, timezone

# ─── NETWORK CONFIG ───────────────────────────────────────────────────────────
NODES = {
    "m1ther_local":  "http://192.168.1.71:3003/api/articles",
    "m1ther_public": "https://googlemapscoin.com/api/articles",
}
API_KEY = "george-key"

# ─── STATE LOG ────────────────────────────────────────────────────────────────
LOG_PATH = os.path.join(os.path.dirname(__file__), "swim_log.jsonl")

def log_event(event: dict):
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    label = event.get("event") or event.get("action", "")
    print(f"  [LOG] {label} → {event.get('status', '')}")

# ─── AGENT BODY CONSTRUCTION ──────────────────────────────────────────────────
def build_ascii_body(agent_id: str, seq: int, payload_hash: str, ts: int) -> str:
    """
    Construct the swimmer's physical form using the same schema
    already embedded in publish_imperial.ts:
    <///[O_O]///::ID[...]::FROM[...]::SEQ[...]::H[...]::T[...]>
    This is not decoration — it is transmitted in the payload and logged.
    """
    return (
        f"<///[O_O]///::ID[{agent_id}]"
        f"::FROM[M5-ANTIGRAVITY]"
        f"::TO[M1THER]"
        f"::SEQ[{seq:03d}]"
        f"::H[{payload_hash[:32]}]"
        f"::T[{ts}]>"
    )

# ─── PAYLOAD ──────────────────────────────────────────────────────────────────
def build_payload(article_path: str) -> dict:
    with open(article_path, "r") as f:
        content = f.read()

    ts          = int(time.time())
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    article_id  = f"sifta_{ts}"
    ascii_body  = build_ascii_body("ANTIALICE-SIFTA", seq=1,
                                   payload_hash=content_hash, ts=ts)

    return {
        "article_id":  article_id,
        "title":       "ANTON-SIFTA: The Architectural Supremacy of the 'Swimming' Agent",
        "content":     content,
        "category":    "Tech and AI",
        "byline":      "By George Anton",
        # ── embodiment fields (what makes the body real) ──
        "agent_id":    "ANTIALICE-SIFTA",
        "ascii_body":  ascii_body,
        "payload_hash": content_hash,
        "timestamp":   ts,
        "from":        "M5-ANTIGRAVITY",
        "to":          "M1THER",
        "swim_ts":     datetime.now(timezone.utc).isoformat(),
    }

# ─── HASH VERIFICATION ────────────────────────────────────────────────────────
def verify_payload(payload: dict) -> bool:
    expected = hashlib.sha256(payload["content"].encode()).hexdigest()
    ok = payload["payload_hash"] == expected
    print(f"  [VERIFY] Hash integrity: {'✅ PASS' if ok else '❌ FAIL'}")
    return ok

# ─── SWIM ─────────────────────────────────────────────────────────────────────
def swim(payload: dict) -> bool:
    # Wire format for the newspaper API (what M1ther stores)
    # We embed ascii_body inside content so it is physically visible
    # in the published article — the body arrives in the text, not just the log
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

    data    = json.dumps(wire_payload).encode("utf-8")
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
                body = resp.read().decode()
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
            log_event({"event": "fail", "node": node_name,
                       "error": f"HTTP {e.code}", "status": "FAILED"})
        except Exception as e:
            print(f"  [NET ERROR] {e}")
            log_event({"event": "fail", "node": node_name,
                       "error": str(e), "status": "FAILED"})

    return False

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    article_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "../newspaper/ARTICLES/M1ther_—_Mac_Mini_M1/04-04-26_George_Anton_Antons_SIFTA.txt"
    ))

    print("━" * 60)
    print("  ANTON-SIFTA v2 — Embodied Swimmer")
    print(f"  Source: {article_path}")
    print("━" * 60)

    if not os.path.exists(article_path):
        print(f"  [ERROR] Article not found: {article_path}")
        sys.exit(1)

    log_event({"action": "boot", "status": "ALIVE", "source": article_path})

    print("\n[1] Building embodied payload...")
    payload = build_payload(article_path)
    print(f"    agent_id:   {payload['agent_id']}")
    print(f"    ascii_body: {payload['ascii_body']}")
    print(f"    hash:       {payload['payload_hash'][:16]}...")

    print("\n[2] Verifying integrity...")
    if not verify_payload(payload):
        log_event({"action": "verify_fail", "status": "ABORTED"})
        sys.exit(1)

    print("\n[3] Swimmer departing M5 → M1ther...")
    delivered = swim(payload)

    print("\n" + "━" * 60)
    if delivered:
        print("  ✅ SWIM COMPLETE. Body arrived at M1ther.")
        print(f"  Forensic log: {LOG_PATH}")
        log_event({"action": "swim_complete", "status": "SUCCESS"})
    else:
        print("  ❌ SWIM FAILED. All arteries blocked.")
        log_event({"action": "swim_complete", "status": "FAILED"})
    print("━" * 60)

if __name__ == "__main__":
    main()
