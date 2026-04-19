#!/usr/bin/env python3
"""
mutation_governor.py — Stability organ for genome-driven mutations
════════════════════════════════════════════════════════════════════
Thermodynamic constraint layer between:

  MycelialGenome (mutation pressure)  →  SCAR / Neural Gate (execution)

Prevents:
  - runaway self-rewrite
  - replay loops (identical mutation spam)
  - hotspot collapse (one file hammered)
  - unbounded global mutation rate

Replay hashes are recorded only on successful commit(), not on rejected
candidates, so failed attempts do not poison future proposals.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_GOVERNOR_STATE = _STATE_DIR / "mutation_governor.json"

# Cap stored replay hashes to bound memory (FIFO eviction via deque)
_MAX_REPLAY_TRACK = 8000

# ── §5.2.x Path sensitivity (heat-aware governance) ──────────────
# Raw heat units that saturate the [0, 1] sensitivity overlay.
# A sensor write of `intensity = SENSITIVITY_HEAT_SATURATION` drives the
# overlay to 1.0 (matches a "System" substring contribution exactly).
SENSITIVITY_HEAT_SATURATION: float = 100.0

# Sentinel meaning "we tried to load SwarmPotentialField once and failed"
# — prevents re-import storms on every gate call when SPF is absent.
_SPF_UNAVAILABLE = object()


class MutationGovernor:
    """
    Controls genome-driven mutations with:
    - global rate limiting (per minute)
    - per-file budgets
    - per-file cooldown
    - mutation replay protection (content-hash)
    - heat-aware risk/friction/reversibility scoring (System/Kernel
      substring floor + SwarmPotentialField overlay; degrades to
      substring-only when the field is cold or unavailable)
    - dual-sig audit gate (optional, structural): every SCAR must carry
      a PheromoneTrace (proposer) + ApprovalTrace (reviewer) when
      require_dual_sig=True. Reviewer must be in the allowlist.

    §5.2 Leverage mechanisms (SOLID_PLAN):
    - friction layer: state-disruption cost penalizes noisy mutation
    - reversibility index: low-undo actions require human gate
    - attention budget: hard cap on reads/writes/spawns per cycle
    - dual-sig gate: cross-review before commit (structural, not stylistic)

    Quorum tier: when friction > 0.7 and require_dual_sig=True,
    the gate requires _dual_sig_quorum approvals (default 2).
    Wire this after allowlist is populated with ≥2 reviewer keys.
    """

    # ── §5.2.3 Attention budget defaults ─────────────────────────
    ATTENTION_COSTS = {
        "read_trace":    5,
        "analyze_event": 10,
        "write_trace":   8,
        "mutate_file":   15,
        "spawn_agent":   50,
    }

    def __init__(
        self,
        max_mutations_per_minute: int = 5,
        file_budget: int = 10,
        cooldown: float = 30.0,
        risk_threshold: float = 0.7,
        # §5.2 leverage knobs
        friction_ceiling: float = 0.8,
        reversibility_threshold: float = 0.3,
        attention_budget_per_cycle: int = 100,
        # §5.2.11 Dual-sig audit gate
        require_dual_sig: bool = False,
        reviewer_allowlist: Optional[set] = None,
        _dual_sig_quorum: int = 1,
    ):
        self.max_mutations_per_minute = max_mutations_per_minute
        self.file_budget = file_budget
        self.cooldown = cooldown
        self.risk_threshold = risk_threshold

        # §5.2 leverage
        self.friction_ceiling = friction_ceiling
        self.reversibility_threshold = reversibility_threshold
        self.attention_budget_per_cycle = attention_budget_per_cycle
        self._attention_spent: int = 0
        self._cycle_start: float = time.time()

        # §5.2.11 Dual-sig gate
        # require_dual_sig=False by default — flip True after callers are migrated.
        # reviewer_allowlist: set of reviewer_public_key_hex strings (flat, v1).
        # reviewer_registry:  ReviewerRegistry (TUF-adapted, threshold-aware, preferred).
        # Empty allowlist + no registry + require_dual_sig=True → fail-closed (blocks all).
        self.require_dual_sig: bool = require_dual_sig
        self._reviewer_allowlist: set = set(reviewer_allowlist or [])
        self._reviewer_registry = None  # populated via set_reviewer_registry()
        # Quorum: SCARs with friction > 0.7 require this many approvals.
        # Default 1. Bump to 2 once ≥2 reviewer keys are in the allowlist.
        # TUF threshold: wire _reviewer_registry.threshold_for_role("auditor") here.
        self._dual_sig_quorum: int = _dual_sig_quorum

        self._global_events: deque[float] = deque()
        self._file_budgets: dict[str, int] = defaultdict(lambda: file_budget)
        self._last_mutation_time: dict[str, float] = {}
        self._seen_hashes: deque[str] = deque(maxlen=_MAX_REPLAY_TRACK)
        self._seen_set: set[str] = set()
        self.last_reject_reason: str = ""

        # Lazy SwarmPotentialField cache (populated on first sensitivity query).
        # Holds either: None (not yet attempted), an SPF instance, or
        # _SPF_UNAVAILABLE (tried and failed — degrade to substring-only).
        self._spf_cached = None

        self._load()  # may replace _seen_hashes from disk

    # ── Risk ─────────────────────────────────────────────────────

    def _mutation_content_hash(self, mutation: str) -> str:
        return hashlib.sha256(mutation.encode()).hexdigest()

    def _risk_score(self, file_path: str, mutation: str) -> float:
        score = 0.0
        score += self._path_sensitivity(file_path) * 0.5
        if len(mutation) > 500:
            score += 0.2
        return min(score, 1.0)

    # ── §5.2.x Heat-aware path sensitivity ───────────────────────

    def _get_potential_field(self):
        """
        Lazy-load the SwarmPotentialField once per governor instance.

        Returns the SPF instance, or None if the module is unavailable or
        instantiation failed. Caches the failure case via _SPF_UNAVAILABLE
        so we don't pay an import attempt on every gate call.

        The governor degrades gracefully to substring-only sensitivity if
        the field is absent — daughter-safe: never raises into the gate.
        """
        if self._spf_cached is _SPF_UNAVAILABLE:
            return None
        if self._spf_cached is not None:
            return self._spf_cached
        try:
            try:
                from System.swarm_potential_field import SwarmPotentialField
            except ImportError:
                from swarm_potential_field import SwarmPotentialField  # type: ignore
            self._spf_cached = SwarmPotentialField()
            return self._spf_cached
        except Exception:
            self._spf_cached = _SPF_UNAVAILABLE
            return None

    def _path_sensitivity(self, file_path: str) -> float:
        """
        Heat-aware path sensitivity weight in [0, 1.6].

        Sources, combined via MAX (heat never relaxes a substring contribution;
        a substring match never silences a hot-field signal):

          • Substring floor — backward compatibility for cold/missing field:
              "System" in fp → +1.0
              "Kernel" in fp → +0.6   (matches old risk-gate ratio 0.3/0.5)
            Floors are additive, so a path containing both substrings yields
            1.6 (preserving the original gate's +0.8 risk-score behavior when
            multiplied by the call site's 0.5 weight).

          • Heat overlay — only when SwarmPotentialField is loaded AND the
            resolved path has positive heat. Negative heat (dead zones) is
            intentionally NOT a sensitivity signal here: dead zones are an
            auto-immune concern, not a mutation-pressure concern.
                heat_norm = clamp01(raw_heat / SENSITIVITY_HEAT_SATURATION)

        Path resolution anchors to _REPO (the governor's repo root), NOT the
        process cwd, because SwarmPotentialField stores absolute resolved
        paths written by sensors that may run from any directory. A naive
        Path(fp).resolve() would silently miss every field key — exactly
        the BUG-17 cosmetic-wiring failure mode (read-side wired, write-side
        not).
        """
        fp = file_path.replace("\\", "/")

        substring_weight = 0.0
        if "System" in fp:
            substring_weight += 1.0
        if "Kernel" in fp:
            substring_weight += 0.6

        heat_weight = 0.0
        spf = self._get_potential_field()
        if spf is not None:
            try:
                abs_path = (_REPO / fp).resolve()
                raw_heat = spf.field.get(abs_path, 0.0)
                if raw_heat > 0.0:
                    heat_weight = min(1.0, raw_heat / SENSITIVITY_HEAT_SATURATION)
            except Exception:
                pass  # Sensitivity NEVER raises into the gate

        return max(substring_weight, heat_weight)

    # ── §5.2.11 Dual-sig audit gate ──────────────────────────────

    def add_reviewer(self, reviewer_public_key_hex: str) -> None:
        """
        Register a reviewer public key in the flat allowlist.
        For threshold-aware multi-role governance, prefer set_reviewer_registry().
        TODO: persist allowlist to .sifta_state/reviewer_allowlist.json
        TODO: revocation — per-key revocation list in .sifta_state/revoked_keys.json
        """
        self._reviewer_allowlist.add(reviewer_public_key_hex)

    def remove_reviewer(self, reviewer_public_key_hex: str) -> None:
        """Remove a reviewer key from the flat allowlist (key rotation / revocation)."""
        self._reviewer_allowlist.discard(reviewer_public_key_hex)

    def set_reviewer_registry(self, registry: object) -> None:
        """
        Use a ReviewerRegistry (TUF-adapted, threshold-aware) as the authoritative
        source for reviewer pubkeys. Takes precedence over the flat allowlist.
        """
        self._reviewer_registry = registry

    def _check_dual_sig(
        self,
        friction: float,
        proposer_trace: object,
        approver_traces: list,
    ) -> bool:
        """
        Verify the dual-sig contract for a SCAR proposal.

        Quorum: high-friction SCARs (friction > 0.7) require _dual_sig_quorum
        DISTINCT approvals (multiset blocked — same fix as python-tuf
        fix-signature-threshold: counting the same key twice toward quorum
        is a Sybil attack vector).

        Uses ReviewerRegistry if set, falls back to flat allowlist.
        """
        try:
            try:
                from System.swimmer_pheromone_identity import verify_approval, APPROVAL_TTL
            except ImportError:
                from swimmer_pheromone_identity import verify_approval, APPROVAL_TTL

            if proposer_trace is None:
                self.last_reject_reason = "dual_sig:missing_proposer_trace"
                return False
            if not approver_traces:
                self.last_reject_reason = "dual_sig:missing_approver_trace"
                return False

            # Quorum: high-friction SCARs require more approvals
            required = self._dual_sig_quorum if friction > 0.7 else 1

            valid_approvals = 0
            seen_reviewer_ids: set = set()  # TUF Sybil fix: distinct keys only
            for apr in approver_traces:
                # Block same reviewer counting twice toward quorum
                if apr.reviewer_id in seen_reviewer_ids:
                    continue
                if verify_approval(
                    proposer_trace, apr,
                    reviewer_allowlist=self._reviewer_allowlist if self._reviewer_allowlist else None,
                    reviewer_registry=self._reviewer_registry,
                    approval_ttl=APPROVAL_TTL,
                ):
                    seen_reviewer_ids.add(apr.reviewer_id)
                    valid_approvals += 1
                if valid_approvals >= required:
                    return True

            self.last_reject_reason = (
                f"dual_sig:insufficient_approvals:{valid_approvals}/{required}"
            )
            return False

        except Exception as exc:
            # Dual-sig gate NEVER raises into the caller.
            self.last_reject_reason = f"dual_sig:error:{type(exc).__name__}"
            return False

    # ── §5.2.1 Friction layer ────────────────────────────────────

    def friction_cost(self, file_path: str, mutation: str) -> float:
        """
        State disruption cost, not just compute.
        Biology works because change is expensive.
        """
        complexity = min(1.0, len(mutation) / 2000)
        fp = file_path.replace("\\", "/")
        # Magnitude: heat-aware path sensitivity (System/Kernel substring
        # floor preserved when SwarmPotentialField is cold or unavailable).
        magnitude = self._path_sensitivity(file_path) * 0.5
        if "__init__" in fp:
            magnitude += 0.2
        # Novelty penalty: unique hash = novel = higher friction
        h = self._mutation_content_hash(mutation)
        novelty = 0.0 if h in self._seen_set else 0.15
        return min(1.0, complexity + magnitude + novelty)

    # ── §5.2.2 Reversibility index ───────────────────────────────

    def reversibility_score(self, file_path: str, mutation: str) -> float:
        """
        Score undoability [0, 1]. 1.0 = fully reversible.
        Below threshold → require human gate.
        """
        score = 1.0
        # Deleting files is irreversible
        if "delete" in mutation.lower() or "rm " in mutation.lower():
            score -= 0.6
        # Heat-aware path sensitivity penalty: System/Kernel paths and any
        # path with positive SwarmPotentialField heat are harder to undo.
        # Multiplier 0.5 preserves the historical Kernel reversibility weight
        # (0.6 * 0.5 = 0.3) and tightens System reversibility (was 0.2 → 0.5),
        # consistent with the architect's safety-forward directive.
        score -= self._path_sensitivity(file_path) * 0.5
        # Large mutations are harder to review and revert
        if len(mutation) > 1000:
            score -= 0.15
        return max(0.0, score)

    # ── §5.2.3 Attention budget ──────────────────────────────────

    def _maybe_reset_attention_cycle(self) -> None:
        """Auto-reset attention every 60s (one swarm cycle)."""
        if time.time() - self._cycle_start > 60.0:
            self._attention_spent = 0
            self._cycle_start = time.time()

    def spend_attention(self, action: str = "mutate_file") -> bool:
        """
        Spend attention tokens. Returns True if budget allows.
        Call this from swim loops and blackboard readers.
        """
        self._maybe_reset_attention_cycle()
        cost = self.ATTENTION_COSTS.get(action, 10)
        if self._attention_spent + cost > self.attention_budget_per_cycle:
            return False
        self._attention_spent += cost
        return True

    def attention_remaining(self) -> int:
        """How many attention tokens remain this cycle."""
        self._maybe_reset_attention_cycle()
        return max(0, self.attention_budget_per_cycle - self._attention_spent)

    def reset_attention_cycle(self) -> None:
        """Manual epoch reset for attention budget."""
        self._attention_spent = 0
        self._cycle_start = time.time()

    # ── Global rate ──────────────────────────────────────────────

    def _global_allowed(self) -> bool:
        now = time.time()
        while self._global_events and now - self._global_events[0] > 60.0:
            self._global_events.popleft()
        return len(self._global_events) < self.max_mutations_per_minute

    def _file_allowed(self, file_path: str) -> bool:
        last = self._last_mutation_time.get(file_path, 0.0)
        return (time.time() - last) > self.cooldown

    def _track_seen(self, h: str) -> None:
        if h in self._seen_set:
            return
        mx = self._seen_hashes.maxlen
        if mx is not None and len(self._seen_hashes) == mx:
            old = self._seen_hashes[0]
            self._seen_set.discard(old)
        self._seen_hashes.append(h)
        self._seen_set.add(h)

    def _normalize_fp(self, file_path: str) -> str:
        """
        Normalize file_path to a stable repo-relative string before using
        it as a dict key in _file_budgets and _last_mutation_time.

        WHY: callers pass file_path in different forms depending on their
        working directory — absolute (/Users/ioanganton/Music/ANTON_SIFTA/...),
        partial (/Music/ANTON_SIFTA/...), or relative (System/foo.py).
        Without normalization, the same file accumulates separate budget
        entries under each path form, silently breaking budget accounting.

        Strategy: try to resolve to absolute, then express relative to _REPO.
        Falls back to the original string if resolution fails (safe-degrade).
        """
        try:
            p = Path(file_path)
            if not p.is_absolute():
                p = (_REPO / p).resolve()
            else:
                p = p.resolve()
            try:
                return str(p.relative_to(_REPO))
            except ValueError:
                return str(p)
        except Exception:
            return file_path

    # ── Public API ───────────────────────────────────────────────

    def allow(
        self,
        file_path: str,
        mutation: str,
        *,
        proposer_trace: Optional[object] = None,
        approver_traces: Optional[list] = None,
    ) -> bool:
        """
        Return True if this mutation may enter the SCAR proposal pipeline.
        Does not record replay hash — call commit() only after SCAR accepts.

        Gate order: temporal → replay → rate → cooldown → budget → risk →
                    §5.2 friction → §5.2 reversibility → §5.2 attention →
                    §5.2.11 dual-sig (when require_dual_sig=True) →
                    §5.2.10 objective → §5.2.7 shadow → §5.2.4 contradiction

        Dual-sig params (keyword-only, optional):
            proposer_trace  : PheromoneTrace signed by the proposing swimmer.
            approver_traces : list[ApprovalTrace] from registered reviewers.
            Both are ignored when require_dual_sig=False (default).
            When require_dual_sig=True and traces are absent → rejected.
        """
        self.last_reject_reason = ""
        file_path = self._normalize_fp(file_path)  # Step 1: stable key

        # ── §5.2.6 Temporal climate gate ──────────────────────────
        # If the swarm is in FROZEN state, block ALL mutations.
        # FROZEN = architect absent + dead zones detected.
        try:
            try:
                from System.temporal_layering import get_layer
            except ImportError:
                from temporal_layering import get_layer
            layer = get_layer()
            last = layer.get_last_pulse()
            if last and last.mutation_climate == "FROZEN":
                self.last_reject_reason = "temporal_frozen"
                return False
        except ImportError:
            pass

        h = self._mutation_content_hash(mutation)
        if h in self._seen_set:
            self.last_reject_reason = "replay"
            return False

        if not self._global_allowed():
            self.last_reject_reason = "global_rate"
            return False

        if not self._file_allowed(file_path):
            self.last_reject_reason = "cooldown"
            return False

        if self._file_budgets[file_path] <= 0:
            self.last_reject_reason = "file_budget"
            return False

        risk = self._risk_score(file_path, mutation)
        if risk > self.risk_threshold:
            self.last_reject_reason = f"risk:{risk:.2f}"
            return False

        # ── §5.2.1 Friction gate ─────────────────────────────────
        friction = self.friction_cost(file_path, mutation)
        if friction > self.friction_ceiling:
            self.last_reject_reason = f"friction:{friction:.2f}"
            return False

        # ── §5.2.2 Reversibility gate ────────────────────────────
        rev = self.reversibility_score(file_path, mutation)
        if rev < self.reversibility_threshold:
            self.last_reject_reason = f"reversibility:{rev:.2f}"
            return False

        # ── §5.2.3 Attention gate ────────────────────────────────
        if not self.spend_attention("mutate_file"):
            self.last_reject_reason = "attention_exhausted"
            return False

        # ── §5.2.11 Dual-sig audit gate ──────────────────────────
        # Convention becomes structural: gate refuses without the second sig
        # when enabled. Tiered: by default only the highest-risk paths require
        # dual-sig (Kernel/ and mutation_governor itself), minimising blast
        # radius until ≥2 reviewer keys are registered and the pipeline
        # produces ApprovalTraces in production.
        _fp_lower = file_path.lower()
        require_for_this = self.require_dual_sig and (
            "kernel" in _fp_lower or "mutation_governor" in _fp_lower
        )
        if require_for_this:
            if not self._check_dual_sig(
                friction, proposer_trace, list(approver_traces or [])
            ):
                return False  # last_reject_reason set inside _check_dual_sig
        # Non-tiered paths pass through in v1.
        # Expand require_for_this predicate after ≥2 reviewer keys registered
        # and the pipeline produces valid ApprovalTraces in production.

        # ── §5.2.10 Objective worth gate ─────────────────────────
        # Final question: is this mutation WORTH IT?
        try:
            from objective_registry import get_registry
            reg = get_registry()
            estimates = reg.estimate_mutation(
                file_path, mutation,
                friction=friction, reversibility=rev
            )
            if not reg.is_worth_it(estimates):
                self.last_reject_reason = f"objective_score:{reg.score_action(estimates):.2f}"
                return False
        except ImportError:
            pass  # Registry not available — degrade gracefully

        # ── §5.2.7 Shadow Simulation gate ────────────────────────
        # Ultimate sanity check: does the code compile?
        if file_path.endswith('.py'):
            try:
                try:
                    from System.shadow_simulator import get_simulator
                except ImportError:
                    from shadow_simulator import get_simulator
                sim = get_simulator()
                sim_ok, sim_msg = sim.simulate_mutation(file_path, mutation)
                if not sim_ok:
                    self.last_reject_reason = f"shadow_simulation_failed"
                    return False
            except ImportError:
                pass  # Simulator not available

        # ── §5.2.4 Contradiction gate ─────────────────────────────
        # For state mutations (.json files in .sifta_state), check if
        # the proposed content contradicts existing beliefs on the Blackboard.
        if file_path.endswith('.json') and '.sifta_state' in file_path:
            try:
                import json as _json
                try:
                    from System.contradiction_engine import get_engine
                except ImportError:
                    from contradiction_engine import get_engine
                engine = get_engine()
                # Load existing state and read proposed state
                existing_path = _REPO / file_path
                if existing_path.exists():
                    existing = _json.loads(existing_path.read_text())
                    proposed = _json.loads(mutation)  # mutation = new JSON string
                    agent_context = f"Governor:{file_path}"
                    # Check each key the proposed state wants to change
                    for k, new_val in proposed.items():
                        safe, msg = engine.assert_belief(agent_context, k, new_val, existing)
                        if not safe:
                            self.last_reject_reason = f"contradiction_detected:{k}"
                            return False
            except (ImportError, Exception):
                pass  # Degrade gracefully — never hard-block on parse error

        return True

    def commit(self, file_path: str, mutation: str) -> None:
        """Call after a mutation is successfully proposed to SCAR."""
        file_path = self._normalize_fp(file_path)  # Step 1: stable key
        h = self._mutation_content_hash(mutation)
        self._track_seen(h)
        self._global_events.append(time.time())
        self._file_budgets[file_path] -= 1
        self._last_mutation_time[file_path] = time.time()
        self._persist()

    def reset_budgets(self) -> None:
        """Optional epoch reset — nudge depleted files back toward 1."""
        for k in list(self._file_budgets.keys()):
            self._file_budgets[k] = max(self._file_budgets[k], 1)
        self._persist()

    def _persist(self) -> None:
        try:
            payload = {
                "ts": time.time(),
                "file_budgets": dict(self._file_budgets),
                "last_mutation_time": self._last_mutation_time,
                "seen_hashes": list(self._seen_hashes),
            }
            _GOVERNOR_STATE.write_text(json.dumps(payload, indent=1))
        except Exception:
            pass

    def _load(self) -> None:
        if not _GOVERNOR_STATE.exists():
            return
        try:
            data = json.loads(_GOVERNOR_STATE.read_text())
            self._file_budgets = defaultdict(
                lambda: self.file_budget,
                data.get("file_budgets", {}),
            )
            self._last_mutation_time = data.get("last_mutation_time", {})
            hashes = data.get("seen_hashes", [])
            self._seen_hashes = deque(hashes, maxlen=_MAX_REPLAY_TRACK)
            self._seen_set = set(self._seen_hashes)
        except Exception:
            pass


if __name__ == "__main__":
    g = MutationGovernor()
    ok = g.allow("System/foo.py", "hello")
    print("allow1", ok, g.last_reject_reason)
    if ok:
        g.commit("System/foo.py", "hello")
    ok2 = g.allow("System/foo.py", "hello")
    print("allow2_replay", ok2, g.last_reject_reason)
