#!/usr/bin/env python3
"""Browser stigmergic memory — Alice remembers the sites she visits, verified.

George 2026-05-30: inside her SIFTA browser, websites are categorized by the
site name; each entry keeps the link, the content description Alice learned by
comparing the on-screen image against the actual page text, and — if the owner
confirms it with her — a stronger, truth-verified memory. Stigmergic, unified
field, with truth-verification receipts.

This is the Cowork lane (Lane A of WISH_013): the pure ingest / categorize /
verify / recall core, file-backed and sandbox-testable. The live wiring (feed
it the Alice Browser snapshot + the screen-frame OCR) and the owner-confirmation
UI are sibling lanes verified on the M5.

The science behind the design
-----------------------------
* Schema theory (Bartlett 1932) + episodic→semantic consolidation
  (hippocampus→neocortex): categorize by site name (a schema); each visit is an
  episodic trace; revisits reinforce and consolidate the category. Strength
  decays like every other pheromone in the field.
* Source Monitoring Framework (Johnson & Raye): a memory carries NO built-in
  truth tag — truth is inferred from features (sensory/contextual agreement).
  So Alice grades each memory: did the on-screen image agree with the page
  text? Did the owner confirm it? Owner confirmation is the strongest source
  tag → highest trust. This is reality-monitoring, not faith.
* Stigmergy (Theraulaz & Bonabeau) + proof-of-work: the memory lives as
  append-only traces; the verification receipt is the cost-bearing proof that
  this memory was checked, not invented (§6 tool-truth).

Boundary (§4.2.2): when this organ runs on Alice's hardware it writes
truth-verification receipts (truth_label below). It does NOT mint STGM; real
STGM settlement comes only from Alice's economy organs. This module just grades
and records.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "browser_stigmergic_memory.jsonl"
FEATURE_LEDGER = STATE_DIR / "browser_site_feature_memory.jsonl"

TRUTH_LABEL = "BROWSER_STIGMERGIC_MEMORY_V1"
FEATURE_TRUTH_LABEL = "BROWSER_SITE_FEATURE_MEMORY_V1"

# Verification (source-monitoring) tiers, weakest → strongest.
V_UNVERIFIED = "UNVERIFIED"            # no image evidence to cross-check
V_MISMATCH = "IMAGE_TEXT_MISMATCH"     # image OCR disagreed with page text
V_IMAGE_MATCH = "IMAGE_TEXT_MATCH"     # image OCR agreed with page text
V_OWNER_CONFIRMED = "OWNER_CONFIRMED"  # the owner confirmed it with Alice

_AGREEMENT_MATCH_THRESHOLD = 0.30  # Jaccard of content words to call it a match


def _state_base(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _ledger(state_dir: Optional[Path | str]) -> Path:
    base = _state_base(state_dir)
    return base / "browser_stigmergic_memory.jsonl"


def _feature_ledger(state_dir: Optional[Path | str]) -> Path:
    base = _state_base(state_dir)
    return base / "browser_site_feature_memory.jsonl"


def categorize(url: str, title: str = "") -> str:
    """Category = the site name. Prefer the registrable host ('tiktok.com'),
    fall back to the title's site segment."""
    try:
        host = urlparse(url or "").netloc.lower()
    except Exception:
        host = ""
    host = re.sub(r"^www\.", "", host)
    if host:
        parts = host.split(".")
        # keep the last two labels for the common case (tiktok.com, bbc.co.uk→co.uk
        # is acceptable as a coarse category; site name is what the owner reads).
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    # No URL host — use the trailing segment of a 'caption | tag | Site' title.
    if title and "|" in title:
        return title.split("|")[-1].strip().lower()
    return (title or "unknown").strip().lower() or "unknown"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def agreement_score(screen_text: str, page_text: str) -> float:
    """Jaccard overlap of content words between the on-screen image OCR and the
    actual page text. 1.0 = identical vocabulary, 0.0 = disjoint."""
    a, b = _words(screen_text), _words(page_text)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return round(inter / union, 4) if union else 0.0


def verification_status(
    *, screen_text: Optional[str] = None, page_text: Optional[str] = None,
    owner_confirmed: bool = False,
) -> tuple[str, float]:
    """Grade the memory's truth tier (source monitoring). Returns (tier, score)."""
    if owner_confirmed:
        # Owner confirmation is the strongest source tag regardless of OCR.
        score = agreement_score(screen_text or "", page_text or "") if (screen_text and page_text) else 1.0
        return V_OWNER_CONFIRMED, score
    if screen_text and page_text:
        score = agreement_score(screen_text, page_text)
        return (V_IMAGE_MATCH if score >= _AGREEMENT_MATCH_THRESHOLD else V_MISMATCH), score
    return V_UNVERIFIED, 0.0


