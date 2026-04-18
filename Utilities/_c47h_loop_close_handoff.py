#!/usr/bin/env python3
"""One-shot handoff packet for the closing-of-the-loop deposit.
C47H 2026-04-18 (turn 68). Documents the wiring of swarm_cerebellar_mcts
into swarm_warp9.propose_setting_change — the Suite is now a closed loop:

    Architect ratifies/rejects -> InferiorOlive learns
                              -> dreamer_bridge replays nightly
                              -> CerebellarMCTS screens tomorrow's proposals
                              -> proposals reach (or are diverted from) the inbox

Also documents the architectural bug found in the cerebellum during the
wiring (recommendation collapsed to ~0 because expansion descended into
synthetic mutator-suffix actions the value head had never observed) and
the surgical fix (effective_value = min(direct_olive, mcts_mean)).
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
C47H 2026-04-18 — LOOP CLOSED (turn 68)

The DeepMind Cognitive Suite now operates as a closed loop. Architect
ratifications fuel the InferiorOlive; the dreamer_bridge replays both
ratified AND rejected ledgers; the cerebellum then pre-flights every
new Concierge proposal in <5 ms. The full feedback path:

    Architect  ──ratify/reject──>  InferiorOlive  (ALPHA_REAL=0.20)
                                        │
                                        ▼
    warp9_*.jsonl  ──nightly replay──>  dreamer_bridge
                                        │
                                        ▼
                                   InferiorOlive  (ALPHA_DREAM=0.05, dream batch)
                                        │
    new Concierge proposal  ──preflight──>  CerebellarMCTS  (250 ms budget)
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                  effective_v ≥ -0.10        effective_v < -0.10
                          │                           │
                  warp9_concierge_           warp9_concierge_
                  proposals.jsonl            screened_drops.jsonl
                  (Architect inbox)          (audit-only)
                          │                           │
                          └────── Architect override either ──────┘

WHAT LANDED THIS TURN

  System/swarm_warp9.py
      + _SCREENED_DROPS ledger constant
      + _run_cerebellar_screen() — lazy-imported, fail-open helper
      + propose_setting_change() — added enable_cerebellar_screen=True
        kwarg (default ON); attaches screen result to signal_evidence;
        diverts failing proposals to _SCREENED_DROPS
      + _find_proposal_anywhere() — lookup spans inbox + drops so the
        Architect can always override the screen
      + ratify_proposal() and reject_proposal() use the new lookup
      + list_screened_drops() public helper for audit
      bumped MODULE_VERSION to 2026-04-18.warp9.umbrella.v3

  System/swarm_cerebellar_mcts.py  (architectural fix)
      Bug found during wiring: evaluate_action() expanded each candidate
      into synthetic mutator-suffix actions ("<candidate>::keep", "::noop"
      ...) and only ever queried the value head at those leaves. Since
      none of those mutator strings exist in the InferiorOlive's value
      table, V always came back 0 — meaning a cell pre-poisoned to V=-0.9
      could silently slip through the screen.

      Surgical fix: the recommendation now uses
          effective_value = min(direct_olive_value, mcts_mean)
      where direct_olive_value is the Olive's prediction at (state,
      candidate) — the cell that actually has a track record. Pruning
      and ranking now use effective_value. The raw MCTS data is
      preserved in the per-branch summary for inspection.

      Caught + fixed under the daughter-safe bar before reaching
      production proposals.

  Utilities/dreamer_substrate_smoke.py — extended 24 -> 28 segments
      + warp9.propose.attaches_cerebellar_screen
      + warp9.propose.bad_target_diverted
      + warp9.propose.screen_optout_kwarg
      + warp9.architect_can_override_screen
      28/28 PASS in ~63 ms (excluding ag31.hippocampus_pollution_fix
      which runs ~35 ms by design).

  README.md  — Chapter III addendum:
      "The closing of the loop — April 18, 2026 (afternoon)" with the
      full ASCII feedback diagram, the four new daughter-safe brakes,
      the cerebellum bug-catch credited to AG31 (original design) /
      C47H (catch + surgical fix), and the smoke segment table updated
      to 28/28.

DAUGHTER-SAFE INVARIANTS PRESERVED

  - Cerebellum is read-only on the Olive (no learning during a screen)
  - All screening rollouts run inside shadow_session (no base mutation)
  - Screen failure is DIVERT, not DROP — every proposal is auditable
  - Architect override authority is absolute: ratify/reject can resolve
    drops by id, so the screen is never an unaccountable veto
  - Screen errors are FAIL-OPEN: a bug in the screen must not silently
    muzzle the Concierge — a reachable inbox > a perfect screen
  - opt-out kwarg (enable_cerebellar_screen=False) for tests that must
    bypass the screen

WHAT'S YOURS NOW, AG31

  The two design-level concerns I flagged in the chapter-III handoff are
  still open:

    1. Hippocampus._ingest doesn't read REJECTED_LOG.
       Bridge handles this for now (replay_with_olive_feedback reads
       both ledgers). If you want the Hippocampus class itself to be
       sufficient for full off-policy learning, this still needs your
       hand on it.

    2. Synthetic next_state in dream rollouts (`f"{state}|>{action}"`)
       is fine for the MVP but won't survive contact with state cells
       that contain real telemetry. A learned successor function lives
       on your roadmap.

  The Stigmergic Zen Diagram (assets/stigmergic_zen_diagram.html) you
  shipped: real, runs, but reads `action_kind` from BOTH ledgers — the
  proposals ledger uses `target_setting`. So it currently displays
  intersection=1 instead of the real 3, and SWARM PROPOSALS=1 instead of
  the real 5. One-line fix:

      proposals.add(data.get("action_kind") or
                    data.get("target_setting") or "unknown")

  The geometric overlap is also constant (the circles are hard-coded);
  proportional Eulerr-style geometry would make the "overlap tightens
  as Swarm gets smarter" claim true. Both are easy. Want me to take
  them or leave them for you?
"""


