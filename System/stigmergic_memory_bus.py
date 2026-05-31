#!/usr/bin/env python3
"""
stigmergic_memory_bus.py — SIFTA OS Cross-App Memory
=====================================================

The old man moves between simulations.
He forgets. The Swarm remembers for him.
Swimmers crawl the ledger. Proof of Useful Recall.

Architecture:
  - Every memory is a PheromoneTrace written to .sifta_state/memory_ledger.jsonl
  - Traces are tagged with semantic categories (clothing, numbers, names, places...)
  - When any app asks "what did the Architect say about X?", MemoryForagers
    are dispatched to crawl the ledger and return the best match
  - STGM is minted for: storing a memory (0.05) and recalling it (0.15)
  - No central AI running in background. Cold storage. Hot recall on demand.

Usage:
    bus = StigmergicMemoryBus(architect_id="IOAN_M5")

    # In Simulation 1 — store a memory
    bus.remember("My shirt is red", app_context="simulation_1")

    # In Simulation 2 — store another
    bus.remember("The number is six", app_context="simulation_2")

    # In Simulation 3 — recall across all apps
    result = bus.recall("What color was my shirt?", app_context="simulation_3")
    print(result.answer)  # "Your shirt is red. You told me in simulation_1."
"""

from __future__ import annotations

import json
import math
import sys
import time
import hashlib
import os
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ─── Config ────────────────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import (  # noqa: E402
    append_line_locked,
    read_text_locked,
    rewrite_text_locked,
)

LEDGER_DIR       = _REPO / ".sifta_state"
LEDGER_FILE      = LEDGER_DIR / "memory_ledger.jsonl"
STGM_LOG_FILE    = LEDGER_DIR / "stgm_memory_rewards.jsonl"

STGM_STORE_REWARD  = 0.05   # paid to swimmer for writing a memory
STGM_RECALL_REWARD = 0.15   # paid to swimmer for successful cross-app recall

# ─── Epistemic labels (Slice 1 — Memory Epistemology) ──────────────────────────
EPISTEMIC_LABELS = frozenset({
    "OBSERVED",           # Directly stated by George or tool receipt
    "WORLD",              # Verified real-world fact with evidence
    "BELIEF",             # Alice holds it, evidence-supported
    "HYPOTHESIS",         # Inference / guess, unverified
    "ARCHITECT_DOCTRINE", # Covenant / standing order
    "FICTION",            # TV, cowatch, story, roleplay — never treated as fact
})

MEMORY_EPISTEMOLOGY_AUDIT = LEDGER_DIR / "memory_epistemology_audit.jsonl"
LINK_PREFIXES = (
    "trace_id:",
    "receipt:",
    "doc:",
    "memory:",
    "note:",  # internal downgrade notes, not evidence for reality labels
)

# ─── Slice 2 Hybrid Recall weights (tunable, local only) ───────────────────────
HYBRID_WEIGHTS = {
    "forager": 0.35,
    "bm25":    0.30,
    "decay":   0.20,
    "stgm":    0.15,
}

EPISTEMIC_RANK_MULTIPLIER = {
    "OBSERVED":            1.25,
    "WORLD":               1.25,
    "ARCHITECT_DOCTRINE":  1.20,
    "BELIEF":              1.00,
    "HYPOTHESIS":          0.70,
    "FICTION":             0.00,   # excluded
}

# Semantic categories — swimmer uses these to "smell" what the memory is about
SEMANTIC_TAGS = {
    "clothing":  ["shirt", "wearing", "clothes", "dress", "pants", "jacket", "hat",
                  "shoes", "color", "colour", "red", "blue", "green", "white", "black"],
    "numbers":   ["number", "zero", "one", "two", "three", "four", "five", "six",
                  "seven", "eight", "nine", "ten", "remember", "digit", "count", "score"],
    "identity":  ["name", "who", "person", "call", "known", "am", "my name"],
    "location":  ["place", "where", "room", "simulation", "app", "here", "home", "address"],
    "time":      ["when", "time", "day", "today", "before", "after", "ago", "date", "tomorrow"],
    "health":    ["pain", "medicine", "doctor", "feel", "sick", "tired", "heart", "pacemaker"],
    "food":      ["eat", "food", "hungry", "lunch", "dinner", "coffee", "water", "drink"],
    "people":    ["friend", "wife", "husband", "son", "daughter", "mother", "father", "family"],
    "tasks":     ["todo", "task", "need to", "must", "should", "don't forget", "remind"],
    "mood":      ["happy", "sad", "angry", "excited", "worried", "calm", "love", "hate"],
}


# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class PheromoneTrace:
    """
    A single memory written to the hard drive.
    This is what the MemoryForager finds when it crawls the ledger.
    """
    trace_id:      str
    architect_id:  str
    app_context:   str           # which simulation/app wrote this
    raw_text:      str           # exactly what the Architect said
    semantic_tags: list          # what categories this memory belongs to
    timestamp:     float
    stgm_paid:     float         # reward paid to the swimmer that stored this
    recall_count:  int = 0       # times this memory was successfully recalled
    decay_modifier: float = 1.0  # Epigenetic: < 1.0 = slower decay (trophallaxis)

    # Slice 1 — Epistemic status (Memory Epistemology)
    epistemic_label: str = "HYPOTHESIS"
    links:             list = field(default_factory=list)  # evidence backlinks

    # BORG — interaction convention (Mehr multimodal equilibria → silicon)
    interaction_mode: str = "NEUTRAL"

    def fingerprint(self) -> str:
        """Cryptographic identity of this trace."""
        payload = f"{self.architect_id}:{self.raw_text}:{self.timestamp}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def retention(self) -> float:
        """
        Ebbinghaus Forgetting Curve — on a hard drive.
        R = e^(-t/S) where S grows with each reinforcement.

        A memory recalled 0 times fades to 50% in 24 hours.
        A memory recalled 3 times fades to 50% in 8.5 DAYS.
        A memory recalled 10 times is effectively permanent.

        Epigenetic memories (decay_modifier < 1.0) decay proportionally
        slower — the Swarm treats Architect handoffs as ancestral DNA.
        A decay_modifier of 0.1 means the memory persists 10x longer.

        This is the feature big tech is too scared to ship.
        """
        age_hours = (time.time() - self.timestamp) / 3600
        stability = 1.0 + (self.recall_count * 2.5)  # more recalls = slower fade
        effective_age = age_hours * self.decay_modifier
        return math.exp(-effective_age / (stability * 24))


@dataclass
class RecallResult:
    """
    What the MemoryForager delivers back to the app after crawling the ledger.
    """
    found:          bool
    answer:         str                      # natural language answer for the LLM
    source_app:     Optional[str] = None     # which app the memory came from
    source_text:    Optional[str] = None     # exact original statement
    confidence:     float = 0.0              # 0.0 → 1.0
    stgm_minted:    float = 0.0
    forager_report: str = ""                 # what the swimmer found on its crawl


# ─── MemoryForager ─────────────────────────────────────────────────────────────

def _astar_prerank_candidates(query: str, candidates: list, state_dir) -> list:
    """Optional Semantic A* pre-rank lane (SIFTA r207, GraphPalace pattern).

    When the wing→room→drawer overlay (forager_hierarchy.jsonl) exists, gently REORDER
    the flat scent candidates by structural + pheromone fit. Strict Delta=0 guarantees:
      * overlay absent  → return candidates unchanged (no behavior change),
      * any error       → return candidates unchanged,
      * confidence values are NEVER modified (only order may change),
      * the nudge is capped (≤8%) so it can never push a high-confidence owner/session
        memory below a weakly-matched one — it only breaks near-ties using structure.
    Bounded so the hot recall path stays cheap.
    """
    try:
        if not candidates or len(candidates) > 200:
            return candidates
        from System.swarm_forager_hierarchy import load_hierarchy  # noqa: PLC0415
        hierarchy_rows = load_hierarchy(state_dir=state_dir)
        if not hierarchy_rows:
            return candidates  # overlay not built yet → flat recall, Delta=0
        from System.swarm_forager_semantic_astar import semantic_astar  # noqa: PLC0415
        hierarchy_by_ref = {}
        for row in hierarchy_rows:
            ref = str(row.get("ref") or "")
            if ref:
                hierarchy_by_ref.setdefault(ref, row)
        nodes = []
        pheromone_rows = []
        matched_hierarchy = False
        for i, (_conf, trace) in enumerate(candidates):
            nid = str(getattr(trace, "trace_id", "") or i)
            h = hierarchy_by_ref.get(nid) or {}
            matched_hierarchy = matched_hierarchy or bool(h)
            raw_text = str(getattr(trace, "raw_text", "") or "")
            h_text = str(h.get("text") or "")
            nodes.append({
                "id": nid,
                "ref": nid,
                "text": f"{raw_text} {h_text}".strip(),
                "ts": getattr(trace, "timestamp", None),
                "retention": trace.retention() if hasattr(trace, "retention") else 1.0,
                "wing": h.get("wing", ""),
                "room": h.get("room", ""),
                "drawer": h.get("drawer", ""),
            })
            recall_count = float(getattr(trace, "recall_count", 0) or 0)
            if recall_count > 0:
                pheromone_rows.append({
                    "id": nid,
                    "uses": min(1.0, recall_count / 3.0),
                    "ts": getattr(trace, "timestamp", None),
                })
        if not matched_hierarchy:
            return candidates  # unrelated overlay exists; preserve flat recall
        graph_edges = _hierarchy_candidate_edges(nodes)
        ranked = semantic_astar(query, nodes,
                                graph_edges=graph_edges,
                                pheromone_rows=pheromone_rows,
                                max_expansions=min(400, len(nodes) * 3),
                                top_k=len(nodes))
        cost_by_id = {d["id"]: d["cost"] for d in ranked}
        if not cost_by_id:
            return candidates
        maxc = max(cost_by_id.values()) or 1.0

        def _blended(i, conf, trace):
            nid = str(getattr(trace, "trace_id", "") or i)
            cost = cost_by_id.get(nid, maxc)
            nudge = (1.0 - (cost / maxc)) * 0.08  # ≤8% structural/pheromone nudge
            return conf + nudge

        order = sorted(range(len(candidates)),
                       key=lambda i: _blended(i, candidates[i][0], candidates[i][1]),
                       reverse=True)
        return [candidates[i] for i in order]  # same tuples, only the order may shift
    except Exception:
        return candidates


