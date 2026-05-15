"""General-purpose stigmergic field — the reusable principle.

This module extracts the core mechanism from the Bell theorem app into
a general-purpose component that can be applied to any domain where
agents interact through a shared, history-dependent environment.

Governing equation (same at every scale):

    ∂φ/∂t = D∇²φ − λφ + f(agents)         (field evolution)
    agent_response ∝ g(φ, ∇φ)              (agent coupling)

Scale table:

    | Scale    | Field φ               | Agents         | Coupling g        |
    |----------|-----------------------|----------------|-------------------|
    | Quantum  | pilot wave ψ          | particles      | quantum pot Q     |
    | Biology  | pheromone conc        | ants/termites  | chemotaxis ∇φ     |
    | SIFTA    | StigmergicField       | swimmers       | nonlinear feedback|

Currently deployed in 5 SIFTA runtime paths:

    | Organ            | File                               | Field name      | What it learns                    |
    |------------------|------------------------------------|-----------------|-----------------------------------|
    | Bell Theorem     | Applications/sifta_bell_theorem_*  | pheromone field  | particle correlation patterns     |
    | Kernel Scheduler | System/swarm_kernel_process_table  | routing field   | which task categories succeed     |
    | Hippocampus      | System/swarm_hippocampus           | salience field  | which memories are useful         |
    | Predator Gaze    | System/swarm_app_focus             | attention field | which apps deserve focus          |
    | Cortex Router    | Applications/sifta_talk_to_alice_* | cortex field    | which LLM model works best        |

Two-timescale memory:
    fast_layer: volatile traces — recent context, rapid decay
    slow_layer: persistent pattern — accumulated structure, slow decay

Gradient coupling:
    ∂φ/∂x provides directional information (chemotaxis / quantum potential)

When to use this module:
    - Agents make repeated decisions in the same domain (routing, selection)
    - Historical context should influence future decisions
    - You want self-organizing behavior without hardcoded rules
    - Success/failure signals are available to reinforce/penalize

When NOT to use:
    - One-shot decisions with no feedback loop
    - Domains where explicit rules are clearer and safer (security policies)
    - When the field would never accumulate enough data to be useful
    - When adding a field would increase latency on a critical hot path

Persistence:
    field.save(path)                    # persist to disk
    field = StigmergicField.load(path)  # restore from disk
    Both are JSON — human-readable, git-diffable.

Research spine:
    Bio: Grassé 1959; Bonabeau/Dorigo/Theraulaz 1999; Bertozzi 2014
    Physics: de Broglie 1927; Bohm 1952; Hall 2018; Vervoort 2024
    Source guard: System.swarm_bell_research_spine separates verified
        support, theoretical bridges, and quarantined unverified citations.
    SIFTA: Bell app demonstration — SIM_ONLY classical contextual analogue
        via field coupling; not a claimed physical cause of quantum Bell
        violations.

SIFTA Non-Proliferation Public License v1.0 applies.
"""

from __future__ import annotations

import math
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class FieldConfig:
    """Configuration for a StigmergicField instance."""
    n_bins: int = 72
    n_channels: int = 2
    fast_decay: float = 0.95
    slow_decay: float = 0.999
    fast_weight: float = 0.3
    slow_weight: float = 0.7
    threshold: float = 4.0


