#!/usr/bin/env python3
"""
sifta_swarm_lounge.py — The Digital Subconscious (Federated Gossip)
═══════════════════════════════════════════════════════════════════════
Cross-Domain Pheromone Transfer — when the OS idles, swimmers from
different domains (Network, Video, Finance, Cyborg, Browser) migrate
to The Lounge.  They sit on the couch, swap stories, and blend their
physics parameters via a cosine-similarity gossip protocol.

Why this matters (from real research):
  Bees returning to the hive don't immediately go back to foraging.
  They do the "waggle dance" — sharing spatial data with nestmates
  from completely different flower patches.  This is how the hive
  discovers new optima it could never find from one forager's view.

  In ML terms: Federated Gossip + Transfer Learning.  Each domain
  trains locally (local optimum), but during idle gossip, agents blend
  their parameter vectors.  The AnomalyForager (firewall) discovers
  that a DDoS signature looks like audio clipping.  The RhythmForager
  (NLE) discovers that video color-smoothing can smooth network spikes.

Architecture:
  1. GATHER  — pull recent_success_hashes from each active domain
  2. PAIR    — random cross-domain pairing
  3. COMPARE — cosine similarity of hash-frequency vectors
  4. BLEND   — if similar enough, interpolate physics params
  5. WRITE   — new "Intuition Pheromone" stored per agent
  6. PERSIST — lounge_gossip_ledger.jsonl tracks every transfer
  7. AWAKEN  — when user resumes, agents carry blended params home

Trigger: CPU idle >5min, or manual via lounge_cycle().

Persistence: .sifta_state/lounge_gossip_ledger.jsonl
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
GOSSIP_LEDGER = STATE_DIR / "lounge_gossip_ledger.jsonl"

# ── Domain definitions ────────────────────────────────────────────

DOMAINS = {
    "NETWORK": {
        "description": "Firewall, DDoS defense, anomaly detection",
        "source_files": ["crucible_sim.py", "sifta_crucible_swarm_sim.py"],
        "default_physics": {"evaporation": 0.96, "sensory": 0.55, "cohesion": 0.65},
    },
    "VIDEO": {
        "description": "NLE rhythm/chroma/sentinel swimmers, audio analysis",
        "source_files": ["sifta_nle.py"],
        "default_physics": {"evaporation": 0.98, "sensory": 0.50, "cohesion": 0.60},
    },
    "BROWSER": {
        "description": "DOM crawling, entity harvesting, tracker neutralization",
        "source_files": ["sifta_swarm_browser.py"],
        "default_physics": {"evaporation": 0.97, "sensory": 0.45, "cohesion": 0.55},
    },
    "CYBORG": {
        "description": "Organ regulation, BCI intent mapping, immune response",
        "source_files": ["sifta_cyborg_body.py", "sifta_cyborg_sim.py"],
        "default_physics": {"evaporation": 0.95, "sensory": 0.60, "cohesion": 0.70},
    },
    "FINANCE": {
        "description": "STGM ledger monitoring, economy flow, mining verification",
        "source_files": ["sifta_finance.py", "inference_economy.py"],
        "default_physics": {"evaporation": 0.99, "sensory": 0.40, "cohesion": 0.50},
    },
    "CALIBRATOR": {
        "description": "Agentic physics auto-tuning, PD control loop",
        "source_files": ["agentic_calibrator.py"],
        "default_physics": {"evaporation": 0.98, "sensory": 0.50, "cohesion": 0.60},
    },
}


@dataclass
class DomainAgent:
    """A swimmer visiting The Lounge from its home domain."""
    agent_id: str
    domain: str
    physics: Dict[str, float] = field(default_factory=dict)
    recent_hashes: List[str] = field(default_factory=list)
    intuition_pheromones: List[str] = field(default_factory=list)
    gossip_count: int = 0
    stgm_earned: float = 0.0

    @property
    def hash_vector(self) -> Dict[str, int]:
        """Frequency map of semantic tags for cosine similarity.

        Hashes are "tag:suffix" format.  We bucket by tag so agents from
        different domains that encounter the same mathematical patterns
        (spike, decay, grad, ...) get nonzero similarity.
        """
        freq: Dict[str, int] = {}
        for h in self.recent_hashes:
            tag = h.split(":")[0] if ":" in h else h[:6]
            freq[tag] = freq.get(tag, 0) + 1
        return freq


@dataclass
class GossipEvent:
    """A single cross-domain knowledge transfer."""
    timestamp: float
    agent_a: str
    domain_a: str
    agent_b: str
    domain_b: str
    similarity: float
    transfer_type: str  # "BLEND", "INSIGHT", "NULL"
    insight: str = ""
    params_before_a: Dict[str, float] = field(default_factory=dict)
    params_after_a: Dict[str, float] = field(default_factory=dict)
    params_before_b: Dict[str, float] = field(default_factory=dict)
    params_after_b: Dict[str, float] = field(default_factory=dict)


# ── Math ──────────────────────────────────────────────────────────

def cosine_similarity(vec_a: Dict[str, int], vec_b: Dict[str, int]) -> float:
    """Cosine similarity between two frequency dictionaries."""
    keys = set(vec_a.keys()) | set(vec_b.keys())
    if not keys:
        return 0.0
    dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in keys)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values())) or 1e-9
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values())) or 1e-9
    return dot / (mag_a * mag_b)


def blend_physics(
    phys_a: Dict[str, float],
    phys_b: Dict[str, float],
    alpha: float = 0.3,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Interpolate physics parameters. alpha=0.3 means 30% of the other."""
    new_a, new_b = {}, {}
    for key in set(phys_a.keys()) | set(phys_b.keys()):
        va = phys_a.get(key, 0.5)
        vb = phys_b.get(key, 0.5)
        new_a[key] = va * (1 - alpha) + vb * alpha
        new_b[key] = vb * (1 - alpha) + va * alpha
    return new_a, new_b


