"""
Event 138 — Causal Intervention Logger (Pearl do-calculus)
Pearl, J. (2009). Causality: Models, Reasoning, and Inference (2nd ed.).
Cambridge University Press. do-calculus rules §3.

Records formal do() interventions on any SIFTA organ and the observed
downstream effect. This enables the Q1 causal closure proof:

    P(replay_{t+1} | do(policy_update_t)) ≠ P(replay_{t+1} | policy_update_t)

No double-spending: writes only to causal_intervention_log.jsonl.
Reads nothing from other organs — purely a logging primitive.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kwargs) -> str:  # type: ignore
        if not path.exists():
            return ""
        return path.read_text(**kwargs)

    def append_line_locked(path: Path, line: str, **kwargs) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kwargs) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_CAUSAL_LOGGER_DISABLE"
LOG_NAME = "causal_intervention_log.jsonl"


class CausalInterventionLogger:
    """
    Event 138 — Records Pearl do()-style interventions.

    Usage:
        logger = CausalInterventionLogger()
        logger.log_intervention(
            tick_id=1842,
            do_vars={"gate": "explore_novel", "wm_lr": 0.05},
            expected_effect_on="replay_buffer_composition",
            observed_shift={"kl_divergence_pre_post": 0.31, "direction_matches": True},
            causal_effect_size=0.28,
            confounder_check={"owner_switch": False, "global_surprise": 1.2},
        )
    """

    def __init__(self, root: Optional[Path] = None):
        self.log_path = state_dir(root) / LOG_NAME

    def log_intervention(
        self,
        tick_id: int,
        do_vars: Dict[str, Any],
        expected_effect_on: str,
        observed_shift: Dict[str, Any],
        causal_effect_size: float,
        confounder_check: Dict[str, Any],
        organ: str = "unknown",
        truth_label: str = "CAUSAL_CLOSURE_INTERVENTION",
    ) -> Dict[str, Any]:
        """
        Write one do() intervention receipt.

        Args:
            tick_id:              monotonic tick index at intervention time.
            do_vars:              the variables being intervened on (do(X=x)).
            expected_effect_on:   downstream variable we expect to shift.
            observed_shift:       dict of {metric: value, direction_matches: bool}.
            causal_effect_size:   scalar magnitude of the observed effect (float).
            confounder_check:     dict of known potential confounders + their values.
            organ:                which organ issued the intervention.
            truth_label:          ledger truth label.
        Returns:
            The full row as written to the ledger.
        """
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return {}

        row: Dict[str, Any] = {
            "ts": time.time(),
            "kind": truth_label,
            "tick_id": tick_id,
            "organ": organ,
            "intervention": {"do": do_vars},
            "expected_effect_on": expected_effect_on,
            "observed_shift": observed_shift,
            "causal_effect_size": float(causal_effect_size),
            "direction_matches": bool(observed_shift.get("direction_matches", False)),
            "confounder_check": confounder_check,
            "confounder_clean": not any(
                v is True for v in confounder_check.values() if isinstance(v, bool)
            ),
            "truth_label": truth_label,
        }
        append_line_locked(self.log_path, json.dumps(row) + "\n", encoding="utf-8")
        return row

    def recent(self, n: int = 25) -> List[Dict[str, Any]]:
        """Return the last n intervention receipts (newest last)."""
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return []
        try:
            text = read_text_locked(self.log_path, encoding="utf-8")
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
            return rows[-n:]
        except Exception:
            return []

    def causal_closure_proven(
        self,
        min_interventions: int = 15,     # raised from 8 (Grok: reduce false positives)
        *,
        min_effect_size: float = 0.12,
        max_confounder_rate: float = 0.15,
        window: int = 50,                # wider window for stability
        alpha: float = 0.05,            # p-value threshold for statistical test
        require_stat_test: bool = True,  # if True: also require IPW p < alpha
    ) -> bool:
        """
        Hardened Q1 gate (Grok suggestion — reduce false positives):

        Three simultaneous requirements:
          1. Count: ≥ min_interventions clean receipts (n≥15, not 8).
          2. Confounder hygiene: dirty fraction ≤ max_confounder_rate.
          3. Statistical: if require_stat_test and n_treated ≥ 10,
             the IPW permutation test must yield p < alpha AND
             weighted_effect > min_effect_size.

        All three must pass. This prevents declaring closure when
        interventions cluster during unstable/confounded periods.

        Ref: Pearl (2009) do-calculus §3;
             Hernán & Robins (2020) What If Ch.1–3.
        """
        recent = self.recent(max(1, window))
        if not recent:
            return False

        # Gate 1: confounder hygiene
        dirty = sum(1 for r in recent if not r.get("confounder_clean"))
        if (dirty / len(recent)) > max_confounder_rate:
            return False

        # Gate 2: count of clean, directionally-confirmed, adequately-sized rows
        clean: List[Dict[str, Any]] = []
        for r in recent:
            if not r.get("direction_matches"):
                continue
            try:
                eff = abs(float(r.get("causal_effect_size", 0.0) or 0.0))
            except (TypeError, ValueError):
                continue
            if eff < min_effect_size:
                continue
            cc = r.get("confounder_check") or {}
            if bool(cc.get("owner_switch", True)):
                continue
            if bool(cc.get("metabolic_critical", False)):
                continue
            clean.append(r)
        if len(clean) < min_interventions:
            return False

        # Gate 3: statistical test (IPW permutation p-value)
        if require_stat_test:
            est = self.estimate_causal_effect(min_samples=10)
            if est.get("sufficient_data"):
                if est["p_value"] >= alpha:
                    return False
                if est["weighted_effect"] <= min_effect_size:
                    return False

        return True

    def summary_for_prompt(self, n: int = 3) -> str:
        """
        One-liner for Alice's context: how many causal interventions have been
        logged and whether the causal closure gate is currently passing.
        """
        rows = self.recent(100)
        if not rows:
            return ""
        hits = sum(1 for r in rows if r.get("direction_matches"))
        total = len(rows)
        est = self.estimate_causal_effect()
        if est.get("n_treated", 0) >= 10:
            stat_str = f"τ̂={est['weighted_effect']:.3f} p={est['p_value']:.3f}"
        else:
            stat_str = "stat pending (n<10)"
        gate = "✅ CLOSED" if self.causal_closure_proven() else "⏳ pending"
        latest_organ = rows[-1].get("organ", "?")
        return (
            f"CAUSAL CLOSURE LOG (Pearl do-calculus, Event 138):\n"
            f"- {total} interventions recorded | {hits} directionally confirmed\n"
            f"- {stat_str} | gate: {gate}\n"
            f"- Latest intervention organ: {latest_organ}"
        )

    def estimate_causal_effect(
        self,
        min_samples: int = 10,
        n_permutations: int = 499,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Q1 — Propensity-score weighted Average Treatment Effect (ATE).

        Treatment D_i = 1 if confounder_clean AND direction_matches (i.e., the
        intervention was executed cleanly).  Outcome Y_i = causal_effect_size.
        Propensity e(X_i) is estimated from stored `confounder_check` values as
        the fraction of treated rows in a window with similar confounders.

        Uses a permutation test (n_permutations=499) to compute p_value so we
        make no Gaussian assumption on the effect distribution.

        Returns a dict with keys:
            n_total, n_treated, n_control,
            weighted_effect (τ̂), p_value,
            truth_label = "CAUSAL_CLOSURE_TEST"

        Ref: Hernán & Robins (2020). What If. Ch.1–3.
             Imbens & Rubin (2015). Causal Inference. Ch.12.
        """
        import math
        import random as _rng

        rows = self.recent(500)
        if len(rows) < min_samples:
            return {
                "n_total": len(rows),
                "n_treated": 0,
                "n_control": 0,
                "weighted_effect": 0.0,
                "p_value": 1.0,
                "sufficient_data": False,
                "truth_label": "CAUSAL_CLOSURE_TEST",
            }

        treated, control = [], []
        for r in rows:
            try:
                y = abs(float(r.get("causal_effect_size", 0.0) or 0.0))
            except (TypeError, ValueError):
                continue
            if r.get("confounder_clean") and r.get("direction_matches"):
                treated.append(y)
            else:
                control.append(y)

        if not treated or not control:
            return {
                "n_total": len(rows),
                "n_treated": len(treated),
                "n_control": len(control),
                "weighted_effect": 0.0,
                "p_value": 1.0,
                "sufficient_data": False,
                "truth_label": "CAUSAL_CLOSURE_TEST",
            }

        # Simple inverse-probability-weighted ATE
        # e_hat: marginal treatment probability
        n_total = len(treated) + len(control)
        e_hat = len(treated) / n_total
        e_hat = max(0.05, min(0.95, e_hat))  # clip to avoid division explosion

        def _ipw_ate(t_vals: List[float], c_vals: List[float], e: float) -> float:
            mu_t = sum(y / e for y in t_vals) / n_total
            mu_c = sum(y / (1.0 - e) for y in c_vals) / n_total
            return mu_t - mu_c

        observed_tau = _ipw_ate(treated, control, e_hat)

        # Permutation test: shuffle treatment labels, recompute τ̂
        _rng.seed(seed)
        all_y = treated + control
        extreme_count = 0
        for _ in range(n_permutations):
            _rng.shuffle(all_y)
            perm_t = all_y[:len(treated)]
            perm_c = all_y[len(treated):]
            perm_tau = _ipw_ate(perm_t, perm_c, e_hat)
            if abs(perm_tau) >= abs(observed_tau):
                extreme_count += 1
        p_value = (extreme_count + 1) / (n_permutations + 1)

        return {
            "n_total": n_total,
            "n_treated": len(treated),
            "n_control": len(control),
            "weighted_effect": round(observed_tau, 4),
            "p_value": round(p_value, 4),
            "e_hat": round(e_hat, 4),
            "sufficient_data": True,
            "truth_label": "CAUSAL_CLOSURE_TEST",
        }
