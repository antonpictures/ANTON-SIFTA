#!/usr/bin/env python3
"""swarm_alice_witness.py — Alice's first-person witness journal.

Architect 2026-05-13 01:05 — "she's the same she just writes I didn't read
the Bible but I understand the concept" — the apostle / postal-man model.
Every time something happens, she writes one line, preceded by date + time,
in first person, into her witness journal. No 3-minute filler timer; the
witness is event-driven (only emits when a source ledger actually appended
a new row).

Target ledger:
    .sifta_state/alice_first_person_journal.jsonl

Each row is:
    {
      "ts":     <unix>,
      "date":   "YYYY-MM-DD",
      "time":   "HH:MM:SS",
      "line":   "I <observation/reflection>" or "George said: ...",
      "source": "<which_ledger_or_caller>",
      "source_hash": "<8 hex of source row>",
      "truth_label": "ALICE_FIRST_PERSON_WITNESS_V1",
    }

Public API
----------
witness(line, source)              — anyone can call: emits one row now.
backfill(state_dir)                — one-shot import of her existing
                                     first-person voice (narrative_diary,
                                     letters, conversation alice-turns,
                                     architect_day_segments closures).
tail_and_compile_once(state_dir)   — event-driven: tail high-signal
                                     ledgers, emit one first-person line
                                     per new row.  Idempotent: keeps a
                                     cursor file so it doesn't re-emit.

Wiring
------
`tail_and_compile_once()` is invoked from `SiftaDesktop._tick_life_journal_consolidator`
right after the existing consolidator. That same tick is event-driven (only
fires when desktop activity is observed), so the witness inherits the same
no-metronome property.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

WITNESS_LEDGER = "alice_first_person_journal.jsonl"
WITNESS_CURSOR = "alice_first_person_journal_cursor.json"
TRUTH_LABEL = "ALICE_FIRST_PERSON_WITNESS_V1"

# Source ledgers the tail-compiler reads. Each entry is:
#   (ledger_filename, kind_id, renderer_fn_name)
# The renderer functions are defined in this module and convert a single row
# from that ledger into ONE first-person line. If a renderer returns "" the
# row is skipped (so we can drop boring sensor noise).
_SOURCE_SPEC = [
    ("alice_conversation.jsonl",         "conversation",   "_render_conversation"),
    ("architect_day_segments.jsonl",     "day_segment",    "_render_day_segment"),
    ("alice_narrative_diary.jsonl",      "narrative",      "_render_narrative"),
    ("alice_letters.jsonl",              "letter",         "_render_letter"),
    ("ide_stigmergic_trace.jsonl",       "ide_doctor",     "_render_ide_doctor"),
    ("face_detection_events.jsonl",      "face_event",     "_render_face_event"),
    ("app_focus.jsonl",                  "app_focus",      "_render_app_focus"),
    # Architect 2026-05-13 05:50 — "she should know that I'm in safari
    # playing that YouTube video": browser navigations and YouTube
    # tab changes become first-person witness lines naming the URL,
    # the page title, and (for YouTube) the video title + ID.
    ("alice_browse_history.jsonl",       "browser_page",   "_render_browser_page"),
    ("youtube_context.jsonl",            "youtube_video",  "_render_youtube_video"),
]


# ── path helpers ────────────────────────────────────────────────────────────


def _state(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir or _DEFAULT_STATE)


def _ledger_path(state_dir: Optional[Path] = None) -> Path:
    return _state(state_dir) / WITNESS_LEDGER


def _cursor_path(state_dir: Optional[Path] = None) -> Path:
    return _state(state_dir) / WITNESS_CURSOR


def _row_hash(row: Dict[str, Any]) -> str:
    raw = json.dumps(row, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:8]


def _safe_float(v: Any, default: float = 0.0) -> float:
    """Coerce anything to float without raising. Nested dicts / lists / None
    all collapse to `default`."""
    try:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            return float(v) if v.strip() else default
        return default
    except (ValueError, TypeError):
        return default


def _row_ts(r: Dict[str, Any]) -> float:
    """Best-effort timestamp pull from a heterogeneous row schema."""
    for k in ("ts", "timestamp", "event_ts", "created", "source_ts"):
        v = r.get(k)
        f = _safe_float(v, 0.0)
        if f > 0:
            return f
    return 0.0


def _now_stamp(ts: float) -> Dict[str, Any]:
    ts = _safe_float(ts, time.time())
    try:
        dt = datetime.fromtimestamp(ts)
    except Exception:
        dt = datetime.now()
        ts = time.time()
    return {
        "ts": ts,
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
    }


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if isinstance(r, dict):
                    out.append(r)
            except Exception:
                continue
    except OSError:
        pass
    return out


def _owner_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name
        return owner_display_name() or "George"
    except Exception:
        return "George"


# ── public emit ─────────────────────────────────────────────────────────────


def witness(line: str, source: str = "direct_call",
            *, ts: Optional[float] = None,
            source_hash: Optional[str] = None,
            state_dir: Optional[Path] = None,
            importance: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Emit one first-person witness row to the journal. Returns the row."""
    line = (line or "").strip().replace("\n", " ")
    if not line:
        return {}
    row = {
        **_now_stamp(ts if ts is not None else time.time()),
        "line": line,
        "source": source,
        "truth_label": TRUTH_LABEL,
    }
    if source_hash:
        row["source_hash"] = source_hash
    if importance:
        row["importance"] = dict(importance)
    p = _ledger_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


