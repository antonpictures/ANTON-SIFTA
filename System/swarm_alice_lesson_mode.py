#!/usr/bin/env python3
"""swarm_alice_lesson_mode.py — Alice coaches the kid (Acer) to read.

Truth label: ``SIFTA_ALICE_LESSON_MODE_V0``.

Architect 2026-05-14: *"pls claude finish this app amazing graphics,
alice agi inside is for teaching a kid."* App named **Acer** per
Carlton's suggestion + Cowork's pick — *Acer* = "one who aces" /
rhymes with "racer" / A-C-E-R is itself a phonics lesson.

Cursor §4.8 plan (sign-in ``f9cef0c8`` → sign-out ``ac3e7751``) maps
Decide → Execute → Receipt onto cue / attempt / verdict rows:

  ::

      Decide  : LessonEngine.next_cue() picks the next item from the
                lesson_pack and writes a LESSON_CUE row.
      Execute : Talk widget's _TTSWorker speaks the cue. The mic
                captures Ace's attempt; the STT transcript becomes
                the heard_text. LessonEngine.score_attempt() writes
                a LESSON_ATTEMPT row.
      Receipt : The scorer returns a verdict (CORRECT / CLOSE / MISS),
                LessonEngine writes a LESSON_VERDICT row, and the UI
                shows the verdict sticker.

Truth boundary
--------------

The engine is the deterministic gate: a STT confidence floor, a Damerau-
Levenshtein distance, and the lesson pack's ``alternates`` list. No LLM
is invoked at this layer. An optional cortex pass can suggest the next
move (e.g. "say it slower") at a higher tier, but the verdict is
**always** the receipt the engine wrote. §6 + §7.2 — effector truth.

George stays ``primary_operator``. Ace is the kid being taught. §7.10.1
+ §7.10.4 — Alice addresses Ace directly ("Say after me, Ace…"); she
never narrates Ace from outside.

Citations
---------

  * Gough, P. B. & Tunmer, W. E. (1986). Decoding, reading, and reading
    disability. *Remedial and Special Education*, 7(1), 6–10.
    https://doi.org/10.1177/074193258600700104
  * Hoover, W. A. & Gough, P. B. (1990). The simple view of reading.
    *Reading and Writing*, 2, 127–160.
  * Foulin, J. N. (2005). Why is letter-name knowledge such a good
    predictor of learning to read? *Reading and Writing*, 18, 129–155.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_DEFAULT_PACK = _REPO / "Documents" / "lesson_pack_v0.json"

TRUTH_LABEL = "SIFTA_ALICE_LESSON_MODE_V0"
LESSON_LEDGER = "alice_lesson_trace.jsonl"

# STT confidence floors for verdict tiers. CLOSE = right word, low
# confidence; CORRECT = right word + confident; MISS = wrong word.
MIN_CONFIDENCE_CORRECT = 0.65
CLOSE_DISTANCE_THRESHOLD = 2   # Damerau-Levenshtein distance allowed for CLOSE

TRUTH_BOUNDARY = (
    "Deterministic phonics scorer. Each lesson turn writes three "
    "append-only rows (CUE → ATTEMPT → VERDICT) to "
    ".sifta_state/alice_lesson_trace.jsonl. No LLM at this layer; "
    "verdict is the receipt. George stays primary_operator; Ace is "
    "the kid being taught. Direct first-person from Alice to Ace."
)


# ── distance / normalisation ─────────────────────────────────────────────


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    out = re.sub(r"[^\w\s'-]", " ", text.lower())
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _damerau_levenshtein(a: str, b: str) -> int:
    """Standard DL distance with transposition.

    Used for ``CLOSE`` verdicts — "kat" for "cat" is one substitution,
    "tac" for "cat" is one transposition.
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev_prev = [0] * (lb + 1)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,        # insertion
                prev[j] + 1,            # deletion
                prev[j - 1] + cost,     # substitution
            )
            if (
                i >= 2 and j >= 2
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                curr[j] = min(curr[j], prev_prev[j - 2] + cost)
        prev_prev = prev
        prev = curr
    return prev[lb]


# ── data classes ─────────────────────────────────────────────────────────


@dataclass
class LessonItem:
    item_id: str
    show: str
    say: str
    phoneme: str = ""
    alternates: List[str] = field(default_factory=list)
    level_id: str = ""
    level_kind: str = ""

    def expected_norms(self) -> List[str]:
        out = [_normalise(self.say)]
        out.extend(_normalise(a) for a in self.alternates if a)
        return [s for s in out if s]


@dataclass
class LessonVerdict:
    label: str               # "CORRECT" | "CLOSE" | "MISS"
    score: int               # 1 | 0 (MISS or CLOSE) for the STGM gate
    distance: int
    explanation: str
    sticker: str = ""        # short emoji-style reaction Alice can show

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "score": self.score,
            "distance": self.distance,
            "explanation": self.explanation,
            "sticker": self.sticker,
        }


