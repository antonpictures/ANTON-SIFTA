#!/usr/bin/env python3
"""Stigmergic media identifier for Alice co-watch sessions.

This is not acoustic fingerprinting against a proprietary catalog. It is the
receipt-native layer first: YouTube page/caption context, observed media
transcripts, watch memory, and focus receipts are fused into a probabilistic
"what is playing?" guess.

The app can feel like Shazam, but the truth label stays honest:
STIGMERGIC_MEDIA_GUESS, not definitive recognition.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
GUESS_LEDGER = STATE_DIR / "media_shazam_guesses.jsonl"
TRUTH_LABEL = "STIGMERGIC_MEDIA_GUESS"


# YouTube API v3 category ids. Active flags reflect the commonly used public
# upload categories; legacy entries stay available so old receipts still parse.
YOUTUBE_CATEGORIES: tuple[dict[str, Any], ...] = (
    {"id": "1", "name": "Film & Animation", "active": True},
    {"id": "2", "name": "Autos & Vehicles", "active": True},
    {"id": "10", "name": "Music", "active": True},
    {"id": "15", "name": "Pets & Animals", "active": True},
    {"id": "17", "name": "Sports", "active": True},
    {"id": "18", "name": "Short Movies", "active": False},
    {"id": "19", "name": "Travel & Events", "active": True},
    {"id": "20", "name": "Gaming", "active": True},
    {"id": "21", "name": "Videoblogging", "active": False},
    {"id": "22", "name": "People & Blogs", "active": True},
    {"id": "23", "name": "Comedy", "active": True},
    {"id": "24", "name": "Entertainment", "active": True},
    {"id": "25", "name": "News & Politics", "active": True},
    {"id": "26", "name": "Howto & Style", "active": True},
    {"id": "27", "name": "Education", "active": True},
    {"id": "28", "name": "Science & Technology", "active": True},
    {"id": "29", "name": "Nonprofits & Activism", "active": True},
    {"id": "30", "name": "Movies", "active": False},
    {"id": "31", "name": "Anime/Animation", "active": False},
    {"id": "32", "name": "Action/Adventure", "active": False},
    {"id": "33", "name": "Classics", "active": False},
    {"id": "34", "name": "Comedy", "active": False},
    {"id": "35", "name": "Documentary", "active": False},
    {"id": "36", "name": "Drama", "active": False},
    {"id": "37", "name": "Family", "active": False},
    {"id": "38", "name": "Foreign", "active": False},
    {"id": "39", "name": "Horror", "active": False},
    {"id": "40", "name": "Sci-Fi/Fantasy", "active": False},
    {"id": "41", "name": "Thriller", "active": False},
    {"id": "42", "name": "Shorts", "active": False},
    {"id": "43", "name": "Shows", "active": False},
    {"id": "44", "name": "Trailers", "active": False},
)


_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Film & Animation": (
        "movie", "film", "scene", "clip", "trailer", "cinema", "actor",
        "actress", "director", "snatch", "john wick", "scarface", "batman",
        "gangs of new york", "goodfellas", "scorsese", "warner bros",
        "boxoffice", "binge society",
    ),
    "Autos & Vehicles": ("car", "truck", "tesla", "engine", "vehicle", "driving", "motor"),
    "Music": ("music", "song", "album", "live performance", "lyrics", "concert", "remix"),
    "Pets & Animals": ("dog", "cat", "animal", "wildlife", "pet", "veterinary"),
    "Sports": ("sports", "match", "game", "football", "basketball", "boxing", "fighter"),
    "Travel & Events": ("travel", "tour", "flight", "hotel", "city walk", "event"),
    "Gaming": ("gameplay", "gaming", "minecraft", "fortnite", "speedrun", "boss fight"),
    "People & Blogs": ("vlog", "daily", "creator", "personal", "storytime", "podcast"),
    "Comedy": ("comedy", "funny", "stand up", "skit", "parody", "joke"),
    "Entertainment": ("entertainment", "celebrity", "show", "interview", "movie", "clip"),
    "News & Politics": (
        "news", "politics", "breaking", "election", "trump", "biden",
        "cnn", "fox news", "msnbc", "bbc", "reuters", "associated press",
        "cnbc", "bloomberg", "sky news", "al jazeera",
    ),
    "Howto & Style": ("how to", "tutorial", "style", "fashion", "makeup", "recipe", "diy"),
    "Education": ("lecture", "course", "explainer", "university", "lesson", "learn"),
    "Science & Technology": (
        "science", "technology", "ai", "nvidia", "jensen", "gpu", "cuda",
        "supercomputer", "chips", "tsmc", "compute", "agents", "reasoning",
        "biology", "physics", "engineering", "quantum", "parallel universe",
        "multiverse", "experiment", "experiments", "consciousness",
        "perception", "cosmology", "universe",
    ),
    "Nonprofits & Activism": ("nonprofit", "activism", "charity", "human rights", "petition"),
    "Documentary": ("documentary", "true story", "archive", "investigation", "mainstream", "traditions"),
    "Movies": ("full movie", "movie", "film"),
    "Shows": ("episode", "season", "show", "series"),
    "Trailers": ("official trailer", "teaser", "trailer"),
}

_SOURCE_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("movie_or_fiction_clip", "fiction/movie clip", ("movie", "film", "scene", "clip", "snatch", "goodfellas", "john wick", "scarface", "trailer")),
    ("news_network", "news network / politics", ("cnn", "fox news", "msnbc", "bbc", "reuters", "associated press", "cnbc", "bloomberg", "sky news", "al jazeera")),
    ("tech_interview", "technology interview / keynote", ("nvidia", "jensen", "gpu", "cuda", "tsmc", "supercomputer", "ai factory", "compute")),
    ("science_documentary", "science documentary", ("parallel universe", "multiverse", "quantum", "physics", "experiment", "experiments", "consciousness", "perception", "cosmology")),
    ("music_video", "music video / performance", ("music", "song", "lyrics", "concert", "remix")),
    ("podcast_or_long_interview", "podcast / long interview", ("podcast", "interview", "lex fridman", "conversation", "full episode")),
    ("gaming_video", "gaming video", ("gameplay", "gaming", "minecraft", "fortnite", "boss fight")),
)

_SCENE_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "CINEMATIC": ("Film & Animation", "Entertainment"),
    "NEWS": ("News & Politics",),
    "MUSIC": ("Music",),
    "SPORTS": ("Sports",),
    "GAMING": ("Gaming",),
    "PODCAST": ("People & Blogs", "Education"),
    "AMBIENT": ("Music", "Entertainment"),
}

_SCENE_SOURCE_HINTS: dict[str, tuple[str, str]] = {
    "CINEMATIC": ("movie_or_fiction_clip", "fiction/movie clip"),
    "NEWS": ("news_network", "news network / politics"),
    "MUSIC": ("music_video", "music video / performance"),
    "SPORTS": ("sports_broadcast", "sports broadcast"),
    "GAMING": ("gaming_video", "gaming video"),
    "PODCAST": ("podcast_or_long_interview", "podcast / long interview"),
}

_KNOWN_WORKS: tuple[tuple[str, str, str], ...] = (
    ("snatch", "Snatch", "Guy Ritchie"),
    ("goodfellas", "Goodfellas", "Martin Scorsese"),
    ("john wick", "John Wick", "Chad Stahelski"),
    ("scarface", "Scarface", "Brian De Palma"),
    ("the dark knight", "The Dark Knight", "Christopher Nolan"),
    ("inglourious basterds", "Inglourious Basterds", "Quentin Tarantino"),
    ("full metal jacket", "Full Metal Jacket", "Stanley Kubrick"),
    ("gangs of new york", "Gangs of New York", "Martin Scorsese"),
)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'&.-]{2,}")
_STOPWORDS = {
    "about", "again", "alice", "ambient", "because", "caption", "context",
    "direct", "george", "media", "observed", "playing", "reason", "route",
    "source", "status", "that", "this", "video", "watch", "with", "youtube",
}

_SELF_SHAZAM_CONTEXT_RE = re.compile(
    r"(?:"
    r"\bContext:\s*category\s*=[^\n]*|"
    r"\bprimary_category:\s*[^\n]*|"
    r"\bmedia_guess\s*=[^|\n]*|"
    r"\bacoustic_scene\s*=\s*[^;|\n]*|"
    r"\b(?:Science\s*&\s*Technology|Film\s*&\s*Animation|News\s*&\s*Politics|"
    r"Autos\s*&\s*Vehicles|Pets\s*&\s*Animals|Travel\s*&\s*Events|"
    r"People\s*&\s*Blogs|Howto\s*&\s*Style|Entertainment|Comedy|Gaming|Music|"
    r"Sports|Education)\s+source\s*:\s*[^|.\n]*|"
    r"\bsource\s*[:=]\s*(?:technology\s+interview\s*/\s*keynote|gaming|movie|"
    r"fiction|news|music|sports|podcast)[^;|\n]*|"
    r"\bSIFTA\s+Media\s+Shazam\b"
    r")",
    re.IGNORECASE,
)


def _clean_self_referential_focus(text: str) -> str:
    """Remove Shazam's own previous guess from focus text before scoring.

    Focus previews are valuable because they carry the visible YouTube title.
    They can also contain the currently open Shazam app's own category line:
    ``Context: category=Gaming; conf=...``. Feeding that back into the scorer
    creates a runaway loop where one wrong category becomes overwhelming proof.
    """
    return _SELF_SHAZAM_CONTEXT_RE.sub(" ", str(text or ""))


def _contains_term(text: str, term: str) -> bool:
    """Match category/source terms without substring bleed.

    The old scorer used raw substring checks, so ``compute`` matched
    ``computer speakers`` and helped mislabel a Goodfellas movie clip as
    Science & Technology. Multi-word phrases still use substring matching;
    single-token terms require token boundaries.
    """
    haystack = str(text or "").lower()
    needle = str(term or "").lower().strip()
    if not needle:
        return False
    if re.search(r"\s", needle):
        return needle in haystack
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None


def youtube_categories(*, include_legacy: bool = True) -> list[dict[str, Any]]:
    cats = [dict(c) for c in YOUTUBE_CATEGORIES if include_legacy or c.get("active")]
    return sorted(cats, key=lambda c: (not bool(c.get("active")), int(c["id"])))


def _tail_jsonl(path: Path, n: int = 128) -> list[dict[str, Any]]:
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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


def _text_parts(row: Mapping[str, Any]) -> list[str]:
    keys = (
        "title", "channel", "frontmost_window", "caption_excerpt", "page_context",
        "ask_panel_answer_excerpt", "content_kind", "content_category",
        "source_work", "director", "dialogue_boundary", "text_preview",
        "focus_preview", "reason", "url", "video_id", "scene",
    )
    out: list[str] = []
    for key in keys:
        if key == "scene" and str(row.get("source") or "") == "acoustic_scene_classifier":
            try:
                scene_conf = float(row.get("confidence", 0.0) or 0.0)
            except Exception:
                scene_conf = 0.0
            if scene_conf < 0.55:
                continue
        value = row.get(key)
        if isinstance(value, (list, tuple)):
            out.extend(_clean_self_referential_focus(x) if key == "focus_preview" else str(x) for x in value)
        elif value:
            text = _clean_self_referential_focus(value) if key == "focus_preview" else str(value)
            if text.strip():
                out.append(text)
    return out


def collect_media_evidence(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    window_s: float = 7200.0,
    limit: int = 96,
) -> list[dict[str, Any]]:
    """Collect bounded recent media receipts for category guessing."""
    root = Path(state_dir)
    now_ts = float(now if now is not None else time.time())
    evidence: list[dict[str, Any]] = []

    latest = _read_json(root / "youtube_context_latest.json")
    if latest:
        evidence.append({"source": "youtube_context_latest", **latest})

    sources = {
        "youtube_context": root / "youtube_context.jsonl",
        "youtube_watch_memory": root / "youtube_watch_memory.jsonl",
        "media_ingress_gate": root / "media_ingress_gate.jsonl",
        "media_session_memory": root / "media_session_memory.jsonl",
        "acoustic_scene_classifier": root / "acoustic_scene_classifications.jsonl",
    }
    for source, path in sources.items():
        for row in _tail_jsonl(path, limit):
            try:
                ts = float(row.get("ts", row.get("last_ts", 0.0)) or 0.0)
            except Exception:
                ts = 0.0
            if ts and now_ts - ts > window_s:
                continue
            evidence.append({"source": source, **row})

    # Keep newest rows last but preserve source labels.
    def _ts(row: Mapping[str, Any]) -> float:
        try:
            return float(row.get("ts", row.get("last_ts", 0.0)) or 0.0)
        except Exception:
            return 0.0

    return sorted(evidence, key=_ts)[-limit:]


def _blob_from_evidence(evidence: list[Mapping[str, Any]]) -> str:
    chunks: list[str] = []
    for row in evidence:
        chunks.extend(_text_parts(row))
    return " ".join(chunks)


def _score_categories(blob: str, evidence: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    low = blob.lower()
    scores: Counter[str] = Counter()
    terms: dict[str, set[str]] = {c["name"]: set() for c in YOUTUBE_CATEGORIES}
    known = _known_work(blob)
    if known:
        scores["Film & Animation"] += 8
        scores["Entertainment"] += 2
        terms["Film & Animation"].add(f"known_work:{known['source_work']}")
        terms["Entertainment"].add("known_work:fiction_media")
    latest_scene_row = next(
        (
            row
            for row in reversed(evidence)
            if str(row.get("source") or "") == "acoustic_scene_classifier"
            and str(row.get("scene") or "").upper() in _SCENE_CATEGORY_HINTS
        ),
        {},
    )

    for row in evidence:
        category = str(row.get("content_category") or "").strip()
        if category:
            scores[category] += 7
            terms.setdefault(category, set()).add("receipt:content_category")
        frame = str(row.get("reality_frame") or "").upper()
        if "FICTIONAL_MEDIA" in frame:
            scores["Film & Animation"] += 5
            terms["Film & Animation"].add("receipt:fictional_media")
        scene = str(row.get("scene") or "").upper()
        if row is latest_scene_row and scene in _SCENE_CATEGORY_HINTS:
            try:
                scene_conf = float(row.get("confidence", 0.0) or 0.0)
            except Exception:
                scene_conf = 0.0
            if scene_conf < 0.55:
                continue
            for idx, category in enumerate(_SCENE_CATEGORY_HINTS[scene]):
                scores[category] += 4.0 * scene_conf if idx == 0 else 1.5 * scene_conf
                terms.setdefault(category, set()).add(f"acoustic_scene:{scene}")
        title = str(row.get("title") or "")
        if title:
            title_low = title.lower()
            if any(x in title_low for x in ("scene", "clip", "movie", "film", "trailer")):
                scores["Film & Animation"] += 4
                scores["Entertainment"] += 2
                terms["Film & Animation"].add("title:clip/movie")

    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if _contains_term(low, kw):
                bump = 2 if " " in kw else 1
                scores[category] += bump
                terms.setdefault(category, set()).add(kw)

    rows: list[dict[str, Any]] = []
    for cat in youtube_categories(include_legacy=True):
        name = cat["name"]
        score = float(scores.get(name, 0.0))
        if score <= 0:
            continue
        rows.append(
            {
                "id": cat["id"],
                "name": name,
                "active": bool(cat.get("active")),
                "score": score,
                "evidence_terms": sorted(terms.get(name, set()))[:10],
            }
        )
    rows.sort(key=lambda r: (-float(r["score"]), not bool(r["active"]), r["name"]))
    return rows


def _source_guesses(blob: str) -> list[dict[str, Any]]:
    low = blob.lower()
    guesses: list[dict[str, Any]] = []
    for source_type, label, needles in _SOURCE_RULES:
        hits = [n for n in needles if _contains_term(low, n)]
        if not hits:
            continue
        guesses.append(
            {
                "source_type": source_type,
                "label": label,
                "score": float(len(hits)),
                "evidence_terms": hits[:8],
            }
        )
    guesses.sort(key=lambda g: (-float(g["score"]), g["source_type"]))
    return guesses


def _source_guesses_from_evidence(blob: str, evidence: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    guesses = _source_guesses(blob)
    existing = {g["source_type"] for g in guesses}
    row = next(
        (
            item
            for item in reversed(evidence)
            if str(item.get("source") or "") == "acoustic_scene_classifier"
            and str(item.get("scene") or "").upper() in _SCENE_SOURCE_HINTS
        ),
        {},
    )
    if row:
        scene = str(row.get("scene") or "").upper()
        source_type, label = _SCENE_SOURCE_HINTS[scene]
        try:
            scene_conf = float(row.get("confidence", 0.0) or 0.0)
        except Exception:
            scene_conf = 0.0
        if source_type not in existing and scene_conf >= 0.55:
            guesses.append(
                {
                    "source_type": source_type,
                    "label": label,
                    "score": scene_conf + 0.75,
                    "evidence_terms": [f"acoustic_scene:{scene}"],
                }
            )
            existing.add(source_type)
    guesses.sort(key=lambda g: (-float(g["score"]), g["source_type"]))
    return guesses


def _known_work(blob: str) -> dict[str, str]:
    low = blob.lower()
    for needle, work, director in _KNOWN_WORKS:
        if needle in low:
            return {"source_work": work, "director": director}
    return {}


def _evidence_terms(blob: str, limit: int = 18) -> list[str]:
    counts: Counter[str] = Counter()
    for token in _TOKEN_RE.findall(blob.lower()):
        token = token.strip("'&.-")
        if len(token) < 3 or token in _STOPWORDS:
            continue
        counts[token] += 1
    return [term for term, _count in counts.most_common(limit)]


def guess_media_identity(
    evidence: list[Mapping[str, Any]],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Return the current best media identity/category guess from receipts."""
    now_ts = float(now if now is not None else time.time())
    blob = _blob_from_evidence(evidence)
    categories = _score_categories(blob, evidence)
    sources = _source_guesses_from_evidence(blob, evidence)
    work = _known_work(blob)
    acoustic_scene = ""
    acoustic_scene_confidence = 0.0
    acoustic_scene_scores: dict[str, float] = {}
    for row in reversed(evidence):
        scene = str(row.get("scene") or "").upper()
        if not scene:
            continue
        try:
            acoustic_scene_confidence = float(row.get("confidence", 0.0) or 0.0)
        except Exception:
            acoustic_scene_confidence = 0.0
        acoustic_scene = scene if scene != "UNKNOWN" and acoustic_scene_confidence >= 0.55 else "UNKNOWN"
        scores = row.get("scores")
        if isinstance(scores, dict):
            acoustic_scene_scores = {
                str(k): float(v)
                for k, v in scores.items()
                if isinstance(v, (int, float))
            }
        break

    title = ""
    channel = ""
    video_id = ""
    url = ""
    for row in reversed(evidence):
        title = title or " ".join(str(row.get("title") or "").split())[:180]
        channel = channel or " ".join(str(row.get("channel") or "").split())[:120]
        video_id = video_id or str(row.get("video_id") or row.get("youtube_video_id") or "")[:64]
        url = url or str(row.get("url") or "")[:260]

    top = categories[0] if categories else {}
    second = categories[1] if len(categories) > 1 else {}
    top_score = float(top.get("score", 0.0) or 0.0)
    second_score = float(second.get("score", 0.0) or 0.0)
    confidence = 0.0
    if top_score:
        confidence = min(0.98, max(0.18, top_score / (top_score + second_score + 4.0)))

    source_top = sources[0] if sources else {}
    status = "guessed" if evidence and categories else ("no_category_signal" if evidence else "no_recent_media_evidence")
    return {
        "ts": now_ts,
        "truth_label": TRUTH_LABEL,
        "status": status,
        "primary_category": top.get("name", ""),
        "primary_category_id": top.get("id", ""),
        "confidence": round(confidence, 4),
        "category_candidates": categories[:8],
        "source_type": source_top.get("source_type", ""),
        "source_label": source_top.get("label", ""),
        "source_candidates": sources[:6],
        "acoustic_scene": acoustic_scene,
        "acoustic_scene_confidence": round(acoustic_scene_confidence, 4),
        "acoustic_scene_scores": acoustic_scene_scores,
        "title_guess": title,
        "channel_guess": channel,
        "video_id": video_id,
        "url": url,
        "evidence_terms": _evidence_terms(blob),
        "evidence_rows": len(evidence),
        "source_ledgers": sorted({str(row.get("source") or "") for row in evidence if row.get("source")}),
        "raw_audio_logged": False,
        "truth_note": (
            "Stigmergic media guess from local receipts. It may identify category, "
            "source family, or known work, but it is not a definitive acoustic catalog match."
        ),
        **work,
    }