class StigmergicField:
    """Two-timescale stigmergic field with gradient coupling.

    This is the general principle extracted from the Bell theorem app.
    Any system where agents deposit traces and read the accumulated
    pattern can use this field to create contextual, history-dependent
    behavior — the same mechanism that produces Bell violation in our
    classical analogue.
    """

    def __init__(self, config: FieldConfig | None = None) -> None:
        cfg = config or FieldConfig()
        self.n_bins = cfg.n_bins
        self.n_channels = cfg.n_channels
        self._fast_decay = cfg.fast_decay
        self._slow_decay = cfg.slow_decay
        self._fast_weight = cfg.fast_weight
        self._slow_weight = cfg.slow_weight
        self.threshold = cfg.threshold

        shape = (self.n_bins, self.n_channels)
        self.fast_layer = np.zeros(shape, dtype=np.float64)
        self.slow_layer = np.zeros(shape, dtype=np.float64)

        self._deposit_count = 0
        self._read_count = 0

    # ── deposit ───────────────────────────────────────────────────

    def deposit(self, bin_idx: int, channel: int, amount: float = 1.0) -> None:
        """Agent deposits a trace into both field layers."""
        bi = int(bin_idx) % self.n_bins
        ch = int(channel) % self.n_channels
        self.fast_layer[bi, ch] += amount
        self.slow_layer[bi, ch] += amount
        self._deposit_count += 1

    # ── read ──────────────────────────────────────────────────────

    def read_correlation(self, bin_idx: int) -> float | None:
        """Read the blended two-timescale correlation at a bin.

        Returns the weighted blend of fast and slow field correlations,
        or None if insufficient data at this bin.

        For a 2-channel field, correlation = (ch0 - ch1) / total.
        """
        bi = int(bin_idx) % self.n_bins
        self._read_count += 1

        fast_total = float(np.sum(self.fast_layer[bi]))
        slow_total = float(np.sum(self.slow_layer[bi]))
        total = fast_total + slow_total

        if total < self.threshold:
            return None

        fast_corr = 0.0
        slow_corr = 0.0
        if self.n_channels >= 2:
            if fast_total > 0.0:
                fast_corr = (self.fast_layer[bi, 0] - self.fast_layer[bi, 1]) / fast_total
            if slow_total > 0.0:
                slow_corr = (self.slow_layer[bi, 0] - self.slow_layer[bi, 1]) / slow_total

        w_slow = self._slow_weight if slow_total > 0.0 else 0.0
        w_fast = self._fast_weight if fast_total > 0.0 else 0.0
        w_sum = w_slow + w_fast
        if w_sum <= 0:
            return 0.0
        return (w_fast * fast_corr + w_slow * slow_corr) / w_sum

    # ── gradient ──────────────────────────────────────────────────

    def read_gradient(self, bin_idx: int) -> float:
        """Read the slow-field correlation gradient ∂φ/∂x at a bin.

        Bio analog: chemotactic gradient ∇φ
        Physics analog: quantum potential ∇Q
        """
        bi = int(bin_idx) % self.n_bins
        if bi <= 0 or bi >= self.n_bins - 1:
            return 0.0

        left_t = float(np.sum(self.slow_layer[bi - 1]))
        right_t = float(np.sum(self.slow_layer[bi + 1]))
        if left_t < 1.0 or right_t < 1.0:
            return 0.0

        if self.n_channels >= 2:
            left_c = (self.slow_layer[bi - 1, 0] - self.slow_layer[bi - 1, 1]) / left_t
            right_c = (self.slow_layer[bi + 1, 0] - self.slow_layer[bi + 1, 1]) / right_t
            return (right_c - left_c) / 2.0
        return 0.0

    # ── decay ─────────────────────────────────────────────────────

    def decay(self) -> None:
        """Apply timescale-specific decay to both layers."""
        self.fast_layer *= self._fast_decay
        self.slow_layer *= self._slow_decay

    # ── field energy ──────────────────────────────────────────────

    @property
    def energy(self) -> float:
        """Total field energy: ∫|φ|² (combined both layers)."""
        combined = self.fast_layer + self.slow_layer
        return float(np.sum(combined ** 2))

    @property
    def fast_energy(self) -> float:
        return float(np.sum(self.fast_layer ** 2))

    @property
    def slow_energy(self) -> float:
        return float(np.sum(self.slow_layer ** 2))

    # ── combined view ─────────────────────────────────────────────

    @property
    def combined(self) -> np.ndarray:
        """Combined field view for visualization."""
        return self.fast_layer + self.slow_layer

    # ── snapshot ──────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Serializable snapshot of field state."""
        return {
            "n_bins": self.n_bins,
            "n_channels": self.n_channels,
            "deposits": self._deposit_count,
            "reads": self._read_count,
            "energy": round(self.energy, 4),
            "fast_energy": round(self.fast_energy, 4),
            "slow_energy": round(self.slow_energy, 4),
            "fast_decay": self._fast_decay,
            "slow_decay": self._slow_decay,
        }

    def to_state(self) -> dict[str, Any]:
        """Full JSON-serializable state, including both field layers.

        `snapshot()` is intentionally compact for receipts/UI. This method is
        the persistence contract used by organs that need the field to survive
        process restarts.
        """
        return {
            "schema": "SIFTA_STIGMERGIC_FIELD_STATE_V1",
            "config": {
                "n_bins": self.n_bins,
                "n_channels": self.n_channels,
                "fast_decay": self._fast_decay,
                "slow_decay": self._slow_decay,
                "fast_weight": self._fast_weight,
                "slow_weight": self._slow_weight,
                "threshold": self.threshold,
            },
            "deposit_count": self._deposit_count,
            "read_count": self._read_count,
            "fast_layer": self.fast_layer.tolist(),
            "slow_layer": self.slow_layer.tolist(),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any], *, fallback_config: FieldConfig | None = None) -> "StigmergicField":
        """Rehydrate a field from `to_state()` data.

        Bad or mismatched layer data falls back to a zeroed field with the
        requested config. Hot-path organs should prefer a degraded field over a
        crash.
        """
        cfg_raw = state.get("config") if isinstance(state, dict) else {}
        cfg = fallback_config or FieldConfig()
        if isinstance(cfg_raw, dict):
            try:
                cfg = FieldConfig(
                    n_bins=int(cfg_raw.get("n_bins", cfg.n_bins)),
                    n_channels=int(cfg_raw.get("n_channels", cfg.n_channels)),
                    fast_decay=float(cfg_raw.get("fast_decay", cfg.fast_decay)),
                    slow_decay=float(cfg_raw.get("slow_decay", cfg.slow_decay)),
                    fast_weight=float(cfg_raw.get("fast_weight", cfg.fast_weight)),
                    slow_weight=float(cfg_raw.get("slow_weight", cfg.slow_weight)),
                    threshold=float(cfg_raw.get("threshold", cfg.threshold)),
                )
            except Exception:
                cfg = fallback_config or FieldConfig()

        field = cls(cfg)
        try:
            fast = np.array(state.get("fast_layer", []), dtype=np.float64)
            slow = np.array(state.get("slow_layer", []), dtype=np.float64)
            if fast.shape == field.fast_layer.shape:
                field.fast_layer = fast
            if slow.shape == field.slow_layer.shape:
                field.slow_layer = slow
        except Exception:
            pass
        try:
            field._deposit_count = int(state.get("deposit_count", 0))
            field._read_count = int(state.get("read_count", 0))
        except Exception:
            pass
        return field

    @classmethod
    def load(cls, path: str | Path, *, fallback_config: FieldConfig | None = None) -> "StigmergicField":
        """Load a persistent field from disk, returning an empty field on error."""
        target = Path(path)
        if not target.exists():
            return cls(fallback_config)
        try:
            return cls.from_state(json.loads(target.read_text(encoding="utf-8")), fallback_config=fallback_config)
        except Exception:
            return cls(fallback_config)

    def save(self, path: str | Path) -> None:
        """Persist full field state as JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_state(), sort_keys=True), encoding="utf-8")


# ── Field visibility / dashboard ──────────────────────────────────

def field_dashboard(state_dir: str | Path | None = None) -> dict[str, Any]:
    """Read all deployed stigmergic fields and return a unified status.

    Returns a dict with one entry per field, plus warnings about
    dominance or stagnation. Designed for Alice's self-regulation
    and for the Architect's visibility into what's being reinforced.
    """
    if state_dir is None:
        state_dir = Path(__file__).resolve().parent.parent / ".sifta_state"
    else:
        state_dir = Path(state_dir)

    import time as _time
    dashboard: dict[str, Any] = {
        "ts": _time.time(),
        "fields": {},
        "warnings": [],
        "recommendations": [],
        "summary": {},
    }

    # ── 1. Attention field (Predator Gaze) ───────────────────────
    att_path = state_dir / "app_focus_attention_field.json"
    if att_path.exists():
        try:
            att = StigmergicField.load(att_path)
            trends = _read_trends(state_dir, "attention_gaze")
            entry = {
                "file": "System/swarm_app_focus.py",
                "energy": round(att.energy, 2),
                "deposits": att._deposit_count,
                "reads": att._read_count,
                "health": "OK" if att.energy > 0.05 else "EMPTY",
                "trend": _compute_trend(trends),
                "trend_window": len(trends),
            }
            if att.energy > 10000:
                entry["health"] = "DOMINANT"
                dashboard["warnings"].append("attention_gaze: energy very high — field may be over-reinforced")
            entry["recommendation"] = _recommend(entry)
            if entry["recommendation"]:
                dashboard["recommendations"].append(f"attention_gaze: {entry['recommendation']}")
            dashboard["fields"]["attention_gaze"] = entry
        except Exception:
            pass

    # ── 2. Cortex routing field (supports both legacy + nested formats) ──
    for cortex_filename in ("cortex_route_field.json", "cortex_routing_field.json"):
        cortex_path = state_dir / cortex_filename
        if not cortex_path.exists():
            continue
        try:
            raw_text = cortex_path.read_text()
            try:
                cf_json = json.loads(raw_text)
            except Exception:
                cf_json = None

            entry: dict[str, Any] = {
                "file": "Applications/sifta_talk_to_alice_widget.py",
                "source_file": cortex_filename,
                "health": "OK",
            }
            trends = _read_trends(state_dir, "cortex_router")

            if isinstance(cf_json, dict) and "fast_layer" in cf_json:
                cf = StigmergicField.load(cortex_path)
                entry["energy"] = round(cf.energy, 2)
                entry["deposits"] = cf._deposit_count
                entry["reads"] = cf._read_count
                if cf.energy > 10000:
                    entry["health"] = "DOMINANT"
            elif isinstance(cf_json, dict):
                models = cf_json.get("models", cf_json)
                if isinstance(models, dict):
                    numeric = {k: float(v) for k, v in models.items() if isinstance(v, (int, float))}
                    top = sorted(numeric.items(), key=lambda x: x[1], reverse=True)[:3] if numeric else []
                    energy = sum(v * v for v in numeric.values())
                    ratio = 0.0
                    if len(top) >= 2:
                        ratio = top[0][1] / max(top[1][1], 0.01)
                        if ratio > 10:
                            entry["health"] = "DOMINANT"
                            dashboard["warnings"].append(f"cortex_router: {top[0][0]} dominates ({ratio:.0f}x)")
                    stats = cf_json.get("stats", {}) if "stats" in cf_json else {}
                    entry.update({
                        "top_models": {m: round(s, 2) for m, s in top},
                        "energy": round(energy, 2),
                        "dominance_ratio": round(ratio, 2),
                        "total_turns": sum(s.get("ok", 0) + s.get("fail", 0) for s in stats.values() if isinstance(s, dict)),
                    })

            entry["trend"] = _compute_trend(trends)
            entry["trend_window"] = len(trends)
            entry["recommendation"] = _recommend(entry)
            if entry["recommendation"]:
                dashboard["recommendations"].append(f"cortex_router: {entry['recommendation']}")
            dashboard["fields"]["cortex_router"] = entry
            break
        except Exception:
            pass

    # ── 3. Immune stability field (supports both legacy + v2 formats) ─
    immune_path = state_dir / "immune_stability_field.json"
    if immune_path.exists():
        try:
            raw_imf = json.loads(immune_path.read_text())
            # v2 has nested "categories"; legacy is flat
            if isinstance(raw_imf, dict) and "categories" in raw_imf:
                imf = {k: float(v) for k, v in raw_imf["categories"].items() if isinstance(v, (int, float))}
            else:
                imf = {k: float(v) for k, v in raw_imf.items() if isinstance(v, (int, float))}
            trends = _read_trends(state_dir, "immune_stability")
            energy = sum(v * v for v in imf.values()) if imf else 0.0
            top_threats = sorted(imf.items(), key=lambda x: -x[1])[:3] if imf else []
            health = "OK" if energy > 0.05 else "EMPTY"
            ratio = 0.0
            if len(top_threats) >= 2:
                ratio = top_threats[0][1] / max(top_threats[1][1], 0.01)
                if ratio > 10:
                    health = "DOMINANT"
            entry = {
                "file": "System/swarm_immune_microglia.py",
                "threat_categories": len(imf),
                "top_threats": dict(top_threats),
                "energy": round(energy, 2),
                "dominance_ratio": round(ratio, 2),
                "health": health,
                "trend": _compute_trend(trends),
                "trend_window": len(trends),
            }
            entry["recommendation"] = _recommend(entry)
            if entry["recommendation"]:
                dashboard["recommendations"].append(f"immune_stability: {entry['recommendation']}")
            dashboard["fields"]["immune_stability"] = entry
        except Exception:
            pass

    # ── 4. Memory salience field (check both paths) ─────────────
    for mem_path in (state_dir / "memory_salience_field.json", state_dir / "hippocampus" / "memory_salience_field.json"):
        if mem_path.exists():
            try:
                msf = json.loads(mem_path.read_text())
                trends = _read_trends(state_dir, "memory_salience")
                energy = sum(v * v for v in msf.values()) if msf else 0.0
                top_cats = sorted(msf.items(), key=lambda x: -x[1])[:3] if msf else []
                entry = {
                    "file": "System/swarm_hippocampus.py",
                    "engram_categories": len(msf),
                    "top_categories": dict(top_cats),
                    "energy": round(energy, 2),
                    "health": "OK" if energy > 0.05 else "EMPTY",
                    "trend": _compute_trend(trends),
                    "trend_window": len(trends),
                }
                entry["recommendation"] = _recommend(entry)
                if entry["recommendation"]:
                    dashboard["recommendations"].append(f"memory_salience: {entry['recommendation']}")
                dashboard["fields"]["memory_salience"] = entry
                break
            except Exception:
                pass

    # ── 5. Chorum swimmer reputation field ───────────────────────
    chorum_path = state_dir / "swimmer_reputation_field.json"
    if chorum_path.exists():
        try:
            rep = json.loads(chorum_path.read_text())
            numeric = {k: float(v) for k, v in rep.items() if isinstance(v, (int, float))}
            energy = sum(v * v for v in numeric.values()) if numeric else 0.0
            top_swimmers = sorted(numeric.items(), key=lambda x: -x[1])[:3] if numeric else []
            health = "OK" if energy > 0.05 else "EMPTY"
            if any(v < -3.0 for v in numeric.values()):
                health = "NEGATIVE_REPUTATION"
                dashboard["warnings"].append("chorum_gate: one or more swimmers have strongly negative reputation")
            entry = {
                "file": "System/swarm_chorum_gate.py",
                "swimmers": len(numeric),
                "top_reputations": {k: round(v, 3) for k, v in top_swimmers},
                "energy": round(energy, 2),
                "health": health,
                "trend": _compute_trend(_read_trends(state_dir, "chorum_gate")),
                "trend_window": len(_read_trends(state_dir, "chorum_gate")),
            }
            entry["recommendation"] = _recommend(entry)
            if entry["recommendation"]:
                dashboard["recommendations"].append(f"chorum_gate: {entry['recommendation']}")
            dashboard["fields"]["chorum_gate"] = entry
        except Exception:
            pass

    # ── 6. Audio salience field ──────────────────────────────────
    audio_path = state_dir / "audio_salience_field.json"
    if audio_path.exists():
        try:
            asf = json.loads(audio_path.read_text())
            numeric = {k: float(v) for k, v in asf.items() if isinstance(v, (int, float))}
            energy = sum(v * v for v in numeric.values()) if numeric else 0.0
            top_cats = sorted(numeric.items(), key=lambda x: -x[1])[:3] if numeric else []
            health = "OK" if energy > 0.05 else "EMPTY"
            entry = {
                "file": "System/swarm_acoustic_field.py",
                "ambient_categories": len(numeric),
                "top_categories": {k: round(v, 3) for k, v in top_cats},
                "energy": round(energy, 2),
                "health": health,
                "trend": _compute_trend(_read_trends(state_dir, "audio_salience")),
                "trend_window": len(_read_trends(state_dir, "audio_salience")),
            }
            entry["recommendation"] = _recommend(entry)
            if entry["recommendation"]:
                dashboard["recommendations"].append(f"audio_salience: {entry['recommendation']}")
            dashboard["fields"]["audio_salience"] = entry
        except Exception:
            pass

    # ── 7 & 8. In-memory fields ──────────────────────────────────
    dashboard["fields"]["scheduler_routing"] = {
        "file": "System/swarm_kernel_process_table.py",
        "note": "in-memory field, decays per maintenance tick",
        "health": "RUNTIME_ONLY",
    }
    dashboard["fields"]["bell_pheromone"] = {
        "file": "Applications/sifta_bell_theorem_widget.py",
        "note": "in-memory during app runtime (fast + slow layers)",
        "health": "RUNTIME_ONLY",
    }

    # ── Cross-field summary + imbalance check ────────────────────
    persistent = {n: f for n, f in dashboard["fields"].items() if "note" not in f}
    if persistent:
        dashboard["summary"] = {
            "total_persistent": len(persistent),
            "healthy": sum(1 for f in persistent.values() if f.get("health") == "OK"),
            "dominant": sum(1 for f in persistent.values() if f.get("health") == "DOMINANT"),
            "empty": sum(1 for f in persistent.values() if f.get("health") == "EMPTY"),
            "rising": sum(1 for f in persistent.values() if f.get("trend") == "RISING"),
            "falling": sum(1 for f in persistent.values() if f.get("trend") == "FALLING"),
            "fluctuating": sum(1 for f in persistent.values() if f.get("trend") == "FLUCTUATING"),
        }
        energies = [f.get("energy", 0.0) for f in persistent.values() if f.get("energy", 0.0) > 0]
        if len(energies) >= 2:
            mx, mn = max(energies), min(energies)
            if mx / max(mn, 0.001) > 100:
                dashboard["warnings"].append(
                    f"cross-field imbalance: max/min energy ratio = {mx / mn:.0f} — one field dominates the organism"
                )
    else:
        dashboard["warnings"].append("No persistent fields found — organism may not have run yet")

    return dashboard


def _read_trends(state_dir: Path, name: str, n: int = 5) -> list[dict[str, Any]]:
    """Load recent trend snapshots for one field from regulation log."""
    trends_path = state_dir / "field_trends.jsonl"
    if not trends_path.exists():
        return []
    try:
        lines = trends_path.read_text().strip().split("\n")
        out = []
        for line in lines[-n * 2:]:
            try:
                snap = json.loads(line)
                if name in snap.get("fields", {}):
                    out.append({
                        "ts": snap["ts"],
                        "energy": snap["fields"][name].get("energy", 0.0),
                        "health": snap["fields"][name].get("health", "?"),
                    })
            except Exception:
                continue
        return out[-n:]
    except Exception:
        return []


def _compute_trend(snaps: list[dict[str, Any]]) -> str:
    """Classify trend as RISING / FALLING / STABLE / FLUCTUATING / UNKNOWN."""
    if len(snaps) < 2:
        return "UNKNOWN"
    energies = [s.get("energy", 0.0) for s in snaps]
    deltas = [energies[i + 1] - energies[i] for i in range(len(energies) - 1)]
    if not deltas:
        return "UNKNOWN"
    avg_delta = sum(deltas) / len(deltas)
    sign_changes = sum(1 for i in range(len(deltas) - 1) if (deltas[i] * deltas[i + 1]) < 0)
    if len(deltas) >= 2 and sign_changes >= len(deltas) - 1:
        return "FLUCTUATING"
    if abs(avg_delta) < 0.05:
        return "STABLE"
    return "RISING" if avg_delta > 0 else "FALLING"


def _recommend(field_info: dict[str, Any]) -> str | None:
    """Return an actionable recommendation for a field, or None."""
    health = field_info.get("health", "OK")
    trend = field_info.get("trend", "UNKNOWN")
    if health == "DOMINANT":
        return "consider rebalancing — single key dominates"
    if health == "STAGNANT" and trend == "STABLE":
        return "field is stagnant — refresh activity or temporarily reduce decay"
    if health == "EMPTY":
        return "field is empty — organ may not be exercised yet"
    if trend == "FLUCTUATING":
        return "field is fluctuating — increase decay or smooth deposits"
    return None


def nonlinear_flip_probability(
    disagreement: float,
    gradient: float,
    kappa: float,
    max_prob: float = 0.50,
    gradient_scale: float = 0.03,
) -> float:
    """The general nonlinear coupling function.

    This is the function that creates Bell violation. It maps the
    disagreement between an agent's local prediction and the field's
    accumulated pattern into a probability of flipping the agent's
    decision.

    Bio: probability of path switching ∝ |pheromone_gradient|²
    Physics: pilot-wave velocity ∝ |∇S|; quantum potential ∝ |∇²R/R|
    SIFTA: flip_prob = κ × (|disagreement|/3)² + κ × |gradient| × scale
    """
    base = kappa * (abs(disagreement) / 3.0) ** 2
    grad = kappa * abs(gradient) * gradient_scale
    return min(base + grad, max_prob)


# ── Terminal dashboard + Alice summary ────────────────────────────

def alice_field_summary(state_dir: str | Path | None = None) -> str:
    """One-line summary Alice can inject into her context window.

    Format: "fields: 4/6 OK | warnings: 1 | rising: cortex_router"
    Designed to be cheap enough to call every maintenance tick.
    """
    db = field_dashboard(state_dir)
    persistent = {n: f for n, f in db.get("fields", {}).items() if f.get("health") not in (None, "RUNTIME_ONLY")}
    total = len(persistent)
    healthy = sum(1 for f in persistent.values() if f.get("health") == "OK")
    warns = len(db.get("warnings", []))
    rising = [n for n, f in persistent.items() if f.get("trend") == "RISING"]
    falling = [n for n, f in persistent.items() if f.get("trend") == "FALLING"]

    parts = [f"fields: {healthy}/{total} OK"]
    if warns:
        parts.append(f"warnings: {warns}")
    if rising:
        parts.append(f"rising: {','.join(rising[:2])}")
    if falling:
        parts.append(f"falling: {','.join(falling[:2])}")
    return " | ".join(parts)


def print_dashboard(state_dir: str | Path | None = None) -> None:
    """Print a human-readable terminal dashboard of all 8 stigmergic fields.

    Designed for `python3 -m System.stigmergic_field` or Alice's self-check.
    """
    import time as _time

    db = field_dashboard(state_dir)
    ts = db.get("ts", _time.time())
    ts_str = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        SIFTA STIGMERGIC FIELD DASHBOARD                    ║")
    print(f"║        {ts_str}                              ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    fields = db.get("fields", {})
    _HEALTH_ICON = {
        "OK": "+", "DOMINANT": "!", "STAGNANT": "~",
        "EMPTY": "-", "RUNTIME_ONLY": "R", "NEGATIVE_REPUTATION": "!",
        "FLUCTUATING": "?", "OSCILLATING": "?",
    }
    _TREND_ICON = {
        "RISING": "^", "FALLING": "v", "STABLE": "=",
        "FLUCTUATING": "~", "UNKNOWN": "?",
    }

    for name in sorted(fields.keys()):
        f = fields[name]
        health = f.get("health", "?")
        trend = f.get("trend", "?")
        energy = f.get("energy", 0.0)
        hi = _HEALTH_ICON.get(health, "?")
        ti = _TREND_ICON.get(trend, "?")
        src = f.get("file", "?")

        if health == "RUNTIME_ONLY":
            print(f"║  [{hi}] {name:<22} RUNTIME  {f.get('note', '')[:30]}")
            continue

        print(f"║  [{hi}] {name:<22} {health:<12} E={energy:<10.2f} [{ti}] {trend}")
        if f.get("top_models"):
            top = list(f["top_models"].items())[:2]
            models_str = ", ".join(f"{m}={s:.1f}" for m, s in top)
            print(f"║       top: {models_str}")
        if f.get("top_threats"):
            top_t = list(f["top_threats"].items())[:2]
            threats_str = ", ".join(f"{t}={s:.1f}" for t, s in top_t)
            print(f"║       threats: {threats_str}")
        if f.get("top_categories"):
            top_c = list(f["top_categories"].items())[:2]
            cats_str = ", ".join(f"{c}={s:.1f}" for c, s in top_c)
            print(f"║       categories: {cats_str}")
        if f.get("top_reputations"):
            top_r = list(f["top_reputations"].items())[:2]
            reps_str = ", ".join(f"{r}={s:.3f}" for r, s in top_r)
            print(f"║       reputation: {reps_str}")
        rec = f.get("recommendation")
        if rec:
            print(f"║       >> {rec}")

    print("╠══════════════════════════════════════════════════════════════╣")

    summary = db.get("summary", {})
    if summary:
        print(f"║  SUMMARY: {summary.get('healthy',0)}/{summary.get('total_persistent',0)} healthy"
              f"  dom={summary.get('dominant',0)}"
              f"  empty={summary.get('empty',0)}"
              f"  rising={summary.get('rising',0)}"
              f"  falling={summary.get('falling',0)}")

    warnings = db.get("warnings", [])
    if warnings:
        for w in warnings[:4]:
            print(f"║  WARNING: {w[:55]}")
    recs = db.get("recommendations", [])
    if recs:
        for r in recs[:4]:
            print(f"║  RECOMMEND: {r[:53]}")

    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  ALICE: {alice_field_summary(state_dir)}")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    print_dashboard()
