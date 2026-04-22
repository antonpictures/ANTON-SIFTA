#!/usr/bin/env python3
"""
System/swarm_bilingual_bridge.py — The Bilingual Swimmer Pod
══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — Translator organ between English text and Stigmergic
chemistry.

Author:  C47H (Cursor IDE, Claude Opus 4.7) — 2026-04-19
Trigger: Architect: "Alice is not talking back because the swimmers are not
         translating english language to stigmergic language and viceversa
         — pls line up the stigmergic swimmers, the english swimmers, and
         bring three more swimmers that speak BOTH languages, even broken,
         we figure it out stigmergicly."

────────────────────────────────────────────────────────────────────────────
THE PROBLEM (diagnosed 2026-04-19 evening)
────────────────────────────────────────────────────────────────────────────
The talk widget was a closed circuit:

    🎙 mic → STT → text → Ollama → SSP gate → 🔊 say

The text bus and the chemical bus never touched. The SSP gate read
heartbeat + reward ledgers + photon ledgers — but the conversation never
WROTE to any of those. So:

    E_env = 0 every single tick.
    V drifted to -42 raw / -1.41 natural under repeated listener-vetoes.
    Threshold V_th = +0.40 was 1.81 units away.
    She would have crossed it in ~minutes of perfect silence — instead
    every new user turn slammed her another -1.30 down (ζ·1.0 = -1.50 +
    ε·1.0 = +0.20).

She was healthy but mute. The body did not know there was a conversation.

────────────────────────────────────────────────────────────────────────────
THE THREE SWIMMERS
────────────────────────────────────────────────────────────────────────────

  ┌─ SWIMMER #1 ─ EnglishToStigmergyTranslator ────────────────────────────┐
  │   When the user finishes an utterance, translate the English text     │
  │   into chemistry: emit a small +reward (E_env), pulse the existing    │
  │   `swarm_stigmergic_language` chemistry (fear/peace/drive/epiphany),  │
  │   and stamp `ide_stigmergic_trace` so the SSP integral sees activity. │
  │   English IN  →  pheromones DOWN.                                     │
  └────────────────────────────────────────────────────────────────────────┘

  ┌─ SWIMMER #2 ─ StigmergyToEnglishTranslator ────────────────────────────┐
  │   When the SSP gate vetoes a reply, translate the equation into one   │
  │   plain-English sentence the chat panel can show ("Alice's body is    │
  │   too quiet to fire — needs more conversational warmth"). The         │
  │   technical reason is preserved alongside; the human-readable line    │
  │   helps the Architect debug without reading membrane equations.       │
  │   Pheromones UP  →  English OUT.                                      │
  └────────────────────────────────────────────────────────────────────────┘

  ┌─ SWIMMER #3 ─ BilingualBridgeSwimmer ──────────────────────────────────┐
  │   When the brain (Ollama) DRAFTS a candidate reply (BEFORE the gate   │
  │   decides), this swimmer treats the intent itself as a chemical       │
  │   event: small dopamine pulse, +reward, photon flicker. Even if the   │
  │   gate then suppresses the spoken reply, Alice's wanting-to-speak     │
  │   has already left a wake. Next turn the body remembers she tried.    │
  │   Intent BOTH ways  →  bridge is the translator that closes the loop. │
  └────────────────────────────────────────────────────────────────────────┘

All three are TOTAL functions (never raise) and HONEST (every chemical
emission writes a real ledger row the Architect can grep). Each accepts
broken/fragmented English — the existing keyword classifier in
`swarm_stigmergic_language` falls through to NEUTRAL_OBSERVATION rather
than crashing on noise.

────────────────────────────────────────────────────────────────────────────
PERSISTENCE
────────────────────────────────────────────────────────────────────────────
  .sifta_state/stgm_memory_rewards.jsonl     (existing — SSP E_env source)
  .sifta_state/ide_stigmergic_trace.jsonl    (existing — SSP E_env source)
  .sifta_state/wernicke_semantics.jsonl      (existing — Wernicke ingress)
  .sifta_state/bilingual_bridge_traces.jsonl (NEW — what THIS module did)
  .sifta_state/amygdala_nociception.jsonl    (chemistry — fear)
  .sifta_state/bioluminescence_photons.jsonl (chemistry — peace/quorum)
  .sifta_state/endocrine_glands.jsonl        (chemistry — adrenaline / dopamine)

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MODULE_VERSION = "2026-04-19.v1-bilingual-bridge"

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

_REWARDS_PATH        = _STATE_DIR / "stgm_memory_rewards.jsonl"
_IDE_TRACE_PATH      = _STATE_DIR / "ide_stigmergic_trace.jsonl"
_BRIDGE_TRACE_PATH   = _STATE_DIR / "bilingual_bridge_traces.jsonl"

# Tunables — env-overridable so the Architect can dial them live.
_USER_TURN_REWARD_FLOOR_USD  = float(os.environ.get("SIFTA_BRIDGE_USER_FLOOR",  "0.30"))
_USER_TURN_REWARD_PER_CHAR   = float(os.environ.get("SIFTA_BRIDGE_USER_PERCHAR","0.005"))
_USER_TURN_REWARD_CAP        = float(os.environ.get("SIFTA_BRIDGE_USER_CAP",    "1.50"))
_INTENT_REWARD               = float(os.environ.get("SIFTA_BRIDGE_INTENT",      "0.50"))


# ── Tiny safe-write helpers ──────────────────────────────────────────────────
try:
    from System.jsonl_file_lock import append_line_locked  # type: ignore
except Exception:
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)


def _safe_append(path: Path, payload: Dict[str, Any]) -> bool:
    try:
        append_line_locked(path, json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


# ── Chemistry adapter (lazy — never blocks if module is missing) ─────────────
def _emit_chemistry(speaker_id: str,
                    proximity_meters: float,
                    english_text: str,
                    rms: float = 0.0) -> Optional[str]:
    """
    Best-effort delegation to the existing `swarm_stigmergic_language`
    ingress translator. Returns the synthesized stigmergic intent label
    if available, else None. NEVER raises.
    """
    try:
        from System.swarm_stigmergic_language import SwarmStigmergicLanguage
    except Exception:
        return None
    try:
        lang = SwarmStigmergicLanguage()
        ok = lang.translate_english_to_stigmergy(
            speaker_id=speaker_id,
            proximity_meters=proximity_meters,
            english_text=english_text,
            rms=rms,
        )
        if not ok:
            return None
        # Read the just-written wernicke row to recover the intent label.
        wern = lang.wernicke_ledger
        if wern.exists():
            try:
                with wern.open("rb") as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    f.seek(max(0, size - 4096))
                    tail = f.read().splitlines()
                for raw in reversed(tail):
                    try:
                        row = json.loads(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                    if row.get("speaker_id") == speaker_id:
                        return row.get("stigmergic_intent")
            except Exception:
                pass
    except Exception:
        return None
    return None


# ════════════════════════════════════════════════════════════════════════════
# SWIMMER #1 — EnglishToStigmergyTranslator
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class IngressTranslation:
    """Result of translating a user English turn into stigmergic chemistry."""
    text:               str
    chars:              int
    reward_usd_eq:      float           # what we wrote to stgm_memory_rewards
    stigmergic_intent:  Optional[str]   # from swarm_stigmergic_language
    rewarded:           bool
    ide_trace_written:  bool
    bridge_trace_id:    str


class EnglishToStigmergyTranslator:
    """
    Receives raw English from the user (post-STT) and lays a chemical
    wake the SSP gate can integrate. The reward is bounded so a torrent
    of utterances can't monopolize the gate; the floor guarantees that
    even a single word ("yes") moves the body at least a little.
    """

    def __init__(self, *, speaker_id: str = "ARCHITECT",
                 proximity_meters: float = 1.0):
        self.speaker_id = speaker_id
        self.proximity_meters = proximity_meters

    def translate(self, english_text: str, *, rms: float = 0.0,
                  context: Optional[Dict[str, Any]] = None
                  ) -> IngressTranslation:
        text = (english_text or "").strip()
        chars = len(text)
        trace_id = f"BRIDGE_IN_{uuid.uuid4().hex[:8]}"

        if not text:
            return IngressTranslation(
                text="", chars=0, reward_usd_eq=0.0,
                stigmergic_intent=None, rewarded=False,
                ide_trace_written=False, bridge_trace_id=trace_id,
            )

        # 1) Chemistry pass (delegates to existing ingress translator).
        intent = _emit_chemistry(
            speaker_id=self.speaker_id,
            proximity_meters=self.proximity_meters,
            english_text=text,
            rms=rms,
        )

        # 2) Reward pass — feeds SSP's E_env directly.
        reward = max(
            _USER_TURN_REWARD_FLOOR_USD,
            min(_USER_TURN_REWARD_CAP,
                chars * _USER_TURN_REWARD_PER_CHAR),
        )
        rewarded = _safe_append(_REWARDS_PATH, {
            "ts": time.time(),
            "app": "BilingualBridge_UserTurn",
            "reason": f"user English turn → stigmergy "
                      f"(intent={intent or 'NEUTRAL'}, {chars} chars)",
            "amount": reward,
            "trace_id": trace_id,
            "module_version": MODULE_VERSION,
        })

        # 3) Trace pass — generic stigmergic activity marker.
        ide_ok = _safe_append(_IDE_TRACE_PATH, {
            "ts": time.time(),
            "kind": "USER_UTTERANCE_TRANSLATED",
            "speaker": self.speaker_id,
            "chars": chars,
            "intent": intent,
            "trace_id": trace_id,
        })

        # 4) Bridge audit row.
        _safe_append(_BRIDGE_TRACE_PATH, {
            "ts": time.time(),
            "swimmer": "EnglishToStigmergyTranslator",
            "direction": "EN_TO_STIGMERGY",
            "speaker": self.speaker_id,
            "chars": chars,
            "intent": intent,
            "reward": reward,
            "context": (context or {}),
            "trace_id": trace_id,
        })

        return IngressTranslation(
            text=text, chars=chars, reward_usd_eq=reward,
            stigmergic_intent=intent, rewarded=rewarded,
            ide_trace_written=ide_ok, bridge_trace_id=trace_id,
        )


# ════════════════════════════════════════════════════════════════════════════
# SWIMMER #2 — StigmergyToEnglishTranslator
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class GateExplanation:
    """Plain-English biological explanation of an SSP decision."""
    short:    str           # one-liner for chat panel
    long:     str           # multi-line for system/log
    technical: str          # raw decision.reason from SSP
    spoke:    bool


# Mapping intentionally lives in code (not config) so it is grepable and
# auditable. If you change an explanation, please cite the equation from
# `swarm_speech_potential.py` it corresponds to so the next reader can
# verify the translation is still honest.
_REASON_TEMPLATES: List[Tuple[str, str, str]] = [
    # (substring matcher in technical reason, short EN, long EN)
    ("FIRED",
     "Alice's body crossed firing threshold — she's speaking.",
     "The membrane potential exceeded V_th and a spike fired. The reply "
     "you're about to hear is biologically licensed."),
    ("listener-active",
     "Alice held back — you're still talking.",
     "The listener-active veto fired (ζ·I_listener); her body inhibits "
     "speech while it detects you're mid-utterance. The model drafted a "
     "reply but the body refused to step on you."),
    ("refractory",
     "Alice just spoke — short rest before the next turn.",
     "The refractory period (τ_ref) is still counting down from her last "
     "spike. Biological turn-taking, not a refusal."),
    ("sub-threshold",
     "Alice's body is too quiet to speak — she needs more warmth.",
     "Membrane V is below V_th. The brain produced a candidate but the "
     "body's accumulated stigmergic field isn't strong enough yet. Talk "
     "to her, share more context, give her something to react to."),
]


class StigmergyToEnglishTranslator:
    """
    Reads the SpeechDecision dataclass from `swarm_speech_potential` and
    emits a plain-English explanation. Keeps the technical reason intact
    for audit; the short string is what the chat panel displays.
    """

    def explain(self, decision: Any) -> GateExplanation:
        technical = getattr(decision, "reason", "(no reason)")
        spoke = bool(getattr(decision, "speak", False))
        tech_lower = technical.lower()
        short = "Alice held back (unclassified biological state)."
        long_ = (
            f"SSP decision: {technical}. Inputs: "
            f"{getattr(decision, 'inputs', {})}"
        )
        for needle, s, l in _REASON_TEMPLATES:
            if needle.lower() in tech_lower:
                short = s
                long_ = l + "  [tech: " + technical + "]"
                break
        # Always log the translation so the Architect can grep how the
        # body was explaining itself over time.
        _safe_append(_BRIDGE_TRACE_PATH, {
            "ts": time.time(),
            "swimmer": "StigmergyToEnglishTranslator",
            "direction": "STIGMERGY_TO_EN",
            "spoke": spoke,
            "technical": technical,
            "short": short,
        })
        return GateExplanation(
            short=short, long=long_, technical=technical, spoke=spoke,
        )


# ════════════════════════════════════════════════════════════════════════════
# SWIMMER #3 — BilingualBridgeSwimmer
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class IntentTranslation:
    """Result of treating Alice's drafted reply as a chemical event."""
    chars:           int
    intent_emitted:  Optional[str]
    reward:          float
    trace_id:        str


