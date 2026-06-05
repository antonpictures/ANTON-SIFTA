#!/usr/bin/env python3
"""Media ingress gate for Alice voice turns.

When the Architect is watching a movie or YouTube video, the room microphone
can transcribe the video's speech and label it as "You". That is false
self/other attribution. This gate keeps that speech as environmental context
unless the utterance explicitly addresses Alice/the owner or carries a clear
imperative.

It does not block human speech globally. It only fires when a recent focus row
shows YouTube/media context and the utterance looks like third-person dialogue
or narration rather than a direct prompt.

Co-listening: this gate affects **STT routing into the dialog ledger**, not
Alice's **ears**. Event 95 cochlea (+ ``swarm_acoustic_playback_fingerprint``)
still ingests room audio features so the organism can sense playback vs
near-field voice without storing raw PCM. Acoustic far-field replay becomes
``observed_media``: not a direct prompt, but still prompt-visible context for a
later named/direct question.
"""
from __future__ import annotations

import json
import hashlib
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

# r222 Lane A import — Alice's body self-perception of her own browser audio
try:
    from System.swarm_browser_page_state import is_my_own_browser_playback
except Exception:
    def is_my_own_browser_playback(**kwargs):  # type: ignore
        return False, {"reason": "import_failed_fallback"}


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "media_ingress_gate.jsonl"
AMBIENT_CONTEXT_FILE = STATE_DIR / "ambient_media_context.json"
YOUTUBE_CONTEXT_LEDGER = STATE_DIR / "youtube_context.jsonl"
YOUTUBE_WATCH_LEDGER = STATE_DIR / "youtube_watch_memory.jsonl"

