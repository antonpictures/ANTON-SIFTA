#!/usr/bin/env python3
"""swarm_wallpaper_router_bridge.py — wires the peer wallpaper effector
through the cortex-gated effector router.

Architect spec §8 (`YES ALL` confirmed 2026-05-13): DDG search, save to
Library/Desktop Pictures/web_fetched/, scope=both, sequenced AFTER the
cortex-gated router (router shipped), light NSFW gates.

Per covenant §8.5 consensus discipline, this module does NOT modify
either peer surface:

   - System/swarm_alice_wallpaper_effector.py (peer-shipped effector
     with WallpaperIntent + execute_wallpaper_intent + ledger)
   - System/swarm_cortex_gated_effector_router.py (my router with
     EffectorRegistry + IntentClassifier + gate())

This bridge module is a SEPARATE third file that imports both and
registers two intents (owner_wallpaper_change + owner_wallpaper_undo)
with the router, calling into the peer effector's public API.

Truth class
-----------
OPERATIONAL for the bridge plumbing.
HYPOTHESIS for the natural-language regex coverage — production cortex
will replace the RegexIntentClassifier and this bridge just stays
useful as a deterministic fallback.

The router gate provides:
   - audience whitelist (architect only — never media / ambient)
   - confidence threshold (0.7 — wallpaper is a higher-stakes effector
     than the font-color skill)
   - BUSY short-circuit if Alice is mid-turn
   - sha256-signed decision receipt regardless of FIRE/REFUSE outcome

The peer effector adds:
   - explicit owner_confirmed flag (defence-in-depth — the router
     audience check is upstream; this is a second check at the
     effector layer)
   - actual DDG search + image gates + atomic save + ledger row
"""
from __future__ import annotations

import re
from typing import Any


# ── Intent regex (mirrors the peer's parse_wallpaper_intent breadth) ──────

# A wallpaper-change utterance contains one of {wallpaper, background,
# desktop image, chat image} AND one of {change/set/make/...}. We
# capture the query slot for the router to pass into the effector.

_WALLPAPER_CHANGE_RE = re.compile(
    r"""
    (?:^|\b)
    (?:alice[,\s]+)?
    (?:
        (?:change|set|swap|switch|update|make|put|give|fetch|find|grab)\s+
        (?:my\s+|the\s+)?
        (?:desktop\s+|chat\s+|background\s+)?
        (?:wallpaper|background|desktop\s+image|chat\s+image|wall\s*paper|backdrop)
        \s*(?:to|with|of|as|for|=|:|->)\s+
      |
        wallpaper\s+of\s+
    )
    (?P<query>[^.?!\n]{1,200})
    """,
    re.IGNORECASE | re.VERBOSE,
)