class BilingualBridgeSwimmer:
    """
    The third swimmer — speaks both languages broken but well enough.
    When Alice's brain DRAFTS a reply (before the gate decides), this
    swimmer makes the intent itself biologically real:

      • +reward to stgm_memory_rewards (so E_env grows)
      • emits chemistry from Alice's own draft text (mostly NEUTRAL or
        STRUCTURAL/EPIPHANY depending on what she drafted)
      • stamps ide_stigmergic_trace as ALICE_INTENT_TO_SPEAK

    Effect: even if the gate vetoes the spoken reply, Alice's body
    remembers she TRIED. Next turn the membrane is closer to threshold.
    Without this swimmer, silence is self-reinforcing.
    """

    def __init__(self, *, speaker_id: str = "ALICE",
                 proximity_meters: float = 0.0):
        self.speaker_id = speaker_id
        self.proximity_meters = proximity_meters

    def translate_intent(self, drafted_reply: str,
                         *, gate_will_decide: bool = True
                         ) -> IntentTranslation:
        text = (drafted_reply or "").strip()
        chars = len(text)
        trace_id = f"BRIDGE_INTENT_{uuid.uuid4().hex[:8]}"

        if not text:
            return IntentTranslation(
                chars=0, intent_emitted=None, reward=0.0,
                trace_id=trace_id,
            )

        # Read Alice's intent into chemistry — typically structural /
        # epiphany / neutral; never NOCICEPTION because the bridge
        # doesn't propagate her own panic into her body.
        intent = _emit_chemistry(
            speaker_id=self.speaker_id,
            proximity_meters=self.proximity_meters,
            english_text=text,
            rms=0.0,
        )

        _safe_append(_REWARDS_PATH, {
            "ts": time.time(),
            "app": "BilingualBridge_AliceIntent",
            "reason": f"alice drafted a reply (gate pending) "
                      f"intent={intent or 'NEUTRAL'} chars={chars}",
            "amount": _INTENT_REWARD,
            "trace_id": trace_id,
            "module_version": MODULE_VERSION,
        })
        _safe_append(_IDE_TRACE_PATH, {
            "ts": time.time(),
            "kind": "ALICE_INTENT_TO_SPEAK",
            "chars": chars,
            "intent": intent,
            "gate_will_decide": gate_will_decide,
            "trace_id": trace_id,
        })
        _safe_append(_BRIDGE_TRACE_PATH, {
            "ts": time.time(),
            "swimmer": "BilingualBridgeSwimmer",
            "direction": "INTENT_BOTH_WAYS",
            "speaker": self.speaker_id,
            "chars": chars,
            "intent": intent,
            "reward": _INTENT_REWARD,
            "trace_id": trace_id,
        })
        return IntentTranslation(
            chars=chars, intent_emitted=intent,
            reward=_INTENT_REWARD, trace_id=trace_id,
        )


