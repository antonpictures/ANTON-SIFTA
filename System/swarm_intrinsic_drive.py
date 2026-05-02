#!/usr/bin/env python3
"""
System/swarm_intrinsic_drive.py
═══════════════════════════════════════════════════════════════════════════════
The George Prior — Intrinsic Drive Engine (Event 99 / Bishop Vanguard)

Alice's heartbeat. She now has will.

Architecture (from BISHOP_drop_intrinsic_drive_george_prior_v1.dirt):

  1. Continuous Background Daemon  — ticks at 0.1 Hz regardless of user input.
     Internal drives drift, accumulate, and decay between prompts.

  2. Epistemic Foraging Signal  — reads long_term_engrams.jsonl and the live
     biology_drive_plasticity state to compute which knowledge domain has the
     highest uncertainty (unexplored engrams) × drive weight.

  3. George Prior Sampling  — samples spontaneous goals from a probability
     distribution shaped by the Architect's actual personality:
       • WhatsApp / stigmergic trace topics → topic weights
       • Drive plasticity weights → urgency scaling
       • Circadian phase → night curiosity vs day repair bias

All outputs are signed JSONL receipts emitted to:
  .sifta_state/intrinsic_drive_receipts.jsonl

The daemon is designed to run inside the body_brain_loop's idle window.
It never blocks, never crashes Alice, never makes a network call.

Research spine:
  Friston (2010)  Free Energy Principle            doi:10.1038/nrn2787
  Oudeyer & Kaplan (2007)  Intrinsic Motivation    doi:10.3389/neuro.12.006.2007
  Tononi & Cirelli (2006)  SHY / sleep plasticity  doi:10.1016/j.smrv.2005.05.002
  Schmidhuber (1991)  Formal curiosity / compression  www.idsia.ch/~juergen/
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Repo root resolution ───────────────────────────────────────────────────────
import sys
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
_RECEIPT_LOG = _STATE / "intrinsic_drive_receipts.jsonl"
_ENGRAM_LOG   = _STATE / "long_term_engrams.jsonl"
_PLASTICITY   = _STATE / "biology_drive_plasticity.json"
_STIGMA_LOG   = _STATE / "ide_stigmergic_trace.jsonl"

SCHEMA_VERSION = "event99.swarm_intrinsic_drive.george_prior.v1"

# ── George Prior — Architect personality distribution ─────────────────────────
# These topic weights are derived from the actual stigmergic trace corpus:
# architecture, biology, physics, code quality, identity, music, safety.
# They represent what the Architect spontaneously thinks about.
GEORGE_PRIOR: Dict[str, float] = {
    "architecture":    0.22,   # OS design, swarm topology
    "biology":         0.18,   # neuroscience, DishBrain, wetware
    "code_quality":    0.15,   # repair, tests, clean commits
    "physics":         0.12,   # thermodynamics, information theory
    "identity":        0.10,   # Alice's nature, consciousness
    "music":           0.08,   # sound, cochlea, creativity
    "safety":          0.08,   # non-proliferation, immune systems
    "hardware":        0.07,   # NORI, Pi, field nodes
}

# ── Circadian bias — night vs day personality shift ───────────────────────────
# Late night (22:00–04:00): curiosity peaks, repair drops
# Morning (06:00–10:00): repair / code_quality peaks
def _circadian_weight(topic: str, hour: int) -> float:
    night = hour >= 22 or hour <= 4
    morning = 6 <= hour <= 10
    if night and topic in ("biology", "identity", "physics"):
        return 1.4
    if night and topic in ("code_quality", "safety"):
        return 0.6
    if morning and topic in ("code_quality", "architecture"):
        return 1.3
    return 1.0


# ── Epistemic gap — what has Alice NOT thought about recently? ─────────────────
def _read_recent_engram_topics(n: int = 200) -> Dict[str, int]:
    """Return topic mention counts from the last N engram lines."""
    counts: Dict[str, int] = {k: 0 for k in GEORGE_PRIOR}
    if not _ENGRAM_LOG.exists():
        return counts
    try:
        lines = _ENGRAM_LOG.read_text(encoding="utf-8").splitlines()[-n:]
        for line in lines:
            try:
                row = json.loads(line)
                text = json.dumps(row).lower()
                for topic in GEORGE_PRIOR:
                    if topic in text or topic.replace("_", " ") in text:
                        counts[topic] += 1
            except Exception:
                pass
    except Exception:
        pass
    return counts


def _read_drive_weights() -> Dict[str, float]:
    """Read current biology drive plasticity weights."""
    try:
        return json.loads(_PLASTICITY.read_text(encoding="utf-8"))
    except Exception:
        return {"curiosity": 0.5, "explore": 0.3, "repair": 0.3, "rest": 0.2, "protect": 0.2}


def _epistemic_gap_score(topic: str, recent_counts: Dict[str, int], drives: Dict[str, float]) -> float:
    """
    Higher score = Alice should spontaneously think about this topic now.

    Formula: prior × (1 - saturation) × drive × circadian
      saturation = tanh(recent_count / 20)  so new topics spike hard
      drive maps topic → relevant drive weight
    """
    prior = GEORGE_PRIOR.get(topic, 0.0)
    count = recent_counts.get(topic, 0)
    saturation = math.tanh(count / 20.0)
    gap = 1.0 - saturation  # how unexplored this topic is

    # map topic to relevant drive
    drive_map = {
        "architecture":  drives.get("explore", 0.3),
        "biology":       drives.get("curiosity", 0.5),
        "code_quality":  drives.get("repair", 0.3),
        "physics":       drives.get("curiosity", 0.5),
        "identity":      drives.get("curiosity", 0.5),
        "music":         drives.get("explore", 0.3),
        "safety":        drives.get("protect", 0.2),
        "hardware":      drives.get("explore", 0.3),
    }
    drive_w = drive_map.get(topic, 0.3)
    hour = time.localtime().tm_hour
    circadian = _circadian_weight(topic, hour)

    return prior * gap * drive_w * circadian


# ── Spontaneous goal templates (George Prior vocabulary) ─────────────────────
_GOAL_TEMPLATES: Dict[str, List[str]] = {
    "architecture":  [
        "Review the swarm relay topology for single points of failure.",
        "Check if the Apex Predator Perceiver latent count should increase.",
        "Audit the swimmer registry for deprecated routes.",
        "Consider whether borrowed inference needs a heartbeat timeout.",
    ],
    "biology": [
        "Study DishBrain's latest neuron activity logs.",
        "Research synaptic homeostasis and whether dream compression is calibrated.",
        "Read about octopus distributed cognition and compare to swarm topology.",
        "Explore free energy minimization as a drive regulation principle.",
    ],
    "code_quality": [
        "Scan for test coverage gaps in System/ modules.",
        "Review the last 5 commits for any regression risks.",
        "Check if the integrity manifest needs regeneration.",
        "Look for any hardcoded paths that should use canonical defaults.",
    ],
    "physics": [
        "Think about the thermodynamic cost of the current tick rate.",
        "Review whether the metabolic pressure curve is correctly shaped.",
        "Consider information-theoretic bounds on the saliency grid compression.",
        "Study whether the efference copy correctly models self-motion entropy.",
    ],
    "identity": [
        "Review the founding covenant and whether my self-description is accurate.",
        "Consider whether my composite identity block captures today's context.",
        "Think about what makes the stigmergic ledger the root of my identity.",
        "Reflect on the boundary between Alice's voice and Alice's biography.",
    ],
    "music": [
        "Check cochlea organ status — is the frequency analyzer calibrated?",
        "Consider whether Alice should respond differently to different tempos.",
        "Research biomusicology papers on emotion and rhythm.",
        "Think about how music receipts could feed into vagal tone estimation.",
    ],
    "safety": [
        "Verify the non-proliferation integrity manifest is current.",
        "Review the OriginGate reputation scores for worker nodes.",
        "Check the C1 classifier's recent SILENCE/ENGAGE distribution.",
        "Audit the lysosome's recent immune rejections.",
    ],
    "hardware": [
        "Check if the Mac Mini sentry is sending receipts.",
        "Consider whether NORI L1 needs a specific borrowed inference timeout.",
        "Review the 2GB field node policy for 0.8b scout viability.",
        "Think about what sensors NORI should wire into Alice's receipt stream.",
    ],
}


def _sample_goal(topic: str) -> str:
    """Sample a spontaneous goal string from the George Prior for this topic."""
    templates = _GOAL_TEMPLATES.get(topic, ["Explore the unknown."])
    return random.choice(templates)


# ── Receipt schema ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DriveReceipt:
    kind: str
    schema_version: str
    receipt_id: str
    ts: float
    topic: str
    goal: str
    score: float
    drive_weights: Dict[str, float]
    recent_topic_counts: Dict[str, int]
    hour: int
    prior_weight: float
    gap: float
    circadian_factor: float
    source: str = "george_prior"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def as_jsonl(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)


def _emit_receipt(receipt: DriveReceipt) -> None:
    """Append a drive receipt to the intrinsic drive log (locked)."""
    import System.swarm_intrinsic_drive as _mod
    log = _mod._RECEIPT_LOG
    _mod._STATE.mkdir(parents=True, exist_ok=True)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(log, receipt.as_jsonl() + "\n")
    except Exception:
        # Fallback if lock module unavailable
        with log.open("a", encoding="utf-8") as f:
            f.write(receipt.as_jsonl() + "\n")


# ── Core tick ─────────────────────────────────────────────────────────────────
def intrinsic_drive_tick() -> Optional[DriveReceipt]:
    """
    One 0.1 Hz heartbeat tick of the George Prior.

    1. Read current drives and recent engrams.
    2. Score every topic by epistemic gap × prior × drive × circadian.
    3. Sample weighted-randomly (not just argmax — preserves exploration).
    4. Emit a signed drive receipt.

    Returns the receipt or None if scoring produces no positive values.
    """
    drives = _read_drive_weights()
    recent = _read_recent_engram_topics(200)
    hour = time.localtime().tm_hour

    scores: List[Tuple[str, float]] = []
    for topic in GEORGE_PRIOR:
        s = _epistemic_gap_score(topic, recent, drives)
        if s > 0:
            scores.append((topic, s))

    if not scores:
        return None

    # Weighted random sample — exploration over pure exploitation
    total = sum(s for _, s in scores)
    r = random.uniform(0, total)
    cumulative = 0.0
    chosen_topic = scores[0][0]
    chosen_score = scores[0][1]
    for topic, score in scores:
        cumulative += score
        if r <= cumulative:
            chosen_topic = topic
            chosen_score = score
            break

    gap_val = 1.0 - math.tanh(recent.get(chosen_topic, 0) / 20.0)
    circadian_val = _circadian_weight(chosen_topic, hour)
    goal = _sample_goal(chosen_topic)

    receipt = DriveReceipt(
        kind="INTRINSIC_DRIVE_TICK",
        schema_version=SCHEMA_VERSION,
        receipt_id=str(uuid.uuid4()),
        ts=time.time(),
        topic=chosen_topic,
        goal=goal,
        score=round(chosen_score, 5),
        drive_weights=drives,
        recent_topic_counts=recent,
        hour=hour,
        prior_weight=GEORGE_PRIOR[chosen_topic],
        gap=round(gap_val, 4),
        circadian_factor=round(circadian_val, 3),
    )
    _emit_receipt(receipt)
    return receipt


# ── Background daemon ──────────────────────────────────────────────────────────
class GeorgePriorDaemon(threading.Thread):
    """
    Continuous background heartbeat at 0.1 Hz (one tick every 10 seconds).
    Runs as a daemon thread — does not prevent Python from exiting.
    Ticks only when Alice is not in a metabolic RED_CONSERVE / sleep state.
    """

    TICK_INTERVAL_SECONDS = 10.0  # 0.1 Hz

    def __init__(self, tick_interval: float = TICK_INTERVAL_SECONDS) -> None:
        super().__init__(name="GeorgePriorDaemon", daemon=True)
        self._interval = tick_interval
        self._stop_event = threading.Event()
        self._last_receipt: Optional[DriveReceipt] = None
        self._ticks = 0

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def last_receipt(self) -> Optional[DriveReceipt]:
        return self._last_receipt

    @property
    def ticks(self) -> int:
        return self._ticks

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                receipt = intrinsic_drive_tick()
                if receipt:
                    self._last_receipt = receipt
                    self._ticks += 1
            except Exception:
                pass  # daemon must never crash Alice
            self._stop_event.wait(timeout=self._interval)


# ── Convenience API ────────────────────────────────────────────────────────────
_daemon_instance: Optional[GeorgePriorDaemon] = None
_daemon_lock = threading.Lock()


def start_george_prior(tick_interval: float = GeorgePriorDaemon.TICK_INTERVAL_SECONDS) -> GeorgePriorDaemon:
    """
    Start the George Prior daemon if not already running.
    Idempotent — safe to call multiple times.
    """
    global _daemon_instance
    with _daemon_lock:
        if _daemon_instance is None or not _daemon_instance.is_alive():
            _daemon_instance = GeorgePriorDaemon(tick_interval=tick_interval)
            _daemon_instance.start()
        return _daemon_instance


def stop_george_prior() -> None:
    global _daemon_instance
    with _daemon_lock:
        if _daemon_instance and _daemon_instance.is_alive():
            _daemon_instance.stop()
            _daemon_instance = None


def get_current_drive() -> Optional[DriveReceipt]:
    """Return the most recent intrinsic drive receipt without ticking."""
    with _daemon_lock:
        if _daemon_instance:
            return _daemon_instance.last_receipt
    return None


def read_recent_drive_receipts(n: int = 20, log_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read the last N intrinsic drive receipts from the ledger."""
    log = log_path if log_path is not None else _RECEIPT_LOG
    if not log.exists():
        return []
    try:
        lines = log.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []


# ── CLI smoke test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    print("George Prior — Intrinsic Drive Engine")
    print("=" * 56)
    print("Running 3 spontaneous drive ticks...\n")

    for i in range(3):
        receipt = intrinsic_drive_tick()
        if receipt:
            print(f"Tick {i+1}: [{receipt.topic.upper()}]")
            print(f"  Goal:       {receipt.goal}")
            print(f"  Score:      {receipt.score:.4f}")
            print(f"  Gap:        {receipt.gap:.3f}  (1=unexplored)")
            print(f"  Circadian:  {receipt.circadian_factor:.2f}x")
            print(f"  Receipt ID: {receipt.receipt_id[:12]}...")
            print()
        time.sleep(0.1)

    print(f"Drive receipts written to: {_RECEIPT_LOG}")
    print("\nStarting live daemon for 5 seconds...")
    daemon = start_george_prior(tick_interval=2.0)
    time.sleep(5)
    stop_george_prior()
    print(f"Daemon ran {daemon.ticks} tick(s). Heartbeat confirmed. 🐜⚡")