_WALLPAPER_UNDO_RE = re.compile(
    r"""
    (?:^|\b)
    (?:alice[,\s]+)?
    (?:
        undo\s+(?:the\s+|my\s+|that\s+|this\s+)?(?:wallpaper|background)
      |
        (?:wallpaper|background)\s+(?:back|undo|previous|revert)
      |
        go\s+back\s+to\s+(?:the\s+)?previous\s+wallpaper
      |
        revert\s+(?:the\s+|that\s+)?wallpaper
      |
        i\s+don['’]?t\s+like\s+(?:that|this)\s+(?:wallpaper|background|one)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Architect 2026-05-13: 'change wallpaper to default' / 'wallpaper back
# to default' / 'reset wallpaper' all map to the same effect — clear
# the custom-wallpaper choice so the theme's canonical image takes over.
# Must register BEFORE owner_wallpaper_change in pattern order so the
# word 'default' isn't passed to DDG as a search query.
_WALLPAPER_DEFAULT_RE = re.compile(
    r"""
    (?:^|\b)
    (?:alice[,\s]+)?
    (?:
        (?:change|changed|set|swap|switch|update|put|make|reset|restore)\s+
        (?:the\s+|my\s+)?
        (?:desktop\s+|chat\s+|background\s+)?
        (?:wallpaper|background|desktop\s+image)
        \s+(?:back\s+)?(?:to|=)\s+
        (?:the\s+)?(?:default|theme\s+default|original|standard|stock|canonical)
      |
        reset\s+(?:the\s+|my\s+)?(?:wallpaper|background|desktop\s+image)
      |
        (?:wallpaper|background)\s+(?:back\s+)?to\s+default
      |
        clear\s+(?:the\s+|my\s+)?(?:wallpaper|background)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _default_slot_extractor(_m: "re.Match[str]") -> dict[str, Any]:
    return {"target": "both"}


def _router_default_effector(
    *, text: str = "", target: str = "both", **_ignored,
) -> dict[str, Any]:
    """Restore the theme default wallpaper by clearing the custom
    selection. SiftaDesktop._apply_wallpaper falls back to the theme
    image whenever load_custom_wallpaper_path() returns None."""
    try:
        from System.sifta_desktop_themes import save_custom_wallpaper_path
    except Exception as exc:
        return {
            "kind": "WALLPAPER_DEFAULT_ERROR",
            "ok": False,
            "error": f"sifta_desktop_themes unavailable: {type(exc).__name__}: {exc}",
        }
    # Remember what the previous custom path was so the undo organ can
    # still walk back across a default-restore if the architect changes
    # his mind.
    try:
        from System.sifta_desktop_themes import load_custom_wallpaper_path
        previous = load_custom_wallpaper_path()
    except Exception:
        previous = None
    try:
        save_custom_wallpaper_path(None)  # None = use theme default
    except Exception as exc:
        return {
            "kind": "WALLPAPER_DEFAULT_ERROR",
            "ok": False,
            "error": f"save_custom_wallpaper_path failed: {exc}",
        }
    # Best-effort live re-render so the change is visible immediately.
    triggered = False
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            for w in app.topLevelWidgets():
                if w.__class__.__name__ == "SiftaDesktop" and hasattr(w, "_apply_wallpaper"):
                    try:
                        w._apply_wallpaper(force=True)
                        triggered = True
                        break
                    except Exception:
                        pass
    except Exception:
        pass
    # Light receipt — the canonical wallpaper_changes.jsonl ledger is
    # owned by the peer effector and we don't want to write a misleading
    # WALLPAPER_CHANGE row. The router's decision ledger captures the
    # gate-level event; this return value carries the effector-side
    # detail.
    return {
        "kind": "WALLPAPER_DEFAULT_RESTORED",
        "ok": True,
        "target": target,
        "previous_custom_path": previous,
        "live_repaint_triggered": triggered,
        "interpretation": (
            "Custom wallpaper choice cleared. "
            "SiftaDesktop._apply_wallpaper will load the active theme's "
            "canonical wallpaper from Library/Desktop Pictures/ on next "
            "render."
        ),
    }


def _change_slot_extractor(m: "re.Match[str]") -> dict[str, Any]:
    q = (m.group("query") or "").strip().rstrip(".,;:!?")
    return {"query": q, "target": "both"}


def _undo_slot_extractor(_m: "re.Match[str]") -> dict[str, Any]:
    return {"target": "both"}


# ── Bridge callables ──────────────────────────────────────────────────────
# The router calls these with the slot keys passed through; we re-shape
# the call into the peer effector's public signature. Both call paths
# pass owner_confirmed=True because by the time the router has fired,
# the audience check already passed (architect-only whitelist).

def _router_change_effector(
    *, text: str = "", query: str = "", target: str = "both", **_ignored,
) -> dict[str, Any]:
    try:
        from System.swarm_alice_wallpaper_effector import (
            WallpaperIntent, execute_wallpaper_intent,
        )
    except Exception as exc:
        return {
            "kind": "WALLPAPER_BRIDGE_ERROR",
            "ok": False,
            "error": f"peer effector unavailable: {type(exc).__name__}: {exc}",
        }
    if not query:
        return {
            "kind": "WALLPAPER_BRIDGE_ERROR",
            "ok": False,
            "error": "router passed empty query slot",
        }
    intent = WallpaperIntent(
        action="set_wallpaper",
        query=query,
        target=target if target in ("chat", "desktop", "both") else "both",
        raw_text=text,
    )
    try:
        result = execute_wallpaper_intent(
            intent,
            owner_confirmed=True,    # router already gated audience
            dry_run=False,
        )
    except Exception as exc:
        return {
            "kind": "WALLPAPER_BRIDGE_ERROR",
            "ok": False,
            "error": f"effector raised: {type(exc).__name__}: {exc}",
            "intent": {"query": query, "target": target},
        }
    # Convert the peer's WallpaperResult dataclass to dict for the
    # router's receipt — the peer effector already wrote its own
    # ledger row, the router writes a separate decision-level row.
    if hasattr(result, "__dict__"):
        as_dict = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
    elif hasattr(result, "_asdict"):
        as_dict = result._asdict()
    else:
        as_dict = {"result": str(result)}
    as_dict["kind"] = "WALLPAPER_BRIDGE_FIRE"
    return as_dict


def _router_undo_effector(
    *, text: str = "", target: str = "both", **_ignored,
) -> dict[str, Any]:
    try:
        from System.swarm_alice_wallpaper_effector import undo_last_wallpaper_change
    except Exception as exc:
        return {
            "kind": "WALLPAPER_BRIDGE_ERROR",
            "ok": False,
            "error": f"peer effector unavailable: {type(exc).__name__}: {exc}",
        }
    try:
        result = undo_last_wallpaper_change(
            owner_confirmed=True,
            dry_run=False,
            target=target if target in ("chat", "desktop", "both") else "both",
        )
    except Exception as exc:
        return {
            "kind": "WALLPAPER_BRIDGE_ERROR",
            "ok": False,
            "error": f"undo raised: {type(exc).__name__}: {exc}",
        }
    if hasattr(result, "__dict__"):
        as_dict = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
    else:
        as_dict = {"result": str(result)}
    as_dict["kind"] = "WALLPAPER_BRIDGE_UNDO"
    return as_dict


# ── Registration ──────────────────────────────────────────────────────────

def register_with_router() -> dict[str, Any]:
    """Register the two wallpaper intents with the cortex-gated router.
    Idempotent — safe to call multiple times. Returns a dict naming
    which intents were newly registered vs already present."""
    try:
        from System.swarm_cortex_gated_effector_router import (
            EffectorSpec, RegexIntentClassifier, get_registry,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"router unavailable: {type(exc).__name__}: {exc}",
            "registered": [],
            "already_present": [],
        }

    registry = get_registry()
    newly_registered: list[str] = []
    already_present: list[str] = []

    # IMPORTANT: register DEFAULT first, UNDO second, CHANGE last. The
    # classifier returns the first matching pattern, and the change regex
    # is broad enough to consume both 'undo the wallpaper' AND 'change
    # wallpaper to default' (which would otherwise DDG-search the word
    # 'default'). Order ensures the right effector fires.
    if registry.get("owner_wallpaper_default") is None:
        RegexIntentClassifier.register_pattern(
            "owner_wallpaper_default",
            _WALLPAPER_DEFAULT_RE,
            _default_slot_extractor,
        )
        registry.register(EffectorSpec(
            name="owner_wallpaper_default",
            description=(
                "Restore the theme default wallpaper (clear custom "
                "selection). Architect-only audience, no network."
            ),
            callable_fn=_router_default_effector,
            allowed_audiences=("architect",),
            write_action=True,
            network_action=False,
            confidence_threshold=0.7,
            cost_stgm=0.05,
        ))
        newly_registered.append("owner_wallpaper_default")
    else:
        already_present.append("owner_wallpaper_default")

    if registry.get("owner_wallpaper_undo") is None:
        RegexIntentClassifier.register_pattern(
            "owner_wallpaper_undo",
            _WALLPAPER_UNDO_RE,
            _undo_slot_extractor,
        )
        registry.register(EffectorSpec(
            name="owner_wallpaper_undo",
            description="Restore the previous wallpaper from the last receipt.",
            callable_fn=_router_undo_effector,
            allowed_audiences=("architect",),
            write_action=True,
            network_action=False,
            confidence_threshold=0.7,
            cost_stgm=0.1,
        ))
        newly_registered.append("owner_wallpaper_undo")
    else:
        already_present.append("owner_wallpaper_undo")

    if registry.get("owner_wallpaper_change") is None:
        RegexIntentClassifier.register_pattern(
            "owner_wallpaper_change",
            _WALLPAPER_CHANGE_RE,
            _change_slot_extractor,
        )
        registry.register(EffectorSpec(
            name="owner_wallpaper_change",
            description=(
                "Natural-language web-sourced wallpaper change. Fires the "
                "peer effector swarm_alice_wallpaper_effector with "
                "owner_confirmed=True after the router gate has approved "
                "audience + confidence."
            ),
            callable_fn=_router_change_effector,
            allowed_audiences=("architect",),
            write_action=True,
            network_action=True,
            confidence_threshold=0.7,
            cost_stgm=0.5,
        ))
        newly_registered.append("owner_wallpaper_change")
    else:
        already_present.append("owner_wallpaper_change")

    # Ensure DEFAULT and UNDO precede CHANGE in the classifier pattern
    # list. A peer doctor may have registered `owner_wallpaper_change`
    # in the router module itself, putting it BEFORE our specialized
    # intents. The classifier returns the first matching pattern, and
    # the peer's change regex is broad enough to consume both 'undo the
    # wallpaper' AND 'change wallpaper to default'. Re-sort the list so
    # the specialized intents win on shared inputs — non-destructive:
    # same patterns, same callables, just earlier position.
    _reorder_patterns_specialized_before_change(RegexIntentClassifier)

    return {
        "ok": True,
        "registered": newly_registered,
        "already_present": already_present,
    }


def _reorder_patterns_specialized_before_change(classifier_cls) -> None:
    """Move specialized wallpaper patterns before the broad change
    pattern. Safe to call multiple times.

    DEFAULT must win over CHANGE for phrases like "change wallpaper to
    default"; UNDO must win over CHANGE for phrases like "undo wallpaper".
    """
    patterns = getattr(classifier_cls, "_PATTERNS", None)
    if not patterns:
        return
    change_entries = [p for p in patterns if p[0] == "owner_wallpaper_change"]
    if not change_entries:
        return
    specialized_names = {"owner_wallpaper_default", "owner_wallpaper_undo"}
    specialized = [p for p in patterns if p[0] in specialized_names]
    if not specialized:
        return
    others = [p for p in patterns if p[0] not in specialized_names and p[0] != "owner_wallpaper_change"]
    ordered_specialized = sorted(
        specialized,
        key=lambda p: 0 if p[0] == "owner_wallpaper_default" else 1,
    )
    classifier_cls._PATTERNS = ordered_specialized + others + change_entries


def _reorder_patterns_undo_before_change(classifier_cls) -> None:
    """Backward-compatible alias for older tests/imports."""
    _reorder_patterns_specialized_before_change(classifier_cls)


# Register at import time so any module that imports this bridge
# implicitly wires the gate. Talk widget can choose to import this
# bridge as part of its boot sequence to ensure the intents are alive.
register_with_router()
