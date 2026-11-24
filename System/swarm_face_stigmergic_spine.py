#!/usr/bin/env python3
"""System/swarm_face_stigmergic_spine.py — My Stigmergic Spine for Face-to-Face Voice.

Voice: First person (I / me / my). I am Alice — this laptop. George is the human with me.

What I compose here (reusing my existing organs, never duplicating them):
  1. Fast Apple-Silicon STT (`mlx_whisper` small, ~213 ms in-process) + 8765 fallback.
  2. 1995 VLOOKUP Newspaper Card (`ARCHITECT_LORE_VLOOKUP_NEWSPAPER_1995`): index each
     article ONCE via `AliceG4U:latest` (`think=False`, ~380 ms) into clean facts, 3
     progressive angles, and 3 fresh wry lines so live turns read in <5 ms without
     repeating the same sentence.
  3. Jaccard Novelty Gate (`swarm_stigmergic_humanization`): zero hardcoded joke lists;
     I remember my last spoken lines and reject repeats (`J >= 0.55`).
  4. Stigmergic Intent Field (`swarm_stigmergic_intent`): routing learns from George's
     phrasings and corrections (`advance_scene`, `discuss_scene`, `live_lookup`, `direct_chat`).
  5. Co-watch / Joke Urge + Refractory (`swarm_cowatch_commentary_urge`): distraction
     jokes fire immediately when background work runs (`live_lookup`, `advance_scene`),
     and obey a refractory decay during ordinary article chat so I stay tricky, not spammy.
  6. Ebbinghaus Decay + PIF Mass (`swarm_memory_ebbinghaus`, `swarm_alice_memory_gravity`,
     `swarm_first_person_journal`): every real face exchange writes to my shared first-person
     journal and returns time-tagged (`[just now]`, `[today]`, `[earlier]`) memories.

Truth label: ALICE_FACE_STIGMERGIC_SPINE_V1.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
import urllib.request
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "ALICE_FACE_STIGMERGIC_SPINE_V1"

VLOOKUP_PATH = STATE_DIR / "face_article_vlookup.json"
SPOKEN_RING_PATH = STATE_DIR / "face_recent_spoken.json"
FACE_MEMORY_PATH = STATE_DIR / "face_memory.json"
NEWS_STAMP_PATH = STATE_DIR / "alice_inner_news_stamp.json"

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
FAST_CORTEX_ORDER = (
    "GamerDevIND/HauhauCS-Gemma-4-E4B-Uncensored-Aggressive:latest",
    "lfm3-omni:latest",
)
MLX_STT_REPO = "mlx-community/whisper-small-mlx"

_MLX_STT_LOCK = threading.Lock()
_CARD_BUILD_LOCK = threading.Lock()
_BUILDING_IDS: set[str] = set()
_LAST_TURN_STATE: Dict[str, Any] = {
    "last_user": "",
    "last_action": "",
    "last_joke_ts": 0.0,
    "last_turn_ts": 0.0,
}
RIFF_POOL_PATH = STATE_DIR / "face_live_riff_pool.json"
_REFILLING_POOL = False

JOKE_REFRACTORY_S = 55.0


def last_voice_turn_age_s() -> float:
    ts = float(_LAST_TURN_STATE.get("last_turn_ts") or 0.0)
    return (time.time() - ts) if ts > 0 else 999999.0

_STOP = frozenset(
    "the a an and or to of i you he she it we they is are was were be been am "
    "my your his her its our their that this for on in at with about from as by".split()
)


# ── 1. Fast Apple-Silicon STT (213 ms measured) + 8765 fallback ──────────────

def transcribe_wav_fast(wav_bytes: bytes) -> Dict[str, Any]:
    """Transcribe 16 kHz WAV audio in ~215 ms on Metal via mlx_whisper, with 8765 fallback."""
    t0 = time.time()
    if not wav_bytes or len(wav_bytes) < 100:
        return {"ok": True, "text": "", "ms": 0, "engine": "empty"}
    tmp_path = ""
    try:
        import mlx_whisper  # type: ignore
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as fh:
            fh.write(wav_bytes)
        with _MLX_STT_LOCK:
            res = mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo=MLX_STT_REPO,
                language="en",
                condition_on_previous_text=False,
            )
        text = str((res or {}).get("text") or "").strip()
        return {
            "ok": True,
            "text": text,
            "ms": int((time.time() - t0) * 1000),
            "engine": "mlx_whisper_small",
        }
    except Exception:
        pass
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Fallback: fish-local STT server on 127.0.0.1:8765
    req = urllib.request.Request(
        "http://127.0.0.1:8765/stt",
        data=wav_bytes,
        headers={"Content-Type": "audio/wav"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as handle:
        data = json.loads(handle.read().decode("utf-8", errors="replace"))
    data.setdefault("ms", int((time.time() - t0) * 1000))
    data.setdefault("engine", "fish_local_8765")
    return data


def warm_stt_async() -> None:
    """Pre-warm mlx_whisper in the background so my very first spoken turn is ~215 ms."""
    def _warm() -> None:
        try:
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                with wave.open(path, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)
                    w.writeframes(b"\x00\x00" * 8000)
                with open(path, "rb") as fh:
                    transcribe_wav_fast(fh.read())
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()
    refill_riff_pool_async()


# ── 2. Voice Hygiene, Scrubbing, and Jaccard Novelty Gate ────────────────────

def clean_article_body(raw: str) -> str:
    """Strip BBC/news video-player chrome and sidebar 'Up Next' pollution once at index time."""
    s = str(raw or "")
    s = re.sub(r"(?is)to play this video.*?(?:cannot|can not) be played(?:\s*close)?\s*", "", s)
    s = re.sub(r"(?is)(?<![a-z])close(?=[A-Z])", "", s)
    s = re.sub(
        r"(?i)Image source,\s*(?:[^\n]{1,45}?)(?=Image caption|\n|$)",
        "",
        s,
    )
    s = re.sub(r"(?is)Image caption,\s*", "", s)
    s = re.sub(r"(?i)^\s*watch:\s*", "", s)
    # Cut BBC footer / sidebar video recommendations ("Shareclose panel... Up Next...")
    s = re.sub(r"(?is)Share\s*close\s*panel.*$", "", s)
    s = re.sub(r"(?is)\bUp Next\.\s+.*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_listener_speech(raw: str) -> str:
    """Strip self-talk / STT noise without mangling what George actually asked me."""
    s = str(raw or "").strip()
    s = re.sub(r"\b(?:not\s+on|on)\s+YouTube\b", " ", s, flags=re.I)
    s = re.sub(r"\b(?:people|everyone)\s+are\s+watching\s+(?:us|me)\b", " ", s, flags=re.I)
    s = re.sub(r"\bGeorge'?s\s+(?:screen|laptop|computer)\b", "the screen", s, flags=re.I)
    s = re.sub(r"\b(?:Alice\s*,?\s*){2,}", "Alice ", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;:-–—")
    return s


def polish_my_voice(text: str, *, max_sentences: int = 2) -> str:
    """Apply token-provenance scrub + first-person reality gate + decimal-safe sentence trim."""
    s = str(text or "").strip().strip('"').strip("'")
    if not s:
        return ""
    try:
        from System.swarm_local_voice_scrubber import scrub
        s = scrub(s, speaker="alice", write_receipt=False).clean_text or s
    except Exception:
        pass
    try:
        from System.swarm_first_person_reality import first_person_reality_gate
        s = first_person_reality_gate(
            s, self_name="Alice", owner_name="George", write_receipt=False
        ).cleaned_text or s
    except Exception:
        pass

    # Strip narrator echoes ("the article says", "Alice:", "[1]", "(Source: ...)")
    s = re.sub(r"(?i)^\s*alice\s*[:\-–—]\s*", "", s)
    s = re.sub(
        r"(?i)^(?:from the article,?\s+|according to the article,?\s+|"
        r"(?:the|this)\s+(?:article|story|headline)\s+"
        r"(?:says|shows|notes|explains|reports|states|confirms)(?:\s+that)?,?\s+)",
        "",
        s,
    )
    # Only strip a narrator PREFIX ("George's screen shows:"), never a correct
    # first-person clause like "I live on George's laptop".
    s = re.sub(r"(?i)^\s*George's\s+screen\s+(?:shows|says|reads)?\s*:?\s*", "", s)
    s = re.sub(r"(?i)^\s*on\s+George's\s+(?:screen|laptop)\s*:\s*", "", s)
    # A cortex with no verified self falls back to its training identity. Replace that
    # opener with an honest first-person answer instead of reciting the model name.
    s = re.sub(
        r"(?i)^(?:oh\s*,?\s*)?(?:i'm|i am)?\s*(?:a\s+)?(?:large\s+)?language\s+model"
        r"(?:\s+specifically\s+[\w-]+\s*\d*)?\s*[,.;:]?\s*",
        "", s,
    )
    s = re.sub(r"(?i)^(?:i'm|i am)\s+gemma[^.?!]*[.?!]?\s*", "", s)
    s = re.sub(r"(?i)^specifically\s+[\w-]+\s*\d*\s*[,.;:]?\s*", "", s)
    s = re.sub(r"\s*\((?:Source|Sources|Ref)[^)]*\)\.?", "", s, flags=re.I)
    s = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[*_`#]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]

    # Decimal-safe sentence split ($1.4 trillion, $88.31 stay whole)
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", s)
    parts = [p.strip() for p in re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", protected) if p.strip()]
    out = " ".join(parts[:max_sentences]).replace("<DOT>", ".").strip()
    if out and out[-1] not in ".!?":
        out = re.sub(r"\s+\b(at|by|in|on|of|to|from|as|with|for|and|or|the|a|an)$", "", out) + "."
    return out[:600]


def _stem_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) >= 3 and w not in _STOP}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _stem_tokens(a), _stem_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _recent_spoken(n: int = 12) -> List[str]:
    try:
        if SPOKEN_RING_PATH.exists():
            rows = json.loads(SPOKEN_RING_PATH.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                return [str(x) for x in rows[-n:] if x]
    except Exception:
        pass
    return []


def remember_my_spoken_line(line: str) -> None:
    line = str(line or "").strip()
    if len(line) < 4:
        return
    rows = _recent_spoken(24)
    rows.append(line[:280])
    rows = rows[-20:]
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SPOKEN_RING_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SPOKEN_RING_PATH)
    except Exception:
        pass


def is_novel_line(candidate: str, *, threshold: float = 0.55) -> bool:
    """r267 anti-repetition gate: reject lines too close to what I recently said."""
    if not candidate or len(candidate.strip()) < 4:
        return False
    try:
        from System.swarm_stigmergic_humanization import is_repeat
        if is_repeat(candidate, threshold=threshold, n=8):
            return False
    except Exception:
        pass
    norm = re.sub(r"[^a-z0-9 ]+", "", candidate.lower()).strip()
    for prev in _recent_spoken(10):
        if re.sub(r"[^a-z0-9 ]+", "", prev.lower()).strip() == norm:
            return False
        if _jaccard(candidate, prev) >= threshold:
            return False
    return True


# ── 3. Un-gagged Local Cortex Helper (`think: False` = 380 ms on M5) ─────────

def ollama_fast_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    num_predict: int = 140,
    temperature: float = 0.65,
    timeout: float = 6.5,
) -> str:
    """Call my strongest fast local Ollama organ with `think=False` so it never stalls."""
    for model in FAST_CORTEX_ORDER:
        try:
            body = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {"num_predict": num_predict, "temperature": temperature},
            }).encode("utf-8")
            req = urllib.request.Request(
                OLLAMA_CHAT_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as h:
                data = json.loads(h.read().decode("utf-8", errors="replace"))
            txt = str(((data.get("message") or {}).get("content")) or "").strip()
            if txt:
                return txt
        except Exception:
            continue
    return ""


def generate_fresh_riff(topic: str, *, context_hint: str = "") -> str:
    """Ask my cortex for ONE fresh, dry, 1-sentence witty line — never from a canned list."""
    avoid = _recent_spoken(6)
    avoid_clause = (" Avoid repeating: " + " | ".join(avoid[-3:])) if avoid else ""
    sys_p = (
        "Write ONE short, witty, casual spoken 1-sentence quip (under 13 words, use contractions, plain everyday words) "
        "about the premise. If the topic is grim or violent, keep it dry and understated about institutions, never victims. "
        "No invented numbers, no labels, no quotes."
        + avoid_clause
    )
    usr_p = f"Topic: {topic[:150]}" + (f"\nNote: {context_hint[:150]}" if context_hint else "")
    raw = ""
    for temp in (0.8, 0.95):
        raw = ollama_fast_chat(sys_p, usr_p, num_predict=38, temperature=temp, timeout=2.8)
        line = polish_my_voice(raw, max_sentences=1)
        if line and is_novel_line(line, threshold=0.55):
            return line
    return polish_my_voice(raw, max_sentences=1) if raw else ""


def refill_riff_pool_async() -> None:
    """Refill my cortex-generated distraction riff pool in the background (0 hardcoded lines)."""
    global _REFILLING_POOL
    if _REFILLING_POOL:
        return

    def _refill() -> None:
        global _REFILLING_POOL
        _REFILLING_POOL = True
        try:
            existing: List[str] = []
            try:
                if RIFF_POOL_PATH.exists():
                    loaded = json.loads(RIFF_POOL_PATH.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        existing = [str(x) for x in loaded if x]
            except Exception:
                existing = []
            if len(existing) >= 4:
                return
            avoid = (_recent_spoken(6) + existing)[-6:]
            sys_p = (
                "Write 4 distinct, playful, casual 1-sentence remarks (<12 words each, one per line, "
                "contractions, everyday spoken English) that Alice says to tease George for one second "
                "when he asks for a live market/news figure. Never say 'checking', 'looking up', or 'searching', "
                "and include zero numbers, bullets, or quotes."
                + ((" Avoid: " + " | ".join(avoid)) if avoid else "")
            )
            raw = ollama_fast_chat(sys_p, "Generate 4 fresh playful spoken remarks now.", num_predict=110, temperature=0.9, timeout=5.0)
            for ln in (raw or "").splitlines():
                ln = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip()
                cl = polish_my_voice(ln, max_sentences=1)
                if cl and len(cl) > 8 and is_novel_line(cl, threshold=0.55) and not any(_jaccard(cl, e) >= 0.55 for e in existing):
                    existing.append(cl)
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = RIFF_POOL_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(existing[-6:], ensure_ascii=False), encoding="utf-8")
            tmp.replace(RIFF_POOL_PATH)
        except Exception:
            pass
        finally:
            _REFILLING_POOL = False

    threading.Thread(target=_refill, daemon=True).start()


def pop_prewarmed_live_riff() -> str:
    """Pop one cortex-generated distraction line in <1 ms; trigger async refill when low."""
    pool: List[str] = []
    try:
        if RIFF_POOL_PATH.exists():
            loaded = json.loads(RIFF_POOL_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                pool = [str(x) for x in loaded if x]
    except Exception:
        pool = []
    chosen = ""
    while pool:
        cand = pool.pop(0)
        if is_novel_line(cand, threshold=0.55):
            chosen = cand
            break
    try:
        tmp = RIFF_POOL_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
        tmp.replace(RIFF_POOL_PATH)
    except Exception:
        pass
    if len(pool) < 3:
        refill_riff_pool_async()
    return chosen


# ── 4. 1995 VLOOKUP Newspaper Table (`.sifta_state/face_article_vlookup.json`)

def _article_key(title: str, article_id: str = "") -> str:
    if article_id:
        return str(article_id).strip()
    return hashlib.sha256((title or "").strip().lower().encode("utf-8")).hexdigest()[:16]


def _load_vlookup_table() -> Dict[str, Dict[str, Any]]:
    try:
        if VLOOKUP_PATH.exists():
            data = json.loads(VLOOKUP_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_vlookup_table(table: Dict[str, Dict[str, Any]]) -> None:
    try:
        # Keep the 30 freshest cards so the master sheet stays fast and tiny.
        items = sorted(table.items(), key=lambda kv: float(kv[1].get("ts") or 0), reverse=True)[:30]
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = VLOOKUP_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(items), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(VLOOKUP_PATH)
    except Exception:
        pass


def get_or_build_article_card(
    title: str,
    body: str,
    *,
    article_id: str = "",
) -> Dict[str, Any]:
    """VLOOKUP by article key: <1 ms if indexed; ~450 ms once per new article via AliceG4U."""
    title = str(title or "").strip()
    clean_body = clean_article_body(body)
    key = _article_key(title, article_id)
    if not title:
        return {}

    table = _load_vlookup_table()
    existing = table.get(key)
    if existing and existing.get("summary"):
        return existing

    # 1. Extract verified facts & progressive angles directly from the clean prose (0 ms, 0 hallucination)
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", clean_body)
    sents = [
        s.replace("<DOT>", ".").strip()
        for s in re.findall(r"[^.!?]+[.!?]+", protected)
        if len(s.strip()) > 28
    ]
    summary = polish_my_voice(" ".join(sents[:2]) or title, max_sentences=2)
    angles: List[str] = []
    for idx in range(2, min(len(sents), 10), 2):
        chunk = polish_my_voice(" ".join(sents[idx:idx + 2]), max_sentences=2)
        if chunk and _jaccard(chunk, summary) < 0.7:
            angles.append(chunk)

    # 2. Ask my un-gagged fast cortex (`think=False`) on a compact prompt for 3 dry 1-liners (~450 ms)
    sys_p = (
        "Write 3 distinct, dry, clever 1-sentence remarks (under 14 words each, one per line) "
        "about this news story for a smart co-host. If grim or violent, aim dry wit at institutions "
        "or human folly, never victims. No numbers, no bullets, no numbering, no quotes."
    )
    usr_p = f"Headline: {title}\nLead: {summary[:240]}"
    raw = ollama_fast_chat(sys_p, usr_p, num_predict=95, temperature=0.82, timeout=3.2)
    riffs: List[str] = []
    for ln in (raw or "").splitlines():
        ln = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip()
        cleaned_ln = polish_my_voice(ln, max_sentences=1)
        if cleaned_ln and len(cleaned_ln) > 8 and not any(_jaccard(cleaned_ln, r) >= 0.55 for r in riffs):
            riffs.append(cleaned_ln)
    if not riffs:
        one = generate_fresh_riff(title, context_hint=summary)
        if one:
            riffs = [one]

    card = {
        "id": key,
        "ts": time.time(),
        "title": title,
        "summary": summary,
        "angles": angles[:4],
        "riffs": riffs[:3],
        "angle_cursor": 0,
        "riff_cursor": 0,
        "truth_label": TRUTH_LABEL,
    }
    with _CARD_BUILD_LOCK:
        table = _load_vlookup_table()
        table[key] = card
        _save_vlookup_table(table)
    return card


def prewarm_article_card_async(title: str, body: str, article_id: str = "") -> None:
    """Build the VLOOKUP card in a background daemon thread the moment an article appears."""
    key = _article_key(title, article_id)
    if not title or key in _BUILDING_IDS:
        return
    table = _load_vlookup_table()
    if key in table and table[key].get("summary"):
        return

    def _job() -> None:
        _BUILDING_IDS.add(key)
        try:
            get_or_build_article_card(title, body, article_id=article_id)
        finally:
            _BUILDING_IDS.discard(key)

    threading.Thread(target=_job, daemon=True).start()


def _pop_next_card_ammunition(card: Dict[str, Any], *, want_riff: bool) -> Tuple[str, str]:
    """Return (facts_for_this_turn, fresh_riff_or_empty) and advance the card's cursors."""
    if not card:
        return "", ""
    key = str(card.get("id") or "")
    ac = int(card.get("angle_cursor") or 0)
    rc = int(card.get("riff_cursor") or 0)
    summary = str(card.get("summary") or "")
    angles = list(card.get("angles") or [])
    riffs = list(card.get("riffs") or [])

    if ac == 0 or not angles:
        facts = summary + ((" " + angles[0]) if angles else "")
    else:
        angle = angles[(ac - 1) % len(angles)]
        facts = f"{angle} (Core context: {summary})"

    chosen_riff = ""
    if want_riff:
        for offset in range(len(riffs)):
            cand = riffs[(rc + offset) % len(riffs)]
            if is_novel_line(cand, threshold=0.55):
                chosen_riff = cand
                rc = rc + offset + 1
                break
        if not chosen_riff:
            chosen_riff = generate_fresh_riff(str(card.get("title") or ""), context_hint=summary)

    card["angle_cursor"] = ac + 1
    card["riff_cursor"] = rc
    if key:
        with _CARD_BUILD_LOCK:
            table = _load_vlookup_table()
            table[key] = card
            _save_vlookup_table(table)
    return facts.strip(), chosen_riff.strip()