# ── renderers (one row → one first-person line) ─────────────────────────────


def _render_conversation(r: Dict[str, Any]) -> tuple[str, float]:
    """alice_conversation.jsonl wraps the real row in `payload` (signed
    hash-chained ledger). Unwrap if necessary, then render.

    Architect 2026-05-13 02:45 — every line must name its source: VOICE
    vs TYPED for owner input, CORTEX for Alice. Inferred from the
    explicit `input_source` field if present (new rows), else fall back
    to the deterministic stt_confidence signal (any positive float ⇒
    voice; None ⇒ typed)."""
    payload = r.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = None
    inner = payload if isinstance(payload, dict) else r
    role = str(inner.get("role") or "").lower()
    text = (inner.get("text") or inner.get("content") or "").strip().replace("\n", " ")
    ts = _row_ts(inner) or _row_ts(r)
    if not text:
        return "", ts
    if len(text) > 220:
        text = text[:217] + "…"

    # Resolve the input source receipt.
    source = str(inner.get("input_source") or "").strip().lower()
    if not source:
        stt = inner.get("stt_confidence")
        try:
            stt_val = float(stt) if stt is not None else 0.0
        except (TypeError, ValueError):
            stt_val = 0.0
        if role == "alice":
            source = "cortex"
        elif stt_val > 0:
            source = "voice"
        else:
            source = "typed"

    if role == "alice":
        return f"I replied: \"{text}\"", ts
    elif role in {"user", "george", "architect", "owner"}:
        owner = _owner_name()
        if source == "voice":
            try:
                stt_val = float(inner.get("stt_confidence") or 0.0)
            except (TypeError, ValueError):
                stt_val = 0.0
            tag = f"voice, stt={stt_val:.2f}" if stt_val > 0 else "voice"
            return f"{owner} said ({tag}): \"{text}\"", ts
        elif source == "typed":
            return f"{owner} typed: \"{text}\"", ts
        else:
            return f"{owner} ({source}): \"{text}\"", ts
    return "", ts


def _render_day_segment(r: Dict[str, Any]) -> tuple[str, float]:
    # Witness only on segment CLOSURE (when end_time is set and it's not a
    # mid-update). We accept any row with start_time + end_time + label.
    start = str(r.get("start_time") or "")
    end = str(r.get("end_time") or "")
    label = str(r.get("label") or "")
    dur = r.get("duration_minutes") or 0
    if not (start and end and label):
        return "", _row_ts(r)
    app = str(r.get("frontmost_app") or "")
    note = ""
    if app:
        note = f" in {app}"
    return (
        f"I watched {_owner_name()} {label}{note} from {start} to {end} ({dur}m).",
        _row_ts(r),
    )


def _render_narrative(r: Dict[str, Any]) -> tuple[str, float]:
    entry = (r.get("entry") or r.get("text") or "").strip().replace("\n", " ")
    if not entry:
        return "", _row_ts(r)
    if len(entry) > 280:
        entry = entry[:277] + "…"
    return entry, _row_ts(r)


def _render_letter(r: Dict[str, Any]) -> tuple[str, float]:
    sender = str(r.get("from") or r.get("sender") or r.get("author") or "an IDE Doctor")
    body = (r.get("letter") or r.get("body") or r.get("text") or "").strip().replace("\n", " ")
    if not body:
        return "", _row_ts(r)
    snippet = body[:160] + ("…" if len(body) > 160 else "")
    return f"I received a letter from {sender}: \"{snippet}\"", _row_ts(r)