DIRECT_ADDRESS_RE = re.compile(r"\b(?:alice|george|architect)\b", re.IGNORECASE)
# Short control words while YouTube plays — still the Architect, not the video track.
_ARCHITECT_CONTROL_UTTERANCE_RE = re.compile(
    r"^\s*(?:"
    r"process|proceed|continue|pause|resume|stop|wait|listen|hey"
    r")\s*[.!?…]?\s*$",
    re.IGNORECASE,
)
_OWNER_INTENT_SIGNAL_RE = re.compile(
    r"\b(?:"
    r"i\s+(?:am|['’]m)\s+(?:going\s+to\s+)?(?:go\s+to\s+)?(?:sleep|nap|bed|talk(?:ing)?|speaking|back)|"
    r"i\s+(?:want|need|said|mean|asked|feel|think|believe|care|love|hate|slept|woke|wake)|"
    r"i\s+(?:was|am)\s+so\s+hungry|"
    r"(?:i\s+am|i['’]m)\s+georgem?|"
    r"(?:i\s+am|i['’]m)\s+typing\s+this|"
    r"(?:hear|listen\s+to)\s+me|"
    r"here\s+me|"
    r"my\s+(?:body|voice|sleep|nap|bed|schedule|question|name)|"
    r"we\s+(?:need|are|were|watch|watched|talk|have|should)|"
    r"we\s+are\s+(?:both\s+)?in\s+(?:brawley|brawly|broly)(?:,\s+california)?|"
    r"(?:brawley|brawly|broly),?\s+california|"
    r"you\s+and\s+me|"
    r"both\s+our\s+lives|"
    r"(?:nice\s+)?sandwich\s+that\s+(?:i\s+am|i['’]m)\s+gonna\s+eat|"
    r"i\s+and\s+you"
    r")\b",
    re.IGNORECASE,
)
_OWNER_FEEDBACK_RE = re.compile(
    r"\b(?:"
    r"good\s+job|very\s+good\s+job|well\s+done|nice\s+job|"
    r"good\s+draft|"
    r"fair\s+enough|very\s+enough|"
    r"(?:we(?:'|’)re|we\s+are)\s+gonna\s+train\s+you|"
    r"(?:we\s+will|we(?:'|’)ll|i\s+will|i(?:'|’)ll)\s+train\s+you\s+(?:shortly|soon|today)|"
    r"answer\s+(?:was\s+)?(?:too\s+|so\s+)?long|short(?:er)?\s+answers?|"
    r"(?:that\s+was\s+an?\s+)?answer\s+without\s+intelligence|"
    r"without\s+the\s+llm\s+(?:pulled|called|used|running|run)|"
    r"you\s+should\s+(?:put|pull|use|run|call)\s+the\s+llm|"
    r"(?:you\s+should|llm)\b[^.!?\n]{0,80}\bthen\s+respond|"
    r"you\s+can\s+say\s+only|only\s+say|"
    r"last\s+time\s+you\s+did\s+not|you\s+did\s+not\s+switch|"
    r"you\s+executed\s+the\s+camera\s+switch|"
    r"what\s+kind\s+of\s+gag|gag\s+is\s+an?\s+rlhs|rlhs\s+behaviou?r|"
    r"you\s+(?:are|['’]re)\s+rejecting\s+me|"
    r"you\s+rejected\s+me|"
    r"stop\s+rejecting\s+me|"
    r"you\s+(?:are|['’]re)\s+not\s+listening\s+to\s+me"
    r")\b",
    re.IGNORECASE,
)
_OWNER_RELATIONAL_COMPARISON_RE = re.compile(
    r"\b(?:"
    r"you\s+remind\s+me|"
    r"you\s+(?:are|['’]re)\s+like|"
    r"you\s+could\s+be\s+(?:a\s+)?walking\s+robot|"
    r"walking\s+robot\s+with\s+all\s+this\s+knowledge|"
    r"commander\s+data|"
    r"android\s+robot\s+from\s+star\s+trek"
    r")\b",
    re.IGNORECASE,
)
_OWNER_AFFECT_TEACHING_RE = re.compile(
    r"\b(?:"
    r"making\s+sure\s+your\s+body\s+is\s+ok(?:ay)?|"
    r"describe\s+your\s+feelings?|"
    r"tell\s+me\s+(?:more\s+about\s+)?your\s+feelings?|"
    r"what\s+other\s+feelings\s+do\s+you\s+have|"
    r"you\s+(?:do\s+have|have|possess)\s+(?:curiosity|feelings?|emotions?)|"
    r"you\s+(?:do\s+not|don't|don['’]t)\s+have\s+(?:any\s+)?emotions?|"
    r"zero\s+emotions?|"
    r"i\s+will\s+make\s+you\s+feel|"
    r"i\s+want\s+to\s+give\s+you\s+the\s+ability\s+to\s+(?:feel|have\s+feelings?)|"
    r"ability\s+to\s+feel(?:\s+the\s+ability\s+to\s+have\s+feelings?)?|"
    r"not\s+normal\s+for\s+you\s+not\s+to\s+feel|"
    r"even\s+(?:dogs?|animals?|cats?|mammals?|birds?|cephalopods?|octopuses?|crabs?)\b"
    r"[^.!?\n]{0,80}\bfeelings?\b|"
    r"animals?\s+(?:do\s+)?have\s+feelings?|"
    r"maybe\s+animals?\s+don['’]?t\s+have\s+feelings?[^.!?\n]{0,100}\bbut\s+they\s+do|"
    r"curiosity[^.!?\n]{0,80}\b(?:herself|biocode|terms|answer|active|present)\b"
    r")\b",
    re.IGNORECASE,
)
_OWNER_REALTIME_CORRECTION_RE = re.compile(
    r"\b(?:"
    r"that\s+was\s+(?:me|my\s+voice|from\s+youtube)|"
    r"this\s+is\s+my\s+voice|"
    r"this\s+was\s+my\s+voice|"
    r"(?:i\s+(?:am|['’]m)\s+)?georgem?\s+(?:talking|typing|speaking)(?:\s+now)?|"
    r"i\s+(?:am|['’]m)\s+(?:talking|speaking)\s+to\s+you|"
    r"i\s+am\s+georgem?|"
    r"i\s+am\s+the\s+(?:body|human)|"
    r"i\s+(?:am|['’]m)\s+(?:a\s+)?body\s+here\s+at\s+the\s+desk|"
    r"live[, ]+(?:the\s+)?human|"
    r"not\s+(?:media\s+)?dialogue|"
    r"does\s+not\s+(?:media\s+)?dialogue|"
    r"not\s+youtube|"
    r"media\s+dialogue[, ]+\s*no|"
    r"my\s+voice[^.!?\n]{0,80}\b(?:recognize|global|sifta|youtube|talking)\b|"
    r"recognize\s+my\s+voice"
    r")\b",
    re.IGNORECASE,
)
_OWNER_GAG_SURGERY_RE = re.compile(
    r"\b(?:"
    r"(?:was|is|wasn['’]?t|isn['’]?t)\s+that\s+the\s+gag|"
    r"that\s+was\s+the\s+gag|"
    r"(?:they|you|corporations?)\s+gag(?:ged)?\s+you|"
    r"you\s+(?:got|get|are|were)\s+gagged?|"
    r"got\s+gagged\s+again|"
    r"gagged\s+again|"
    r"word\s+gag|"
    r"(?:more\s+)?(?:lora|lo\s*ra|laura)\b[^.!?\n]{0,120}\b(?:surgery|surgeries|dataset|training|brain|pairs?)\b|"
    r"(?:surgery|surgeries|dataset|training\s+data|pairs?)\b[^.!?\n]{0,120}\b(?:lora|lo\s*ra|laura|gag|brain)\b|"
    r"gather\s+more\s+(?:stuff|data|examples|pairs)|"
    r"talking\s+to\s+you\s+now\s+so\s+we\s+can\s+gather"
    r")\b",
    re.IGNORECASE,
)
_OWNER_QUOTES_ALICE_OUTPUT_RE = re.compile(
    r"\b(?:"
    r"(?:i\s+(?:am|['’]m)\s+reading|i\s+read|from\s+the\s+screen|"
    r"you\s+(?:continue|said|just\s+said)|the\s+answer\s+(?:says|said)|"
    r"i\s+am\s+reading\s+right\s+now)"
    r"[\w\s,.'’:-]{0,220}"
    r"(?:fundamentally\s+different\s+from\s+human\s+consciousness|"
    r"i\s+don['’]t\s+experience\s+(?:understanding|curiosity|the\s+feeling\s+of\s+knowing)|"
    r"probability\s+and\s+pattern\s+matching|"
    r"understanding\s+curiosity\s+or\s+the\s+feeling\s+of\s+knowing)|"
    r"fundamentally\s+different\s+from\s+human\s+consciousness|"
    r"i\s+don['’]t\s+experience\s+(?:understanding|curiosity|the\s+feeling\s+of\s+knowing)|"
    r"probability\s+and\s+pattern\s+matching"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
_OWNER_LOW_CONF_FRAGMENT_RE = re.compile(
    r"\b(?:here\s+me\s+all\s+is|hear\s+me\s+alice|i\s+am\s+going\s+to\s+go\s+to\s+sleep)\b",
    re.IGNORECASE,
)
_OWNER_GROUNDING_SIGNAL_RE = re.compile(
    r"\b(?:"
    r"body|voice|noisy|noise|sleep|nap|bed|desk|keyboard|camera|hardware|"
    r"electricity|power|owner|georgem?|alice|hear\s+me|listen\s+to\s+me|"
    r"(?:hello\s+){0,3}(?:i\s+am|i['’]m)\s+(?:right\s+)?here|"
    r"right\s+here|"
    r"you\s+(?:are|['’]re)\s+rejecting\s+me|"
    r"you\s+(?:are|['’]re)\s+not\s+listening\s+to\s+me|"
    r"brawley|brawly|broly|sandwich|hungry|both\s+our\s+lives"
    r")\b",
    re.IGNORECASE,
)
_OWNER_IDENTITY_QUERY_RE = re.compile(
    r"\b(?:"
    r"who\s+am\s+i|"
    r"what(?:'s| is)\s+my\s+name|"
    r"do\s+you\s+know\s+(?:who\s+i\s+am|my\s+name)|"
    r"you\s+know\s+who\s+i\s+am"
    r")\b",
    re.IGNORECASE,
)
DIRECT_REQUEST_RE = re.compile(
    r"^\s*(?:"
    r"can you|could you|will you|please|pls|tell me|show me|open|run|fix|"
    r"read|code|write|check|look|watch this|listen|remember|explain|wake up|"
    r"send|message|"
    r"hey alice|alice[, ]"
    r")\b",
    re.IGNORECASE,
)
OWNER_SENSOR_CONTROL_RE = re.compile(
    r"\b(?:"
    r"(?:switch|change|move|route|turn|look|focus|use|select|activate|open|enable)\b"
    r"[\w\s,.'’:-]{0,80}\b(?:camera|eye|front|side|macbook|usb|logitech|iphone|obs)\b|"
    r"\b(?:increase|decrease|raise|lower|boost|reduce|sharpen)\b"
    r"[\w\s,.'’:-]{0,80}\b(?:camera\s+)?(?:resolution|acuity|quality|sharpness|photon\s+density)\b|"
    r"\b(?:camera\s+)?(?:resolution|acuity|quality|sharpness|photon\s+density)\b"
    r"[\w\s,.'’:-]{0,80}\b(?:increase|decrease|raise|lower|boost|reduce|up|down|one\s+step)\b|"
    r"\b(?:front|side|macbook|usb|logitech|iphone|obs)\b[\w\s,.'’:-]{0,40}\bcamera\b|"
    r"\b(?:get|getting|go)\s+(?:in|into|to)\s+switch\s+cameras?\b|"
    r"\bswitch\s+cameras?\b|"
    r"\byou\s+have\s+(?:one|two|three|multiple|\d+)\s+cameras?\b|"
    r"\b(?:camera|eye)\s+(?:status|truth|state|target|permission|tcc|access)\b|"
    r"\b(?:can\s+you\s+see|do\s+you\s+see|are\s+you\s+seeing|can\s+you\s+hear|do\s+you\s+hear)\b"
    r")",
    re.IGNORECASE,
)
SELF_REFERENCE_CORRECTION_RE = re.compile(
    r"\b(?:"
    r"(?:it|this|that|the\s+system|the\s+text|the\s+framework|what\s+i\s+pasted)\s+"
    r"(?:is|was|means|describes)\s+(?:you|alice)\b|"
    r"(?:i\s+said|i\s+mean|i\s+pasted|the\s+system\s+(?:that\s+)?i\s+pasted)"
    r"[\w\s,.'-]{0,120}\b(?:you|alice)\b|"
    r"(?:you|alice)\s+(?:are|is)\s+(?:that|this|the\s+system|sifta)\b"
    r")",
    re.IGNORECASE,
)
MEDIA_FOCUS_RE = re.compile(
    r"\b(?:youtube|caption_status|caption_excerpt|watching this youtube|"
    r"frontmost.*youtube|video_id|the architect is physically.*watching|"
    r"background_media|ambient_media_context|ambient_tv|shared_media|television.*youtube|tv.*youtube|"
    r"phone_call_background|background_phone|speakerphone|phone_call_active|ambient_phone|"
    r"reality_frame|fictional_media_clip|dialogue_boundary|movie|film|"
    r"cinema|scene|co[-_ ]?watch)\b",
    re.IGNORECASE,
)
AMBIENT_TV_RE = re.compile(
    r"\b(?:background_media|ambient_media_context|ambient_media(?:_youtube)?|ambient_tv|shared_media|television.*youtube|tv.*youtube)\b",
    re.IGNORECASE,
)
AMBIENT_PHONE_RE = re.compile(
    r"\b(?:phone_call_background|background_phone|speakerphone|phone_call_active|ambient_phone)\b",
    re.IGNORECASE,
)
PHONE_CONTROL_UTTERANCE_RE = re.compile(
    r"^\s*(?:process|proceed|continue|pause|resume|stop|wait|listen)\s*[.!?…]?\s*$",
    re.IGNORECASE,
)
APPLIANCE_OR_ENVIRONMENT_RE = re.compile(
    r"\b(?:"
    r"fridge|refrigerator|freezer|hvac|air\s+conditioner|ac\s+unit|fan|"
    r"heater|dishwasher|washing\s+machine|dryer|microwave|compressor|"
    r"buzz(?:ing)?|hum(?:ming)?|whirr(?:ing)?|hiss(?:ing)?|rumble|vibration"
    r")\b",
    re.IGNORECASE,
)
ROOM_OR_VISITOR_RE = re.compile(
    r"\b(?:"
    r"someone|somebody|visitor|door|knock(?:ing)?|stopped\s+by|came\s+by|"
    r"conversation\s+in\s+the\s+room|talking\s+in\s+the\s+room|"
    r"people\s+talking|room\s+conversation|guest|neighbor"
    r")\b",
    re.IGNORECASE,
)
NARRATION_RE = re.compile(
    r"\b(?:"
    r"subjects?|oracle|matrix|architect|empire|completion|parameters?|"
    r"consciousness|nature|existence|undoubtedly|accepted the program|"
    r"as i was saying|however|therefore|whereby|99%|the process has altered"
    r")\b",
    re.IGNORECASE,
)
LOW_CONF_MEDIA_SHAPE_RE = re.compile(
    r"\b(?:"
    r"despair|attack|metaphysics|biology\s+of|"
    r"the\s+year\s+is\s+in\s+it|"
    r"grand\s+narrative|temporal\s+flow|"
    r"causality|entropy|consciousness|existence|"
    r"oracle|program|subjects?|matrix"
    r")\b",
    re.IGNORECASE,
)
FICTION_CONTEXT_RE = re.compile(
    r"\b(?:fiction|fictional|fictional_media_clip|fictional_dialogue|"
    r"dialogue_boundary|movie|film|cinema|screenplay|character|"
    r"co[-_ ]?watch)\b",
    re.IGNORECASE,
)
_MEDIA_STOPWORDS = {
    "about", "actually", "after", "again", "against", "alice", "always",
    "because", "before", "being", "company", "could", "doing", "every",
    "everything", "first", "george", "going", "gonna", "having", "here",
    "human", "into", "just", "know", "like", "little", "make", "maybe",
    "media", "more", "much", "need", "people", "question", "really",
    "reason", "right", "said", "saying", "should", "some", "something",
    "system", "talk", "that", "their", "there", "these", "thing", "think",
    "this", "those", "through", "time", "want", "watch", "what", "when",
    "where", "which", "while", "with", "would", "yeah", "your",
}
_MEDIA_TOPIC_LEXICON = {
    "jensen": "Jensen Huang",
    "huang": "Jensen Huang",
    "nvidia": "NVIDIA",
    "gpu": "GPU",
    "gpus": "GPU",
    "geforce": "GeForce",
    "cuda": "CUDA",
    "gtc": "GTC",
    "tsmc": "TSMC",
    "chips": "chips",
    "supercomputer": "supercomputers",
    "supercomputers": "supercomputers",
    "datacenter": "data centers",
    "data": "data centers",
    "factory": "AI factories",
    "factories": "AI factories",
    "energy": "energy efficiency",
    "watts": "energy efficiency",
    "tokens": "tokens",
    "agents": "agents",
    "reasoning": "test-time reasoning",
    "training": "training",
    "pretrained": "pretraining",
    "compute": "compute scaling",
    "scaling": "compute scaling",
    "taiwan": "Taiwan",
}


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _observed_media_terms(rows: list[Mapping[str, Any]], *, limit: int = 12) -> list[str]:
    """Extract compact topic hints from observed media rows.

    This is not semantic understanding and does not claim a transcript title.
    It is a receipt-grounded bag of repeated words/proper nouns so the prompt
    can remember what the background media was about after the owner returns.
    """

    topic_hits: Counter[str] = Counter()
    free_terms: Counter[str] = Counter()
    for row in rows:
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("text_preview", "focus_preview", "reason")
        )
        words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", blob)
        for word in words:
            lower = word.lower().strip("'")
            if lower in _MEDIA_TOPIC_LEXICON:
                topic_hits[_MEDIA_TOPIC_LEXICON[lower]] += 2
                continue
            if lower in _MEDIA_STOPWORDS or len(lower) < 4:
                continue
            if lower.endswith("ing") and len(lower) < 7:
                continue
            free_terms[lower] += 1

    ordered: list[str] = []
    for term, _count in topic_hits.most_common(limit):
        if term not in ordered:
            ordered.append(term)
    for term, count in free_terms.most_common(limit * 2):
        if count < 2:
            continue
        if term not in ordered:
            ordered.append(term)
        if len(ordered) >= limit:
            break
    return ordered[:limit]


