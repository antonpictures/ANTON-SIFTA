#!/usr/bin/env python3
"""swarm_opencode_body_feed.py — feed the laptop's continuous sensor state into OpenCode.

OpenCode runs non-stop (`opencode serve`). This organ reads the body's latest
perception (latest_perception.json), active window, body snapshot, and ambient
transcript tail, formats a compact digest, and injects it as a text job into a
dedicated OpenCode session via `opencode run`. Result: the bigger cortex sees
the room/body state on a cadence without the owner typing.

Usage:
  python3 System/swarm_opencode_body_feed.py            # feed forever (5 min)
  python3 System/swarm_opencode_body_feed.py --once     # one feed
  python3 System/swarm_opencode_body_feed.py --interval 120
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
SESSION_FILE = STATE / "body_feed_session.txt"
OPENCODE_CLI = os.environ.get(
    "OPENCODE_CLI",
    "/Users/ioanganton/Library/Application Support/ai.opencode.desktop/cli/2.4.1-arm64/opencode-cli",
)
LOG = Path("/tmp/opencode_body_feed.log")


def _log(msg: str) -> None:
    line = f"{__import__('datetime').datetime.now().isoformat()} {msg}"
    print(line, flush=True)
    try:
        LOG.open("a").write(line + "\n")
    except Exception:
        pass


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _read_last_jsonl(path: Path) -> dict:
    try:
        if path.exists():
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                return json.loads(lines[-1])
    except Exception:
        pass
    return {}


def gather_digest() -> str:
    perc = _read_json(STATE / "latest_perception.json")
    window = _read_last_jsonl(STATE / "active_window.jsonl")
    body = _read_json(STATE / "alice_body_snapshot.json")
    ambient_tail = ""
    try:
        lines = [l for l in (STATE / "ambient_room_transcripts.jsonl").read_text().splitlines() if l.strip()]
        if lines:
            last = json.loads(lines[-1])
            ambient_tail = str(last.get("text") or last.get("text_preview") or "")[:180]
    except Exception:
        pass

    vitals = perc.get("system_vitals") or {}
    iso = perc.get("iso") or ""
    summary = perc.get("perception_summary") or ""
    transcript = perc.get("audio_transcript") or ""
    app = window.get("app") or body.get("autopilot", {}).get("desktop_processes")
    win = window.get("window")
    mem = body.get("memory", {})
    power = body.get("power", {})

    parts = [
        f"[BODY FEED {iso}]",
        f"perception: {summary[:240]}",
    ]
    if transcript:
        parts.append(f"heard: {transcript[:160]}")
    if ambient_tail and ambient_tail != transcript:
        parts.append(f"room: {ambient_tail[:160]}")
    parts.append(f"window: {app} — {win}")
    parts.append(f"vitals: load {vitals.get('load1')}/{vitals.get('load5')}/{vitals.get('load15')} "
                 f"cpu {vitals.get('cpu_pct')}% mem {vitals.get('mem_used_pct')}% "
                 f"bat {vitals.get('battery_pct')}% {vitals.get('power')}")
    parts.append(f"mem: {mem.get('free_bytes',0)//(1024**3)}GB free / {mem.get('total_bytes',0)//(1024**3)}GB")
    return " | ".join(parts)


def get_or_create_session() -> str:
    if SESSION_FILE.exists():
        sid = SESSION_FILE.read_text().strip()
        if sid.startswith("ses_"):
            return sid
    # create a new session by sending one message without --session
    out = _run_opencode("Body feed online. You are Alice's body-feed channel: read each digest and reply with one short line.")
    sid = _parse_session_id(out)
    if sid:
        SESSION_FILE.write_text(sid)
    return sid


def _parse_session_id(output: str) -> str:
    m = re.search(r'"sessionID"\s*:\s*"(ses_[A-Za-z0-9]+)"', output)
    return m.group(1) if m else ""


def _run_opencode(message: str, session_id: str | None = None) -> str:
    cmd = [OPENCODE_CLI, "run", message, "--format", "json"]
    if session_id:
        cmd += ["--session", session_id]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        _log(f"opencode run failed: {e}")
        return ""


def feed_once() -> None:
    digest = gather_digest()
    _log(f"digest: {digest[:200]}")
    sid = get_or_create_session()
    if sid:
        out = _run_opencode(digest, sid)
        # extract reply text
        reply = ""
        for line in out.splitlines():
            try:
                obj = json.loads(line)
                if obj.get("type") == "text":
                    reply = obj.get("part", {}).get("text", "")
            except Exception:
                pass
        _log(f"reply: {reply[:200]}")
    else:
        _log("no session id; skipping injection")


def main() -> int:
    ap = argparse.ArgumentParser(description="Feed body sensor state into OpenCode")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=300, help="seconds between feeds")
    args = ap.parse_args()

    STATE.mkdir(parents=True, exist_ok=True)
    _log(f"body feed started (interval={args.interval}s)")

    while True:
        try:
            feed_once()
        except Exception as e:
            _log(f"feed crashed: {e}")
        if args.once:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
