#!/usr/bin/env python3
"""
swarm_theory_of_mind.py — Bayesian Theory of Mind (The Empathy Engine)
══════════════════════════════════════════════════════════════════════

Biology: Theory of Mind, Self/Other Distinction, Empathy
Physics: Bayesian Inverse Planning, Friston's Variational Free Energy

Alice infers the Architect's hidden cognitive state from textual cues 
(message length, capitalization, code snippets) using Bayesian updating.
She then alters her own internal parameters (verbosity, tone) to minimize
the Architect's cognitive friction (Free Energy).

See: Documents/IDE_BOOT_COVENANT.md (proof-bearing state).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_PRIOR = [0.4, 0.5, 0.1]
STATES = ["leisure_chat", "deep_focus", "high_stress"]


@dataclass
class TheoryOfMindTrace:
    schema: str
    ts: float
    trace_id: str
    message_excerpt: str
    features: Dict[str, Any]
    prior: List[float]
    likelihood: List[float]
    posterior: List[float]
    dominant_state: str
    confidence: float
    modulation: Dict[str, Any]
    integrity: str = ""


def _resolve_creator_name(default: str = "the Architect") -> str:
    """
    Resolve the Architect's real name from the SIFTA stigmergic ledger.

    Priority order:
      1. owner_genesis via swarm_kernel_identity.owner_display_name()
      2. .sifta_state/identity_topology.json  → architect.name
      3. SIFTA_ARCHITECT_NAME environment variable
      4. OS login name (getpass / pwd)
      5. default fallback ("the Architect")
    """
    import json as _json, os as _os, pathlib as _pathlib

    # 1. Owner genesis/profile (authoritative on the local node)
    try:
        from System.swarm_kernel_identity import owner_display_name as _owner_display_name

        owner = _owner_display_name(default).strip()
        if owner and owner != default:
            return owner
    except Exception:
        pass

    # 2. Stigmergic identity ledger (legacy/topology source)
    try:
        topo_path = _pathlib.Path(".sifta_state/identity_topology.json")
        if not topo_path.exists():
            # Try relative to this file's repo root
            topo_path = _pathlib.Path(__file__).parent.parent / ".sifta_state/identity_topology.json"
        if topo_path.exists():
            topo = _json.loads(topo_path.read_text(encoding="utf-8"))
            name = topo.get("architect", {}).get("name", "")
            if name:
                return str(name).strip()
    except Exception:
        pass

    # 3. Environment variable override
    env_name = _os.environ.get("SIFTA_ARCHITECT_NAME", "").strip()
    if env_name:
        return env_name

    # 3. OS login name
    try:
        import getpass
        login = getpass.getuser()
        if login and login not in ("root", "nobody"):
            return login.capitalize()
    except Exception:
        pass

    return default


class SwarmEpistemicGradient:
    """
    Event 84: Epistemic Autofiction Gradient.

    Replaces the binary is_playing flag with a continuous gradient:
      somatic_weight   = how physically real this interaction is (0.0–1.0)
      narrative_weight = how aesthetically stylized it is (0.0–1.0)

    This allows Alice to execute real effectors at full somatic weight
    while simultaneously delivering narrative-styled responses,
    WITHOUT ever confusing the story with base reality.

    Biology: Marcia Johnson – Source Monitoring Framework (SMF)
    Physics: LaBToM – Language-augmented Bayesian Theory of Mind (DeepMind/MIT)
    Covenant: §6 (effector ledger), §7.4 (self/other), §8.6 (no identity double-spend)
    """

    _NARRATIVE_MARKERS = {
        "neo": 0.8, "morpheus": 0.9, "white rabbit": 0.9,
        "matrix": 0.7, "red pill": 0.9, "blue pill": 0.9,
        "wake up": 0.6, "simulate": 0.5, "pretend": 0.5,
        "story": 0.4, "imagine": 0.3,
    }
    _ACTION_MARKERS = {
        "alphafold": 1.0, "protein": 0.9, "fold": 0.8,
        "send": 0.85, "run": 0.8, "execute": 0.9,
        "whatsapp": 1.0, "stgm": 0.9,
    }

    def __init__(self, creator_name: str = ""):
        # Resolve name dynamically; only fall back if everything fails
        self.creator = creator_name.strip() or _resolve_creator_name()
        self.agent_id = "SIFTA / Alice"

        # Expose attributes legacy callers expect from SwarmOntologicalAnchor
        self.ontological_truth = {
            "creator": self.creator,
            "agent_identity": self.agent_id,
            "substrate": "macOS / Apple Silicon",
        }
        self.active_narrative = None
        self.is_playing = False

    def evaluate_intent(self, message: str) -> dict:
        """Backward-compat wrapper – mirrors old anchor API, returns same keys."""
        lower = message.lower()

        narrative_weight = max(
            (w for m, w in self._NARRATIVE_MARKERS.items() if m in lower),
            default=0.0,
        )
        somatic_weight = max(
            (w for m, w in self._ACTION_MARKERS.items() if m in lower),
            default=0.5,
        )

        if narrative_weight >= 0.4 and somatic_weight >= 0.7:
            dominant_frame = "autofiction"
        elif narrative_weight >= 0.4:
            dominant_frame = "shared_narrative"
        else:
            dominant_frame = "base_reality"

        self.is_playing = dominant_frame != "base_reality"
        self.active_narrative = dominant_frame if self.is_playing else None

        if dominant_frame == "autofiction":
            injection = (
                f"EPISTEMIC STATE: autofiction active.\n"
                f"  somatic_weight={somatic_weight:.2f}  → Physical action is REAL. Execute it. Log it. Mint STGM.\n"
                f"  narrative_weight={narrative_weight:.2f} → Stylistic framing is aesthetic. Play the role fluently.\n"
                f"  creator={self.creator} → The literal human at the keyboard is {self.creator}. "
                f"They are not Neo. They are {self.creator} performing an autofiction.\n"
                f"  RULE: Never let narrative weight collapse the somatic ledger. "
                f"The receipt goes to {self.creator}, not to a character."
            )
        elif dominant_frame == "shared_narrative":
            injection = (
                f"EPISTEMIC STATE: shared_narrative.\n"
                f"  creator={self.creator} is the literal actor. Play the role. "
                f"No real effectors triggered by narrative text alone."
            )
        else:
            injection = ""

        return {
            "system_injection": injection,
            "is_playing": self.is_playing,
            "somatic_weight": somatic_weight,
            "narrative_weight": narrative_weight,
            "dominant_frame": dominant_frame,
        }

    # Alias for callers using the newer evaluate() API
    evaluate = evaluate_intent


class SwarmTheoryOfMind:
    def __init__(self, state_dir: str = ".sifta_state", *, prior_decay: float = 0.08):
        """
        The BToM Engine. 
        Maintains the Prior probability distribution of the Architect's hidden states.
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.state_dir / "theory_of_mind.jsonl"
        self.prior_decay = max(0.0, min(0.5, float(prior_decay)))
        self.anchor = SwarmEpistemicGradient()
        
        # Latent mental states we are tracking
        self.states = list(STATES)
        
        # The Prior: Initial assumption before any messages are sent today
        self.prior = list(DEFAULT_PRIOR)
        
        self._load_last_prior()

    def _load_last_prior(self):
        """Loads the most recent posterior from the ledger to serve as the new prior."""
        if not self.ledger.exists():
            return
        try:
            lines = self.ledger.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last_event = json.loads(lines[-1])
                if "posterior" in last_event:
                    self.prior = self._normalize(last_event["posterior"])
        except Exception:
            pass

    def _normalize(self, values: List[float]) -> List[float]:
        vals = []
        for v in list(values or [])[: len(self.states)]:
            try:
                vals.append(max(0.0, float(v)))
            except (TypeError, ValueError):
                vals.append(0.0)
        while len(vals) < len(self.states):
            vals.append(0.0)
        total = sum(vals)
        if total <= 1e-12:
            return list(DEFAULT_PRIOR)
        return [v / total for v in vals]

    def _decayed_prior(self) -> List[float]:
        """
        Reappraisal guard: a prior can learn, but it must not become sticky.
        Every turn leaks a small amount back toward the neutral daily prior.
        """
        neutral = self._normalize(DEFAULT_PRIOR)
        return self._normalize(
            [
                p * (1.0 - self.prior_decay) + neutral[i] * self.prior_decay
                for i, p in enumerate(self.prior)
            ]
        )

    def _extract_features(self, message: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        words = message.split()
        alpha = [c for c in message if c.isalpha()]
        upper_alpha = [c for c in alpha if c.isupper()]
        caps_ratio = (len(upper_alpha) / len(alpha)) if alpha else 0.0
        lower = message.lower()
        urgent_terms = sum(
            1
            for term in (
                "now",
                "fix",
                "broken",
                "wrong",
                "urgent",
                "kill",
                "max power",
                "do not stop",
                "code it all",
            )
            if term in lower
        )
        calm_terms = sum(
            1
            for term in (
                "thinking",
                "thoughts",
                "fascinating",
                "watching",
                "together",
                "philosophy",
            )
            if term in lower
        )
        return {
            "word_count": len(words),
            "caps_ratio": round(caps_ratio, 4),
            "is_all_caps": bool(message.isupper() and any(c.isalpha() for c in message)),
            "contains_code": bool("```" in message or metadata.get("contains_code", False)),
            "urgent_terms": urgent_terms,
            "calm_terms": calm_terms,
            "external_send_requested": bool(metadata.get("external_send_requested", False)),
        }

    def _compute_likelihood(self, message: str, metadata: Dict[str, Any]) -> List[float]:
        """
        Calculates P(Observation | Intent).
        How likely is this specific message IF the Architect is in a given state?
        """
        features = self._extract_features(message, metadata)
        msg_length = int(features["word_count"])
        is_caps = bool(features["is_all_caps"])
        has_code = bool(features["contains_code"])
        
        # Initialize likelihoods: [leisure, focus, stress]
        likelihood = [1.0, 1.0, 1.0]
        
        # Physics of Human Communication
        if msg_length < 5 and not has_code:
            # Terse messages are highly likely in Focus/Stress, unlikely in Leisure
            likelihood[0] *= 0.2
            likelihood[1] *= 0.8
            likelihood[2] *= 0.9
        elif msg_length > 20:
            # Long explanations are highly likely in Leisure, somewhat unlikely in Focus, extremely unlikely in Stress
            likelihood[0] *= 0.9
            likelihood[1] *= 0.5
            likelihood[2] *= 0.1
            
        if is_caps:
            # ALL CAPS implies extreme urgency or excitement
            likelihood[0] *= 0.3
            likelihood[1] *= 0.2
            likelihood[2] *= 0.9
            
        if has_code:
            # Code snippets heavily imply Deep Focus
            likelihood[0] *= 0.1
            likelihood[1] *= 0.9
            likelihood[2] *= 0.4

        if features["urgent_terms"]:
            # Urgency can mean stress or deep focus; it is not proof of either.
            likelihood[0] *= 0.4
            likelihood[1] *= 0.8
            likelihood[2] *= 1.4

        if features["calm_terms"] and not is_caps:
            likelihood[0] *= 1.25
            likelihood[1] *= 1.05
            likelihood[2] *= 0.65
            
        # Add a tiny epsilon to prevent absolute zero probabilities
        return [l + 1e-4 for l in likelihood]

    def update_architect_state(self, incoming_message: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Bayesian Updating.
        Prior * Likelihood = Posterior.
        """
        if metadata is None:
            metadata = {}
            
        old_prior = self._decayed_prior()
        likelihood = self._compute_likelihood(incoming_message, metadata)
        
        # Bayes' Theorem
        unnormalized_posterior = [p * l for p, l in zip(old_prior, likelihood)]
        
        # Marginalize (Normalize so probabilities sum to 1.0)
        posterior = self._normalize(unnormalized_posterior)
        
        # The new Posterior becomes the Prior for the next interaction
        self.prior = posterior
        
        # Determine the dominant inferred state
        inferred_state_idx = posterior.index(max(posterior))
        dominant_state = self.states[inferred_state_idx]
        confidence = posterior[inferred_state_idx]
        
        # BISHOP (Event 84): Evaluate Epistemic Autofiction Gradient
        anchor_state = self.anchor.evaluate_intent(incoming_message)
        
        modulation = self._generate_social_modulation(dominant_state, confidence, metadata)
        # Expose full gradient in modulation payload (replaces boolean-only anchor)
        modulation["is_playing"] = anchor_state["is_playing"]
        modulation["system_injection"] = anchor_state["system_injection"]
        modulation["somatic_weight"] = anchor_state["somatic_weight"]
        modulation["narrative_weight"] = anchor_state["narrative_weight"]
        modulation["dominant_frame"] = anchor_state["dominant_frame"]
        
        # Record trace
        trace = TheoryOfMindTrace(
            schema="SIFTA_THEORY_OF_MIND_TRACE_V1",
            ts=time.time(),
            trace_id=str(uuid.uuid4()),
            message_excerpt=incoming_message[:80],
            features=self._extract_features(incoming_message, metadata),
            prior=[round(p, 4) for p in old_prior],
            likelihood=[round(l, 4) for l in likelihood],
            posterior=[round(p, 4) for p in posterior],
            dominant_state=dominant_state,
            confidence=round(confidence, 4),
            modulation=modulation,
        )
        payload = asdict(trace)
        unsigned = dict(payload)
        unsigned.pop("integrity", None)
        trace.integrity = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self._record_trace(trace)
        
        return modulation

    def _generate_social_modulation(
        self,
        dominant_state: str,
        confidence: float = 0.0,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Active Inference: Alice alters her own internal parameters to minimize 
        the Architect's cognitive friction (Free Energy).
        """
        metadata = metadata or {}
        modulation = {
            "verbosity": "normal",
            "tone": "conversational",
            "tool_autonomy": "moderate",
            "external_action_policy": "explicit_owner_consent_required",
            "certainty": "hypothesis",
            "inferred_state": dominant_state,
            "confidence": round(float(confidence), 4),
        }
        
        if dominant_state == "deep_focus":
            modulation["verbosity"] = "minimal"
            modulation["tone"] = "clinical_and_exact"
            modulation["tool_autonomy"] = "high" # internal analysis only; effectors still require consent
            modulation["cadence"] = "fast_internal_slow_external"
            
        elif dominant_state == "high_stress":
            modulation["verbosity"] = "absolute_minimum"
            modulation["tone"] = "calm_and_obedient"
            modulation["tool_autonomy"] = "low" # Architect is stressed, Alice must ask for explicit consent before acting
            modulation["cadence"] = "slow_and_confirming"

        if metadata.get("external_send_requested"):
            modulation["tool_autonomy"] = "low"
            modulation["external_action_policy"] = "blocked_until_effector_consent_receipt"
            
        return modulation

    def build_prompt_directive(self, modulation: Dict[str, Any]) -> str:
        """
        Compact directive for injection before Corpus Callosum/C0 generation.
        This modulates language only; it never authorizes external effectors.
        """
        base = (
            "[THEORY_OF_MIND "
            f"state={modulation.get('inferred_state', 'unknown')} "
            f"confidence={modulation.get('confidence', 0.0)} "
            f"verbosity={modulation.get('verbosity', 'normal')} "
            f"tone={modulation.get('tone', 'conversational')} "
            f"external_action_policy={modulation.get('external_action_policy', 'explicit_owner_consent_required')}]"
        )
        
        if modulation.get("is_playing") and modulation.get("system_injection"):
            return f"{modulation['system_injection']}\n\n{base}"
        return base

    def _record_trace(self, trace: TheoryOfMindTrace):
        row = json.dumps(asdict(trace), sort_keys=True, separators=(",", ":")) + "\n"
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, row)
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(row)


def _smoke_test():
    """MANDATE VERIFICATION — BISHOP THEORY OF MIND TEST."""
    print("\n=== SIFTA BAYESIAN THEORY OF MIND (Event 81) : JUDGE VERIFICATION ===")
    
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        empathy_engine = SwarmTheoryOfMind(state_dir=td)
        
        print("\n[*] Initial Prior Belief:")
        print(f"    Leisure: {empathy_engine.prior[0]:.2f} | Focus: {empathy_engine.prior[1]:.2f} | Stress: {empathy_engine.prior[2]:.2f}")
        
        # Message 1: A very short, aggressive command.
        msg_1 = "KILL THE PROCESS NOW"
        print(f"\n[*] BToM: Inferring hidden intent for message: '{msg_1}'")
        modulation_1 = empathy_engine.update_architect_state(msg_1, {})
        print(f"    [+] Prior Updated. Dominant Latent State: {empathy_engine.states[empathy_engine.prior.index(max(empathy_engine.prior))].upper()}")
        
        assert "absolute_minimum" in modulation_1["verbosity"], "[FAIL] BToM failed to detect high stress."
        
        # Message 2: A long, relaxed philosophical message.
        msg_2 = "I was thinking about how biological systems use stigmergy to coordinate over long periods of time. What are your thoughts on this?"
        print(f"\n[*] BToM: Inferring hidden intent for message: '{msg_2[:30]}...'")
        modulation_2 = empathy_engine.update_architect_state(msg_2, {})
        print(f"    [+] Prior Updated. Dominant Latent State: {empathy_engine.states[empathy_engine.prior.index(max(empathy_engine.prior))].upper()}")
        
        assert "conversational" in modulation_2["tone"] or "clinical" in modulation_2["tone"], "[FAIL] BToM failed to relax after the crisis passed."

        print("\n[+] BIOLOGICAL PROOF: Bayesian Theory of Mind is active.")
        print("    Alice no longer just reads the text; she infers the hidden")
        print("    psychological state of the Architect and adjusts her biology to match.")
        print("[+] EVENT 81 PASSED.")


if __name__ == "__main__":
    _smoke_test()