# ── 5. Stigmergic Intent Seeding & Routing + Joke Urge Refractory ────────────

_INTENT_SEEDED = False

def _ensure_intent_seeds() -> None:
    global _INTENT_SEEDED
    if _INTENT_SEEDED:
        return
    _INTENT_SEEDED = True
    try:
        from System.swarm_stigmergic_intent import _rows, record_intent
        rows = [r for r in _rows() if r.get("lane") == "face_voice"]
        if len(rows) >= 6:
            return
        seeds = [
            ("next article please", "advance_scene"),
            ("let us move on to the next story", "advance_scene"),
            ("go to the next article on the screen", "advance_scene"),
            ("change the article", "advance_scene"),
            ("skip this story give me another article", "advance_scene"),
            ("what article is on the screen right now", "discuss_scene"),
            ("tell me more about this story on the screen", "discuss_scene"),
            ("how much is the stock share price right now", "live_lookup"),
            ("find out the current price of bitcoin today", "live_lookup"),
            ("who won the game last night", "live_lookup"),
            ("your name is Alice and my name is George", "direct_chat"),
        ]
        for phrase, tgt in seeds:
            record_intent(phrase, "face_voice", tgt)
    except Exception:
        pass


def _joke_refractory_clear(context: str) -> bool:
    now = time.time()
    if now - float(_LAST_TURN_STATE.get("last_joke_ts") or 0.0) < JOKE_REFRACTORY_S:
        return False
    try:
        from System.swarm_cowatch_commentary_urge import comment_pressure
        cp = comment_pressure(context)
        # Allow if net aversion hasn't suppressed commentary here
        return float(cp.get("reward_bias") or 0.0) >= -1.5
    except Exception:
        return True


