#!/usr/bin/env python3
"""Concept birth human anchors — one primary human per deep product/concept.

George (2026-06-19 r1325): every concept that is a real product/company/app should
resolve to a verified human birth anchor (Gabriel Weinberg ↔ DuckDuckGo, Vlad Tenev
↔ Robinhood app, Mark Zuckerberg ↔ Facebook). Myth/folklore anchors are separate
collision rows — not the fintech app, not the search engine.

George (2026-06-19 r1345) temporal-pin doctrine (`ARCHITECT_DOCTRINE`):
A fuzzy world-concept ("America", "AI", "the war") can mean many eras and stories.
Naming a real human birth/temporal pin ("George Washington", "Gabriel Weinberg")
collapses time and topic so swimmers travel through history on receipts, not myth.
The person does not replace the concept — they disambiguate *which* conversation
epoch is live. No owner Q&A required; anchors are stigmergic rows, not memory myth.

Truth label: CONCEPT_HUMAN_ANCHOR_V1
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

TRUTH_LABEL = "CONCEPT_HUMAN_ANCHOR_V1"
SCHEMA = "CONCEPT_HUMAN_ANCHOR_ROW_V1"
SOURCE_ANCHORED_LABEL = "SOURCE_ANCHORED"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "concept_human_anchors.jsonl"

# r1349 — tournament + repo-scan receipts backing founder anchors (not cortex myth).
_SOURCE_RECEIPTS: dict[str, tuple[str, ...]] = {
    "Gabriel Weinberg": (
        "CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",
        "CURSOR_PROMPT_R1343_REPO_SCAN_CURSOR_WORKLOAD.md:64",
    ),
    "Mark Zuckerberg": ("CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",),
    "Vlad Tenev": ("CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",),
    "Aravind Srinivas": ("CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",),
    "Evan Schwartz": (
        "CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",
        "CURSOR_PROMPT_R1343_REPO_SCAN_CURSOR_WORKLOAD.md:64",
    ),
}

# Seed anchors — primary birth human + optional cofounders/collisions.
_SEED: tuple[dict[str, Any], ...] = (
    {
        "concept_id": "duckduckgo_search_engine",
        "surface_phrases": ("duckduckgo", "duck duck go", "ddg"),
        "concept_type": "search_engine_company",
        "primary_birth_anchor": {
            "human_name": "Gabriel Weinberg",
            "role": "founder",
            "truth_label": SOURCE_ANCHORED_LABEL,
            "source_receipts": list(_SOURCE_RECEIPTS["Gabriel Weinberg"]),
        },
        "secondary_anchors": [],
        "collision_anchors": [
            {
                "human_name": "Daffy Duck",
                "role": "mythic_brand_collision",
                "note": "cartoon mascot wordplay only — not the company founder",
            },
            {
                "human_name": "Evan Schwartz",
                "role": "common_name_collision_not_founder",
                "note": "NOT DuckDuckGo founder — Gabriel Weinberg holds the birth anchor",
                "truth_label": SOURCE_ANCHORED_LABEL,
                "source_receipts": list(_SOURCE_RECEIPTS["Evan Schwartz"]),
            },
        ],
        "confidence": 0.85,
    },
    {
        "concept_id": "google_search_company",
        "surface_phrases": ("google", "alphabet google search"),
        "concept_type": "search_engine_company",
        "primary_birth_anchor": {
            "human_name": "Larry Page",
            "role": "cofounder_primary_origin",
            "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
            "source_receipts": [],
        },
        "secondary_anchors": [
            {
                "human_name": "Sergey Brin",
                "role": "cofounder",
                "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
                "source_receipts": [],
            }
        ],
        "collision_anchors": [],
        "confidence": 0.55,
        "cofounder_ambiguity": True,
    },
    {
        "concept_id": "facebook_social_network",
        "surface_phrases": ("facebook", "meta facebook"),
        "concept_type": "social_network_company",
        "primary_birth_anchor": {
            "human_name": "Mark Zuckerberg",
            "role": "founder",
            "truth_label": SOURCE_ANCHORED_LABEL,
            "source_receipts": list(_SOURCE_RECEIPTS["Mark Zuckerberg"]),
        },
        "secondary_anchors": [],
        "collision_anchors": [],
        "confidence": 0.85,
    },
    {
        "concept_id": "robinhood_fintech_app",
        "surface_phrases": (
            "robinhood app",
            "robinhood markets",
            "robinhood brokerage",
            "robinhood trading",
        ),
        "concept_type": "fintech_app_company",
        "primary_birth_anchor": {
            "human_name": "Vlad Tenev",
            "role": "cofounder_primary_origin",
            "truth_label": SOURCE_ANCHORED_LABEL,
            "source_receipts": list(_SOURCE_RECEIPTS["Vlad Tenev"]),
        },
        "secondary_anchors": [
            {
                "human_name": "Baiju Bhatt",
                "role": "cofounder",
                "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
                "source_receipts": [],
            }
        ],
        "collision_anchors": [
            {
                "human_name": "Robin Hood",
                "role": "folklore_literary_anchor",
                "note": "myth/fairytale figure — not the Robinhood fintech app",
            }
        ],
        "confidence": 0.55,
        "cofounder_ambiguity": True,
    },
    {
        "concept_id": "perplexity_ai_search",
        "surface_phrases": ("perplexity", "perplexity ai", "perplexity.ai"),
        "concept_type": "search_engine_company",
        "primary_birth_anchor": {
            "human_name": "Aravind Srinivas",
            "role": "cofounder_ceo_primary_origin",
            "truth_label": SOURCE_ANCHORED_LABEL,
            "source_receipts": list(_SOURCE_RECEIPTS["Aravind Srinivas"]),
        },
        "secondary_anchors": [
            {
                "human_name": "Johnny Ho",
                "role": "cofounder",
                "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
                "source_receipts": [],
            },
            {
                "human_name": "Denis Yarats",
                "role": "cofounder",
                "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
                "source_receipts": [],
            },
        ],
        "collision_anchors": [],
        "confidence": 0.5,
        "cofounder_ambiguity": True,
    },
    {
        "concept_id": "america_nation_concept",
        "surface_phrases": ("america", "united states", "usa", "u.s.", "u.s.a."),
        "concept_type": "fuzzy_place_concept",
        "fuzzy_concept": True,
        "temporal_epoch_pin": {
            "pin_human": "George Washington",
            "era_label": "American Revolutionary War / founding era (circa 1775–1797)",
            "doctrine": (
                "Place-name alone is ambiguous across centuries; default temporal pin "
                "collapses the conversation epoch without asking the owner."
            ),
        },
        "primary_birth_anchor": {
            "human_name": "George Washington",
            "role": "default_temporal_epoch_pin",
            "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
            "source_receipts": [],
        },
        "collision_anchors": [
            {
                "human_name": "Amerigo Vespucci",
                "role": "namesake_etymology_collision",
                "note": "continent name origin — not the same as the modern nation concept",
            }
        ],
        "confidence": 0.45,
    },
    {
        "concept_id": "george_washington_temporal_pin",
        "surface_phrases": (
            "george washington",
            "president washington",
            "general washington",
        ),
        "concept_type": "temporal_epoch_pin_human",
        "temporal_epoch_pin": {
            "pin_human": "George Washington",
            "era_label": "American Revolutionary War / first U.S. presidency (circa 1775–1797)",
            "doctrine": "Naming this human pins time; conversation is about that epoch unless receipts say otherwise.",
        },
        "primary_birth_anchor": {
            "human_name": "George Washington",
            "role": "temporal_epoch_pin",
            "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
            "source_receipts": [],
        },
        "disambiguates_concepts": ("america", "united states", "revolutionary war"),
        "collision_anchors": [],
        "confidence": 0.5,
    },
    # r1614 George morning doctrine: history concepts need epoch + unique people
    # ("swimmers" in human time — one Einstein, one Troy war horizon, not free myth).
    {
        "concept_id": "trojan_war_myth_history",
        "surface_phrases": (
            "trojan war",
            "troy war",
            "siege of troy",
            "trojan horse",
            "iliad troy",
        ),
        "concept_type": "history_epoch_concept",
        "fuzzy_concept": True,
        "temporal_epoch_pin": {
            "pin_human": "Homer (tradition) / Late Bronze Age archaeology",
            "era_label": "Late Bronze Age Aegean (archaeology often ~12th–13th c. BCE) + later Greek epic tradition",
            "doctrine": (
                "r1614: mythology talk still needs a time pin — archaeology horizon "
                "vs epic composition are different epochs; name which one is live."
            ),
        },
        "primary_birth_anchor": {
            "human_name": "Homer",
            "role": "epic_tradition_pin_not_eye_witness",
            "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
            "source_receipts": [],
        },
        "collision_anchors": [
            {
                "human_name": "Heinrich Schliemann",
                "role": "archaeology_excavator_collision",
                "note": "19th c. excavator of Hisarlik — not a Trojan War participant",
            }
        ],
        "confidence": 0.4,
    },
    {
        "concept_id": "albert_einstein_physics",
        "surface_phrases": ("einstein", "albert einstein", "relativity einstein"),
        "concept_type": "history_unique_person_swimmer",
        "temporal_epoch_pin": {
            "pin_human": "Albert Einstein",
            "era_label": "early–mid 20th century physics (special/general relativity era ~1905–1915+)",
            "doctrine": "Unique human history swimmer — one Einstein; pins physics talk to that century unless receipts say otherwise.",
        },
        "primary_birth_anchor": {
            "human_name": "Albert Einstein",
            "role": "unique_person_epoch_pin",
            "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
            "source_receipts": [],
        },
        "collision_anchors": [],
        "confidence": 0.55,
    },
    {
        "concept_id": "donald_trump_political_figure",
        "surface_phrases": ("donald trump", "trump", "president trump"),
        "concept_type": "history_unique_person_swimmer",
        "temporal_epoch_pin": {
            "pin_human": "Donald Trump",
            "era_label": "early 21st century U.S. politics (2016+ public figure / presidency eras)",
            "doctrine": "Unique person swimmer — pins which political epoch is live; not interchangeable with other presidents.",
        },
        "primary_birth_anchor": {
            "human_name": "Donald Trump",
            "role": "unique_person_epoch_pin",
            "truth_label": "HYPOTHESIS_UNTIL_SOURCE_VERIFIED",
            "source_receipts": [],
        },
        "collision_anchors": [],
        "confidence": 0.5,
    },
)

_FOUNDER_QUERY_RE = re.compile(
    r"\b(?:who\s+(?:founded|started|created|built)|founder\s+of|birth\s+anchor\s+for)\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _row_for_phrase(phrase: str) -> Optional[dict[str, Any]]:
    target = _normalize_phrase(phrase)
    if not target:
        return None
    best: Optional[dict[str, Any]] = None
    best_len = -1
    for seed in _SEED:
        for surface in seed.get("surface_phrases") or ():
            surface_norm = _normalize_phrase(str(surface))
            if not surface_norm:
                continue
            if target == surface_norm or surface_norm in target or target in surface_norm:
                if len(surface_norm) > best_len:
                    best = seed
                    best_len = len(surface_norm)
    if best is None:
        return None
    row = dict(best)
    row["schema"] = SCHEMA
    row["truth_label"] = TRUTH_LABEL
    row["matched_phrase"] = phrase
    return row


def resolve_concept_anchor(
    phrase: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Resolve a product/concept phrase to its primary human birth anchor."""
    _ = _state_dir(state_dir)
    return _row_for_phrase(phrase)