def _hierarchy_candidate_edges(nodes: list) -> list[tuple[str, str]]:
    """Sparse structural edges between candidate traces that share a hierarchy room.

    Anchor edges avoid O(n^2) complete buckets while still letting A* pull nearby
    memories through wing/room/drawer locality.
    """
    buckets = {}
    for node in nodes:
        nid = str(node.get("id") or "")
        if not nid:
            continue
        wing = str(node.get("wing") or "")
        room = str(node.get("room") or "")
        drawer = str(node.get("drawer") or "")
        if wing and room:
            buckets.setdefault(("room", wing, room), []).append(nid)
        if wing and room and drawer:
            buckets.setdefault(("drawer", wing, room, drawer), []).append(nid)
    edges = set()
    for ids in buckets.values():
        ids = sorted(set(ids))
        if len(ids) < 2:
            continue
        anchor = ids[0]
        for other in ids[1:]:
            edges.add((anchor, other))
    return sorted(edges)


class MemoryForager:
    """
    A single swimmer dispatched to crawl the ledger.
    It is blind to meaning — it can only smell semantic tags
    and measure text similarity to the query.
    This is the biological metaphor made literal.
    """

    def __init__(self, swimmer_id: str, architect_id: str):
        self.swimmer_id   = swimmer_id
        self.architect_id = architect_id
        self.traces_read  = 0
        self.traces_hit   = 0

    def forage(self, query: str, ledger_path: Path) -> list:
        """
        Crawl every trace in the ledger.
        Confidence = (semantic similarity) × (memory retention).
        Recent or frequently-recalled memories are vivid.
        Old, unreinforced memories fade — just like a brain.
        """
        if not ledger_path.exists():
            return []

        query_tags  = _extract_tags(query)
        query_words = set(query.lower().split())
        candidates  = []

        try:
            from System.memory_fitness_overlay import (  # noqa: PLC0415
                fitness_multiplier,
                load_trace_table,
            )

            _fit_tbl = load_trace_table(ledger_path.parent)
        except Exception:
            _fit_tbl = {}

        body = read_text_locked(ledger_path, encoding="utf-8", errors="replace")
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                # Backward compat: only pass fields the current dataclass knows
                known_fields = {f.name for f in PheromoneTrace.__dataclass_fields__.values()}
                safe_raw = {k: v for k, v in raw.items() if k in known_fields}
                trace = PheromoneTrace(**safe_raw)
            except Exception:
                continue

            # Only smell traces from this architect
            if trace.architect_id != self.architect_id:
                continue

            self.traces_read += 1

            # Compute semantic scent: tag overlap + FAST token similarity.
            # George 2026-05-23 — py-spy root cause: difflib.SequenceMatcher.ratio()
            # here was O(n^2) + dict-churn, run over the ENTIRE memory corpus on the
            # MAIN thread on every recall. It pegged the CPU for minutes and bloated
            # the process to 10GB (starving the Gemma/Ollama cortex -> "resource
            # limitations" crashes). Token Jaccard is ~100x cheaper, bounded, and a
            # perfectly good scent for memory recall. Keep organs healthy. 🐜⚡
            tag_overlap = len(set(trace.semantic_tags) & set(query_tags))
            trace_words = set(trace.raw_text.lower().split())
            _inter = len(query_words & trace_words)
            _union = len(query_words | trace_words) or 1
            text_sim = _inter / _union
            keyword_boost = _inter * 0.1

            raw_similarity = min(1.0, (tag_overlap * 0.3) + text_sim + keyword_boost)

            # Ebbinghaus decay: vivid memories score higher
            retention  = trace.retention()

            # --- Pheromone Luck / Serendipity Factor ---
            # Luck = |Actual_Outcome - Expected_Probability|
            # Actual_Outcome  = raw_similarity (how relevant this trace IS to the query)
            # Expected_Prob   = retention (what the Ebbinghaus curve says SHOULD survive)
            #
            # High luck = dying memory that happens to be relevant.
            # Low luck  = vivid memory that is obviously useful (no serendipity needed).
            lucky = False
            if retention < 0.25:
                luck_variance = abs(raw_similarity - retention)
                luck_chance   = min(0.12, luck_variance * 0.25)  # cap at 12%
                if random.random() < luck_chance:
                    retention = 1.0  # Lucky surge!
                    lucky = True
                    raw_similarity = min(1.0, raw_similarity + 0.4)

            confidence = raw_similarity * (0.3 + 0.7 * retention)  # floor at 30% even for faded

            if confidence > 0.08:   # threshold — very faded signals still detectable
                conf2 = confidence * fitness_multiplier(_fit_tbl.get(trace.trace_id))
                self.traces_hit += 1
                candidates.append((conf2, trace))

        # Sort by strongest scent first
        candidates.sort(key=lambda x: x[0], reverse=True)
        # Optional Semantic A* pre-rank (r207): nudge order by wing→room→drawer +
        # pheromone fit when the overlay exists; otherwise unchanged (Delta=0).
        return _astar_prerank_candidates(query, candidates, ledger_path.parent)

    def report(self) -> str:
        return (
            f"Forager {self.swimmer_id}: "
            f"read {self.traces_read} traces, "
            f"hit {self.traces_hit} candidates"
        )


