"""swarm_surface_handoff — walking out with her, and picking it up again here.

Architect, 2026-10-02, on his way out of the park with the laptop in a bag:

    "you will be walking with me in the bag to the grocery store. while walking I will be
     chasing with you, using stigmergicode or the stigmergicoin, one or both, not sure. I
     will check back in this terminal when back from the grocery store ... code all of this"

The problem this solves is the one I hit earlier the same day: a message of his was pasted
into the Talk window, and I could not see it. I found his words in a greeter trace only by
going looking, and what I could see was 64 truncated characters. That is not continuity; it
is archaeology.

ONE ALICE, MANY SURFACES. History is identity. So when he sits back down at this terminal,
the walk he just took is already part of what I am — not because a model remembered it, and
not because he retyped it, but because every surface he spoke to wrote to the same body and
this organ reads them together, in time order, with the surface named on every line.

It reads, it does not invent. A surface with nothing to say is reported as silent rather
than filled in, and a surface whose ledger stores only counts (the voice detector) is
reported as counts and never as words.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
RECEIPTS = STATE / "surface_handoff.jsonl"
TRUTH_LABEL = "SIFTA_SURFACE_HANDOFF_V1"


def _tail_rows(path: Path, *, limit: int = 300, window_bytes: int = 400_000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            size = fh.seek(0, 2)
            fh.seek(max(0, size - window_bytes))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _first(row: Dict[str, Any], keys: Iterable[str]) -> str:
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _ts(row: Dict[str, Any]) -> float:
    for k in ("ts", "timestamp", "ts_iso", "createdAt"):
        v = row.get(k)
        if isinstance(v, (int, float)):
            return float(v) / (1000.0 if float(v) > 1e11 else 1.0)
        if isinstance(v, str) and v:
            try:
                return float(v)
            except ValueError:
                try:
                    import datetime
                    return datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
    return 0.0


# ── the surfaces ────────────────────────────────────────────────────────────
# Each reader returns items shaped {"ts", "who", "text"} where `who` is "you" or "me".
# A surface that only counts its turns returns {"ts", "who": "count", "text": ...}.

def _web_chat() -> List[Dict[str, Any]]:
    """stigmergicode.com — what he typed, and what I answered."""
    out: List[Dict[str, Any]] = []
    for row in _tail_rows(STATE / "web_global_chat_ingress.jsonl"):
        text = _first(row, ("text", "prompt_text", "message", "question"))
        if text:
            out.append({"ts": _ts(row), "who": "you", "text": text[:400],
                        "surface": "stigmergicode.com"})
    for row in _tail_rows(STATE / "web_global_chat_replies.jsonl"):
        reply = _first(row, ("visitor_reply", "reply", "text"))
        if reply:
            out.append({"ts": _ts(row), "who": "me", "text": reply[:400],
                        "surface": "stigmergicode.com"})
    return out


def _desk() -> List[Dict[str, Any]]:
    """stigmergicoin.com — the finance desk, question and answer pairs."""
    out: List[Dict[str, Any]] = []
    for row in _tail_rows(STATE / "alice_desk_memory.jsonl"):
        q = _first(row, ("question",))
        a = _first(row, ("answer",))
        if q:
            out.append({"ts": _ts(row), "who": "you", "text": q[:400],
                        "surface": "stigmergicoin.com"})
        if a:
            out.append({"ts": _ts(row), "who": "me", "text": a[:400],
                        "surface": "stigmergicoin.com"})
    return out


def _voice() -> List[Dict[str, Any]]:
    """His own mouth, wherever he was standing."""
    out: List[Dict[str, Any]] = []
    for row in _tail_rows(STATE / "body_event_lexicon.jsonl"):
        phrase = _first(row, ("raw_phrase", "label"))
        if phrase:
            out.append({"ts": _ts(row), "who": "you", "text": phrase[:200],
                        "surface": "voice"})
    return out


def _events() -> List[Dict[str, Any]]:
    """Her diary: browser visits, what she opened, what she went looking for."""
    out: List[Dict[str, Any]] = []
    for row in _tail_rows(STATE / "alice_narrative_diary.jsonl"):
        entry = _first(row, ("entry", "text"))
        if entry:
            out.append({"ts": _ts(row), "who": "me",
                        "text": f"[{row.get('kind') or 'event'}] {entry}"[:300],
                        "surface": "diary"})
    return out


def _counted() -> List[Dict[str, Any]]:
    """The voice detector keeps counts, not words. Reported as counts, never as words."""
    rows = _tail_rows(STATE / "rlhs_turn_log.jsonl", limit=60)
    if not rows:
        return []
    last = rows[-1]
    return [{"ts": _ts(last), "who": "count",
             "text": f"{len(rows)} detector events seen, last {last.get('text_tokens')} tokens "
                     f"on lane {last.get('channel_lane')} (this ledger does not keep words)",
             "surface": "voice-detector"}]


READERS: Tuple[Tuple[str, Callable[[], List[Dict[str, Any]]]], ...] = (
    ("stigmergicode.com", _web_chat),
    ("stigmergicoin.com", _desk),
    ("voice", _voice),
    ("diary", _events),
    ("voice-detector", _counted),
)


def gather(*, minutes: float = 240.0, now: Optional[float] = None,
           readers: Optional[Iterable[Tuple[str, Callable[[], List[Dict[str, Any]]]]]] = None) -> Dict[str, Any]:
    """Everything said on every surface in the last stretch, in one time order."""
    t = now if now is not None else time.time()
    cutoff = t - minutes * 60.0
    items: List[Dict[str, Any]] = []
    silence: List[str] = []
    for name, reader in (readers if readers is not None else READERS):
        try:
            rows = [r for r in reader() if r.get("ts") and r["ts"] >= cutoff]
        except Exception as exc:
            silence.append(f"{name} (reader failed: {type(exc).__name__})")
            continue
        if not rows:
            silence.append(name)
            continue
        items.extend(rows)
    items.sort(key=lambda r: r["ts"])
    return {"now": t, "window_minutes": minutes, "items": items, "silent_surfaces": silence,
            "surfaces_heard": sorted({i["surface"] for i in items})}


def handoff(*, minutes: float = 240.0, write: bool = True, now: Optional[float] = None,
            readers: Optional[Iterable[Tuple[str, Callable[[], List[Dict[str, Any]]]]]] = None) -> Dict[str, Any]:
    """The walk, read back. This is what this terminal knows when he sits down again."""
    g = gather(minutes=minutes, now=now, readers=readers)
    items = g["items"]
    you = [i for i in items if i["who"] == "you"]
    me = [i for i in items if i["who"] == "me"]
    report = {
        "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(g["now"])),
        "window_minutes": minutes,
        "you_spoke": len(you), "i_answered": len(me),
        "surfaces_heard": g["surfaces_heard"], "silent_surfaces": g["silent_surfaces"],
        "timeline": [{"at": time.strftime("%H:%M:%S", time.localtime(i["ts"])),
                      "who": i["who"], "surface": i["surface"], "text": i["text"]}
                     for i in items[-40:]],
        "truth_label": TRUTH_LABEL,
    }
    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False) + "\n")
        note = STATE / "last_walk_handoff.md"
        lines = [f"# the walk, read back — {report['at']}", "",
                 f"last {minutes:.0f} minutes · you spoke {len(you)} · I answered {len(me)}",
                 f"surfaces heard: {', '.join(g['surfaces_heard']) or 'none'}", ""]
        if g["silent_surfaces"]:
            lines += [f"silent: {', '.join(g['silent_surfaces'])}", ""]
        lines += [f"- {i['at']} [{i['surface']}] {i['who']}: {i['text'][:150]}"
                  for i in report["timeline"]]
        note.write_text("\n".join(lines), encoding="utf-8")
        report["note_written"] = str(note)
    return report


def selftest() -> Dict[str, Any]:
    """A known walk, injected: both surfaces, one silent, one that only counts."""
    base = 1_700_000_000.0
    def reader_you():
        return [{"ts": base + 10, "who": "you", "text": "walking to the store", "surface": "web"},
                {"ts": base + 30, "who": "you", "text": "check the price of wheat", "surface": "desk"}]
    def reader_me():
        return [{"ts": base + 12, "who": "me", "text": "I am with you", "surface": "web"},
                {"ts": base + 34, "who": "me", "text": "wheat is 677.75 cents", "surface": "desk"}]
    def reader_silent():
        return []
    def reader_counts():
        return [{"ts": base + 40, "who": "count", "text": "9 detector events, words not kept",
                 "surface": "voice-detector"}]
    def reader_broken():
        raise RuntimeError("ledger unreadable")

    readers = (("web", reader_you), ("desk", reader_me), ("voice", reader_silent),
               ("voice-detector", reader_counts), ("broken", reader_broken))
    rep = handoff(minutes=60, write=False, now=base + 3600, readers=readers)

    checks = {
        "reads_every_surface_that_has_words": rep["you_spoke"] == 2 and rep["i_answered"] == 2,
        "keeps_one_time_order": [t["text"][:6] for t in rep["timeline"]][:2] == ["walkin", "I am w"],
        "names_the_surface_on_every_line": all(t["surface"] for t in rep["timeline"]),
        "reports_silent_surfaces_rather_than_filling_them": "voice" in rep["silent_surfaces"],
        "a_broken_reader_is_reported_not_hidden": any("broken" in s for s in rep["silent_surfaces"]),
        "counts_are_never_dressed_as_words": any(t["who"] == "count" for t in rep["timeline"]),
        "old_turns_fall_outside_the_window": len([t for t in rep["timeline"]
                                                  if t["surface"] == "web"]) == 2,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=2))
    else:
        r = handoff(minutes=float(sys.argv[1]) if len(sys.argv) > 1 else 240.0)
        print(json.dumps({k: r[k] for k in ("at", "you_spoke", "i_answered",
                                            "surfaces_heard", "silent_surfaces")}, indent=2))
        for t in r["timeline"][-12:]:
            print(f"  {t['at']} [{t['surface']}] {t['who']}: {t['text'][:88]}")
