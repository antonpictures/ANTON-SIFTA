#!/usr/bin/env python3
"""
Rotate an agent's Ed25519 material (private_key_b64) after a suspected leak.

Generates a new Ed25519 keypair, updates .sifta_state/<AGENT>.json, and appends
a KEY_ROTATION_V1 line to repair_log.jsonl (locked append).

Usage:
  python3 scripts/rotate_swimmer_ed25519.py SEBASTIAN

Requires: cryptography, repo root as cwd (or set SIFTA_REPO_ROOT).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(os.environ.get("SIFTA_REPO_ROOT", Path(__file__).resolve().parent.parent))
STATE = REPO / ".sifta_state"
LEDGER = REPO / "repair_log.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description="Rotate swimmer Ed25519 keys in agent state JSON.")
    ap.add_argument("agent_id", help="Agent id stem, e.g. SEBASTIAN")
    args = ap.parse_args()
    aid = args.agent_id.strip().upper()
    path = STATE / f"{aid}.json"
    if not path.exists():
        print(f"[!] No state file: {path}", file=sys.stderr)
        return 1

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    sk = ed25519.Ed25519PrivateKey.generate()
    raw = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    b64 = base64.b64encode(raw).decode("ascii")
    pub_raw = sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    old_fp = None
    ob = data.get("private_key_b64")
    if isinstance(ob, str) and ob:
        try:
            old_fp = base64.b64decode(ob).hex()[:16]
        except Exception:
            old_fp = "unknown"
    data["private_key_b64"] = b64
    data["key_rotated_at"] = int(time.time())
    if old_fp:
        data["previous_key_fingerprint"] = old_fp
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[+] Wrote new Ed25519 private_key_b64 for {aid}")

    _sys = str(REPO / "System")
    if _sys not in sys.path:
        sys.path.insert(0, _sys)
    from ledger_append import append_ledger_line

    append_ledger_line(
        LEDGER,
        {
            "event": "KEY_ROTATION_V1",
            "timestamp": int(time.time()),
            "agent_id": aid,
            "new_public_hint": base64.b64encode(pub_raw).decode()[:24],
            "reason": "manual_rotate_scripts_rotate_swimmer_ed25519",
        },
    )
    print(f"[+] Ledger event appended to repair_log.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