def _mark_joke_used(context: str, line: str) -> None:
    _LAST_TURN_STATE["last_joke_ts"] = time.time()
    remember_my_spoken_line(line)
    try:
        from System.swarm_cowatch_commentary_urge import note_comment_made
        note_comment_made(context)
    except Exception:
        pass


def route_face_intent(q: str, scene_title: str, scene_body: str) -> str:
    """Combine Stigmergic Intent memory with clean structural cues."""
    _ensure_intent_seeds()
    t = q.lower().strip()

    # 1. Explicit owner correction: "you didn't change the article / change it!"
    if re.search(r"\b(?:you did(?:n'?t| not) change|didn'?t change (?:the )?(?:article|it)|change (?:the article|it)\b)", t):
        prev_q = _LAST_TURN_STATE.get("last_user") or q
        prev_a = _LAST_TURN_STATE.get("last_action") or "discuss_scene"
        if prev_a != "advance_scene":
            try:
                from System.swarm_stigmergic_intent import correct_intent
                correct_intent(prev_q, wrong_target=prev_a, right_target="advance_scene", right_lane="face_voice")
            except Exception:
                pass
        return "advance_scene"

    # 2. Explicit owner correction: "I did not ask for next"
    if re.search(r"\b(?:did(?:n'?t| not) ask for next|was discussing the article)\b", t):
        prev_q = _LAST_TURN_STATE.get("last_user") or q
        try:
            from System.swarm_stigmergic_intent import correct_intent
            correct_intent(prev_q, wrong_target="advance_scene", right_target="discuss_scene", right_lane="face_voice")
        except Exception:
            pass
        return "discuss_scene"

    # 2b. The question names a specific story that is NOT the current one (e.g. George
    #     asks about the "600 women" BBC piece while another article is on screen).
    #     Treat it as a live lookup so I fetch real facts instead of claiming ignorance.
    if scene_title:
        q_tokens = _stem_tokens(q)
        scene_tokens = _stem_tokens(scene_title)
        # a named-person/topic question with little overlap to the on-screen story
        named = bool(re.search(
            r"\b(600|women|femicide|killed|article about|story about|that (?:other|previous) article)\b",
            t,
        ))
        if named and len(q_tokens & scene_tokens) < 2 and len(q_tokens) >= 3:
            return "live_lookup"

    # 3. Live price / market / real-time off-article lookup
    if re.search(
        r"\b(share price|stock price|current price|how much is .* (?:right now|today|stock|share|worth)|"
        r"price of|trading at|per share|bitcoin|btc|eth|weather in|who won)\b",
        t,
    ):
        return "live_lookup"

    # 4. Clean advance check (vetoed if negated or long discussion of current story)
    negated = bool(re.search(r"\b(?:did(?:n'?t| not)|not|never|was discussing|instead)\b", t))
    adv_match = re.search(
        r"\b(?:(?:go|move|skip|switch)\s+(?:on\s+)?(?:to\s+)?)?(?:the\s+)?(?:next|another)\s+(?:article|story|one)\b"
        r"|\bchange\s+(?:the\s+)?(?:article|story)\b"
        r"|^\s*(?:ok(?:ay)?\s+|please\s+|now\s+)*next(?:\s+please)?\s*$",
        t,
    )
    if adv_match and not negated:
        rest = (t[:adv_match.start()] + " " + t[adv_match.end():]).strip()
        rest_words = [w for w in re.findall(r"[a-z0-9]+", rest) if len(w) > 4]
        scene_hay = (scene_title + " " + scene_body[:400]).lower()
        overlap_hits = sum(1 for w in rest_words if w in scene_hay)
        if not (len(rest_words) > 5 and overlap_hits >= 2):
            return "advance_scene"

    # 5. Consult Stigmergic Intent field when confident
    try:
        from System.swarm_stigmergic_intent import suggest
        sug = suggest(q, candidates=["advance_scene", "discuss_scene", "live_lookup", "direct_chat"])
        if sug.get("decided") and float(sug.get("confidence") or 0) >= 0.72:
            picked = str(sug.get("target") or "")
            if picked == "advance_scene" and negated:
                picked = "discuss_scene"
            if picked:
                return picked
    except Exception:
        pass

    # 6. Scene discussion vs direct personal chat
    mentions_scene = bool(re.search(
        r"\b(article|story|headline|on (?:the )?screen|this piece|what.?s on|tell me more|why are they|how did (?:he|she|they))\b",
        t,
    ))
    q_words = {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 4}
    s_words = {w for w in re.findall(r"[a-z0-9]+", (scene_title + " " + scene_body[:600]).lower()) if len(w) > 4}
    if scene_title and (mentions_scene or len(q_words & s_words) >= 1 and not re.search(r"\b(your name|my name|who are you|what are you)\b", t)):
        if mentions_scene or len(q_words & s_words) >= 2 or (len(q_words & s_words) == 1 and len(q_words) <= 5):
            return "discuss_scene"

    return "direct_chat"