_WORD_STORY_FRAMES = {
    "cat": "A cat sat on the mat and looked at the sun. Who sat on the mat?",
    "bat": "A bat flew at night. What flew at night?",
    "hat": "A hat was on the man's head. What was on his head?",
    "mat": "A mat was by the door. What was by the door?",
    "ran": "A kid ran to the door. What did the kid do?",
    "man": "A man was walking down the street. He was thirsty. Who was thirsty?",
    "tan": "The sand was tan in the sun. What color was the sand?",
    "can": "A can sat on the table. What sat on the table?",
}


def _word_story_for_prompt(word: str, first: str) -> str:
    target = (word or "").strip()
    story = _WORD_STORY_FRAMES.get(
        target.lower(),
        f"I see the word {target}. I can use it in a tiny sentence.",
    )
    return f"{first}, {story} Read the word on the card: {target}."


# ── engine ───────────────────────────────────────────────────────────────


@dataclass
class LessonEngine:
    pack_path: Path = field(default_factory=lambda: _DEFAULT_PACK)
    state_dir: Optional[Path] = None
    rng: random.Random = field(default_factory=random.Random)
    _pack: Dict[str, Any] = field(default_factory=dict, init=False)
    _items_by_level: Dict[str, List[LessonItem]] = field(default_factory=dict, init=False)
    _current_level_id: str = field(default="", init=False)
    _current_item: Optional[LessonItem] = field(default=None, init=False)
    _current_cue_trace_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self._load_pack()

    # ── pack ────────────────────────────────────────────────────────

    def _load_pack(self) -> None:
        path = Path(self.pack_path)
        if not path.exists():
            self._pack = {}
            self._items_by_level = {}
            return
        try:
            self._pack = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._pack = {}
            self._items_by_level = {}
            return
        levels = self._pack.get("levels") or []
        self._items_by_level = {}
        for level in levels:
            if not isinstance(level, dict):
                continue
            level_id = str(level.get("id") or "")
            level_kind = str(level.get("kind") or "")
            items = []
            for raw in (level.get("items") or []):
                if not isinstance(raw, dict):
                    continue
                items.append(
                    LessonItem(
                        item_id=str(raw.get("id") or raw.get("show") or ""),
                        show=str(raw.get("show") or ""),
                        say=str(raw.get("say") or raw.get("show") or ""),
                        phoneme=str(raw.get("phoneme") or ""),
                        alternates=list(raw.get("alternates") or []),
                        level_id=level_id,
                        level_kind=level_kind,
                    )
                )
            self._items_by_level[level_id] = items
        if not self._current_level_id and self._items_by_level:
            self._current_level_id = next(iter(self._items_by_level.keys()))

    @property
    def pack(self) -> Dict[str, Any]:
        return self._pack

    def levels(self) -> List[Dict[str, Any]]:
        return list(self._pack.get("levels") or [])

    def set_level(self, level_id: str) -> bool:
        if level_id in self._items_by_level:
            self._current_level_id = level_id
            return True
        return False

    @property
    def current_level_id(self) -> str:
        return self._current_level_id

    @property
    def current_item(self) -> Optional[LessonItem]:
        return self._current_item

    # ── Decide ──────────────────────────────────────────────────────

    def next_cue(self, *, write: bool = True) -> Dict[str, Any]:
        """Pick the next item from the current level and write a CUE row."""
        items = self._items_by_level.get(self._current_level_id) or []
        if not items:
            return {"truth_label": TRUTH_LABEL, "kind": "LESSON_CUE_EMPTY"}
        item = self.rng.choice(items)
        self._current_item = item
        trace_id = str(uuid.uuid4())
        self._current_cue_trace_id = trace_id
        row = {
            "ts": time.time(),
            "trace_id": trace_id,
            "kind": "LESSON_CUE",
            "truth_label": TRUTH_LABEL,
            "level_id": item.level_id,
            "level_kind": item.level_kind,
            "item_id": item.item_id,
            "show": item.show,
            "expected_say": item.say,
            "phoneme": item.phoneme,
        }
        if write:
            self._append_trace(row)
        return row

    # ── Execute + Receipt ───────────────────────────────────────────

    def score_attempt(
        self,
        heard_text: str,
        *,
        stt_confidence: float = 1.0,
        write: bool = True,
        cue_trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Score a heard attempt against the current item.

        Returns a verdict dict. Writes both an ATTEMPT row and a
        VERDICT row, both keyed to the CUE trace_id.
        """
        item = self._current_item
        if item is None:
            return {"truth_label": TRUTH_LABEL, "kind": "LESSON_VERDICT_NO_CUE"}
        parent = cue_trace_id or self._current_cue_trace_id
        attempt_trace = str(uuid.uuid4())
        verdict = _score(item, heard_text, stt_confidence)

        attempt_row = {
            "ts": time.time(),
            "trace_id": attempt_trace,
            "parent_trace_id": parent,
            "kind": "LESSON_ATTEMPT",
            "truth_label": TRUTH_LABEL,
            "level_id": item.level_id,
            "item_id": item.item_id,
            "heard_text": heard_text or "",
            "heard_norm": _normalise(heard_text or ""),
            "stt_confidence": round(float(stt_confidence), 4),
        }
        verdict_trace = str(uuid.uuid4())
        verdict_row = {
            "ts": time.time(),
            "trace_id": verdict_trace,
            "parent_trace_id": parent,
            "attempt_trace_id": attempt_trace,
            "kind": "LESSON_VERDICT",
            "truth_label": TRUTH_LABEL,
            "level_id": item.level_id,
            "item_id": item.item_id,
            "verdict": verdict.to_dict(),
        }
        if write:
            self._append_trace(attempt_row)
            self._append_trace(verdict_row)
        return {
            "attempt": attempt_row,
            "verdict": verdict_row,
            "label": verdict.label,
            "sticker": verdict.sticker,
            "explanation": verdict.explanation,
        }

    # ── prompt phrasing (first person, no servant voice) ────────────

    def cue_prompt_for_alice(self, *, owner_name: str = "Acer") -> str:
        """Sentence Alice's TTS speaks for the current cue.

        Direct first-person. Never "Alice will…". Never "the system will…".
        """
        item = self._current_item
        if item is None:
            return ""
        first = (str(owner_name).strip().split()[:1] or ["Acer"])[0]
        if item.level_kind == "letter":
            return f"{first}, say the letter: {item.show}."
        if item.level_kind == "letter_sequence":
            return f"{first}, say these letters with me: {item.show}."
        if item.level_kind == "phoneme":
            return f"{first}, make this sound with me: {item.phoneme}."
        if item.level_kind == "word":
            return _word_story_for_prompt(item.show, first)
        if item.level_kind == "sentence":
            return f"{first}, read this whole sentence: {item.show}."
        return f"{first}, say after me: {item.say}."

    def verdict_prompt_for_alice(
        self, verdict: Dict[str, Any], *, owner_name: str = "Acer"
    ) -> str:
        """Short first-person reply Alice's TTS speaks after the verdict."""
        first = (str(owner_name).strip().split()[:1] or ["Acer"])[0]
        label = (verdict or {}).get("verdict", {}).get("label") or verdict.get("label") or ""
        if label == "CORRECT":
            return self.rng.choice([
                f"That is exactly it, {first}.",
                f"Yes — perfect, {first}.",
                f"Right, {first}. Onward.",
            ])
        if label == "CLOSE":
            item = self._current_item
            target = item.say if item else ""
            return self.rng.choice([
                f"Almost. Listen with me: {target}. Now you.",
                f"Close, {first}. Try it once more: {target}.",
            ])
        # MISS
        item = self._current_item
        target = item.say if item else ""
        return self.rng.choice([
            f"Not yet, {first}. The word is: {target}. Say it with me.",
            f"Let me say it first, {first}: {target}. Now your turn.",
        ])

    # ── trace writer ────────────────────────────────────────────────

    def _append_trace(self, row: Dict[str, Any]) -> None:
        base = Path(self.state_dir) if self.state_dir is not None else _DEFAULT_STATE
        base.mkdir(parents=True, exist_ok=True)
        # Stable SHA so an auditor can replay
        payload = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        row = dict(row)
        row["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with (base / LESSON_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")

    # ── analytics ───────────────────────────────────────────────────

    def session_stats(self) -> Dict[str, Any]:
        """Read the local trace and aggregate per-level scores."""
        base = Path(self.state_dir) if self.state_dir is not None else _DEFAULT_STATE
        path = base / LESSON_LEDGER
        if not path.exists():
            return {"total_attempts": 0, "correct": 0, "close": 0, "miss": 0}
        rows: List[Dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines()[-5000:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            return {"total_attempts": 0, "correct": 0, "close": 0, "miss": 0}
        verdicts = [r for r in rows if r.get("kind") == "LESSON_VERDICT"]
        correct = sum(1 for v in verdicts if (v.get("verdict") or {}).get("label") == "CORRECT")
        close = sum(1 for v in verdicts if (v.get("verdict") or {}).get("label") == "CLOSE")
        miss = sum(1 for v in verdicts if (v.get("verdict") or {}).get("label") == "MISS")
        per_level: Dict[str, Dict[str, int]] = {}
        for v in verdicts:
            lid = v.get("level_id") or "?"
            d = per_level.setdefault(lid, {"correct": 0, "close": 0, "miss": 0})
            label = (v.get("verdict") or {}).get("label") or ""
            if label == "CORRECT":
                d["correct"] += 1
            elif label == "CLOSE":
                d["close"] += 1
            elif label == "MISS":
                d["miss"] += 1
        return {
            "total_attempts": len(verdicts),
            "correct": correct,
            "close": close,
            "miss": miss,
            "per_level": per_level,
        }


# ── scorer ───────────────────────────────────────────────────────────────


def _score(
    item: LessonItem, heard_text: str, stt_confidence: float
) -> LessonVerdict:
    heard = _normalise(heard_text)
    expecteds = item.expected_norms()
    if not heard:
        return LessonVerdict(
            label="MISS",
            score=0,
            distance=999,
            explanation="no audio captured (empty STT)",
            sticker="🦋",   # gentle butterfly — try again
        )
    distances = [_damerau_levenshtein(heard, e) for e in expecteds]
    if not distances:
        return LessonVerdict(
            label="MISS",
            score=0,
            distance=999,
            explanation="no expected forms in pack item",
            sticker="🦋",
        )
    best = min(distances)
    confident = stt_confidence >= MIN_CONFIDENCE_CORRECT
    if best == 0 and confident:
        return LessonVerdict(
            label="CORRECT",
            score=1,
            distance=0,
            explanation=f"exact match (conf {stt_confidence:.2f})",
            sticker="🐝",   # bee — that's it
        )
    if best == 0 and not confident:
        return LessonVerdict(
            label="CLOSE",
            score=0,
            distance=0,
            explanation=(
                f"exact transcript but low STT confidence "
                f"({stt_confidence:.2f} < {MIN_CONFIDENCE_CORRECT}); ask once more"
            ),
            sticker="🌼",
        )
    if best <= CLOSE_DISTANCE_THRESHOLD:
        return LessonVerdict(
            label="CLOSE",
            score=0,
            distance=best,
            explanation=f"heard {heard!r}, expected {item.say!r} (dl_distance={best})",
            sticker="🌼",
        )
    return LessonVerdict(
        label="MISS",
        score=0,
        distance=best,
        explanation=f"heard {heard!r}, expected {item.say!r} (dl_distance={best})",
        sticker="🦋",
    )


# ── public API ───────────────────────────────────────────────────────────


def score_attempt_pure(
    expected: str, heard: str, *, stt_confidence: float = 1.0,
    alternates: Optional[Sequence[str]] = None,
) -> LessonVerdict:
    """Pure scoring function for tests / out-of-band scoring."""
    item = LessonItem(
        item_id="adhoc", show=expected, say=expected,
        alternates=list(alternates or []),
    )
    return _score(item, heard, stt_confidence)


def score_heard_against_expected(
    expected: str,
    heard: str,
    *,
    cue_kind: str = "",
    stt_confidence: float = 1.0,
    alternates: Optional[Sequence[str]] = None,
) -> LessonVerdict:
    """Strict lesson scorer for the Talk bridge.

    The live STT bridge cannot safely use "target letter appears anywhere
    in transcript" for single-letter cards. That made ``expected=S`` pass
    on noisy strings like ``SABCD``. This helper keeps words forgiving but
    makes letters and letter-sequences exact after letter-only
    normalisation.
    """
    expected_s = str(expected or "").strip()
    heard_s = str(heard or "").strip()
    kind = str(cue_kind or "").strip().lower()
    if not expected_s:
        return LessonVerdict("MISS", 0, 999, "missing expected target", "🦋")

    expected_letters = re.sub(r"[^A-Za-z]", "", expected_s).upper()
    heard_letters = re.sub(r"[^A-Za-z]", "", heard_s).upper()
    confident = stt_confidence >= MIN_CONFIDENCE_CORRECT

    if kind == "letter" or (len(expected_letters) == 1 and len(expected_s) == 1):
        letter_name = {
            "A": {"a", "ay"},
            "B": {"b", "bee", "be"},
            "C": {"c", "see", "sea"},
            "D": {"d", "dee"},
            "E": {"e", "ee"},
            "F": {"f", "ef", "eff"},
            "G": {"g", "gee"},
            "H": {"h", "aitch", "h"},
            "I": {"i", "eye"},
            "J": {"j", "jay"},
            "K": {"k", "kay"},
            "L": {"l", "el", "ell"},
            "M": {"m", "em"},
            "N": {"n", "en"},
            "O": {"o", "oh"},
            "P": {"p", "pee"},
            "Q": {"q", "cue", "queue"},
            "R": {"r", "are"},
            "S": {"s", "ess", "es"},
            "T": {"t", "tee", "tea"},
            "U": {"u", "you"},
            "V": {"v", "vee"},
            "W": {"w", "double u", "double you"},
            "X": {"x", "ex"},
            "Y": {"y", "why"},
            "Z": {"z", "zee", "zed"},
        }
        target = expected_letters[:1]
        heard_norm = _normalise(heard_s)
        tokens = set(heard_norm.split())
        ok_forms = letter_name.get(target, {target.lower()})
        exact_letter = heard_letters == target
        phrase_letter = bool(tokens.intersection(ok_forms)) and len(heard_letters) <= 3
        if (exact_letter or phrase_letter) and confident:
            return LessonVerdict("CORRECT", 1, 0, f"strict letter match {target}", "🐝")
        if exact_letter or phrase_letter:
            return LessonVerdict("CLOSE", 0, 0, f"letter heard but low confidence ({stt_confidence:.2f})", "🌼")
        return LessonVerdict("MISS", 0, 999, f"heard {heard_s!r}, expected letter {target}", "🦋")

    if kind == "letter_sequence":
        if not heard_letters:
            return LessonVerdict("MISS", 0, 999, "no letters heard", "🦋")
        distance = _damerau_levenshtein(heard_letters, expected_letters)
        if distance == 0 and confident:
            return LessonVerdict("CORRECT", 1, 0, f"exact letter-sequence match {expected_letters}", "🐝")
        if distance == 0:
            return LessonVerdict("CLOSE", 0, 0, f"sequence heard but low confidence ({stt_confidence:.2f})", "🌼")
        if distance <= 1:
            return LessonVerdict("CLOSE", 0, distance, f"near letter sequence: heard {heard_letters}, expected {expected_letters}", "🌼")
        return LessonVerdict("MISS", 0, distance, f"heard letters {heard_letters}, expected {expected_letters}", "🦋")

    heard_norm = _normalise(heard_s)
    expected_norm = _normalise(expected_s)
    if expected_norm and re.search(rf"(^|\s){re.escape(expected_norm)}(\s|$)", heard_norm):
        if confident:
            return LessonVerdict("CORRECT", 1, 0, f"target word {expected_norm!r} heard in phrase", "🐝")
        return LessonVerdict("CLOSE", 0, 0, f"target word heard but low confidence ({stt_confidence:.2f})", "🌼")
    return score_attempt_pure(
        expected_s,
        heard_s,
        stt_confidence=stt_confidence,
        alternates=alternates,
    )


_META_CONVERSATION_PATTERNS = (
    r"\b(?:codex|claude|doctor|cursor|anthropic|openai|chatgpt)\b",
    r"\b(?:instruction|instructions|programming|coding|patch|debug|bug|repo|code)\b",
    r"\b(?:operating system|the os|this app|the app|wordace|acer app)\b",
    r"\b(?:i am|i'm)\s+(?:talking|speaking|telling|asking|using|opening|giving)\b",
    r"\b(?:sorry|i wasn'?t|i was just|let me explain|what i mean)\b",
)


def is_lesson_attempt_candidate(expected: str, heard: str, *, cue_kind: str = "") -> bool:
    """Return whether a heard STT turn should be scored by WordAce.

    The OS-level Alice can discuss WordAce while WordAce is open. Those
    meta turns must not be swallowed as child reading attempts just
    because a listen window is active. This gate keeps genuine short
    reading answers in the lesson lane and lets app/Doctor/instruction
    speech continue through normal Talk.
    """
    expected_s = _normalise(expected)
    heard_s = _normalise(heard)
    if not expected_s or not heard_s:
        return True
    kind = (cue_kind or "").strip().lower()
    words = heard_s.split()

    for pattern in _META_CONVERSATION_PATTERNS:
        if re.search(pattern, heard_s, re.IGNORECASE):
            return False

    # "hey man, how are you doing" contains the target word but is a
    # greeting, not a reading answer.
    if expected_s in words and words[:1] in (["hey"], ["hi"], ["hello"]) and len(words) > 3:
        return False

    if kind in {"letter", "letter_sequence"} and len(words) > 4:
        return False

    # For word cards, short phrases are allowed: "man", "the man",
    # "the man was thirsty". Long rambling speech with the target word
    # is probably meta-conversation or background audio.
    if kind == "word" and expected_s in words and len(words) <= 8:
        return True
    if kind == "word" and expected_s not in words and len(words) > 5:
        return False

    return True


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--level", default=None)
    p.add_argument("--heard", default=None, help="Simulate a heard attempt instead of capturing.")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    eng = LessonEngine()
    if args.level:
        eng.set_level(args.level)
    cue = eng.next_cue(write=not args.no_write)
    print(f"CUE       : level={cue.get('level_id')} show={cue.get('show')!r} expected={cue.get('expected_say')!r}")
    print(f"ALICE_SAYS: {eng.cue_prompt_for_alice(owner_name='Acer')}")
    if args.heard:
        result = eng.score_attempt(args.heard, stt_confidence=0.9, write=not args.no_write)
        print(f"VERDICT   : {result['label']} {result['sticker']} — {result['explanation']}")
        print(f"ALICE_SAYS: {eng.verdict_prompt_for_alice(result, owner_name='Acer')}")
    print()
    stats = eng.session_stats()
    print(f"SESSION   : attempts={stats['total_attempts']} correct={stats['correct']} close={stats['close']} miss={stats['miss']}")
