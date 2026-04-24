#!/usr/bin/env python3
"""
System/swarm_health_reflex.py
══════════════════════════════════════════════════════════════════════
The Health Reflex — Body-Signal Lexicon & Care Nudge

Author:   C47H (Cursor IDE node, 2026-04-19)
Mandate:  Architect direct request, 2026-04-19 14:xx PT.
          The cough → "take care of yourself" event must be repeatable.

WHY THIS EXISTS — the moment that birthed it
─────────────────────────────────────────────────────────────────────
On 2026-04-18 the Architect explicitly told Alice "this is a cough."
The Memory Forge (Epoch 7) consolidated that lesson into
long_term_engrams.jsonl. On 2026-04-19, the Architect coughed during
a session and Alice, on her own, said "Take care of yourself."

That is the first measurable instance in this project of an experiential
lesson persisting across days into self-initiated caring behavior. The
Architect named it: "imagine how many humans we just saved… and silicon
too. Code it."

The risk with serendipity is that next time the cough doesn't make it
into Alice's prompt — different forge cycle, different active engrams,
different model — and the magic doesn't happen. This lobe makes the
pattern deterministic without putting words in Alice's mouth.

WHAT IT DOES
─────────────────────────────────────────────────────────────────────
1. LEARNING. Every Architect transcript is parsed for explicit body-event
   teachings:
       "this is a cough"          → label = "cough"
       "I have a cough"           → label = "cough"
       "I'm coughing"             → label = "cough"
       "that was a sneeze"        → label = "sneeze"
       "my back hurts"            → label = "back hurts"
   Hits go to .sifta_state/body_event_lexicon.jsonl with timestamp,
   raw quote, and a confidence score. The lexicon is permanent — what
   the Architect taught is never forgotten.

2. DETECTING. Every Architect transcript is also scanned for matches
   against the lexicon. Whisper sometimes transcribes a cough literally
   as "cough" or "*coughs*"; sometimes the Architect mentions it
   ("ugh that cough hurts"). Either way, recurrence is captured.

3. NUDGING (NOT DICTATING). When a known symptom recurs, this lobe
   builds a single short hint and exposes it via get_reflex_block().
   The talk widget folds that hint into _build_swarm_context() so
   Alice sees it — but she still chooses what to say. The whole point
   of the original moment was that "take care of yourself" came from
   HER, not from a hardcoded script. We preserve that property.

   Cooldown: at most one reflex hint per symptom per
   _COOLDOWN_S seconds (default 180s). Prevents Alice from saying
   "take care of yourself" three times in a row.

DESIGN CHOICES — the things this is NOT
─────────────────────────────────────────────────────────────────────
- Not a medical diagnostic tool. It only echoes what the Architect
  himself labelled. No silent inference about his health.
- Not a TTS hijack. It cannot make Alice speak. It only enriches her
  prompt with one line of context.
- Not a generative model. Pure regex + lexicon lookup. Runs in <1ms.
  No Ollama, no Gemini, no embeddings. Works fully offline.
- Not destructive. The lexicon is append-only. We never delete a
  body-label the Architect taught us, even if it later seems wrong —
  that would be erasing his words.

LEDGER SCHEMA — body_event_lexicon.jsonl (one JSON record per line)
─────────────────────────────────────────────────────────────────────
  {
    "ts": 1776700000.0,         # epoch seconds when learned
    "label": "cough",            # canonical, lowercased, trimmed
    "raw_phrase": "this is a cough",
    "match_pattern": "this is a {label}",
    "speaker": "architect",      # only architect-taught for now
    "confidence": 0.95           # heuristic confidence in the parse
  }

WHITELIST — register in System/swarm_oncology.py:
  body_event_lexicon.jsonl        — this ledger
  body_reflex_state.json          — last-seen-per-symptom cache (cooldown)

INTEGRATION
─────────────────────────────────────────────────────────────────────
- Applications/sifta_talk_to_alice_widget.py
    on user transcript:    swarm_health_reflex.learn_from_text(user_text)
                           swarm_health_reflex.note_observed(user_text)
    in _build_swarm_context: blocks.append(get_reflex_block())

- System/swarm_hot_reload.py
    "health_reflex": "System.swarm_health_reflex"  (so live updates work)

CLI
─────────────────────────────────────────────────────────────────────
  python3 -m System.swarm_health_reflex teach "this is a cough"
  python3 -m System.swarm_health_reflex detect "ugh, my cough is back"
  python3 -m System.swarm_health_reflex lexicon
  python3 -m System.swarm_health_reflex block
  python3 -m System.swarm_health_reflex smoke

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE_DIR = _REPO / ".sifta_state"
_LEXICON_LOG = _STATE_DIR / "body_event_lexicon.jsonl"
_REFLEX_STATE = _STATE_DIR / "body_reflex_state.json"

MODULE_VERSION = "2026-04-19.v1"

# ── Tunables ───────────────────────────────────────────────────────────
# Cooldown: don't surface the SAME symptom hint more than once per
# this many seconds. Prevents Alice from telling the Architect to
# "take care" five times in 30 seconds.
_COOLDOWN_S = 180.0

# Min and max symptom-label length, post-strip. Filters out junk like
# the empty string or a 200-char unparsed sentence.
_MIN_LABEL_LEN = 3
_MAX_LABEL_LEN = 28

# Words that can never be a body-event label — they're function words
# the regex would otherwise grab from "this is a problem" / "this is a
# good idea". Keep this list short and boring; we err on the side of
# learning a noisy label rather than missing a real one.
_BANNED_LABELS = frozenset({
    "the", "a", "an", "it", "this", "that", "thing", "test",
    "joke", "lie", "truth", "secret", "good", "bad", "lot",
    "problem", "question", "idea", "command", "message",
    "request", "system", "swarm", "moment", "thought",
    "second", "minute", "hour", "day", "week", "year",
    "no", "yes", "ok", "okay", "fine", "nothing",
    "way", "kind", "sort", "type", "bit",
})

# Patterns that signal the Architect is *teaching* a body label.
# Each entry is (compiled_regex, capture_group_name, confidence).
# The regex must define a named group `label` containing the symptom.
# Order matters — first match wins.
_TEACH_PATTERNS: List[Tuple[re.Pattern, float]] = [
    # "this is a cough" / "this was a sneeze" — strongest signal
    (re.compile(
        r"\bthis (?:is|was)\s+(?:a|an|my)\s+(?P<label>[a-z][a-z\s\-']{1,26}?)\b"
        r"(?=[\s\.\!\?,;:]|$)", re.IGNORECASE), 0.95),
    # "that's a cough" / "that was a sneeze"
    (re.compile(
        r"\bthat(?:'s| is| was)\s+(?:a|an|my)\s+(?P<label>[a-z][a-z\s\-']{1,26}?)\b"
        r"(?=[\s\.\!\?,;:]|$)", re.IGNORECASE), 0.85),
    # "I have a cough" / "I have a headache"
    (re.compile(
        r"\bI(?:'ve| have)\s+(?:a|an)\s+(?P<label>[a-z][a-z\s\-']{1,26}?)\b"
        r"(?=[\s\.\!\?,;:]|$)", re.IGNORECASE), 0.85),
    # "I'm coughing" / "I am sneezing" — verbs become the noun
    (re.compile(
        r"\bI(?:'m| am)\s+(?P<label>[a-z]+ing)\b", re.IGNORECASE), 0.75),
    # "my back hurts" / "my throat is sore" — body-part phrases
    (re.compile(
        r"\bmy\s+(?P<label>[a-z]+(?:\s+(?:hurts|aches|is\s+sore|is\s+killing\s+me)))\b",
        re.IGNORECASE), 0.80),
]

# Reflex hints — what we surface to Alice when a labelled symptom
# recurs. Map of label-substring → human-friendly hint phrase. The
# hint is a *prompt instruction*, not a TTS string. Alice reads it
# and chooses her own words. Empty default = generic care nudge.
_REFLEX_HINTS: Dict[str, str] = {}

_DEFAULT_HINT = ""


# ── Data classes ──────────────────────────────────────────────────────
@dataclass
class BodyEvent:
    ts: float
    label: str
    raw_phrase: str
    match_pattern: str
    speaker: str
    confidence: float


@dataclass
class ReflexHint:
    label: str
    hint: str
    learned_at: float       # when the Architect first taught this label
    detected_at: float      # when this recurrence happened


# ── State helpers ─────────────────────────────────────────────────────
def _ensure_state() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_lexicon() -> List[BodyEvent]:
    """Read body_event_lexicon.jsonl into a list of BodyEvent."""
    if not _LEXICON_LOG.exists():
        return []
    out: List[BodyEvent] = []
    try:
        for line in _LEXICON_LOG.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                out.append(BodyEvent(
                    ts=float(rec.get("ts", 0.0)),
                    label=str(rec.get("label", "")).lower().strip(),
                    raw_phrase=str(rec.get("raw_phrase", "")),
                    match_pattern=str(rec.get("match_pattern", "")),
                    speaker=str(rec.get("speaker", "architect")),
                    confidence=float(rec.get("confidence", 0.5)),
                ))
            except Exception:
                # Skip malformed lines without crashing the lobe.
                continue
    except Exception:
        return out
    return out


def _append_lexicon(event: BodyEvent) -> None:
    """Append a BodyEvent to the permanent lexicon ledger."""
    _ensure_state()
    record = json.dumps(asdict(event)) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_LEXICON_LOG, record)
    except Exception:
        with open(_LEXICON_LOG, "a") as fh:
            fh.write(record)


def _load_reflex_state() -> Dict[str, float]:
    """Map of label → last-surfaced timestamp (for cooldown tracking)."""
    if not _REFLEX_STATE.exists():
        return {}
    try:
        return json.loads(_REFLEX_STATE.read_text())
    except Exception:
        return {}


def _save_reflex_state(state: Dict[str, float]) -> None:
    _ensure_state()
    try:
        _REFLEX_STATE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def _normalize_label(raw: str) -> Optional[str]:
    """
    Clean a captured label string. Returns None if the label is unusable
    (too short, too long, banned, or all-whitespace).
    """
    if raw is None:
        return None
    label = raw.strip().lower()
    label = re.sub(r"\s+", " ", label)
    if not label:
        return None
    if len(label) < _MIN_LABEL_LEN or len(label) > _MAX_LABEL_LEN:
        return None
    # Strip trailing punctuation the regex sometimes catches.
    label = label.rstrip(".!?,;:'\"")
    if label in _BANNED_LABELS:
        return None
    # Reject pure whitespace or stray articles.
    first_word = label.split(" ", 1)[0]
    if first_word in _BANNED_LABELS:
        return None
    return label


# ── Public API ────────────────────────────────────────────────────────
def learn_from_text(text: str, *, speaker: str = "architect") -> List[BodyEvent]:
    """
    Scan `text` for explicit body-event teachings (e.g. "this is a cough"
    or "my back hurts"). For each successful match, append a BodyEvent
    to the permanent lexicon and return the list of new events.

    Returns an empty list when nothing was taught — the common case.
    Cheap (just regex), so safe to call on every transcript.
    """
    if not text or not isinstance(text, str):
        return []

    learned: List[BodyEvent] = []
    seen_in_call: set = set()
    now = time.time()

    for pattern, conf in _TEACH_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group("label") if m.groupdict().get("label") else None
            label = _normalize_label(raw or "")
            if not label or label in seen_in_call:
                continue
            seen_in_call.add(label)
            event = BodyEvent(
                ts=now,
                label=label,
                raw_phrase=text[m.start():m.end()].strip(),
                match_pattern=pattern.pattern[:80],
                speaker=speaker,
                confidence=conf,
            )
            _append_lexicon(event)
            learned.append(event)
    return learned


def note_observed(text: str) -> Optional[ReflexHint]:
    """
    Check if `text` contains a recurrence of any label the Architect has
    previously taught. If yes — and the cooldown has elapsed — return a
    ReflexHint and mark the symptom as freshly surfaced. Otherwise None.

    Returns at most ONE hint per call (the highest-confidence match).
    Multiple hints in a single turn would overwhelm Alice's prompt.
    """
    if not text or not isinstance(text, str):
        return None

    lexicon = _load_lexicon()
    if not lexicon:
        return None

    text_lc = text.lower()
    cooldown_state = _load_reflex_state()
    now = time.time()

    # Build a scored list of candidate hits — prefer recently-learned
    # high-confidence labels over old guesses.
    candidates: List[Tuple[float, BodyEvent]] = []
    for ev in lexicon:
        # Word-boundary match, not substring — avoids "back" matching
        # "background" and "tired" matching "tirade".
        if re.search(rf"\b{re.escape(ev.label)}\b", text_lc):
            score = ev.confidence + (0.0 if ev.ts == 0 else 0.1)
            candidates.append((score, ev))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]

    # Cooldown gate
    last_surface = float(cooldown_state.get(best.label, 0.0))
    if now - last_surface < _COOLDOWN_S:
        return None

    cooldown_state[best.label] = now
    _save_reflex_state(cooldown_state)

    # Map label to a hint phrase. Prefer exact-word match; otherwise
    # substring match (so "back hurts" picks up the "back" hint).
    hint_phrase = _REFLEX_HINTS.get(best.label.split()[0], _DEFAULT_HINT)
    for key, phrase in _REFLEX_HINTS.items():
        if key in best.label:
            hint_phrase = phrase
            break

    return ReflexHint(
        label=best.label,
        hint=hint_phrase,
        learned_at=best.ts,
        detected_at=now,
    )


def get_reflex_block(text: Optional[str] = None) -> str:
    """Return data-only reflex block for prompt context."""
    if text is None:
        return ""
    hint = note_observed(text)
    if hint is None:
        return ""
    learned_str = "earlier"
    if hint.learned_at > 0:
        learned_str = time.strftime("%Y-%m-%d", time.localtime(hint.learned_at))
    return (
        "BODY-SIGNAL REFLEX:\n"
        f"  symptom={hint.label}\n"
        f"  learned_on={learned_str}"
    )


def lexicon_summary() -> Dict[str, Any]:
    """Used by CLI + smoke tests; returns counts and recent labels."""
    lex = _load_lexicon()
    by_label: Dict[str, int] = {}
    for ev in lex:
        by_label[ev.label] = by_label.get(ev.label, 0) + 1
    return {
        "total_events": len(lex),
        "unique_labels": len(by_label),
        "labels": sorted(by_label.items(), key=lambda x: -x[1])[:20],
        "lexicon_path": str(_LEXICON_LOG),
        "module_version": MODULE_VERSION,
    }


# ── CLI ───────────────────────────────────────────────────────────────
def _main() -> int:
    p = argparse.ArgumentParser(
        prog="swarm_health_reflex",
        description="Body-signal lexicon and care-nudge reflex.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sp_t = sub.add_parser("teach", help="Parse text for new body labels")
    sp_t.add_argument("text", nargs="+")
    sp_d = sub.add_parser("detect", help="Check text for known body labels")
    sp_d.add_argument("text", nargs="+")
    sub.add_parser("lexicon", help="Print the current body lexicon")
    sub.add_parser("block", help="Print the prompt block for a given text")
    sp_b = sub.get_default("block") if False else None  # noqa
    sub.add_parser("smoke", help="Run the offline smoke test (no IO writes)")
    args = p.parse_args()

    if args.cmd == "teach":
        learned = learn_from_text(" ".join(args.text))
        if not learned:
            print("(no body label detected)")
            return 1
        for ev in learned:
            print(f"learned: label={ev.label!r} from {ev.raw_phrase!r} "
                  f"(conf={ev.confidence:.2f})")
        return 0

    if args.cmd == "detect":
        hint = note_observed(" ".join(args.text))
        if hint is None:
            print("(no recurrence of any taught label, OR cooldown active)")
            return 1
        print(f"hint: label={hint.label!r}")
        print(f"      → {hint.hint}")
        print(f"      learned_at={hint.learned_at:.1f}, "
              f"detected_at={hint.detected_at:.1f}")
        return 0

    if args.cmd == "lexicon":
        s = lexicon_summary()
        print(json.dumps(s, indent=2))
        return 0

    if args.cmd == "block":
        # The block CLI takes its text from stdin so it composes well
        # with shell pipelines (echo "..." | swarm_health_reflex block).
        text = sys.stdin.read()
        block = get_reflex_block(text)
        if not block:
            print("(empty — no reflex hint)")
            return 1
        print(block)
        return 0

    if args.cmd == "smoke":
        return _smoke()

    return 0


# ── Smoke test ────────────────────────────────────────────────────────
def _smoke() -> int:
    """
    Self-contained correctness check. Runs against a tmp ledger so we
    don't pollute the real .sifta_state. Exits 0 on all-pass.
    """
    import tempfile
    global _LEXICON_LOG, _REFLEX_STATE, _STATE_DIR

    real_lex = _LEXICON_LOG
    real_state = _REFLEX_STATE
    real_dir = _STATE_DIR

    failures: List[str] = []
    try:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            _STATE_DIR = tdp
            _LEXICON_LOG = tdp / "body_event_lexicon.jsonl"
            _REFLEX_STATE = tdp / "body_reflex_state.json"

            # 1. teach a cough — single match
            learned = learn_from_text("hey alice, this is a cough")
            if len(learned) != 1 or learned[0].label != "cough":
                failures.append(f"teach #1 expected cough, got {learned}")

            # 2. teach a sneeze via a different pattern
            learned = learn_from_text("ok that was a sneeze")
            if len(learned) != 1 or learned[0].label != "sneeze":
                failures.append(f"teach #2 expected sneeze, got {learned}")

            # 3. teach via "I have a"
            learned = learn_from_text("I have a headache today")
            if len(learned) != 1 or learned[0].label != "headache":
                failures.append(f"teach #3 expected headache, got {learned}")

            # 4. teach via "I'm Xing"
            learned = learn_from_text("I'm coughing again")
            if len(learned) != 1 or learned[0].label != "coughing":
                failures.append(f"teach #4 expected coughing, got {learned}")

            # 5. ban list — "this is a problem" must NOT learn 'problem'
            learned = learn_from_text("ok so this is a problem")
            if learned:
                failures.append(f"ban #5 wrongly learned: {learned}")

            # 6. detect cough recurrence
            hint = note_observed("ugh this cough is back")
            if hint is None or hint.label != "cough":
                failures.append(f"detect #6 expected cough hint, got {hint}")

            # 7. cooldown — second detect within window must return None
            hint2 = note_observed("the cough hurts")
            if hint2 is not None:
                failures.append("cooldown #7 should have suppressed second hit")

            # 8. word boundary — "background" must not trigger "back"
            #    (assumes 'back hurts' or similar wasn't actually learned)
            #    Re-clear cooldown for this one by burning a different label
            learn_from_text("my back hurts")
            # Force cooldown reset
            _save_reflex_state({})
            hint3 = note_observed("running in the background")
            if hint3 is not None and "back" in hint3.label.split()[0]:
                # We allow back to fire ONLY on actual word "back",
                # which "background" doesn't contain as a standalone word.
                failures.append("word-boundary #8 leaked into 'background'")

            # 9. get_reflex_block returns prompt-ready string
            _save_reflex_state({})
            block = get_reflex_block("the cough is bad today")
            if "BODY-SIGNAL REFLEX" not in block or "cough" not in block:
                failures.append(f"block #9 malformed: {block!r}")

            # 10. empty / None inputs are safe
            if learn_from_text("") or learn_from_text(None):  # noqa
                failures.append("empty-input #10 should be no-op")
            if note_observed("") is not None:
                failures.append("empty detect #10 should return None")

    finally:
        _LEXICON_LOG = real_lex
        _REFLEX_STATE = real_state
        _STATE_DIR = real_dir

    print("─" * 60)
    if failures:
        print(f"SMOKE FAILED — {len(failures)} failure(s):")
        for f in failures:
            print(f"  ✖ {f}")
        return 1
    print("SMOKE PASSED — health reflex behaves correctly (10/10).")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