def resolve_concept_anchors(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Resolve every known concept mention in conversational order.

    A turn can move from Troy to Einstein to present-day politics. Returning
    only one best match loses that subject transition, so this keeps one row
    per concept and records where its first explicit surface appeared.
    """
    _ = _state_dir(state_dir)
    q = str(text or "")
    if not q.strip():
        return []
    matches: list[tuple[int, int, dict[str, Any]]] = []
    for seed_index, seed in enumerate(_SEED):
        best: Optional[tuple[int, str]] = None
        for surface in seed.get("surface_phrases") or ():
            surface_s = str(surface or "").strip()
            if not surface_s:
                continue
            hit = re.search(
                r"(?<!\w)" + re.escape(surface_s) + r"(?!\w)",
                q,
                re.IGNORECASE,
            )
            if hit is None:
                continue
            candidate = (hit.start(), surface_s)
            if best is None or candidate[0] < best[0] or (
                candidate[0] == best[0] and len(candidate[1]) > len(best[1])
            ):
                best = candidate
        if best is None:
            continue
        row = dict(seed)
        row["schema"] = SCHEMA
        row["truth_label"] = TRUTH_LABEL
        row["matched_phrase"] = best[1]
        row["mention_index"] = best[0]
        matches.append((best[0], seed_index, row))
    matches.sort(key=lambda item: (item[0], item[1]))
    return [row for _, _, row in matches]


def resolve_concept_from_url(url: str) -> Optional[dict[str, Any]]:
    """Map a browser URL host to a concept anchor when known."""
    try:
        host = urlparse((url or "").strip()).netloc.lower()
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    host_map = {
        "duckduckgo.com": "duckduckgo",
        "google.com": "google",
        "facebook.com": "facebook",
        "robinhood.com": "robinhood app",
        "perplexity.ai": "perplexity",
    }
    phrase = host_map.get(host)
    if not phrase:
        return None
    return resolve_concept_anchor(phrase)


def _append_ledger(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def answer_concept_temporal_pin_query(
    query_text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Reflex when a fuzzy concept or temporal-pin human is named (not a search command)."""
    q = query_text or ""
    if not q.strip():
        return ""
    if _FOUNDER_QUERY_RE.search(q):
        return ""
    if re.search(r"\bSEARCH\s+ON\b", q, re.IGNORECASE):
        return ""
    best: Optional[dict[str, Any]] = None
    best_len = -1
    for seed in _SEED:
        if not (seed.get("temporal_epoch_pin") or seed.get("fuzzy_concept")):
            continue
        for surface in seed.get("surface_phrases") or ():
            surface_s = str(surface)
            if re.search(r"\b" + re.escape(surface_s) + r"\b", q, re.IGNORECASE):
                if len(surface_s) > best_len:
                    row = resolve_concept_anchor(surface_s, state_dir=state_dir)
                    if row:
                        best = row
                        best_len = len(surface_s)
    if not best:
        return ""
    primary = best.get("primary_birth_anchor") or {}
    name = str(primary.get("human_name") or "").strip()
    temporal = best.get("temporal_epoch_pin") or {}
    era = str(temporal.get("era_label") or "").strip()
    if not name and not era:
        return ""
    parts = [
        f"Concept temporal pin for {best.get('matched_phrase') or 'this topic'}:",
    ]
    if name:
        parts.append(f"human pin = {name} ({primary.get('role') or 'anchor'}).")
    if era:
        parts.append(f"era collapsed to: {era}.")
    if best.get("fuzzy_concept"):
        parts.append(
            "The place/concept name alone is fuzzy; this pin selects which history lane is live."
        )
    parts.append(f"Truth label: {primary.get('truth_label') or TRUTH_LABEL}.")
    reply = " ".join(parts)
    _append_ledger(
        {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "kind": "temporal_pin_query_answer",
            "query": q[:300],
            "concept_id": best.get("concept_id"),
            "primary_human": name,
            "era_label": era,
            "ts": time.time(),
        },
        state_dir=state_dir,
    )
    return reply


def answer_concept_founder_query(
    query_text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Reflex answer for founder/birth-anchor questions from seed ledger only."""
    q = query_text or ""
    if not _FOUNDER_QUERY_RE.search(q):
        return ""
    concept_phrase = ""
    m = re.search(
        r"\b(?:founded|started|created|built)\s+(.+?)(?:\?|$)",
        q,
        re.IGNORECASE,
    )
    if m:
        concept_phrase = m.group(1).strip(" ?'\"")
    if not concept_phrase:
        m2 = re.search(r"\bfounder\s+of\s+(.+?)(?:\?|$)", q, re.IGNORECASE)
        if m2:
            concept_phrase = m2.group(1).strip(" ?'\"")
    if not concept_phrase:
        for seed in _SEED:
            for surface in seed.get("surface_phrases") or ():
                if re.search(r"\b" + re.escape(str(surface)) + r"\b", q, re.IGNORECASE):
                    concept_phrase = str(surface)
                    break
            if concept_phrase:
                break
    row = resolve_concept_anchor(concept_phrase, state_dir=state_dir)
    if not row:
        return ""
    primary = row.get("primary_birth_anchor") or {}
    name = str(primary.get("human_name") or "").strip()
    if not name:
        return ""
    collisions = row.get("collision_anchors") or []
    secondary = row.get("secondary_anchors") or []
    parts = [
        f"Concept birth anchor receipt for {row.get('matched_phrase') or concept_phrase}: "
        f"primary human = {name} ({primary.get('role') or 'founder'}).",
    ]
    if secondary:
        others = ", ".join(str(s.get("human_name") or "") for s in secondary if s.get("human_name"))
        if others:
            parts.append(f"Cofounder anchors preserved: {others}.")
    if row.get("cofounder_ambiguity"):
        parts.append(
            "Cofounder ambiguity is preserved — I do not force false single-founder certainty without source receipts."
        )
    if collisions:
        myth = ", ".join(
            str(c.get("human_name") or "") for c in collisions if c.get("human_name")
        )
        if myth:
            parts.append(f"Separate myth/collision anchors (not this product): {myth}.")
    temporal = row.get("temporal_epoch_pin") or {}
    era = str(temporal.get("era_label") or "").strip()
    if era:
        parts.append(
            f"Temporal epoch pin: {temporal.get('pin_human') or name} → {era} "
            "(fuzzy concept collapsed to a travelable history lane)."
        )
    if row.get("fuzzy_concept"):
        parts.append(
            "This concept is fuzzy alone; the human pin selects which era/topic is live."
        )
    receipts = primary.get("source_receipts") or []
    if receipts:
        parts.append(f"Source receipts: {', '.join(str(r) for r in receipts[:4])}.")
    parts.append(f"Truth label: {primary.get('truth_label') or TRUTH_LABEL}.")
    reply = " ".join(parts)
    _append_ledger(
        {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "kind": "founder_query_answer",
            "query": q[:300],
            "concept_id": row.get("concept_id"),
            "primary_human": name,
            "ts": time.time(),
        },
        state_dir=state_dir,
    )
    return reply


def concept_anchor_memory_block(
    query_text: str = "",
    *,
    max_chars: int = 1200,
) -> str:
    """Prompt block when the turn mentions a known concept/product."""
    q = query_text or ""
    rows = resolve_concept_anchors(q)
    if not rows:
        return ""
    lines = ["## CONCEPT BIRTH HUMAN ANCHORS (receipt-grade, not cortex guess)"]
    for row in rows[:6]:
        primary = row.get("primary_birth_anchor") or {}
        lines.append(
            f"- {row.get('concept_id')}: primary={primary.get('human_name')} "
            f"({primary.get('role')}); type={row.get('concept_type')}"
        )
        if row.get("collision_anchors"):
            cols = ", ".join(
                str(c.get("human_name") or "") for c in row.get("collision_anchors") or []
            )
            if cols:
                lines.append(f"  collision (not product founder): {cols}")
        temporal = row.get("temporal_epoch_pin") or {}
        if temporal.get("era_label"):
            lines.append(
                f"  temporal_pin: {temporal.get('pin_human')} → {temporal.get('era_label')}"
            )
        if row.get("fuzzy_concept"):
            lines.append("  fuzzy_concept: attach human pin or receipt before time-travel claims")
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "resolve_concept_anchor",
    "resolve_concept_anchors",
    "resolve_concept_from_url",
    "answer_concept_founder_query",
    "answer_concept_temporal_pin_query",
    "concept_anchor_memory_block",
]