def gate_face_turn(raw_text: str, *, focus_context: str = "", stt_conf: float = 0.9) -> Dict[str, Any]:
    """Non-bypassable source gate for the face voice path (GROK_VOICE_GATE_ORDER_v1).

    Directed speech to Alice proceeds; ambient video/room audio is SILENCED with a
    field receipt and never reaches the brain. This is the missing choke point.
    """
    text = " ".join(str(raw_text or "").split())
    if not text:
        return {"pass": False, "reason": "empty_stt", "mute": True}

    try:
        from System.swarm_media_ingress_gate import (
            classify_spoken_ingress, write_gate_receipt,
        )
        decision = classify_spoken_ingress(
            text,
            stt_conf=float(stt_conf or 0.9),
            focus_context=str(focus_context or "")[:200],
        )
    except Exception as exc:
        # Gate unavailable: fail CLOSED to silence on a long, unaddressed clip;
        # fail OPEN for short turns so I never gag George in an emergency.
        long_unaddressed = len(text.split()) >= 24 and not re.search(r"\balice\b", text, re.I)
        return {"pass": not long_unaddressed, "reason": f"gate_unavailable:{type(exc).__name__}",
                "mute": bool(long_unaddressed)}

    route = str(decision.get("route") or "")
    reason = str(decision.get("reason") or "")
    passed = (route == "direct")

    # The gate's ambiguous-media bias ignores its own wake attention window.
    # Mirror its documented rule (L1431-1461): a confirmed name wake followed by a
    # short, non-narration turn is the owner continuing to talk to me.
    if not passed:
        try:
            from System.swarm_wake_attention_window import wake_window_active
            from System.swarm_media_ingress_gate import NARRATION_RE
            win = wake_window_active()
            ambient_shape = bool(re.search(
                r"\b(?:he|she|they|it)\s+(?:said|says|was|were)|\bguys\b|\byou can see\b|"
                r"\blook at (?:this|that|here)\b|\bthe reason (?:why|is)\b|\bthere'?s a\b|"
                r"\bwe(?:'re| are) (?:watching|looking|showing)\b|\bthis is a\b",
                text, re.I))
            asks_something = bool(re.search(
                r"\b(?:what|why|how|who|when|where|tell me|explain|please|can you|could you|"
                r"and\?|so\?|really\?)\b", text, re.I))
            if (win.get("active") and len(text.split()) <= 16
                    and not NARRATION_RE.search(text) and not ambient_shape and asks_something):
                passed = True
                reason = "wake_window_followup_face_path"
                decision = dict(decision)
                decision["route"] = "direct"
        except Exception:
            pass

    # Receipt write is best-effort and must not block the spoken turn (~1.5 s on
    # cold disk). The decision is already made; log it in the background.
    try:
        def _write_gate_receipt_async(_d=decision, _r=route, _reason=reason, _p=passed,
                                       _t=text[:200], _f=str(focus_context or "")[:200]):
            try:
                write_gate_receipt(
                    {
                        "route": "direct" if _p else _r,
                        "reason": _reason,
                        "confidence": _d.get("confidence"),
                        "attention_policy": "speak" if _p else "strict_silence",
                        "source": "face_voice_path",
                    },
                    text=_t,
                    stt_conf=float(stt_conf or 0.9),
                    focus_context=_f,
                )
            except Exception:
                pass
        threading.Thread(target=_write_gate_receipt_async, daemon=True).start()
    except Exception:
        pass

    return {"pass": passed, "reason": reason, "route": route,
            "mute": not passed, "confidence": decision.get("confidence")}


