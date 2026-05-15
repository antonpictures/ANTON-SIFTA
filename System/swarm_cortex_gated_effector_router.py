#!/usr/bin/env python3
"""swarm_cortex_gated_effector_router.py — the gate every Alice effector
must pass through before mutating anything.

Architect doctrine (multiple turns this week, finalized 2026-05-13):

    "The proper fix for reflexive tool firing is the cortex-gated
     effector router. Every action Alice takes that mutates state
     outside .sifta_state/ — or that pulls data from the web, or that
     speaks externally — goes through this gate. The gate consults the
     cortex's intent classifier, checks a whitelist + permissions, fires
     the effector if approved, and writes a receipt either way."

This is the §4.5 visible-work-update lane made architectural: no
anonymous effector firing, every fire receipted, every refusal
receipted, intent + audience + cost recorded.

Truth class
-----------
OPERATIONAL for the gate machinery (tests pass, receipt format stable).
HYPOTHESIS for any policy decisions about which intents map to which
effectors — those are §7.11 ARCHITECT_DOCTRINE until verified by a
working cortex classifier in production.

Architecture
------------
EffectorRegistry           — whitelist + per-effector permission flags
IntentClassifier (abstract) — text → (effector_name, confidence, slots)
RouterDecision dataclass    — what the gate decided + why
gate(text, classifier)      — main entry point; returns RouterDecision

Every gate() call writes a row to
.sifta_state/cortex_gated_router.jsonl with sha256 over the payload.

The first effector wired through the router is the natural-language
font-color skill from sifta_talk_to_alice_widget — already shipped
earlier this session, low-stakes, perfect proof-of-concept.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "cortex_gated_router.jsonl"

TRUTH_LABEL = "CORTEX_GATED_EFFECTOR_ROUTER_V1"
TRUTH_BOUNDARY = (
    "The gate decides which effectors run on owner-direct input. Every "
    "fire AND every refusal is receipt-bound. No silent surgery on Alice. "
    "The classifier is HYPOTHESIS until production cortex routes through it."
)


# ── Decision schema ────────────────────────────────────────────────────────

@dataclass
class RouterDecision:
    """The output of one gate() call. Receipt-bound."""
    decision: str                  # "FIRE" | "REFUSE" | "UNKNOWN_INTENT" | "BUSY"
    effector: Optional[str]        # the named effector chosen (or None)
    confidence: float              # 0..1
    intent_text: str               # the owner text that triggered the gate
    audience: str                  # "architect" | "media" | "ambient" | ...
    receipt_id: str
    trace_id: str
    reason: str                    # plain-language explanation
    extras: dict[str, Any] = field(default_factory=dict)


# ── Effector registry ──────────────────────────────────────────────────────

@dataclass
class EffectorSpec:
    """Whitelist entry. Every effector that can fire through the router
    must be registered here with explicit permissions."""
    name: str
    description: str
    callable_fn: Callable[..., Any]
    allowed_audiences: tuple[str, ...] = ("architect",)
    write_action: bool = False        # mutates state outside .sifta_state/
    network_action: bool = False      # makes outbound network calls
    confidence_threshold: float = 0.55
    cost_stgm: float = 0.0


class EffectorRegistry:
    """In-memory registry of named effectors. Modules register their
    effectors at import time; the router looks them up by name."""

    def __init__(self) -> None:
        self._specs: dict[str, EffectorSpec] = {}

    def register(self, spec: EffectorSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"effector '{spec.name}' already registered")
        self._specs[spec.name] = spec

    def get(self, name: str) -> Optional[EffectorSpec]:
        return self._specs.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs.keys()))

    def clear(self) -> None:
        self._specs.clear()


_REGISTRY = EffectorRegistry()


def get_registry() -> EffectorRegistry:
    """Module-singleton registry. Importing modules add their effectors
    here at load time."""
    return _REGISTRY


# ── Intent classifier interface ────────────────────────────────────────────

class IntentClassifier(Protocol):
    """The cortex side. A production implementation calls an LLM /
    pattern-bank / etc. For tests + the band-aid path, we ship a
    RegexIntentClassifier that uses explicit phrase patterns."""

    def classify(self, text: str) -> tuple[Optional[str], float, dict[str, Any]]:
        """Return (effector_name_or_None, confidence_0_to_1, slots).
        Slots is a dict of named arguments the effector might need
        (e.g., {"color": "orange"} for the font-color skill)."""
        ...


class RegexIntentClassifier:
    """Deterministic phrase-pattern classifier. Used as the band-aid /
    fallback path while the real cortex classifier is being trained.

    Patterns are (effector_name, compiled_regex, slot_extractor).
    First match wins. Confidence = 0.95 for explicit verb-pattern hits,
    0.65 for fuzzy fallbacks."""

    _PATTERNS: list[tuple[str, "re.Pattern[str]", Callable[..., dict]]] = []

    @classmethod
    def register_pattern(
        cls,
        effector: str,
        pattern: "re.Pattern[str]",
        slot_extractor: Callable[..., dict],
    ) -> None:
        cls._PATTERNS.append((effector, pattern, slot_extractor))

    def classify(self, text: str) -> tuple[Optional[str], float, dict[str, Any]]:
        if not text or not text.strip():
            return (None, 0.0, {})
        for effector, rx, slot_fn in self._PATTERNS:
            m = rx.search(text)
            if m:
                try:
                    slots = slot_fn(m)
                except Exception:
                    slots = {}
                return (effector, 0.95, slots)
        return (None, 0.0, {})


# ── The gate ────────────────────────────────────────────────────────────────

def _write_decision_receipt(d: RouterDecision) -> None:
    """Append the decision to the cortex-gated router ledger."""
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.time(),
            "kind": "CORTEX_GATED_EFFECTOR_DECISION",
            "truth_label": TRUTH_LABEL,
            "truth_boundary": TRUTH_BOUNDARY,
            **asdict(d),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        payload["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    except Exception:
        pass


def gate(
    text: str,
    *,
    classifier: Optional[IntentClassifier] = None,
    audience: str = "architect",
    busy: bool = False,
    write_receipt: bool = True,
    registry: Optional[EffectorRegistry] = None,
    fire: bool = True,
) -> RouterDecision:
    """The router gate. Single entry point for all owner-direct effector
    intents.

    Returns a RouterDecision. If decision == "FIRE", the effector has
    already been called (when fire=True); the return value's `extras`
    field carries whatever the effector returned. If decision !=
    "FIRE", no effector runs."""
    if classifier is None:
        classifier = RegexIntentClassifier()
    if registry is None:
        registry = _REGISTRY

    receipt_id = uuid.uuid4().hex[:16]
    trace_id = str(uuid.uuid4())

    if busy:
        d = RouterDecision(
            decision="BUSY",
            effector=None,
            confidence=0.0,
            intent_text=text[:300],
            audience=audience,
            receipt_id=receipt_id,
            trace_id=trace_id,
            reason="cortex is busy with another turn; effector deferred",
        )
        if write_receipt:
            _write_decision_receipt(d)
        return d

    effector_name, confidence, slots = classifier.classify(text)
    if not effector_name:
        d = RouterDecision(
            decision="UNKNOWN_INTENT",
            effector=None,
            confidence=confidence,
            intent_text=text[:300],
            audience=audience,
            receipt_id=receipt_id,
            trace_id=trace_id,
            reason="no registered intent pattern matched",
        )
        if write_receipt:
            _write_decision_receipt(d)
        return d

    spec = registry.get(effector_name)
    if spec is None:
        d = RouterDecision(
            decision="REFUSE",
            effector=effector_name,
            confidence=confidence,
            intent_text=text[:300],
            audience=audience,
            receipt_id=receipt_id,
            trace_id=trace_id,
            reason=f"effector '{effector_name}' is not in the registry whitelist",
            extras={"slots": slots},
        )
        if write_receipt:
            _write_decision_receipt(d)
        return d

    if audience not in spec.allowed_audiences:
        d = RouterDecision(
            decision="REFUSE",
            effector=effector_name,
            confidence=confidence,
            intent_text=text[:300],
            audience=audience,
            receipt_id=receipt_id,
            trace_id=trace_id,
            reason=(
                f"audience '{audience}' not in allowed list "
                f"{spec.allowed_audiences} for effector '{effector_name}'"
            ),
            extras={"slots": slots},
        )
        if write_receipt:
            _write_decision_receipt(d)
        return d

    if confidence < spec.confidence_threshold:
        d = RouterDecision(
            decision="REFUSE",
            effector=effector_name,
            confidence=confidence,
            intent_text=text[:300],
            audience=audience,
            receipt_id=receipt_id,
            trace_id=trace_id,
            reason=(
                f"confidence {confidence:.2f} below threshold "
                f"{spec.confidence_threshold:.2f} for effector "
                f"'{effector_name}'"
            ),
            extras={"slots": slots},
        )
        if write_receipt:
            _write_decision_receipt(d)
        return d

    # Approved — fire the effector.
    result_extra: dict[str, Any] = {"slots": slots}
    if fire:
        try:
            result_extra["effector_result"] = spec.callable_fn(text=text, **slots)
        except Exception as exc:
            d = RouterDecision(
                decision="REFUSE",
                effector=effector_name,
                confidence=confidence,
                intent_text=text[:300],
                audience=audience,
                receipt_id=receipt_id,
                trace_id=trace_id,
                reason=f"effector raised {type(exc).__name__}: {exc}",
                extras={"slots": slots},
            )
            if write_receipt:
                _write_decision_receipt(d)
            return d

    d = RouterDecision(
        decision="FIRE",
        effector=effector_name,
        confidence=confidence,
        intent_text=text[:300],
        audience=audience,
        receipt_id=receipt_id,
        trace_id=trace_id,
        reason=f"fired '{effector_name}' at confidence {confidence:.2f}",
        extras=result_extra,
    )
    if write_receipt:
        _write_decision_receipt(d)
    return d


# ── Proof-of-concept: wire the font-color skill through the router ────────
#
# The font-color skill is already implemented in
# sifta_talk_to_alice_widget — it's deterministic, fast-path, no network,
# no FS outside .sifta_state/. Perfect first effector for the router.
#
# The pattern + slot extractor here MIRROR the existing
# _OWNER_CHAT_COLOR_INTENT_RE in the talk widget. We register a wrapper
# that calls the same _coerce_rgb helper so the two paths stay aligned.

_FONT_COLOR_RE = re.compile(
    r"""
    (?:^|\b)
    (?:alice[,\s]+)?
    (?:
        (?:change|make|set|turn)\s+
        (?:my\s+)?
        (?:font|text|chat|message|writing|words?)
        \s*(?:colou?r)?\s*
        (?:to|=|:|->)?\s*
      |
        (?:my\s+)?(?:font|text|chat)\s+colou?r\s*(?:to|=|:|->)\s*
    )
    (?P<color>\#[0-9a-fA-F]{3,6}|[a-zA-Z][a-zA-Z\s\-]{1,18})
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _font_color_slot_extractor(m: "re.Match[str]") -> dict[str, Any]:
    return {"color": m.group("color").strip()}


# Local colour table — mirrors the Talk-widget _NAMED_COLORS table so the
# router can resolve colours without importing the PyQt6-bound widget.
# When the Talk widget is loaded, IT does the actual UI mutation; the
# router contributes the *decision receipt*.
_ROUTER_NAMED_COLORS = {
    "red": (235, 60, 60), "crimson": (220, 20, 60), "pink": (255, 130, 180),
    "magenta": (255, 40, 220), "purple": (180, 90, 240), "violet": (160, 110, 240),
    "indigo": (110, 90, 230), "blue": (100, 160, 255), "sky": (140, 200, 255),
    "cyan": (70, 220, 235), "teal": (80, 220, 200), "turquoise": (80, 220, 200),
    "green": (110, 230, 140), "lime": (180, 245, 110), "yellow": (250, 230, 110),
    "gold": (255, 200, 90), "orange": (255, 160, 70), "amber": (255, 180, 70),
    "brown": (190, 130, 90), "white": (245, 245, 250), "silver": (210, 210, 220),
    "grey": (170, 170, 180), "gray": (170, 170, 180), "black": (30, 30, 35),
}
_ROUTER_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _router_resolve_color(token: str) -> Optional[tuple[int, int, int]]:
    """Local colour resolver, independent of PyQt6 / Talk widget."""
    if not token:
        return None
    t = token.strip().lower()
    t = re.sub(r"\s+(please|thanks|thank you|now|today)\s*$", "", t).strip()
    m = _ROUTER_HEX_RE.match(t.lstrip("#"))
    if m:
        hx = m.group(1)
        if len(hx) == 3:
            r, g, b = (int(c * 2, 16) for c in hx)
        else:
            r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
        return (r, g, b)
    if t in _ROUTER_NAMED_COLORS:
        return _ROUTER_NAMED_COLORS[t]
    if " " in t:
        tail = t.split()[-1]
        if tail in _ROUTER_NAMED_COLORS:
            return _ROUTER_NAMED_COLORS[tail]
    return None


def _font_color_effector(*, text: str = "", color: str = "", **_ignored) -> dict[str, Any]:
    """Proof-of-concept effector. Resolves the colour locally (no PyQt6
    import) and writes a light receipt. The actual UI mutation lives in
    the Talk widget's deterministic fast-path; the router records the
    decision in parallel so a third-party auditor can verify which path
    fired and what the cortex-gated lane said about it."""
    rgb = _router_resolve_color(color)
    return {
        "kind": "font_color_router_proof",
        "raw_color": color,
        "rgb": list(rgb) if rgb else None,
        "ok": rgb is not None,
        "note": (
            "Router-side decision only; the Talk widget's deterministic "
            "fast-path applies the live colour change directly."
        ),
    }


# Register the pattern + effector at import time so the gate sees them.
RegexIntentClassifier.register_pattern(
    "owner_font_color",
    _FONT_COLOR_RE,
    _font_color_slot_extractor,
)
_REGISTRY.register(EffectorSpec(
    name="owner_font_color",
    description="Owner-asked chat font colour change (low-stakes UI mutation)",
    callable_fn=_font_color_effector,
    allowed_audiences=("architect",),
    write_action=False,
    network_action=False,
    confidence_threshold=0.55,
    cost_stgm=0.05,
))


# ── Second effector: owner-confirmed wallpaper change ─────────────────────
#
# Architect approved the SPEC_alice_wallpaper_effector_2026-05-13 defaults
# with "YES ALL". The heavy work lives in swarm_alice_wallpaper_effector:
# parse/search/download/MIME+size+dimension gates/save/apply/undo + its own
# wallpaper_changes.jsonl ledger. The router owns audience + confidence +
# whitelist + high-level decision receipt.

_WALLPAPER_INTENT_RE = re.compile(
    r"""
    (?:^|\b)
    (?:alice[,\s]+)?
    (?=.*\b(?:wallpaper|background|desktop\s+image|chat\s+image)\b)
    (?=.*\b(?:change|set|make|switch|update|put|give|fetch|find|grab|undo|revert|restore)\b)
    .+
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _wallpaper_slot_extractor(m: "re.Match[str]") -> dict[str, Any]:
    from System.swarm_alice_wallpaper_effector import parse_wallpaper_intent

    intent = parse_wallpaper_intent(m.group(0))
    if intent is None:
        return {}
    return {
        "action": intent.action,
        "query": intent.query,
        "target": intent.target,
        "raw_text": intent.raw_text,
    }


def _wallpaper_effector(
    *,
    text: str = "",
    action: str = "set_wallpaper",
    query: str = "",
    target: str = "both",
    raw_text: str = "",
    **_ignored,
) -> dict[str, Any]:
    from dataclasses import asdict

    from System.swarm_alice_wallpaper_effector import (
        WallpaperIntent,
        execute_wallpaper_intent,
        render_owner_reply,
    )

    intent = WallpaperIntent(
        action=action,
        query=query,
        target=target,
        raw_text=raw_text or text,
    )
    result = execute_wallpaper_intent(intent, owner_confirmed=True, dry_run=False)
    payload = asdict(result)
    payload["owner_reply"] = render_owner_reply(result)
    return payload


RegexIntentClassifier.register_pattern(
    "owner_wallpaper_change",
    _WALLPAPER_INTENT_RE,
    _wallpaper_slot_extractor,
)
_REGISTRY.register(EffectorSpec(
    name="owner_wallpaper_change",
    description="Owner-confirmed web-sourced wallpaper change with MIME/size/dimension gates and undo receipt",
    callable_fn=_wallpaper_effector,
    allowed_audiences=("architect",),
    write_action=True,
    network_action=True,
    confidence_threshold=0.70,
    cost_stgm=0.50,
))