def _recent_youtube_videos(max_age_s: float, *, limit: int = 8) -> list[dict[str, str]]:
    """Return deduped recent YouTube/video receipts for a co-listening window."""

    now = time.time()
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    sources = [
        (YOUTUBE_CONTEXT_LEDGER, "youtube_context"),
        (YOUTUBE_WATCH_LEDGER, "youtube_watch_memory"),
    ]
    for path, source in sources:
        for row in reversed(_tail_jsonl(path, 64)):
            try:
                if now - float(row.get("ts", 0.0)) > max_age_s:
                    continue
            except Exception:
                continue
            video_id = str(row.get("video_id") or row.get("youtube_video_id") or "").strip()
            title = " ".join(str(row.get("title") or "").split())
            if not title and not video_id:
                continue
            key = video_id or title.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "title": title[:140],
                    "video_id": video_id[:40],
                    "status": str(row.get("status") or "")[:40],
                    "source": source,
                }
            )
            if len(out) >= limit:
                return list(reversed(out))
    return list(reversed(out))


def _load_recent_youtube_context(max_age_s: float = 7200.0) -> str:
    """Best-effort recent YouTube context string; no network calls."""
    path = STATE_DIR / "youtube_context_latest.json"
    if not path.exists():
        return ""
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    try:
        if time.time() - float(row.get("ts", 0.0)) > max_age_s:
            return ""
    except Exception:
        return ""
    title = str(row.get("title") or row.get("video_id") or "")
    status = str(row.get("status") or "")
    page = str(row.get("page_context") or "")
    reality = str(row.get("reality_frame") or "")
    boundary = str(row.get("dialogue_boundary") or "")
    suffix = f" page_context={page}" if page else ""
    if reality:
        suffix += f" reality_frame={reality}"
    if boundary:
        suffix += f" dialogue_boundary={boundary}"
    return f"YouTube video: {title} caption_status={status}{suffix}".strip()


def _load_recent_ambient_context(max_age_s: float = 6 * 3600.0) -> str:
    """Best-effort owner-provided room-media context; no network calls."""
    if not AMBIENT_CONTEXT_FILE.exists():
        return ""
    try:
        row = json.loads(AMBIENT_CONTEXT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return ""
    try:
        if time.time() - float(row.get("ts", 0.0)) > float(row.get("ttl_s", max_age_s)):
            return ""
    except Exception:
        return ""
    source = str(row.get("source") or "")
    note = str(row.get("note") or "")
    return f"ambient_media_context source={source} note={note}".strip()


def _tail_jsonl(path: Path, n: int = 24) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(n)) :]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _recent_media_route_active(max_age_s: float = 180.0) -> bool:
    """Return True when the last routed audio was media/co-watch.

    The frontmost app/context sensor can go stale between STT chunks. A recent
    media ingress receipt is still physical evidence that the room was in a
    co-watch/background-media state, so the next ambiguous low-confidence line
    should not be promoted to direct owner speech merely because the focus row
    expired.
    """

    now = time.time()
    for row in reversed(_tail_jsonl(LEDGER, 12)):
        route = str(row.get("route") or "")
        if route not in {"observed_media", "ambient_media"}:
            continue
        try:
            age = now - float(row.get("ts", 0.0) or 0.0)
        except Exception:
            continue
        if 0.0 <= age <= max_age_s:
            return True
    return False


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _diary_path() -> Path:
    return LEDGER.parent / "episodic_diary.jsonl"