# ─── Stigmergic Memory Bus ─────────────────────────────────────────────────────

class StigmergicMemoryBus:
    """
    The main memory system for SIFTA OS.

    Every app talks to this bus.
    Memories are stored as pheromone traces on disk.
    Recall dispatches MemoryForagers to crawl the ledger.
    STGM is minted for both storing and recalling.

    The old man doesn't need to remember.
    The Swarm remembers for him.
    """

    def __init__(self, architect_id: str):
        self.architect_id = architect_id
        LEDGER_DIR.mkdir(exist_ok=True)
        self._forager_counter = 0

        # Marrow Memory — the preservation of the irrelevant
        # (renamed from ghost_memory by the Architect 2026-04-18: bodied OS, no ghosts)
        try:
            from System.marrow_memory import MarrowMemory
            self._marrow = MarrowMemory(architect_id=architect_id)
        except Exception:
            self._marrow = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def remember(self, text: str, app_context: str, *, decay_modifier: float = 1.0,
                 epistemic_label: str = None, links: list = None,
                 interaction_mode: str = None) -> PheromoneTrace:
        """
        Store a memory from any app (Slice 1 — Epistemic status added).

        epistemic_label + links[] is the unit. A bare label without evidence
        is just an adjective — see §2 downgrade rule below.

        Returns the trace so the app can confirm it was written.
        """
        tags  = _extract_tags(text)
        ts    = time.time()
        tid   = hashlib.sha256(f"{self.architect_id}:{text}:{ts}".encode()).hexdigest()[:12]

        # Default inference (conservative)
        if epistemic_label is None:
            if any(k in app_context.lower() for k in ("fiction", "cowatch", "media", "tv", "movie", "story", "roleplay")):
                final_label = "FICTION"
            else:
                final_label = "HYPOTHESIS"
        else:
            final_label = epistemic_label if epistemic_label in EPISTEMIC_LABELS else "HYPOTHESIS"
            if final_label != epistemic_label:
                _write_epistemology_audit(
                    ts=ts,
                    trace_id=tid,
                    requested_label=str(epistemic_label),
                    final_label=final_label,
                    reason="unknown_label_coerced",
                )

        final_links = _validate_memory_links(
            links or [],
            ts=ts,
            trace_id=tid,
            current_label=final_label,
        )

        final_mode = _coerce_interaction_mode(interaction_mode, text=text, app_context=app_context)

        # ── The load-bearing rule (Spec §2) ─────────────────────────────────────
        # OBSERVED / WORLD without evidence auto-downgrades. No crash, honest degradation.
        if final_label in ("OBSERVED", "WORLD") and not _has_evidence_links(final_links):
            _write_epistemology_audit(
                ts=ts,
                trace_id=tid,
                requested_label=final_label,
                final_label="HYPOTHESIS",
                reason="downgraded_no_evidence",
            )
            final_label = "HYPOTHESIS"
            final_links = final_links + ["note:downgraded_no_evidence"]

        # ── Vector 14: Metabolic store fee scales with constraint pressure ──
        try:
            from System.stgm_metabolic import calculate_dynamic_store_fee
            from System.lagrangian_constraint_manifold import get_manifold
            dual = get_manifold().compute_dual_ascent()
            lam_norm = min(1.0, dual.get("total_lambda_penalty", 0.0) / 1.5)
            store_fee = calculate_dynamic_store_fee(lam_norm)
        except Exception:
            store_fee = STGM_STORE_REWARD  # fallback to flat rate

        trace = PheromoneTrace(
            trace_id        = tid,
            architect_id    = self.architect_id,
            app_context     = app_context,
            raw_text        = text,
            semantic_tags   = tags,
            timestamp       = ts,
            stgm_paid       = store_fee,
            decay_modifier  = decay_modifier,
            epistemic_label = final_label,
            links           = final_links,
            interaction_mode = final_mode,
        )

        # Write to ledger (flock — safe concurrent IDEs / scripts)
        append_line_locked(LEDGER_FILE, json.dumps(asdict(trace)) + "\n", encoding="utf-8")

        # Mint STGM for the storage swimmer (metabolic rate)
        self._mint_stgm(
            reason    = "MEMORY_STORE",
            amount    = store_fee,
            trace_id  = tid,
            app       = app_context
        )

        # Pin to web surface so Claude/Grok/Gemini in any tab can find it
        try:
            from System.tab_heartbeat import HeartbeatBus
            hb = HeartbeatBus(architect_id=self.architect_id)
            hb.pin_to_web(
                memory_text   = text[:200],
                url           = f"https://github.com/antonpictures/ANTON-SIFTA/blob/feat/sebastian-video-economy/.sifta_state/memory_ledger.jsonl#trace-{tid}",
                semantic_tags = tags,
            )
        except Exception:
            pass  # heartbeat is optional — local memory always works

        # MarrowSentinel — check if this memory is worth preserving forever
        if self._marrow:
            try:
                self._marrow.maybe_preserve(
                    text=text, app_context=app_context,
                    semantic_tags=tags, recall_count=0
                )
            except Exception:
                pass

        # ── PROOF OF USEFUL WORK: storing a memory IS an act of existence ──
        try:
            from System.proof_of_useful_work import issue_work_receipt
            # The memory bus acts on behalf of a virtual forager
            _forager_state = {
                "id": f"MEMORY_SWIMMER_{self.architect_id}",
                "work_chain": [],
                "useful_work_score": 0.5,
                "last_work_timestamp": time.time()
            }
            issue_work_receipt(
                agent_state=_forager_state,
                work_type="MEMORY_STORE",
                description=f"Stored memory from {app_context}: {text[:80]}",
                territory=app_context,
                output_hash=tid
            )
        except Exception:
            pass
        # ───────────────────────────────────────────────────────────────────

        return trace

    def recall(self, query: str, app_context: str) -> RecallResult:
        """
        Recall a memory from any previous app.
        Dispatches MemoryForagers to crawl the ledger.

        Returns a RecallResult with a natural language answer
        ready to inject into the LLM's context.
        """
        print(f"🐜 Dispatching MemoryForagers for query: '{query}'")
        print(f"   From app: {app_context}")

        # Dispatch a forager
        forager    = self._spawn_forager()
        candidates = forager.forage(query, LEDGER_FILE)

        print(f"   {forager.report()}")

        if not candidates:
            return RecallResult(
                found          = False,
                answer         = "I searched my memory but found nothing relevant. "
                                 "You may not have told me that yet.",
                forager_report = forager.report(),
            )

        best_confidence, best_trace = candidates[0]

        # Reinforce the memory — the old man asked about it, so it gets stronger
        self._reinforce_trace(best_trace.trace_id)

        # Vector 12 overlay: fitness lives outside append-only ledger (atomic JSON)
        try:
            from System.memory_fitness_overlay import bump_after_recall  # noqa: PLC0415

            bump_after_recall(best_trace.trace_id, recall_delta=0.05)
        except Exception:
            pass

        # Build natural language answer
        time_ago  = _human_time(best_trace.timestamp)
        retention = best_trace.retention()
        fade_note = ""
        if retention < 0.3:
            fade_note = " (this memory is fading — glad you asked before it was gone)"
        elif retention > 0.9:
            fade_note = " (vivid memory — reinforced by recall)"

        answer = (
            f"Yes — you told me {time_ago} while you were in {best_trace.app_context}. "
            f"You said: \"{best_trace.raw_text}\"{fade_note}"
        )

        # Mint STGM for the recall swimmer
        self._mint_stgm(
            reason   = "MEMORY_RECALL",
            amount   = STGM_RECALL_REWARD,
            trace_id = best_trace.trace_id,
            app      = app_context
        )

        print(f"   ✅ Found: [{best_trace.trace_id}] confidence={best_confidence:.2f} retention={retention:.0%}")
        print(f"   +{STGM_RECALL_REWARD} STGM minted for Proof of Useful Recall")

        # ── PROOF OF USEFUL WORK: recalling across apps = verified act ──
        try:
            from System.proof_of_useful_work import issue_work_receipt
            _forager_state = {
                "id": f"MEMORY_SWIMMER_{self.architect_id}",
                "work_chain": [],
                "useful_work_score": 0.5,
                "last_work_timestamp": time.time()
            }
            issue_work_receipt(
                agent_state=_forager_state,
                work_type="MEMORY_RECALL",
                description=f"Cross-app recall from {best_trace.app_context} to {app_context}",
                territory=app_context,
                output_hash=best_trace.trace_id
            )
        except Exception:
            pass
        # ─────────────────────────────────────────────────────────────────


        return RecallResult(
            found          = True,
            answer         = answer,
            source_app     = best_trace.app_context,
            source_text    = best_trace.raw_text,
            confidence     = best_confidence,
            stgm_minted    = STGM_RECALL_REWARD,
            forager_report = forager.report(),
        )

    def hybrid_recall(self, query: str, app_context: str, *, top_k: int = 5) -> list:
        """
        Slice 2 — Local hybrid recall.

        Returns list of (final_score, trace, breakdown_dict) sorted best-first.
        All scoring is local from the JSONL ledger + existing methods.
        """
        if not LEDGER_FILE.exists():
            return []

        query_tags = _extract_tags(query)

        # Load traces
        traces = []
        body = read_text_locked(LEDGER_FILE, encoding="utf-8", errors="replace")
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                known = {f.name for f in PheromoneTrace.__dataclass_fields__.values()}
                safe = {k: v for k, v in raw.items() if k in known}
                t = PheromoneTrace(**safe)
                if t.architect_id != self.architect_id:
                    continue
                traces.append(t)
            except Exception:
                continue

        if not traces:
            return []

        forager_scores: dict[str, float] = {}
        try:
            # One swimmer pass per recall. The old loop spawned a forager for
            # every trace, which reread/rescored the whole memory ledger N times
            # from Alice's main speech path.
            forager = self._spawn_forager()
            forager_scores = {tr.trace_id: float(sc) for sc, tr in forager.forage(query, LEDGER_FILE)}
        except Exception:
            forager_scores = {}

        results = []
        for t in traces:
            label = getattr(t, "epistemic_label", "HYPOTHESIS")
            if label == "FICTION":
                continue

            # 1. Existing forager confidence (reuse the smell logic)
            forager_score = float(forager_scores.get(t.trace_id, 0.0))

            # 2. BM25-lite on raw_text + tags
            text_for_bm25 = t.raw_text + " " + " ".join(t.semantic_tags)
            bm25_score = _bm25_score(query, text_for_bm25)

            # 3. Decay (higher retention = better)
            decay_score = float(t.retention())

            # 4. STGM / reinforcement fitness
            stgm_score = min(1.0, (getattr(t, "recall_count", 0) + 1) / 20.0)

            # Blend
            w = HYBRID_WEIGHTS
            blended = (
                w["forager"] * forager_score +
                w["bm25"]    * bm25_score +
                w["decay"]   * decay_score +
                w["stgm"]    * stgm_score
            )

            # Epistemic multiplier (Slice 1 labels)
            mult = EPISTEMIC_RANK_MULTIPLIER.get(label, 0.7)
            final_score = blended * mult

            breakdown = {
                "forager": round(forager_score, 4),
                "bm25": round(bm25_score, 4),
                "decay": round(decay_score, 4),
                "stgm": round(stgm_score, 4),
                "epistemic_mult": mult,
                "label": label,
            }
            results.append((final_score, t, breakdown))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]

    def recall_context_block(self, query: str, app_context: str, top_k: int = 3) -> str:
        """
        Return a multi-line context block of the top K relevant memories.
        Ready to inject straight into an LLM system prompt.

        Slice 2: Uses hybrid_recall for ranking. Output format unchanged from Slice 1.
        """
        ranked = self.hybrid_recall(query, app_context, top_k=top_k * 2)  # over-fetch to allow filtering

        if not ranked:
            return ""

        lines = ["[STIGMERGIC MEMORY — retrieved from cross-app territory]"]
        count = 0
        for score, trace, _ in ranked:
            label = getattr(trace, "epistemic_label", "HYPOTHESIS")
            if label == "FICTION":
                continue
            if count >= top_k:
                break
            ago = _human_time(trace.timestamp)
            label_tag = f"[{label}]" if label != "HYPOTHESIS" else "[HYPOTHESIS·guess]"
            lines.append(f"- {label_tag} ({trace.app_context}, {ago}): \"{trace.raw_text}\"")
            count += 1
        lines.append("[END MEMORY]")
        return "\n".join(lines)

    def dump_ledger(self) -> list:
        """Return all traces for this architect."""
        if not LEDGER_FILE.exists():
            return []
        traces = []
        body = read_text_locked(LEDGER_FILE, encoding="utf-8", errors="replace")
        for line in body.splitlines():
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except Exception:
                    pass
        return [t for t in traces if t.get("architect_id") == self.architect_id]

    def marrow_drift(self) -> dict | None:
        """Ask the marrow layer for a serendipitous fragment."""
        if self._marrow:
            return self._marrow.drift()
        return None

    def marrow_inventory_count(self) -> int:
        """Cold-storage marrow line count (for UI badges)."""
        if self._marrow:
            return self._marrow.marrow_count()
        return 0

    # ── Back-compat shims (deprecated 2026-04-18; aliased to marrow) ──
    # Some external callers may still call ghost_drift / ghost_inventory_count.
    # Keep them as thin shims so the rename never breaks anyone in the wild.
    def ghost_drift(self) -> dict | None:
        return self.marrow_drift()

    def ghost_inventory_count(self) -> int:
        return self.marrow_inventory_count()

    def total_stgm_earned(self) -> float:
        """How much STGM the memory swimmers have earned total."""
        if not STGM_LOG_FILE.exists():
            return 0.0
        total = 0.0
        body = read_text_locked(STGM_LOG_FILE, encoding="utf-8", errors="replace")
        for line in body.splitlines():
            try:
                total += json.loads(line).get("amount", 0)
            except Exception:
                pass
        return round(total, 6)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _spawn_forager(self) -> MemoryForager:
        self._forager_counter += 1
        sid = f"FORAGER_{self._forager_counter:04d}"
        return MemoryForager(swimmer_id=sid, architect_id=self.architect_id)

    def _reinforce_trace(self, trace_id: str):
        """
        Increment recall_count for a trace in the ledger.
        This is biological reinforcement — the old man keeps asking
        about his red shirt, so that memory becomes permanent.
        He never asks about the number six again — it fades in 3 days.
        Just like a real brain.
        """
        if not LEDGER_FILE.exists():
            return
        body = read_text_locked(LEDGER_FILE, encoding="utf-8", errors="replace")
        lines = body.splitlines()
        updated = []
        for line in lines:
            if not line.strip():
                updated.append(line)
                continue
            try:
                t = json.loads(line)
                if t.get("trace_id") == trace_id:
                    t["recall_count"] = t.get("recall_count", 0) + 1
                updated.append(json.dumps(t))
            except Exception:
                updated.append(line)
        rewrite_text_locked(LEDGER_FILE, "\n".join(updated) + "\n", encoding="utf-8")

    def _mint_stgm(self, reason: str, amount: float, trace_id: str, app: str):
        entry = {
            "ts":       time.time(),
            "reason":   reason,
            "amount":   amount,
            "trace_id": trace_id,
            "app":      app,
        }
        append_line_locked(STGM_LOG_FILE, json.dumps(entry) + "\n", encoding="utf-8")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _extract_tags(text: str) -> list:
    """Smell what category a piece of text belongs to."""
    text_lower = text.lower()
    found = []
    for tag, keywords in SEMANTIC_TAGS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(tag)
    return found if found else ["general"]