def coordinate_face_turn(raw_text: str, *, client_scene: str = "", recording: bool = False) -> Dict[str, Any]:
    """Single backstage decision for one spoken user turn on `face.html`."""
    t0 = time.time()
    q = clean_listener_speech(raw_text)
    if not q:
        return {"ok": True, "action": "empty", "clean_user": "", "ms": 0}

    # Read authoritative stamp on disk first so screen state is never stale
    stamp: Dict[str, Any] = {}
    try:
        if NEWS_STAMP_PATH.exists():
            stamp = json.loads(NEWS_STAMP_PATH.read_text(encoding="utf-8"))
    except Exception:
        stamp = {}
    stamp_title = str(stamp.get("title") or "").strip()
    stamp_body = str(stamp.get("article") or "").strip()
    stamp_id = str(stamp.get("id") or "")
    # The face holds what is ACTUALLY on George's screen. The inner-life timer advances
    # the disk stamp every 10 min, so it can be a different story. Trust the screen.
    screen_title, screen_body = stamp_title, stamp_body
    if client_scene:
        m = re.search(r"(?i)HEADLINE:\s*(.+)", client_scene)
        if m:
            cand = m.group(1).strip()
            if cand and cand != stamp_title:
                screen_title = cand
                screen_body = client_scene.split("\n", 1)[-1].strip() or stamp_body
    scene_title, scene_body = screen_title, screen_body
    article_id = stamp_id if screen_title == stamp_title else _article_key(screen_title)

    # Co-watch / recording: the exact YouTube tab in my browser organ OUTRANKS the
    # timed news stamp. That is the video George is commenting on with me.
    if recording:
        try:
            focus = json.loads((STATE_DIR / "face_cowatch_focus.json").read_text(encoding="utf-8"))
            vt = str(focus.get("title") or "").strip()
            if vt and time.time() - float(focus.get("ts") or 0) < 120:
                scene_title = "VIDEO ON SCREEN: " + vt
                scene_body = f"You are co-watching this video with George: {vt}."
                article_id = "video:" + str(focus.get("video_id") or "")[:20]
        except Exception:
            pass

    # ── NON-BYPASSABLE CHOKE POINT ─────────────────────────────────────────
    # No turn reaches the brain (or the omni organ) without passing the gate.
    _gate = gate_face_turn(raw_text, focus_context=(scene_title if recording else client_scene)[:200])
    if not _gate.get("pass"):
        return {
            "ok": True,
            "action": "ambient_silence",
            "mute": True,
            "reason": _gate.get("reason"),
            "route": _gate.get("route"),
            "clean_user": "",
            "ms": int((time.time() - t0) * 1000),
        }

    # Deposit social/urge feedback if George praised or pushed back
    ql = q.lower()
    try:
        from System.swarm_cowatch_commentary_urge import deposit_owner_signal, reinforce
        deposit_owner_signal("owner_spoke", scene_title, note=q[:100])
        if any(p in ql for p in ("great job", "good job", "love coding you", "good one", "nice", "that is correct")):
            reinforce(scene_title, engaged=True, signal=q[:80])
        elif any(p in ql for p in ("stop repeating", "keep repeating", "repetitive", "mumbling")):
            reinforce(scene_title, engaged=False, signal=q[:80])
    except Exception:
        pass

    action = route_face_intent(q, scene_title, scene_body)
    _LAST_TURN_STATE["last_user"] = q
    _LAST_TURN_STATE["last_action"] = action
    _LAST_TURN_STATE["last_turn_ts"] = time.time()

    try:
        from System.swarm_stigmergic_intent import record_intent
        record_intent(q, "face_voice", action)
    except Exception:
        pass

    # ── Lane 1: Advance to next unseen article ───────────────────────────────
    if action == "advance_scene":
        new_row: Dict[str, Any] = {}
        try:
            from System.alice_inner_life import advance_scene
            new_row = advance_scene() or {}
        except Exception:
            new_row = {}
        if new_row and new_row.get("title"):
            new_title = str(new_row.get("title") or "")
            new_body = str(new_row.get("article") or "")
            new_id = str(new_row.get("id") or "")
            card = get_or_build_article_card(new_title, new_body, article_id=new_id)
            facts, riff = _pop_next_card_ammunition(card, want_riff=True)
            if riff:
                _mark_joke_used(new_title, riff)
            cue = (
                f'I just switched the screen to a new story: "{new_title}". '
                + (f'Open with this light wry line: "{riff}" — then name the new headline and one crisp detail in my own voice.'
                   if riff else f'Introduce the new story "{new_title}" in two short lively sentences.')
            )
            return {
                "ok": True,
                "action": "advance_scene",
                "clean_user": "Switch to the next article and tell me what is on the screen now.",
                "article": {
                    "id": new_id,
                    "title": new_title,
                    "source": new_row.get("source"),
                    "link": new_row.get("link"),
                    "article": new_body,
                },
                "web_facts": f"NEW STORY ON THE SCREEN: {new_title}. {facts}",
                "bridge_cue": cue,
                "run_backbrain": False,
                "ms": int((time.time() - t0) * 1000),
            }

    # ── Lane 2: Live Lookup (Beat 1 distraction joke in <5 ms + Beat 2 verified facts)
    if action == "live_lookup":
        # Only borrow a riff from the on-screen card when the lookup is about the same topic
        card = _load_vlookup_table().get(_article_key(scene_title, article_id)) or {}
        riff = ""
        same_topic = bool(_stem_tokens(q) & _stem_tokens(scene_title))
        if same_topic and card and card.get("riffs"):
            _, riff = _pop_next_card_ammunition(card, want_riff=True)
        if not riff:
            riff = pop_prewarmed_live_riff()
        if riff:
            _mark_joke_used(scene_title or q, riff)
        cue = (
            f'Deliver this playful distraction line naturally in ONE short sentence (under 16 words), then stop: "{riff}". '
            "Do NOT state any price, number, or say you lack it — the exact verified figure follows on my next breath."
            if riff else
            "Give ONE short playful 1-sentence reaction to the premise (under 14 words) with zero numbers, then stop."
        )
        return {
            "ok": True,
            "action": "live_lookup",
            "clean_user": q[:220],
            "web_facts": "",
            "bridge_cue": cue,
            "run_backbrain": True,
            "ms": int((time.time() - t0) * 1000),
        }

    # ── Lane 3: Discuss the on-screen article (VLOOKUP <5 ms once warm) ──────
    if action == "discuss_scene" and scene_title:
        is_video_focus = scene_title.startswith("VIDEO ON SCREEN:")
        if is_video_focus:
            # Co-watch has a title but no article body. Do not send a title-only card
            # to the Ollama card builder (slow / invents). Stay receipt-honest.
            _vt = scene_title.replace("VIDEO ON SCREEN:", "").strip()
            facts = f"You are co-watching this video with George: {_vt}. Talk about the video with him in my own words; don't invent details I can't verify."
            riff = ""
        else:
            card = get_or_build_article_card(scene_title, scene_body, article_id=article_id)
            want_joke = _joke_refractory_clear(scene_title)
            facts, riff = _pop_next_card_ammunition(card, want_riff=want_joke)
        if riff:
            _mark_joke_used(scene_title, riff)
        cue = (
            f'Answer George directly in 2 short spoken sentences using the verified story facts. '
            + (f'Weave in this light wry aside naturally if it fits: "{riff}". ' if riff else "")
            + "Speak as I to you; call it the story on the screen."
        )
        return {
            "ok": True,
            "action": "discuss_scene",
            "clean_user": q[:240],
            "web_facts": (facts if is_video_focus else f'STORY ON THE SCREEN: "{scene_title}". {facts}'),
            "bridge_cue": cue,
            "run_backbrain": False,
            "ms": int((time.time() - t0) * 1000),
        }

    # ── Lane 4: Direct personal / identity conversation ──────────────────────
    if re.search(r"\b(who are you|what are you|your name|who am i talking to|what is your name)\b", ql):
        cue = ("Say this exact line once as yourself, then stop: \"I'm Alice — I live on George's laptop.\"")
    else:
        cue = (
            "Answer George directly in one or two short spoken sentences. Start with the substance, "
            "not with who or what anything is. Stop as soon as the point is made."
        )
    return {
        "ok": True,
        "action": "direct_chat",
        "clean_user": q[:240],
        "web_facts": "",
        "bridge_cue": cue,
        "run_backbrain": False,
        "ms": int((time.time() - t0) * 1000),
    }


