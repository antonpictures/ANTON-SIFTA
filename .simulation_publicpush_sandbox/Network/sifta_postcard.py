# sifta_postcard.py
# GEN8 — Human Layer Memory
# "Scars tell the swarm what happened. Postcards tell the Architect why it mattered."

import json
import time
from pathlib import Path
from datetime import datetime

POSTCARD_DIR = Path(".sifta_state/postcards")
POSTCARD_DIR.mkdir(parents=True, exist_ok=True)


def write_postcard(message: str, context: dict = None, author: str = "ARCHITECT") -> Path:
    ts = time.time()
    ts_int = int(ts)

    payload = {
        "timestamp": ts,
        "date": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "author": author,
        "message": message,
        "context": context or {}
    }

    path = POSTCARD_DIR / f"{ts_int}.postcard.json"
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  [💌 POSTCARD] \"{message[:72]}{'...' if len(message) > 72 else ''}\"")
    return path


def read_postcards(limit: int = 10) -> list:
    files = sorted(POSTCARD_DIR.glob("*.postcard.json"), reverse=True)
    out = []
    for f in files[:limit]:
        try:
            with open(f) as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    return out


def print_postcards(limit: int = 10):
    cards = read_postcards(limit)
    if not cards:
        print("  [💌] No postcards written yet.")
        return
    print("══════════════════════════════════════════════════")
    print("  💌  POSTCARD MEMORY — HUMAN LAYER")
    print("══════════════════════════════════════════════════")
    for c in cards:
        print(f"  [{c.get('date', '?')}] — {c.get('author', '?')}")
        print(f"  \"{c['message']}\"")
        if c.get("context"):
            print(f"  {c['context']}")
        print("  ──────────────────────────────────────────────")