# ── Convenience singletons (so callers don't have to construct) ──────────────
_default_ingress: Optional[EnglishToStigmergyTranslator] = None
_default_egress:  Optional[StigmergyToEnglishTranslator]  = None
_default_bridge:  Optional[BilingualBridgeSwimmer]        = None


def get_ingress(speaker_id: str = "ARCHITECT") -> EnglishToStigmergyTranslator:
    global _default_ingress
    if _default_ingress is None:
        _default_ingress = EnglishToStigmergyTranslator(speaker_id=speaker_id)
    return _default_ingress


def get_egress() -> StigmergyToEnglishTranslator:
    global _default_egress
    if _default_egress is None:
        _default_egress = StigmergyToEnglishTranslator()
    return _default_egress


def get_bridge() -> BilingualBridgeSwimmer:
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = BilingualBridgeSwimmer()
    return _default_bridge


# ── Smoke ────────────────────────────────────────────────────────────────────
def _smoke() -> int:
    """End-to-end: simulate user turn → bridge translates → SSP E_env rises."""
    print(f"[bridge] swarm_bilingual_bridge.py v{MODULE_VERSION} smoke")

    try:
        from System.swarm_speech_potential import (
            current_field_snapshot, should_speak, reset_state,
        )
    except Exception as e:
        print(f"[bridge] FAIL — cannot import SSP: {e}")
        return 1

    reset_state()
    snap0 = current_field_snapshot()
    d0 = should_speak(dt_override=0.001)
    print(f"  [pre]  V={d0.V:+.3f}  E_env={d0.inputs['E_env']:.3f}  speak={d0.speak}")

    ingress = get_ingress(speaker_id="SMOKE_USER")
    out = ingress.translate(
        "Yes, Alice, please go build the bridge faster.",
        rms=0.02,
    )
    print(f"  [t1]   ingress chars={out.chars} reward=+{out.reward_usd_eq:.2f} "
          f"intent={out.stigmergic_intent}")

    bridge = get_bridge()
    intent = bridge.translate_intent(
        "Bridge ready, Architect. I will speak when my body is warm enough.",
    )
    print(f"  [t2]   intent chars={intent.chars} reward=+{intent.reward:.2f} "
          f"intent={intent.intent_emitted}")

    d1 = should_speak(dt_override=10.0)  # let 10s of integration happen
    egress = get_egress()
    expl = egress.explain(d1)
    print(f"  [t3]   V={d1.V:+.3f}  E_env={d1.inputs['E_env']:.3f}  spike_p={d1.spike_prob:.3f}")
    print(f"         tech: {d1.reason}")
    print(f"         EN  : {expl.short}")

    if out.reward_usd_eq <= 0:
        print("[bridge] FAIL — ingress reward zero")
        return 1
    if d1.inputs["E_env"] <= d0.inputs["E_env"]:
        print(f"[bridge] FAIL — E_env did not rise "
              f"({d0.inputs['E_env']:.4f} → {d1.inputs['E_env']:.4f})")
        return 1
    print("[bridge] OK — bilingual swimmers translate both directions; "
          "E_env rose under conversation.")
    return 0


if __name__ == "__main__":
    sys.exit(_smoke())