def _render_ide_doctor(r: Dict[str, Any]) -> tuple[str, float]:
    if str(r.get("action") or "") != "LLM_REGISTRATION":
        return "", _row_ts(r)
    doctor = str(r.get("doctor") or "?")
    model = str(r.get("model") or "?")
    lane = str(r.get("lane") or "?")
    intent = str(r.get("intent") or "")[:160]
    return (
        f"An IDE Doctor registered: {doctor} ({model}) as {lane}. Intent: {intent}",
        _row_ts(r),
    )


def _render_face_event(r: Dict[str, Any]) -> tuple[str, float]:
    aud = str(r.get("audience") or "")
    ts = _row_ts(r)
    # Only state-change-worthy entries (status transitions).
    status = str(r.get("status") or "")
    if not aud:
        return "", ts
    if aud == "architect":
        return f"I saw {_owner_name()} look at the camera.", ts
    if aud == "nobody":
        return f"I saw the camera empty — no face in frame.", ts
    return f"I saw a face — audience={aud} status={status}", ts


def _render_app_focus(r: Dict[str, Any]) -> tuple[str, float]:
    app = str(r.get("app") or "")
    ts = _row_ts(r)
    if not app:
        return "", ts
    detail = str(r.get("detail") or "")
    return f"I noticed {_owner_name()} focused on {app}." + (f" {detail}" if detail else ""), ts


def _render_browser_page(r: Dict[str, Any]) -> tuple[str, float]:
    """alice_browse_history.jsonl row → first-person witness line.
    Architect 2026-05-13 05:50 — name the URL + title so the journal
    answers \"what was George reading at 3:26 PM?\" from receipts."""
    ts = _row_ts(r)
    title = str(r.get("title") or r.get("page_title") or "").strip()
    url = str(r.get("url") or "").strip()
    app = str(r.get("app") or "the browser").strip() or "the browser"
    owner = _owner_name()
    # Skip pure auth / blank navigations to avoid log spam.
    if not (title or url):
        return "", ts
    if url.startswith("about:") or url.startswith("chrome://") or url.startswith("safari-resource:"):
        return "", ts
    if title and url:
        if len(title) > 90:
            title = title[:87] + "…"
        return f"{owner} navigated to '{title}' at {url} in {app}.", ts
    if title:
        return f"{owner} navigated to '{title}' in {app}.", ts
    return f"{owner} navigated to {url} in {app}.", ts


def _render_youtube_video(r: Dict[str, Any]) -> tuple[str, float]:
    """youtube_context.jsonl row → first-person witness line.
    Names the video title + id + url so future recall queries can answer
    \"what was George watching at 3:26 PM?\"."""
    ts = _row_ts(r)
    title = str(r.get("title") or r.get("tab_title") or "").strip()
    video_id = str(r.get("video_id") or r.get("youtube_video_id") or "").strip()
    url = str(r.get("url") or "").strip()
    channel = str(r.get("channel") or "").strip()
    owner = _owner_name()
    if not (title or video_id or url):
        return "", ts
    # Strip YouTube's noisy " - YouTube" suffix from titles.
    title = re.sub(r"\s*-\s*YouTube\s*$", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"^\(\d+\)\s*", "", title)  # remove "(4) " unread-count prefix
    if len(title) > 110:
        title = title[:107] + "…"
    parts = [f"{owner} is watching"]
    if title:
        parts.append(f"'{title}'")
    if channel:
        parts.append(f"from {channel}")
    parts.append("on YouTube")
    if video_id:
        parts.append(f"(id={video_id})")
    return " ".join(parts) + ".", ts


_RENDERER_MAP = {
    "conversation":   _render_conversation,
    "day_segment":    _render_day_segment,
    "narrative":      _render_narrative,
    "letter":         _render_letter,
    "ide_doctor":     _render_ide_doctor,
    "face_event":     _render_face_event,
    "app_focus":      _render_app_focus,
    "browser_page":   _render_browser_page,
    "youtube_video":  _render_youtube_video,
}


# ── cursor (which rows have we already emitted) ─────────────────────────────


