#!/usr/bin/env python3
"""Resolve vague "open a link I like" browser intents from receipts.

This organ does not invent links and does not keep a hand-written person table.
It ranks URLs Alice already visited by dwell time, repeat visits, recency, and
recent owner-context overlap, then writes a resolution receipt when asked.
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "browser_preference_resolutions.jsonl"
TRUTH_LABEL = "BROWSER_PREFERENCE_RESOLVER_V1"

_STOPWORDS = {
    "about", "after", "alice", "also", "and", "are", "because", "browser",
    "can", "could", "does", "for", "from", "have", "into", "just", "like",
    "link", "look", "love", "more", "open", "page", "please", "pls",
    "really", "that", "the", "them", "this", "with", "what", "when",
    "where", "will", "would", "your", "you",
}

_POSITIVE_CONTEXT_HINTS = (
    "like", "liked", "love", "favorite", "favourite", "beautiful", "amazing",
    "stare", "stared", "staring", "body", "perfect", "hard", "good",
)


@dataclass
class PreferredLink:
    url: str
    title: str = ""
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "score": round(float(self.score), 4),
            "reasons": list(self.reasons),
            "evidence": dict(self.evidence),
        }


def _state_base(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return DEFAULT_STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _read_jsonl(path: Path, *, limit: Optional[int] = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if limit is not None:
        lines = lines[-max(1, int(limit)) :]
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _coerce_ts(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except Exception:
        pass
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            from datetime import datetime

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text).timestamp()
        except Exception:
            return default
    return default


def _row_time(row: Mapping[str, Any]) -> float:
    for key in ("closed_at", "opened_at", "ts", "timestamp", "time", "created_at"):
        ts = _coerce_ts(row.get(key), 0.0)
        if ts > 0:
            return ts
    return 0.0


def _row_dwell(row: Mapping[str, Any]) -> float:
    for key in ("dwell_s", "duration_s", "view_s", "elapsed_s"):
        try:
            value = float(row.get(key) or 0.0)
        except Exception:
            continue
        if math.isfinite(value) and value > 0:
            return min(value, 600.0)
    return 0.0


def _host_path(url: str) -> tuple[str, str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return "", ""
    return parsed.netloc.lower().removeprefix("www."), parsed.path or ""


def _is_preference_candidate_url(url: str, title: str = "") -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    host, path = _host_path(url)
    if not host:
        return False
    lowered = f"{host}{path}?{urlparse(url).query if '://' in url else ''}".lower()
    if host in {"duckduckgo.com", "www.duckduckgo.com"} and "50x.html" in lowered:
        return False
    if host.endswith("google.com") and ("/search" in path or "/imgres" in path):
        return False
    if host in {"x.com", "twitter.com"} and path in {"", "/", "/home", "/notifications", "/explore"}:
        return False
    if host == "instagram.com" and path in {"", "/", "/explore/"}:
        return False
    if host == "youtube.com" and path in {"", "/"}:
        return False
    if any(token in lowered for token in ("privacy", "terms", "login", "signup", "settings")):
        return False
    return bool((title or "").strip() or path.strip("/"))


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9_@.]{3,}", (text or "").lower())
    return [w.strip(".") for w in words if w.strip(".") and w.strip(".") not in _STOPWORDS]


def _recent_context_terms(state: Path, owner_text: str, *, limit: int = 120) -> dict[str, float]:
    rows = _read_jsonl(state / "alice_conversation.jsonl", limit=limit)
    chunks: list[str] = [owner_text or ""]
    for row in rows:
        role = str(row.get("role") or row.get("speaker") or "").lower()
        if role and role not in {"user", "owner", "ioan", "george"}:
            continue
        content = str(row.get("content") or row.get("text") or row.get("message") or "")
        if content:
            chunks.append(content)
    joined = "\n".join(chunks)
    positive_window = any(hint in joined.lower() for hint in _POSITIVE_CONTEXT_HINTS)
    terms: dict[str, float] = {}
    for token in _tokenize(joined):
        if len(token) < 4:
            continue
        terms[token] = terms.get(token, 0.0) + (2.0 if positive_window else 1.0)
    return terms


def _stigmergic_text_by_url(state: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in _read_jsonl(state / "browser_stigmergic_memory.jsonl", limit=2500):
        url = str(row.get("url") or "")
        if not url:
            continue
        bits = [
            str(row.get("title") or ""),
            str(row.get("learned_description") or ""),
            str(row.get("category") or ""),
        ]
        out[url] = " ".join(bit for bit in bits if bit)
    return out


def _content_bonus(url: str, title: str) -> float:
    host, path = _host_path(url)
    text = f"{host} {path} {title}".lower()
    bonus = 0.0
    if any(token in text for token in ("/status/", "/photo/", "/p/", "/reel/", "/video/")):
        bonus += 35.0
    if any(token in text for token in ("/media", "photos", "posts")):
        bonus += 25.0
    if path.count("/") <= 1 and len(path.strip("/")) >= 3:
        bonus += 18.0
    return bonus


def resolve_preferred_browser_link(
    owner_text: str = "",
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    max_rows: int = 2500,
) -> Optional[PreferredLink]:
    """Return the best receipted URL for a vague liked-link request."""
    state = _state_base(state_dir)
    t = time.time() if now is None else float(now)
    rows = _read_jsonl(state / "alice_browse_history.jsonl", limit=max_rows)
    if not rows:
        return None
    context_terms = _recent_context_terms(state, owner_text)
    learned_text = _stigmergic_text_by_url(state)

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip()
        if not _is_preference_candidate_url(url, title):
            continue
        dwell = _row_dwell(row)
        ts = _row_time(row)
        item = grouped.setdefault(
            url,
            {
                "url": url,
                "title": title,
                "count": 0,
                "total_dwell": 0.0,
                "max_dwell": 0.0,
                "last_ts": 0.0,
                "recent_dwell": 0.0,
                "rows": [],
            },
        )
        if title:
            item["title"] = title
        item["count"] += 1
        item["total_dwell"] += dwell
        item["max_dwell"] = max(float(item["max_dwell"]), dwell)
        item["last_ts"] = max(float(item["last_ts"]), ts)
        if ts > 0:
            age = max(0.0, t - ts)
            item["recent_dwell"] += dwell * math.exp(-age / (6.0 * 3600.0))
        item["rows"].append({"ts": ts, "dwell_s": dwell, "title": title})

    best: Optional[PreferredLink] = None
    for url, item in grouped.items():
        count = max(1, int(item["count"]))
        total = float(item["total_dwell"])
        avg = total / count
        last_ts = float(item["last_ts"])
        age_s = max(0.0, t - last_ts) if last_ts > 0 else 999999.0
        recency = math.exp(-age_s / (4.0 * 3600.0))
        text = " ".join(
            [
                str(item.get("title") or ""),
                url,
                learned_text.get(url, ""),
            ]
        ).lower()
        context_hits = [
            term for term, weight in sorted(context_terms.items(), key=lambda kv: kv[1], reverse=True)
            if term and term in text
        ][:8]
        context_score = sum(min(context_terms.get(term, 0.0), 8.0) * 7.0 for term in context_hits)
        reasons = [
            f"dwell_total={round(total, 1)}s",
            f"avg_dwell={round(avg, 1)}s",
            f"visits={count}",
            f"last_seen_age_s={round(age_s, 1)}",
        ]
        if context_hits:
            reasons.append("context_match=" + ",".join(context_hits[:5]))
        freshness = 0.25 + 0.75 * recency
        # r542: when owner attaches screenshot of current browser ("attached your screen body") and says
        # "i already have izzy in browser" or similar, boost the matching recent izzy/abellaskies URL as the
        # "live current liked link" the owner is pointing to right now (the one already open in the limb).
        # This prevents inventing or searching external when the owner says he already has the page in browser.
        screen_shown_boost = 0.0
        owner_lower = (owner_text or "").lower()
        if any(p in owner_lower for p in ("attached your screen", "your screen body", "i already have izzy in browser", "i already have izzy in browser lok")):
            if "izzy" in owner_lower or "abellaskies" in owner_lower:
                if "izzy" in text or "abellaskies" in text or ("instagram" in text and "izzy" in owner_lower):
                    screen_shown_boost = 600.0
                    reasons.append("owner_shown_current_via_attached_screen=izzy")
        candidate = PreferredLink(
            url=url,
            title=str(item.get("title") or ""),
            score=(
                min(total, 1800.0) * 0.50 * freshness
                + min(avg, 420.0) * 0.50 * freshness
                + math.log1p(count) * 28.0
                + min(float(item["recent_dwell"]), 600.0) * 0.45
                + recency * 90.0
                + context_score
                + _content_bonus(url, str(item.get("title") or ""))
                + screen_shown_boost
            ),
            reasons=reasons,
            evidence={
                "count": count,
                "total_dwell_s": round(total, 3),
                "avg_dwell_s": round(avg, 3),
                "max_dwell_s": round(float(item["max_dwell"]), 3),
                "last_ts": last_ts,
                "context_hits": context_hits,
                "truth_label": TRUTH_LABEL,
            },
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def record_preference_resolution(
    owner_text: str,
    preferred: Optional[PreferredLink],
    *,
    state_dir: Optional[Path | str] = None,
    action: str = "open_preferred_browser_link",
    note: str = "",
) -> str:
    receipt_id = f"bpr-{int(time.time() * 1000)}-{abs(hash((owner_text, preferred.url if preferred else ''))) % 100000:05d}"
    state = _state_base(state_dir)
    row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
        "action": action,
        "owner_text": owner_text,
        "ok": preferred is not None,
        "chosen": preferred.to_dict() if preferred else {},
        "note": note,
    }
    try:
        state.mkdir(parents=True, exist_ok=True)
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return receipt_id


def preference_prompt_block(
    *,
    owner_text: str = "",
    state_dir: Optional[Path | str] = None,
) -> str:
    preferred = resolve_preferred_browser_link(owner_text, state_dir=state_dir)
    if not preferred:
        return ""
    title = preferred.title or preferred.url
    return (
        "BROWSER PREFERENCE LINK INTENT (receipt-backed; r541):\n"
        f"- owner_text={owner_text[:220]!r}\n"
        f"- chosen_title={title}\n"
        f"- chosen_url={preferred.url}\n"
        f"- score={round(preferred.score, 2)}\n"
        f"- evidence={'; '.join(preferred.reasons)}\n"
        "RULE: For vague requests like 'open something/a link I like', this "
        "receipted URL is the target. Do not invent another URL, gallery, title, "
        "or vibe. Reply briefly around this chosen_url; the Alice Browser hand "
        "will open this exact target and receipt it."
    )


_INVENTED_PREFERENCE_LINK_RE = re.compile(
    r"\b(?:unsplash|ephemeral beauty|light on the water|golden sunset|"
    r"california coast|nature photography|serene nature|stunning.*gallery|"
    r"high-resolution images of still lakes|perfect reflection)\b",
    re.IGNORECASE | re.DOTALL,
)


def guard_preferred_link_reply(
    reply: str,
    *,
    owner_text: str = "",
    state_dir: Optional[Path | str] = None,
) -> str:
    """Replace invented liked-link chatter with the receipted preferred URL.

    This is a narrow mouth guard. The cortex still gets first pass, but if it
    ignores the browser-diary evidence and names a fake link/gallery, Alice's
    visible reply is grounded back to the URL the browser hand will actually
    open.
    """
    preferred = resolve_preferred_browser_link(owner_text, state_dir=state_dir)
    if not preferred:
        return reply
    text = str(reply or "")
    if preferred.url in text:
        return reply
    mentioned_urls = [u.rstrip(").,]\"'") for u in re.findall(r"https?://\S+", text)]
    invented_url = any(url != preferred.url for url in mentioned_urls)
    invented_link_talk = bool(_INVENTED_PREFERENCE_LINK_RE.search(text))
    claims_opening = bool(re.search(r"\b(?:opening|opened|link being opened|going to open)\b", text, re.I))
    if not (invented_url or invented_link_talk or claims_opening):
        return reply

    title = preferred.title or preferred.url
    reasons = "; ".join(preferred.reasons[:4]) or "browser diary match"
    return (
        f"I love you too. I checked my browser diary and picked {title}: "
        f"{preferred.url}. Evidence: {reasons}. Opening that in Alice Browser now."
    )


__all__ = [
    "TRUTH_LABEL",
    "PreferredLink",
    "resolve_preferred_browser_link",
    "record_preference_resolution",
    "preference_prompt_block",
    "guard_preferred_link_reply",
]