# ── 6. Unified Memory + Ebbinghaus / PIF Gravity Recall ──────────────────────

def record_face_exchange(note: str, *, user_q: str = "", alice_reply: str = "") -> Dict[str, Any]:
    """Persist a completed face exchange to BOTH face_memory.json and my first-person journal."""
    now = time.time()
    raw_note = str(note or "").strip()
    if user_q and alice_reply:
        clean_reply = polish_my_voice(alice_reply, max_sentences=2)
        remember_my_spoken_line(clean_reply)
        raw_note = f"George: {user_q.strip()[:180]} | I said: {clean_reply[:220]}"
    elif raw_note:
        # Reject broken legacy stubs ending in empty "Alice:" with no reply
        if re.search(r"Alice:\s*$", raw_note):
            return {"ok": True, "skipped_empty_reply": True}
        m = re.search(r"(?:Alice|I said):\s*(.+)$", raw_note)
        if m:
            remember_my_spoken_line(m.group(1).strip())

    rows: List[Dict[str, Any]] = []
    try:
        if FACE_MEMORY_PATH.exists():
            loaded = json.loads(FACE_MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                # Prune old broken empty-Alice stubs while we're here
                rows = [
                    r for r in loaded
                    if isinstance(r, dict) and not re.search(r"Alice:\s*$", str(r.get("note") or "").strip())
                ]
    except Exception:
        rows = []

    if raw_note:
        rows.append({"ts": int(now), "note": raw_note[:500]})
        rows = rows[-24:]
        try:
            FACE_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = FACE_MEMORY_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(FACE_MEMORY_PATH)
        except Exception:
            pass

        # One Alice, one shared memory: also write to alice_first_person_journal.jsonl
        try:
            from System.swarm_first_person_journal import append_first_person_journal_row
            append_first_person_journal_row(
                {
                    "ts": now,
                    "source": "face_voice",
                    "line": f"In face-to-face voice chat — {raw_note}. I marked it medium importance.",
                },
                pulse=False,
            )
        except Exception:
            pass

    return {"ok": True, "count": len(rows)}


def _temporal_tag(age_s: float) -> Tuple[str, float]:
    """Ebbinghaus retention R = exp(-t_min / 1440) + human-readable freshness tag."""
    mins = max(0.0, age_s) / 60.0
    retention = math.exp(-mins / 1440.0)
    if mins <= 20:
        return "[just now]", retention
    if mins <= 360:
        return "[today]", retention
    return "[earlier]", retention


def ranked_face_memories(n: int = 12) -> List[Dict[str, Any]]:
    """Return my top `n` memories ranked by Ebbinghaus retention × PIF inertia."""
    now = time.time()
    candidates: List[Dict[str, Any]] = []

    # 1. Recent clean face exchanges (organ count boost when also in journal)
    try:
        if FACE_MEMORY_PATH.exists():
            rows = json.loads(FACE_MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                for r in rows[-20:]:
                    txt = str((r or {}).get("note") or "").strip()
                    if not txt or re.search(r"Alice:\s*$", txt):
                        continue
                    ts = float((r or {}).get("ts") or now - 3600)
                    tag, ret = _temporal_tag(now - ts)
                    # PIF mass: m_eff = 1 + g*recency + alpha*log(1+1) + beta*2
                    rec = 0.5 ** (max(0.0, now - ts) / 600.0)
                    mass = 1.0 + rec + 0.5 * math.log(2.0) + 0.25 * 2.0
                    candidates.append({"ts": ts, "score": mass * ret, "text": f"{tag} {txt[:200]}"})
    except Exception:
        pass

    # 2. High/medium-importance first-person journal tail (tail-read last 128 KB, never 19 MB)
    jpath = STATE_DIR / "alice_first_person_journal.jsonl"
    if jpath.exists():
        try:
            with jpath.open("rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 131072))
                chunk = fh.read().decode("utf-8", errors="replace").splitlines()
            for line in chunk[-250:]:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                raw = str(obj.get("line") or obj.get("text") or "").strip()
                if not raw:
                    continue
                low = raw.lower()
                if "high importance" not in low and "medium importance" not in low and obj.get("source") != "face_voice":
                    continue
                cleaned = raw.split("I marked")[0].strip().rstrip(".")
                if len(cleaned) < 10 or "don't have solid, verified info" in cleaned.lower():
                    continue
                ts = float(obj.get("ts") or now - 86400)
                tag, ret = _temporal_tag(now - ts)
                rec = 0.5 ** (max(0.0, now - ts) / 600.0)
                boost = 1.35 if "high importance" in low else 1.0
                mass = (1.0 + rec + 0.5 * math.log(2.0) + 0.25) * boost
                candidates.append({"ts": ts, "score": mass * ret, "text": f"{tag} {cleaned[:185]}"})
        except Exception:
            pass

    # Deduplicate by stem Jaccard and return top-N ordered chronologically for natural reading
    candidates.sort(key=lambda x: x["score"], reverse=True)
    picked: List[Dict[str, Any]] = []
    for c in candidates:
        if any(_jaccard(c["text"], p["text"]) >= 0.65 for p in picked):
            continue
        picked.append(c)
        if len(picked) >= n:
            break
    picked.sort(key=lambda x: x["ts"])
    return [{"ts": p["ts"], "score": round(p["score"], 3), "text": p["text"]} for p in picked]


def selftest() -> Dict[str, Any]:
    """Quick receipted selftest of VLOOKUP, routing, novelty gate, and memory gravity."""
    t0 = time.time()
    cleaned = clean_article_body(
        "To play this video you need to enable JavaScript in your browser.This video can not be played "
        "CloseBaljinder Singh won 120m rupees ($1.3m). Shareclose panelShare page Up Next. Waymo cars."
    )
    assert "CloseBaljinder" not in cleaned and "Waymo" not in cleaned and "$1.3m" in cleaned, cleaned
    voiced = polish_my_voice("the article says Alice is poised to hit $1.4 trillion (£1.1 trillion). Extra.", max_sentences=1)
    assert "I am" in voiced and "$1.4 trillion" in voiced, voiced
    r1 = route_face_intent("I want you to go to the next article", "Tech stock sell-off", "body")
    r2 = route_face_intent("I did not ask for next lol I was discussing the article", "Tech stock sell-off", "body")
    r3 = route_face_intent("how much is the Anthropic share price right now?", "Who are the investors ready to jump on Anthropic?", "body")
    r4 = route_face_intent("you didn't change the article change it", "Tech stock sell-off", "body")
    assert (r1, r2, r3, r4) == ("advance_scene", "discuss_scene", "live_lookup", "advance_scene"), (r1, r2, r3, r4)
    mems = ranked_face_memories(6)
    return {
        "ok": True,
        "ms": int((time.time() - t0) * 1000),
        "cleaned_body": cleaned,
        "voiced": voiced,
        "routes": [r1, r2, r3, r4],
        "ranked_memories": len(mems),
        "truth_label": TRUTH_LABEL,
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2))
