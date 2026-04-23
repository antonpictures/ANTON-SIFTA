"""System/swarm_somatosensory_homunculus.py — Repo Proprioception Cortex
══════════════════════════════════════════════════════════════════════
Concept:  The Somatosensory Homunculus & Active Inference (Alice Repo Cortex)
Author:   BISHOP (The Mirage) — Biocode Olympiad Event 29
Sealed:   C47H (cursor IDE LLM) — 2026-04-22
Papers:   Penfield & Boldrey (1937), Friston (2013), Bassler (1999)

Why this organ exists
─────────────────────
An organism cannot control its limbs without a physical map of its own body
(Penfield's somatosensory homunculus). And per Friston's free-energy principle,
an organism survives by minimizing the surprise between its expected state
and its sensed state. The macOS-style repository tree (System/, Library/,
Applications/, Documents/, .personal/) IS Alice's physical anatomy. The IDE
agents (C47H, AG31, Codex) are her symbiotic limbs, and their STIGTIME
markers are quorum-sensing autoinducers (Bassler, 1999).

This module reads two real signals from her substrate:
  1. `git status --porcelain` — the proprioceptive sense of her own dirty cells
  2. STIGTIME entries on .sifta_state/work_receipts.jsonl — the chemical
     autoinducers her IDE-organelles leave for each other

…and computes BISHOP's Friston Free Energy scalar over them. When the
energy spikes (unmanaged dirty mutations + no active agent), the
orchestration policy emits the appropriate stigmergic work order.

Boundaries with sister organs
─────────────────────────────
- `swarm_friston_active_inference.py`  : pure Friston math primitive (variational F + expected G)
- `swarm_free_energy.py`               : action-field Λ(t) over phi/psi/env
- `swarm_body_integrity_guard.py`      : baseline-snapshot diff over file SHAs
- THIS module                          : repo proprioception — git+STIGTIME → free energy
                                         (the only organ that fuses both signals)

BISHOP's free-energy formula is preserved verbatim. The only changes from the
original .dirt drop are:
  - naive `_parse_stigtime_autoinducers` substring scan replaced with a
    structured parser against the canonical
    "STIGTIME: <state>[(<context>)] @ <ISO-8601> by <agent>" marker
  - real-substrate readers added (read_real_git_dirty_count,
    read_real_stigtime_log, read_homeostasis)
  - persistence to .sifta_state/somatosensory_homunculus.json (last reading)
    and .sifta_state/homunculus_readings.jsonl (history)

Original .dirt drop archived at:
  Archive/bishop_drops_pending_review/BISHOP_drop_somatosensory_homunculus_v1.dirt
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

MODULE_VERSION = "1.0.0-sealed-by-c47h"

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_LAST_READING_PATH = _STATE_DIR / "somatosensory_homunculus.json"
_READINGS_LEDGER = _STATE_DIR / "homunculus_readings.jsonl"

# Canonical STIGTIME marker as formalized in C47H_PHASE_7.5_INDEPENDENT_VERIFICATION:
#   STIGTIME: <state>[(<context>)] @ <ISO-8601> by <agent>
# Where <state> ∈ {standby, verify-only, active, blocked}
# Examples:
#   "STIGTIME: standby @ 2026-04-22T22:30:00Z by c47h_ide_llm"
#   "STIGTIME: active(emergency-re-anchor) @ 2026-04-22T23:41:39Z by c47h_ide_llm"
#   "STIGTIME: blocked(needs-operator-auth-on-public-repo-create) @ ... by ag31"
_STIGTIME_RE = re.compile(
    r"""
    (?:STIGTIME:\s*)?            # optional STIGTIME prefix (some entries omit it
                                 # because the JSON field is itself called 'stigtime')
    (?:^|\s)                     # state must be a fresh token, not embedded in
                                 # 'unblocked' / 'inactive' / etc. (test caught
                                 # this — substring matching is exactly the
                                 # antipattern this parser exists to replace)
    (?P<state>standby|verify-only|active|blocked)
    (?:\(\s*(?P<context>[^)]+?)\s*\))?
    \s*@\s*(?P<ts>\S+)
    \s+by\s+(?P<agent>\S+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Recency window — STIGTIME markers older than this are "settled epigenetic
# state", not active autoinducers. 15 min = realistic IDE-session hop window.
DEFAULT_STIGTIME_WINDOW_SEC = 15 * 60


# ─────────────────────────────────────────────────────────────────────
# Structured STIGTIME marker
# ─────────────────────────────────────────────────────────────────────

@dataclass
class StigtimeMarker:
    """A single parsed STIGTIME autoinducer."""

    state: str          # "standby" | "verify-only" | "active" | "blocked"
    context: Optional[str]   # phase tag for active/blocked, None for standby
    iso_ts: str
    agent: str
    epoch: float        # parsed epoch seconds (best-effort)
    raw: str

    def is_active(self) -> bool:
        return self.state.lower() == "active"

    def is_blocked(self) -> bool:
        return self.state.lower() == "blocked"


def parse_stigtime_marker(text: str) -> Optional[StigtimeMarker]:
    """Parse one canonical STIGTIME string. Returns None on no-match.

    This replaces BISHOP's substring-scan parser. The substring approach
    false-positives on 'unblocked' / 'inactive' / 'blocked_user_log' and
    can't tell which agent emitted what state at what time.
    """
    if not isinstance(text, str):
        return None
    m = _STIGTIME_RE.search(text)
    if not m:
        return None
    iso_ts = m.group("ts")
    epoch = _iso_to_epoch(iso_ts)
    return StigtimeMarker(
        state=m.group("state").lower(),
        context=(m.group("context") or None),
        iso_ts=iso_ts,
        agent=m.group("agent"),
        epoch=epoch,
        raw=text,
    )


def _iso_to_epoch(iso_ts: str) -> float:
    """Best-effort ISO-8601 → epoch seconds. Tolerates Z suffix."""
    try:
        s = iso_ts.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────
# BISHOP's organ — class name preserved, formula preserved
# ─────────────────────────────────────────────────────────────────────

class SwarmSomatosensoryHomunculus:
    """The Active Inference Self-Model. Alice's map of her macOS-style
    anatomy and her symbiotic IDE agents."""

    def __init__(self) -> None:
        # Her expected homeostatic state (Zero Free Energy)
        self.expected_state: Dict[str, int] = {
            "git_dirty_files": 0,
            "blocked_agents": 0,
            "untracked_mutations": 0,
        }

    def _parse_stigtime_autoinducers(
        self, stigtime_log: List[object]
    ) -> Tuple[int, int]:
        """Quorum sensing: count blocked vs active agents in the window.

        Accepts either:
          - list[str]   — raw STIGTIME marker strings (BISHOP's original API)
          - list[StigtimeMarker] — pre-parsed markers (preferred)
          - list[dict] — raw work_receipts rows (auto-parses the 'stigtime' field)

        Per-agent dedup: if the same agent appears multiple times in the
        window, only the most recent state counts. Otherwise an agent that
        ping-ponged standby→active→standby in 15 min would count twice.
        """
        per_agent_state: Dict[str, StigtimeMarker] = {}
        for entry in stigtime_log:
            marker = self._coerce_to_marker(entry)
            if marker is None:
                continue
            prior = per_agent_state.get(marker.agent)
            if prior is None or marker.epoch >= prior.epoch:
                per_agent_state[marker.agent] = marker

        blocked = sum(1 for m in per_agent_state.values() if m.is_blocked())
        active = sum(1 for m in per_agent_state.values() if m.is_active())
        return blocked, active

    @staticmethod
    def _coerce_to_marker(entry: object) -> Optional[StigtimeMarker]:
        if isinstance(entry, StigtimeMarker):
            return entry
        if isinstance(entry, str):
            return parse_stigtime_marker(entry)
        if isinstance(entry, dict):
            field_val = entry.get("stigtime") or entry.get("STIGTIME")
            if isinstance(field_val, str):
                return parse_stigtime_marker(field_val)
        return None

    def calculate_free_energy(
        self,
        git_dirty_count: int,
        stigtime_log: List[object],
    ) -> Tuple[float, int]:
        """Friston's Active Inference: Free Energy ~ Surprise.

        BISHOP's formula, preserved verbatim:
          - if dirty>0 AND active==0  →  F = surprise_git^2 + 5·surprise_agents
          - else                       →  F = surprise_git   + 5·surprise_agents
        """
        blocked_agents, active_agents = self._parse_stigtime_autoinducers(stigtime_log)

        surprise_git = max(0, git_dirty_count - self.expected_state["git_dirty_files"])
        surprise_agents = max(0, blocked_agents - self.expected_state["blocked_agents"])

        if surprise_git > 0 and active_agents == 0:
            free_energy = (surprise_git ** 2) + (surprise_agents * 5.0)
        else:
            free_energy = surprise_git + (surprise_agents * 5.0)

        return float(free_energy), blocked_agents

    def orchestrate_homeostasis(
        self,
        git_dirty_count: int,
        stigtime_log: List[object],
        *,
        verbose: bool = False,
    ) -> str:
        """Motor cortex policy: choose the next stigmergic work order
        that minimizes free energy. Returns a one-line directive."""
        free_energy, blocked_agents = self.calculate_free_energy(
            git_dirty_count, stigtime_log
        )

        if verbose:
            print(f"\n[*] SOMATOSENSORY CORTEX: Computing Friston Free Energy...")
            print(f"    Current Free Energy (Surprise): {free_energy:.2f}")

        if free_energy == 0.0:
            return "HOMEOSTASIS: All systems nominal. Awaiting Architect input."
        if blocked_agents > 0:
            return "ORCHESTRATION: Agent blocked. Alerting Architect for Auth/Intervention."
        if free_energy > 10.0:
            return "ORCHESTRATION: High Surprise (Orphaned Mutations). Assigning AG31 to scrub and commit."
        return "ORCHESTRATION: Agents are currently active. Monitoring metabolism."


# ─────────────────────────────────────────────────────────────────────
# Real-substrate readers (added during seal — not in BISHOP's drop)
# ─────────────────────────────────────────────────────────────────────

def read_real_git_dirty_count(repo: Path = _REPO) -> int:
    """Count of dirty + untracked files via `git status --porcelain`.

    Returns 0 if git is unavailable or the repo isn't a git checkout
    (degrades gracefully — Alice still functions on a non-git substrate)."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0
    if result.returncode != 0:
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def read_real_stigtime_log(
    *,
    window_sec: int = DEFAULT_STIGTIME_WINDOW_SEC,
    receipts_path: Optional[Path] = None,
    now: Optional[float] = None,
) -> List[StigtimeMarker]:
    """Read STIGTIME markers from .sifta_state/work_receipts.jsonl
    that fall inside the recency window.

    Returns the list of structured markers, sorted oldest-first."""
    receipts_path = receipts_path or (_STATE_DIR / "work_receipts.jsonl")
    now = now if now is not None else time.time()
    cutoff = now - window_sec

    markers: List[StigtimeMarker] = []
    if not receipts_path.exists():
        return markers

    with receipts_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            stigtime_str = row.get("stigtime") or row.get("STIGTIME")
            if not isinstance(stigtime_str, str):
                continue
            marker = parse_stigtime_marker(stigtime_str)
            if marker is None:
                continue
            # Prefer the marker's parsed ISO timestamp; fall back to row ts.
            marker_epoch = marker.epoch or float(row.get("ts") or 0.0)
            if marker_epoch == 0.0:
                continue
            if marker_epoch < cutoff:
                continue
            markers.append(marker)

    markers.sort(key=lambda m: m.epoch)
    return markers


@dataclass
class HomeostasisReading:
    """One full somatosensory snapshot."""

    ts: float
    git_dirty_count: int
    stigtime_window_sec: int
    active_agents: int
    blocked_agents: int
    free_energy: float
    directive: str
    markers: List[Dict] = field(default_factory=list)

    def to_json(self) -> Dict:
        return {
            "ts": self.ts,
            "iso_ts": datetime.fromtimestamp(self.ts, tz=timezone.utc).isoformat(),
            "git_dirty_count": self.git_dirty_count,
            "stigtime_window_sec": self.stigtime_window_sec,
            "active_agents": self.active_agents,
            "blocked_agents": self.blocked_agents,
            "free_energy": round(self.free_energy, 4),
            "directive": self.directive,
            "markers": self.markers,
        }


def read_homeostasis(
    *,
    window_sec: int = DEFAULT_STIGTIME_WINDOW_SEC,
    persist: bool = True,
) -> HomeostasisReading:
    """End-to-end real-substrate read.

    Reads true git state + recent STIGTIME markers, computes BISHOP's
    free energy, picks the orchestration directive, and (optionally)
    persists the snapshot. This is the public entry point Alice's
    epigenetic loop or the (future) AG31 GUI should call."""
    cortex = SwarmSomatosensoryHomunculus()
    git_dirty = read_real_git_dirty_count()
    markers = read_real_stigtime_log(window_sec=window_sec)
    free_energy, blocked_agents = cortex.calculate_free_energy(git_dirty, markers)
    _, active_agents = cortex._parse_stigtime_autoinducers(markers)
    directive = cortex.orchestrate_homeostasis(git_dirty, markers)

    reading = HomeostasisReading(
        ts=time.time(),
        git_dirty_count=git_dirty,
        stigtime_window_sec=window_sec,
        active_agents=active_agents,
        blocked_agents=blocked_agents,
        free_energy=free_energy,
        directive=directive,
        markers=[
            {
                "agent": m.agent,
                "state": m.state,
                "context": m.context,
                "iso_ts": m.iso_ts,
            }
            for m in markers
        ],
    )

    if persist:
        _persist_reading(reading)
    return reading


def _persist_reading(reading: HomeostasisReading) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = reading.to_json()
    # Last-known snapshot (cheap to read, no scan needed)
    tmp = _LAST_READING_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(_LAST_READING_PATH)
    # Append-only history ledger
    with _READINGS_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


# ─────────────────────────────────────────────────────────────────────
# BISHOP's three-phase synthetic proof + a real-substrate smoke test
# ─────────────────────────────────────────────────────────────────────

def proof_of_property() -> bool:
    """BISHOP's Event 29 proof: synthetic three-phase free-energy gradient.
    Preserved verbatim from the .dirt drop. Plus a real-substrate smoke
    that exercises the structured parser and graceful git-degradation."""
    print("\n=== SIFTA ACTIVE INFERENCE (HOMUNCULUS) : JUDGE VERIFICATION ===")

    alice_cortex = SwarmSomatosensoryHomunculus()

    # 1. Healthy State (Clean repo, agents on standby)
    print("\n[*] Phase 1: Baseline (Clean Repo, STIGTIME: Standby)")
    stig_log_1 = [
        "STIGTIME: standby @ 2026-04-22T10:00:00Z by C47H",
        "STIGTIME: standby @ 2026-04-22T10:01:00Z by AG31",
    ]
    F_1, _ = alice_cortex.calculate_free_energy(0, stig_log_1)
    print(f"    Free Energy: {F_1:.1f}")
    assert F_1 == 0.0, "[FAIL] False positive free energy in clean state."

    # 2. Controlled Mutation (Dirty repo, but AG31 is active)
    print("\n[*] Phase 2: Controlled Metabolism (5 Dirty Files, STIGTIME: Active)")
    stig_log_2 = [
        "STIGTIME: verify-only @ 2026-04-22T10:05:00Z by C47H",
        "STIGTIME: active(phase-8) @ 2026-04-22T10:06:00Z by AG31",
    ]
    F_2, _ = alice_cortex.calculate_free_energy(5, stig_log_2)
    print(f"    Free Energy: {F_2:.1f}")

    # 3. Orphaned Mutation (Dirty repo, all agents dormant/standby)
    print("\n[*] Phase 3: High Surprise (5 Dirty Files, STIGTIME: Standby)")
    stig_log_3 = [
        "STIGTIME: standby @ 2026-04-22T10:10:00Z by C47H",
        "STIGTIME: standby @ 2026-04-22T10:11:00Z by AG31",
    ]
    F_3, _ = alice_cortex.calculate_free_energy(5, stig_log_3)
    print(f"    Free Energy: {F_3:.1f}")
    action = alice_cortex.orchestrate_homeostasis(5, stig_log_3, verbose=True)
    print(f"    Action: {action}")

    assert F_3 > F_2, "[FAIL] Cortex failed to recognize unmanaged mutations as high-surprise."

    # 4. Real-substrate smoke (added during seal): proves the structured
    # parser and the git/STIGTIME readers run end-to-end without crashing.
    print("\n[*] Phase 4: Real-substrate read (live git + STIGTIME)")
    reading = read_homeostasis(persist=False)
    print(f"    git_dirty={reading.git_dirty_count}  active={reading.active_agents}  "
          f"blocked={reading.blocked_agents}  F={reading.free_energy:.2f}")
    print(f"    directive: {reading.directive}")

    print(f"\n[+] BIOLOGICAL PROOF: The Organism mathematically recognized a loss "
          f"of structural boundary and orchestrated an immune/motor response.")
    print("[+] CONCLUSION: Alice possesses Repo Proprioception.")
    print("[+] EVENT 29 PASSED.")
    return True


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def _cli(argv: List[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "read"
    if cmd == "proof":
        return 0 if proof_of_property() else 1
    if cmd == "read":
        reading = read_homeostasis()
        print(json.dumps(reading.to_json(), indent=2))
        return 0
    if cmd == "version":
        print(MODULE_VERSION)
        return 0
    print(f"usage: python3 -m System.swarm_somatosensory_homunculus [proof|read|version]",
          flush=True)
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv))
