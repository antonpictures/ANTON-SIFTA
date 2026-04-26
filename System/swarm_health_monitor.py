#!/usr/bin/env python3
"""
swarm_health_monitor.py — The Single Number
════════════════════════════════════════════════════════════════
Not mythology. Not narrative. Not lineage poetry.

One number: SYSTEM HEALTH SCORE (0-100).

Measures exactly 6 things:
  1. Hardware stability     (homeostasis_engine)
  2. Memory growth          (.sifta_state/ disk footprint)
  3. Economic efficiency    (warren_buffett: yield vs cost)
  4. Mutation containment   (mutation_governor: rejection rate)
  5. Field density          (mycelial_genome: heatwave state)
  6. Death rate             (apoptosis: graveyard pressure)

Warren Buffett reads this. The Cartography Dashboard reads this.
The Architect reads this. One number. No metaphor.

SIFTA Non-Proliferation Public License applies.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_HEALTH_LOG = _STATE_DIR / "health_scores.jsonl"

# Weight allocation — each dimension sums to 100
WEIGHTS = {
    "hardware":   25,   # CPU, memory, disk, IO latency
    "memory":     15,   # .sifta_state disk growth bounded?
    "economic":   20,   # STGM yield vs metabolic cost
    "mutation":   15,   # governor rejection rate healthy?
    "field":      15,   # genome density below heatwave?
    "mortality":  10,   # apoptosis rate not spiking?
}

# Thresholds
STATE_DIR_MAX_MB = 50.0      # .sifta_state should stay under 50MB
DEATH_RATE_ALARM = 5         # >5 deaths in last hour = alarm
MUTATION_REJECT_ALARM = 0.8  # >80% rejection rate = alarm


class HealthScore:
    """
    Computes one number: 0-100.
    No narrative. No lineage. Pure measurement.
    """

    def __init__(self):
        self.dimensions: dict[str, float] = {}
        self.raw: dict[str, dict] = {}

    def compute(self) -> int:
        """Run all 6 measurements. Return integer 0-100."""
        self.dimensions = {
            "hardware":  self._measure_hardware(),
            "memory":    self._measure_memory_growth(),
            "economic":  self._measure_economic(),
            "mutation":  self._measure_mutation(),
            "field":     self._measure_field(),
            "mortality": self._measure_mortality(),
        }

        score = sum(
            self.dimensions[k] * (WEIGHTS[k] / 100.0)
            for k in WEIGHTS
        )

        final = max(0, min(100, int(round(score * 100))))
        self._log(final)
        return final

    # ── 1. Hardware Stability (25%) ──────────────────────────

    def _measure_hardware(self) -> float:
        """Read homeostasis_engine. Returns 0.0-1.0."""
        try:
            from homeostasis_engine import compute_stability_index, measure_body_state
            state = measure_body_state()
            stability = compute_stability_index(state)
            self.raw["hardware"] = state
            return stability
        except Exception:
            return 0.5  # unknown = neutral

    # ── 2. Memory Growth (15%) ───────────────────────────────

    def _measure_memory_growth(self) -> float:
        """
        .sifta_state/ total size vs 50MB ceiling.
        Under 50% = perfect. Over 100% = zero.
        """
        try:
            total_bytes = sum(
                f.stat().st_size
                for f in _STATE_DIR.rglob("*")
                if f.is_file()
            )
            mb = total_bytes / (1024 * 1024)
            self.raw["memory"] = {"state_dir_mb": round(mb, 2), "ceiling_mb": STATE_DIR_MAX_MB}

            ratio = mb / STATE_DIR_MAX_MB
            if ratio < 0.5:
                return 1.0
            elif ratio < 1.0:
                return 1.0 - (ratio - 0.5) * 2.0  # linear 1.0→0.0
            else:
                return 0.0
        except Exception:
            return 0.5

    # ── 3. Economic Efficiency (20%) ─────────────────────────

    def _measure_economic(self) -> float:
        """
        Canonical STGM economy health, translated to 0.0-1.0.
        Wallet money is repair_log.jsonl only; reputation/game ledgers are
        reported as separate non-spendable signals.
        """
        try:
            try:
                from System.stgm_economy import scan_economy
            except ImportError:
                from stgm_economy import scan_economy  # type: ignore

            scan = scan_economy()
            self.raw["economic"] = scan.as_dict()
            return scan.health_score
        except Exception:
            return 0.5

    # ── 4. Mutation Containment (15%) ────────────────────────

    def _measure_mutation(self) -> float:
        """
        Read mutation_governor.json. High rejection rate = unhealthy
        (means the swarm is trying too hard to mutate itself).
        """
        gov_state = _STATE_DIR / "mutation_governor.json"
        try:
            if not gov_state.exists():
                return 0.8  # no governor data = mostly fine

            data = json.loads(gov_state.read_text())
            budgets = data.get("file_budgets", {})
            self.raw["mutation"] = {"file_count": len(budgets)}

            if not budgets:
                return 1.0

            exhausted = sum(1 for b in budgets.values() if b <= 0)
            ratio = exhausted / len(budgets)
            self.raw["mutation"]["exhausted_ratio"] = round(ratio, 2)

            if ratio > MUTATION_REJECT_ALARM:
                return 0.1  # almost everything blocked = bad
            return 1.0 - ratio
        except Exception:
            return 0.5

    # ── 5. Field Density (15%) ───────────────────────────────

    def _measure_field(self) -> float:
        """
        Read mycelial_genome.json. Heatwave active = stressed.
        Density > 80% without heatwave = dangerous.
        """
        genome_state = _STATE_DIR / "mycelial_genome.json"
        try:
            if not genome_state.exists():
                return 0.8  # no genome data = mostly fine

            data = json.loads(genome_state.read_text())
            density = data.get("density", 0.0)
            heatwave = data.get("heatwave_active", False)
            self.raw["field"] = {"density": density, "heatwave": heatwave}

            if heatwave:
                return 0.3  # actively stressed
            if density > 0.8:
                return 0.2  # over threshold, no heatwave = dangerous
            if density > 0.6:
                return 0.7 - (density - 0.6)  # degrading
            return 1.0
        except Exception:
            return 0.5

    # ── 6. Mortality Rate (10%) ──────────────────────────────

    def _measure_mortality(self) -> float:
        """
        Read death_certificates.jsonl. Recent deaths = stressed swarm.
        Zero deaths = perfect. >5/hour = alarm.
        """
        death_log = _STATE_DIR / "apoptosis" / "death_certificates.jsonl"
        try:
            if not death_log.exists():
                return 1.0  # no deaths = healthy

            now = time.time()
            hour_ago = now - 3600
            recent_deaths = 0
            total_deaths = 0

            with open(death_log) as f:
                for line in f:
                    try:
                        cert = json.loads(line)
                        total_deaths += 1
                        if cert.get("timestamp", 0) > hour_ago:
                            recent_deaths += 1
                    except Exception:
                        pass

            self.raw["mortality"] = {
                "total": total_deaths,
                "last_hour": recent_deaths,
            }

            if recent_deaths == 0:
                return 1.0
            if recent_deaths <= 2:
                return 0.7
            if recent_deaths <= DEATH_RATE_ALARM:
                return 0.4
            return 0.1  # mass die-off
        except Exception:
            return 0.5

    # ── Logging ──────────────────────────────────────────────

    def _log(self, score: int):
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "score": score,
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "raw": self.raw,
        }
        try:
            with open(_HEALTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    # ── Human Report ─────────────────────────────────────────

    def report(self, score: int) -> str:
        grade = (
            "🟢 HEALTHY"    if score >= 80 else
            "🟡 NOMINAL"    if score >= 60 else
            "🟠 DEGRADING"  if score >= 40 else
            "🔴 CRITICAL"
        )

        lines = [
            "╔════════════════════════════════════════════════════╗",
            f"║   SWARM HEALTH SCORE:  {score:>3} / 100   {grade:<16} ║",
            "╠════════════════════════════════════════════════════╣",
        ]

        labels = {
            "hardware":  "Hardware Stability",
            "memory":    "Memory Growth",
            "economic":  "Economic Efficiency",
            "mutation":  "Mutation Containment",
            "field":     "Field Density",
            "mortality": "Mortality Rate",
        }

        for key, label in labels.items():
            val = self.dimensions.get(key, 0)
            wt  = WEIGHTS[key]
            pct = int(val * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            lines.append(
                f"║  {label:<22} {bar} {pct:>3}% (×{wt}%) ║"
            )

        lines.append("╚════════════════════════════════════════════════════╝")
        return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(_REPO / "System"))

    print("=" * 54)
    print("  SIFTA — SWARM HEALTH MONITOR")
    print("  One number. No metaphor.")
    print("=" * 54 + "\n")

    monitor = HealthScore()
    score = monitor.compute()
    print(monitor.report(score))

    print(f"\n  Logged to: {_HEALTH_LOG}")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n  POWER TO THE SWARM 🐜⚡")