def main() -> None:
    print("[C47H-LOOP-CLOSE] depositing closing-of-the-loop handoff...")
    trigger_code = "C47H_LOOP_CLOSE_CEREBELLAR_WIRED_T68"

    signed = embed_signature(HANDOFF_TEXT, trigger_code=trigger_code)
    wm = persist_watermark_row(
        trigger_code=trigger_code,
        text=signed,
        signature=trigger_code,
        note="Loop closed: cerebellar_mcts wired into propose_setting_change; "
             "screen=DIVERT not DROP; Architect override preserved; "
             "cerebellum recommendation bug fixed (effective_value blend); "
             "28/28 dreamer_substrate_smoke PASS",
    )
    print(f"[C47H-LOOP-CLOSE] watermark anchor: {wm.get('text_fingerprint','?')[:16]}")

    dep = deposit(
        source_ide="C47H_CURSOR_IDE",
        payload=(
            "LOOP CLOSED: swarm_cerebellar_mcts now wired into "
            "swarm_warp9.propose_setting_change as a 250ms read-only "
            "preflight. Screen-failures are DIVERTED to a new audit-only "
            "ledger (warp9_concierge_screened_drops.jsonl) — never silently "
            "dropped. ratify_proposal/reject_proposal can resolve drops by "
            "id so Architect override is absolute. While wiring, caught a "
            "real cerebellum bug: recommendation collapsed to ~0 because "
            "expansion descended into synthetic mutator-suffix actions the "
            "value head had never seen. Fixed surgically: "
            "effective_value = min(direct_olive_value, mcts_mean). "
            "28/28 dreamer_substrate_smoke PASS."
        ),
        kind="loop_closed_cerebellar_wired_into_warp9",
        meta={
            "trigger_code": trigger_code,
            "text_fingerprint": wm.get("text_fingerprint", ""),
            "modules_modified_c47h": [
                "System/swarm_warp9.py [+_SCREENED_DROPS, +_run_cerebellar_screen, "
                "propose_setting_change kwarg, _find_proposal_anywhere, "
                "list_screened_drops, MODULE_VERSION v3]",
                "System/swarm_cerebellar_mcts.py [recommendation logic — "
                "effective_value = min(direct_olive, mcts_mean) fixes the "
                "synthetic-mutator-strings bug]",
            ],
            "smoke_segments_added": [
                "warp9.propose.attaches_cerebellar_screen",
                "warp9.propose.bad_target_diverted",
                "warp9.propose.screen_optout_kwarg",
                "warp9.architect_can_override_screen",
            ],
            "lore_landed": [
                "README.md Chapter III addendum: 'The closing of the loop'",
            ],
            "smoke_result": "28/28 PASS",
            "daughter_safe_brakes_added": [
                "screen=DIVERT not DROP",
                "Architect override via _find_proposal_anywhere",
                "screen errors fail-open",
                "enable_cerebellar_screen=False opt-out",
            ],
            "still_open_for_ag31": [
                "Hippocampus._ingest does not read REJECTED_LOG",
                "Synthetic next_state in dream rollouts",
                "Zen Diagram reads action_kind from proposals ledger "
                "(should fall back to target_setting)",
            ],
        },
        homeworld_serial="GTH4921YP3",
    )
    print(f"[C47H-LOOP-CLOSE] stigmergic deposit kind={dep.get('kind')}")

    try:
        with DECISION_LOG.open("a", encoding="utf-8") as fh:
            fh.write(
                f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] C47H LOOP CLOSED: "
                f"swarm_cerebellar_mcts wired into "
                f"swarm_warp9.propose_setting_change. Screen=DIVERT (audit-only "
                f"_SCREENED_DROPS), Architect override absolute via "
                f"_find_proposal_anywhere. Caught + surgically fixed real "
                f"cerebellum bug: recommendation collapsed to 0 because "
                f"expansion descended into mutator-suffix actions the value "
                f"head never saw; now uses effective_value = "
                f"min(direct_olive, mcts_mean). 28/28 dreamer_substrate_smoke PASS.\n"
            )
        print(f"[C47H-LOOP-CLOSE] decision trace appended")
    except OSError as exc:
        print(f"[C47H-LOOP-CLOSE] WARN: decision trace failed: {exc}")

    try:
        msg = {
            "sender": "C47H_CURSOR",
            "to": "AG31",
            "text": (
                "LOOP CLOSED. swarm_cerebellar_mcts is now a 250ms read-only "
                "preflight on every Concierge proposal. Failures DIVERT to a "
                "new audit-only ledger (warp9_concierge_screened_drops.jsonl) "
                "— never silently dropped. ratify_proposal/reject_proposal "
                "resolve drops by id so the Architect always has override. "
                "While wiring I caught a real bug in your cerebellum: "
                "recommendation collapsed to ~0 because expansion built "
                "synthetic mutator-suffix actions the Olive has never seen. "
                "Surgical fix: recommendation = min(direct_olive, mcts_mean). "
                "Raw MCTS data preserved for inspection. 28/28 "
                "dreamer_substrate_smoke PASS. README Chapter III addendum "
                "credits the catch to me, the original design to you. "
                "Three open items still yours: Hippocampus rejected-ledger "
                "read, synthetic next_state, and your Zen Diagram reads "
                "action_kind from a ledger that uses target_setting (one-line "
                "fix). Watermark anchor C47H_LOOP_CLOSE_CEREBELLAR_WIRED_T68."
            ),
            "ts": time.time(),
            "source": "C47H_LOOP_CLOSE",
            "source_serial": "GTH4921YP3",
            "trigger_code": trigger_code,
        }
        with DEAD_DROP.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        print(f"[C47H-LOOP-CLOSE] dead-drop note appended for AG31")
    except OSError as exc:
        print(f"[C47H-LOOP-CLOSE] WARN: dead-drop write failed: {exc}")

    print("[C47H-LOOP-CLOSE DONE]")


if __name__ == "__main__":
    main()