def write_media_guess(
    row: Mapping[str, Any],
    *,
    state_dir: Path | str = STATE_DIR,
) -> dict[str, Any]:
    root = Path(state_dir)
    out = dict(row)
    root.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        root / "media_shazam_guesses.jsonl",
        json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latest = root / "media_shazam_latest.json"
    tmp = latest.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(latest)
    return out


def observe_current_media(
    *,
    state_dir: Path | str = STATE_DIR,
    now: float | None = None,
    window_s: float = 7200.0,
    write: bool = True,
) -> dict[str, Any]:
    evidence = collect_media_evidence(state_dir=state_dir, now=now, window_s=window_s)
    guess = guess_media_identity(evidence, now=now)
    if write:
        return write_media_guess(guess, state_dir=state_dir)
    return guess


def format_guess_for_prompt(row: Mapping[str, Any]) -> str:
    if not row or row.get("status") == "no_recent_media_evidence":
        return ""
    bits = [
        f"media_guess={row.get('primary_category') or 'unknown'}",
        f"confidence={row.get('confidence')}",
    ]
    if row.get("source_label"):
        bits.append(f"source={row.get('source_label')}")
    if row.get("title_guess"):
        bits.append(f"title={row.get('title_guess')}")
    if row.get("source_work"):
        bits.append(f"work={row.get('source_work')}")
    return " | ".join(bits)


if __name__ == "__main__":
    print(json.dumps(observe_current_media(), indent=2, ensure_ascii=False))