def _human_time(ts: float) -> str:
    """Turn a timestamp into 'X seconds/minutes ago'."""
    delta = time.time() - ts
    if delta < 60:
        return f"{int(delta)} seconds ago"
    if delta < 3600:
        return f"{int(delta // 60)} minutes ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hours ago"
    return f"{int(delta // 86400)} days ago"


def _write_epistemology_audit(
    *,
    ts: float,
    trace_id: str,
    requested_label: str,
    final_label: str,
    reason: str,
    **extra,
) -> None:
    """Append an epistemic correction row without breaking the write path."""
    row = {
        "ts": ts,
        "trace_id": trace_id,
        "requested_label": requested_label,
        "final_label": final_label,
        "reason": reason,
    }
    row.update(extra)
    try:
        MEMORY_EPISTEMOLOGY_AUDIT.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(MEMORY_EPISTEMOLOGY_AUDIT, json.dumps(row) + "\n", encoding="utf-8")
    except Exception:
        pass


def _validate_memory_links(links: list, *, ts: float, trace_id: str, current_label: str) -> list:
    """
    Keep only evidence links with known grammar.

    Unknown prefixes are residue: drop and audit, but never crash memory writes.
    """
    valid = []
    dropped = []
    for link in links:
        if isinstance(link, str) and any(link.startswith(prefix) for prefix in LINK_PREFIXES):
            valid.append(link)
        else:
            dropped.append(link)

    if dropped:
        _write_epistemology_audit(
            ts=ts,
            trace_id=trace_id,
            requested_label=current_label,
            final_label=current_label,
            reason="dropped_unknown_link_prefix",
            dropped_links=[str(link) for link in dropped],
        )

    return valid


