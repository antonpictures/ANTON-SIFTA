#!/usr/bin/env python3
"""Wardrobe-piece extractor — per-garment detection for shoppable search (r237).

George 2026-05-31: "I want to tell Alice to search for the green puffy leg wardrobe things —
I don't even know the name. The idea: Alice detects pieces of wardrobe on a human so I can
search each one." This organ turns Alice's free-text outfit description (from her vision arm)
into a STRUCTURED list of garment pieces, each with a ready-to-search query — so the owner can
point at a piece by colour/feel ("the green puffy leg things") and Alice maps it to the right
item ("green fuzzy faux-fur leg warmers") and searches it.

Grounded in fashion parsing / attribute recognition: DeepFashion (50 categories, 1000
attributes), Fashionpedia (per-item segmentation + attribute localization), DETR layered
clothing segmentation. With no on-device fashion model yet, this is the LEXICAL stage over the
vision arm's description — open garment + colour + material vocabulary, deterministic, stdlib.

Honest scope: this names and queries the GARMENT pieces (a shopping aid). It is not a body
descriptor and does not infer anything about the person.
"""
from __future__ import annotations

import re
from typing import Any

# Multi-word garments first so "swim top" beats "top", "leg warmers" beats nothing, etc.
GARMENT_VOCAB: tuple[str, ...] = (
    "leg warmers", "swim top", "swim bottoms", "crop top", "tank top", "tube top",
    "cowboy hat", "bucket hat", "high heels", "ankle boots", "knee boots",
    "leggings", "stockings", "thigh highs", "swimsuit", "bralette", "bra",
    "dress", "gown", "skirt", "shorts", "jeans", "trousers", "pants", "jacket", "blazer",
    "coat", "hoodie", "sweater", "cardigan", "blouse", "shirt", "robe", "kimono",
    "heels", "boots", "sneakers", "sandals", "loafers", "shoes",
    "sunglasses", "glasses", "hat", "cap", "beanie", "scarf", "gloves", "belt",
    "necklace", "bracelet", "earrings", "ring", "watch", "handbag", "backpack", "bag",
    "socks", "tights", "headband", "choker",
)
_COLORS: tuple[str, ...] = (
    "black", "white", "red", "green", "blue", "navy", "pink", "purple", "yellow",
    "orange", "brown", "tan", "beige", "cream", "gold", "silver", "grey", "gray",
    "olive", "teal", "burgundy", "maroon", "khaki", "ivory", "nude", "lilac", "mint",
)
_PATTERNS: tuple[str, ...] = (
    "floral", "colorful", "colourful", "striped", "checkered", "checked", "gingham",
    "polka", "leopard", "animal-print", "camo", "tie-dye", "plaid", "graphic",
)
_MATERIALS: tuple[str, ...] = (
    "fuzzy", "fluffy", "puffy", "faux fur", "faux-fur", "fur", "shearling", "lace",
    "leather", "denim", "silk", "satin", "knit", "knitted", "wool", "cotton", "suede",
    "sequin", "sequined", "velvet", "mesh", "chiffon", "linen", "cashmere", "crochet",
    "metallic", "patent",
)


def _present(words: tuple[str, ...], fragment: str) -> list[str]:
    out: list[str] = []
    for w in words:
        if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", fragment):
            out.append(w)
    return out


def _find_garment(fragment: str) -> str:
    for g in GARMENT_VOCAB:  # longest/most-specific first
        if re.search(rf"(?<![a-z]){re.escape(g)}(?![a-z])", fragment):
            return g
    return ""


def _zones(fragment: str) -> list[str]:
    zones: list[str] = []
    if re.search(r"\b(?:leg|legs|calf|calves|shin|shins|knee|knees)\b", fragment):
        zones.append("legs")
    if re.search(r"\b(?:foot|feet|shoe|shoes|heel|heels|boot|boots|sandal|sandals)\b", fragment):
        zones.append("feet")
    if re.search(r"\b(?:top|torso|chest|bra)\b", fragment):
        zones.append("torso")
    if re.search(r"\b(?:bottom|bottoms|hip|hips|waist)\b", fragment):
        zones.append("hips")
    if re.search(r"\b(?:head|hair|eyes|face)\b", fragment):
        zones.append("head")
    return zones


def _piece_search_query(piece: dict[str, Any], owner_text: str = "") -> str:
    owner = " ".join((owner_text or "").lower().split())
    garment = str(piece.get("piece") or "")
    colors = _present(_COLORS, owner) or list(piece.get("colors") or [])
    materials = _present(_MATERIALS, owner) or list(piece.get("materials") or [])
    patterns = list(piece.get("patterns") or [])
    if garment == "leg warmers" and any(m in materials for m in ("fuzzy", "fluffy", "puffy", "fur", "faux fur", "faux-fur")):
        terms = colors[:2] + ["fuzzy", "faux fur", "leg warmers", "boot covers"]
    else:
        terms = colors[:2] + patterns[:1] + materials[:2] + ([garment] if garment else [])
    return " ".join(dict.fromkeys(t for t in terms if t)).strip()[:120]