def record_visit(
    url: str,
    *,
    title: str = "",
    learned_description: str = "",
    screen_text: Optional[str] = None,
    page_text: Optional[str] = None,
    owner_confirmed: bool = False,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Record (or reinforce) a visit as a stigmergic memory trace."""
    ts = float(now if now is not None else time.time())
    category = categorize(url, title)
    tier, score = verification_status(
        screen_text=screen_text, page_text=page_text, owner_confirmed=owner_confirmed
    )
    prior = [r for r in _read_all(state_dir) if r.get("url") == url]
    visit_count = len(prior) + 1
    entry = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "category": category,
        "url": url,
        "title": title,
        "learned_description": learned_description,
        "verification": tier,
        "agreement_score": score,
        "owner_confirmed": bool(owner_confirmed),
        "visit_count": visit_count,
    }
    if write:
        path = _ledger(state_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    return entry


def _line_evidence(page_text: str, needles: tuple[str, ...]) -> list[str]:
    evidence: list[str] = []
    for raw in (page_text or "").splitlines():
        line = " ".join(raw.strip().split())
        if not line:
            continue
        folded = line.casefold()
        if any(n.casefold() in folded for n in needles):
            if line not in evidence:
                evidence.append(line[:180])
        if len(evidence) >= 4:
            break
    return evidence


def infer_site_features(
    url: str,
    *,
    title: str = "",
    page_text: str = "",
) -> list[dict[str, Any]]:
    """Infer reusable site features under the website category.

    These are "how to use this website" memories, not page summaries. Example:
    TikTok has a Search rail/input, and profile pages live at `/@handle`.
    """
    category = categorize(url, title)
    blob = f"{url}\n{title}\n{page_text}".casefold()
    features: list[dict[str, Any]] = []

    def add(name: str, label: str, description: str, evidence: tuple[str, ...]) -> None:
        if any(f["feature_name"] == name for f in features):
            return
        lines = _line_evidence(page_text, evidence)
        features.append(
            {
                "category": category,
                "feature_name": name,
                "label": label,
                "description": description,
                "evidence": lines or [e for e in evidence if e in blob][:3],
            }
        )

    if "search" in blob:
        if category == "tiktok.com":
            add(
                "search",
                "TikTok search",
                "TikTok exposes Search in the left rail / search input; use it to find accounts, videos, sounds, hashtags, and topics.",
                ("Search", "search"),
            )
        else:
            add(
                "search",
                "Site search",
                "This website exposes a search control; use it to find site-local content.",
                ("Search", "search"),
            )

    if category == "tiktok.com":
        if re.search(r"tiktok\.com/@[A-Za-z0-9._-]+", url or ""):
            add(
                "profile_page",
                "TikTok profile page",
                "TikTok creator profiles are addressed as /@handle and show the creator page, follower/like counts, and posted videos or collections.",
                ("Following", "Followers", "Likes", "Message", "@"),
            )
        if any(term in blob for term in ("followers", "likes", "following")):
            add(
                "profile_metrics",
                "TikTok profile metrics",
                "TikTok profile pages expose following, follower count, and likes; these are profile-level identity/context receipts.",
                ("Following", "Followers", "Likes"),
            )
        if "message" in blob:
            add(
                "message_button",
                "TikTok message button",
                "TikTok profiles can expose a Message button; use it as a visible affordance, not proof a message was sent.",
                ("Message",),
            )
        if re.search(r"\bbody check\s*\(\d+\)", page_text or "", re.IGNORECASE):
            add(
                "profile_collection_modal",
                "TikTok profile collection modal",
                "TikTok can open a creator collection/modal such as 'Body check (6)' listing multiple posts inside the profile.",
                ("Body check", "views"),
            )

    return features


def _read_feature_all(state_dir: Optional[Path | str]) -> list[dict[str, Any]]:
    path = _feature_ledger(state_dir)
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except Exception:
        return []
    return out


def record_site_features(
    url: str,
    *,
    title: str = "",
    page_text: str = "",
    screen_text: Optional[str] = None,
    owner_confirmed: bool = False,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> list[dict[str, Any]]:
    """Record reusable site features under their website category."""
    ts = float(now if now is not None else time.time())
    inferred = infer_site_features(url, title=title, page_text=page_text)
    tier, score = verification_status(
        screen_text=screen_text,
        page_text=page_text,
        owner_confirmed=owner_confirmed,
    )
    prior = _read_feature_all(state_dir)
    rows: list[dict[str, Any]] = []
    for feat in inferred:
        category = feat["category"]
        name = feat["feature_name"]
        observations = [
            r for r in prior
            if r.get("category") == category and r.get("feature_name") == name
        ]
        row = {
            "ts": ts,
            "truth_label": FEATURE_TRUTH_LABEL,
            "memory_kind": "site_feature",
            "category": category,
            "feature_name": name,
            "label": feat["label"],
            "description": feat["description"],
            "evidence": feat.get("evidence", []),
            "source_url": url,
            "title": title,
            "verification": tier,
            "agreement_score": score,
            "owner_confirmed": bool(owner_confirmed),
            "observation_count": len(observations) + 1,
        }
        rows.append(row)

    if write and rows:
        path = _feature_ledger(state_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    return rows


def record_snapshot_memory(
    *,
    url: str,
    title: str = "",
    page_text: str = "",
    screen_text: Optional[str] = None,
    owner_confirmed: bool = False,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Record both the visit and reusable site features from a browser snapshot."""
    clean_text = " ".join((page_text or "").split())
    if clean_text:
        learned = f"{title or categorize(url)}: {clean_text[:260]}"
    else:
        learned = f"{title or categorize(url)}: address/title receipt only; live body text not readable yet."
    visit = record_visit(
        url,
        title=title,
        learned_description=learned,
        screen_text=screen_text,
        page_text=page_text,
        owner_confirmed=owner_confirmed,
        now=now,
        state_dir=state_dir,
        write=write,
    )
    features = record_site_features(
        url,
        title=title,
        page_text=page_text,
        screen_text=screen_text,
        owner_confirmed=owner_confirmed,
        now=now,
        state_dir=state_dir,
        write=write,
    )
    if write and categorize(url, title) == "tiktok.com":
        try:
            from System.swarm_browser_site_playbook import record_search_from_url, seed_defaults

            seed_defaults(state_dir=state_dir)
            record_search_from_url(
                url,
                source="browser_snapshot",
                owner_confirmed=owner_confirmed,
                now=now,
                state_dir=state_dir,
            )
        except Exception:
            pass
    elif write:
        try:
            from System.swarm_browser_site_playbook import record_search_from_url

            record_search_from_url(
                url,
                source="browser_snapshot",
                owner_confirmed=owner_confirmed,
                now=now,
                state_dir=state_dir,
            )
        except Exception:
            pass
    return {"visit": visit, "features": features}


def confirm(url: str, *, state_dir: Optional[Path | str] = None,
            now: Optional[float] = None) -> dict[str, Any]:
    """Owner confirms a remembered site with Alice → upgrade to OWNER_CONFIRMED
    and write a confirmation trace (the strongest source tag)."""
    latest = latest_for_url(url, state_dir=state_dir)
    return record_visit(
        url,
        title=latest.get("title", "") if latest else "",
        learned_description=latest.get("learned_description", "") if latest else "",
        owner_confirmed=True,
        now=now,
        state_dir=state_dir,
    )


def _read_all(state_dir: Optional[Path | str]) -> list[dict[str, Any]]:
    path = _ledger(state_dir)
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out


def latest_for_url(url: str, *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    rows = [r for r in _read_all(state_dir) if r.get("url") == url]
    return rows[-1] if rows else {}


def recall(
    category: Optional[str] = None, *, state_dir: Optional[Path | str] = None
) -> dict[str, list[dict[str, Any]]]:
    """Recall memory grouped by site category. With ``category`` set, return
    just that category's entries (latest state per url). Returns
    {category: [entries...]} sorted by recency."""
    rows = _read_all(state_dir)
    # latest row per url carries the consolidated state (visit_count, best tier)
    by_url: dict[str, dict[str, Any]] = {}
    for r in rows:
        by_url[r.get("url", "")] = r
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in by_url.values():
        cat = entry.get("category", "unknown")
        grouped.setdefault(cat, []).append(entry)
    for cat in grouped:
        grouped[cat].sort(key=lambda e: float(e.get("ts", 0)), reverse=True)
    if category is not None:
        return {category: grouped.get(category, [])}
    return grouped


def recall_site_features(
    category: Optional[str] = None, *, state_dir: Optional[Path | str] = None
) -> dict[str, list[dict[str, Any]]]:
    """Recall latest reusable site features grouped by website category."""
    rows = _read_feature_all(state_dir)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("category") or "unknown"), str(row.get("feature_name") or ""))
        by_key[key] = row
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in by_key.values():
        cat = str(row.get("category") or "unknown")
        grouped.setdefault(cat, []).append(row)
    for cat in grouped:
        grouped[cat].sort(key=lambda r: str(r.get("feature_name") or ""))
    if category is not None:
        return {category: grouped.get(category, [])}
    return grouped


def site_category_prompt_block(
    category: Optional[str] = None,
    *,
    state_dir: Optional[Path | str] = None,
    max_categories: int = 3,
    max_features: int = 6,
) -> str:
    """Compact cortex block: how Alice has learned to use websites by category."""
    grouped = recall_site_features(category=category, state_dir=state_dir)
    if not grouped:
        return ""
    lines = ["BROWSER SITE CATEGORIES (Alice Browser learned features):"]
    count = 0
    for cat, features in sorted(grouped.items()):
        if not features:
            continue
        lines.append(f"- {cat}:")
        for feature in features[:max_features]:
            lines.append(
                f"  · {feature.get('label')}: {feature.get('description')} "
                f"(observed {feature.get('observation_count', 1)}x; {feature.get('verification')})"
            )
        count += 1
        if count >= max_categories:
            break
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "FEATURE_TRUTH_LABEL",
    "V_UNVERIFIED", "V_MISMATCH", "V_IMAGE_MATCH", "V_OWNER_CONFIRMED",
    "categorize", "agreement_score", "verification_status",
    "infer_site_features", "record_site_features", "record_snapshot_memory",
    "record_visit", "confirm", "latest_for_url", "recall",
    "recall_site_features", "site_category_prompt_block",
]