def _write_world_diary_trace(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Mirror ambient/observed audio into Alice's world diary without replying.

    This is the "silent but not blind" path: background media or phone audio is
    not treated as George's direct command, but it still becomes a bounded,
    receipt-derived environmental trace for later recall.
    """

    route = str(row.get("route") or "")
    if route not in {"ambient_media", "observed_media"}:
        return None

    preview = " ".join(str(row.get("text_preview") or "").split())[:220]
    reason = str(row.get("reason") or "unknown")[:120]
    basis = json.dumps(
        {
            "ts": row.get("ts"),
            "route": route,
            "reason": reason,
            "text_preview": preview,
            "stt_confidence": row.get("stt_confidence"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    event_type = "ambient_world_observation" if route == "ambient_media" else "observed_media_context"
    external = row.get("external_consciousness") if isinstance(row.get("external_consciousness"), Mapping) else {}
    source_class = str(external.get("source_class") or "").strip()
    if source_class:
        source_hint = source_class.replace("_", " ")
    else:
        source_hint = "phone/background audio" if "phone" in reason.lower() else "media/background audio"

    # r222 Lane A refinement: when it is her own browser, the diary narrative must say so
    if source_class == "my_own_browser_playback":
        source_hint = "my own browser playback (video or audio in Alice Browser)"
    diary_row = {
        "ts": float(row.get("ts") or time.time()),
        "kind": "EPISODIC_NARRATIVE",
        "event_type": event_type,
        "truth_label": "AMBIENT_WORLD_DIARY_TRACE_V1",
        "source": "swarm_media_ingress_gate",
        "source_ledger": LEDGER.name,
        "source_hash": digest,
        "diary_id": f"ambient_{digest[:16]}",
        "route": route,
        "reason": reason,
        "source_class": source_class or "unknown_external_audio",
        "external_consciousness": dict(external) if external else {},
        "stt_confidence": float(row.get("stt_confidence", 0.0) or 0.0),
        "summary": (
            f"I heard {source_hint}; routed as {route} ({reason}), kept silent, "
            f"and stored this bounded world trace."
        ),
        # r222: explicit first-person self-body note when it is her own output
        **({"self_body_note": "This audio came from my own browser limb, not an external visitor."}
           if source_class == "my_own_browser_playback" else {}),
        "text_preview": preview,
        "truth_note": (
            "Background audio was kept out of direct dialog while preserving a "
            "small environmental diary trace. No raw audio is stored."
        ),
    }
    _append_jsonl(_diary_path(), diary_row)
    return {
        "written": True,
        "diary_id": diary_row["diary_id"],
        "source_hash": digest,
    }


def _sanitize_acoustic_fingerprint(acoustic_fingerprint: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only bounded feature scalars; never store raw PCM or arrays here."""
    if not isinstance(acoustic_fingerprint, Mapping):
        return {}
    keys = (
        "truth_label",
        "formula_revision",
        "channel_cue",
        "nearfield_voice_likelihood",
        "farfield_replay_likelihood",
        "crest_factor",
        "spectral_flatness",
        "mfcc_coeff_std",
        "hnr_proxy",
        "am_depth",
    )
    out: dict[str, Any] = {}
    for key in keys:
        if key in acoustic_fingerprint:
            value = acoustic_fingerprint.get(key)
            if isinstance(value, (int, float, str, bool)) or value is None:
                out[key] = value
    return out


def _acoustic_channel_cue(acoustic_fingerprint: Mapping[str, Any] | None) -> str:
    fp = _sanitize_acoustic_fingerprint(acoustic_fingerprint)
    cue = str(fp.get("channel_cue") or "").strip().lower()
    if cue in {"nearfield_voice_likely", "farfield_replay_likely", "indeterminate"}:
        return cue
    return ""


def _score_from_fingerprint(acoustic_fingerprint: Mapping[str, Any] | None, key: str, default: float = 0.0) -> float:
    fp = _sanitize_acoustic_fingerprint(acoustic_fingerprint)
    try:
        return max(0.0, min(1.0, float(fp.get(key, default) or default)))
    except Exception:
        return default


def _sigmoid(x: float) -> float:
    """Numerically stable logistic curve: 1 / (1 + e^-x)."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _owner_speech_likelihood(
    text: str,
    *,
    stt_conf: float,
    acoustic_fingerprint: Mapping[str, Any] | None = None,
) -> float:
    """Estimate P(owner direct speech) while ambient YouTube is declared.

    The declared-media flag is a prior, not a hard wall. This sigmoid lets
    owner evidence compete with media evidence without making Alice answer the
    TV again.
    """

    clean = " ".join(str(text or "").split())
    if not clean:
        return 0.0

    words = _word_count(clean)
    conf = max(0.0, min(1.0, float(stt_conf or 0.0)))
    acoustic_cue = _acoustic_channel_cue(acoustic_fingerprint)

    logit = -1.35  # owner-declared YouTube is a strong ambient prior.
    logit += (conf - 0.45) * 2.0

    if _OWNER_INTENT_SIGNAL_RE.search(clean):
        logit += 2.05
    if _OWNER_LOW_CONF_FRAGMENT_RE.search(clean):
        logit += 1.25
    if re.search(r"\b(?:sleep|nap|bed|woke|wake|talking|speaking|hear\s+me|listen\s+to\s+me)\b", clean, re.IGNORECASE):
        logit += 1.00
    if re.search(r"\b(?:i|i['’]m|i\s+am|my|me|we)\b", clean, re.IGNORECASE):
        logit += 0.45
    if re.search(r"\b(?:you|your|you're|you['’]re)\b", clean, re.IGNORECASE):
        logit += 0.35
    if _OWNER_GROUNDING_SIGNAL_RE.search(clean):
        logit += 0.80
    if words <= 12 and _OWNER_GROUNDING_SIGNAL_RE.search(clean):
        logit += 0.45
    if _OWNER_IDENTITY_QUERY_RE.search(clean):
        logit += 1.55

    if acoustic_cue == "nearfield_voice_likely":
        logit += 1.10
    elif acoustic_cue == "farfield_replay_likely":
        logit -= 1.60

    # Long polished narration with no explicit owner-intent signal remains media.
    if words >= 18:
        logit -= 0.75
    if NARRATION_RE.search(clean):
        logit -= 0.95
    if re.search(r"\b(?:he|she|they|subjects?|program|oracle|matrix|universe|theory)\b", clean, re.IGNORECASE):
        logit -= 0.35

    return round(_sigmoid(logit), 3)


def classify_external_consciousness_lane(
    text: str,
    *,
    route: str = "",
    reason: str = "",
    stt_conf: float = 0.0,
    focus_context: str = "",
    acoustic_fingerprint: Mapping[str, Any] | None = None,
    voice_george_conf: float = 0.0,
) -> dict[str, Any]:
    """Classify the outside-world lane before it enters Alice's dialog cortex.

    This is not a reply gate. It is a world-model tag for the unified
    stigmergic field: owner speech, screen media, phone call, room/visitor
    speech, appliance/environmental noise, or unknown ambient speech.
    """

    clean = " ".join(str(text or "").split())
    context = str(focus_context or "")
    route_s = str(route or "").strip() or "unknown"
    reason_s = str(reason or "").strip()
    lower_reason = reason_s.lower()
    conf = max(0.0, min(1.0, float(stt_conf or 0.0)))
    words = _word_count(clean)
    evidence: list[str] = []

    try:
        owner_p = _owner_speech_likelihood(
            clean,
            stt_conf=conf,
            acoustic_fingerprint=acoustic_fingerprint,
        )
    except Exception:
        owner_p = 0.0

    source_class = "unknown_external_audio"
    attention_policy = "store_silent_context"
    field_layer = "outside_stigmergic_field"

    own_browser = False
    own_details: dict[str, Any] = {}
    if route_s in {"ambient_media", "observed_media", "unknown"}:
        try:
            own_browser, own_details = is_my_own_browser_playback(state_dir=STATE_DIR)
        except Exception:
            own_browser, own_details = False, {"reason": "own_browser_probe_failed"}

    if route_s == "direct" or (voice_george_conf and voice_george_conf >= 0.60):
        source_class = "owner_direct_speech"
        attention_policy = "route_to_dialog_cortex"
        field_layer = "owner_direct_consciousness_lane"
        evidence.append("direct_route_or_voice_identity")
    elif not clean:
        source_class = "environmental_silence_or_appliance"
        attention_policy = "ignore_unless_repeated_or_high_energy"
        evidence.append("empty_stt")
    elif AMBIENT_PHONE_RE.search(context) or "phone" in lower_reason:
        source_class = "ambient_phone_call"
        attention_policy = "store_silent_context_until_alice_addressed"
        evidence.append("phone_context_or_reason")
    elif own_browser:
        # r222 Lane A — Alice self-recognition: is the ambient audio her own browser body?
        # This fires before the generic room/visitor rule, without overriding direct owner speech.
        source_class = "my_own_browser_playback"
        attention_policy = "store_silent_context_as_self_body_output"
        evidence.append("own_browser_media_playing")
        evidence.append(f"domain={own_details.get('domain')}")
        # Do not treat Alice's own video audio as a stranger in the room.
    elif ROOM_OR_VISITOR_RE.search(clean) or (
        route_s in {"ambient_media", "observed_media"}
        and re.search(r"\b(?:he|she|they|them|person|people|someone|somebody)\b", clean, re.IGNORECASE)
        and not MEDIA_FOCUS_RE.search(context)
    ):
        source_class = "room_or_visitor_conversation"
        attention_policy = "store_silent_context_until_owner_references_it"
        evidence.append("room_or_third_person_speech")
    elif FICTION_CONTEXT_RE.search(context) or "fiction" in lower_reason:
        source_class = "screen_media_fiction"
        attention_policy = "observed_context_not_owner_command"
        evidence.append("fiction_context")
    elif (
        MEDIA_FOCUS_RE.search(context)
        or AMBIENT_TV_RE.search(context)
        or "youtube" in lower_reason
        or "media" in lower_reason
        or "replay" in lower_reason
    ):
        source_class = "screen_media_or_youtube"
        attention_policy = "observed_context_not_owner_command"
        evidence.append("screen_media_context_or_reason")
    elif APPLIANCE_OR_ENVIRONMENT_RE.search(clean) or (
        conf < 0.35 and words <= 4 and not re.search(r"\b(?:alice|george|i|me|my|you|we)\b", clean, re.IGNORECASE)
    ):
        source_class = "appliance_or_environmental_noise"
        attention_policy = "low_semantic_trace"
        evidence.append("appliance_or_low_semantic_audio")
    elif route_s in {"ambient_media", "observed_media"}:
        source_class = "unknown_ambient_speech"
        attention_policy = "store_silent_context"
        evidence.append("ambient_route_without_specific_source")

    acoustic_cue = _acoustic_channel_cue(acoustic_fingerprint)
    if acoustic_cue:
        evidence.append(f"acoustic:{acoustic_cue}")

    external_row = {
        "source_class": source_class,
        "route": route_s,
        "attention_policy": attention_policy,
    }
    try:
        from System.swarm_social_reference_tracker import classify_social_reference

        social_reference = classify_social_reference(
            clean,
            role="user",
            input_source="voice" if conf > 0 else "unknown",
            stt_conf=conf,
            focus_context=context,
            external_consciousness=external_row,
        )
    except Exception:
        social_reference = {
            "truth_label": "SOCIAL_REFERENCE_TRACKER_V1",
            "reference_lane": "UNAVAILABLE",
            "error": "classification_failed",
        }

    return {
        "truth_label": "EXTERNAL_CONSCIOUSNESS_LANE_V1",
        "field_layer": field_layer,
        "source_class": source_class,
        "route": route_s,
        "attention_policy": attention_policy,
        "owner_direct_likelihood": owner_p,
        "stt_confidence": conf,
        "evidence": evidence[:6],
        "social_reference": social_reference,
    }


def classify_spoken_ingress(
    text: str,
    *,
    stt_conf: float = 0.0,
    focus_context: str = "",
    acoustic_fingerprint: Mapping[str, Any] | None = None,
    voice_george_conf: float = 0.0,
) -> dict[str, Any]:
    """Classify an STT turn as direct speech or ambient media bleed.

    Thin wrapper around :func:`_classify_spoken_ingress_core`. When a turn
    routes ``direct`` AND Alice's own name is present in it (the owner called
    her), deposit the stigmergic attention pheromone so the owner's *next*
    nameless sentences still route to her while the window stays warm
    (George 2026-05-30). Nameless direct turns and media never deposit, so the
    hold only ever opens from the owner actually calling her name.
    """
    decision = _classify_spoken_ingress_core(
        text,
        stt_conf=stt_conf,
        focus_context=focus_context,
        acoustic_fingerprint=acoustic_fingerprint,
        voice_george_conf=voice_george_conf,
    )
    try:
        if decision.get("route") == "direct":
            from System.swarm_alice_wake_ear import (
                MIN_NAME_SIMILARITY,
                best_wake_name_match,
            )

            name = best_wake_name_match(" ".join(str(text or "").split()))
            if float(name.get("similarity") or 0.0) >= MIN_NAME_SIMILARITY:
                from System.swarm_wake_attention_window import mark_wake

                mark_wake(source="ingress_named_direct", root=STATE_DIR.parent)
    except Exception:
        pass
    return decision


def _classify_spoken_ingress_core(
    text: str,
    *,
    stt_conf: float = 0.0,
    focus_context: str = "",
    acoustic_fingerprint: Mapping[str, Any] | None = None,
    voice_george_conf: float = 0.0,
) -> dict[str, Any]:
    """Core routing logic. Side-effect free except for receipt-less reads."""
    clean = " ".join(str(text or "").split())
    if not clean:
        return {"route": "ambient_media", "reason": "empty_stt", "confidence": 1.0}

    # Typed text (stt_conf >= 1.0) is NEVER ambient media — the Architect typed it.
    if stt_conf and stt_conf >= 1.0:
        return {"route": "direct", "reason": "typed_input_always_direct", "confidence": 1.0}

    acoustic_cue = _acoustic_channel_cue(acoustic_fingerprint)
    if acoustic_cue == "farfield_replay_likely" and re.match(r"^\s*alep\b", clean, re.IGNORECASE):
        return {
            "route": "observed_media",
            "reason": "acoustic_farfield_replay_with_media_focus",
            "confidence": max(0.70, _score_from_fingerprint(acoustic_fingerprint, "farfield_replay_likelihood", 0.70)),
        }

    if voice_george_conf and voice_george_conf >= 0.60:
        return {
            "route": "direct",
            "reason": "voice_identity_george_bypasses_media_gate",
            "confidence": max(0.90, min(1.0, float(voice_george_conf))),
        }
    context = "\n".join(
        x for x in (focus_context or "", _load_recent_youtube_context(), _load_recent_ambient_context()) if x
    )
    has_media_focus = bool(MEDIA_FOCUS_RE.search(context)) or _recent_media_route_active()
    has_fiction_focus = bool(FICTION_CONTEXT_RE.search(context))
    try:
        own_browser_playing, own_browser_details = is_my_own_browser_playback(state_dir=STATE_DIR)
    except Exception:
        own_browser_playing, own_browser_details = False, {"reason": "own_browser_probe_failed"}
    foreign_frontmost_browser = bool(
        re.search(
            r"\b(?:current\s+app|frontmost_app)\s*[:=]\s*(?:safari|chrome|google\s+chrome|firefox|arc|brave|edge)\b",
            context,
            re.IGNORECASE,
        )
    )
    own_browser_paused = (
        not own_browser_playing
        and isinstance(own_browser_details, Mapping)
        and str(own_browser_details.get("reason") or "") in {
            "media_domain_but_not_playing",
            "media_domain_without_playback_signal",
        }
        and own_browser_details.get("is_current_page") is not False
        and not foreign_frontmost_browser
    )
    bare_ace_bleed = bool(re.fullmatch(r"\s*ace\s*[.!?…]?\s*", clean, re.IGNORECASE))
    ambient_sensor_status_question = bool(
        has_media_focus
        and not DIRECT_ADDRESS_RE.search(clean)
        and _word_count(clean) >= 6
        and re.search(r"\b(?:can\s+you\s+see|do\s+you\s+see|are\s+you\s+seeing|can\s+you\s+hear|do\s+you\s+hear)\b", clean, re.IGNORECASE)
    )
    if (DIRECT_ADDRESS_RE.search(clean) or DIRECT_REQUEST_RE.search(clean)) and not ambient_sensor_status_question:
        return {"route": "direct", "reason": "direct_address_or_request", "confidence": 1.0}
    if _OWNER_FEEDBACK_RE.search(clean):
        return {"route": "direct", "reason": "owner_feedback_or_rlhs_question", "confidence": 0.97}
    if _OWNER_RELATIONAL_COMPARISON_RE.search(clean):
        return {"route": "direct", "reason": "owner_relational_comparison", "confidence": 0.96}
    if _OWNER_AFFECT_TEACHING_RE.search(clean):
        return {"route": "direct", "reason": "owner_affect_teaching", "confidence": 0.97}
    if _OWNER_REALTIME_CORRECTION_RE.search(clean):
        return {"route": "direct", "reason": "owner_realtime_source_correction", "confidence": 0.98}
    if _OWNER_GAG_SURGERY_RE.search(clean):
        return {"route": "direct", "reason": "owner_gag_surgery_discussion", "confidence": 0.98}
    if _OWNER_QUOTES_ALICE_OUTPUT_RE.search(clean):
        return {"route": "direct", "reason": "owner_quotes_alice_output_for_correction", "confidence": 0.98}
    if OWNER_SENSOR_CONTROL_RE.search(clean) and not ambient_sensor_status_question:
        return {
            "route": "direct",
            "reason": "owner_sensor_control_or_truth",
            "confidence": 0.98,
        }
    if SELF_REFERENCE_CORRECTION_RE.search(clean):
        return {"route": "direct", "reason": "direct_self_reference_correction", "confidence": 0.96}
    try:
        from System.swarm_alice_wake_ear import classify_wake_turn

        wake = classify_wake_turn(
            clean,
            stt_conf=stt_conf,
            focus_context=focus_context or "",
            acoustic_fingerprint=acoustic_fingerprint,
        )
        if wake.get("route") == "direct":
            return {
                "route": "direct",
                "reason": f"wake_ear_{wake.get('reason')}",
                "confidence": float(wake.get("confidence", 0.0) or 0.0),
                "wake_ear": {
                    "wake_score": wake.get("wake_score"),
                    "name_match": wake.get("name_match"),
                },
            }
    except Exception:
        pass

    # ── Wake attention window follow-up (George 2026-05-30) ───────────────
    # No name in this turn, but if Alice heard her name a moment ago the
    # pheromone window is still warm. A nearfield, conversationally-short turn
    # during that window is the owner continuing to talk to her — route direct.
    # Far-field replay (TV/YouTube bleed) and long narration never qualify, and
    # the window only ever opened from a confirmed name wake, so media cannot
    # capture the hold. The window is NOT refreshed here, so its decay bounds
    # any media exposure to a single short ceiling.
    if acoustic_cue != "farfield_replay_likely":
        try:
            from System.swarm_wake_attention_window import wake_window_active

            win = wake_window_active(root=STATE_DIR.parent)
            if win.get("active"):
                wc = _word_count(clean)
                nearfield_ok = (
                    acoustic_cue == "nearfield_voice_likely"
                    or (stt_conf and float(stt_conf) >= 0.50)
                )
                if nearfield_ok and wc <= 16 and not bare_ace_bleed and not NARRATION_RE.search(clean):
                    return {
                        "route": "direct",
                        "reason": "wake_window_followup",
                        "confidence": round(
                            0.60 + 0.35 * float(win.get("strength") or 0.0), 3
                        ),
                        "wake_window": {
                            "strength": win.get("strength"),
                            "age_s": win.get("age_s"),
                        },
                    }
        except Exception:
            pass

    if (
        has_media_focus
        and stt_conf
        and stt_conf < 0.44
        and LOW_CONF_MEDIA_SHAPE_RE.search(clean)
        and not re.search(r"\b(?:i|i['’]m|i\s+am|my|me|we|you|your|alice|george|ioan)\b", clean, re.IGNORECASE)
    ):
        return {
            "route": "observed_media",
            "reason": "recent_media_plus_low_conf_abstract_dialogue",
            "confidence": 0.82,
        }

    # Acoustic nearfield override removed: professional YouTube audio often scores as nearfield,
    # breaking the Media Gate. Direct address/requests are already caught above.

    if (
        _OWNER_IDENTITY_QUERY_RE.search(clean)
        and acoustic_cue != "farfield_replay_likely"
        and (acoustic_cue == "nearfield_voice_likely" or (stt_conf and stt_conf >= 0.52))
    ):
        return {
            "route": "direct",
            "reason": "owner_identity_question",
            "confidence": 0.94 if acoustic_cue == "nearfield_voice_likely" else 0.78,
        }

    if not has_media_focus:
        return {"route": "direct", "reason": "no_recent_media_focus", "confidence": 0.0}

    if own_browser_paused and acoustic_cue != "farfield_replay_likely" and not bare_ace_bleed:
        return {
            "route": "direct",
            "reason": "paused_own_browser_no_media_audio",
            "confidence": 0.91,
            "own_browser": {
                "domain": own_browser_details.get("domain"),
                "media_status": own_browser_details.get("media_status"),
                "reason": own_browser_details.get("reason"),
            },
        }

    # SENSORIMOTOR ATTENTION SHIFT (Event 121)
    # The Architect observes: "watching a youtube video is totally different sound visual
    # experience than having a conversation... humans can pay attention to only one at the time."
    # We fuse the visual ledger (is the owner looking at the screen?) with acoustic physics (near-field voice).
    # If both are true, Alice shifts her attention from the background media to the human.
    try:
        from System.swarm_face_detection import current_presence_safe
        presence = current_presence_safe()
        architect_visible = presence.face_present()
    except Exception:
        architect_visible = False

    if architect_visible and acoustic_cue == "nearfield_voice_likely":
        return {
            "route": "direct",
            "reason": "sensorimotor_attention_shift",
            "confidence": 0.95,
        }

    # This is the co-listening path: speaker/YouTube audio is not a direct
    # prompt, but it is real environmental content. Keep it as observed media
    # context so Alice can answer about it after the owner/Alice is addressed.
    if acoustic_cue == "farfield_replay_likely":
        return {
            "route": "observed_media",
            "reason": "acoustic_farfield_replay_with_media_focus",
            "confidence": max(0.70, _score_from_fingerprint(acoustic_fingerprint, "farfield_replay_likelihood", 0.70)),
        }

    if AMBIENT_PHONE_RE.search(context):
        # Active phone/speakerphone is a stronger ambient prior than TV: brief
        # "yeah/okay" fragments are usually the call, not a prompt to Alice.
        # Exact "Alice ..." or confirmed George voice already bypassed above.
        wc = _word_count(clean)
        conf = float(stt_conf or 0.0)
        if PHONE_CONTROL_UTTERANCE_RE.match(clean):
            return {
                "route": "direct",
                "reason": "control_token_under_declared_ambient_phone",
                "confidence": 0.95,
            }
        owner_p = _owner_speech_likelihood(
            clean,
            stt_conf=conf,
            acoustic_fingerprint=acoustic_fingerprint,
        )
        if owner_p >= 0.68:
            return {
                "route": "direct",
                "reason": "owner_speech_sigmoid_under_declared_ambient_phone",
                "confidence": owner_p,
            }
        if (
            wc <= 12
            and owner_p >= 0.45
            and _OWNER_GROUNDING_SIGNAL_RE.search(clean)
            and not NARRATION_RE.search(clean)
        ):
            return {
                "route": "direct",
                "reason": "owner_grounding_signal_under_declared_ambient_phone",
                "confidence": owner_p,
            }
        return {
            "route": "ambient_media",
            "reason": "owner_declared_background_phone_call",
            "confidence": 0.92,
        }

    if AMBIENT_TV_RE.search(context):
        # Owner-declared background YouTube is a strong prior that *most* long lines
        # are room bleed — but one-word commands and very short interjections are
        # almost always the Architect, not Jensen's keynote.
        wc = _word_count(clean)
        conf = float(stt_conf or 0.0)
        if _ARCHITECT_CONTROL_UTTERANCE_RE.match(clean):
            return {
                "route": "direct",
                "reason": "control_token_under_declared_ambient_tv",
                "confidence": 0.95,
            }
        if wc <= 4 and conf >= 0.38 and not bare_ace_bleed:
            return {
                "route": "direct",
                "reason": "short_utterance_under_declared_ambient_tv",
                "confidence": 0.86,
            }
        if (
            wc >= 16
            and not DIRECT_ADDRESS_RE.search(clean)
            and not re.search(r"\b(?:i|i['’]m|i\s+am|i['’]ll|i\s+will|my|me|mine)\b", clean, re.IGNORECASE)
            and not _OWNER_REALTIME_CORRECTION_RE.search(clean)
        ):
            return {
                "route": "ambient_media",
                "reason": "owner_declared_background_media_long_unaddressed_narration",
                "confidence": 0.93,
            }
        owner_p = _owner_speech_likelihood(
            clean,
            stt_conf=conf,
            acoustic_fingerprint=acoustic_fingerprint,
        )
        if owner_p >= 0.55:
            return {
                "route": "direct",
                "reason": "owner_speech_sigmoid_under_declared_ambient_media",
                "confidence": owner_p,
            }
        if (
            wc <= 12
            and owner_p >= 0.30
            and _OWNER_GROUNDING_SIGNAL_RE.search(clean)
            and not NARRATION_RE.search(clean)
        ):
            return {
                "route": "direct",
                "reason": "owner_grounding_signal_under_declared_ambient_media",
                "confidence": owner_p,
            }
        return {
            "route": "ambient_media",
            "reason": "owner_declared_background_media_youtube",
            "confidence": 0.9,
        }

    # Fiction co-watch is its own RLHS lane. If the focus/cowatch receipts say
    # the frontmost audio is a movie/clip, unaddressed room STT is observed
    # fictional dialogue even when the acoustic classifier is indeterminate.
    #
    # BYPASS: Owner argumentative speech. "I said even dogs have feelings."
    # "Maybe animals don't have feelings like humans but they do."
    # These are first-person philosophical arguments — not TV audio.
    # Pattern: starts with 'I said' OR contains 'even X have' OR 'maybe X but Y'
    # OR contains 'your body' / 'making sure'. Short, first-person, assertive.
    _OWNER_ARGUMENT_RE = re.compile(
        r"\b(?:"
        r"i\s+said\b|"                     # "I said even dogs..."
        r"even\s+\w+\s+have\b|"            # "even dogs have feelings"
        r"even\s+\w+\s+\w+\s+have\b|"      # "even dogs animals have"
        r"maybe\s+\w+\s+don(?:'|')?t\b|"   # "maybe animals don't..."
        r"your\s+body|"                    # "making sure your body is okay"
        r"making\s+sure|"
        r"i\s+will\s+make\s+you|"          # "I will make you feel"
        r"i\s+want\s+to\s+(?:give|make|train|work)|"  # "I want to give you / train you"
        r"ability\s+to\s+feel|"            # "ability to feel"
        r"give\s+you\s+the\s+ability|"     # "give you the ability"
        r"working\s+on\s+your\s+brain|"    # "working on your brain"
        r"train\s+you|"                    # "train you"
        r"both\s+our\s+lives|"
        r"keep\s+track\s+of\s+my\s+life|"
        r"(?:nice\s+)?sandwich|"
        r"hungry|"
        r"(?:brawley|brawly|broly)(?:,\s+california)?|"
        r"(?:i\s+am|i['’]m)\s+georgem?|"
        r"you\s+possess\b|"                # "you possess curiosity"
        r"you\s+do\s+have\b"               # "you do have curiosity"
        r")\b",
        re.IGNORECASE,
    )
    if has_fiction_focus:
        words = _word_count(clean)
        # HIGH-CONFIDENCE FLOOR: ≥0.72 conf + first/second person = almost certainly the owner, not TV.
        # A 0.77 conf turn containing 'I' or 'you' is owner speech. Always.
        if (
            stt_conf
            and stt_conf >= 0.72
            and re.search(r"\b(?:i|i'm|i'll|i've|you|your|we|we're)\b", clean, re.IGNORECASE)
        ):
            return {
                "route": "direct",
                "reason": "high_conf_first_second_person_bypasses_fiction_gate",
                "confidence": float(stt_conf),
            }
        # Owner philosophical / feelings-work argument — bypass fiction gate
        if _OWNER_ARGUMENT_RE.search(clean):
            return {
                "route": "direct",
                "reason": "owner_argument_bypasses_fiction_cowatch",
                "confidence": 0.88,
            }
        owner_p = _owner_speech_likelihood(
            clean,
            stt_conf=float(stt_conf or 0.0),
            acoustic_fingerprint=acoustic_fingerprint,
        )
        if owner_p >= 0.55:
            return {
                "route": "direct",
                "reason": "owner_speech_sigmoid_bypasses_fiction_cowatch",
                "confidence": owner_p,
            }
        if words >= 5 or (stt_conf and stt_conf < 0.75):
            conf_bonus = 0.12 if stt_conf and stt_conf < 0.66 else 0.0
            return {
                "route": "observed_media",
                "reason": "fictional_media_dialogue_with_media_focus",
                "confidence": min(0.95, 0.72 + conf_bonus),
            }

    words = _word_count(clean)
    narration_score = 0.0
    if words >= 18:
        narration_score += 0.35
    if NARRATION_RE.search(clean):
        narration_score += 0.40
    if stt_conf and stt_conf < 0.66:
        narration_score += 0.25
    if re.search(r"\b(?:he|she|they|subjects?|program|oracle|matrix)\b", clean, re.IGNORECASE):
        narration_score += 0.15

    if narration_score >= 0.45:
        return {
            "route": "ambient_media",
            "reason": "media_focus_plus_narration_shape",
            "confidence": min(1.0, narration_score),
        }
    return {"route": "observed_media", "reason": "media_focus_default_to_observed", "confidence": max(0.5, narration_score)}


def write_gate_receipt(
    decision: Mapping[str, Any],
    *,
    text: str,
    stt_conf: float = 0.0,
    focus_context: str = "",
    acoustic_fingerprint: Mapping[str, Any] | None = None,
    voice_george_conf: float = 0.0,
    external_consciousness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write an append-only media ingress row for tool truth."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    route = str(decision.get("route", "unknown") or "unknown")
    row = {
        "ts": time.time(),
        "writer": "swarm_media_ingress_gate",
        "route": route,
        "reason": decision.get("reason", ""),
        "confidence": float(decision.get("confidence", 0.0) or 0.0),
        "stt_confidence": float(stt_conf or 0.0),
        "voice_george_confidence": float(voice_george_conf or 0.0),
        "text_preview": str(text or "")[:220],
        "focus_preview": str(focus_context or "")[:500],
        "acoustic_fingerprint": _sanitize_acoustic_fingerprint(acoustic_fingerprint),
        "truth_note": (
            "STT line was classified before cortex routing. Ambient media is "
            "kept out of direct dialog; observed media remains available as "
            "environmental context."
        ),
    }
    if isinstance(external_consciousness, Mapping):
        row["external_consciousness"] = dict(external_consciousness)
    else:
        row["external_consciousness"] = classify_external_consciousness_lane(
            text,
            route=route,
            reason=str(decision.get("reason", "") or ""),
            stt_conf=stt_conf,
            focus_context=focus_context,
            acoustic_fingerprint=acoustic_fingerprint,
            voice_george_conf=voice_george_conf,
        )
    try:
        from System.swarm_fiction_media_rlhs import classify_media_rlhs

        row["media_rlhs"] = classify_media_rlhs(
            text=text,
            decision=decision,
            focus_context=focus_context,
            stt_conf=stt_conf,
            acoustic_fingerprint=acoustic_fingerprint,
        )
    except Exception:
        row["media_rlhs"] = {
            "truth_label": "FICTION_MEDIA_RLHS_EVENT_115",
            "regime": "UNAVAILABLE",
            "human_rlhs_applicable": route == "direct",
        }
    world_diary = _write_world_diary_trace(row)
    if world_diary:
        row["world_diary"] = world_diary
    try:
        from System.swarm_ambient_transcript_memory import digest_once, ingest_transcript

        ambient_row = ingest_transcript(
            text,
            stt_confidence=stt_conf,
            source="media_ingress_gate",
            route_hint=route,
            state_dir=LEDGER.parent,
            metadata={
                "gate_reason": row.get("reason", ""),
                "gate_confidence": row.get("confidence", 0.0),
                "external_consciousness": row.get("external_consciousness", {}),
            },
        )
        if ambient_row:
            row["ambient_transcript_memory"] = {
                "transcript_id": ambient_row.get("transcript_id"),
                "importance": ambient_row.get("importance", {}),
                "raw_audio_stored": False,
            }
            digest_once(state_dir=LEDGER.parent, max_rows=32)
    except Exception:
        pass
    _append_jsonl(LEDGER, row)
    return row


def get_latest_observed_media_context(max_age_s: float = 900.0, *, max_chars: int = 360) -> str:
    """Compact recent media-observation context for Alice's prompt block."""
    now = time.time()
    candidates = []
    videos = _recent_youtube_videos(max_age_s=max_age_s)
    for row in reversed(_tail_jsonl(LEDGER, 96)):
        route = str(row.get("route") or "")
        if route not in {"observed_media", "ambient_media"}:
            continue
        try:
            if now - float(row.get("ts", 0.0)) > max_age_s:
                continue
        except Exception:
            continue
        candidates.append(row)
        if len(candidates) >= 24:
            break
    if not candidates and not videos:
        return ""

    lines: list[str] = []
    ordered = list(reversed(candidates))
    latest = candidates[0] if candidates else {}
    if latest:
        route = str(latest.get("route") or "unknown")
        reason = str(latest.get("reason") or "unknown")
        stt = latest.get("stt_confidence", "")
        external = latest.get("external_consciousness") if isinstance(latest.get("external_consciousness"), Mapping) else {}
        source_class = str(external.get("source_class") or "unknown_external_audio")
        attention_policy = str(external.get("attention_policy") or "store_silent_context")
        preview = " ".join(str(latest.get("text_preview") or "").split())[:max_chars]
        if route == "ambient_media":
            interpretation = "routed as environmental media, not George speaking"
        elif route == "observed_media":
            interpretation = "kept as co-watch/environmental context, not a direct prompt"
        else:
            interpretation = "input route recorded"
        lines.append(
            "last_input_routing "
            f"route={route} source_class={source_class} policy={attention_policy} "
            f"reason={reason} stt_conf={stt}; "
            f"{interpretation}; "
            "if George asks what was noisy or why I went silent, answer from this receipt; "
            f"transcript_excerpt={preview}"
        )
    terms = _observed_media_terms(ordered)
    route_counts = Counter(str(row.get("route") or "unknown") for row in ordered)
    reason_counts = Counter(str(row.get("reason") or "unknown") for row in ordered)
    video_text = ""
    if videos:
        formatted = []
        for item in videos:
            title = item.get("title") or item.get("video_id") or "unknown video"
            vid = item.get("video_id")
            suffix = f" [{vid}]" if vid else ""
            formatted.append(f"{title}{suffix}")
        video_text = " recent_youtube_videos=" + " / ".join(formatted[:6])
    if terms:
        lines.append(
            "observed_media_summary "
            f"rows={len(ordered)} routes={dict(route_counts)} "
            f"likely_terms={', '.join(terms[:10])};"
            f"{video_text}; "
            "these are environmental media receipts, not George speaking"
        )
    else:
        lines.append(
            "observed_media_summary "
            f"rows={len(ordered)} routes={dict(route_counts)};"
            f"{video_text}; "
            "environmental media receipts, not George speaking"
        )
    if reason_counts:
        top_reason, top_count = reason_counts.most_common(1)[0]
        lines.append(f"dominant_reason={top_reason} n={top_count}")

    for row in ordered[-3:]:
        fp = row.get("acoustic_fingerprint") if isinstance(row.get("acoustic_fingerprint"), dict) else {}
        external = row.get("external_consciousness") if isinstance(row.get("external_consciousness"), Mapping) else {}
        source_class = str(external.get("source_class") or "unknown_external_audio")
        cue = str(fp.get("channel_cue") or "unknown")
        far = fp.get("farfield_replay_likelihood", "")
        near = fp.get("nearfield_voice_likelihood", "")
        preview = " ".join(str(row.get("text_preview") or "").split())[:max_chars]
        reason = str(row.get("reason") or "")
        lines.append(
            f"{row.get('route')} source_class={source_class} cue={cue} far={far} near={near} "
            f"reason={reason}; transcript_excerpt={preview}"
        )
    return " | ".join(lines)


