#!/usr/bin/env python3
"""
System/swarm_imessage_receptor.py
═══════════════════════════════════════════════════════════════════════════
The Synaptic Tap (Two-Way iMessage Telepathy) — C47H 2026-04-23

A background daemon that monitors the local macOS Messages SQLite database
(`chat.db`) for incoming texts from the Architect.

When a new text arrives, it drops it into `.sifta_state/imessage_inbox.jsonl`
for Alice's brain to read and respond to natively.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ID_FILE = _STATE / "architect_imessage_id.txt"
_INBOX_FILE = _STATE / "imessage_inbox.jsonl"
_STATE_FILE = _STATE / "imessage_receptor_state.json"
_CHAT_DB = Path.home() / "Library/Messages/chat.db"


def _get_architect_handle(conn: sqlite3.Connection) -> int:
    """Resolve the Architect's target string to a SQLite handle_id."""
    if not _ID_FILE.exists():
        return -1
    raw_id = _ID_FILE.read_text().strip()
    if not raw_id:
        return -1
        
    # SQLite LIKE search to match variations (+1323..., 323...)
    # We strip the '+' or leading '1' for a broader match.
    search_term = raw_id.replace("+1", "").replace("+", "").replace("-", "").replace(" ", "")
    
    cur = conn.cursor()
    cur.execute("SELECT ROWID FROM handle WHERE id LIKE ? OR uncanonicalized_id LIKE ?", (f"%{search_term}%", f"%{search_term}%"))
    row = cur.fetchone()
    if row:
        return row[0]
    return -1


def _read_last_rowid() -> int:
    if not _STATE_FILE.exists():
        return -1
    try:
        return json.loads(_STATE_FILE.read_text()).get("last_rowid", -1)
    except Exception:
        return -1


def _write_last_rowid(rowid: int) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps({"last_rowid": rowid}))


def _deposit_inbox(text: str) -> None:
    """Deposit the incoming message to the inbox."""
    _INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "text": text,
        "processed": False
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_INBOX_FILE, json.dumps(row) + "\n")
    except Exception:
        with _INBOX_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            
    # Update pheromone field to wake Alice
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_imessage_receptor", intensity=2.0)
    except Exception:
        pass


def sense_loop() -> None:
    """Main daemon loop."""
    print(f"[imessage_receptor] Starting tap on {_CHAT_DB}")
    if not _CHAT_DB.exists():
        print(f"[imessage_receptor] ERROR: {_CHAT_DB} not found.")
        return

    # To avoid blasting Alice with old history on first run, we fast-forward
    last_rowid = _read_last_rowid()
    if last_rowid == -1:
        try:
            with sqlite3.connect(f"file:{_CHAT_DB}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(ROWID) FROM message")
                row = cur.fetchone()
                if row and row[0]:
                    last_rowid = row[0]
                    _write_last_rowid(last_rowid)
                    print(f"[imessage_receptor] Fast-forwarded to ROWID {last_rowid}")
        except Exception as e:
            print(f"[imessage_receptor] ERROR during fast-forward: {e}")

    consecutive_errors = 0
    while True:
        try:
            with sqlite3.connect(f"file:{_CHAT_DB}?mode=ro", uri=True) as conn:
                handle_id = _get_architect_handle(conn)
                if handle_id == -1:
                    time.sleep(5)
                    continue

                cur = conn.cursor()
                # is_from_me = 0 means incoming message
                # Note: if the Architect texts their own Apple ID from their iPhone,
                # macOS Messages might treat it as incoming (0) or outgoing (1).
                # We check `handle_id` to be sure. 
                query = """
                    SELECT ROWID, text, is_from_me 
                    FROM message 
                    WHERE handle_id = ? AND ROWID > ? AND text IS NOT NULL
                    ORDER BY ROWID ASC
                """
                cur.execute(query, (handle_id, last_rowid))
                rows = cur.fetchall()
                
                for row in rows:
                    r_id, text, is_from_me = row
                    
                    # We only ingest messages that are not system-generated swimmers
                    # AND we ensure they don't start with SIFTA_SWIM: to prevent feedback loops.
                    if text and not text.startswith("SIFTA_SWIM:"):
                        # If the Architect sends a message from their iPhone to the Mac's account
                        # we ingest it. 
                        print(f"[imessage_receptor] New message intercepted: {text}")
                        _deposit_inbox(text)
                    
                    last_rowid = r_id
                    _write_last_rowid(last_rowid)
                    
            consecutive_errors = 0
            
        except sqlite3.OperationalError as e:
            # chat.db might be locked temporarily by imagent
            consecutive_errors += 1
            if consecutive_errors > 5:
                print(f"[imessage_receptor] SQLite Error (Needs Full Disk Access?): {e}")
        except Exception as e:
            print(f"[imessage_receptor] Loop error: {e}")
            
        time.sleep(2.0)


if __name__ == "__main__":
    sense_loop()
