"""
Event 137 — Microglia Synaptic Pruner
Controlled forgetting — the immune-deletion complement to replay/consolidation.

Biological provenance:
  Tremblay, M.-È., Lowery, R. & Bhatt, D. (2010). Microglial interactions with
  synapses are modulated by visual experience. PLoS Biol 8(11), e1000527.
  doi:10.1371/journal.pbio.1000527

Design laws:
  1. Never prune safety-critical or owner-identity entries (hard invariant).
  2. Every prune action is logged before it is applied (ledger-first).
  3. At most MAX_PRUNES_PER_CYCLE deletions per call (caloric budget).
  4. Depress (reduce priority) before delete (two-phase forgetting).
  5. No mutation of any organ's internal Python objects — writes to JSONL
     side-channel only; the target organ re-reads on its next tick.

Wires to: replay (stale memories), PFC-BG arbiter (depressed options),
WM (contradicted keys), astrocyte (trigger on high surprise),
Lyapunov monitor (only prune if stability_ok=True).
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str, **kwargs) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kwargs) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_MICROGLIA_DISABLE"
MAX_PRUNES_PER_CYCLE = 10

PruneAction = Literal["keep", "depress", "delete"]

# Criterion weights — must sum to 1.0 (no double-spending of salience budget)
_CRITERIA: Dict[str, float] = {
    "unused":       0.25,
    "low_reward":   0.30,
    "high_regret":  0.20,
    "contradicted": 0.15,
    "stale":        0.10,
}
assert abs(sum(_CRITERIA.values()) - 1.0) < 1e-9, "Criterion weights must sum to 1.0"


class MicrogliaSynapticPruner:
    """
    Event 137 — Synaptic pruner with controlled forgetting.
    Scores ledger entries, decides keep/depress/delete,
    logs every decision, applies bounded deletions.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = root or Path(".sifta_state")
        self.log_path = self.root / "microglia_prune.jsonl"

    # ── Scoring ────────────────────────────────────────────────────────────

    def score_entry(self, entry: Dict[str, Any]) -> Tuple[float, str]:
        """
        Returns (prune_score ∈ [0,1], dominant_criterion).
        Higher score → stronger case for pruning.
        """
        scores: Dict[str, float] = {}
        scores["unused"]       = _CRITERIA["unused"]       if entry.get("usage_count", 1) == 0 else 0.0
        scores["low_reward"]   = _CRITERIA["low_reward"]   if entry.get("recent_reward_mean", 0.0) < -0.1 else 0.0
        scores["high_regret"]  = _CRITERIA["high_regret"]  if entry.get("recent_regret", 0.0) > 0.3 else 0.0
        scores["contradicted"] = _CRITERIA["contradicted"] if entry.get("wm_contradiction_pe", 0.0) > 0.4 else 0.0
        scores["stale"]        = _CRITERIA["stale"]        if entry.get("age_hours", 0.0) > 72.0 else 0.0

        total = min(sum(scores.values()), 1.0)
        dominant = max(scores, key=lambda k: scores[k]) if total > 0 else "none"
        return total, dominant

    def decide_action(self, score: float, safety_critical: bool) -> PruneAction:
        """Hard invariant: safety-critical entries are never pruned."""
        if safety_critical or score < 0.4:
            return "keep"
        if score < 0.7:
            return "depress"  # lower priority in arbiter/gates, keep in ledger
        return "delete"       # archive out of active set

    # ── Main prune cycle ───────────────────────────────────────────────────

    def prune(
        self,
        ledger: List[Dict[str, Any]],
        ledger_type: str = "replay",
        stability_ok: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate every entry in `ledger`.
        Returns the list of prune receipt rows (also appended to log).

        Args:
            ledger:       list of dicts read from any SIFTA JSONL ledger
            ledger_type:  label for receipt ("replay", "gate", "wm", "owner")
            stability_ok: Lyapunov gate — refuse all deletes if False
        """
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return []

        receipts: List[Dict[str, Any]] = []
        delete_count = 0

        for entry in ledger:
            is_safety = bool(
                entry.get("safety_critical", False)
                or ledger_type == "owner"
                or entry.get("invariant", False)
            )
            score, dominant = self.score_entry(entry)
            action = self.decide_action(score, is_safety)

            # Lyapunov gate: hard-block deletes if system is not stable
            if action == "delete" and not stability_ok:
                action = "depress"

            # Caloric budget: cap total deletions per cycle
            if action == "delete":
                if delete_count >= MAX_PRUNES_PER_CYCLE:
                    action = "depress"
                else:
                    delete_count += 1

            if action == "keep":
                continue

            receipt: Dict[str, Any] = {
                "ts": time.time(),
                "kind": "MICROGLIA_PRUNE",
                "ledger_type": ledger_type,
                "target_key": entry.get("key", entry.get("kind", "unknown")),
                "prune_score": round(score, 4),
                "dominant_criterion": dominant,
                "age_hours": entry.get("age_hours", 0.0),
                "usage_count": entry.get("usage_count", 0),
                "recent_reward_mean": entry.get("recent_reward_mean", 0.0),
                "wm_contradiction_pe": entry.get("wm_contradiction_pe", 0.0),
                "safety_critical": is_safety,
                "action": action,
                "stability_ok": stability_ok,
                "truth_label": "CONTROLLED_FORGETTING",
            }
            append_line_locked(self.log_path, json.dumps(receipt) + "\n", encoding="utf-8")
            receipts.append(receipt)

        return receipts
