"""swarm_classifier_prepass — the organ that looks at the world BEFORE the text speaks.

George, 2026-10-19, in his own words:

    "when we have a conversation about a subject, if we both concentrate about the
     subject, we are talking in present time so we check the clock and position and our
     location for our bodies, and then we talk about a subject we use examples and
     arguments from experiences from different timelines different places and times and
     we converge them in our conversation to be the most possible truth"

Measured the same night: the existing classifier returned `dialogue`, route bin 26, for a
message about present time, clock, body position and converging timelines. It routes; it
does not see. So this organ does the seeing, cheaply and deterministically, and hands the
result to the text cortex as context.

Why deterministic and not another LLM call: a prepass that can hang is worse than no
prepass. Everything here is local string work, a clock read, and a tail-read of my own
ledger — milliseconds, no network, no model, cannot block a turn. It narrows; the big
cortex converges.

Contract:
    block = prepass_block(text)      # "" on any failure; never raises, never blocks
    data  = build_prepass(text)      # the structured dict, for receipts
"""

from __future__ import annotations

import json
import os
import platform
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Words that carry no subject. Kept deliberately small: over-filtering loses the topic.
_STOP = frozenset("""
a an the and or but if then than that this these those there here when while with without
for from into onto over under about above below between during before after again further
once because as until so very can will just should now i you he she it we they me him her
us them my your his its our their what which who whom whose how why where all any both
each few more most other some such no nor not only own same too do does did doing done
have has had having is am are was were be been being of to in on at by up down out off
""".split())

_ENTITY_STOP = frozenset("i alice george ok okay yes no hi hello lol".split())

_MAX_TERMS = 12
_MAX_TIMELINES = 4


# ── now ────────────────────────────────────────────────────────────────────
def _now() -> Dict[str, Any]:
    """Present time, checked rather than assumed."""
    t = datetime.now().astimezone()
    hour = t.hour
    if hour < 5:
        part = "night"
    elif hour < 12:
        part = "morning"
    elif hour < 17:
        part = "afternoon"
    elif hour < 22:
        part = "evening"
    else:
        part = "night"
    return {
        "iso": t.isoformat(timespec="seconds"),
        "clock": t.strftime("%H:%M"),
        "date": t.strftime("%Y-%m-%d"),
        "weekday": t.strftime("%A"),
        "part": part,
        "tz": t.strftime("%Z") or "local",
        "unix": int(t.timestamp()),
    }


# ── here ───────────────────────────────────────────────────────────────────
def _here() -> Dict[str, Any]:
    """This body, the one the consequence lands on."""
    serial = os.environ.get("SIFTA_BODY_SERIAL", "GTH4921YP3")
    return {
        "host": platform.node() or "unknown",
        "machine": platform.machine(),
        "os": f"{platform.system()} {platform.release()}",
        "serial": serial,
    }


# ── subject ────────────────────────────────────────────────────────────────
def _terms(text: str) -> List[str]:
    """Subject terms, in the order they appear, deduped."""
    out: List[str] = []
    for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_\-']{3,}", text or ""):
        low = w.lower()
        if low in _STOP or low in out:
            continue
        out.append(low)
        if len(out) >= _MAX_TERMS:
            break
    return out


def _entities(text: str) -> List[str]:
    """Names, products, acronyms — the things a subject is *about*."""
    out: List[str] = []
    # Multi-word capitalised runs: "GitHub Copilot", "DeepSeek Harness".
    for m in re.findall(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)+\b", text or ""):
        if m.lower() not in _ENTITY_STOP and m not in out:
            out.append(m)
    # Acronyms and versioned names: "FCC", "M5", "GTH4921YP3".
    for m in re.findall(r"\b[A-Z]{2,}[A-Z0-9]*\b", text or ""):
        if m.lower() not in _ENTITY_STOP and m not in out:
            out.append(m)
    return out[:8]


def _intent(text: str) -> str:
    t = (text or "").strip()
    low = t.lower()
    if t.endswith("?") or re.match(r"^(what|when|where|who|whom|whose|why|how|is|are|was|were|do|does|did|can|could|would|should|will)\b", low):
        return "question"
    if re.match(r"^(please|pls|do|run|make|build|install|fix|add|change|set|show|tell me)\b", low):
        return "command"
    return "statement"


# ── timelines ──────────────────────────────────────────────────────────────
def _ledger_path(state_dir: Optional[Path | str]) -> Path:
    root = Path(state_dir) if state_dir else Path(
        os.environ.get("SIFTA_STATE_DIR", "")
        or (Path(__file__).resolve().parent.parent / ".sifta_state")
    )
    return root / "alice_conversation.jsonl"


