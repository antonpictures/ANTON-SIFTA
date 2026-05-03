#!/usr/bin/env python3
"""Media ingress gate for Alice voice turns.

When the Architect is watching a movie or YouTube video, the room microphone
can transcribe the video's speech and label it as "You". That is false
self/other attribution. This gate keeps that speech as environmental context
unless the utterance explicitly addresses Alice/George or carries a clear
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
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


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
DIRECT_REQUEST_RE = re.compile(
    r"^\s*(?:"
    r"can you|could you|will you|please|pls|tell me|show me|open|run|fix|"
    r"read|code|write|check|look|watch this|listen|remember|explain|wake up|"
    r"send|message|"
    r"hey alice|alice[, ]"
    r")\b",
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
    r"reality_frame|fictional_media_clip|dialogue_boundary|movie|film|"
    r"cinema|scene|co[-_ ]?watch)\b",
    re.IGNORECASE,
)
AMBIENT_TV_RE = re.compile(
    r"\b(?:background_media|ambient_media_context|ambient_media(?:_youtube)?|ambient_tv|shared_media|television.*youtube|tv.*youtube)\b",
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
    can remember what the background media was about after George returns.
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


def classify_spoken_ingress(
    text: str,
    *,
    stt_conf: float = 0.0,
    focus_context: str = "",
    acoustic_fingerprint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify an STT turn as direct speech or ambient media bleed.

    Returns:
      {
        "route": "direct" | "ambient_media" | "observed_media",
        "reason": str,
        "confidence": float,
      }
    """
    clean = " ".join(str(text or "").split())
    if not clean:
        return {"route": "ambient_media", "reason": "empty_stt", "confidence": 1.0}

    # Typed text (stt_conf >= 1.0) is NEVER ambient media — the Architect typed it.
    if stt_conf and stt_conf >= 1.0:
        return {"route": "direct", "reason": "typed_input_always_direct", "confidence": 1.0}

    if DIRECT_ADDRESS_RE.search(clean) or DIRECT_REQUEST_RE.search(clean):
        return {"route": "direct", "reason": "direct_address_or_request", "confidence": 1.0}
    if SELF_REFERENCE_CORRECTION_RE.search(clean):
        return {"route": "direct", "reason": "direct_self_reference_correction", "confidence": 0.96}

    acoustic_cue = _acoustic_channel_cue(acoustic_fingerprint)
    context = "\n".join(
        x for x in (focus_context or "", _load_recent_youtube_context(), _load_recent_ambient_context()) if x
    )
    has_media_focus = bool(MEDIA_FOCUS_RE.search(context))
    has_fiction_focus = bool(FICTION_CONTEXT_RE.search(context))

    # Acoustic nearfield override removed: professional YouTube audio often scores as nearfield,
    # breaking the Media Gate. Direct address/requests are already caught above.

    if not has_media_focus:
        return {"route": "direct", "reason": "no_recent_media_focus", "confidence": 0.0}

    # This is the co-listening path: speaker/YouTube audio is not a direct
    # prompt, but it is real environmental content. Keep it as observed media
    # context so Alice can answer about it after George/Alice is addressed.
    if acoustic_cue == "farfield_replay_likely":
        return {
            "route": "observed_media",
            "reason": "acoustic_farfield_replay_with_media_focus",
            "confidence": max(0.70, _score_from_fingerprint(acoustic_fingerprint, "farfield_replay_likelihood", 0.70)),
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
        if wc <= 4 and conf >= 0.38:
            return {
                "route": "direct",
                "reason": "short_utterance_under_declared_ambient_tv",
                "confidence": 0.86,
            }
        return {
            "route": "ambient_media",
            "reason": "owner_declared_background_media_youtube",
            "confidence": 0.9,
        }

    # Fiction co-watch is its own RLHS lane. If the focus/cowatch receipts say
    # the frontmost audio is a movie/clip, unaddressed room STT is observed
    # fictional dialogue even when the acoustic classifier is indeterminate.
    if has_fiction_focus:
        words = _word_count(clean)
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
        "text_preview": str(text or "")[:220],
        "focus_preview": str(focus_context or "")[:500],
        "acoustic_fingerprint": _sanitize_acoustic_fingerprint(acoustic_fingerprint),
        "truth_note": (
            "STT line was classified before cortex routing. Ambient media is "
            "kept out of direct dialog; observed media remains available as "
            "environmental context."
        ),
    }
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
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
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
        preview = " ".join(str(latest.get("text_preview") or "").split())[:max_chars]
        if route == "ambient_media":
            interpretation = "suppressed as environmental media, not George speaking"
        elif route == "observed_media":
            interpretation = "kept as co-watch/environmental context, not a direct prompt"
        else:
            interpretation = "input route recorded"
        lines.append(
            "last_input_routing "
            f"route={route} reason={reason} stt_conf={stt}; "
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
        cue = str(fp.get("channel_cue") or "unknown")
        far = fp.get("farfield_replay_likelihood", "")
        near = fp.get("nearfield_voice_likelihood", "")
        preview = " ".join(str(row.get("text_preview") or "").split())[:max_chars]
        reason = str(row.get("reason") or "")
        lines.append(
            f"{row.get('route')} cue={cue} far={far} near={near} reason={reason}; transcript_excerpt={preview}"
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


__all__ = [
    "classify_spoken_ingress",
    "get_latest_observed_media_context",
    "record_ambient_media_context",
    "write_gate_receipt",
]