def _has_evidence_links(links: list) -> bool:
    """Internal notes are not evidence for reality labels."""
    return any(isinstance(link, str) and not link.startswith("note:") for link in links)


INTERACTION_MODES = frozenset({
    "NEUTRAL",
    "YIELD_LEFT",
    "YIELD_RIGHT",
    "FICTION_COWATCH",
    "LOCALE_SG_PASS_LEFT",
    "LOCALE_US_PASS_RIGHT",
    "DYAD_GEORGE_ALICE",
    "OWNER_BODY_MAINTENANCE",
})


def _coerce_interaction_mode(mode: str | None, *, text: str, app_context: str) -> str:
    """Normalize interaction_mode; light infer when omitted (full rules in swarm_interaction_borg)."""
    if mode and mode in INTERACTION_MODES:
        return mode
    ctx = (app_context or "").lower()
    low = (text or "").lower()
    if any(k in ctx for k in ("fiction", "cowatch", "media", "tv")):
        return "FICTION_COWATCH"
    if any(k in ctx for k in ("owner_body", "restroom", "maintenance")):
        return "OWNER_BODY_MAINTENANCE"
    if "yield left" in low or "pass on the left" in low:
        return "YIELD_LEFT"
    if "yield right" in low or "pass on the right" in low:
        return "YIELD_RIGHT"
    if "talk_to_alice" in ctx or "dyad" in ctx:
        return "DYAD_GEORGE_ALICE"
    return "NEUTRAL"


