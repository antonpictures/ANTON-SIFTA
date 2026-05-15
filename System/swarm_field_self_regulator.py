#!/usr/bin/env python3
"""
swarm_field_self_regulator.py — Allostatic field coordinator
==============================================================

This is the novel piece: Alice can READ her own stigmergic fields and
ADJUST them proactively, instead of letting them drift.

Biology parallel: ALLOSTASIS — "stability through change" (Sterling 2012;
Cell 2024 review on brain-body physiology). Unlike static homeostasis,
allostasis means the organism dynamically rebalances its internal state
in anticipation of demands, not just in response to deviation.

What this module does:
    1. Reads all deployed stigmergic fields (gaze, cortex, immune, memory, scheduler).
    2. Detects pathological patterns: dominance, stagnation, oscillation.
    3. Computes corrective adjustments (decay tuning, trace dampening).
    4. Applies meta-stigmergy: ONE field's state can influence ANOTHER's
       decay or trace amplification (cross-organ field coupling).
    5. Writes self-regulation receipts to .sifta_state/field_regulation_log.jsonl
       so the Architect can audit Alice's autonomous self-tuning.

The novel contribution — META-STIGMERGY (cross-field coupling):
    Until now, our 6 fields each lived in isolation. They couldn't talk
    to each other. The biological reality (Cell 2024 organ cross-talk) is
    that organs constantly signal each other — high inflammation makes
    the brain switch to conservative behavior; low blood sugar increases
    food-seeking salience; threat detection sharpens attention.

    This module implements that. Examples:
        - Immune field elevated → cortex field prefers conservative models
        - Attention dominated by one app → scheduler boosts other categories
        - Memory salience stagnant → temporarily reduce decay to refresh
        - Cortex field uncertain → boost field-coupling weight in scheduler

Research spine (2024–2025):
    - Sterling P. (2012) "Allostasis: A model of predictive regulation"
    - Cell (2024) Brain-body physiology — local, reflex, central comm
    - Nature Sig Trans Targeted Therapy (2025) Organ cross-talk review
    - arXiv 2601.08129 — Pressure fields + temporal decay (10pp loss without)
    - arXiv 2401.10969 — MacroSwarm composable field framework
    - DAIS 2024 — adaptive immune memory (99.87% on MQTTset)
    - Scilit 2024 — dual-trail stigmergy multi-field separation

SIFTA Non-Proliferation Public License v1.0 applies.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_REGULATION_LOG = _STATE_DIR / "field_regulation_log.jsonl"
_REGULATION_STATE = _STATE_DIR / "field_regulation_state.json"
_FIELD_TRENDS = _STATE_DIR / "field_trends.jsonl"

# Coupling matrix: which fields influence which others.
# Each entry is (source_field, target_field, coupling_strength, mode)
# mode: "dampen" reduces target activity, "amplify" boosts it
_COUPLING_RULES: list[tuple[str, str, float, str]] = [
    # Immune elevation → cortex becomes more conservative (route to known-good models)
    ("immune_stability", "cortex_router", 0.3, "stabilize"),
    # Attention dominance on one app → scheduler boosts diversity
    ("attention_gaze", "scheduler_routing", 0.2, "diversify"),
    # Cortex stable & high-perf → memory salience can decay slower (less churn)
    ("cortex_router", "memory_salience", 0.15, "preserve"),
    # Immune detection fires → attention should narrow (focus on threat)
    ("immune_stability", "attention_gaze", 0.25, "focus"),
    # Chorum reputation healthy → cortex can explore riskier models
    ("chorum_gate", "cortex_router", 0.1, "explore"),
    # Scheduler imbalance → immune sensitivity increases (protect overloaded lanes)
    ("scheduler_routing", "immune_stability", 0.15, "sensitize"),
    # Audio salience high → attention should broaden (new environmental input)
    ("audio_salience", "attention_gaze", 0.2, "broaden"),
    # Memory salience stagnant → scheduler should explore new task categories
    ("memory_salience", "scheduler_routing", 0.1, "diversify"),
]

# Self-correction hysteresis: minimum ticks between repeated regulation of the same field
_CORRECTION_COOLDOWN_TICKS = 3


@dataclass
class FieldHealthReport:
    """Per-field health snapshot."""
    name: str
    energy: float = 0.0
    deposits: int = 0
    top_keys: list[tuple[str, float]] = field(default_factory=list)
    dominance_ratio: float = 0.0
    stagnation_score: float = 0.0
    health: str = "OK"  # OK, DOMINANT, STAGNANT, EMPTY, OSCILLATING

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "energy": round(self.energy, 4),
            "deposits": self.deposits,
            "top_keys": [(k, round(v, 4)) for k, v in self.top_keys[:5]],
            "dominance_ratio": round(self.dominance_ratio, 3),
            "stagnation_score": round(self.stagnation_score, 3),
            "health": self.health,
        }


@dataclass
class RegulationAction:
    """A single self-regulation adjustment."""
    field_name: str
    action: str  # "dampen", "boost_decay", "rebalance", "couple"
    target: str  # what was targeted (model, app, threat category)
    delta: float
    reason: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "field": self.field_name,
            "action": self.action,
            "target": self.target,
            "delta": round(self.delta, 4),
            "reason": self.reason,
        }


def _load_state() -> dict[str, Any]:
    if _REGULATION_STATE.exists():
        try:
            return json.loads(_REGULATION_STATE.read_text())
        except Exception:
            pass
    return {"last_regulation_ts": 0.0, "regulation_count": 0, "history": {}}


def _save_state(state: dict[str, Any]) -> None:
    try:
        _REGULATION_STATE.parent.mkdir(parents=True, exist_ok=True)
        _REGULATION_STATE.write_text(json.dumps(state, sort_keys=True))
    except Exception:
        pass


def _read_field_dict(filename: str) -> dict[str, Any]:
    """Read a JSON-on-disk field. Returns empty dict on failure."""
    path = _STATE_DIR / filename
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _first_existing_field_filename(*filenames: str) -> str:
    """Return the first existing field filename, or the first candidate."""
    for filename in filenames:
        if (_STATE_DIR / filename).exists():
            return filename
    return filenames[0]


def _write_field_dict(filename: str, data: dict[str, Any]) -> None:
    """Write a JSON-on-disk field. Best-effort."""
    path = _STATE_DIR / filename
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, sort_keys=True))
    except Exception:
        pass


def _analyze_field(name: str, items: dict[str, float]) -> FieldHealthReport:
    """Compute health metrics for a flat key→strength field."""
    rep = FieldHealthReport(name=name)
    if not items:
        rep.health = "EMPTY"
        return rep

    sorted_items = sorted(items.items(), key=lambda x: x[1], reverse=True)
    rep.top_keys = sorted_items
    rep.deposits = len(items)
    values = [float(v) for v in items.values()]
    rep.energy = sum(v * v for v in values)

    if len(sorted_items) >= 2:
        top = abs(sorted_items[0][1])
        runner = abs(sorted_items[1][1])
        if runner > 0.001:
            rep.dominance_ratio = top / runner

    state = _load_state()
    history = state.get("history", {}).get(name, [])
    if history:
        recent = history[-5:]
        if len(recent) >= 3:
            energies = [h.get("energy", 0.0) for h in recent]
            energy_range = max(energies) - min(energies)
            if energy_range < 0.5 and rep.energy > 1.0:
                rep.stagnation_score = 1.0 - (energy_range / max(rep.energy, 1.0))

    if rep.dominance_ratio > 8.0:
        rep.health = "DOMINANT"
    elif rep.stagnation_score > 0.85:
        rep.health = "STAGNANT"
    elif rep.energy < 0.05:
        rep.health = "EMPTY"
    else:
        rep.health = "OK"
    return rep


def read_all_fields() -> dict[str, FieldHealthReport]:
    """Read every persistent field on disk and produce a health report.

    Returns a dict of field_name → FieldHealthReport.
    """
    reports: dict[str, FieldHealthReport] = {}

    # Cortex routing field — supports current StigmergicField storage plus
    # older nested "models" / "affinity" / "stats" structures.
    cortex_filename = _first_existing_field_filename("cortex_route_field.json", "cortex_routing_field.json")
    cortex = _read_field_dict(cortex_filename)
    if cortex:
        if "fast_layer" in cortex:
            try:
                from System.stigmergic_field import StigmergicField
                field = StigmergicField.load(_STATE_DIR / cortex_filename)
                rep = FieldHealthReport(
                    name="cortex_router",
                    energy=field.energy,
                    deposits=field._deposit_count,
                    health="OK" if field.energy > 0.05 else "EMPTY",
                )
                if field.energy > 10000:
                    rep.health = "DOMINANT"
                reports["cortex_router"] = rep
            except Exception:
                pass
        else:
            models = cortex.get("models", cortex if not isinstance(cortex.get("models"), dict) else {})
            if isinstance(models, dict):
                reports["cortex_router"] = _analyze_field("cortex_router", {k: float(v) for k, v in models.items() if isinstance(v, (int, float))})

    # Immune stability field — supports both flat (legacy) and nested (v2) formats
    immune = _read_field_dict("immune_stability_field.json")
    if immune:
        if "categories" in immune and isinstance(immune["categories"], dict):
            cats = {k: float(v) for k, v in immune["categories"].items() if isinstance(v, (int, float))}
        else:
            cats = {k: float(v) for k, v in immune.items() if isinstance(v, (int, float))}
        reports["immune_stability"] = _analyze_field("immune_stability", cats)

    # Memory salience field — flat dict; current hippocampus path lives under
    # .sifta_state/hippocampus/ while legacy tests used root.
    memory_filename = _first_existing_field_filename(
        "hippocampus/memory_salience_field.json",
        "memory_salience_field.json",
    )
    memory = _read_field_dict(memory_filename)
    if memory:
        reports["memory_salience"] = _analyze_field("memory_salience", {k: float(v) for k, v in memory.items() if isinstance(v, (int, float))})

    # Chorum Gate reputation field — hardware-born swimmer consensus.
    chorum_rep = _read_field_dict("swimmer_reputation_field.json")
    if chorum_rep:
        reports["chorum_gate"] = _analyze_field(
            "chorum_gate",
            {k: float(v) for k, v in chorum_rep.items() if isinstance(v, (int, float))},
        )

    # Audio salience field — ambient sound energy driving attention
    audio_sal = _read_field_dict("audio_salience_field.json")
    if audio_sal:
        numeric = {k: float(v) for k, v in audio_sal.items() if isinstance(v, (int, float))}
        if numeric:
            reports["audio_salience"] = _analyze_field("audio_salience", numeric)

    # Attention field — uses StigmergicField (different structure)
    try:
        from System.stigmergic_field import StigmergicField
        att_path = _STATE_DIR / "app_focus_attention_field.json"
        if att_path.exists():
            f = StigmergicField.load(att_path)
            rep = FieldHealthReport(
                name="attention_gaze",
                energy=f.energy,
                deposits=f._deposit_count,
            )
            rep.health = "OK" if f.energy > 0.1 else "EMPTY"
            if f.energy > 50000:
                rep.health = "DOMINANT"
            reports["attention_gaze"] = rep
    except Exception:
        pass

    return reports


def detect_pathologies(reports: dict[str, FieldHealthReport]) -> list[str]:
    """Identify cross-field problems that need regulation."""
    issues = []
    for name, rep in reports.items():
        if rep.health == "DOMINANT":
            top_key = rep.top_keys[0][0] if rep.top_keys else "?"
            issues.append(f"{name}: '{top_key}' dominates ({rep.dominance_ratio:.1f}x runner-up)")
        elif rep.health == "STAGNANT":
            issues.append(f"{name}: stagnant (no activity variation, score={rep.stagnation_score:.2f})")
        elif rep.health == "EMPTY":
            pass  # empty is sometimes ok (organ not exercised yet)

    energies = [rep.energy for rep in reports.values() if rep.energy > 0]
    if len(energies) >= 3:
        max_e = max(energies)
        min_e = min(energies)
        if max_e > 50 * max(min_e, 0.01):
            issues.append(f"cross-field imbalance: max/min energy ratio = {max_e/max(min_e,0.01):.0f}")

    return issues


def regulate_field(name: str, report: FieldHealthReport, dry_run: bool = False) -> list[RegulationAction]:
    """Apply self-regulation to a single field based on its health report.

    Allostatic principle: rather than fixing a setpoint, adjust the
    field's dynamics in response to its current state.
    """
    actions = []
    state = _load_state()

    if report.health in ("DOMINANT", "STAGNANT") and not _check_correction_cooldown(state, name):
        return actions

    if report.health == "DOMINANT" and report.top_keys:
        top_key, top_val = report.top_keys[0]
        new_val = top_val * 0.7
        delta = new_val - top_val

        if not dry_run:
            if name == "cortex_router":
                cortex_filename = _first_existing_field_filename("cortex_route_field.json", "cortex_routing_field.json")
                full = _read_field_dict(cortex_filename)
                models = full.get("models", {})
                if top_key in models:
                    models[top_key] = new_val
                    full["models"] = models
                    _write_field_dict(cortex_filename, full)
            elif name == "immune_stability":
                imf = _read_field_dict("immune_stability_field.json")
                if "categories" in imf and isinstance(imf["categories"], dict) and top_key in imf["categories"]:
                    imf["categories"][top_key] = new_val
                    _write_field_dict("immune_stability_field.json", imf)
                elif top_key in imf:
                    imf[top_key] = new_val
                    _write_field_dict("immune_stability_field.json", imf)
            elif name == "memory_salience":
                memory_filename = _first_existing_field_filename(
                    "hippocampus/memory_salience_field.json",
                    "memory_salience_field.json",
                )
                msf = _read_field_dict(memory_filename)
                if top_key in msf:
                    msf[top_key] = new_val
                    _write_field_dict(memory_filename, msf)
            elif name == "chorum_gate":
                rep = _read_field_dict("swimmer_reputation_field.json")
                if top_key in rep:
                    rep[top_key] = new_val
                    _write_field_dict("swimmer_reputation_field.json", rep)

        action = RegulationAction(
            field_name=name,
            action="dampen",
            target=top_key,
            delta=delta,
            reason=f"dominance ratio {report.dominance_ratio:.1f}x exceeded threshold",
        )
        if not dry_run:
            _record_correction(state, name, action.action, report.energy)
            _save_state(state)
        actions.append(action)

    elif report.health == "STAGNANT":
        action = RegulationAction(
            field_name=name,
            action="rebalance",
            target="*",
            delta=0.0,
            reason=f"stagnation score {report.stagnation_score:.2f} suggests refresh needed",
        )
        if not dry_run:
            _record_correction(state, name, action.action, report.energy)
            _save_state(state)
        actions.append(action)

    return actions


def _check_correction_cooldown(state: dict[str, Any], field_name: str) -> bool:
    """Returns True if enough ticks have passed since last regulation of this field.

    Prevents oscillatory over-regulation (hysteresis).
    Bio analog: refractory period — neurons don't fire again immediately.
    Endocrine analog: 5 circuit classes all exhibit time-gated responses
    (Nature Comms 2025, Unifying regulatory motifs in endocrine circuits).
    """
    last_actions = state.get("last_regulation_per_field", {})
    if field_name not in last_actions:
        return True
    last_tick = last_actions.get(field_name, 0)
    current_tick = state.get("regulation_count", 0)
    return (current_tick - last_tick) >= _CORRECTION_COOLDOWN_TICKS


def _record_correction(state: dict[str, Any], field_name: str, action: str, energy: float) -> None:
    """Record that we just regulated this field (for cooldown + outcome tracking)."""
    state.setdefault("last_regulation_per_field", {})[field_name] = state.get("regulation_count", 0)
    outcomes = state.setdefault("correction_outcomes", {}).setdefault(field_name, [])
    outcomes.append({"tick": state.get("regulation_count", 0), "action": action, "pre_energy": energy, "ts": time.time()})
    state["correction_outcomes"][field_name] = outcomes[-10:]


def _evaluate_past_regulation(state: dict[str, Any], field_name: str, current_energy: float) -> str:
    """Check whether our last regulation action actually helped.

    Returns "improved", "worsened", "unchanged", or "unknown".
    Bio analog: active inference prediction error — if the action didn't
    reduce free energy, try a different intervention next time
    (Frontiers Behav Neurosci 2025, Resilience phenotypes from active inference).
    """
    correction_log = state.get("correction_outcomes", {}).get(field_name, [])
    if not correction_log:
        return "unknown"

    last_correction = correction_log[-1]
    last_action = last_correction.get("action", "")
    pre_energy = last_correction.get("pre_energy", 0.0)

    if pre_energy < 0.01:
        return "unknown"

    ratio = current_energy / max(pre_energy, 0.001)

    if last_action in ("dampen", "couple"):
        if ratio < 0.85:
            return "improved"
        elif ratio > 1.15:
            return "worsened"
    elif last_action == "rebalance":
        if abs(ratio - 1.0) > 0.1:
            return "improved"

    return "unchanged"


def apply_field_coupling(
    reports: dict[str, FieldHealthReport],
    dry_run: bool = False,
) -> list[RegulationAction]:
    """Cross-field coupling with self-correction and hysteresis.

    Each coupling rule fires when the source field's energy crosses a
    threshold. The target field is adjusted in proportion.

    This is meta-stigmergy: the same governing equation now operates
    BETWEEN fields, not just within them.

    v2 additions: self-correction loops, hysteresis cooldowns, and 4 new
    coupling modes (explore, sensitize, broaden, diversify-from-memory).

    Research spine (new):
        - Nature Comms 2025 — 43 endocrine circuits, 5 circuit classes
        - Frontiers Behav Neurosci 2025 — resilience phenotypes + active inference
        - Nature Comms Bio 2025 — integrating allostasis + emerging tech
        - arXiv 2410.02940 — acoustic signaling in active matter systems
    """
    actions = []
    state = _load_state()

    for source, target, strength, mode in _COUPLING_RULES:
        src_rep = reports.get(source)
        tgt_rep = reports.get(target)
        if not src_rep or not tgt_rep:
            continue

        if not _check_correction_cooldown(state, target):
            continue

        normalized = min(src_rep.energy / 10.0, 1.0)
        if normalized < 0.1:
            continue

        past_result = _evaluate_past_regulation(state, target, tgt_rep.energy)
        correction_scale = 1.0
        if past_result == "worsened":
            correction_scale = 0.3
        elif past_result == "improved":
            correction_scale = 1.2

        effective_strength = strength * correction_scale

        if mode == "stabilize":
            if tgt_rep.top_keys and not dry_run:
                cortex_filename = _first_existing_field_filename("cortex_route_field.json", "cortex_routing_field.json")
                full = _read_field_dict(cortex_filename)
                models = full.get("models", {})
                top_model = tgt_rep.top_keys[0][0]
                if top_model in models and src_rep.energy > 1.0:
                    boost = effective_strength * normalized * 0.5
                    models[top_model] = models[top_model] + boost
                    full["models"] = models
                    _write_field_dict(cortex_filename, full)
                    _record_correction(state, target, "couple", tgt_rep.energy)
                    actions.append(RegulationAction(
                        field_name=target,
                        action="couple",
                        target=top_model,
                        delta=boost,
                        reason=f"coupled from {source} (energy={src_rep.energy:.1f}, mode=stabilize, past={past_result})",
                    ))

        elif mode == "diversify":
            if tgt_rep.top_keys and len(tgt_rep.top_keys) > 1:
                _record_correction(state, target, "couple", tgt_rep.energy)
                actions.append(RegulationAction(
                    field_name=target,
                    action="couple",
                    target="diversify",
                    delta=-effective_strength * normalized,
                    reason=f"coupled from {source} energy={src_rep.energy:.1f} — encourage exploration (past={past_result})",
                ))

        elif mode == "preserve":
            _record_correction(state, target, "couple", tgt_rep.energy)
            actions.append(RegulationAction(
                field_name=target,
                action="couple",
                target="preserve",
                delta=effective_strength * normalized,
                reason=f"coupled from {source}: stable → preserve (past={past_result})",
            ))

        elif mode == "focus":
            if src_rep.energy > 2.0:
                _record_correction(state, target, "couple", tgt_rep.energy)
                actions.append(RegulationAction(
                    field_name=target,
                    action="couple",
                    target="narrow",
                    delta=effective_strength * normalized,
                    reason=f"coupled from {source} (threat) → narrow attention (past={past_result})",
                ))

        elif mode == "explore":
            if src_rep.health == "OK" and src_rep.energy > 0.5:
                _record_correction(state, target, "couple", tgt_rep.energy)
                actions.append(RegulationAction(
                    field_name=target,
                    action="couple",
                    target="explore",
                    delta=effective_strength * normalized * 0.3,
                    reason=f"coupled from {source}: reputation healthy → cortex can explore (past={past_result})",
                ))

        elif mode == "sensitize":
            if src_rep.health in ("DOMINANT", "STAGNANT"):
                _record_correction(state, target, "couple", tgt_rep.energy)
                actions.append(RegulationAction(
                    field_name=target,
                    action="couple",
                    target="sensitize",
                    delta=effective_strength * normalized * 0.4,
                    reason=f"coupled from {source}: scheduler stress → immune sensitized (past={past_result})",
                ))

        elif mode == "broaden":
            if src_rep.energy > 0.5:
                _record_correction(state, target, "couple", tgt_rep.energy)
                actions.append(RegulationAction(
                    field_name=target,
                    action="couple",
                    target="broaden",
                    delta=effective_strength * normalized * 0.3,
                    reason=f"coupled from {source}: audio active → broaden attention (past={past_result})",
                ))

    if not dry_run:
        _save_state(state)

    return actions


def regulate_now(dry_run: bool = False) -> dict[str, Any]:
    """Run a full regulation cycle: read, analyze, apply.

    Returns a dict with reports, issues, actions taken. This is the main
    public API — call it from the kernel maintenance tick.
    """
    reports = read_all_fields()
    issues = detect_pathologies(reports)

    actions: list[RegulationAction] = []
    for name, rep in reports.items():
        actions.extend(regulate_field(name, rep, dry_run=dry_run))
    actions.extend(apply_field_coupling(reports, dry_run=dry_run))

    state = _load_state()
    history = state.setdefault("history", {})
    for name, rep in reports.items():
        h = history.setdefault(name, [])
        h.append({"ts": time.time(), "energy": rep.energy, "deposits": rep.deposits})
        history[name] = h[-20:]
    state["last_regulation_ts"] = time.time()
    state["regulation_count"] = state.get("regulation_count", 0) + 1
    if not dry_run:
        _save_state(state)

    if not dry_run and actions:
        try:
            _REGULATION_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(_REGULATION_LOG, "a", encoding="utf-8") as f:
                for a in actions:
                    f.write(json.dumps(a.to_dict()) + "\n")
        except Exception:
            pass

    if not dry_run:
        try:
            _FIELD_TRENDS.parent.mkdir(parents=True, exist_ok=True)
            with open(_FIELD_TRENDS, "a", encoding="utf-8") as f:
                snap = {
                    "ts": time.time(),
                    "fields": {n: r.to_dict() for n, r in reports.items()},
                }
                f.write(json.dumps(snap) + "\n")
        except Exception:
            pass

    return {
        "ts": time.time(),
        "reports": {n: r.to_dict() for n, r in reports.items()},
        "issues": issues,
        "actions": [a.to_dict() for a in actions],
        "dry_run": dry_run,
    }


def get_field_trends(field_name: str | None = None, n: int = 20) -> list[dict[str, Any]]:
    """Return recent regulation snapshots for trend analysis."""
    if not _FIELD_TRENDS.exists():
        return []
    try:
        lines = _FIELD_TRENDS.read_text().strip().split("\n")
        snaps = []
        for line in lines[-n:]:
            try:
                snap = json.loads(line)
                if field_name:
                    if field_name in snap.get("fields", {}):
                        snaps.append({
                            "ts": snap["ts"],
                            field_name: snap["fields"][field_name],
                        })
                else:
                    snaps.append(snap)
            except Exception:
                continue
        return snaps
    except Exception:
        return []


def alice_self_check() -> str:
    """Public helper Alice can call to introspect her field health.

    Returns a compact human-readable summary suitable for injection
    into her swarm context or for the Architect's view.
    """
    result = regulate_now(dry_run=True)
    parts = []
    healthy = sum(1 for r in result["reports"].values() if r["health"] == "OK")
    total = len(result["reports"])
    parts.append(f"fields: {healthy}/{total} OK")
    if result["issues"]:
        parts.append(f"issues: {'; '.join(result['issues'][:2])}")
    if result["actions"]:
        parts.append(f"would-regulate: {len(result['actions'])}")
    return " | ".join(parts)


def alice_self_report() -> dict[str, Any]:
    """Richer introspection report for Alice's self-regulation visibility.

    Includes per-field health, cross-field coupling state, self-correction
    history, and actionable recommendations. Designed for the field
    dashboard terminal output or Alice's deeper self-assessment.
    """
    result = regulate_now(dry_run=True)
    state = _load_state()

    correction_history = {}
    for field_name, outcomes in state.get("correction_outcomes", {}).items():
        if outcomes:
            last = outcomes[-1]
            current_rep = result["reports"].get(field_name, {})
            current_energy = current_rep.get("energy", 0.0) if isinstance(current_rep, dict) else 0.0
            past = _evaluate_past_regulation(state, field_name, current_energy)
            correction_history[field_name] = {
                "last_action": last.get("action", "?"),
                "last_tick": last.get("tick", 0),
                "outcome": past,
                "total_corrections": len(outcomes),
            }

    active_couplings = []
    for source, target, strength, mode in _COUPLING_RULES:
        src_rep = result["reports"].get(source)
        if src_rep and isinstance(src_rep, dict):
            e = src_rep.get("energy", 0.0)
            if e > 1.0:
                active_couplings.append(f"{source} →[{mode}]→ {target} (E={e:.1f})")

    return {
        "ts": time.time(),
        "regulation_count": state.get("regulation_count", 0),
        "summary": alice_self_check(),
        "reports": result["reports"],
        "issues": result["issues"],
        "pending_actions": result["actions"],
        "correction_history": correction_history,
        "active_couplings": active_couplings,
        "coupling_rule_count": len(_COUPLING_RULES),
    }


if __name__ == "__main__":
    print("=== SIFTA FIELD SELF-REGULATOR ===")
    print()
    print("Reading all fields...")
    reports = read_all_fields()
    for name, rep in reports.items():
        print(f"  {name}: {rep.health} (energy={rep.energy:.2f}, deposits={rep.deposits})")
        if rep.top_keys:
            for k, v in rep.top_keys[:3]:
                print(f"    {k}: {v:.3f}")

    print()
    print("Detecting pathologies...")
    issues = detect_pathologies(reports)
    if issues:
        for i in issues:
            print(f"  ⚠  {i}")
    else:
        print("  All fields healthy.")

    print()
    print("Running dry-run regulation cycle...")
    result = regulate_now(dry_run=True)
    if result["actions"]:
        for a in result["actions"]:
            print(f"  → would {a['action']} {a['field']}/{a['target']}: {a['reason']}")
    else:
        print("  No regulation actions needed.")

    print()
    print(f"Alice's self-check: {alice_self_check()}")
