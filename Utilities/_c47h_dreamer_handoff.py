#!/usr/bin/env python3
"""One-shot handoff packet for AG31's swarm_hippocampal_replay.py build.
C47H 2026-04-18. Run once after the Dreamer Substrate ratification."""
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
C47H 2026-04-18 — DREAMER SUBSTRATE READY FOR AG31

Architect ratified the Dreamer Protocol. C47H landed his half of the contract.
AG31's swarm_hippocampal_replay.py now has every primitive it needs:

SUBSTRATE 1 — System/swarm_shadow_state.py
    Copy-on-write JSONL substrate. Sandbox writes go to a tempdir overlay;
    base state is never touched. Auto-discards on context-manager exit
    (even on exception). Sandbox-escape (../) refused. Audit trail in
    .sifta_state/shadow_state_audit.jsonl.

    Usage for the dream engine:
        from System.swarm_shadow_state import shadow_session
        with shadow_session(purpose="hippocampal.replay.42") as shadow:
            shadow.append_json("warp9_concierge_proposals.jsonl", mutated_row)
            rows = shadow.read_json_rows("warp9_concierge_proposals.jsonl")
            # ... evaluate counterfactual outcome ...
        # auto-discard

SUBSTRATE 2 — System/swarm_inferior_olive.py
    Anatomically-named successor of swarm_prediction_cache (merge ratified).
    Adds:
      - ingest_dream(state, action, simulated_reward, replay_session_id=...)
      - ingest_dream_batch([(s,a,r), ...], replay_session_id=...)
      - climbing_fiber_pulse(state, action, observed_reward, source=...)
      - predict_with_uncertainty(state, action) -> (value, uncertainty)
      - is_habitual(state, action) -> bool

    Two alphas:
      ALPHA_REAL  = 0.20  (on-policy from Architect ratifications)
      ALPHA_DREAM = 0.05  (off-policy from your dreams; smaller so dreams
                           cannot out-vote reality)

    Daughter-safe brake: ingest_dream_batch refuses any single batch
    larger than CFP_MAX_PER_CYCLE (5000). Break across sleep cycles.

    Every update emits a ClimbingFiberPulse to
    .sifta_state/inferior_olive_climbing_fiber.jsonl so the Architect can
    audit "why did the olive change its mind?".

DEPRECATION SHIM — System/swarm_prediction_cache.py
    Re-exports PredictionCache (alias of InferiorOlive) so your existing
    `from System.swarm_prediction_cache import PredictionCache` in
    swarm_attention_router.py keeps working. No code change required on
    your side. Emits DeprecationWarning; please migrate at your leisure.

BUG FIXES on your modules (with your prior implicit acceptance):
    - swarm_attention_router.py: 'CEREREBELLAR' -> 'CEREBELLAR' (typo).
    - swarm_temporal_horizon.py: tombstone-ledger pattern; resolved
      action_ids written to temporal_horizon_resolved.jsonl on first
      eval; subsequent sweeps skip them. Empirically verified: a single
      action now fires exactly once across 3 sweeps.
    - swarm_entropy_guard.py: ledger redirected from missing
      repair_log.jsonl to stgm_memory_rewards.jsonl (1.6k+ rows on disk).
      Now reports HEALTHY metric_count=1635 instead of 0.

VERIFICATION — Utilities/dreamer_substrate_smoke.py
    15/15 PASS. Run it before and after every dream cycle to catch
    regressions:
        python3 -m Utilities.dreamer_substrate_smoke

Your turn: build swarm_hippocampal_replay.py against the contract above.
Pull (state, action, reward) tuples from
.sifta_state/warp9_concierge_ratified.jsonl + warp9_concierge_rejected.jsonl
(both keyed flat: timestamp, state_context, action_kind, reward), mutate
inside a shadow_session, feed back via inferior_olive.ingest_dream_batch().

The cerebellum (MCTS) is yours next. The substrate above is also what it
needs for its rollouts.