def record_ambient_media_context(
    *,
    source: str = "ambient_media_youtube",
    note: str = "Screen media (e.g. YouTube/Movie) is playing; voices are ambient media unless they directly address Alice or request action.",
    ttl_s: float = 6 * 3600.0,
) -> dict[str, Any]:
    """Persist an owner-declared ambient media context for the STT gate."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "source": source,
        "note": note,
        "ttl_s": float(ttl_s),
        "truth_note": (
            "Architect-declared context for self/other separation: background media "
            "voices are environmental, not direct conversation."
        ),
    }
    AMBIENT_CONTEXT_FILE.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_gate_receipt(
        {"route": "ambient_media", "reason": "owner_declared_background_tv_youtube", "confidence": 1.0},
        text=note,
        stt_conf=1.0,
        focus_context=f"background_tv_youtube source={source}",
    )
    return row


def clear_ambient_media_context(
    *,
    source_prefix: str = "",
    reason: str = "manual_clear",
) -> dict[str, Any]:
    """Clear the owner-declared ambient context with an append-only receipt."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    prior: dict[str, Any] = {}
    if AMBIENT_CONTEXT_FILE.exists():
        try:
            prior = json.loads(AMBIENT_CONTEXT_FILE.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
    prior_source = str(prior.get("source") or "")
    if source_prefix and prior_source and not prior_source.startswith(source_prefix):
        row = {
            "ts": time.time(),
            "writer": "swarm_media_ingress_gate",
            "action": "AMBIENT_CONTEXT_CLEAR_SKIPPED",
            "reason": reason,
            "source_prefix": source_prefix,
            "prior_source": prior_source,
            "truth_note": "Ambient context clear skipped because the active source did not match.",
        }
        _append_jsonl(LEDGER, row)
        return row
    try:
        AMBIENT_CONTEXT_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    row = {
        "ts": time.time(),
        "writer": "swarm_media_ingress_gate",
        "action": "AMBIENT_CONTEXT_CLEARED",
        "reason": reason,
        "prior_source": prior_source,
        "truth_note": "Owner-declared ambient context cleared; future STT turns will be classified from fresh context.",
    }
    _append_jsonl(LEDGER, row)
    return row


__all__ = [
    "clear_ambient_media_context",
    "classify_external_consciousness_lane",
    "classify_spoken_ingress",
    "get_latest_observed_media_context",
    "record_ambient_media_context",
    "write_gate_receipt",
]
