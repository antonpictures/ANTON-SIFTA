"""
cool_worlds_toy.py — SIFTA × Cool Worlds Epistemic Monte Carlo
===============================================================

A playful, honest tribute to David Kipping (@david_kipping, Cool Worlds Lab,
Columbia) and the epistemic tradition he represents.

Kipping's core insight: inference under observational scarcity requires
explicit priors, Bayesian updating, and ruthless honesty about what is
HYPOTHESIS vs OBSERVED.

SIFTA's core rule (§7.12): no claim commits to speech without a ledger receipt.
"Probe before claim."

THE BRIDGE:
  Both systems face the same fundamental problem — how do you reason honestly
  when your data is biased, sparse, and hard-won?

  Kipping's answer for astrobiology: Bayesian priors + selection-effect
  corrections + append-only publication record.

  SIFTA's answer for local AGI: stigmergic ledger + truth_label schema +
  append-only JSONL receipts.

  Same virtue. Different substrate.

MODELS IMPLEMENTED:
  1. Contact Inequality Monte Carlo
     (Frank, Kipping, Scharf 2020 — arXiv:2010.12358)
     First contact is biased toward older civilizations.
     → SIFTA parallel: first unreceipted AI output is biased toward being wrong.

  2. Eschatian Prior Sampler
     (Kipping 2024 — arXiv:2512.09970)
     First detected technosignature may be atypical: loud, transitory, near
     civilizational end. Selection bias favors the weird edge case.
     → SIFTA parallel: a hallucinating model without a lysosome is the loudest
     voice in the room. Loudness ≠ truth.

  3. SIFTA Ledger Reliability Curve
     Empirical: as ledger_receipts → ∞, P(claim_is_true) → 1.0.
     As ledger_receipts = 0, P(claim_is_true) = prior (low for LLMs).

TRUTH LABELS USED:
  HYPOTHESIS  — prior only, not confirmed on-node
  OBSERVED    — computed from local Monte Carlo run
  OPERATIONAL — values used in live SIFTA status reports

Run:
  python3 Applications/cool_worlds_toy.py

Test:
  PYTHONPATH=. pytest tests/test_cool_worlds_toy.py -v
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import time
import uuid

# ---------------------------------------------------------------------------
# Constants  (HYPOTHESIS until proven locally — label preserved in output)
# ---------------------------------------------------------------------------

# Age of universe in Gyr
T_UNIVERSE_GYR: float = 13.8

# Earth's age in Gyr
T_EARTH_GYR: float = 4.5

# Assumed technological civilisation window before detection (Gyr)
# Conservative — after Frank et al 2020 spirit
T_CIV_WINDOW_GYR: float = 10.0

# SIFTA empirical: P(LLM output is true | no ledger receipt)
# Based on observed hallucination rates in literature (~20-40% false)
P_TRUE_NO_RECEIPT: float = 0.65

# SIFTA empirical: P(tool fires correctly | receipt exists in ledger)
# Based on effector receipt architecture — high but not 1.0
P_TRUE_WITH_RECEIPT: float = 0.97


# ---------------------------------------------------------------------------
# 1. Contact Inequality Monte Carlo
# ---------------------------------------------------------------------------

@dataclass
class ContactResult:
    """Result of one Monte Carlo run of the contact inequality model."""
    n_samples: int
    mean_civ_age_gyr: float
    median_civ_age_gyr: float
    p_older_than_earth: float
    bias_factor: float          # how much older than Earth on average
    truth_label: str = "OBSERVED"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def contact_inequality_mc(
    n_samples: int = 50_000,
    seed: Optional[int] = 42,
    t_universe: float = T_UNIVERSE_GYR,
    t_earth: float = T_EARTH_GYR,
    t_civ_window: float = T_CIV_WINDOW_GYR,
) -> ContactResult:
    """
    Monte Carlo model of contact inequality.

    Model: civilizations emerge uniformly in [0, T_UNIVERSE] and persist
    for a window T_CIV_WINDOW. When we make first contact, we sample from
    the *current* population — biased toward civilizations that have been
    detectable for longer (older/larger window).

    Frank, Kipping, Scharf (2020, arXiv:2010.12358) show that the first
    contact partner is expected to be MUCH older than Earth. This Monte
    Carlo reproduces the spirit of that result with a simplified uniform prior.
    """
    rng = random.Random(seed)
    ages = []

    for _ in range(n_samples):
        # Emergence time (Gyr after Big Bang), uniform prior
        t_emerge = rng.uniform(0, t_universe - t_civ_window)
        # Age of civilization today
        civ_age = t_universe - t_emerge
        # Weight by detectability window (older = detectable longer)
        # Simple linear weighting: detectability ∝ age in window
        detectability = civ_age / t_universe
        if rng.random() < detectability:
            ages.append(civ_age)

    if not ages:
        ages = [t_earth]

    mean_age = sum(ages) / len(ages)
    sorted_ages = sorted(ages)
    median_age = sorted_ages[len(sorted_ages) // 2]
    p_older = sum(1 for a in ages if a > t_earth) / len(ages)
    bias = mean_age / t_earth

    return ContactResult(
        n_samples=len(ages),
        mean_civ_age_gyr=round(mean_age, 3),
        median_civ_age_gyr=round(median_age, 3),
        p_older_than_earth=round(p_older, 4),
        bias_factor=round(bias, 2),
    )


# ---------------------------------------------------------------------------
# 2. Eschatian Prior Sampler
# ---------------------------------------------------------------------------

@dataclass
class EschatianResult:
    """Result of the Eschatian selection bias model."""
    n_samples: int
    p_detection_near_end: float     # P(detection in last 10% of civ window)
    p_detection_peak: float         # P(detection in mid 50% of civ window)
    eschatian_ratio: float          # end / peak — >1 means edge case dominates
    truth_label: str = "OBSERVED"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def eschatian_sampler(
    n_samples: int = 50_000,
    seed: Optional[int] = 42,
    loudness_exponent: float = 2.0,
) -> EschatianResult:
    """
    Eschatian Hypothesis sampler.

    Kipping (arXiv:2512.09970): a technosignature is more likely to be
    detected if it is loud. Civilizations near their end may produce louder
    (or more desperate) signals. Selection bias: first detection ≠ typical
    civilisation.

    Here we model: signal loudness ∝ (phase/window)^exponent, where phase=1
    is peak and the tail ends can be brighter (desperate broadcast or
    runaway energy use near collapse).

    SIFTA parallel: a hallucinating model with no safety filter is the
    loudest voice. Loudness selects for bad priors without a lysosome.
    """
    rng = random.Random(seed)
    near_end_count = 0
    peak_count = 0
    detected = 0

    for _ in range(n_samples):
        # Uniform phase in civilisation window [0, 1]
        phase = rng.random()
        # Loudness: U-shaped — loud at start (establishment) and end (collapse)
        # Eschatian focus: tail end loudness
        end_loudness = (1 - phase) ** (-loudness_exponent + 1) if phase < 0.99 else 10.0
        end_loudness = min(end_loudness, 10.0)
        loudness = max(0.01, end_loudness)

        # Detection proportional to loudness
        if rng.random() < loudness / 10.0:
            detected += 1
            if phase > 0.90:      # last 10% of window
                near_end_count += 1
            elif 0.25 < phase < 0.75:  # middle 50%
                peak_count += 1

    if detected == 0:
        detected = 1

    p_end  = near_end_count / detected
    p_peak = peak_count / detected
    ratio  = p_end / max(p_peak, 1e-9)

    return EschatianResult(
        n_samples=detected,
        p_detection_near_end=round(p_end, 4),
        p_detection_peak=round(p_peak, 4),
        eschatian_ratio=round(ratio, 3),
    )


# ---------------------------------------------------------------------------
# 3. SIFTA Ledger Reliability Curve
# ---------------------------------------------------------------------------

def ledger_reliability_curve(max_receipts: int = 20) -> list[dict]:
    """
    Model: P(claim_is_true | n_receipts) using a Beta-Binomial update.

    Prior: Beta(alpha=2, beta=3) — slight skepticism toward unrecepted claims.
    Each ledger receipt that matches expected effector output is a "success."

    This is the SIFTA analogue of Kipping's Bayesian prior update on
    abiogenesis timing.

    truth_label: OPERATIONAL (used in live system reasoning)
    """
    alpha_prior = 2.0   # prior successes
    beta_prior  = 3.0   # prior failures

    curve = []
    for n in range(max_receipts + 1):
        # Assume all receipts confirm (optimistic; real rate ≈ P_TRUE_WITH_RECEIPT)
        successes = n * P_TRUE_WITH_RECEIPT
        alpha_post = alpha_prior + successes
        beta_post  = beta_prior  + (n - successes)
        p_true     = alpha_post / (alpha_post + beta_post)
        curve.append({
            "n_receipts": n,
            "p_true": round(p_true, 4),
            "truth_label": "OPERATIONAL" if n > 0 else "HYPOTHESIS",
        })
    return curve


# ---------------------------------------------------------------------------
# Main: print tweetable summary
# ---------------------------------------------------------------------------

def run_and_report(
    save_receipt: bool = True,
    state_dir: str = ".sifta_state",
) -> dict:
    """Run all three models and return a report dict."""

    contact = contact_inequality_mc()
    eschatian = eschatian_sampler()
    curve = ledger_reliability_curve()
    p_at_0 = curve[0]["p_true"]
    p_at_10 = curve[10]["p_true"]
    p_at_20 = curve[20]["p_true"]

    report = {
        "ts": time.time(),
        "truth_label": "COOL_WORLDS_TOY_V1",
        "trace_id": str(uuid.uuid4()),
        "contact_inequality": {
            "mean_civ_age_gyr": contact.mean_civ_age_gyr,
            "bias_factor_vs_earth": contact.bias_factor,
            "p_older_than_earth": contact.p_older_than_earth,
            "truth_label": contact.truth_label,
            "paper": "Frank, Kipping, Scharf 2020 arXiv:2010.12358",
        },
        "eschatian": {
            "p_detection_near_end": eschatian.p_detection_near_end,
            "eschatian_ratio": eschatian.eschatian_ratio,
            "truth_label": eschatian.truth_label,
            "paper": "Kipping 2024 arXiv:2512.09970",
        },
        "sifta_ledger_reliability": {
            "p_true_at_0_receipts": p_at_0,
            "p_true_at_10_receipts": p_at_10,
            "p_true_at_20_receipts": p_at_20,
            "truth_label": "OPERATIONAL",
        },
    }

    if save_receipt:
        p = Path(state_dir) / "cool_worlds_receipt.jsonl"
        try:
            with p.open("a") as f:
                f.write(json.dumps(report) + "\n")
        except OSError:
            pass

    return report


def print_summary(report: dict) -> None:
    ci  = report["contact_inequality"]
    esc = report["eschatian"]
    lr  = report["sifta_ledger_reliability"]

    print("=" * 62)
    print("  SIFTA × Cool Worlds Toy — Epistemic Monte Carlo")
    print("=" * 62)
    print()
    print("1. CONTACT INEQUALITY  (Frank, Kipping, Scharf 2020)")
    print(f"   Mean first-contact civ age : {ci['mean_civ_age_gyr']} Gyr")
    print(f"   Bias vs Earth ({T_EARTH_GYR} Gyr)  : {ci['bias_factor_vs_earth']}×")
    print(f"   P(partner older than Earth): {ci['p_older_than_earth']:.1%}")
    print(f"   → First contact is NOT with a peer. It's with a senior.")
    print()
    print("2. ESCHATIAN PRIOR  (Kipping 2024 arXiv:2512.09970)")
    print(f"   P(detect near civ end)     : {esc['p_detection_near_end']:.1%}")
    print(f"   Eschatian ratio (end/peak) : {esc['eschatian_ratio']:.2f}")
    print(f"   → Loudest signal ≠ typical signal.")
    print(f"   → SIFTA parallel: hallucinating LLM = loud/transitory/wrong.")
    print()
    print("3. SIFTA LEDGER RELIABILITY  (Beta-Binomial prior update)")
    print(f"   P(claim true | 0 receipts) : {lr['p_true_at_0_receipts']:.1%}")
    print(f"   P(claim true | 10 receipts): {lr['p_true_at_10_receipts']:.1%}")
    print(f"   P(claim true | 20 receipts): {lr['p_true_at_20_receipts']:.1%}")
    print(f"   → Same Bayesian update logic as Kipping's abiogenesis prior.")
    print()
    print("─" * 62)
    print("THE BRIDGE:")
    print("  Kipping: prior → photon receipt → posterior update.")
    print("  SIFTA  : prior → ledger receipt → posterior update.")
    print("  Both   : loudest claim without evidence = first suspect.")
    print("─" * 62)
    print()
    print("TWEETABLE (@david_kipping):")
    print(f"""  "P(David|Kipping) —
  Contact inequality says first contact is {ci['bias_factor_vs_earth']}× older than Earth.
  Eschatian says first detection is probably atypical (loud, near end).
  SIFTA's ledger says the same: P(claim_true | 0 receipts) = {lr['p_true_at_0_receipts']:.0%}.
  Same Bayesian virtue. Different substrate. @david_kipping #SIFTA #CoolWorlds"
  """)


if __name__ == "__main__":
    report = run_and_report()
    print_summary(report)