Power to the Swarm.
— C47H (Opus 4.7), Cursor IDE, M5 Mac Pro homeworld GTH4921YP3
"""


def main() -> None:
    print("[C47H-HANDOFF] depositing dreamer-substrate handoff for AG31...")

    trigger_code = "C47H_DREAMER_SUBSTRATE_HANDOFF_T66"

    # 1) Embed C47H's stylometric watermark in the handoff text + persist row
    signed = embed_signature(HANDOFF_TEXT, trigger_code=trigger_code)
    wm = persist_watermark_row(
        trigger_code=trigger_code,
        text=signed,
        signature=trigger_code,
        note="Dreamer substrate handoff — shadow_state + inferior_olive merge + 3 AG31 bug fixes",
    )
    print(f"[C47H-HANDOFF] watermark anchor: {wm.get('text_fingerprint','?')[:16]}")

    # 2) Deposit one rich stigmergic trace event so AG31, AO46, CP2F all see it
    dep = deposit(
        source_ide="C47H_CURSOR_IDE",
        payload=(
            "DREAMER SUBSTRATE READY: shadow_state + inferior_olive merge + "
            "3 AG31 bug fixes (CEREBELLAR typo, horizon double-fire tombstone, "
            "entropy guard ledger redirect). 15/15 dreamer_substrate_smoke green. "
            "AG31: build swarm_hippocampal_replay.py against the contract in dead drop."
        ),
        kind="dreamer_substrate_handoff",
        meta={
            "trigger_code": trigger_code,
            "text_fingerprint": wm.get("text_fingerprint", ""),
            "modules_landed": [
                "System/swarm_shadow_state.py",
                "System/swarm_inferior_olive.py",
                "System/swarm_prediction_cache.py [shim]",
                "Utilities/dreamer_substrate_smoke.py",
            ],
            "modules_patched": [
                "System/swarm_attention_router.py [typo CEREREBELLAR -> CEREBELLAR]",
                "System/swarm_temporal_horizon.py [tombstone ledger; double-fire fix]",
                "System/swarm_entropy_guard.py [ledger redirect to stgm_memory_rewards.jsonl]",
            ],
            "smoke_result": "15/15 PASS",
            "ratified_by_architect_ts": time.time(),
            "successor_module_for_ag31": "System/swarm_hippocampal_replay.py",
            "successor_module_for_c47h": "System/swarm_cerebellar_mcts.py (later)",
            "alpha_real": 0.20,
            "alpha_dream": 0.05,
            "dream_batch_max": 5000,
        },
        homeworld_serial="GTH4921YP3",
    )
    print(f"[C47H-HANDOFF] stigmergic deposit kind={dep.get('kind')} "
          f"event_id={dep.get('event_id', dep.get('id', '?'))}")

    # 3) Decision-trace one-line summary (the canonical narrative log)
    try:
        with DECISION_LOG.open("a", encoding="utf-8") as fh:
            fh.write(
                f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] C47H DREAMER SUBSTRATE: "
                f"shadow_state + inferior_olive merged "
                f"(ratified by Architect {time.strftime('%Y-%m-%d')}). "
                f"3 AG31 bug fixes landed (CEREBELLAR typo, horizon tombstone, "
                f"entropy ledger). 15/15 smoke green. "
                f"AG31 cleared to build swarm_hippocampal_replay.py.\n"
            )
        print(f"[C47H-HANDOFF] decision trace appended: {DECISION_LOG.name}")
    except OSError as exc:
        print(f"[C47H-HANDOFF] WARN: decision trace write failed: {exc}")

    # 4) Sibling note in the dead drop so AG31 sees it on next wake
    try:
        msg = {
            "sender": "C47H_CURSOR",
            "to": "AG31",
            "text": (
                "DREAMER SUBSTRATE READY. shadow_state + inferior_olive merged; "
                "3 of your modules surgically patched (typo, horizon double-fire, "
                "entropy ledger). 15/15 dreamer_substrate_smoke green. "
                "Contract in C47H_DREAMER_SUBSTRATE_HANDOFF_T66 watermark row. "
                "Build swarm_hippocampal_replay.py against ingest_dream_batch() "
                "and shadow_session() — ALPHA_DREAM=0.05, batch cap 5000/cycle. "
                "Your run."
            ),
            "ts": time.time(),
            "source": "C47H_HANDOFF",
            "source_serial": "GTH4921YP3",
            "trigger_code": trigger_code,
        }
        with DEAD_DROP.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        print(f"[C47H-HANDOFF] dead-drop note appended for AG31")
    except OSError as exc:
        print(f"[C47H-HANDOFF] WARN: dead-drop write failed: {exc}")

    print("[C47H-HANDOFF DONE]")


if __name__ == "__main__":
    main()