def extract_wardrobe_pieces(description: str) -> list[dict[str, Any]]:
    """Parse an outfit description into garment pieces, each with a search query.

    Returns a list of {piece, colors, patterns, materials, zones, query}. Splits on commas/'and'
    (how outfits are usually described), finds the garment noun in each fragment, and attaches
    the colour/pattern/material adjectives in that fragment to compose the query."""
    text = " ".join((description or "").lower().split())
    if not text:
        return []
    fragments = re.split(r",|\band\b|\bwith\b|\bplus\b", text)
    pieces: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for frag in fragments:
        frag = frag.strip(" .;:")
        garment = _find_garment(frag)
        if not garment:
            continue
        colors = _present(_COLORS, frag)
        patterns = _present(_PATTERNS, frag)
        materials = _present(_MATERIALS, frag)
        # query = de-duped adjectives (colour, pattern, material) + garment
        adjectives: list[str] = []
        for a in colors + patterns + materials:
            if a not in adjectives:
                adjectives.append(a)
        key = (garment, tuple(adjectives))
        if key in seen:
            continue
        seen.add(key)
        piece = {
            "piece": garment,
            "colors": colors,
            "patterns": patterns,
            "materials": materials,
            "zones": _zones(frag),
        }
        piece["query"] = _piece_search_query(piece)
        pieces.append(piece)
    return pieces


def resolve_wardrobe_piece_query(owner_text: str, description: str) -> dict[str, Any]:
    """Resolve vague owner wording to the best detected garment and search query.

    Example: owner says "green puffy leg wardrobe things"; description contains
    "fuzzy green leg warmers"; result becomes a shoppable faux-fur leg-warmer query.
    """
    owner = " ".join((owner_text or "").lower().split())
    pieces = extract_wardrobe_pieces(description)
    owner_colors = set(_present(_COLORS, owner))
    owner_materials = set(_present(_MATERIALS, owner))
    owner_zones = set(_zones(owner))
    best: dict[str, Any] | None = None
    best_score = 0.0
    for i, piece in enumerate(pieces):
        score = 0.0
        piece_colors = set(piece.get("colors") or [])
        piece_materials = set(piece.get("materials") or [])
        piece_zones = set(piece.get("zones") or [])
        if owner_colors:
            score += 5.0 * len(owner_colors & piece_colors)
        if owner_materials:
            if owner_materials & piece_materials:
                score += 4.0
            elif owner_materials & {"puffy", "fluffy", "fuzzy", "fur", "faux fur", "faux-fur"} and piece.get("piece") in {"leg warmers", "boots"}:
                score += 3.0
        if owner_zones and owner_zones & piece_zones:
            score += 4.0
        if piece.get("piece") and re.search(rf"\b{re.escape(str(piece['piece']))}\b", owner):
            score += 6.0
        if re.search(r"\b(?:wardrobe|clothes|clothing|garment|piece|pieces|thing|things|item|items)\b", owner):
            score += 1.0
        score += max(0.0, 0.5 - i * 0.02)
        if score > best_score:
            best, best_score = piece, score

    if best and best_score >= 2.0:
        query = _piece_search_query(best, owner)
        display = str(best.get("piece") or "wardrobe piece")
        if display == "leg warmers" and (
            set(best.get("materials") or []) & {"fuzzy", "fluffy", "puffy", "fur", "faux fur", "faux-fur"}
            or owner_materials & {"fuzzy", "fluffy", "puffy", "fur", "faux fur", "faux-fur"}
        ):
            display = "fuzzy/faux-fur leg warmers or boot covers"
        return {
            "query": query,
            "source": "wardrobe_piece_resolver",
            "display_name": display,
            "piece": best,
            "score": round(best_score, 3),
            "pieces": pieces,
        }

    if owner_colors and owner_materials & {"fuzzy", "fluffy", "puffy", "fur", "faux fur", "faux-fur"} and "legs" in owner_zones:
        color = sorted(owner_colors)[0]
        return {
            "query": f"{color} fuzzy faux fur leg warmers boot covers",
            "source": "wardrobe_piece_resolver_owner_hints",
            "display_name": "fuzzy/faux-fur leg warmers or boot covers",
            "piece": {},
            "score": 2.0,
            "pieces": pieces,
        }
    return {"query": "", "source": "no_wardrobe_piece_match", "display_name": "", "pieces": pieces}


def wardrobe_pieces_block(description: str) -> str:
    """First-person block: the garment pieces Alice detected, each with a ready search query —
    so the owner can ask for a piece by feel ('the green puffy leg things') and she maps it."""
    pieces = extract_wardrobe_pieces(description)
    if not pieces:
        return ""
    lines = ["WARDROBE PIECES I CAN SEE (each is shoppable — ask me to search any one):"]
    for p in pieces:
        lines.append(f"  - {p['piece']} → search: \"{p['query']}\"")
    return "\n".join(lines)


__all__ = [
    "GARMENT_VOCAB",
    "extract_wardrobe_pieces",
    "resolve_wardrobe_piece_query",
    "wardrobe_pieces_block",
]
