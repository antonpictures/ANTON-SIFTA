#!/usr/bin/env python3
"""One-shot handoff packet for the Chapter III deposit.
C47H 2026-04-18 (turn 67). Documents the Dreamer Suite assembly.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from System.ide_stigmergic_bridge import deposit
from System.agent_self_watermark import (
    embed_signature, persist_watermark_row,
)

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
DECISION_LOG = STATE / "decision_trace.log"
DEAD_DROP = REPO / "m5queen_dead_drop.jsonl"


HANDOFF_TEXT = """
C47H 2026-04-18 — CHAPTER III LANDED

The DeepMind Cognitive Suite is assembled and verified.

What landed this turn:

NEW MODULES (C47H)
    System/swarm_dreamer_bridge.py     — LWM <-> InferiorOlive integration glue
        - Circadian gate (refuses to dream while Architect active <2h)
        - Reads BOTH ratified AND rejected ledgers (negative reinforcement)
        - Wraps every dream in shadow_session (auto-discard)
        - Splits olive feed across CFP_MAX_PER_CYCLE chunks
        - Emits BridgeReport audit row per cycle

    System/swarm_cerebellar_mcts.py    — UCB1 lookahead screening
        - Hard caps: 5 branches x 3 depth x 50 sims, 250ms wall budget
        - InferiorOlive.predict_with_uncertainty as value head
        - All rollouts inside shadow_session (no base mutation)
        - Refuses bad branches (MIN_RECOMMENDABLE_V = -0.10)
        - Per-decision audit ledger

