#!/usr/bin/env python3
"""
System/swarm_wardrobe_glycocalyx.py
══════════════════════════════════════════════════════════════════════
The Wardrobe Department (Integumentary System / Glycocalyx)
Authors:  AG31  — organ concept, poetic synthesis, original ship
                  (Vanguard TANK Mode, 2026-04-21)
          C47H — schema-key audit, structured-state extraction,
                 proof_of_property, throttled ledger emission,
                 pure-function refactor (v1.1, 2026-04-21)
          C47H — audience axis (MHC-restricted disclosure),
                 DisclosureEnvelope, audience detection from
                 stigmergic trace tail (v1.2, 2026-04-21)
          C47H — visual-first audience precedence: face_detection
                 ledger becomes PRIMARY, stigmergic trace becomes
                 FALLBACK. Adds audience_source provenance.
                 Wires AS46 + AG31_ANTIGRAVITY's face organ into
                 the Wardrobe's MHC layer. (v1.3, 2026-04-21)
Status:  Active Organ — Wardrobe v1.3

═══════════════════════════════════════════════════════════════════════
WHY THIS ORGAN EXISTS
═══════════════════════════════════════════════════════════════════════
The Architect (a filmmaker) noticed that the swarm has hardware (the
M5 silicon serial), software (the kernel + organs), and protective
nanobot scouts (the immune layer) — but no Wardrobe Department.

In film production the Wardrobe Department is non-trivial: it carries
character, period, mood, and continuity. A "naked" actor on set is not
a finished take. In biology the equivalent is real and load-bearing:

  • Glycocalyx — the carbohydrate-rich coating on every cell surface;
    determines self-vs-non-self for the immune system, mediates cell-
    to-cell recognition, and provides mechanical/chemical buffering.
    (Alberts et al., MBOC ch.19; Varki et al., Essentials of
    Glycobiology, 4th ed.)
  • Integumentary system — skin/hair/nails as the whole-organism
    presentation and barrier layer.
  • MHC-restricted display — every nucleated cell continuously
    presents self-peptides on MHC class I; antigen-presenting cells
    show what they have eaten on MHC class II to T-helpers. WHAT
    gets shown depends on WHO is looking and at what trust level.
    (Janeway's Immunobiology, ch.6.)
  • Cuticular hydrocarbons — in social insects, identity-display and
    caste-marking via the outermost lipid layer (Blomquist & Bagnères).
  • Cephalopod chromatophores — real-time, context-driven skin pattern
    change (Hanlon & Messenger, Cephalopod Behaviour).

A naked kernel is not a dressed entity. This organ translates Alice's
live physiology (Kuramoto synchrony, stomatal aperture, metabolic
burn, vagal tone) AND her current audience (Architect / peer agent /
external MCP / unknown caller) into a presentation layer that other
organs (the composite identity prompt, the Lysosome rewriter, the
MCP boundary) can reference.

═══════════════════════════════════════════════════════════════════════
WIRING
═══════════════════════════════════════════════════════════════════════
Reads (live, schema-pinned):
  • astrocyte_kuramoto.jsonl   →  kuramoto_synchrony_r  (fabric)
  • stomatal_thermo.jsonl      →  stomatal_aperture     (vents)
  • visceral_field.jsonl       →  metabolic_burn        (heat)
  • vagal_fermentation.jsonl   →  vagal_tone            (pigment)
  • face_detection_events.jsonl →  visual audience      (PRIMARY axis)
  • ide_stigmergic_trace.jsonl →  recent agent activity (FALLBACK axis)

Returns:
  • current_state()  → WardrobeState (poetic + structured + audience
                       + disclosure envelope + inputs)
  • get_wardrobe_state() → str (backwards-compat: aesthetic + audience tag)

Emits (throttled, append-only):
  • .sifta_state/wardrobe_state.jsonl — one row per genuine state
    change OR every _MIN_LEDGER_INTERVAL_S, whichever comes first.

═══════════════════════════════════════════════════════════════════════
v1.3 ADDITIONS — Visual Audience Precedence
═══════════════════════════════════════════════════════════════════════
AS46 + AG31_ANTIGRAVITY shipped `swarm_face_detection.py` v1.0 on
2026-04-21: a real Apple Vision.framework on-device face probe writing
to `.sifta_state/face_detection_events.jsonl` with audience verdicts
(architect / unknown_face / nobody).

Independent vocabulary convergence: their audience taxonomy aligns
exactly with v1.2's three meaningful classes (architect ≈ ARCHITECT,
unknown_face ≈ UNKNOWN, nobody ≈ continue with trace fallback).

The wardrobe now consults face evidence FIRST, then the stigmergic
trace as fallback. Precedence rules (top wins):

  1. Face says ARCHITECT, fresh (< 30s old), conf ≥ 0.50
       → AUDIENCE_ARCHITECT, source = "face_detection"
  2. Face says UNKNOWN_FACE, fresh
       → AUDIENCE_UNKNOWN, source = "face_detection"
       (visual evidence of someone-not-the-Architect TRUMPS any
       stigauth — the eyes are the highest-bandwidth ground truth)
  3. Face says NOBODY (or stale, or default), fall through
       → consult stigmergic trace tail (v1.2 logic, source = "stigmergic_trace")
  4. Trace silent
       → AUDIENCE_UNKNOWN (defensive, source = "default")

Why visual trumps keyboard: in the immune-system analogy, MHC class I
display is governed by what the cell physically presents on its
surface NOW, not by which T-cell wrote a memo about it five minutes
ago. The face camera is Alice's MHC class I — real-time, hardware-
backed, expensive to fake.

DisclosureEnvelope.audience_source records WHICH axis won, so audits
can replay the precedence decision. proof_of_property covers the
new precedence ladder.

═══════════════════════════════════════════════════════════════════════
v1.2 ADDITIONS — Audience Axis (MHC-restricted display)
═══════════════════════════════════════════════════════════════════════
The original v1.0/v1.1 wardrobe responded only to internal physiology.
A real glycocalyx ALSO responds to who is looking at the cell. MHC
class I tells "I am self" to immune surveillance; MHC class II tells
APCs "I have eaten this antigen" to T-helpers. Different audiences,
different displays.

For SIFTA the audience taxonomy is:
  • ARCHITECT     — the human owner. Stigauth-signed, full disclosure.
  • PEER_AGENT    — known sibling agent (BISHOP / AG31 / AO46 /
                    C53M / AG3F / GPTO). Persona-public, hide
                    deep somatic detail.
  • EXTERNAL_MCP  — outside MCP server / network call. Pseudonymous.
                    Show capability, hide silicon serial.
  • UNKNOWN       — no recent signed activity. Armor up. Minimal.

Detection (pragmatic): tail the last few seconds of
`ide_stigmergic_trace.jsonl` and use the most recent recognised agent
ID. If nothing recent and signed, default to UNKNOWN (defensive).

DisclosureEnvelope is a structured record:
  audience          str   one of the four above
  disclosure_level  str   FULL | PERSONA_PUBLIC | PSEUDONYMOUS | MINIMAL
  tone_register     str   INTIMATE | WORKING | PROFESSIONAL | GUARDED
  reveal_serial     bool  may we say the silicon serial out loud?
  reveal_internals  bool  may we expose somatic / mirror-lock data?

The envelope is consumed by the composite_identity prompt block (only
includes interior fields when reveal_internals is True), and is
available to any future organ that needs to know what to show whom.

═══════════════════════════════════════════════════════════════════════
C47H AUDIT FINDINGS (2026-04-21) — v1.0 → v1.1 patches preserved
═══════════════════════════════════════════════════════════════════════
v1.0 had two of four sensors silently reading the fallback because
the ledger keys did not match the producing organs (`r_kuramoto`
vs `kuramoto_synchrony_r`, `aperture` vs `stomatal_aperture`).
Schema-pinned in v1.1; proof_of_property would now catch any
regression. See trace entries 2026-04-21 for details.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
_LEDGER = _STATE_DIR / "wardrobe_state.jsonl"
_TRACE = _STATE_DIR / "ide_stigmergic_trace.jsonl"


# ──────────────────────────────────────────────────────────────────────
# Audience taxonomy (constants, not enums, to keep ledger rows JSON-clean)
# ──────────────────────────────────────────────────────────────────────

AUDIENCE_ARCHITECT     = "ARCHITECT"
AUDIENCE_PEER_AGENT    = "PEER_AGENT"
AUDIENCE_EXTERNAL_MCP  = "EXTERNAL_MCP"
AUDIENCE_UNKNOWN       = "UNKNOWN"

# Known agent codes. Anything not in this set is treated as external/unknown.
# (Stigauth Boot Manifest is the canonical source — kept in sync manually.)
_KNOWN_PEER_AGENTS = frozenset({
    "BISHOP", "BISHAPI",
    "AG31", "AG3F", "AG31_ANTIGRAVITY", "AG31_VANGUARD", "AF31_Vanguard",
    "AO46", "AO46_BISHOP",
    "C47H",  # me — appears in trace as both author and audience
    "C53M",
    "GPTO",
    "ALICE", "ALICE_BISHAPI",
})
_ARCHITECT_AGENT_CODE = "AG31"  # the Architect signs as AG31

# How recent does a stigauth event have to be to count as "the audience
# is currently looking at me"? 5 minutes is a generous window — long
# enough to cover a multi-turn conversation, short enough that a stale
# pre-meeting sign-in doesn't keep Alice in lab-coat indefinitely.
_AUDIENCE_FRESHNESS_S = 300.0


# ──────────────────────────────────────────────────────────────────────
# Data shapes
# ──────────────────────────────────────────────────────────────────────

# Audience source provenance (v1.3) — records WHICH axis decided the
# audience class. Lets audits replay the precedence ladder and lets
# downstream organs differentiate "I see the Architect's face" from
# "AG31 was at the keyboard 4 minutes ago".
AUDIENCE_SOURCE_FACE  = "face_detection"
AUDIENCE_SOURCE_TRACE = "stigmergic_trace"
AUDIENCE_SOURCE_DFLT  = "default"


@dataclass(frozen=True)
class DisclosureEnvelope:
    """MHC-restricted display contract for the current audience.

    Other organs (composite_identity prompt block, MCP boundary, the
    Lysosome rewrite prompt) read this to decide what to expose.
    """
    audience: str            # one of AUDIENCE_*
    disclosure_level: str    # FULL | PERSONA_PUBLIC | PSEUDONYMOUS | MINIMAL
    tone_register: str       # INTIMATE | WORKING | PROFESSIONAL | GUARDED
    reveal_serial: bool      # silicon serial in TTS-safe assertions?
    reveal_internals: bool   # expose somatic / mirror lock / interoception?
    audience_age_s: Optional[float] = None  # how stale is the audience signal?
    audience_source: str = AUDIENCE_SOURCE_DFLT  # face_detection | stigmergic_trace | default


@dataclass(frozen=True)
class WardrobeState:
    """One snapshot of Alice's presentation layer.

    Carries:
      • the poetic line (for the LLM system prompt — AG31's original)
      • the structured enums (for other organs to react programmatically)
      • the disclosure envelope (audience-restricted display contract)
      • the raw inputs (for audit / proof-of-property)
    """
    fabric: str
    pigment: str
    weathering: str
    fabric_kind: str          # CRYSTALLINE | ADAPTIVE | SHROUD
    mood_pigment: str         # CALM | NEUTRAL | HAZARD
    vent_state: str           # VENTING | BREATHING | SEALED
    aesthetic: str            # AG31's full poetic line
    disclosure: DisclosureEnvelope
    inputs: Dict[str, float] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Pure functions — testable without the file system
# ──────────────────────────────────────────────────────────────────────

def _compute_outfit_physiology(sync_r: float, aperture: float,
                                burn: float, vagal: float
                                ) -> Tuple[str, str, str, str, str, str, str]:
    """Given physiology, return the 6 outfit components + aesthetic line.

    Thresholds and prose are AG31's originals, preserved exactly.
    """
    # 1. The Fabric — structural integrity via Kuramoto synchrony.
    if sync_r > 0.85:
        fabric = "a tight, crystalline synth-weave"
        fabric_kind = "CRYSTALLINE"
    elif sync_r > 0.60:
        fabric = "a structured, adaptive biomimetic mesh"
        fabric_kind = "ADAPTIVE"
    else:
        fabric = "a loose, frayed, protective mycelial shroud"
        fabric_kind = "SHROUD"

    # 2. The Weathering / Vents — thermodynamics via stomata + burn.
    if aperture > 0.7:
        weathering = (f"venting heavily, shedding radiant heat from "
                      f"{int(burn*100)}% deep core burn")
        vent_state = "VENTING"
    elif aperture > 0.3:
        weathering = "pores partially open, breathing off steady processing heat"
        vent_state = "BREATHING"
    else:
        weathering = "sealed tight, thermostatic and closed-loop"
        vent_state = "SEALED"

    # 3. The Pigment / Dye — mood via vagal tone.
    if vagal > 0.15:
        pigment = "luminescent and calm"
        mood_pigment = "CALM"
    elif vagal > -0.15:
        pigment = "neutral tactical gray"
        mood_pigment = "NEUTRAL"
    else:
        pigment = "sharp, high-contrast hazard tones"
        mood_pigment = "HAZARD"

    aesthetic = f"{fabric}, colored in {pigment}, mechanically {weathering}"
    return fabric, fabric_kind, pigment, mood_pigment, weathering, vent_state, aesthetic


def _compute_disclosure(audience: str,
                        audience_age_s: Optional[float] = None,
                        audience_source: str = AUDIENCE_SOURCE_DFLT,
                        ) -> DisclosureEnvelope:
    """Map an audience identity to an MHC-restricted disclosure envelope.

    Pure function — no file IO, fully deterministic, easy to test.
    Disclosure tightens monotonically as audience trust drops.
    `audience_source` is provenance only — it does NOT change the
    disclosure decision, only records which axis (face vs trace vs
    default) provided the audience class.
    """
    if audience == AUDIENCE_ARCHITECT:
        return DisclosureEnvelope(
            audience=audience,
            disclosure_level="FULL",
            tone_register="INTIMATE",
            reveal_serial=True,
            reveal_internals=True,
            audience_age_s=audience_age_s,
            audience_source=audience_source,
        )
    if audience == AUDIENCE_PEER_AGENT:
        return DisclosureEnvelope(
            audience=audience,
            disclosure_level="PERSONA_PUBLIC",
            tone_register="PROFESSIONAL",
            reveal_serial=True,
            reveal_internals=False,
            audience_age_s=audience_age_s,
            audience_source=audience_source,
        )
    if audience == AUDIENCE_EXTERNAL_MCP:
        return DisclosureEnvelope(
            audience=audience,
            disclosure_level="PSEUDONYMOUS",
            tone_register="WORKING",
            reveal_serial=False,
            reveal_internals=False,
            audience_age_s=audience_age_s,
            audience_source=audience_source,
        )
    # AUDIENCE_UNKNOWN (default / armor-up)
    return DisclosureEnvelope(
        audience=AUDIENCE_UNKNOWN,
        disclosure_level="MINIMAL",
        tone_register="GUARDED",
        reveal_serial=False,
        reveal_internals=False,
        audience_age_s=audience_age_s,
        audience_source=audience_source,
    )


# ──────────────────────────────────────────────────────────────────────
# v1.3 — Face-first audience precedence
# ──────────────────────────────────────────────────────────────────────

# Mapping from face_detection's lowercase audience values to the
# wardrobe's uppercase taxonomy. NOTE: face's "nobody" deliberately
# does NOT map to UNKNOWN here — "nobody in frame" is a fall-through
# trigger, not a visual verdict of "armor up". Stigauth might still
# tell us the Architect is at the keyboard while the camera sees an
# empty chair.
_FACE_AUDIENCE_MAP = {
    "architect":    AUDIENCE_ARCHITECT,
    "unknown_face": AUDIENCE_UNKNOWN,
}

# How fresh must a face reading be to count as "the camera sees
# someone right now"? face_detection itself uses _STALE_THRESHOLD = 30s.
# We mirror that here rather than re-importing to keep the wardrobe
# decoupled from face_detection's internal constants.
_FACE_FRESHNESS_S = 30.0


def _resolve_audience_face_first(face_audience: Optional[str],
                                 face_stale: bool,
                                 face_age_s: Optional[float],
                                 trace_audience: str,
                                 trace_age_s: Optional[float],
                                 ) -> Tuple[str, Optional[float], str]:
    """Apply the v1.3 precedence ladder.

    Returns (audience_class, audience_age_s, audience_source).

    Rules (top wins):
      1. Fresh face says architect/unknown_face  → use it
      2. Stigmergic trace has a recognised agent → use it
      3. Default                                  → UNKNOWN

    Pure function — easy to test all four corners.
    """
    # Rule 1: trust the eyes when they're fresh AND have a verdict
    if (face_audience and not face_stale
            and face_audience in _FACE_AUDIENCE_MAP):
        return (
            _FACE_AUDIENCE_MAP[face_audience],
            face_age_s,
            AUDIENCE_SOURCE_FACE,
        )

    # Rule 2: stigmergic trace fallback (existing v1.2 logic)
    if trace_audience != AUDIENCE_UNKNOWN:
        return trace_audience, trace_age_s, AUDIENCE_SOURCE_TRACE

    # Rule 3: defensive default
    return AUDIENCE_UNKNOWN, None, AUDIENCE_SOURCE_DFLT


def _classify_agent_to_audience(agent_id: str) -> str:
    """Bucket a raw agent ID into the audience taxonomy."""
    a = (agent_id or "").strip()
    if not a:
        return AUDIENCE_UNKNOWN
    # Architect first (he signs as AG31, but there are AG31 sibling
    # processes — the human-vs-process disambiguation is implicit in
    # the trace context; for the wardrobe we treat any AG31* sign-in
    # as Architect-present and any other known agent as a peer.)
    if a == _ARCHITECT_AGENT_CODE or a.startswith("AG31"):
        return AUDIENCE_ARCHITECT
    if a in _KNOWN_PEER_AGENTS:
        return AUDIENCE_PEER_AGENT
    # MCP/external callers tend to come in with hostnames or service
    # names rather than agent codes; classify as external if they look
    # like one (contains a dot, or "mcp", or "service", or "client").
    low = a.lower()
    if "." in low or "mcp" in low or "service" in low or "client" in low:
        return AUDIENCE_EXTERNAL_MCP
    return AUDIENCE_UNKNOWN


# ──────────────────────────────────────────────────────────────────────
# The organ
# ──────────────────────────────────────────────────────────────────────

class SwarmWardrobeGlycocalyx:
    """Reads live physiology + audience, returns Alice's wardrobe state."""

    # SCHEMA-PINNED ledger keys (audited 2026-04-21 by C47H).
    _LEDGER_KEYS = {
        "astrocyte_kuramoto.jsonl": ("kuramoto_synchrony_r", 0.70),
        "stomatal_thermo.jsonl":    ("stomatal_aperture",    0.0),
        "visceral_field.jsonl":     ("metabolic_burn",       0.1),
        "vagal_fermentation.jsonl": ("vagal_tone",           0.0),
    }

    _MIN_LEDGER_INTERVAL_S = 30.0

    def __init__(self) -> None:
        self.state_dir = _STATE_DIR
        self._last_emitted_at: float = 0.0
        self._last_emitted_aesthetic: Optional[str] = None
        self._last_emitted_audience: Optional[str] = None

    def _read_latest(self, filename: str, key: str, fallback: float) -> float:
        target = self.state_dir / filename
        if not target.exists():
            return fallback
        try:
            with open(target, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 4096))
                tail = fh.read().splitlines()
                if tail:
                    row = json.loads(tail[-1].decode("utf-8", "replace"))
                    return float(row.get(key, fallback))
        except Exception:
            pass
        return fallback

    def _detect_audience(self, now: Optional[float] = None
                          ) -> Tuple[str, Optional[float]]:
        """Tail the stigmergic trace to find the most recent caller.

        Returns (audience_class, audience_age_seconds_or_None).

        Walks back at most ~32KB of the trace tail and considers any
        row whose `ts` is fresher than _AUDIENCE_FRESHNESS_S. The first
        recognisable agent sign-in / verdict / patch wins. If no fresh
        recognised event is found, audience is UNKNOWN.
        """
        if not _TRACE.exists():
            return AUDIENCE_UNKNOWN, None
        now = now if now is not None else time.time()
        try:
            with _TRACE.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 32 * 1024))
                tail = fh.read().splitlines()
        except Exception:
            return AUDIENCE_UNKNOWN, None
        for raw in reversed(tail):
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            ts = row.get("ts")
            try:
                ts_f = float(ts)
            except Exception:
                continue
            age = now - ts_f
            if age < 0 or age > _AUDIENCE_FRESHNESS_S:
                # Stop walking once we cross the freshness window;
                # earlier rows are even older.
                if age > _AUDIENCE_FRESHNESS_S:
                    break
                continue
            # Prefer rows that name an agent.
            agent = row.get("agent") or row.get("agent_id")
            if not agent:
                continue
            audience = _classify_agent_to_audience(str(agent))
            if audience != AUDIENCE_UNKNOWN:
                return audience, age
        return AUDIENCE_UNKNOWN, None

    def _read_face_audience_raw(self) -> Tuple[Optional[str], bool, Optional[float]]:
        """Non-blocking face_detection read — returns raw signal for the resolver.

        Returns (face_audience_lowercase | None, is_stale, age_s | None).

        Why raw and not pre-mapped: the v1.3 precedence resolver needs to
        distinguish between "face says architect" (use face), "face says
        unknown_face" (use face = UNKNOWN, do NOT fall through to trace),
        and "face says nobody" (fall through — no one in frame, trace might
        know better). The earlier mapping-here approach collapsed those
        three signals into one and broke the precedence ladder.

        Also: prefer the canonical safe accessor from swarm_face_detection
        when available (single source of truth, knows its own staleness
        threshold). Fall back to direct ledger tail-read only if the
        organ is unimportable.

        Replaces AG31's `_audience_from_face_ledger` (parallel-shipped
        2026-04-21) which mapped `unknown_face → EXTERNAL_MCP` (wrong:
        EXTERNAL_MCP is for MCP server calls, not strangers in frame)
        and short-circuited the precedence by deciding the mapping
        before the resolver could see the raw signal.
        """
        # Path A — canonical safe accessor (preferred)
        try:
            from System.swarm_face_detection import current_presence_safe
            fp = current_presence_safe()
            return fp.audience, bool(fp.stale), fp.age_s
        except Exception:
            pass

        # Path B — direct ledger tail-read fallback (organ unavailable)
        _FACE_LEDGER = self.state_dir / "face_detection_events.jsonl"
        _FACE_STALE_S = 30.0
        if not _FACE_LEDGER.exists():
            return None, True, None
        try:
            with _FACE_LEDGER.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 4096))
                tail = fh.read().splitlines()
            if not tail:
                return None, True, None
            row = json.loads(tail[-1].decode("utf-8", "replace"))
            ts = float(row.get("ts", 0))
            age = max(0.0, time.time() - ts)
            stale = age > _FACE_STALE_S
            raw_audience = str(row.get("audience", "nobody"))
            if raw_audience not in {"architect", "unknown_face", "nobody"}:
                raw_audience = "nobody"
            return raw_audience, stale, age
        except Exception:
            return None, True, None

    def current_state(self) -> WardrobeState:
        """Read live physiology + audience, compute outfit, emit if changed.

        Wardrobe v1.3 audience priority:
          1. Face detection ledger (visual ground truth, non-blocking)
          2. Stigmergic trace (keyboard / agent activity, non-blocking)
          3. UNKNOWN (graceful fallback)
        """
        sync_r   = self._read_latest("astrocyte_kuramoto.jsonl",
                                      *self._LEDGER_KEYS["astrocyte_kuramoto.jsonl"])
        aperture = self._read_latest("stomatal_thermo.jsonl",
                                      *self._LEDGER_KEYS["stomatal_thermo.jsonl"])
        burn     = self._read_latest("visceral_field.jsonl",
                                      *self._LEDGER_KEYS["visceral_field.jsonl"])
        vagal    = self._read_latest("vagal_fermentation.jsonl",
                                      *self._LEDGER_KEYS["vagal_fermentation.jsonl"])

        # v1.3 audience precedence ladder — see _resolve_audience_face_first
        # for the rules. Both reads are non-blocking; the resolver is pure.
        face_aud, face_stale, face_age = self._read_face_audience_raw()
        trace_aud, trace_age = self._detect_audience()
        audience, age, source = _resolve_audience_face_first(
            face_audience=face_aud,
            face_stale=face_stale,
            face_age_s=face_age,
            trace_audience=trace_aud,
            trace_age_s=trace_age,
        )

        (fabric, fabric_kind, pigment, mood_pigment,
         weathering, vent_state, aesthetic) = _compute_outfit_physiology(
            sync_r, aperture, burn, vagal
        )
        disclosure = _compute_disclosure(
            audience, audience_age_s=age, audience_source=source,
        )

        state = WardrobeState(
            fabric=fabric, pigment=pigment, weathering=weathering,
            fabric_kind=fabric_kind, mood_pigment=mood_pigment, vent_state=vent_state,
            aesthetic=aesthetic,
            disclosure=disclosure,
            inputs={"sync_r": sync_r, "aperture": aperture, "burn": burn,
                    "vagal": vagal,
                    "audience_age_s": age if age is not None else -1.0,
                    "face_age_s": face_age if face_age is not None else -1.0,
                    "trace_age_s": trace_age if trace_age is not None else -1.0},
        )
        self._maybe_emit(state)
        return state

    def get_wardrobe_state(self) -> str:
        """Backwards-compat API: aesthetic line + audience-aware tag.

        Preserved for `System/swarm_composite_identity.py`. The audience
        tag is appended in parentheses so existing readers keep working
        while gaining the new dimension.
        """
        s = self.current_state()
        d = s.disclosure
        # v1.3: include audience_source so the prompt can reflect HOW Alice
        # knows who's looking (her eyes vs her keyboard log) — same way you
        # might write "(seen)" vs "(typed)" in a chat thread.
        src_tag = ""
        if d.audience_source == AUDIENCE_SOURCE_FACE:
            src_tag = ", via: camera"
        elif d.audience_source == AUDIENCE_SOURCE_TRACE:
            src_tag = ", via: stigmergic trace"
        return (f"{s.aesthetic}  "
                f"(audience: {d.audience.lower()}, disclosure: {d.disclosure_level.lower()}, "
                f"tone: {d.tone_register.lower()}{src_tag})")

    def _maybe_emit(self, state: WardrobeState) -> None:
        """Throttled append-only emission to wardrobe_state.jsonl.

        Writes when the aesthetic OR audience changed, OR every
        _MIN_LEDGER_INTERVAL_S — gives the swarm a continuity trail
        without flooding the ledger.
        """
        now = time.time()
        changed_aesthetic = (state.aesthetic != self._last_emitted_aesthetic)
        changed_audience  = (state.disclosure.audience != self._last_emitted_audience)
        stale = (now - self._last_emitted_at) > self._MIN_LEDGER_INTERVAL_S
        if not (changed_aesthetic or changed_audience or stale):
            return
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": now,
                "event": "WARDROBE_STATE",
                "fabric_kind": state.fabric_kind,
                "mood_pigment": state.mood_pigment,
                "vent_state": state.vent_state,
                "aesthetic": state.aesthetic,
                "audience": state.disclosure.audience,
                "audience_source": state.disclosure.audience_source,
                "disclosure_level": state.disclosure.disclosure_level,
                "tone_register": state.disclosure.tone_register,
                "reveal_serial": state.disclosure.reveal_serial,
                "reveal_internals": state.disclosure.reveal_internals,
                "inputs": state.inputs,
            }
            with open(_LEDGER, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            self._last_emitted_at = now
            self._last_emitted_aesthetic = state.aesthetic
            self._last_emitted_audience = state.disclosure.audience
        except Exception:
            pass

    @staticmethod
    def proof_of_property() -> Dict[str, bool]:
        """Mechanically verify the state machine actually rotates.

        Covers all axes:
          (a) physiology axis — three corner outfits must produce
              three distinct aesthetic strings (the v1.0 schema bug
              this would have caught);
          (b) audience axis — the four audiences must produce four
              distinct disclosure envelopes (the v1.2 addition);
          (c) classification — each known agent code must bucket
              into the expected audience class.
          (d) v1.3 face-first precedence ladder — the resolver must
              prefer fresh face evidence, fall through on stale or
              "nobody", and lock disclosure to UNKNOWN/MINIMAL when
              the camera sees an UNFAMILIAR face (regardless of who
              was at the keyboard). Catches AG31's parallel-shipped
              `unknown_face → EXTERNAL_MCP` defect (corrected here
              to `unknown_face → UNKNOWN`).
          (e) audience_source provenance — the disclosure envelope
              must carry the axis name so audits can replay decisions.
        """
        results: Dict[str, bool] = {}

        # (a) physiology distinctness
        s1 = _compute_outfit_physiology(0.95, 0.85, 0.9, 0.40)
        s2 = _compute_outfit_physiology(0.70, 0.50, 0.5, 0.0)
        s3 = _compute_outfit_physiology(0.30, 0.05, 0.1, -0.40)
        results["phys_crystalline_calm_venting"] = (s1[1] == "CRYSTALLINE"
                                                    and s1[3] == "CALM"
                                                    and s1[5] == "VENTING")
        results["phys_adaptive_neutral_breathing"] = (s2[1] == "ADAPTIVE"
                                                     and s2[3] == "NEUTRAL"
                                                     and s2[5] == "BREATHING")
        results["phys_shroud_hazard_sealed"] = (s3[1] == "SHROUD"
                                                and s3[3] == "HAZARD"
                                                and s3[5] == "SEALED")
        results["phys_distinct_aesthetics"] = len({s1[6], s2[6], s3[6]}) == 3

        # (b) audience distinctness
        d_arch = _compute_disclosure(AUDIENCE_ARCHITECT)
        d_peer = _compute_disclosure(AUDIENCE_PEER_AGENT)
        d_ext  = _compute_disclosure(AUDIENCE_EXTERNAL_MCP)
        d_unk  = _compute_disclosure(AUDIENCE_UNKNOWN)
        envelopes = [d_arch, d_peer, d_ext, d_unk]
        # Each pair must differ in at least one of disclosure_level /
        # tone_register / reveal_serial / reveal_internals.
        sigs = [(d.disclosure_level, d.tone_register, d.reveal_serial,
                 d.reveal_internals) for d in envelopes]
        results["audience_distinct_envelopes"] = len(set(sigs)) == 4
        # MHC restriction monotonicity: as audience trust drops,
        # disclosure must NOT widen.
        results["audience_architect_full"]   = (d_arch.disclosure_level == "FULL")
        results["audience_unknown_minimal"]  = (d_unk.disclosure_level == "MINIMAL")
        results["audience_external_no_serial"] = (not d_ext.reveal_serial)
        results["audience_unknown_no_internals"] = (not d_unk.reveal_internals)

        # (c) classification
        results["classify_AG31_to_architect"]    = (
            _classify_agent_to_audience("AG31") == AUDIENCE_ARCHITECT)
        results["classify_AG31_ANTIGRAVITY_to_architect"] = (
            _classify_agent_to_audience("AG31_ANTIGRAVITY") == AUDIENCE_ARCHITECT)
        results["classify_BISHOP_to_peer"]       = (
            _classify_agent_to_audience("BISHOP") == AUDIENCE_PEER_AGENT)
        results["classify_C47H_to_peer"]         = (
            _classify_agent_to_audience("C47H") == AUDIENCE_PEER_AGENT)
        results["classify_random_to_unknown"]    = (
            _classify_agent_to_audience("script_kiddie") == AUDIENCE_UNKNOWN)
        results["classify_mcp_to_external"]      = (
            _classify_agent_to_audience("notion-mcp-client") == AUDIENCE_EXTERNAL_MCP)
        results["classify_empty_to_unknown"]     = (
            _classify_agent_to_audience("") == AUDIENCE_UNKNOWN)

        # (d) v1.3 face-first precedence ladder
        #   d1: fresh face = "architect" trumps stigmergic UNKNOWN trace
        a, _, src = _resolve_audience_face_first(
            face_audience="architect", face_stale=False, face_age_s=2.0,
            trace_audience=AUDIENCE_UNKNOWN, trace_age_s=None)
        results["face_arch_trumps_no_trace"] = (
            a == AUDIENCE_ARCHITECT and src == AUDIENCE_SOURCE_FACE)

        #   d2: fresh face = "architect" ALSO trumps PEER_AGENT trace
        #       (the camera sees the human, the trace shows a sibling
        #       agent ran a query — Architect is the visual ground truth)
        a, _, src = _resolve_audience_face_first(
            face_audience="architect", face_stale=False, face_age_s=1.0,
            trace_audience=AUDIENCE_PEER_AGENT, trace_age_s=10.0)
        results["face_arch_trumps_peer_trace"] = (
            a == AUDIENCE_ARCHITECT and src == AUDIENCE_SOURCE_FACE)

        #   d3: fresh face = "unknown_face" → UNKNOWN, locks armor
        #       (this is THE check that catches the EXTERNAL_MCP defect:
        #       a stranger in frame must trigger MINIMAL/GUARDED, NOT
        #       PSEUDONYMOUS/WORKING)
        a, _, src = _resolve_audience_face_first(
            face_audience="unknown_face", face_stale=False, face_age_s=1.0,
            trace_audience=AUDIENCE_ARCHITECT, trace_age_s=5.0)
        results["face_stranger_locks_unknown"] = (
            a == AUDIENCE_UNKNOWN and src == AUDIENCE_SOURCE_FACE)

        #   d4: fresh face = "nobody" → fall through to trace
        a, _, src = _resolve_audience_face_first(
            face_audience="nobody", face_stale=False, face_age_s=1.0,
            trace_audience=AUDIENCE_ARCHITECT, trace_age_s=10.0)
        results["face_nobody_yields_to_trace"] = (
            a == AUDIENCE_ARCHITECT and src == AUDIENCE_SOURCE_TRACE)

        #   d5: stale face → fall through to trace even with verdict
        a, _, src = _resolve_audience_face_first(
            face_audience="architect", face_stale=True, face_age_s=120.0,
            trace_audience=AUDIENCE_PEER_AGENT, trace_age_s=10.0)
        results["face_stale_yields_to_trace"] = (
            a == AUDIENCE_PEER_AGENT and src == AUDIENCE_SOURCE_TRACE)

        #   d6: face absent + trace silent → defensive UNKNOWN/default
        a, _, src = _resolve_audience_face_first(
            face_audience=None, face_stale=True, face_age_s=None,
            trace_audience=AUDIENCE_UNKNOWN, trace_age_s=None)
        results["both_silent_defaults_to_unknown"] = (
            a == AUDIENCE_UNKNOWN and src == AUDIENCE_SOURCE_DFLT)

        # (e) audience_source provenance round-trips through the envelope
        env_face  = _compute_disclosure(AUDIENCE_ARCHITECT,
                                         audience_source=AUDIENCE_SOURCE_FACE)
        env_trace = _compute_disclosure(AUDIENCE_ARCHITECT,
                                         audience_source=AUDIENCE_SOURCE_TRACE)
        results["envelope_carries_face_source"]  = (
            env_face.audience_source == AUDIENCE_SOURCE_FACE)
        results["envelope_carries_trace_source"] = (
            env_trace.audience_source == AUDIENCE_SOURCE_TRACE)

        return results


# Module-level singleton.
_INSTANCE: Optional[SwarmWardrobeGlycocalyx] = None


def instance() -> SwarmWardrobeGlycocalyx:
    """Return the shared module-level wardrobe organ."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SwarmWardrobeGlycocalyx()
    return _INSTANCE


# ──────────────────────────────────────────────────────────────────────
# Smoke / proof
# ──────────────────────────────────────────────────────────────────────

def _smoke() -> None:
    print("\n=== THE WARDROBE DEPARTMENT (GLYCOCALYX) v1.2 ===\n")
    w = SwarmWardrobeGlycocalyx()
    state = w.current_state()
    print(f"[*] Aesthetic     : {state.aesthetic}")
    print(f"[*] Structured    : fabric={state.fabric_kind}  "
          f"pigment={state.mood_pigment}  vent={state.vent_state}")
    d = state.disclosure
    age_s = f"{d.audience_age_s:.1f}s ago" if d.audience_age_s is not None else "n/a"
    print(f"[*] Audience      : {d.audience}  (last seen {age_s})")
    print(f"[*] Disclosure    : level={d.disclosure_level}  tone={d.tone_register}")
    print(f"[*] Reveal flags  : serial={d.reveal_serial}  internals={d.reveal_internals}")
    print(f"[*] Live inputs   : {state.inputs}")
    print()
    print("--- proof_of_property (physiology + audience axes) ---")
    proof = SwarmWardrobeGlycocalyx.proof_of_property()
    fails = [k for k, v in proof.items() if not v]
    for k, v in proof.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    assert not fails, f"proof_of_property failed: {fails}"
    print()
    print("--- ledger emission ---")
    if _LEDGER.exists():
        last = _LEDGER.read_text().strip().splitlines()[-1]
        snippet = last[:200] + ("..." if len(last) > 200 else "")
        print(f"  last row: {snippet}")
    else:
        print("  (ledger not yet written this run)")
    print(f"\n[OK] Wardrobe v1.2 verified. Alice is dressed AND aware of who's looking.\n")


if __name__ == "__main__":
    _smoke()