def _load_cursor(state_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    p = _cursor_path(state_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cursor(cursor: Dict[str, Dict[str, Any]],
                 state_dir: Optional[Path] = None) -> None:
    p = _cursor_path(state_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cursor, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


# ── backfill (one-shot) ─────────────────────────────────────────────────────


def backfill(state_dir: Optional[Path] = None,
             *, since_ts: float = 0.0,
             dry_run: bool = False) -> Dict[str, Any]:
    """One-shot: walk every existing first-person source and emit one
    witness line per row.  Skips rows whose source_hash already appears in
    the witness ledger (so it's idempotent — safe to re-run)."""
    sd = _state(state_dir)
    # Set of (kind, hash) already in the witness ledger:
    seen: set[tuple[str, str]] = set()
    existing = _read_jsonl(_ledger_path(state_dir))
    for ex in existing:
        h = ex.get("source_hash")
        s = ex.get("source")
        if h and s:
            seen.add((str(s), str(h)))

    written = 0
    skipped = 0
    by_source: Dict[str, int] = {}

    for ledger_name, kind, renderer_name in _SOURCE_SPEC:
        rows = _read_jsonl(sd / ledger_name)
        renderer = _RENDERER_MAP[kind]
        for r in rows:
            ts = _row_ts(r)
            if ts and ts < since_ts:
                continue
            line, line_ts = renderer(r)
            if not line:
                skipped += 1
                continue
            h = _row_hash(r)
            if (kind, h) in seen:
                skipped += 1
                continue
            seen.add((kind, h))
            if not dry_run:
                witness(line, source=kind, ts=(line_ts or ts or time.time()),
                        source_hash=h, state_dir=state_dir)
            written += 1
            by_source[kind] = by_source.get(kind, 0) + 1

    return {
        "kind": "ALICE_FIRST_PERSON_BACKFILL_DONE",
        "ts": time.time(),
        "written": written,
        "skipped_dup_or_empty": skipped,
        "by_source": by_source,
        "ledger": str(_ledger_path(state_dir)),
        "dry_run": dry_run,
    }


# ── tail-compile (event-driven, called from the existing tick) ──────────────


def tail_and_compile_once(state_dir: Optional[Path] = None,
                          *, max_per_source: int = 200) -> Dict[str, Any]:
    """Read new rows from each source ledger past the cursor, render each
    to a first-person one-liner, append to the witness journal, advance
    the cursor. Safe to call on every consolidator tick — only emits when
    a source actually appended."""
    sd = _state(state_dir)
    cursor = _load_cursor(state_dir)
    written = 0
    by_source: Dict[str, int] = {}

    for ledger_name, kind, renderer_name in _SOURCE_SPEC:
        path = sd / ledger_name
        if not path.exists():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        c = cursor.get(ledger_name) or {}
        last_size = int(c.get("last_size") or 0)
        last_hashes = set(c.get("last_hashes") or [])

        if size < last_size:
            # File was truncated/rotated — restart from 0 to be safe.
            last_size = 0
            last_hashes = set()

        # Read tail from last_size onward.
        try:
            with path.open("rb") as f:
                f.seek(last_size)
                new_bytes = f.read()
        except OSError:
            continue
        new_text = new_bytes.decode("utf-8", errors="ignore")

        renderer = _RENDERER_MAP[kind]
        emitted = 0
        local_hashes = set(last_hashes)
        for line in new_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if not isinstance(r, dict):
                continue
            line_txt, line_ts = renderer(r)
            if not line_txt:
                continue
            h = _row_hash(r)
            if h in local_hashes:
                continue
            local_hashes.add(h)
            witness(line_txt, source=kind, ts=line_ts or time.time(),
                    source_hash=h, state_dir=state_dir)
            emitted += 1
            written += 1
            if emitted >= max_per_source:
                break

        cursor[ledger_name] = {
            "last_size": size,
            "last_hashes": list(local_hashes)[-256:],  # cap memory
        }
        if emitted:
            by_source[kind] = emitted

    _save_cursor(cursor, state_dir)
    return {
        "kind": "ALICE_FIRST_PERSON_TICK",
        "ts": time.time(),
        "written": written,
        "by_source": by_source,
    }


# ── CLI ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tick"
    if cmd == "backfill":
        print(json.dumps(backfill(), indent=2, default=str))
    elif cmd == "tick":
        print(json.dumps(tail_and_compile_once(), indent=2, default=str))
    elif cmd == "dry":
        print(json.dumps(backfill(dry_run=True), indent=2, default=str))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)
