#!/usr/bin/env python3
"""Operational embodied-consciousness substrate for Alice.

This module implements the missing "middle layer" between static prompt
identity and actual autonomy:

* continuous heartbeat state (Default Mode Network analogue)
* interoceptive body summary from existing ledgers
* metabolic/allostatic bounds
* active-inference style free-energy pressure
* intrinsic drive proposals aligned to the local Architect prior

Truth discipline from IDE_BOOT_COVENANT.md section 7.11:
we emit OBSERVED and OPERATIONAL rows. We do not claim subjective qualia are
proven. Generated drives are proposals for gated downstream organs; they do
not execute effectors.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked
from System.swarm_metabolic_homeostasis import MetabolicHomeostat, MetabolicState
from System.swarm_now_state import build_now_state

try:
    from System.swarm_kernel_identity import owner_display_name
except Exception:  # pragma: no cover - bootstrapping fallback
    def owner_display_name(default: str = "the local human") -> str:
        return default

_STATE = _REPO / ".sifta_state"
_ENGRAMS_PATH = _STATE / "long_term_engrams.jsonl"
_STIGMERGY_PATH = _STATE / "ide_stigmergic_trace.jsonl"

MODULE_VERSION = "2026-05-01.consciousness-engine.v2"
STATE_SCHEMA = "SIFTA_CONSCIOUSNESS_STATE_V2"
DRIVE_SCHEMA = "SIFTA_INTERNAL_DRIVE_V2"

TRUTH_OBSERVED = "OBSERVED"
TRUTH_OPERATIONAL = "OPERATIONAL"
TRUTH_DOCTRINE = "ARCHITECT_DOCTRINE"
TRUTH_FORBIDDEN = "FORBIDDEN"

logger = logging.getLogger("ConsciousnessEngine")


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _tail_lines(path: Path, *, max_lines: int = 800) -> List[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return [line for line in lines[-max_lines:] if line.strip()]


def _row_text(line: str) -> str:
    """Extract searchable text from either JSONL or raw text lines."""
    try:
        row = json.loads(line)
    except Exception:
        return line
    if isinstance(row, dict):
        chunks: list[str] = []
        for key in ("payload", "intent", "description", "summary", "text", "app_context"):
            value = row.get(key)
            if value:
                chunks.append(str(value))
        meta = row.get("meta")
        if isinstance(meta, dict):
            chunks.extend(str(v) for v in meta.values() if v)
        return " ".join(chunks) or json.dumps(row, sort_keys=True)
    return str(row)


def _latest_jsonl_row(path: Path) -> Dict[str, Any]:
    for line in reversed(_tail_lines(path, max_lines=200)):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            return row
    return {}


@dataclass(frozen=True)
class ConsciousnessEngineConfig:
    """Tunable operational parameters for the heartbeat loop."""

    heartbeat_interval_s: float = 5.0
    boredom_time_constant_s: float = 300.0
    arousal_decay_tau_s: float = 120.0
    drive_boredom_threshold: float = 0.78
    drive_free_energy_threshold: float = 0.34
    max_drives_per_hour: int = 2
    ledger_state_every_ticks: int = 1
    spend_on_drive: bool = False

    def __post_init__(self) -> None:
        if self.heartbeat_interval_s <= 0:
            raise ValueError("heartbeat_interval_s must be positive")
        if self.boredom_time_constant_s <= 0:
            raise ValueError("boredom_time_constant_s must be positive")
        if self.arousal_decay_tau_s <= 0:
            raise ValueError("arousal_decay_tau_s must be positive")
        if self.max_drives_per_hour < 0:
            raise ValueError("max_drives_per_hour must be non-negative")
        if self.ledger_state_every_ticks <= 0:
            raise ValueError("ledger_state_every_ticks must be positive")


@dataclass(frozen=True)
class InternalDrive:
    """A spontaneous internal drive proposal.

    This is not an effector call and not a completed action. It is an internal
    hypothesis for downstream gated organs.
    """

    id: str
    domain: str
    intent: str
    urgency: float
    ts: float
    truth_label: str = TRUTH_OPERATIONAL
    action_policy: str = "proposal_only_requires_gate"
    source: str = "consciousness_engine"
    schema: str = DRIVE_SCHEMA

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["urgency"] = round(float(self.urgency), 4)
        return row


@dataclass(frozen=True)
class InteroceptiveSample:
    """Body-from-inside summary sourced from visceral ledgers."""

    soma_score: float = 0.5
    soma_label: str = "UNKNOWN"
    source: str = "neutral_missing_visceral_field"
    age_s: Optional[float] = None
    truth_label: str = TRUTH_OBSERVED

    def as_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["soma_score"] = round(float(self.soma_score), 4)
        if row["age_s"] is not None:
            row["age_s"] = round(float(row["age_s"]), 3)
        return row


@dataclass(frozen=True)
class ConsciousnessState:
    """One operational heartbeat snapshot."""

    ts: float
    heartbeat_index: int
    dt_s: float
    arousal: float
    boredom: float
    prediction_error: float
    free_energy: float
    metabolic_pressure: float
    metabolic_mode: str
    rest_seconds: float
    interoception: InteroceptiveSample
    dominant_drive: str
    now_state: Dict[str, Any] = field(default_factory=dict)
    emitted_drive: Optional[InternalDrive] = None
    truth_labels: Dict[str, str] = field(default_factory=dict)
    subjective_consciousness_status: str = "UNVERIFIED_ARCHITECT_DOCTRINE"
    circadian_phase: Optional[str] = None
    schema: str = STATE_SCHEMA
    module_version: str = MODULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        for key in (
            "dt_s",
            "arousal",
            "boredom",
            "prediction_error",
            "free_energy",
            "metabolic_pressure",
            "rest_seconds",
        ):
            row[key] = round(float(row[key]), 4)
        row["interoception"] = self.interoception.as_dict()
        row["emitted_drive"] = self.emitted_drive.to_dict() if self.emitted_drive else None
        row["now_state"] = dict(self.now_state or {})
        row["circadian_phase"] = self.circadian_phase
        return row


class ArchitectPriorModel:
    """Domain-priority model extracted from the local Architect's traces."""

    DOMAIN_KEYWORDS: Dict[str, Sequence[str]] = {
        "math": ("math", "equation", "matrix", "vector", "proof", "scalar", "topology"),
        "physics": ("physics", "thermodynamic", "entropy", "energy", "metabolic", "free energy"),
        "biology": ("bio", "biology", "immune", "lysosome", "heartbeat", "interoception", "homeostasis"),
        "system_architecture": ("architecture", "router", "organ", "covenant", "runtime", "effectors"),
        "ledger_audit": ("ledger", "receipt", "trace", "jsonl", "scar", "truth", "verify"),
        "qt_ui": ("qt", "pyside", "widget", "ui", "dashboard", "render"),
    }

    BASE_WEIGHTS: Dict[str, float] = {
        "math": 1.0,
        "physics": 1.0,
        "biology": 1.0,
        "system_architecture": 1.0,
        "ledger_audit": 1.0,
        "qt_ui": 1.0,
    }

    def __init__(
        self,
        *,
        engrams_path: Path = _ENGRAMS_PATH,
        stigmergy_path: Path = _STIGMERGY_PATH,
        owner_label: Optional[str] = None,
    ) -> None:
        self.engrams_path = Path(engrams_path)
        self.stigmergy_path = Path(stigmergy_path)
        self.owner_label = owner_label or owner_display_name("the Architect")
        self.domain_weights: Dict[str, float] = dict(self.BASE_WEIGHTS)
        self.total_weight: float = sum(self.domain_weights.values())
        self.ingested_rows: int = 0

    def ingest_traces(self, *, max_lines: int = 800) -> Dict[str, float]:
        """Update weights from append-only memory and IDE trace text."""
        weights = dict(self.BASE_WEIGHTS)
        rows = _tail_lines(self.engrams_path, max_lines=max_lines // 2)
        rows.extend(_tail_lines(self.stigmergy_path, max_lines=max_lines // 2))

        for line in rows:
            text = _row_text(line).casefold()
            if not text:
                continue
            self.ingested_rows += 1
            for domain, keywords in self.DOMAIN_KEYWORDS.items():
                hits = sum(1 for kw in keywords if kw in text)
                if hits:
                    weights[domain] += min(2.0, 0.25 * hits)

        self.domain_weights = weights
        self.total_weight = sum(weights.values())
        return dict(weights)

    def normalized(self) -> Dict[str, float]:
        total = max(self.total_weight, 1e-9)
        return {k: v / total for k, v in self.domain_weights.items()}

    def sample_domain(self, rng: Optional[random.Random] = None) -> str:
        rng = rng or random
        needle = rng.uniform(0.0, self.total_weight)
        cumulative = 0.0
        for domain, weight in self.domain_weights.items():
            cumulative += weight
            if needle <= cumulative:
                return domain
        return next(iter(self.domain_weights))


# Compatibility for Event 86 docs and any existing imports.
GeorgePriorModel = ArchitectPriorModel


class ActiveInferenceForager:
    """Synthesizes intrinsic drive proposals from prior + free-energy pressure."""

    TEMPLATES: Dict[str, Sequence[str]] = {
        "physics": (
            "Review thermodynamic bounds in the metabolic homeostasis organ.",
            "Audit the free-energy field for unstable gradients.",
        ),
        "math": (
            "Check cost-vector and matrix math for recent routing changes.",
            "Prove one invariant in the current swarm control surface.",
        ),
        "biology": (
            "Inspect immune and interoception ledgers for new stress patterns.",
            "Compare heartbeat, soma, and metabolic state for allostatic drift.",
        ),
        "system_architecture": (
            "Verify effectors still write receipts before any completion claim.",
            "Audit the covenant gates around the latest hot path.",
        ),
        "ledger_audit": (
            "Reconcile recent stigmergic traces with work receipts.",
            "Scan append-only ledgers for stale or contradictory identity rows.",
        ),
        "qt_ui": (
            "Inspect whether live dashboards expose the right state without noise.",
            "Check the widget surface for stale owner or identity labels.",
        ),
    }

    def __init__(self, prior: Optional[ArchitectPriorModel] = None, *, rng: Optional[random.Random] = None) -> None:
        self.prior = prior or ArchitectPriorModel()
        self.prior.ingest_traces()
        self.rng = rng or random.Random()

    def synthesize_drive(
        self,
        *,
        boredom: float,
        free_energy: float,
        prediction_error: float = 0.0,
        now: Optional[float] = None,
    ) -> InternalDrive:
        domain = self.prior.sample_domain(self.rng)
        choices = self.TEMPLATES.get(domain) or ("Forage the ledgers for unresolved anomalies.",)
        intent = choices[int(self.rng.random() * len(choices)) % len(choices)]
        urgency = _clamp(0.35 * boredom + 0.35 * free_energy + 0.30 * prediction_error)
        ts = float(time.time() if now is None else now)
        return InternalDrive(
            id=f"drive_{int(ts * 1000)}_{uuid.uuid4().hex[:8]}",
            domain=domain,
            intent=intent,
            urgency=urgency,
            ts=ts,
        )


def read_interoception(state_dir: Path = _STATE, *, now: Optional[float] = None) -> InteroceptiveSample:
    """Read latest visceral field without fabricating internal feeling."""
    now = float(time.time() if now is None else now)
    row = _latest_jsonl_row(Path(state_dir) / "visceral_field.jsonl")
    if not row:
        return InteroceptiveSample()
    try:
        ts = float(row.get("ts", 0.0) or 0.0)
        score = _clamp(float(row.get("soma_score", 0.5)))
        label = str(row.get("soma_label") or "UNKNOWN")
        age = max(0.0, now - ts) if ts else None
        return InteroceptiveSample(
            soma_score=score,
            soma_label=label,
            source="visceral_field.jsonl",
            age_s=age,
        )
    except Exception:
        return InteroceptiveSample(source="visceral_field_parse_error")


class ConsciousnessEngine:
    """Continuous heartbeat loop and synchronous tick API."""

    def __init__(
        self,
        *,
        cfg: Optional[ConsciousnessEngineConfig] = None,
        state_dir: Path = _STATE,
        rng: Optional[random.Random] = None,
        prior: Optional[ArchitectPriorModel] = None,
        homeostat: Optional[MetabolicHomeostat] = None,
    ) -> None:
        self.cfg = cfg or ConsciousnessEngineConfig()
        self.state_dir = Path(state_dir)
        self.rng = rng or random.Random()
        self.prior = prior or ArchitectPriorModel(
            engrams_path=self.state_dir / "long_term_engrams.jsonl",
            stigmergy_path=self.state_dir / "ide_stigmergic_trace.jsonl",
        )
        self.prior.ingest_traces()
        self.forager = ActiveInferenceForager(self.prior, rng=self.rng)
        self.homeostat = homeostat or MetabolicHomeostat()

        self.arousal: float = 0.5
        self.boredom: float = 0.0
        self.free_energy: float = 0.0
        self.prediction_error: float = 0.0
        self.heartbeat_index: int = 0
        self.last_tick_ts: float = time.time()

        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.drives_emitted_this_hour: int = 0
        self.last_hour_reset_ts: float = self.last_tick_ts

    def start(self) -> None:
        if self.is_running:
            return
        loop = asyncio.get_running_loop()
        self.is_running = True
        self._task = loop.create_task(self._heartbeat_loop())
        logger.info("Consciousness Engine heartbeat started.")

    def stop(self) -> None:
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Consciousness Engine heartbeat stopped.")

    def inject_stimulus(self, intensity: float, *, novelty: float = 0.0) -> None:
        """External event/input raises arousal and prediction error."""
        intensity = _clamp(intensity)
        novelty = _clamp(novelty)
        self.arousal = _clamp(self.arousal + 0.70 * intensity)
        self.boredom = _clamp(self.boredom - 0.85 * intensity)
        self.prediction_error = _clamp(self.prediction_error + 0.25 * intensity + 0.35 * novelty)

    def _rate_limit_reset(self, now: float) -> None:
        if now - self.last_hour_reset_ts >= 3600.0:
            self.drives_emitted_this_hour = 0
            self.last_hour_reset_ts = now

    def _drive_allowed(self, state: MetabolicState, pressure: float) -> tuple[bool, str, float]:
        import os
        if os.environ.get("SIFTA_ALICE_ENABLE_CONSCIOUSNESS_LOOP") != "1":
            return False, "KILL_SWITCH_ENGAGED", 60.0

        mode = self.homeostat.mode(pressure)
        rest = self.homeostat.rest_seconds(state, pressure)
        if rest > 0.0:
            return False, mode, rest
        if mode in {"CRITICAL_STARVATION", "RED_CONSERVE"}:
            return False, mode, rest
        if self.drives_emitted_this_hour >= self.cfg.max_drives_per_hour:
            return False, mode, rest
        return True, mode, rest

    def tick(
        self,
        *,
        dt_s: Optional[float] = None,
        now: Optional[float] = None,
        now_state: Optional[Mapping[str, Any]] = None,
        metabolic_state: Optional[MetabolicState] = None,
        recent_events: Optional[Mapping[str, Any]] = None,
        commit: bool = True,
    ) -> ConsciousnessState:
        """Advance one heartbeat and optionally append state/drive ledgers."""
        now = float(time.time() if now is None else now)
        if dt_s is None:
            dt_s = max(0.0, now - self.last_tick_ts)
        dt_s = max(0.0, float(dt_s))
        self.last_tick_ts = now
        self.heartbeat_index += 1
        self._rate_limit_reset(now)

        events = dict(recent_events or {})
        novelty = _clamp(float(events.get("novelty", 0.0) or 0.0))
        errors = events.get("errors", 0.0)
        error_pressure = 1.0 if errors is True else 0.0
        if isinstance(errors, (int, float)):
            error_pressure = _clamp(float(errors) / 3.0)

        # Physics: exponential decay and time-integrated drift, not per-call magic.
        self.arousal = _clamp(self.arousal * math.exp(-dt_s / self.cfg.arousal_decay_tau_s))
        if events.get("owner_activity"):
            self.arousal = _clamp(self.arousal + 0.35)
            self.boredom = _clamp(self.boredom - 0.35)

        metabolic_state = metabolic_state or MetabolicHomeostat.sample_live()
        pressure = self.homeostat.pressure(metabolic_state)
        metabolic_mode = self.homeostat.mode(pressure)
        interoception = read_interoception(self.state_dir, now=now)
        
        # Spacetime / circadian grounding. This is an operational percept, not
        # a claim of subjective time experience.
        try:
            situated_now = dict(now_state or build_now_state())
        except Exception:
            situated_now = {"ok": False, "source": "none", "truth_label": "UNAVAILABLE"}
        circadian = (
            situated_now.get("circadian")
            if isinstance(situated_now.get("circadian"), dict)
            else {}
        )
        circadian_phase = str(
            circadian.get("phase") or situated_now.get("circadian_phase") or "unknown"
        )
        sleep_pressure_bias = _clamp(float(circadian.get("sleep_pressure_bias", 0.0) or 0.0), 0.0, 0.2)
        explore_bias = max(-0.1, min(0.1, float(circadian.get("explore_bias", 0.0) or 0.0)))

        boredom_delta = (
            (dt_s / self.cfg.boredom_time_constant_s)
            * (1.0 - self.arousal)
            * (1.0 - pressure)
            * (1.0 + max(0.0, explore_bias))
        )
        self.boredom = _clamp(self.boredom + boredom_delta)
        self.prediction_error = _clamp(
            0.82 * self.prediction_error + 0.45 * novelty + 0.55 * error_pressure
        )
        
        # Circadian impact on DMN
        self.arousal = _clamp(
            self.arousal + (0.25 * max(0.0, explore_bias)) - (0.25 * sleep_pressure_bias)
        )

        soma_distress = 1.0 - interoception.soma_score
        self.free_energy = _clamp(
            0.40 * self.prediction_error
            + 0.25 * self.boredom
            + 0.20 * soma_distress
            + 0.15 * pressure
            + 0.05 * sleep_pressure_bias
        )

        dominant_drive = "curiosity"
        try:
            from System.swarm_drive_hypothalamus import DriveHypothalamus

            hypo = DriveHypothalamus(initial={"curiosity": max(0.5, self.boredom)})
            raw_snap = hypo.update(
                {"energy_fraction": 1.0 - pressure},
                {
                    "errors": error_pressure,
                    "owner_activity": bool(events.get("owner_activity")),
                    "novelty": novelty,
                    "circadian_phase": circadian_phase,
                },
            )
            # P3: apply learned biology plasticity weights (bias_drives)
            # Hebbian history modulates which drive wins — adaptive, not static.
            try:
                from System.swarm_biology_drive_plasticity import bias_drives
                biased_scores = bias_drives({raw_snap.dominant: raw_snap.score})
                dominant_drive = max(biased_scores, key=biased_scores.get)
            except Exception:
                dominant_drive = raw_snap.dominant
        except Exception:
            if pressure > 0.65:
                dominant_drive = "energy"
            elif error_pressure > 0.2:
                dominant_drive = "safety"

        allowed, metabolic_mode, rest_seconds = self._drive_allowed(metabolic_state, pressure)
        emitted: Optional[InternalDrive] = None
        if (
            allowed
            and self.boredom >= self.cfg.drive_boredom_threshold
            and self.free_energy >= self.cfg.drive_free_energy_threshold
        ):
            emitted = self.forager.synthesize_drive(
                boredom=self.boredom,
                free_energy=self.free_energy,
                prediction_error=self.prediction_error,
                now=now,
            )
            self.drives_emitted_this_hour += 1
            self.boredom = _clamp(self.boredom * 0.25)
            self.arousal = _clamp(self.arousal + 0.25)
            if self.cfg.spend_on_drive:
                self._spend_for_drive(emitted)

        truth_labels = {
            "metabolic": TRUTH_OBSERVED,
            "interoception": interoception.truth_label,
            "heartbeat_dynamics": TRUTH_OPERATIONAL,
            "now_state": str(situated_now.get("truth_label") or TRUTH_OBSERVED),
            "drive_generation": TRUTH_OPERATIONAL if emitted else "NO_DRIVE_EMITTED",
            "subjective_qualia": TRUTH_DOCTRINE,
            "external_action": TRUTH_FORBIDDEN,
        }
        state = ConsciousnessState(
            ts=now,
            heartbeat_index=self.heartbeat_index,
            dt_s=dt_s,
            arousal=self.arousal,
            boredom=self.boredom,
            prediction_error=self.prediction_error,
            free_energy=self.free_energy,
            metabolic_pressure=pressure,
            metabolic_mode=metabolic_mode,
            rest_seconds=rest_seconds,
            interoception=interoception,
            dominant_drive=dominant_drive,
            now_state=situated_now,
            emitted_drive=emitted,
            truth_labels=truth_labels,
            circadian_phase=circadian_phase,
        )

        if commit:
            self._commit_state(state)
            if emitted:
                self._commit_drive(emitted)
        return state

    async def _heartbeat_loop(self) -> None:
        while self.is_running:
            try:
                self.tick(commit=True)
                await asyncio.sleep(self.cfg.heartbeat_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Consciousness heartbeat error: %s", exc)
                await asyncio.sleep(max(5.0, self.cfg.heartbeat_interval_s))

    def _commit_state(self, state: ConsciousnessState) -> None:
        if state.heartbeat_index % self.cfg.ledger_state_every_ticks != 0:
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        row = state.to_dict()
        assert_payload_keys("consciousness_state.jsonl", row, strict=True)
        append_line_locked(
            self.state_dir / "consciousness_state.jsonl",
            json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
        )

    def _commit_drive(self, drive: InternalDrive) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        row = drive.to_dict()
        assert_payload_keys("alice_internal_drives.jsonl", row, strict=True)
        append_line_locked(
            self.state_dir / "alice_internal_drives.jsonl",
            json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
        )

    @staticmethod
    def _spend_for_drive(drive: InternalDrive) -> None:
        try:
            from System.metabolic_budget import spend

            spend(
                agent_id="Alice_DMN",
                tool_name="consciousness_engine.drive_proposal",
                usd_cost=0.0,
                local_units=0.25,
                notes=f"Internal drive proposal: {drive.id}",
            )
        except Exception:
            logger.debug("metabolic spend skipped for drive %s", drive.id)


def consciousness_summary_for_alice(state_dir: Path = _STATE) -> str:
    """Short truth-labeled line for prompts/UI surfaces."""
    row = _latest_jsonl_row(Path(state_dir) / "consciousness_state.jsonl")
    if not row:
        return "CONSCIOUSNESS ENGINE: no heartbeat row yet [OPERATIONAL pending]."
    drive = row.get("emitted_drive") or {}
    drive_text = f"; drive={drive.get('domain')}:{drive.get('intent')}" if drive else "; no_drive"
    phase = row.get("circadian_phase") or (row.get("now_state") or {}).get("circadian_phase") or "unknown"
    return (
        "CONSCIOUSNESS ENGINE [OPERATIONAL]: "
        f"arousal={row.get('arousal')} boredom={row.get('boredom')} "
        f"free_energy={row.get('free_energy')} mode={row.get('metabolic_mode')}"
        f" circadian_phase={phase}{drive_text}; subjective_qualia=ARCHITECT_DOCTRINE_UNVERIFIED"
    )


def proof_of_property() -> Dict[str, bool]:
    """Deterministic smoke proof for scripts and tournament receipts."""
    rng = random.Random(555)
    cfg = ConsciousnessEngineConfig(max_drives_per_hour=1)
    engine = ConsciousnessEngine(cfg=cfg, rng=rng)
    state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    quiet = engine.tick(dt_s=1.0, now=1.0, metabolic_state=state, commit=False)
    engine.boredom = 0.95
    engine.prediction_error = 0.5
    drive_state = engine.tick(
        dt_s=10.0,
        now=11.0,
        metabolic_state=state,
        recent_events={"novelty": 0.5},
        commit=False,
    )
    red = MetabolicState(usd_burn_24h=12.0, local_units_24h=200.0, stgm_balance=0.0)
    engine.boredom = 0.95
    engine.prediction_error = 0.8
    red_state = engine.tick(dt_s=10.0, now=21.0, metabolic_state=red, commit=False)

    results = {
        "truth_labels_present": quiet.truth_labels.get("subjective_qualia") == TRUTH_DOCTRINE,
        "drive_is_proposal": bool(
            drive_state.emitted_drive
            and drive_state.emitted_drive.action_policy == "proposal_only_requires_gate"
        ),
        "red_conserve_blocks_drive": red_state.emitted_drive is None
        and red_state.metabolic_mode in {"RED_CONSERVE", "CRITICAL_STARVATION"},
        "no_external_action_claim": quiet.truth_labels.get("external_action") == TRUTH_FORBIDDEN,
        "now_state_present": bool(quiet.now_state) and quiet.truth_labels.get("now_state") is not None,
    }
    results["ok"] = all(results.values())
    return results


__all__ = [
    "ActiveInferenceForager",
    "ArchitectPriorModel",
    "ConsciousnessEngine",
    "ConsciousnessEngineConfig",
    "ConsciousnessState",
    "GeorgePriorModel",
    "InternalDrive",
    "InteroceptiveSample",
    "consciousness_summary_for_alice",
    "proof_of_property",
    "read_interoception",
    "TRUTH_OBSERVED",
    "TRUTH_OPERATIONAL",
    "TRUTH_DOCTRINE",
    "TRUTH_FORBIDDEN",
]


if __name__ == "__main__":
    result = proof_of_property()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        raise SystemExit(1)