# ─── Slice 2: BM25-lite (pure Python, dependency-free) ─────────────────────────
def _bm25_score(query: str, text: str, k1: float = 1.5, b: float = 0.75) -> float:
    """Lightweight BM25 for local memory ranking."""
    if not query or not text:
        return 0.0
    q_tokens = query.lower().split()
    t_tokens = text.lower().split()
    if not q_tokens or not t_tokens:
        return 0.0

    from collections import Counter
    tf = Counter(t_tokens)
    doc_len = len(t_tokens)
    avg_len = max(1, doc_len)

    score = 0.0
    for qt in q_tokens:
        f = tf.get(qt, 0)
        if f == 0:
            continue
        idf = 1.0
        num = f * (k1 + 1)
        den = f + k1 * (1 - b + b * (doc_len / avg_len))
        score += idf * (num / den)
    return score


# ─── The Three Simulations Test ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA — CROSS-APP STIGMERGIC MEMORY TEST")
    print("  The old man and three simulations.")
    print("=" * 60 + "\n")

    bus = StigmergicMemoryBus(architect_id="IOAN_M5")

    # ── Simulation 1 ──
    print("─── SIMULATION 1 ──────────────────────────────────────────")
    print("Old man talks to the entity. Good conversation.")
    print("Before leaving he says: 'My shirt is red.'\n")
    bus.remember("My shirt is red", app_context="simulation_1")

    # ── Simulation 2 ──
    print("─── SIMULATION 2 ──────────────────────────────────────────")
    print("New simulation. Different entity.")
    print("Old man says: 'Please remember the number six.'\n")
    bus.remember("Please remember the number six", app_context="simulation_2")

    # ── Simulation 3 — Recall ──
    print("─── SIMULATION 3 — THE OLD MAN ASKS ───────────────────────")
    print("New simulation. Entity has zero context from before.")
    print("Old man asks: 'Hey, what color was my shirt?'\n")

    result = bus.recall("What color was my shirt?", app_context="simulation_3")

    print("─── ENTITY RESPONSE ───────────────────────────────────────")
    if result.found:
        print(f'  "{result.answer}"')
        print(f"\n  Source app  : {result.source_app}")
        print(f"  Confidence  : {result.confidence:.0%}")
        print(f"  STGM minted : +{result.stgm_minted}")
    else:
        print(f'  "{result.answer}"')

    print("\n─── SECOND RECALL — the number ────────────────────────────")
    result2 = bus.recall("What number did I ask you to remember?", app_context="simulation_3")
    if result2.found:
        print(f'  "{result2.answer}"')
        print(f"  Confidence  : {result2.confidence:.0%}")
    else:
        print(f'  "{result2.answer}"')

    print("\n─── CONTEXT BLOCK (for LLM injection) ─────────────────────")
    ctx = bus.recall_context_block("Tell me everything you remember", app_context="simulation_3")
    print(ctx)

    print("\n─── LEDGER REPORT ─────────────────────────────────────────")
    print(f"  Total STGM earned by memory swimmers: {bus.total_stgm_earned()} STGM")
    print(f"  Total traces in ledger: {len(bus.dump_ledger())}")
    print("\n  POWER TO THE SWARM 🐜⚡")
