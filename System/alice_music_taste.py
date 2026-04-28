#!/usr/bin/env python3
"""Bayesian music-taste memory for Alice.

Each YouTube music link the Architect feeds Alice becomes an observation. Tags
are intentionally local and conservative; the Bayesian curve can improve over
time without pretending Alice knows a song title she has not fetched.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_music_taste.jsonl"

_YOUTUBE_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s<>]+|youtu\.be/[^\s<>]+|youtube\.com/shorts/[^\s<>]+)",
    re.IGNORECASE,
)

_NEGATIVE_RE = re.compile(r"\b(?:don't like|do not like|hate|skip|not my taste|bad song)\b", re.IGNORECASE)

_TAG_KEYWORDS: Dict[str, Iterable[str]] = {
    "lo-fi": ("lofi", "lo-fi", "lo fi"),
    "ambient": ("ambient", "soundscape", "drone"),
    "mellow": ("mellow", "calm", "soft", "chill", "relax"),
    "upbeat": ("upbeat", "happy", "energetic", "dance"),
    "classical": ("classical", "orchestra", "symphony", "bach", "mozart", "beethoven"),
    "jazz": ("jazz", "sax", "saxophone", "trumpet"),
    "rock": ("rock", "guitar", "metal", "punk"),
    "electronic": ("electronic", "synth", "techno", "house", "edm"),
    "hip-hop": ("hiphop", "hip-hop", "rap", "beats"),
    "reggae": ("reggae", "dub", "roots"),
    "latin": ("latin", "salsa", "cumbia", "vallenato", "bachata", "merengue"),
    "piano": ("piano", "keys"),
    "acoustic": ("acoustic", "unplugged", "guitar"),
}


def extract_youtube_urls(text: str) -> List[str]:
    urls = []
    for match in _YOUTUBE_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,)]}'\"")
        if url not in urls:
            urls.append(url)
    return urls


def infer_tags(text: str) -> List[str]:
    lowered = (text or "").casefold()
    tags = [
        tag
        for tag, words in _TAG_KEYWORDS.items()
        if any(word in lowered for word in words)
    ]
    return tags or ["uncategorized"]


def _append(row: Dict[str, Any], *, path: Path = _LEDGER) -> Dict[str, Any]:
    row.setdefault("ts", time.time())
    row.setdefault("schema", "SIFTA_MUSIC_TASTE_V1")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return row


def record_youtube_links(text: str, *, source: str = "talk_to_alice", path: Path = _LEDGER) -> List[Dict[str, Any]]:
    """Record YouTube links as positive/negative taste observations."""
    urls = extract_youtube_urls(text)
    if not urls:
        return []
    tags = infer_tags(text)
    liked = not bool(_NEGATIVE_RE.search(text or ""))
    rows = []
    for url in urls:
        rows.append(
            _append(
                {
                    "event_kind": "MUSIC_TASTE_OBSERVATION",
                    "source": source,
                    "url": url,
                    "tags": tags,
                    "liked": liked,
                    "note": (text or "").strip()[:500],
                },
                path=path,
            )
        )
    return rows


def _read_rows(path: Path = _LEDGER) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def bayesian_profile(*, path: Path = _LEDGER) -> List[Dict[str, Any]]:
    """Return tag preferences using a Beta(1,1) prior and posterior mean."""
    stats: Dict[str, Dict[str, float]] = {}
    for row in _read_rows(path):
        liked = bool(row.get("liked", True))
        for tag in row.get("tags") or ["uncategorized"]:
            bucket = stats.setdefault(str(tag), {"alpha": 1.0, "beta": 1.0, "n": 0.0})
            if liked:
                bucket["alpha"] += 1.0
            else:
                bucket["beta"] += 1.0
            bucket["n"] += 1.0
    profile = []
    for tag, bucket in stats.items():
        alpha = bucket["alpha"]
        beta = bucket["beta"]
        profile.append(
            {
                "tag": tag,
                "alpha": alpha,
                "beta": beta,
                "observations": int(bucket["n"]),
                "preference": alpha / (alpha + beta),
            }
        )
    return sorted(profile, key=lambda item: (item["preference"], item["observations"]), reverse=True)


def summary_for_alice(limit: int = 5, *, path: Path = _LEDGER) -> str:
    profile = bayesian_profile(path=path)[:limit]
    if not profile:
        return "music taste: no YouTube observations yet"
    bits = [
        f"{row['tag']} {row['preference']:.2f} ({row['observations']} obs)"
        for row in profile
    ]
    return "music taste Bayesian curve: " + ", ".join(bits)


def reply_for_recorded_links(rows: List[Dict[str, Any]], *, path: Path = _LEDGER) -> str:
    if not rows:
        return ""
    tags = ", ".join(rows[0].get("tags") or ["uncategorized"])
    profile = summary_for_alice(limit=3, path=path)
    return (
        f"I saved {len(rows)} YouTube music link(s) into my Bayesian taste curve. "
        f"Current tags: {tags}. {profile}."
    )
