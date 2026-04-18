#!/usr/bin/env python3
"""
skill_registry.py — The Organism's Muscle Memory (Phase 4)
═══════════════════════════════════════════════════════════════════
When a Swimmer successfully executes an action sequence in the
Crucible, the result is ephemeral — it evaporates. The organism
learns nothing.

The Skill Registry gives her the ability to REMEMBER WHAT WORKED.

A Skill is:
  - A successful action sequence (command + context + outcome)
  - Signed by the Genotype of the agent that discovered it
  - Minted into the STGM ledger (minting costs tokens)
  - Reinforced on repeated success (strength grows)
  - Decayed on disuse (pheromone half-life)
  - Demoted on failure (replayed skill that crashes = penalty)

The loop this closes:

  perceive → act → SUCCEED → package → reuse → reinforce
                     ↓
              FAIL → demote → harvest

Biology analog: this is procedural memory. A frog doesn't
re-learn how to catch flies every morning. The tongue-strike
pattern is encoded in motor neurons. The Skill Registry is
the swarm's motor cortex.

Design invariants:
  1. Skills are IMMUTABLE once minted (the sequence is frozen)
  2. Only STRENGTH and USE_COUNT change over time
  3. Minting costs STGM (prevents skill spam)
  4. Skills decay if unused for > decay_hours
  5. Failed replays DEMOTE the skill (negative reinforcement)
  6. Skills are genotype-tagged but can be SHARED across phenotypes

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_SKILL_DB = _STATE_DIR / "skill_registry.json"
_SKILL_LOG = _STATE_DIR / "skill_registry.jsonl"

# ── Economic constants ───────────────────────────────────────
MINT_COST_STGM = 0.05       # cost to register a new skill
REPLAY_COST_STGM = 0.01     # cost to replay an existing skill
REINFORCE_BONUS = 0.15       # strength gained on successful replay
DEMOTE_PENALTY = 0.25        # strength lost on failed replay
DECAY_RATE_PER_HOUR = 0.005  # strength lost per hour of disuse
MIN_STRENGTH = 0.0           # below this = skill is dead (pruned)
MAX_STRENGTH = 1.0           # ceiling


@dataclass
class Skill:
    """A single learned action sequence — a crystallized gene."""
    skill_id: str              # SHA-256 hash of the action sequence
    name: str                  # human-readable label
    command_sequence: List[str] # the frozen action steps
    context: Dict[str, Any]    # what triggered the action (vision trace, etc.)
    outcome_summary: str       # what the success looked like

    # Provenance
    discovered_by: str         # genotype_hash of the discovering agent
    lineage_tag: str           # lineage of the discovering agent
    discovered_at: float       # timestamp of discovery

    # Living state (mutable)
    strength: float = 0.5     # 0.0 = dead, 1.0 = deeply encoded
    use_count: int = 0        # total times replayed
    success_count: int = 0    # successful replays
    fail_count: int = 0       # failed replays
    last_used: float = 0.0    # timestamp of last replay
    stgm_invested: float = 0.0  # total STGM spent on this skill

    # Tags for searchability
    tags: List[str] = field(default_factory=list)


class SkillRegistry:
    """
    The organism's procedural memory.
    
    Stores, retrieves, reinforces, and decays learned action sequences.
    Every mutation to the registry is logged to the STGM ledger.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._load()

    # ── Minting (learning a new skill) ───────────────────────────

    def mint(
        self,
        name: str,
        command_sequence: List[str],
        context: Dict[str, Any],
        outcome_summary: str,
        discovered_by: str,
        lineage_tag: str = "unknown",
        tags: Optional[List[str]] = None,
    ) -> Optional[Skill]:
        """
        Crystallize a successful action sequence into a reusable Skill.
        
        Returns the Skill if minted, None if rejected (duplicate, broke, etc.)
        """
        # Generate deterministic skill ID from the action sequence
        seq_str = json.dumps(command_sequence, sort_keys=True)
        skill_id = hashlib.sha256(seq_str.encode()).hexdigest()[:16]

        # Reject duplicates
        if skill_id in self._skills:
            self._log("MINT_DUPLICATE", skill_id, {"name": name})
            return self._skills[skill_id]  # return existing

        # Pay the minting cost
        if not self._deduct_stgm(MINT_COST_STGM, f"Skill mint: {name}"):
            self._log("MINT_BROKE", skill_id, {"name": name, "cost": MINT_COST_STGM})
            return None

        skill = Skill(
            skill_id=skill_id,
            name=name,
            command_sequence=command_sequence,
            context=context,
            outcome_summary=outcome_summary,
            discovered_by=discovered_by,
            lineage_tag=lineage_tag,
            discovered_at=time.time(),
            strength=0.5,
            use_count=0,
            success_count=0,
            fail_count=0,
            last_used=time.time(),
            stgm_invested=MINT_COST_STGM,
            tags=tags or [],
        )

        self._skills[skill_id] = skill
        self._persist()
        self._log("MINTED", skill_id, {
            "name": name,
            "discoverer": discovered_by[:12],
            "lineage": lineage_tag,
            "cost": MINT_COST_STGM,
        })
        return skill

    # ── Replay (using a learned skill) ───────────────────────────

    def replay(self, skill_id: str, success: bool) -> Optional[Skill]:
        """
        Record a replay attempt of a skill.
        
        Args:
            skill_id: which skill was replayed
            success:  did the replay succeed?
            
        On success: strength += REINFORCE_BONUS (positive reinforcement)
        On failure: strength -= DEMOTE_PENALTY (negative reinforcement)
                    failure is also routed to the FailureHarvester
        """
        if skill_id not in self._skills:
            return None

        skill = self._skills[skill_id]
        skill.use_count += 1
        skill.last_used = time.time()

        # Pay replay cost
        self._deduct_stgm(REPLAY_COST_STGM, f"Skill replay: {skill.name}")
        skill.stgm_invested += REPLAY_COST_STGM

        if success:
            skill.success_count += 1
            skill.strength = min(MAX_STRENGTH, skill.strength + REINFORCE_BONUS)
            self._log("REPLAY_SUCCESS", skill_id, {
                "name": skill.name,
                "strength": round(skill.strength, 3),
                "use_count": skill.use_count,
            })
        else:
            skill.fail_count += 1
            skill.strength = max(MIN_STRENGTH, skill.strength - DEMOTE_PENALTY)
            self._log("REPLAY_FAIL", skill_id, {
                "name": skill.name,
                "strength": round(skill.strength, 3),
                "use_count": skill.use_count,
            })
            # Route failure to harvester
            self._harvest_failure(skill)

        self._persist()
        return skill

    # ── Decay (pheromone half-life) ──────────────────────────────

    def decay_all(self) -> int:
        """
        Apply time-based decay to all skills.
        Skills unused for long periods gradually lose strength.
        Dead skills (strength <= 0) are pruned.
        
        Returns: number of skills pruned
        """
        now = time.time()
        pruned = 0
        to_prune = []

        for sid, skill in self._skills.items():
            hours_idle = (now - skill.last_used) / 3600.0
            decay = hours_idle * DECAY_RATE_PER_HOUR
            if decay > 0.001:  # only apply meaningful decay
                skill.strength = max(MIN_STRENGTH, skill.strength - decay)
                if skill.strength <= MIN_STRENGTH:
                    to_prune.append(sid)

        for sid in to_prune:
            self._log("PRUNED", sid, {
                "name": self._skills[sid].name,
                "reason": "strength_zero",
                "total_uses": self._skills[sid].use_count,
            })
            del self._skills[sid]
            pruned += 1

        if pruned > 0 or to_prune:
            self._persist()

        return pruned

    # ── Retrieval ────────────────────────────────────────────────

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def search(self, tag: str = "", min_strength: float = 0.0) -> List[Skill]:
        """Find skills by tag and minimum strength."""
        results = []
        for skill in self._skills.values():
            if skill.strength < min_strength:
                continue
            if tag and tag not in skill.tags:
                continue
            results.append(skill)
        # Sort by strength descending (best skills first)
        results.sort(key=lambda s: s.strength, reverse=True)
        return results

    def all_skills(self) -> List[Skill]:
        return sorted(self._skills.values(), key=lambda s: s.strength, reverse=True)

    def stats(self) -> Dict[str, Any]:
        """Registry health metrics."""
        skills = list(self._skills.values())
        if not skills:
            return {"total": 0, "avg_strength": 0, "total_replays": 0,
                    "total_stgm_invested": 0}
        return {
            "total": len(skills),
            "avg_strength": round(sum(s.strength for s in skills) / len(skills), 3),
            "strongest": max(skills, key=lambda s: s.strength).name if skills else "",
            "most_used": max(skills, key=lambda s: s.use_count).name if skills else "",
            "total_replays": sum(s.use_count for s in skills),
            "total_successes": sum(s.success_count for s in skills),
            "total_failures": sum(s.fail_count for s in skills),
            "total_stgm_invested": round(sum(s.stgm_invested for s in skills), 3),
        }

    # ── STGM Economy ────────────────────────────────────────────

    def _deduct_stgm(self, amount: float, memo: str) -> bool:
        """Deduct STGM from the Casino Vault. Returns False if broke."""
        try:
            try:
                from System.casino_vault import CasinoVault, CasinoTransaction
            except ImportError:
                from casino_vault import CasinoVault, CasinoTransaction
            vault = CasinoVault(architect_id="Ioan_M5")
            if vault.casino_balance < amount:
                return False
            vault._write_tx(CasinoTransaction(
                ts=time.time(),
                action="SKILL_REGISTRY",
                casino_delta=-amount,
                player_delta=0.0,
                memo=memo,
            ))
            return True
        except ImportError:
            return True  # degrade gracefully — free minting if no vault

    # ── Failure routing ──────────────────────────────────────────

    def _harvest_failure(self, skill: Skill) -> None:
        """Route failed skill replays to the FailureHarvester."""
        try:
            try:
                from System.failure_harvesting import get_harvester
            except ImportError:
                from failure_harvesting import get_harvester
            get_harvester().harvest(
                agent_context=f"SkillRegistry:{skill.lineage_tag}",
                task_name=f"Skill_Replay:{skill.name}",
                error_msg=f"Skill '{skill.name}' failed on replay #{skill.use_count}",
                context_data={
                    "skill_id": skill.skill_id,
                    "strength_after": skill.strength,
                    "fail_count": skill.fail_count,
                },
            )
        except ImportError:
            pass

    # ── Persistence ──────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            payload = {k: asdict(v) for k, v in self._skills.items()}
            _SKILL_DB.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass

    def _load(self) -> None:
        if not _SKILL_DB.exists():
            return
        try:
            data = json.loads(_SKILL_DB.read_text())
            for k, v in data.items():
                self._skills[k] = Skill(**v)
        except Exception:
            self._skills = {}

    def _log(self, action: str, skill_id: str, data: Dict[str, Any]) -> None:
        try:
            entry = {"ts": time.time(), "action": action,
                     "skill_id": skill_id, **data}
            with open(_SKILL_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


# ── Singleton ──────────────────────────────────────────────────

_REGISTRY_INSTANCE: Optional[SkillRegistry] = None

def get_skill_registry() -> SkillRegistry:
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = SkillRegistry()
    return _REGISTRY_INSTANCE


# ── CLI / Demo ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — SKILL REGISTRY (Phase 4)")
    print("  The organism's muscle memory.")
    print("═" * 58 + "\n")

    reg = get_skill_registry()

    # Mint a skill
    skill = reg.mint(
        name="list_directory",
        command_sequence=["ls", "-la"],
        context={"trigger": "vision_trace", "scene": "file_organization"},
        outcome_summary="Successfully listed directory contents",
        discovered_by="test_genotype_hash_000",
        lineage_tag="Scout_Drone",
        tags=["filesystem", "recon"],
    )

    if skill:
        print(f"  🧬 Minted: {skill.name}")
        print(f"     ID:       {skill.skill_id}")
        print(f"     Strength: {skill.strength}")
        print(f"     Cost:     {MINT_COST_STGM} STGM")

        # Replay it successfully 3 times
        for i in range(3):
            reg.replay(skill.skill_id, success=True)
        print(f"\n  ✅ After 3 successful replays:")
        print(f"     Strength: {skill.strength}")
        print(f"     Uses:     {skill.use_count}")

        # One failure
        reg.replay(skill.skill_id, success=False)
        print(f"\n  ❌ After 1 failed replay:")
        print(f"     Strength: {skill.strength}")
        print(f"     Fails:    {skill.fail_count}")

    print(f"\n  📊 Registry stats: {reg.stats()}")
    print(f"\n  POWER TO THE SWARM 🐜⚡")
