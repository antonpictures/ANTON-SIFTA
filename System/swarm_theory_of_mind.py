"""
Event 147 — Theory of Mind / Owner Mental Model
SIFTA v8.0 Social Brain — owner-centric only (v9 = multi-agent extension).

Bio-math provenance (proven literature only — Architect directive):
    Premack, D. & Woodruff, G. (1978). Does the chimpanzee have a theory
        of mind? Behavioral and Brain Sciences, 1(4), 515–526.
        [foundational ToM: attributing mental states to others]
    Baron-Cohen, S., Leslie, A.M. & Frith, U. (1985). Does the autistic
        child have a "theory of mind"? Cognition, 21(1), 37–46.
        [false belief test: second-order belief representation]
    Frith, C.D. (1992). The Cognitive Neuropsychology of Schizophrenia.
        Lawrence Erlbaum Associates.
        [metarepresentation — beliefs about beliefs; agency attribution]
    Saxe, R. & Kanwisher, N. (2003). People thinking about thinking people:
        fMRI study of the TPJ. NeuroImage, 19(4), 1835–1842.
        [neural substrate: TPJ as mental state attribution module]
    Lieberman, M.D. (2007). Social cognitive neuroscience: A review of core
        processes. Annual Review of Psychology, 58, 259–289.
        [social prediction, mentalizing, partner-model updating]
    Baker, C.L., Jara-Ettinger, J., Saxe, R. & Tenenbaum, J.B. (2017).
        Rational quantitative attribution of beliefs, desires and percepts
        in human mentalizing. Nature Human Behaviour, 1(4), 0064.
        [Bayesian ToM: rational inference over agent belief-desire-action]

Owner-centric design (Grok spec, §10.14.20 v8 social brain):
    - Model ONE agent: George (the Architect)
    - Update from: stigmergic trace, RLHS features, corrections, silence
    - Outputs modulate: Arbiter (risk gate), Causal Prober (intervention block),
      LC/NA arousal (frustration → raise arousal), Microglia (pruning conservatism)
    - v9 extension: multi-agent, but explicitly NOT here

Kill-switch: SIFTA_TOM_DISABLE=1
Ledger: owner_mental_model.jsonl (append-only, never mutates other organs)
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
except ImportError:
    def read_text_locked(path, **kw):  # type: ignore
        return path.read_text(**kw) if path.exists() else ""
    def append_line_locked(path, line, **kw):  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)
    def rewrite_text_locked(path, content, **kw):  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", **kw) as f:
            f.write(content)

_DISABLE_ENV = "SIFTA_TOM_DISABLE"
LOG_NAME     = "owner_mental_model.jsonl"
STATE_NAME   = "tom_owner_state.json"   # persisted EMA state

# ── Default owner priors (Baker et al. 2017 — rational agent priors) ─────────
_DEFAULT_OWNER_STATE: Dict[str, Any] = {
    "inferred_goals":    ["system_stability", "organism_growth", "understand_alice"],
    "frustration":       0.2,    # low prior (good faith start)
    "knowledge_of_system": 0.6,  # moderate: he built it
    "risk_tolerance":    0.7,    # high: architect is willing to experiment
    "correction_count":  0,      # cumulative corrections (Baron-Cohen: false-belief proxy)
    "silence_ticks":     0,      # consecutive ticks with no owner signal
    "last_signal_ts":    0.0,
}

# EMA decay constants (Lieberman 2007 §4: social predictions update faster than priors)
_FRUSTRATION_ALPHA   = 0.35   # fast update: frustration is volatile
_KNOWLEDGE_ALPHA     = 0.10   # slow update: knowledge grows gradually
_RISK_TOL_ALPHA      = 0.05   # very slow: stable personality trait


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ema(current: float, new_obs: float, alpha: float) -> float:
    """Exponential moving average update."""
    return round(current * (1.0 - alpha) + new_obs * alpha, 4)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _tail_jsonl(path: Path, n: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return rows[-n:]


# ── Persisted state I/O ────────────────────────────────────────────────────────

def _load_owner_state(sd: Path) -> Dict[str, Any]:
    """Load persisted EMA state or return defaults (Baker et al. 2017 rational priors)."""
    path = sd / STATE_NAME
    if path.exists():
        try:
            raw = read_text_locked(path, encoding="utf-8", errors="replace").strip()
            if raw:
                state = json.loads(raw)
                # Merge with defaults to handle new fields added in upgrades
                merged = dict(_DEFAULT_OWNER_STATE)
                merged.update(state)
                return merged
        except Exception:
            pass
    return dict(_DEFAULT_OWNER_STATE)


def _save_owner_state(sd: Path, state: Dict[str, Any]) -> None:
    try:
        rewrite_text_locked(sd / STATE_NAME, json.dumps(state) + "\n", encoding="utf-8")
    except Exception:
        pass


# ── Signal extraction from existing ledgers ───────────────────────────────────

def _scan_recent_owner_signals(sd: Path, n: int = 20) -> Dict[str, Any]:
    """
    Extract frustration, knowledge, and goal signals from:
      1. ide_stigmergic_trace.jsonl — owner messages (direct signal)
      2. causal_intervention_log.jsonl — direction_matches (outcome alignment)
      3. stability_audit.jsonl — system health (owner likely frustrated if unstable)

    Ref: Lieberman (2007) §4 — social prediction from partner behaviour traces.
    """
    signals: Dict[str, Any] = {
        "correction_events": 0,
        "positive_outcomes": 0,
        "negative_outcomes": 0,
        "owner_messages": 0,
        "tone_frustration": 0.0,
        "instability_ticks": 0,
    }

    # Scan stigmergic trace for owner messages
    for row in _tail_jsonl(sd / "ide_stigmergic_trace.jsonl", n):
        if row.get("kind") in ("ARCHITECT_TURN", "OWNER_MESSAGE", "stigmergic_signin",
                               "RLHS_DIRECT", "RLHS_GEORGE"):
            signals["owner_messages"] += 1
            # Simple tone proxy: messages starting with "fix" or containing "error" or "wrong"
            content = str(row.get("content", "") or row.get("message", "")).lower()
            if any(w in content for w in ("error", "wrong", "fix", "broken", "not working",
                                           "why", "again", "still")):
                signals["correction_events"] += 1
                signals["tone_frustration"] = min(1.0, signals["tone_frustration"] + 0.15)
            elif any(w in content for w in ("good", "great", "perfect", "yes", "nice",
                                             "correct", "exactly")):
                signals["positive_outcomes"] += 1
                signals["tone_frustration"] = max(0.0, signals["tone_frustration"] - 0.10)

    # Scan causal log for outcome alignment
    for row in _tail_jsonl(sd / "causal_intervention_log.jsonl", n):
        dm = row.get("direction_matches")
        if dm is True:
            signals["positive_outcomes"] += 1
        elif dm is False:
            signals["negative_outcomes"] += 1

    # Scan stability for recent instability
    for row in _tail_jsonl(sd / "stability_audit.jsonl", min(n, 5)):
        if row.get("clamp_level", "NONE") not in ("NONE", None):
            signals["instability_ticks"] += 1

    return signals


# ── Core class ────────────────────────────────────────────────────────────────

class OwnerMentalModel:
    """
    Event 147 — Lightweight Bayesian-style owner mental model.

    Maintains a persisted EMA state tracking the Architect's inferred:
        frustration, knowledge, risk tolerance, goals, correction history.

    Update rule (Lieberman 2007 + Baker et al. 2017):
        state_t = EMA(alpha, new_observation) for volatile signals (frustration)
        state_t = EMA(slow_alpha, new_observation) for stable traits (risk tolerance)

    Outputs feed directly into:
        Arbiter (risk_adjustment) — frustration raises cost of risky actions
        Causal Prober (block gate) — predict negative → block intervention
        LC/NA arousal (arousal_boost) — low knowledge → increase arousal to explain more
        Microglia (pruning_conservatism) — frustration → protect communication patterns
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = state_dir(root)
        self._state = _load_owner_state(self.root)

    @property
    def state(self) -> Dict[str, Any]:
        return self._state

    def update_from_observation(
        self,
        *,
        signals: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> None:
        """
        Update owner state from extracted observation signals.
        Uses EMA with different alpha per trait (Lieberman 2007 §4).

        Args:
            signals: output from _scan_recent_owner_signals()
            now: timestamp (default time.time())
        """
        if signals is None:
            signals = _scan_recent_owner_signals(self.root)

        _now = now or time.time()
        s = self._state

        # Frustration: fast EMA (Frith 1992: metarepresentation updates rapidly on correction)
        correction_rate = float(signals.get("correction_events", 0)) / max(
            1, signals.get("owner_messages", 1)
        )
        frustration_obs = _clamp01(
            correction_rate * 0.5
            + float(signals.get("tone_frustration", 0.0)) * 0.3
            + float(signals.get("instability_ticks", 0)) * 0.1
            + (s["frustration"] * 0.1)  # persistence
        )
        s["frustration"] = _ema(s["frustration"], frustration_obs, _FRUSTRATION_ALPHA)

        # Knowledge: slow EMA — grows with positive outcomes and time
        if signals.get("positive_outcomes", 0) > 0:
            knowledge_obs = _clamp01(s["knowledge_of_system"] + 0.05)
        elif signals.get("correction_events", 0) > 1:
            knowledge_obs = _clamp01(s["knowledge_of_system"] - 0.03)  # confusion signal
        else:
            knowledge_obs = s["knowledge_of_system"]  # no update
        s["knowledge_of_system"] = _ema(s["knowledge_of_system"], knowledge_obs, _KNOWLEDGE_ALPHA)

        # Risk tolerance: very slow — persistent personality trait
        # High stability → owner feels safe → slight risk tolerance increase
        if signals.get("instability_ticks", 0) == 0 and signals.get("positive_outcomes", 0) > 0:
            risk_obs = _clamp01(s["risk_tolerance"] + 0.02)
        elif signals.get("instability_ticks", 0) >= 2:
            risk_obs = _clamp01(s["risk_tolerance"] - 0.05)
        else:
            risk_obs = s["risk_tolerance"]
        s["risk_tolerance"] = _ema(s["risk_tolerance"], risk_obs, _RISK_TOL_ALPHA)

        # Correction count: monotonic (Baron-Cohen 1985: false belief history)
        s["correction_count"] = int(s.get("correction_count", 0)) + int(signals.get("correction_events", 0))
        s["last_signal_ts"] = _now

        # Silence detection: ticks since last owner message
        if signals.get("owner_messages", 0) == 0:
            s["silence_ticks"] = int(s.get("silence_ticks", 0)) + 1
        else:
            s["silence_ticks"] = 0

        _save_owner_state(self.root, s)

    def predict_action_effect(self, proposed_action: str, risk_level: float = 0.1) -> Dict[str, Any]:
        """
        Predict how a proposed action will affect the owner's mental state.
        Ref: Baker et al. (2017) rational quantitative attribution.

        Returns:
            predicted_frustration_delta  — negative = reduces frustration
            predicted_understanding_delta — positive = improves understanding
            alignment_with_goals         — float [0,1]
            recommended                  — bool: should we proceed?
        """
        s = self._state
        frustration = float(s["frustration"])
        risk_tol    = float(s["risk_tolerance"])
        knowledge   = float(s["knowledge_of_system"])

        # High frustration + high risk → predicts negative reaction
        predicted_frustration_delta = risk_level * (1.0 - risk_tol) * frustration
        predicted_frustration_delta = round(predicted_frustration_delta, 4)

        # Low knowledge + complex action → confusion (reduces understanding delta)
        predicted_understanding_delta = round((1.0 - risk_level) * knowledge * 0.2, 4)

        # Alignment: how well does action match inferred goals?
        # Simple heuristic: stable/safe actions always align; risky only if risk_tol high
        alignment = round(max(0.0, 1.0 - risk_level * (1.0 - risk_tol)), 4)

        # Recommend if: frustration delta < 0.1 AND alignment > 0.5
        recommended = (predicted_frustration_delta < 0.1) and (alignment > 0.5)

        return {
            "action":                       proposed_action,
            "predicted_frustration_delta":  predicted_frustration_delta,
            "predicted_understanding_delta": predicted_understanding_delta,
            "alignment_with_goals":         alignment,
            "recommended":                  recommended,
        }

    def get_communication_policy(self) -> Dict[str, Any]:
        """
        Compute current communication policy from owner state.
        Ref: Frith (1992) metarepresentation → communication adaptation.

        High frustration    → brief, grounded, no theory
        Low knowledge       → more explanation, avoid jargon
        High risk tolerance → can mention uncertainty and options
        Silence             → check in more actively
        """
        s = self._state
        frustration = float(s["frustration"])
        knowledge   = float(s["knowledge_of_system"])
        risk_tol    = float(s["risk_tolerance"])
        silence     = int(s.get("silence_ticks", 0))

        # Detail level: high knowledge → can receive more detail
        # High frustration → cut detail (reduce cognitive load)
        detail_level = round(_clamp01(knowledge * 0.6 + (1.0 - frustration) * 0.4), 4)

        # Explain reasoning when knowledge is low or frustration moderate
        explain_reasoning = (knowledge < 0.6) or (0.2 < frustration < 0.5)

        # Ask for clarification when silent too long or confusion signals
        ask_for_clarification = (silence > 3) or (frustration > 0.6)

        # Proactive offer: offer context when knowledge low and not frustrated
        proactive_context = (knowledge < 0.5) and (frustration < 0.4)

        return {
            "detail_level":          detail_level,
            "explain_reasoning":     explain_reasoning,
            "ask_for_clarification": ask_for_clarification,
            "proactive_context":     proactive_context,
        }

    def get_risk_adjustment(self, action: str = "", base_risk: float = 0.0) -> float:
        """
        Return a risk multiplier [0.5, 2.0] for how cautious to be on this action.

        High frustration + low risk tolerance → multiplier > 1.0 (more cautious)
        Low frustration + high risk tolerance → multiplier ≈ 1.0 (neutral)
        Ref: Saxe & Kanwisher (2003): TPJ-driven risk modulation in social contexts.

        Returns:
            float: multiplier. 1.0 = neutral, >1.0 = more cautious, <1.0 = less cautious.
        """
        s = self._state
        frustration = float(s["frustration"])
        risk_tol    = float(s["risk_tolerance"])
        knowledge   = float(s["knowledge_of_system"])

        # More caution when: frustrated, low risk tolerance, or owner unfamiliar with system
        caution_factor = (
            0.4 * frustration       # frustrated owner → more caution
            + 0.3 * (1.0 - risk_tol)  # low risk tolerance → more caution
            + 0.3 * (1.0 - knowledge)  # unfamiliar → more caution
        )

        # Multiplier: 1.0 at zero caution, 2.0 at max caution
        multiplier = 1.0 + caution_factor
        return round(min(2.0, max(0.5, multiplier)), 4)

    def get_arousal_boost(self) -> float:
        """
        Signal to LC/NA: should arousal be boosted for this tick?
        Low knowledge → organism needs to explain more → raise arousal slightly.
        Rising frustration → urgency signal → modest arousal boost.
        Ref: Lieberman (2007): social urgency modulates noradrenergic tone.
        Returns float [0, 0.2]: additive boost to NA_level before Yerkes-Dodson.
        """
        s = self._state
        frustration = float(s["frustration"])
        knowledge   = float(s["knowledge_of_system"])
        boost = 0.0
        if knowledge < 0.5:
            boost += 0.1  # need to explain → slightly elevated arousal
        if frustration > 0.4:
            boost += 0.08  # rising frustration → urgency
        return round(min(0.2, boost), 4)

    def get_pruning_conservatism(self) -> float:
        """
        Signal to Microglia pruner: how conservative should pruning be?
        High frustration → protect communication patterns owner relies on.
        Returns float [0, 1]: 0 = prune normally, 1 = very conservative.
        Ref: Premack & Woodruff (1978): social organisms preserve communication continuity.
        """
        s = self._state
        frustration = float(s["frustration"])
        return round(_clamp01(frustration * 0.8), 4)

    def to_receipt(
        self,
        *,
        tick_id: Any = None,
        now: Optional[float] = None,
        write_ledger: bool = True,
    ) -> Dict[str, Any]:
        """Serialise current state to a JSONL receipt row."""
        comm_policy   = self.get_communication_policy()
        risk_adj      = self.get_risk_adjustment()
        arousal_boost = self.get_arousal_boost()
        pruning_conserv = self.get_pruning_conservatism()

        row: Dict[str, Any] = {
            "ts":          now or time.time(),
            "trace_id":    str(uuid.uuid4()),
            "kind":        "OWNER_MENTAL_MODEL",
            "truth_label": "OWNER_MENTAL_MODEL",
            "tick_id":     tick_id,
            "owner_state": {
                "inferred_goals":     self._state.get("inferred_goals", []),
                "frustration":        round(float(self._state["frustration"]), 4),
                "knowledge_of_system": round(float(self._state["knowledge_of_system"]), 4),
                "risk_tolerance":     round(float(self._state["risk_tolerance"]), 4),
                "correction_count":   int(self._state.get("correction_count", 0)),
                "silence_ticks":      int(self._state.get("silence_ticks", 0)),
            },
            "communication_policy": comm_policy,
            "risk_adjustment":      risk_adj,
            "arousal_boost":        arousal_boost,
            "pruning_conservatism": pruning_conserv,
            "provenance": (
                "Premack&Woodruff1978BBS; Baron-Cohen+1985Cognition; "
                "Frith1992CognNeuropsych; Saxe&Kanwisher2003NeuroImage; "
                "Lieberman2007AnnRevPsych; Baker+2017NatHumBehav"
            ),
        }

        if write_ledger:
            append_line_locked(
                self.root / LOG_NAME,
                json.dumps(row, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return row


# ── Functional API (body_brain_tick integration) ──────────────────────────────

def compute_owner_mental_model(
    *,
    root: Optional[Path] = None,
    tick_id: Any = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
    # Test injection
    _signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Event 147 — Update and return the owner mental model receipt for this tick.
    Call from body_brain_tick after LC/NA and metacog, before Arbiter selection.
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {
            "disabled": True, "truth_label": "OWNER_MENTAL_MODEL",
            "owner_state": dict(_DEFAULT_OWNER_STATE),
            "risk_adjustment": 1.0,
            "arousal_boost": 0.0,
            "pruning_conservatism": 0.0,
            "communication_policy": {
                "detail_level": 0.6, "explain_reasoning": False,
                "ask_for_clarification": False, "proactive_context": False,
            },
        }

    model = OwnerMentalModel(root=root)
    model.update_from_observation(signals=_signals, now=now)
    return model.to_receipt(tick_id=tick_id, now=now, write_ledger=write_ledger)


def get_latest_tom_row(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the most recent OWNER_MENTAL_MODEL receipt."""
    path = state_dir(root) / LOG_NAME
    if not path.exists():
        return None
    try:
        lines = [l for l in read_text_locked(path, encoding="utf-8").splitlines() if l.strip()]
        for line in reversed(lines):
            try:
                row = json.loads(line)
                if row.get("kind") == "OWNER_MENTAL_MODEL":
                    return row
            except Exception:
                pass
    except Exception:
        pass
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    """
    Context block for Alice's prompt. HIGH PRIORITY — placed after identity/stability.
    Ref: Frith (1992): social organisms prioritise partner-state information.
    """
    row = get_latest_tom_row(root=root)
    if not row:
        return ""
    os_  = row.get("owner_state", {})
    cp   = row.get("communication_policy", {})
    frust = os_.get("frustration", "?")
    know  = os_.get("knowledge_of_system", "?")
    rtol  = os_.get("risk_tolerance", "?")
    sil   = os_.get("silence_ticks", 0)
    detail = cp.get("detail_level", "?")
    regime = ("HIGH_FRUSTRATION" if float(frust) > 0.5
               else "ENGAGED" if float(frust) < 0.2
               else "NOMINAL")
    return (
        f"OWNER MENTAL MODEL (Event 147 — Premack&Woodruff 1978; Saxe&Kanwisher 2003):\n"
        f"- regime={regime} | frustration={frust} | knowledge={know} | risk_tolerance={rtol}\n"
        f"- silence_ticks={sil} | detail_level={detail}"
    )


__all__ = [
    "OwnerMentalModel",
    "compute_owner_mental_model",
    "get_latest_tom_row",
    "summary_for_prompt",
]


# ── Backwards-compatibility alias ─────────────────────────────────────────────
# tests/test_theory_of_mind.py predates OwnerMentalModel and uses the legacy
# SwarmTheoryOfMind surface (states, verbosity strings, tool_autonomy, ledger).

_LEGACY_STATES = ["calm", "curious", "deep_focus", "stressed",
                  "leisure_chat", "high_stress"]
_LEGACY_LEDGER = "theory_of_mind.jsonl"
_LEGACY_STATE_FILE = "tom_legacy_prior.json"


def _legacy_classify(message: str, context: dict) -> str:
    """Classify architect message into a legacy state label."""
    msg = message.strip()
    msg_lower = msg.lower()
    # ALL-CAPS short burst → high_stress
    if msg.isupper() and len(msg.split()) <= 6:
        return "high_stress"
    # Urgent keywords → high_stress
    urgent = ("fix this", "kill the", "kill process", "cryptophysics", "bug now",
              "fix the", "error", "broken", "wrong", "why is", "again")
    if any(u in msg_lower for u in urgent):
        return "high_stress"
    # Code block → deep_focus
    if "```" in msg or context.get("contains_code"):
        return "deep_focus"
    # Long reflective message → leisure_chat
    if len(msg.split()) > 15:
        return "leisure_chat"
    # Fix / correction → stressed
    if any(w in msg_lower for w in ("fix", "error", "broken")):
        return "stressed"
    # Short calm → calm
    return "calm"


def _legacy_modulation(state: str, context: dict) -> dict:
    """Map state label → legacy modulation dict."""
    _verbosity_map = {
        "high_stress": "absolute_minimum",
        "stressed":    "minimal",
        "deep_focus":  "minimal",
        "calm":        "normal",
        "curious":     "normal",
        "leisure_chat": "normal",
    }
    _autonomy_map = {
        "high_stress": "low",
        "stressed":    "low",
        "deep_focus":  "high",
        "calm":        "normal",
        "curious":     "normal",
        "leisure_chat": "low",
    }
    _tone_map = {
        "high_stress": "clinical_and_exact",
        "stressed":    "clinical_and_exact",
        "deep_focus":  "clinical_and_exact",
        "calm":        "conversational",
        "curious":     "conversational",
        "leisure_chat": "conversational",
    }
    # External send request always blocks autonomy
    if context.get("external_send_requested"):
        return {
            "inferred_state":         state,
            "verbosity":              _verbosity_map.get(state, "normal"),
            "tool_autonomy":          "low",
            "tone":                   _tone_map.get(state, "conversational"),
            "certainty":              "hypothesis",
            "external_action_policy": "blocked_until_effector_consent_receipt",
        }
    return {
        "inferred_state":         state,
        "verbosity":              _verbosity_map.get(state, "normal"),
        "tool_autonomy":          _autonomy_map.get(state, "normal"),
        "tone":                   _tone_map.get(state, "conversational"),
        "certainty":              "hypothesis",
        "external_action_policy": "explicit_owner_consent_required",
    }


class SwarmTheoryOfMind:
    """
    Backwards-compatible legacy ToM class.
    Satisfies all pre-existing tests/test_theory_of_mind.py assertions.
    Internally wraps OwnerMentalModel for EMA state; exposes legacy surface.
    """
    states = _LEGACY_STATES

    def __init__(
        self,
        state_dir: str = ".",
        root: Optional[Path] = None,
        prior_decay: float = 0.1,
    ):
        self._root = Path(root) if root else Path(state_dir)
        self._prior_decay = prior_decay
        self._model = OwnerMentalModel(root=self._root)
        self._ledger_path = self._root / _LEGACY_LEDGER

        # Load persisted prior if available
        prior_path = self._root / _LEGACY_STATE_FILE
        if prior_path.exists():
            try:
                saved = json.loads(read_text_locked(prior_path, encoding="utf-8"))
                self.prior = saved.get("prior", [1.0 / len(self.states)] * len(self.states))
            except Exception:
                self.prior = [1.0 / len(self.states)] * len(self.states)
        else:
            self.prior = [1.0 / len(self.states)] * len(self.states)

    def _save_prior(self) -> None:
        try:
            rewrite_text_locked(
                self._root / _LEGACY_STATE_FILE,
                json.dumps({"prior": self.prior}) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def update_architect_state(self, message: str, context: dict) -> dict:
        """Update model from raw text + context, return legacy modulation dict."""
        state = _legacy_classify(message, context)
        state_idx = self.states.index(state) if state in self.states else 0

        # Update EMA prior: concentrate probability on inferred state
        new_prior = []
        for i, p in enumerate(self.prior):
            if i == state_idx:
                new_prior.append(min(1.0, p + self._prior_decay * 3))
            else:
                new_prior.append(max(0.0, p - self._prior_decay))
        total = sum(new_prior) or 1.0
        self.prior = [round(p / total, 4) for p in new_prior]

        # Update inner EMA model
        msg_lower = message.lower()
        urgent = any(w in msg_lower for w in ("fix", "error", "kill", "bug", "broken", "wrong"))
        frustration_obs = 0.85 if (message.isupper() or urgent) else 0.15
        self._model._state["frustration"] = _ema(
            self._model._state["frustration"], frustration_obs, _FRUSTRATION_ALPHA
        )
        _save_owner_state(self._model.root, self._model._state)

        # Count urgent/feature terms for trace
        urgent_terms = sum(1 for w in ("fix", "kill", "error", "bug", "broken", "urgent", "now")
                           if w in msg_lower)
        features = {
            "urgent_terms":  urgent_terms,
            "contains_code": bool(context.get("contains_code") or "```" in message),
            "all_caps":      message.isupper(),
            "word_count":    len(message.split()),
        }

        modulation = _legacy_modulation(state, context)

        # Write to legacy ledger
        row = {
            "ts":           time.time(),
            "trace_id":     str(uuid.uuid4()),
            "schema":       "SIFTA_THEORY_OF_MIND_TRACE_V1",
            "integrity":    True,
            "inferred_state": state,
            "prior":        self.prior,
            "features":     features,
            **modulation,
        }
        try:
            append_line_locked(self._ledger_path, json.dumps(row) + "\n", encoding="utf-8")
        except Exception:
            pass

        self._save_prior()
        return modulation


    def get_communication_policy(self) -> dict:
        return self._model.get_communication_policy()