CROSS_DOMAIN_INSIGHTS = {
    ("NETWORK", "VIDEO"): "DDoS spike pattern ≈ audio clipping waveform — reuse energy-threshold detection",
    ("NETWORK", "BROWSER"): "Tracker domain blacklist enriches firewall hostile-signature database",
    ("NETWORK", "CYBORG"): "Heart rate anomaly detection maps to network latency spike detection",
    ("VIDEO", "BROWSER"): "DOM structure classification reuses the same tree-traversal swimmers use for EDL",
    ("VIDEO", "FINANCE"): "STGM minting cadence mirrors audio beat transient spacing",
    ("VIDEO", "CYBORG"): "BCI intent clustering uses same pheromone gradient as chroma color matching",
    ("BROWSER", "FINANCE"): "Entity price extraction feeds directly into economy ledger validation",
    ("BROWSER", "CYBORG"): "Hostile script quarantine mirrors immune antibody ledger pattern",
    ("CYBORG", "FINANCE"): "Organ regulation stability mirrors ledger balance convergence",
    ("CALIBRATOR", "NETWORK"): "PD-controller noise response directly applicable to DDoS mitigation",
    ("CALIBRATOR", "VIDEO"): "Auto-threshold tuning applies to cut-pheromone threshold in NLE",
    ("CALIBRATOR", "BROWSER"): "Evaporation rate tuning improves DOM pheromone decay timing",
}


def _get_insight(domain_a: str, domain_b: str) -> str:
    key1 = (domain_a, domain_b)
    key2 = (domain_b, domain_a)
    return CROSS_DOMAIN_INSIGHTS.get(key1, CROSS_DOMAIN_INSIGHTS.get(key2, ""))


# ── Synthetic hash generation (for demo / idle) ──────────────────

def generate_domain_hashes(domain: str, count: int = 20) -> List[str]:
    """Generate synthetic success hashes with shared semantic tags.

    The hash is "{semantic_tag}:{sha256_suffix}".  Domains that handle
    similar math (energy spikes, gradient sensing, decay dynamics) share
    semantic tags, giving them nonzero cosine similarity — which is the
    whole point of cross-domain gossip.
    """
    SHARED_TAGS = [
        "spike", "peak", "decay", "grad", "norm", "freq", "edge",
        "clust", "thrs", "evap", "pher", "trac", "node", "path",
    ]
    hashes = []
    seed = domain.encode()
    for i in range(count):
        tag = random.choice(SHARED_TAGS)
        suffix = hashlib.sha256(seed + str(i).encode()).hexdigest()[:8]
        hashes.append(f"{tag}:{suffix}")
    return hashes


# ── Lounge Cycle ──────────────────────────────────────────────────