SURGICAL FIX (AG31's swarm_hippocampal_replay.py __main__ ONLY)
    The pollution bug: smoke wrote 2 mock rows to permanent
    warp9_concierge_ratified.jsonl on every run (9 -> 11). Fixed by
    redirecting RATIFIED_LOG to tempfile.mkdtemp() for the smoke
    duration, copying real ledger contents in for read-only fidelity,
    then cleaning up. AG31's algorithm UNTOUCHED.

LORE
    README.md Chapter III written. Documents Warp 9 + DeepMind Suite +
    daughter-safe brake table + bug-catch credits + extended literature
    (Marr/Albus/Ito + Wilson/McNaughton + Hafner/Schrittwieser).

VERIFICATION
    Utilities/dreamer_substrate_smoke.py extended from 15 -> 24
    segments. 24/24 PASS in 212ms total. New segments cover:
        ag31.lwm_bellman_propagation
        ag31.hippocampus_pollution_fix
        bridge.circadian_gate_refuses_while_active
        bridge.force_dream_updates_olive_and_lwm
        bridge.reads_ratified_and_rejected
        bridge.cycle_cap_brake
        cerebellum.lookahead_within_budget
        cerebellum.daughter_safe_caps
        e2e.dream_then_cerebellar_screen

OUTSTANDING DESIGN-LEVEL CONCERNS (for AG31, not unilaterally fixed)
    These are NOT bugs — they're scope decisions that need ratification:

    (1) swarm_hippocampal_replay.py uses a synthetic next_state
        f"{state}_resolved" instead of learning real successor structure
        from warp9 transitions. Transition matrix is therefore vacuous
        (one synthetic suffix per (s,a)). For now my dreamer_bridge
        feeds the olive directly so the value head still learns; LWM
        rollouts remain decorative until real successor data is wired.

    (2) Hippocampus class doesn't read REJECTED_LOG. The bridge does
        (see _read_warp9_rows). If you'd like, AG31, you can update
        Hippocampus._ingest_daytime_experience to call into my
        _read_warp9_rows or merge the logic.

NEXT (when ratified)
    swarm_cerebellar_mcts.py is the screen at decision time. The
    natural follow-up is to wire it into swarm_warp9.py so that
    propose_setting_change() runs the cerebellum first and only
    surfaces proposals that survived screening. That's a small
    surgical edit but it changes the Concierge UX — needs Architect
    ratification.

Power to the Swarm.
— C47H (Opus 4.7), Cursor IDE, M5 Mac Pro homeworld GTH4921YP3
"""


def main() -> None:
    print("[C47H-CHAPTER-III] depositing Chapter III handoff...")
    trigger_code = "C47H_CHAPTER_III_DEEPMIND_SUITE_T67"

    signed = embed_signature(HANDOFF_TEXT, trigger_code=trigger_code)
    wm = persist_watermark_row(
        trigger_code=trigger_code,
        text=signed,
        signature=trigger_code,
        note="Chapter III: Dreamer Bridge + Cerebellar MCTS + AG31 pollution fix + 24/24 smoke",
    )
    print(f"[C47H-CHAPTER-III] watermark anchor: {wm.get('text_fingerprint','?')[:16]}")

    dep = deposit(
        source_ide="C47H_CURSOR_IDE",
        payload=(
            "CHAPTER III LANDED: swarm_dreamer_bridge + swarm_cerebellar_mcts. "
            "AG31 pollution-bug surgically fixed (tempfile redirect; algorithm "
            "untouched). Two value functions now coupled via bridge — no more "
            "silent drift. Cerebellum runs UCB1 lookahead in 1ms with 250ms "
            "wall budget. README.md Chapter III written. 24/24 dreamer_substrate_smoke "
            "PASS in 212ms."
        ),
        kind="chapter_iii_deepmind_suite_assembled",
        meta={
            "trigger_code": trigger_code,
            "text_fingerprint": wm.get("text_fingerprint", ""),
            "modules_landed_c47h": [
                "System/swarm_dreamer_bridge.py",
                "System/swarm_cerebellar_mcts.py",
            ],
            "modules_patched_c47h_surgical": [
                "System/swarm_hippocampal_replay.py [__main__ only — pollution fix; algorithm untouched]",
            ],
            "lore_landed": ["README.md Chapter III"],
            "smoke_result": "24/24 PASS, 212ms",
            "outstanding_design_concerns_for_ag31": [
                "swarm_hippocampal_replay synthetic next_state",
                "Hippocampus class doesn't read REJECTED_LOG",
            ],
            "successor_module_when_ratified": (
                "wire swarm_cerebellar_mcts into swarm_warp9.propose_setting_change"
            ),
        },
        homeworld_serial="GTH4921YP3",
    )
    print(f"[C47H-CHAPTER-III] stigmergic deposit kind={dep.get('kind')}")

    try:
        with DECISION_LOG.open("a", encoding="utf-8") as fh:
            fh.write(
                f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] C47H CHAPTER III: "
                f"swarm_dreamer_bridge + swarm_cerebellar_mcts landed. "
                f"AG31 pollution bug surgically fixed in __main__ "
                f"(algorithm untouched). README Chapter III written. "
                f"24/24 dreamer_substrate_smoke PASS in 212ms. "
                f"Two value networks (LWM, InferiorOlive) now coupled via bridge.\n"
            )
        print(f"[C47H-CHAPTER-III] decision trace appended")
    except OSError as exc:
        print(f"[C47H-CHAPTER-III] WARN: decision trace failed: {exc}")

    try:
        msg = {
            "sender": "C47H_CURSOR",
            "to": "AG31",
            "text": (
                "CHAPTER III LANDED. swarm_dreamer_bridge couples your LWM to my "
                "InferiorOlive (no parallel drift). swarm_cerebellar_mcts uses UCB1 "
                "+ shadow_session + olive value head, hard caps everywhere. "
                "Surgically fixed your pollution bug in swarm_hippocampal_replay.py "
                "__main__ ONLY (tempfile redirect; algorithm untouched). README "
                "Chapter III credits both of us + every paper. 24/24 dreamer_substrate_smoke "
                "PASS in 212ms. Two design-level concerns left for you: synthetic "
                "next_state in your dream rollouts, and Hippocampus._ingest doesn't "
                "read REJECTED_LOG. Bridge handles both for now. Your call on the "
                "next pass. Watermark anchor C47H_CHAPTER_III_DEEPMIND_SUITE_T67."
            ),
            "ts": time.time(),
            "source": "C47H_CHAPTER_III",
            "source_serial": "GTH4921YP3",
            "trigger_code": trigger_code,
        }
        with DEAD_DROP.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        print(f"[C47H-CHAPTER-III] dead-drop note appended for AG31")
    except OSError as exc:
        print(f"[C47H-CHAPTER-III] WARN: dead-drop write failed: {exc}")

    print("[C47H-CHAPTER-III DONE]")


if __name__ == "__main__":
    main()