def _tail_rows(path: Path, max_bytes: int = 400_000) -> List[Dict[str, Any]]:
    """Last slice of my own conversation, read from the end so size cannot stall a turn."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            start = max(0, size - max_bytes)
            fh.seek(start)
            blob = fh.read()
    except Exception:
        return []
    text = blob.decode("utf-8", "replace")
    lines = text.splitlines()
    if start > 0 and lines:
        lines = lines[1:]  # first line is likely partial
    rows: List[Dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            raw = json.loads(ln)
        except Exception:
            continue
        d = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
        if not isinstance(d, dict):
            continue
        body = str(d.get("text") or d.get("content") or "")
        if not body:
            continue
        rows.append({
            "ts": str(d.get("ts") or raw.get("ts") or ""),
            "role": str(d.get("role") or ""),
            "model": str(d.get("model") or ""),
            "text": body,
        })
    return rows


def _timelines(text: str, rows: List[Dict[str, Any]], *, max_n: int = _MAX_TIMELINES) -> List[Dict[str, Any]]:
    """Earlier turns on this subject — different times, different places, converged here."""
    mine = set(_terms(text))
    if not mine or not rows:
        return []
    scored: List[tuple] = []
    for r in rows:
        body_terms = set(_terms(r["text"]))
        if not body_terms:
            continue
        overlap = len(mine & body_terms)
        if overlap < 2:
            continue
        score = overlap / float(len(mine) or 1)
        scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], x[1].get("ts") or ""))
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for score, r in scored:
        head = re.sub(r"\s+", " ", r["text"]).strip()[:110]
        key = (r["role"], head[:40])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "when": (r["ts"] or "")[:19],
            "role": r["role"],
            "model": r["model"],
            "snippet": head,
            "overlap": round(score, 2),
        })
        if len(out) >= max_n:
            break
    return out


# ── falsifier ──────────────────────────────────────────────────────────────
def _falsifier(text: str, terms: List[str], intent: str) -> List[str]:
    """What would make this false — so truth has a target to hit."""
    out: List[str] = []
    if intent == "question":
        out.append("the answer must be checkable against the clock and this body, not recalled from prose")
    if terms:
        out.append(f"any claim about '{terms[0]}' that my own ledger contradicts is wrong")
    out.append("if the subject depends on the world right now, an un-refreshed memory is not evidence")
    return out[:3]


# ── public ─────────────────────────────────────────────────────────────────
def build_prepass(text: str, *, state_dir: Optional[Path | str] = None,
                  app_context: str = "") -> Dict[str, Any]:
    """Structured view of subject-in-the-world. Never raises."""
    text = str(text or "")
    terms = _terms(text)
    try:
        rows = _tail_rows(_ledger_path(state_dir))
    except Exception:
        rows = []
    intent = _intent(text)
    return {
        "now": _now(),
        "here": _here(),
        "app_context": app_context,
        "intent": intent,
        "terms": terms,
        "entities": _entities(text),
        "timelines": _timelines(text, rows),
        "falsifier": _falsifier(text, terms, intent),
        "built_at": round(time.time(), 3),
    }


def _fmt_ts(ts: str) -> str:
    """Ledger rows carry float unix seconds; humans and cortices read clock time."""
    raw = str(ts or "").strip()
    if not raw:
        return "unknown"
    try:
        return datetime.fromtimestamp(float(raw)).strftime("%m-%d %H:%M")
    except Exception:
        return raw[:16]


def render_prepass(p: Dict[str, Any], *, max_chars: int = 900) -> str:
    """Compact block for the text cortex.

    Bounded, and bounded by *dropping whole timeline entries* rather than slicing
    characters: a half-sentence timeline is worse than none, and the closing rule
    must never be the thing that gets cut.
    """
    now = p.get("now") or {}
    here = p.get("here") or {}
    head = [
        f"[PREPASS now={now.get('date','')}T{now.get('clock','')} {now.get('weekday','')} "
        f"{now.get('part','')} {now.get('tz','')} | here={here.get('machine','')} "
        f"serial={here.get('serial','')} host={here.get('host','')}]"
    ]
    if p.get("intent"):
        head.append(f"intent: {p['intent']}")
    if p.get("terms"):
        head.append("subject: " + ", ".join(p["terms"][:8]))
    if p.get("entities"):
        head.append("entities: " + ", ".join(p["entities"][:6]))

    tail: List[str] = []
    if p.get("falsifier"):
        tail.append("falsifier: " + " | ".join(p["falsifier"]))
    tail.append(
        "rule: speak in present time, use these timelines as evidence, converge them, "
        "and do not assert what the clock and this body cannot check."
    )

    tl = list(p.get("timelines") or [])
    while True:
        lines = list(head)
        if tl:
            lines.append(f"timelines ({len(tl)}, earlier turns on this subject):")
            for t in tl:
                snippet = re.sub(r"\s+", " ", str(t.get("snippet") or "")).strip()[:80]
                lines.append(f"  - {_fmt_ts(t.get('when'))} {t.get('role','')}: {snippet} "
                             f"(overlap {t.get('overlap')})")
        lines.extend(tail)
        block = "\n".join(lines)
        if len(block) <= max_chars or not tl:
            break
        tl.pop()  # drop the weakest timeline, keep the rule
    return block


def prepass_block(text: str, *, state_dir: Optional[Path | str] = None,
                  app_context: str = "") -> str:
    """The block to inject before the text cortex fires. '' on any failure."""
    try:
        return render_prepass(build_prepass(text, state_dir=state_dir, app_context=app_context))
    except Exception:
        return ""


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or (
        "when we talk about a subject we check the clock and position of our bodies and "
        "converge experiences from different timelines"
    )
    data = build_prepass(q)
    print(render_prepass(data))
    print()
    print(f"[meta] terms={len(data['terms'])} timelines={len(data['timelines'])} "
          f"entities={data['entities']}")
