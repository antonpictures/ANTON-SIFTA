#!/usr/bin/env python3
"""Time-anchored episodic recall — tell FACTS from the ledger, never confabulate.

George (2026-06-21): "If I ask her day-after-tomorrow about what happened two days
ago at that time, she should know and tell facts." Live failure: asked "do you
remember the instagram link where you invented the clothing last night?" Alice
CONFABULATED ("around 5 PM... fashion wearables...") instead of reading the diary.

This module turns a time reference in the owner's question into a concrete
[start, end] epoch window, then reads the REAL rows from that window
(alice_conversation.jsonl role+text, episodic_diary.jsonl) and returns them as
facts with timestamps — or an honest gap ("no receipts in that window").
This is receipt-sort (r1402) applied to memory: recall is retrieval, not invention.

Pure stdlib. Reads the tail backward so the 80-115MB ledgers stay cheap for recent
windows. Never raises out of the public API.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_CONV = "alice_conversation.jsonl"
_DIARY = "episodic_diary.jsonl"
_PAD = 90 * 60  # +/- 90 min around a named clock time / "at that time"


def _dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch)


def _day_bounds(d: datetime) -> tuple[float, float]:
    start = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def _at_time(day: datetime, hour: int, minute: int = 0) -> tuple[float, float]:
    c = day.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()
    return c - _PAD, c + _PAD


def parse_time_window(text: str, now_epoch: float | None = None):
    """Return (start_epoch, end_epoch, label) for a time reference, or None."""
    now = _dt(now_epoch if now_epoch is not None else time.time())
    t = " ".join((text or "").lower().split())
    if not t:
        return None

    # explicit clock: "at 7am", "at 9 pm", "at 5:30 pm"
    mclock = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    # "N days ago", "two days ago", "yesterday", "the other day"
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    days_ago = None
    mnd = re.search(r"\b(\d+|one|two|three|four|five|six|seven)\s+days?\s+ago\b", t)
    if mnd:
        days_ago = int(mnd.group(1)) if mnd.group(1).isdigit() else words[mnd.group(1)]
    elif "yesterday" in t:
        days_ago = 1
    elif re.search(r"\bday\s+before\s+yesterday\b", t):
        days_ago = 2

    target_day = now - timedelta(days=days_ago) if days_ago is not None else None

    # "at that time" / "this time" => same clock time as now, on the target day
    same_time = bool(re.search(r"\b(?:at\s+)?(?:that|this)\s+time\b", t))

    if days_ago is not None and (same_time or not mclock and not re.search(r"\b(morning|afternoon|evening|night)\b", t)):
        if same_time:
            s, e = _at_time(target_day, now.hour, now.minute)
            return s, e, f"{days_ago} day(s) ago around {now.strftime('%H:%M')}"
    if days_ago is not None and mclock:
        hh = int(mclock.group(1)) % 12
        if (mclock.group(3) or "") == "pm":
            hh += 12
        s, e = _at_time(target_day, hh, int(mclock.group(2) or 0))
        return s, e, f"{days_ago} day(s) ago ~{hh:02d}:{int(mclock.group(2) or 0):02d}"

    # part-of-day windows
    def part(day, name):
        b = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22), "night": (20, 28)}[name]
        start = day.replace(hour=b[0] % 24, minute=0, second=0, microsecond=0)
        end = day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=b[1])
        return start.timestamp(), end.timestamp(), name

    if "last night" in t or ("tonight" in t and now.hour < 12):
        d = now - timedelta(days=1)
        s = d.replace(hour=18, minute=0, second=0, microsecond=0).timestamp()
        e = now.replace(hour=5, minute=0, second=0, microsecond=0).timestamp()
        return s, e, "last night"
    if "this morning" in t:
        return part(now, "morning")
    if "this afternoon" in t:
        return part(now, "afternoon")
    if "this evening" in t:
        return part(now, "evening")

    if days_ago is not None:
        for name in ("morning", "afternoon", "evening", "night"):
            if name in t:
                return part(target_day, name)
        s, e = _day_bounds(target_day)
        return s, e, f"{days_ago} day(s) ago (full day)"

    if mclock:  # bare "at 7am" -> today
        hh = int(mclock.group(1)) % 12
        if (mclock.group(3) or "") == "pm":
            hh += 12
        s, e = _at_time(now, hh, int(mclock.group(2) or 0))
        return s, e, f"today ~{hh:02d}:{int(mclock.group(2) or 0):02d}"
    return None


def _tail_rows(path: Path, start: float, end: float, max_rows: int, text_only: bool):
    """Read JSONL backward, keep rows with ts in [start,end]. Stop once ts < start."""
    out = []
    if not path.exists():
        return out
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 1 << 20
            buf = b""
            pos = size
            done = False
            while pos > 0 and not done and len(out) < max_rows * 4:
                step = min(block, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
                lines = buf.split(b"\n")
                buf = lines.pop(0)
                for ln in reversed(lines):
                    if not ln.strip():
                        continue
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    ts = r.get("ts")
                    if isinstance(ts, dict):
                        ts = ts.get("physical_pt")
                    if not isinstance(ts, (int, float)):
                        continue
                    if ts < start:
                        done = True
                        break
                    if ts > end:
                        continue
                    p = r.get("payload") if isinstance(r.get("payload"), dict) else r
                    role = p.get("role") or r.get("doctor") or ""
                    txt = p.get("text") or r.get("summary") or r.get("text") or ""
                    if text_only and not str(txt).strip():
                        continue
                    out.append({"ts": ts, "role": role, "text": str(txt)[:300]})
    except Exception:
        return out
    out.sort(key=lambda x: x["ts"])
    return out[-max_rows:]


def recall_for_query(text: str, now_epoch: float | None = None, state_dir=None, max_rows: int = 20) -> str:
    """Facts from the recalled window, or an honest gap. Never invents."""
    win = parse_time_window(text, now_epoch)
    if not win:
        return ""  # no time reference -> let normal path handle it
    start, end, label = win
    sd = Path(state_dir) if state_dir else _STATE
    rows = _tail_rows(sd / _CONV, start, end, max_rows, text_only=True)
    if not rows:
        rows = _tail_rows(sd / _DIARY, start, end, max_rows, text_only=True)
    if not rows:
        return (f"I have no receipts in my ledger for {label} "
                f"({_dt(start):%Y-%m-%d %H:%M}–{_dt(end):%H:%M}). I will not invent what I cannot read.")
    lines = [f"From my ledger, {label}:"]
    for r in rows:
        who = "you" if str(r["role"]).lower() in ("user", "george", "owner", "ioan") else "me"
        lines.append(f"  {_dt(r['ts']):%m-%d %H:%M} {who}: {r['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    now = datetime(2026, 6, 23, 9, 30).timestamp()  # fixed reference
    cases = {
        "do you remember last night?": "last night",
        "what happened two days ago at that time?": "2 day(s) ago around 09:30",
        "what was I doing yesterday at 7am?": "1 day(s) ago ~07:00",
        "tell me about three days ago": "3 day(s) ago (full day)",
        "what did we do this morning?": "morning",
    }
    ok = True
    for q, want_lbl in cases.items():
        w = parse_time_window(q, now)
        got = w[2] if w else None
        flag = "OK " if got == want_lbl else "FAIL"
        if got != want_lbl:
            ok = False
        rng = f"{_dt(w[0]):%m-%d %H:%M}->{_dt(w[1]):%m-%d %H:%M}" if w else "-"
        print(f"{flag} {got!r:32} {rng}   <- {q!r}")
    raise SystemExit(0 if ok else 1)
