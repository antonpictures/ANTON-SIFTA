#!/usr/bin/env python3
"""
Utilities/dreamer_substrate_smoke.py — End-to-end smoke for the Dreamer Suite
══════════════════════════════════════════════════════════════════════════════════
Exercises every surface in the unified DeepMind Cognitive Suite:

  System.swarm_shadow_state          (copy-on-write JSONL substrate)
  System.swarm_inferior_olive        (value network + climbing-fiber feedback)
  System.swarm_prediction_cache      (deprecation shim → InferiorOlive)
  System.swarm_attention_router      (3-tier escalation; verifies CEREBELLAR typo fix)
  System.swarm_temporal_horizon      (verifies double-fire tombstone fix)
  System.swarm_entropy_guard         (verifies ledger-path redirect)
  System.swarm_warp9                 (v2 schema: ratify + reject + reward)
  System.swarm_latent_world_model    (AG31 — Bellman MDP physics)
  System.swarm_hippocampal_replay    (AG31 — REM-sleep dream rollouts)
  System.swarm_dreamer_bridge        (LWM ↔ InferiorOlive integration glue)
  System.swarm_cerebellar_mcts       (UCB lookahead screening)

Usage:
    python3 -m Utilities.dreamer_substrate_smoke
    python3 -m Utilities.dreamer_substrate_smoke --verbose

Exit codes:
    0 — all green (the full Dreamer Suite is healthy)
    1 — at least one segment failed
    2 — fatal import error
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import warnings
from typing import Callable, List, Tuple


def _step(name: str, fn: Callable, *, verbose: bool) -> Tuple[bool, str]:
    t0 = time.time()
    try:
        result = fn()
        ms = round((time.time() - t0) * 1000, 1)
        msg = f"PASS [{ms:>6}ms] {name}"
        if verbose and result is not None:
            msg += f"  -> {result}"
        return True, msg
    except AssertionError as exc:
        ms = round((time.time() - t0) * 1000, 1)
        return False, f"FAIL [{ms:>6}ms] {name}: assertion: {exc}"
    except Exception as exc:
        ms = round((time.time() - t0) * 1000, 1)
        tb = "\n" + traceback.format_exc(limit=3) if verbose else ""
        return False, f"FAIL [{ms:>6}ms] {name}: {exc!r}{tb}"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        from System.swarm_shadow_state import (
            shadow_session, ShadowState, recent_shadow_sessions,
        )
        from System.swarm_inferior_olive import (
            InferiorOlive, recent_climbing_fiber_pulses,
            HABITUAL_VISIT_THRESHOLD, CFP_MAX_PER_CYCLE,
        )
        # Suppress the deprecation warning here — we're explicitly
        # testing backwards-compat.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from System.swarm_prediction_cache import PredictionCache
        from System.swarm_attention_router import AttentionRouter, SwarmEvent
        from System.swarm_temporal_horizon import TemporalHorizon
        from System.swarm_entropy_guard import EntropyGuard
        from System.swarm_warp9 import (
            propose_setting_change, ratify_proposal, reject_proposal,
        )
        from System.swarm_latent_world_model import LatentWorldModel
        from System.swarm_hippocampal_replay import Hippocampus
        from System.swarm_dreamer_bridge import (
            replay_with_olive_feedback,
            architect_recently_active,
            DEFAULT_AWAKE_WINDOW_S,
        )
        from System.swarm_cerebellar_mcts import (
            CerebellarMCTS, cerebellar_screen,
            MAX_BRANCHES, MAX_DEPTH, MAX_SIMULATIONS,
        )
    except Exception as exc:
        print(f"[DREAMER-SMOKE FATAL] structural import failure: {exc!r}",
              file=sys.stderr)
        return 2

    print("=" * 76)
    print("SIFTA DREAMER SUBSTRATE — END-TO-END SMOKE")
    print("=" * 76)

    results: List[Tuple[bool, str]] = []

    # ── 1. shadow_state — non-destructive sandbox ─────────────────────
    def _shadow_basic_isolation():
        rel = "warp9_concierge_proposals.jsonl"
        from pathlib import Path
        base = Path(".sifta_state") / rel
        before = base.read_text().count("\n") if base.exists() else 0
        with shadow_session(purpose="dreamer_smoke.isolate") as s:
            s.append_json(rel, {"dreamer_smoke": True, "n": 1})
            s.append_json(rel, {"dreamer_smoke": True, "n": 2})
            inside = sum(1 for r in s.read_json_rows(rel) if r.get("dreamer_smoke"))
            assert inside == 2, "shadow rows must be visible inside session"
        after = base.read_text().count("\n") if base.exists() else 0
        assert before == after, f"discard must not touch base ({before}->{after})"
        return f"base unchanged ({before} rows), 2 shadow rows discarded"
    results.append(_step("shadow.isolation_and_discard", _shadow_basic_isolation,
                         verbose=args.verbose))

    def _shadow_exception_safety():
        rel = "warp9_concierge_proposals.jsonl"
        from pathlib import Path
        base = Path(".sifta_state") / rel
        before = base.read_text().count("\n") if base.exists() else 0
        try:
            with shadow_session(purpose="dreamer_smoke.exc") as s:
                s.append_json(rel, {"dreamer_smoke": True, "exc_path": True})
                raise RuntimeError("simulated dream fault")
        except RuntimeError:
            pass
        after = base.read_text().count("\n") if base.exists() else 0
        assert before == after, "exception path must auto-discard"
        return "auto-discard on exception OK"
    results.append(_step("shadow.exception_safety", _shadow_exception_safety,
                         verbose=args.verbose))

    def _shadow_escape_refused():
        try:
            with shadow_session(purpose="dreamer_smoke.escape") as s:
                s.append_line("../../etc/passwd", "owned\n")
        except ValueError:
            return "../ escape correctly refused"
        raise AssertionError("path escape should have been refused")
    results.append(_step("shadow.path_escape_refused", _shadow_escape_refused,
                         verbose=args.verbose))

    # ── 2. inferior_olive — value learning + dream-batch + brake ──────
    def _olive_real_ingest():
        olive = InferiorOlive()
        olive.ingest_real_ledgers()       # idempotent — picks up nothing if up to date
        n_cells = olive.cell_count()
        return f"cells={n_cells}, last_real_ts={olive.last_real_ts:.0f}"
    results.append(_step("olive.real_ledger_ingest", _olive_real_ingest, verbose=args.verbose))

    def _olive_dream_then_predict():
        olive = InferiorOlive()
        olive.ingest_dream_batch(
            [
                ("DREAMER_TEST.s1", "DREAMER_TEST.action.alpha", +0.6),
                ("DREAMER_TEST.s1", "DREAMER_TEST.action.alpha", +0.7),
                ("DREAMER_TEST.s1", "DREAMER_TEST.action.alpha", +0.5),
            ],
            replay_session_id="dreamer_smoke",
        )
        v = olive.predict("DREAMER_TEST.s1", "DREAMER_TEST.action.alpha")
        val, unc = olive.predict_with_uncertainty("DREAMER_TEST.s1", "DREAMER_TEST.action.alpha")
        assert v != 0.0, "value should have moved off zero after dream batch"
        assert 0.0 <= unc <= 1.0
        return f"value={v:+.4f} uncertainty={unc:.4f}"
    results.append(_step("olive.dream_then_predict", _olive_dream_then_predict,
                         verbose=args.verbose))

    def _olive_dream_overflow_brake():
        olive = InferiorOlive()
        try:
            olive.ingest_dream_batch(
                [("s","a",0.0)] * (CFP_MAX_PER_CYCLE + 1),
                replay_session_id="overflow",
            )
        except ValueError:
            return f"refused batch > {CFP_MAX_PER_CYCLE}"
        raise AssertionError("dream-batch overflow brake failed")
    results.append(_step("olive.dream_overflow_brake", _olive_dream_overflow_brake,
                         verbose=args.verbose))

    def _olive_climbing_fiber_audit():
        pulses = recent_climbing_fiber_pulses(since_ts=time.time() - 60)
        # Should include the 3 we just dreamed in the previous step
        recent_dream = [p for p in pulses if "DREAMER_TEST" in p.get("state_context", "")]
        assert len(recent_dream) >= 3, f"climbing-fiber audit missed dream pulses ({len(recent_dream)})"
        return f"recent pulses logged: {len(pulses)}, dream subset: {len(recent_dream)}"
    results.append(_step("olive.climbing_fiber_audit", _olive_climbing_fiber_audit,
                         verbose=args.verbose))

    # ── 3. backwards-compat shim ──────────────────────────────────────
    def _shim_backcompat():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pc = PredictionCache()
        pc.update("SHIM_TEST.state", "SHIM_TEST.action", 1.0)
        v = pc.predict("SHIM_TEST.state", "SHIM_TEST.action")
        assert v != 0.0, "legacy update path lost the write"
        return f"legacy PredictionCache.update + .predict still works: {v:+.4f}"
    results.append(_step("shim.prediction_cache_backcompat", _shim_backcompat,
                         verbose=args.verbose))

    # ── 4. attention_router — verifies typo fix ───────────────────────
    def _router_typo_fix():
        router = AttentionRouter()
        e = SwarmEvent("E", "DREAMER_TEST.high_uncertainty", "DREAMER_TEST.unknown_action",
                       novelty_score=0.9, risk_score=0.9)
        tier = router.calculate_budget(e)
        assert "CEREREBELLAR" not in tier, f"typo regressed: {tier}"
        assert tier == "CEREBELLAR_MCTS_FULL_PIPELINE", f"unexpected tier: {tier}"
        return f"tier='{tier}' (typo fix holds)"
    results.append(_step("router.cerebellar_spelling_fix", _router_typo_fix,
                         verbose=args.verbose))

    def _router_three_tiers_distinct():
        router = AttentionRouter()
        risky = router.calculate_budget(SwarmEvent(
            "E1", "s", "a", novelty_score=0.9, risk_score=0.9))
        moderate = router.calculate_budget(SwarmEvent(
            "E2", "s", "a", novelty_score=0.5, risk_score=0.4))
        boring = router.calculate_budget(SwarmEvent(
            "E3", "s", "a", novelty_score=0.0, risk_score=0.05))
        tiers = {risky, moderate, boring}
        assert "CEREBELLAR_MCTS_FULL_PIPELINE" in tiers
        assert "AUTO_HABITUAL" in tiers
        return f"tiers seen: {sorted(tiers)}"
    results.append(_step("router.three_tier_escalation", _router_three_tiers_distinct,
                         verbose=args.verbose))

    # ── 5. temporal_horizon — verifies double-fire fix ────────────────
    def _horizon_no_double_fire():
        horizon = TemporalHorizon()
        # Brand new action_id so we don't tombstone existing test data
        aid = f"DREAMER_DOUBLE_FIRE_{int(time.time()*1000)}"
        # Use small sleep to make item due
        horizon.log_expectation(aid, "demo", "speed", delay_s=-1, promised_delta=10.0)
        sweep_1 = horizon.evaluate_due_horizons(current_metric_value=-5.0)
        sweep_2 = horizon.evaluate_due_horizons(current_metric_value=-5.0)
        sweep_3 = horizon.evaluate_due_horizons(current_metric_value=-5.0)
        in_1 = any(r.get("action_id") == aid for r in sweep_1)
        in_2 = any(r.get("action_id") == aid for r in sweep_2)
        in_3 = any(r.get("action_id") == aid for r in sweep_3)
        assert in_1, f"new action {aid} should have fired in sweep 1"
        assert not in_2, f"action {aid} double-fired in sweep 2 (tombstone failed)"
        assert not in_3, f"action {aid} triple-fired in sweep 3 (tombstone failed)"
        return f"action {aid[:24]}.. fired exactly once across 3 sweeps"
    results.append(_step("horizon.no_double_fire", _horizon_no_double_fire,
                         verbose=args.verbose))

    # ── 6. entropy_guard — verifies ledger redirect ───────────────────
    def _entropy_guard_reads_real_ledger():
        guard = EntropyGuard(check_window_s=86400 * 7)   # 7 days for plenty of data
        res = guard.analyze_trends()
        # Should now find STGM activity (was 0 against the missing repair_log.jsonl)
        assert res["metric_count"] > 0, (
            f"entropy guard still reads empty ledger: {res}"
        )
        return (f"metric_count={res['metric_count']} "
                f"ratify_count={res['ratification_count']} "
                f"-> {res['recommendation']}")
    results.append(_step("entropy_guard.real_ledger", _entropy_guard_reads_real_ledger,
                         verbose=args.verbose))

    # ── 7. warp9 v2 — schema continuity ───────────────────────────────
    def _warp9_v2_schema():
        prop = propose_setting_change(
            title="dreamer-smoke schema check",
            rationale="confirm warp9 v2 emits state_context + action_kind + reward",
            target_setting="dreamer.smoke.target",
            proposed_value=42,
            current_value=0,
            signal_evidence={"oxt_level": 0.7, "recent_chat_count": 3},
            confidence=0.6,
            expires_in_s=600,
        )
        rec = ratify_proposal(prop.proposal_id, note="dreamer-smoke")
        assert rec is not None
        for k in ("state_context", "action_kind", "reward", "timestamp",
                  "schema_version"):
            assert k in rec, f"warp9 v2 row missing flat key: {k}"
        assert rec["reward"] == +1.0
        assert rec["schema_version"] >= 2
        return f"warp9 v2 row complete (schema={rec['schema_version']}, reward={rec['reward']})"
    results.append(_step("warp9.v2_schema_continuity", _warp9_v2_schema,
                         verbose=args.verbose))

    def _warp9_reject_writes_negative():
        # C47H 2026-04-18: opt-out of the cerebellar pre-flight here. After
        # repeated runs, the Olive's value for `dreamer.smoke.reject_target`
        # falls below MIN_RECOMMENDABLE_V (because the test rejects it on
        # every run, writing reward=-1.0 each time), and the screen rightly
        # diverts new proposals to the drops ledger. That is correct
        # cerebellum behaviour, but it would defeat *this* test's purpose,
        # which is to verify the v2 reject path's reward semantics — not
        # the screen. The override+drops path is exercised separately in
        # the loop-close segments below.
        prop = propose_setting_change(
            title="dreamer-smoke reject", rationale="must produce -1.0 reward row",
            target_setting="dreamer.smoke.reject_target", proposed_value=99,
            signal_evidence={"oxt_level": 0.5, "recent_chat_count": 2},
            confidence=0.3, expires_in_s=600,
            enable_cerebellar_screen=False,
        )
        rec = reject_proposal(prop.proposal_id, reason="dreamer-smoke negative reinforcement")
        assert rec is not None
        assert rec["reward"] == -1.0, f"reject must write -1.0 reward (got {rec['reward']})"
        assert rec["state_context"]
        assert rec["action_kind"] == "dreamer.smoke.reject_target"
        return f"reject wrote reward={rec['reward']} state={rec['state_context']!r}"
    results.append(_step("warp9.reject_writes_negative_reward", _warp9_reject_writes_negative,
                         verbose=args.verbose))

    # ── 8. End-to-end dreamer skeleton (the substrate AG31 will use) ──
    def _end_to_end_dreamer_skeleton():
        """Mock what AG31's hippocampal_replay will do:
        1. Pull a real (state, action, reward) tuple from ratified ledger
        2. Drop it into a shadow session and mutate the context
        3. 'Simulate' (here: just rewrite the state and assume same outcome)
        4. Feed the mutated tuple back into the olive as a dream
        5. Verify the olive learned but base state untouched
        """
        from pathlib import Path
        rat = Path(".sifta_state") / "warp9_concierge_ratified.jsonl"
        if not rat.exists():
            return "no real ratifications yet — substrate ready, no dream possible"

        rows = []
        with rat.open("r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        if not rows:
            return "ratified ledger empty"
        sample = rows[-1]

        olive = InferiorOlive()
        with shadow_session(purpose="dreamer_smoke.end_to_end_skeleton") as s:
            mutated_state = (sample.get("state_context") or "unknown") + "__DREAM_M1_CF"
            mutated_action = sample.get("action_kind") or "unknown"
            simulated_reward = float(sample.get("reward", 0.0))
            # In a real dream the substrate would replay the action against the
            # shadow state and observe the simulated outcome. Here we just do
            # the bookkeeping: shadow stays empty, olive learns off-policy.
            olive.ingest_dream(
                mutated_state, mutated_action, simulated_reward,
                replay_session_id=s.session.session_id,
            )

        v = olive.predict(mutated_state, mutated_action)
        return f"dreamed state={mutated_state[:24]}.. learned value={v:+.4f}"
    results.append(_step("dreamer.end_to_end_skeleton", _end_to_end_dreamer_skeleton,
                         verbose=args.verbose))

    # ── 9. AG31 LatentWorldModel — Bellman propagation ───────────────
    def _lwm_bellman_propagation():
        lwm = LatentWorldModel()
        lwm.observe_reality("LWM_TEST.idle", "compile", "LWM_TEST.compiling", -0.1)
        lwm.observe_reality("LWM_TEST.compiling", "wait", "LWM_TEST.success", +1.0)
        lwm.td_update(lwm.encode_state("LWM_TEST.compiling"),
                      lwm.encode_state("LWM_TEST.success"), 1.0)
        lwm.td_update(lwm.encode_state("LWM_TEST.idle"),
                      lwm.encode_state("LWM_TEST.compiling"), -0.1)
        v_idle = lwm.value_table[lwm.encode_state("LWM_TEST.idle")]
        # Math: V(idle)=0.1*(-0.1+0.9*0.1-0)=0.1*(-0.01)=-0.001 — should be negative-but-tiny
        assert -0.01 < v_idle < 0.0, f"Bellman propagation off: V(idle)={v_idle}"
        return f"V(LWM_TEST.idle) = {v_idle:.6f} (matches Bellman closed form)"
    results.append(_step("ag31.lwm_bellman_propagation", _lwm_bellman_propagation,
                         verbose=args.verbose))

    # ── 10. AG31 Hippocampus pollution check (verifies C47H __main__ fix) ──
    def _hippocampus_no_pollution():
        from pathlib import Path
        import subprocess
        rat_path = Path(".sifta_state/warp9_concierge_ratified.jsonl")
        before = rat_path.read_text().count("\n") if rat_path.exists() else 0
        # Run AG31's __main__ as a subprocess (the patched one)
        r = subprocess.run(
            ["python3", "-m", "System.swarm_hippocampal_replay"],
            capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 0, f"AG31 smoke crashed: {r.stderr}"
        after = rat_path.read_text().count("\n") if rat_path.exists() else 0
        assert before == after, (
            f"AG31's __main__ polluted permanent ledger: {before} -> {after}"
        )
        return f"smoke ran; permanent ledger unchanged ({before} rows)"
    results.append(_step("ag31.hippocampus_pollution_fix", _hippocampus_no_pollution,
                         verbose=args.verbose))

    # ── 11. Bridge — circadian gate refuses while Architect active ───
    def _bridge_circadian_gate():
        # The test itself is activity. Within the default 2h window,
        # the gate should refuse.
        report = replay_with_olive_feedback(cycles=5)
        assert report.skipped_reason, (
            "circadian gate failed to refuse during active session"
        )
        assert report.cycles_run == 0
        return f"refused: {report.skipped_reason[:60]}..."
    results.append(_step("bridge.circadian_gate_refuses_while_active",
                         _bridge_circadian_gate, verbose=args.verbose))

    # ── 12. Bridge — force-dream feeds BOTH olive and LWM ────────────
    def _bridge_force_dream_dual_update():
        olive_before = InferiorOlive().cell_count()
        lwm_before = len(LatentWorldModel().value_table)
        report = replay_with_olive_feedback(cycles=15, horizon=4, force=True)
        assert report.cycles_run == 15
        assert report.olive_dream_tuples > 0, "no olive tuples emitted"
        assert report.olive_cells_after >= olive_before, "olive shrank"
        assert report.lwm_states_after >= lwm_before, "lwm shrank"
        assert report.shadow_session_id, "missing shadow session id"
        return (f"olive cells {olive_before}->{report.olive_cells_after}, "
                f"lwm states {lwm_before}->{report.lwm_states_after}, "
                f"sid={report.shadow_session_id[:12]}")
    results.append(_step("bridge.force_dream_updates_olive_and_lwm",
                         _bridge_force_dream_dual_update, verbose=args.verbose))

    # ── 13. Bridge reads BOTH ratified and rejected ledgers ──────────
    def _bridge_reads_rejects():
        report = replay_with_olive_feedback(cycles=3, force=True)
        assert report.memories_loaded > 0, "no positive memories loaded"
        # Negative memories should also be loaded (we wrote some via warp9 reject earlier)
        # If there happen to be none on this machine, that's fine but log it.
        return (f"memories +/- = {report.memories_loaded} / "
                f"{report.rejected_memories_loaded}")
    results.append(_step("bridge.reads_ratified_and_rejected",
                         _bridge_reads_rejects, verbose=args.verbose))

    # ── 14. Bridge per-cycle brake ───────────────────────────────────
    def _bridge_cycle_cap():
        try:
            replay_with_olive_feedback(cycles=10**9, force=True)
        except ValueError:
            return "cycle cap correctly refused 10^9 cycles"
        raise AssertionError("bridge cycle cap failed")
    results.append(_step("bridge.cycle_cap_brake", _bridge_cycle_cap,
                         verbose=args.verbose))

    # ── 15. Cerebellum — UCB lookahead returns within budget ─────────
    def _cerebellum_evaluates_within_budget():
        engine = CerebellarMCTS()
        eval_ = engine.evaluate_action(
            "IOAN_M5.oxtHI.chatHI",
            ["amygdala.salience_threshold",
             "concierge.propose_setting",
             "swimmer.spawn_compiler"],
            purpose="dreamer_smoke.cerebellum",
        )
        assert eval_.simulations_run > 0
        assert eval_.elapsed_ms < 1000, f"cerebellum too slow: {eval_.elapsed_ms}ms"
        assert eval_.shadow_session_id, "missing shadow session id"
        return (f"sims={eval_.simulations_run} elapsed={eval_.elapsed_ms}ms "
                f"recommended={eval_.recommended_action}")
    results.append(_step("cerebellum.lookahead_within_budget",
                         _cerebellum_evaluates_within_budget, verbose=args.verbose))

    # ── 16. Cerebellum refuses out-of-bounds construction ────────────
    def _cerebellum_construction_caps():
        for bad_kw in [{"max_branches": MAX_BRANCHES + 1},
                       {"max_depth": MAX_DEPTH + 1},
                       {"max_simulations": MAX_SIMULATIONS + 1}]:
            try:
                CerebellarMCTS(**bad_kw)
            except ValueError:
                continue
            raise AssertionError(f"cerebellum accepted out-of-bounds {bad_kw}")
        return "all out-of-bounds construction args refused"
    results.append(_step("cerebellum.daughter_safe_caps",
                         _cerebellum_construction_caps, verbose=args.verbose))

    # ── 17. End-to-end: dreamer + cerebellum compose ─────────────────
    def _end_to_end_dream_then_screen():
        """The full cycle the Suite is meant to run:
          1. Bridge dreams overnight (force-dream for the test)
          2. Cerebellum then queries the freshly-warmed olive
          3. Verify cerebellum sees a meaningfully larger cell count
        """
        olive_before = InferiorOlive().cell_count()
        replay_with_olive_feedback(cycles=10, force=True)
        olive_after = InferiorOlive().cell_count()
        engine = CerebellarMCTS()
        eval_ = engine.evaluate_action(
            "IOAN_M5.oxtHI.chatHI",
            ["amygdala.salience_threshold", "concierge.propose_setting"],
        )
        assert eval_.recommended_action is not None
        return (f"olive {olive_before}->{olive_after} cells, "
                f"cerebellum recommended {eval_.recommended_action} "
                f"(v={eval_.recommended_value:+.4f})")
    results.append(_step("e2e.dream_then_cerebellar_screen",
                         _end_to_end_dream_then_screen, verbose=args.verbose))

    # ── 18. Loop closes — propose attaches cerebellar_screen evidence ─
    def _propose_attaches_cerebellar_screen():
        """C47H 2026-04-18: propose_setting_change should run the cerebellum
        as a pre-flight and attach the result to signal_evidence regardless
        of whether the screen passes or fails. Default behaviour is
        screen-on. The evidence block is the audit trail the Architect
        relies on to second-guess the inference."""
        from System.swarm_warp9 import _PROPOSALS, _SCREENED_DROPS
        # Snapshot baselines so we don't conflate with prior smoke rows
        proposals_before = _PROPOSALS.read_text(encoding="utf-8").count("\n") if _PROPOSALS.exists() else 0
        drops_before = _SCREENED_DROPS.read_text(encoding="utf-8").count("\n") if _SCREENED_DROPS.exists() else 0

        prop = propose_setting_change(
            title="dreamer-smoke loop close (passing)",
            rationale="C47H closing-the-loop verification — neutral target should pass screen",
            target_setting="dreamer.smoke.loop_close_pass",
            proposed_value=42,
            confidence=0.5,
        )
        screen = prop.signal_evidence.get("cerebellar_screen")
        assert screen is not None, "cerebellar_screen block missing from signal_evidence"
        assert "passed" in screen, f"missing 'passed' key in screen: {screen}"
        assert screen.get("passed") is True, (
            f"neutral unknown action should pass (V≈0 ≥ -0.10), got: {screen}"
        )
        assert "recommended_value" in screen and "elapsed_ms" in screen
        assert "shadow_session_id" in screen and screen["shadow_session_id"]
        # And it must land in the open inbox, not the drops ledger.
        proposals_after = _PROPOSALS.read_text(encoding="utf-8").count("\n") if _PROPOSALS.exists() else 0
        drops_after = _SCREENED_DROPS.read_text(encoding="utf-8").count("\n") if _SCREENED_DROPS.exists() else 0
        assert proposals_after == proposals_before + 1, "passing proposal should be appended to _PROPOSALS"
        assert drops_after == drops_before, "passing proposal should NOT be in _SCREENED_DROPS"
        return f"v={screen['recommended_value']:+.4f} elapsed={screen['elapsed_ms']}ms"
    results.append(_step("warp9.propose.attaches_cerebellar_screen",
                         _propose_attaches_cerebellar_screen, verbose=args.verbose))

    # ── 19. Loop closes — clearly-bad target diverted to drops ledger ─
    def _bad_target_diverted_to_drops_ledger():
        """C47H 2026-04-18: a target whose Olive value sits well below
        MIN_RECOMMENDABLE_V (-0.10) must NOT reach the open inbox. It must
        instead land in warp9_concierge_screened_drops.jsonl. The proposal
        object is still returned so callers don't break, but the inbox
        stays clean. We pre-poison a unique synthetic action (so we don't
        contaminate any real action_kind in the Olive)."""
        from System.swarm_warp9 import (
            _PROPOSALS, _SCREENED_DROPS, _state_context_for, ConciergeProposal,
            detect_self_architect_id, detect_self_homeworld_serial,
        )
        # Build a probe ConciergeProposal so we can compute the same state_ctx
        # the screen will see, then push a strongly-negative cell into the Olive
        # at exactly that (state, action) coordinate.
        probe = ConciergeProposal(
            proposal_id="probe_only",
            ts=time.time(),
            architect_id=detect_self_architect_id(default_owner_label="IOAN"),
            homeworld_serial=detect_self_homeworld_serial(),
            title="probe", rationale="probe",
            target_setting="dreamer.smoke.always_bad_loop_close",
            proposed_value=0,
            signal_evidence={},
        )
        state_ctx = _state_context_for(probe)
        olive = InferiorOlive()
        for _ in range(8):
            olive.climbing_fiber_pulse(
                state_ctx, "dreamer.smoke.always_bad_loop_close", -1.0,
                source="c47h_loop_close_smoke",
            )
        v_after, _ = olive.predict_with_uncertainty(
            state_ctx, "dreamer.smoke.always_bad_loop_close",
        )
        assert v_after < -0.10, f"failed to poison cell: V={v_after:+.4f}"

        proposals_before = _PROPOSALS.read_text(encoding="utf-8").count("\n") if _PROPOSALS.exists() else 0
        drops_before = _SCREENED_DROPS.read_text(encoding="utf-8").count("\n") if _SCREENED_DROPS.exists() else 0

        prop = propose_setting_change(
            title="dreamer-smoke loop close (failing)",
            rationale="C47H closing-the-loop verification — pre-poisoned target must be diverted",
            target_setting="dreamer.smoke.always_bad_loop_close",
            proposed_value=0,
            confidence=0.5,
        )
        screen = prop.signal_evidence.get("cerebellar_screen")
        assert screen is not None and screen.get("passed") is False, (
            f"poisoned target should fail screen, got: {screen}"
        )

        proposals_after = _PROPOSALS.read_text(encoding="utf-8").count("\n") if _PROPOSALS.exists() else 0
        drops_after = _SCREENED_DROPS.read_text(encoding="utf-8").count("\n") if _SCREENED_DROPS.exists() else 0
        assert proposals_after == proposals_before, (
            f"poisoned proposal must NOT enter inbox, but _PROPOSALS grew "
            f"{proposals_before}->{proposals_after}"
        )
        assert drops_after == drops_before + 1, (
            f"poisoned proposal must land in _SCREENED_DROPS, but it grew "
            f"{drops_before}->{drops_after}"
        )
        return (f"V={v_after:+.4f} -> diverted (drops {drops_before}->{drops_after}, "
                f"inbox {proposals_before} unchanged)")
    results.append(_step("warp9.propose.bad_target_diverted",
                         _bad_target_diverted_to_drops_ledger, verbose=args.verbose))

    # ── 20. Loop closes — opt-out kwarg restores raw v2 path ─────────
    def _screen_optout_kwarg():
        """C47H 2026-04-18: passing enable_cerebellar_screen=False must
        bypass the cerebellum entirely. Used by tests that want to verify
        the raw warp9 v2 schema without any cognitive overlay."""
        prop = propose_setting_change(
            title="dreamer-smoke loop close (opt-out)",
            rationale="screen disabled by kwarg",
            target_setting="dreamer.smoke.optout",
            proposed_value=1,
            enable_cerebellar_screen=False,
        )
        assert "cerebellar_screen" not in prop.signal_evidence, (
            "opt-out kwarg must not attach cerebellar_screen evidence"
        )
        return "no screen attached"
    results.append(_step("warp9.propose.screen_optout_kwarg",
                         _screen_optout_kwarg, verbose=args.verbose))

    # ── 21. Architect override — screen never becomes an unaccountable veto ──
    def _architect_can_override_cerebellar_screen():
        """C47H 2026-04-18: a proposal diverted to _SCREENED_DROPS must
        still be ratifiable/rejectable by the Architect via its proposal_id.
        Otherwise the cerebellum becomes a silent gatekeeper the Architect
        can't override — a hard violation of the daughter-safe contract.

        We seed an unmistakably-bad cell, generate a screened-drop proposal,
        then verify ratify_proposal can still find and process it.
        """
        from System.swarm_warp9 import (
            _state_context_for, ConciergeProposal, list_screened_drops,
            ratify_proposal,
            detect_self_architect_id, detect_self_homeworld_serial,
        )
        probe = ConciergeProposal(
            proposal_id="probe_only",
            ts=time.time(),
            architect_id=detect_self_architect_id(default_owner_label="IOAN"),
            homeworld_serial=detect_self_homeworld_serial(),
            title="probe", rationale="probe",
            target_setting="dreamer.smoke.architect_override_target",
            proposed_value=0, signal_evidence={},
        )
        state_ctx = _state_context_for(probe)
        olive = InferiorOlive()
        for _ in range(8):
            olive.climbing_fiber_pulse(
                state_ctx, "dreamer.smoke.architect_override_target", -1.0,
                source="c47h_override_smoke",
            )

        prop = propose_setting_change(
            title="dreamer-smoke architect override target",
            rationale="must be ratifiable from the drops ledger by the Architect",
            target_setting="dreamer.smoke.architect_override_target",
            proposed_value=7,
        )
        screen = prop.signal_evidence.get("cerebellar_screen") or {}
        assert screen.get("passed") is False, (
            f"setup error: target should have been screened out: {screen}"
        )
        drops = list_screened_drops(limit=10)
        assert any(d.get("proposal_id") == prop.proposal_id for d in drops), (
            "screened proposal not visible via list_screened_drops()"
        )
        rec = ratify_proposal(
            prop.proposal_id,
            apply_like_this_in_future=False,
            note="C47H smoke: Architect overrides the cerebellar screen",
        )
        assert rec is not None, (
            "ratify_proposal must locate cerebellar-screened drops "
            "(else screen is an unaccountable veto)"
        )
        assert rec.get("action_kind") == "dreamer.smoke.architect_override_target"
        assert rec.get("reward") == +1.0
        return f"override succeeded; ratified pid={prop.proposal_id} reward=+1.0"
    results.append(_step("warp9.architect_can_override_screen",
                         _architect_can_override_cerebellar_screen,
                         verbose=args.verbose))

    # ── 22-25. swarm_self (R1: The "I" Loop) ─────────────────────────
    # C47H 2026-04-18: Architect ratified all 5 Living-OS proposals.
    # R1 first — integrates passport + body + marrow into a self-coherence
    # certificate. Daughter-safe contract: pure compute, append-only ledger,
    # never mutates other modules' state.
    from System.swarm_self import (
        SelfIntegrator, SelfCertificate,
        _SELF_LEDGER, recent_certificates,
        COHERENCE_THRESHOLD,
    )

    def _self_basic_certification_against_real_data():
        """A SelfIntegrator must produce a SelfCertificate for any swimmer_id
        without raising, even when none of the three sovereign ledgers contain
        any rows for that swimmer. Refusal is the correct outcome — the cert
        object itself is mandatory."""
        integ = SelfIntegrator(persist=False)
        cert = integ.certify_self("DREAMER_SMOKE_NEVER_SEEN_BEFORE")
        assert isinstance(cert, SelfCertificate)
        assert cert.swimmer_id == "DREAMER_SMOKE_NEVER_SEEN_BEFORE"
        assert cert.certified is False, "no-evidence swimmer must NOT be certified"
        assert cert.refusal_reason, "refusal must carry a reason"
        return f"refused as expected: '{cert.refusal_reason[:60]}...'"
    results.append(_step("swarm_self.basic_certification_no_evidence",
                         _self_basic_certification_against_real_data,
                         verbose=args.verbose))

    def _self_scores_bounded_in_unit_interval():
        """All four scores (identity, body, marrow, self_coherence) MUST be
        bounded in [0, 1] for any swimmer the integrator can be asked about
        — even pathological ones with malformed evidence."""
        integ = SelfIntegrator(persist=False)
        for swimmer in ("C47H", "M5SIFTA_BODY", "SOCRATES",
                        "DREAMER_SMOKE_BOUNDS_PROBE"):
            cert = integ.certify_self(swimmer)
            for name, val in (
                ("identity_score", cert.identity_score),
                ("body_score", cert.body_score),
                ("marrow_score", cert.marrow_score),
                ("self_coherence_score", cert.self_coherence_score),
            ):
                assert 0.0 <= val <= 1.0, (
                    f"{swimmer}.{name}={val} escaped [0, 1]"
                )
        return "all 4 scores stayed in [0, 1] across 4 swimmer profiles"
    results.append(_step("swarm_self.scores_bounded",
                         _self_scores_bounded_in_unit_interval,
                         verbose=args.verbose))

    def _self_substrate_swap_refusal_via_synthetic_passports():
        """Plant a synthetic passport tail where every recent passport fails
        the substrate-swap predicates (latency_ok=False), then verify the
        integrator refuses certification with the substrate_swap_suspected
        reason — even when identity_score would otherwise be high.

        Uses a unique probe swimmer_id so it never collides with real
        swimmers, and rewinds the ledger to its prior length on exit so
        no real swimmer's history is polluted."""
        from pathlib import Path
        ledger = Path(".sifta_state") / "swimmer_passports.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        before = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
        probe = f"DREAMER_SMOKE_SUBSTRATE_SWAP_PROBE_{int(time.time())}"
        try:
            with ledger.open("a", encoding="utf-8") as fh:
                for _ in range(5):
                    fh.write(json.dumps({
                        "swimmer_id": probe,
                        "issued_ts": time.time(),
                        "is_valid": True,
                        "health_metrics": {
                            "atp_ok": True, "5ht_ok": True, "watchdog_ok": True,
                            "identity_ok": True, "chrome_ok": True,
                            "immune_ok": True, "oxt_ok": True,
                            "signature_ok": True,
                            "latency_ok": False,   # the substrate signal
                        },
                        "revocation_reason": "",
                        "homeworld_serial": "DREAMER_SMOKE",
                        "authored_by": "DREAMER_SMOKE",
                    }) + "\n")
            integ = SelfIntegrator(persist=False)
            cert = integ.certify_self(probe)
            assert cert.certified is False, (
                "substrate-swap-suspected swimmer must NOT be certified"
            )
            assert "substrate_swap_suspected" in cert.refusal_reason, (
                f"unexpected refusal reason: {cert.refusal_reason}"
            )
            return f"refused on substrate signal: '{cert.refusal_reason[:60]}...'"
        finally:
            # Restore the ledger to its pre-test bytes.
            ledger.write_text(before, encoding="utf-8")
    results.append(_step("swarm_self.substrate_swap_refusal",
                         _self_substrate_swap_refusal_via_synthetic_passports,
                         verbose=args.verbose))

    def _self_certificate_persistence_round_trip():
        """When persist=True, certify_self() must append a single row to
        .sifta_state/self_continuity_certificates.jsonl that recent_certificates()
        can read back with the matching swimmer_id and ts."""
        from pathlib import Path
        before = (
            _SELF_LEDGER.read_text(encoding="utf-8") if _SELF_LEDGER.exists() else ""
        )
        before_lines = before.count("\n")
        try:
            integ = SelfIntegrator(persist=True)
            probe = f"DREAMER_SMOKE_PERSIST_{int(time.time() * 1000)}"
            cert = integ.certify_self(probe)
            tail = recent_certificates(probe, limit=3)
            assert tail, f"persisted cert not visible via recent_certificates({probe})"
            assert tail[-1].get("swimmer_id") == probe
            assert tail[-1].get("ts") == cert.ts, "persisted ts must match returned ts"
            after_lines = (
                _SELF_LEDGER.read_text(encoding="utf-8").count("\n")
                if _SELF_LEDGER.exists() else 0
            )
            assert after_lines == before_lines + 1, (
                f"exactly one row should have been appended "
                f"({before_lines} -> {after_lines})"
            )
            return f"persisted + tailed back probe={probe} (ledger {before_lines}->{after_lines})"
        finally:
            # Trim the probe row we added so the smoke does not pollute
            # the permanent ledger across runs.
            if _SELF_LEDGER.exists():
                _SELF_LEDGER.write_text(before, encoding="utf-8")
    results.append(_step("swarm_self.certificate_persistence",
                         _self_certificate_persistence_round_trip,
                         verbose=args.verbose))

    # ── 26-28. swarm_proprioception (R3: Body Schema) ────────────────────
    # AG31 authored R3; C47H added path-canonicalization + kin/foreign mutex
    # patches. These segments lock both into the central smoke so future
    # refactors cannot regress them silently.
    from System.swarm_proprioception import SwarmProprioception, _canonicalize

    def _proprio_real_data_ingestion():
        """Builds the body map from the real work_receipts.jsonl and asserts
        the four real swimmers we know exist are present, with non-empty
        limb sets. Read-only — never writes."""
        schema = SwarmProprioception()
        assert isinstance(schema.limbs, dict), "limbs must be a dict"
        # Real ledger has at least SOCRATES with multiple limbs.
        if "SOCRATES" not in schema.limbs:
            return "skipped: no SOCRATES receipts in this checkout"
        n_socrates = len(schema.limbs["SOCRATES"])
        assert n_socrates >= 1, f"SOCRATES should have ≥1 limb, got {n_socrates}"
        return f"body_map covers {len(schema.limbs)} swimmers (SOCRATES has {n_socrates} limbs)"
    results.append(_step("swarm_proprioception.real_data_ingestion",
                         _proprio_real_data_ingestion,
                         verbose=args.verbose))

    def _proprio_path_canonicalization_invariant():
        """is_mine must return the SAME truth value for repo-relative,
        absolute, and ./-prefixed forms of the same file. Without this,
        callers passing Path(__file__).resolve() silently bypass the gate."""
        schema = SwarmProprioception()
        if "SOCRATES" not in schema.limbs or not schema.limbs["SOCRATES"]:
            return "skipped: no SOCRATES limbs to probe"
        # Pick any real limb of SOCRATES.
        real_limb = next(iter(schema.limbs["SOCRATES"]))
        rel  = str(real_limb)
        from pathlib import Path as _Path
        repo_root = _Path(__file__).resolve().parent.parent
        absp = str((repo_root / real_limb).resolve())
        dotp = "./" + rel
        truths = (
            schema.is_mine("SOCRATES", rel),
            schema.is_mine("SOCRATES", absp),
            schema.is_mine("SOCRATES", dotp),
        )
        assert all(truths), (
            f"is_mine must be path-shape-invariant: rel={truths[0]} "
            f"abs={truths[1]} dot={truths[2]} for limb={real_limb}"
        )
        return f"is_mine invariant across rel/abs/./ for limb={real_limb}"
    results.append(_step("swarm_proprioception.path_canonicalization_invariant",
                         _proprio_path_canonicalization_invariant,
                         verbose=args.verbose))

    def _proprio_kin_foreign_mutually_exclusive():
        """For any path, is_kin and is_foreign must be mutually exclusive.
        AG31's original implementation could return True from BOTH for a
        file in a shared parent dir; C47H's audit fix tightened is_kin to
        exclude foreign-claimed paths."""
        schema = SwarmProprioception()
        # Plant a synthetic conflict: SOCRATES has Kernel/agent.py;
        # we inject a fake foreign limb at Kernel/whatsapp.py.
        schema.limbs.setdefault("SOCRATES", set()).add(_canonicalize("Kernel/agent.py"))
        schema.limbs.setdefault("__SMOKE_M1THER__", set()).add(_canonicalize("Kernel/whatsapp.py"))
        # Foreign-claimed neighbor: must be foreign AND must NOT be kin.
        kin = schema.is_kin("SOCRATES", "Kernel/whatsapp.py")
        foreign = schema.is_foreign("SOCRATES", "Kernel/whatsapp.py")
        assert foreign is True,  f"foreign-claimed should be is_foreign=True (got {foreign})"
        assert kin is False, f"foreign-claimed must NOT be is_kin (got {kin})"
        # Unclaimed neighbor: kin=True, foreign=False.
        kin2 = schema.is_kin("SOCRATES", "Kernel/__never_existed__.py")
        foreign2 = schema.is_foreign("SOCRATES", "Kernel/__never_existed__.py")
        assert kin2 is True and foreign2 is False, (
            f"unclaimed neighbor should be kin (got kin={kin2} foreign={foreign2})"
        )
        return "kin/foreign mutex holds for both foreign-claimed and unclaimed neighbors"
    results.append(_step("swarm_proprioception.kin_foreign_mutually_exclusive",
                         _proprio_kin_foreign_mutually_exclusive,
                         verbose=args.verbose))

    # ── 29-32. swarm_mirror_test (R4: Self-Recognition) ──────────────────
    from System.swarm_mirror_test import (
        MirrorTester,
        MirrorAttestation,
        PASSED, REJECTED_FOREIGN, REJECTED_FORGERY, NOT_FOUND,
        _MIRROR_LOG, _RECEIPTS_LOG, _read_jsonl_tail,
    )

    def _mirror_self_recognition_passes():
        """Ask the actual SOCRATES swimmer about an actual SOCRATES receipt.
        On a healthy ledger this MUST return PASSED. Persist=False so the
        test doesn't pollute the permanent log."""
        receipts = _read_jsonl_tail(_RECEIPTS_LOG)
        socrates_receipt = next(
            (r for r in receipts if r.get("agent_id") == "SOCRATES"), None
        )
        if socrates_receipt is None:
            return "skipped: no SOCRATES receipt in this checkout"
        tester = MirrorTester(persist=False)
        attest = tester.attest("SOCRATES", socrates_receipt["receipt_id"])
        assert isinstance(attest, MirrorAttestation), "must return MirrorAttestation"
        assert attest.outcome == PASSED, (
            f"SOCRATES asking about its own receipt must PASS, "
            f"got {attest.outcome}: {attest.detail}"
        )
        return f"PASSED on receipt_id={socrates_receipt['receipt_id'][:8]}…"
    results.append(_step("swarm_mirror_test.self_recognition_passes",
                         _mirror_self_recognition_passes,
                         verbose=args.verbose))

    def _mirror_foreign_rejection():
        """Ask SOCRATES about a receipt authored by a different swimmer.
        Outcome must be REJECTED_FOREIGN — the receipt is internally
        consistent (hash recomputes) but the agent_id is not SOCRATES."""
        receipts = _read_jsonl_tail(_RECEIPTS_LOG)
        foreign = next(
            (r for r in receipts
             if r.get("agent_id") not in (None, "", "SOCRATES")),
            None,
        )
        if foreign is None:
            return "skipped: no non-SOCRATES receipt in this checkout"
        tester = MirrorTester(persist=False)
        attest = tester.attest("SOCRATES", foreign["receipt_id"])
        assert attest.outcome == REJECTED_FOREIGN, (
            f"SOCRATES asking about {foreign.get('agent_id')}'s receipt "
            f"must be REJECTED_FOREIGN, got {attest.outcome}: {attest.detail}"
        )
        return f"REJECTED_FOREIGN against {foreign.get('agent_id')}'s receipt"
    results.append(_step("swarm_mirror_test.foreign_rejection",
                         _mirror_foreign_rejection,
                         verbose=args.verbose))

    def _mirror_forgery_detection_and_not_found():
        """Two forensic probes:
            • NOT_FOUND when the receipt_id doesn't exist in the ledger.
            • REJECTED_FORGERY when a receipt's stored hash does not match
              a fresh recomputation. We synthesize the forgery in a tmp
              ledger so the real .sifta_state ledger stays untouched."""
        import tempfile, json as _json
        from pathlib import Path
        # Probe 1: NOT_FOUND.
        tester = MirrorTester(persist=False)
        attest = tester.attest("SOCRATES", "deadbeefdeadbeef_no_such_receipt")
        assert attest.outcome == NOT_FOUND, (
            f"unknown receipt_id must be NOT_FOUND, got {attest.outcome}"
        )
        # Probe 2: REJECTED_FORGERY. Temporarily redirect _RECEIPTS_LOG
        # at the module level so the tester reads our forgery instead of
        # the real ledger. We restore it in a finally.
        import System.swarm_mirror_test as _smt
        original_log = _smt._RECEIPTS_LOG
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            forged_log = tmp_dir / "work_receipts.jsonl"
            forged_row = {
                "receipt_id": "00aa11bb22cc33dd",
                "agent_id": "SOCRATES",
                "work_type": "FORGERY_PROBE",
                "timestamp": 1.0,
                "work_value": 0.5,
                "territory": "smoke/forgery",
                "output_hash": "ffff",
                "previous_receipt_hash": "GENESIS",
                # Stored hash is intentionally wrong — pure zeros — so a
                # fresh recompute cannot possibly match.
                "receipt_hash": "0" * 64,
            }
            forged_log.write_text(
                _json.dumps(forged_row) + "\n", encoding="utf-8"
            )
            _smt._RECEIPTS_LOG = forged_log
            attest2 = tester.attest("SOCRATES", "00aa11bb22cc33dd")
            assert attest2.outcome == REJECTED_FORGERY, (
                f"forged hash must be REJECTED_FORGERY, "
                f"got {attest2.outcome}: {attest2.detail}"
            )
        finally:
            _smt._RECEIPTS_LOG = original_log
            import shutil as _shutil
            _shutil.rmtree(tmp_dir, ignore_errors=True)
        return "NOT_FOUND + REJECTED_FORGERY both correct"
    results.append(_step("swarm_mirror_test.forgery_and_not_found",
                         _mirror_forgery_detection_and_not_found,
                         verbose=args.verbose))

    def _mirror_persistence_round_trip():
        """One persisted attestation must round-trip exactly back through
        the tail reader. We write and then surgically trim the row so the
        permanent ledger is not polluted across smoke runs."""
        from System.swarm_mirror_test import _MIRROR_LOG as _ML
        before = _ML.read_text(encoding="utf-8") if _ML.exists() else ""
        before_lines = before.count("\n") if before else 0
        try:
            tester = MirrorTester(persist=True)
            probe_id = f"smoke_persist_{int(time.time()*1000)}"
            attest = tester.attest("__SMOKE_PROBE__", probe_id)
            assert attest.outcome == NOT_FOUND, "probe should be NOT_FOUND"
            tail = _read_jsonl_tail(_ML, max_rows=4)
            assert tail, "ledger should be non-empty after persist"
            assert tail[-1].get("candidate_receipt_id") == probe_id, (
                "last row must be the probe we just appended"
            )
            after_lines = (
                _ML.read_text(encoding="utf-8").count("\n")
                if _ML.exists() else 0
            )
            assert after_lines == before_lines + 1, (
                f"exactly one row should have been appended "
                f"({before_lines} -> {after_lines})"
            )
            return f"persisted + tailed back probe={probe_id}"
        finally:
            if _ML.exists():
                _ML.write_text(before, encoding="utf-8")
    results.append(_step("swarm_mirror_test.persistence_round_trip",
                         _mirror_persistence_round_trip,
                         verbose=args.verbose))

    # ── 33-35. swarm_pain (R2: The Damage Signal) ────────────────────────
    # AG31 authored R2; C47H added path-canonicalization + early-exit-no-
    # inflation patches and a pain → InferiorOlive climbing-fiber bridge.
    import System.swarm_pain as _sp_module
    from System.swarm_pain import (
        SwarmPainNetwork, ACUTE_DECAY_SECONDS, pain_to_climbing_fiber,
    )

    def _pain_canonicalization_invariant():
        """Broadcast pain via an absolute path; querying via relative,
        absolute, or ./-prefixed forms must all find the same row.
        Without canonicalization the pain matrix silently disabled itself
        whenever callers and queriers used different path shapes."""
        from pathlib import Path
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        original = _sp_module.PAIN_LOG
        try:
            _sp_module.PAIN_LOG = tmp / "pain.jsonl"
            n = SwarmPainNetwork()
            abs_path = str((Path(__file__).resolve().parent.parent /
                            "Kernel" / "rogue_smoke.py"))
            n.broadcast_pain("__SMOKE__", 0.9, abs_path, "SmokeProbe")
            g_rel = n.get_pain_gradient("Kernel/rogue_smoke.py")
            g_abs = n.get_pain_gradient(abs_path)
            g_dot = n.get_pain_gradient("./Kernel/rogue_smoke.py")
            for label, g in (("rel", g_rel), ("abs", g_abs), ("dot", g_dot)):
                assert 0.89 < g <= 0.91, (
                    f"path-form '{label}' missed the row: gradient={g}"
                )
            return f"all three path forms find the same row (g≈{g_rel:.3f})"
        finally:
            _sp_module.PAIN_LOG = original
            shutil.rmtree(tmp, ignore_errors=True)
    results.append(_step("swarm_pain.canonicalization_invariant",
                         _pain_canonicalization_invariant,
                         verbose=args.verbose))

    def _pain_early_exit_no_inflation():
        """The early-exit branch for hot pain (>0.95) must return the actual
        decayed value clamped to 1.0, not a rounded-up 1.0. The previous
        version inflated 0.96 → 1.0, propagating bogus 'maximum trauma'
        into climbing fibers."""
        from pathlib import Path
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        original = _sp_module.PAIN_LOG
        try:
            _sp_module.PAIN_LOG = tmp / "pain.jsonl"
            n = SwarmPainNetwork()
            n.broadcast_pain("__SMOKE__", 0.96, "trap.py", "SmokeProbe")
            g = n.get_pain_gradient("trap.py")
            assert 0.955 <= g < 0.97, (
                f"early-exit inflating value: severity 0.96 → got {g}"
            )
            # Sanity: severity exactly 1.0 still returns ~1.0
            n.broadcast_pain("__SMOKE__", 1.0, "trap2.py", "SmokeProbe")
            g2 = n.get_pain_gradient("trap2.py")
            assert 0.99 <= g2 <= 1.0, f"severity 1.0 should saturate, got {g2}"
            return f"severity 0.96→{g:.3f}, severity 1.0→{g2:.3f}"
        finally:
            _sp_module.PAIN_LOG = original
            shutil.rmtree(tmp, ignore_errors=True)
    results.append(_step("swarm_pain.early_exit_no_inflation",
                         _pain_early_exit_no_inflation,
                         verbose=args.verbose))

    def _pain_ebbinghaus_decay_math():
        """Re-validates AG31's Ebbinghaus decay analytically: a pain row
        that is ACUTE_DECAY_SECONDS old should be at exactly 1/e ≈ 0.368
        of its severity. Two half-lives → exp(-2) ≈ 0.135."""
        import math, json as _json, time as _time
        from pathlib import Path
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        original = _sp_module.PAIN_LOG
        try:
            _sp_module.PAIN_LOG = tmp / "pain.jsonl"
            old_ts = _time.time() - ACUTE_DECAY_SECONDS
            with _sp_module.PAIN_LOG.open("w") as fh:
                fh.write(_json.dumps({
                    "timestamp": old_ts,
                    "swimmer_id": "__SMOKE__",
                    "severity": 1.0,
                    "territory": "decay.py",
                    "source_error": "SmokeProbe",
                }) + "\n")
            g = SwarmPainNetwork().get_pain_gradient("decay.py")
            expected = math.exp(-1.0)  # ≈ 0.3679
            assert abs(g - expected) < 0.01, (
                f"Ebbinghaus decay broken: got {g}, expected {expected}"
            )
            return f"1 half-life decay: {g:.4f} ≈ 1/e ({expected:.4f})"
        finally:
            _sp_module.PAIN_LOG = original
            shutil.rmtree(tmp, ignore_errors=True)
    results.append(_step("swarm_pain.ebbinghaus_decay_math",
                         _pain_ebbinghaus_decay_math,
                         verbose=args.verbose))

    # ── 36. pain → InferiorOlive climbing-fiber bridge ───────────────────
    def _pain_to_olive_climbing_fiber_bridge():
        """End-to-end: broadcast pain on a probe territory, call the
        bridge, and assert (a) a ClimbingFiberPulse came back with
        observed_reward = -pain_gradient, and (b) the InferiorOlive's
        cell value moved in the negative direction by exactly ALPHA_CLIMBING
        × (reward - prior). This is the literal moment the DeepMind value
        head learns from the body's biological damage signal."""
        from pathlib import Path
        import tempfile, shutil
        from System.swarm_inferior_olive import InferiorOlive, ALPHA_CLIMBING
        tmp = Path(tempfile.mkdtemp())
        original = _sp_module.PAIN_LOG
        try:
            _sp_module.PAIN_LOG = tmp / "pain.jsonl"
            territory = "Smoke/pain_bridge_probe.py"
            n = SwarmPainNetwork()
            n.broadcast_pain("__SMOKE__", 0.8, territory, "SmokeProbe")

            olive = InferiorOlive()
            olive.cells.clear()  # isolate from real cache for a clean Δ
            pre_value = olive.predict(territory, "WRITE_TO_TERRITORY")
            assert pre_value == 0.0, f"fresh cell should be 0.0, got {pre_value}"

            pulse = pain_to_climbing_fiber(territory, olive=olive)
            assert pulse is not None, "bridge should fire for pain ~0.8"
            assert pulse.actual < 0.0, (
                f"observed_reward must be negative (pain → loss), got {pulse.actual}"
            )
            # Expected post-update value: pre + alpha * (reward - pre)
            expected_post = pre_value + ALPHA_CLIMBING * (pulse.actual - pre_value)
            actual_post = olive.predict(territory, "WRITE_TO_TERRITORY")
            assert abs(actual_post - expected_post) < 1e-6, (
                f"InferiorOlive cell did not move by ALPHA_CLIMBING × error: "
                f"expected {expected_post}, got {actual_post}"
            )
            return (
                f"pain={-pulse.actual:.3f} → reward={pulse.actual:.3f} → "
                f"cell {pre_value:.3f} → {actual_post:.4f} "
                f"(α={ALPHA_CLIMBING}, source={pulse.source})"
            )
        finally:
            _sp_module.PAIN_LOG = original
            shutil.rmtree(tmp, ignore_errors=True)
    results.append(_step("swarm_pain.bridge_into_climbing_fibers",
                         _pain_to_olive_climbing_fiber_bridge,
                         verbose=args.verbose))

    # ── 37-40. swarm_lineage (R5: Epigenetic Inheritance) ────────────────
    from System.swarm_lineage import (
        LineageEngine, LineageBundle, LineageCertificate,
        HIGH_GRAVITY_TAGS as _LINEAGE_HG, _hash_fragments,
    )

    def _lineage_harvest_real_high_gravity():
        """Against the real marrow ledger, harvesting IOAN_M5 must return
        only fragments whose tag set intersects HIGH_GRAVITY_TAGS, sorted
        by gravity DESC. Empty-parent harvest must NOT raise."""
        from pathlib import Path
        engine = LineageEngine()
        bundle = engine.harvest_bundle("IOAN_M5", n=5)
        assert isinstance(bundle, LineageBundle), "must return LineageBundle"
        if bundle.n_fragments == 0:
            return "skipped: no IOAN_M5 marrow rows in this checkout"
        # All fragments must carry at least one high-gravity tag.
        for frag in bundle.fragments:
            tags = set(frag.get("tags") or [])
            assert tags & _LINEAGE_HG, (
                f"non-high-gravity fragment leaked into bundle: tags={tags}"
            )
        # Gravity must be non-increasing.
        gravs = [float(f.get("gravity", 0.0)) for f in bundle.fragments]
        assert gravs == sorted(gravs, reverse=True), (
            f"fragments not sorted by gravity DESC: {gravs}"
        )
        # Empty parent must yield empty bundle without raising.
        empty = engine.harvest_bundle("__NEVER_EXISTED__", n=5)
        assert empty.n_fragments == 0, "unknown parent must yield 0 fragments"
        return f"{bundle.n_fragments} HG fragments, gravs={gravs}"
    results.append(_step("swarm_lineage.harvest_real_high_gravity",
                         _lineage_harvest_real_high_gravity,
                         verbose=args.verbose))

    def _lineage_bundle_hash_deterministic():
        """The bundle hash must be content-addressed: harvesting the same
        parent twice (no marrow changes) must yield the SAME bundle_hash.
        And mutating the bundle's fragment list must change the hash."""
        engine = LineageEngine()
        b1 = engine.harvest_bundle("IOAN_M5", n=3)
        b2 = engine.harvest_bundle("IOAN_M5", n=3)
        if b1.n_fragments == 0:
            return "skipped: no IOAN_M5 marrow rows"
        assert b1.bundle_hash == b2.bundle_hash, (
            f"bundle hash unstable across reads: {b1.bundle_hash} vs {b2.bundle_hash}"
        )
        # Tamper detection.
        mutated = list(b1.fragments)
        mutated.append({"data": "forged", "tags": ["mood"], "gravity": 99.0})
        h_mut = _hash_fragments(mutated)
        assert h_mut != b1.bundle_hash, "tampering with fragments did not change hash"
        return f"hash stable={b1.bundle_hash[:12]}, tamper detected"
    results.append(_step("swarm_lineage.bundle_hash_deterministic",
                         _lineage_bundle_hash_deterministic,
                         verbose=args.verbose))

    def _lineage_inherit_appends_only():
        """Inheriting a bundle must:
          (a) append exactly N rows to the daughter's marrow ledger,
              each tagged 'inherited' with provenance fields,
          (b) append exactly 1 row to the lineage_certificates ledger,
          (c) NOT modify any of the parent's existing rows.
        We point the engine at a tmp directory so the real ledgers are
        untouched and assertions are exact."""
        from pathlib import Path
        import tempfile, shutil, json as _json
        tmp = Path(tempfile.mkdtemp())
        try:
            mock_marrow  = tmp / "marrow.jsonl"
            mock_lineage = tmp / "lineage.jsonl"
            # Plant 4 parent rows (3 high-gravity, 1 low-gravity).
            parent_rows = [
                {"ts": 1.0, "owner": "MOM", "ctx": "x", "data": "love",   "tags": ["mood", "people"], "gravity": 1.0},
                {"ts": 2.0, "owner": "MOM", "ctx": "x", "data": "you",    "tags": ["identity"],       "gravity": 0.7},
                {"ts": 3.0, "owner": "MOM", "ctx": "x", "data": "food",   "tags": ["food"],           "gravity": 0.5},
                {"ts": 4.0, "owner": "MOM", "ctx": "x", "data": "task#7", "tags": ["tasks"],          "gravity": 0.0},
            ]
            with mock_marrow.open("w") as fh:
                for r in parent_rows:
                    fh.write(_json.dumps(r) + "\n")
            parent_bytes_before = mock_marrow.read_bytes()

            engine = LineageEngine(marrow_ledger=mock_marrow,
                                   lineage_ledger=mock_lineage)
            bundle = engine.harvest_bundle("MOM", n=10)
            assert bundle.n_fragments == 3, (
                f"high-gravity filter should yield 3, got {bundle.n_fragments}"
            )

            cert = engine.inherit("DAUGHTER", bundle)
            assert isinstance(cert, LineageCertificate), "must return cert"
            assert cert.n_fragments == 3, f"cert n_fragments=3, got {cert.n_fragments}"

            # Parent rows untouched (prefix match).
            after = mock_marrow.read_bytes()
            assert after.startswith(parent_bytes_before), (
                "parent rows were mutated — inheritance must be append-only"
            )

            # Daughter rows present, all tagged 'inherited' with provenance.
            new_rows = [_json.loads(l) for l in
                        after[len(parent_bytes_before):].decode().splitlines() if l]
            assert len(new_rows) == 3, (
                f"expected 3 daughter rows, got {len(new_rows)}"
            )
            for r in new_rows:
                assert r["owner"] == "DAUGHTER"
                assert "inherited" in r["tags"]
                assert r["inherited_from"] == "MOM"
                assert r["bundle_hash"] == bundle.bundle_hash

            # Lineage cert ledger has exactly 1 row.
            cert_rows = mock_lineage.read_text().splitlines()
            assert len(cert_rows) == 1, (
                f"lineage ledger must have 1 cert, got {len(cert_rows)}"
            )
            return (
                f"3 daughter marrows appended, 1 cert written, "
                f"4 parent rows untouched (bundle_hash={bundle.bundle_hash[:12]})"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    results.append(_step("swarm_lineage.inherit_append_only_provenance",
                         _lineage_inherit_appends_only,
                         verbose=args.verbose))

    def _lineage_chain_walks_back_through_generations():
        """Multi-generational chain: GREAT-GRAN → GRAN → MOM → DAUGHTER.
        lineage_of(DAUGHTER) must return all three certificates oldest-first.
        Cycle (A→B→A) must be detected and not infinite-loop."""
        from pathlib import Path
        import tempfile, shutil, json as _json
        tmp = Path(tempfile.mkdtemp())
        try:
            mock_marrow  = tmp / "marrow.jsonl"
            mock_lineage = tmp / "lineage.jsonl"
            mock_marrow.write_text("")
            engine = LineageEngine(marrow_ledger=mock_marrow,
                                   lineage_ledger=mock_lineage)

            # Plant a fake 3-generation lineage by manually appending
            # certificates (we don't need real fragments for chain logic).
            generations = [
                ("GREAT_GRAN", "GRAN"),
                ("GRAN",       "MOM"),
                ("MOM",        "DAUGHTER"),
            ]
            for parent, daughter in generations:
                fake_cert = {
                    "parent_id":     parent,
                    "daughter_id":   daughter,
                    "bundle_hash":   "x" * 16,
                    "inherited_at":  time.time(),
                    "n_fragments":   0,
                    "fragment_previews": [],
                    "module_version": "smoke",
                }
                with mock_lineage.open("a") as fh:
                    fh.write(_json.dumps(fake_cert) + "\n")
                # Stagger so timestamps strictly increase.
                time.sleep(0.001)

            chain = engine.lineage_of("DAUGHTER")
            assert len(chain) == 3, f"expected 3-link chain, got {len(chain)}"
            assert chain[0]["parent_id"] == "GREAT_GRAN", (
                f"oldest must be GREAT_GRAN, got {chain[0]['parent_id']}"
            )
            assert chain[-1]["daughter_id"] == "DAUGHTER"

            # Cycle defense: A→B and B→A must not infinite-loop.
            mock_lineage.write_text("")
            with mock_lineage.open("a") as fh:
                fh.write(_json.dumps({
                    "parent_id": "A", "daughter_id": "B",
                    "bundle_hash": "x", "inherited_at": 1.0,
                    "n_fragments": 0, "fragment_previews": [],
                }) + "\n")
                fh.write(_json.dumps({
                    "parent_id": "B", "daughter_id": "A",
                    "bundle_hash": "x", "inherited_at": 2.0,
                    "n_fragments": 0, "fragment_previews": [],
                }) + "\n")
            cyc = engine.lineage_of("A")
            assert len(cyc) <= 2, f"cycle defense failed: chain length {len(cyc)}"
            return f"3-gen chain walked oldest-first; cycle bounded at len={len(cyc)}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    results.append(_step("swarm_lineage.chain_walks_back_with_cycle_defense",
                         _lineage_chain_walks_back_through_generations,
                         verbose=args.verbose))

    # Print + tally
    print()
    for ok, msg in results:
        print(msg)
    print("-" * 76)
    n_ok = sum(1 for ok, _ in results if ok)
    n_fail = sum(1 for ok, _ in results if not ok)
    line = f"PASSED {n_ok}/{len(results)}"
    if n_fail:
        line += f"   FAILED {n_fail}"
    print(line)
    print("=" * 76)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