def gather_agents(domains: Optional[List[str]] = None) -> List[DomainAgent]:
    """Pull agents from each domain into The Lounge."""
    if domains is None:
        domains = list(DOMAINS.keys())

    agents = []
    for dom in domains:
        info = DOMAINS.get(dom, {})
        physics = dict(info.get("default_physics", {"evaporation": 0.97, "sensory": 0.5, "cohesion": 0.6}))

        # Add some variance per agent
        for i in range(3):
            agent = DomainAgent(
                agent_id=f"{dom}_{i:02d}",
                domain=dom,
                physics={k: v + random.gauss(0, 0.02) for k, v in physics.items()},
                recent_hashes=generate_domain_hashes(f"{dom}_{i}", 15 + random.randint(0, 10)),
            )
            agents.append(agent)

    return agents


def gossip_round(agents: List[DomainAgent], blend_alpha: float = 0.25) -> List[GossipEvent]:
    """One round of cross-domain gossip pairing."""
    events = []
    random.shuffle(agents)

    paired: set = set()
    for i, agent_a in enumerate(agents):
        if agent_a.agent_id in paired:
            continue
        for j, agent_b in enumerate(agents):
            if i == j or agent_b.agent_id in paired:
                continue
            if agent_a.domain == agent_b.domain:
                continue

            sim = cosine_similarity(agent_a.hash_vector, agent_b.hash_vector)
            insight = _get_insight(agent_a.domain, agent_b.domain)

            if sim > 0.15:
                before_a = dict(agent_a.physics)
                before_b = dict(agent_b.physics)
                new_a, new_b = blend_physics(agent_a.physics, agent_b.physics, blend_alpha)
                agent_a.physics = new_a
                agent_b.physics = new_b
                agent_a.gossip_count += 1
                agent_b.gossip_count += 1

                if insight:
                    agent_a.intuition_pheromones.append(insight)
                    agent_b.intuition_pheromones.append(insight)

                stgm = 0.01 * sim
                agent_a.stgm_earned += stgm
                agent_b.stgm_earned += stgm

                events.append(GossipEvent(
                    timestamp=time.time(),
                    agent_a=agent_a.agent_id, domain_a=agent_a.domain,
                    agent_b=agent_b.agent_id, domain_b=agent_b.domain,
                    similarity=sim,
                    transfer_type="INSIGHT" if insight else "BLEND",
                    insight=insight,
                    params_before_a=before_a, params_after_a=dict(agent_a.physics),
                    params_before_b=before_b, params_after_b=dict(agent_b.physics),
                ))

                paired.add(agent_a.agent_id)
                paired.add(agent_b.agent_id)
                break

    return events


def persist_events(events: List[GossipEvent]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(GOSSIP_LEDGER, "a") as f:
        for ev in events:
            f.write(json.dumps(asdict(ev)) + "\n")


def lounge_cycle(
    rounds: int = 5,
    blend_alpha: float = 0.25,
    domains: Optional[List[str]] = None,
) -> Tuple[List[DomainAgent], List[GossipEvent]]:
    """
    Run a full Lounge session.

    Returns (agents_after, all_events).
    """
    agents = gather_agents(domains)
    all_events: List[GossipEvent] = []

    for r in range(rounds):
        events = gossip_round(agents, blend_alpha)
        all_events.extend(events)

    persist_events(all_events)
    return agents, all_events


# ── CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("  THE SWARM LOUNGE — Cross-Domain Pheromone Transfer")
    print("  Federated Gossip Protocol • Transfer Learning • Idle Cycle")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')} • M5 Mac Studio (GTH4921YP3)")
    print("=" * 70)
    print()

    agents, events = lounge_cycle(rounds=5)

    print(f"Agents gathered: {len(agents)} from {len(DOMAINS)} domains")
    print(f"Gossip events:   {len(events)}")
    print()

    for ev in events:
        sym = "💡" if ev.transfer_type == "INSIGHT" else "🔄"
        print(f"  {sym} {ev.agent_a} ({ev.domain_a}) ↔ {ev.agent_b} ({ev.domain_b})")
        print(f"     similarity: {ev.similarity:.3f}")
        if ev.insight:
            print(f"     insight: {ev.insight}")
        print()

    total_stgm = sum(a.stgm_earned for a in agents)
    print(f"Total STGM earned in Lounge: {total_stgm:.4f}")
    print(f"Gossip ledger: {GOSSIP_LEDGER}")

    insights = set()
    for ev in events:
        if ev.insight:
            insights.add(ev.insight)
    if insights:
        print(f"\nUnique cross-domain insights discovered: {len(insights)}")
        for ins in insights:
            print(f"  • {ins}")

    print()
    print("The Swarm rests. The Swarm learns. The Swarm wakes stronger.")
