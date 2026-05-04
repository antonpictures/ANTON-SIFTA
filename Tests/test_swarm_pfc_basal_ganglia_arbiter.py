import json
from pathlib import Path
import pytest
from System.swarm_pfc_basal_ganglia_arbiter import PFCBasalGangliaArbiter
from System import swarm_active_inference_world_model as wm

def test_convert_replay_to_option_and_select(tmp_path):
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    
    # 1. Convert
    arbiter.convert_replay_to_option(["co_watch", "research_depth"], "collaborative_research_watch")
    assert "collaborative_research_watch" in arbiter.options
    
    # 2. Select under uncertainty
    # High cost, high risk should inhibit
    arbiter.options["collaborative_research_watch"]["cost"] = 0.8
    arbiter.options["collaborative_research_watch"]["risk"] = 0.5
    arbiter.options["collaborative_research_watch"]["uncertainty"] = 0.2
    arbiter.options["collaborative_research_watch"]["q_value"] = 0.3
    
    action, score, details = arbiter.select_action(
        task_id="test_task_1",
        available_options=["collaborative_research_watch"],
        state_features={"time_of_day": 14.5}
    )
    # Score should be negative, hence inhibited to "idle"
    assert action == "idle", "High cost/risk should result in lateral inhibition to idle"
    
def test_transfer_gain_logging(tmp_path):
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    arbiter.convert_replay_to_option(["co_watch"], "test_option")
    
    # Simulate a new task generalization trial
    # architect_reward = 1.0 (positive transfer)
    # reward_without_reused_option = 0.2
    
    trace = arbiter.update_generalization_trial(
        task_id="generalization_task_X",
        option_selected="test_option",
        state_features={"novelty": 0.9},
        actual_outcome={"valence": 0.8},
        architect_reward=1.0,
        reward_without_reused_option=0.2
    )
    
    # 3. Prove Transfer Gain > 0
    assert trace["transfer_gain"] == 0.8
    assert trace["transfer_gain"] > 0, "Transfer gain must be positive"
    assert trace["kind"] == "GENERALIZATION_TRIAL"
    
    # Read from jsonl
    log_path = tmp_path / "pfc_basal_ganglia_arbiter.jsonl"
    with open(log_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        written_trace = json.loads(lines[0])
        assert written_trace["transfer_gain"] == 0.8
        assert written_trace["td_error"] > 0

def test_option_ledger_persistence(tmp_path):
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    arbiter.convert_replay_to_option(["a", "b"], "persisted_opt")
    
    # Reload
    arbiter2 = PFCBasalGangliaArbiter(root=tmp_path)
    assert "persisted_opt" in arbiter2.options
    assert arbiter2.options["persisted_opt"]["source_skills"] == ["a", "b"]


def test_select_action_consumes_event_133_world_model(tmp_path):
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    state = {"attention": 0.7, "energy": 0.5}
    good = "direct_answer"
    bad = "generic_menu"
    context_good = {"task_id": "active_inference_task", "task_family": "pfc_basal_ganglia", "option": good}
    context_bad = {"task_id": "active_inference_task", "task_family": "pfc_basal_ganglia", "option": bad}

    wm.observe(state, {"name": good, "option": good}, context_good, {"attention": 0.9}, reward=0.9, harm=0.0, root=tmp_path)
    wm.observe(state, {"name": bad, "option": bad}, context_bad, {"attention": 0.2}, reward=0.1, harm=0.8, root=tmp_path)

    action, score, details = arbiter.select_action(
        task_id="active_inference_task",
        available_options=[bad, good],
        state_features=state,
        owner_signal=0.0,
        min_dwell_time=0.0,
    )

    assert action == good
    assert details["truth_label"] == "PFC_BG_ACTION_SELECTION"
    assert details["details"]["world_model"]["source"] == "event_133_world_model"
    assert details["details"]["g_vector"] < 0.5

# ============================================================
# PART 2: Biological Steering (§10.14.28)
# DAM Stage 2 blocks, TME Escape drops threshold, NA>0.8 drives exploration
# ============================================================

def test_biological_steering_dam_stage2_blocks_new_gates(tmp_path):
    """DAM Stage 2 blocks options that suggest new gates, increases risk aversion."""
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    
    # "explore_raw" should be blocked because it suggests a new gate
    options = ["safe_routine", "explore_raw"]
    arbiter._save_option("safe_routine", {"q_value": 0.8, "uncertainty": 0.1, "risk": 0.1, "cost": 0.1})
    arbiter._save_option("explore_raw", {"q_value": 0.9, "uncertainty": 0.5, "risk": 0.5, "cost": 0.1})
    
    # Without DAM Stage 2
    winner_normal, score, selection = arbiter.select_action(
        task_id="test",
        available_options=options,
        state_features={},
        dam_stage=0,
        world_model="dummy"
    )
    # With DAM Stage 2
    winner_inflamed, _, selection_inflamed = arbiter.select_action(
        task_id="test",
        available_options=options,
        state_features={},
        dam_stage=2,
        world_model="dummy"
    )
    
    assert "explore_raw" in selection["all_details"]
    assert "explore_raw" not in selection_inflamed["all_details"], "explore_raw should be blocked"
    assert selection_inflamed["biological_steering"]["risk_weight"] == 2.0


def test_biological_steering_tme_escape_desperation(tmp_path):
    """TME ESCAPE halves risk_weight and cost_weight."""
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    options = ["high_cost_risky", "safe"]
    arbiter._save_option("high_cost_risky", {"q_value": 0.9, "uncertainty": 0.1, "risk": 0.8, "cost": 0.8})
    arbiter._save_option("safe", {"q_value": 0.5, "uncertainty": 0.1, "risk": 0.1, "cost": 0.1})
    
    # Normal: high risk and cost penalizes heavily
    win_normal, _, sel_normal = arbiter.select_action("test", options, {}, world_model="dummy")
    
    # ESCAPE: desperate short-term high-variance action
    win_escape, _, sel_escape = arbiter.select_action("test", options, {}, tme_phase="ESCAPE", world_model="dummy")
    
    score_risky_normal = sel_normal["all_details"]["high_cost_risky"]["computed_score"]
    score_risky_escape = sel_escape["all_details"]["high_cost_risky"]["computed_score"]
    
    assert score_risky_escape > score_risky_normal, "ESCAPE should raise score of risky options by discounting cost/risk"
    assert sel_escape["biological_steering"]["risk_weight"] == 0.5
    assert sel_escape["biological_steering"]["cost_weight"] == 0.5


def test_biological_steering_hyperarousal_na(tmp_path):
    """NA > 0.8 increases gw_weight for distractibility/exploration."""
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    options = ["salient_distractor", "boring"]
    arbiter._save_option("salient_distractor", {"q_value": 0.5, "uncertainty": 0.1, "risk": 0.1, "cost": 0.1})
    arbiter._save_option("boring", {"q_value": 0.6, "uncertainty": 0.1, "risk": 0.1, "cost": 0.1})
    
    gw_scores = {"salient_distractor": 1.0, "boring": 0.0}
    
    # Normal NA
    _, _, sel_normal = arbiter.select_action("test", options, {}, gw_scores=gw_scores, na_level=0.5, world_model="dummy")
    # High NA
    _, _, sel_high_na = arbiter.select_action("test", options, {}, gw_scores=gw_scores, na_level=0.85, world_model="dummy")
    
    score_normal = sel_normal["all_details"]["salient_distractor"]["computed_score"]
    score_high_na = sel_high_na["all_details"]["salient_distractor"]["computed_score"]
    
    assert score_high_na > score_normal, "High NA should boost GW salience"
    assert sel_high_na["biological_steering"]["gw_weight"] > sel_normal["biological_steering"]["gw_weight"]


def test_biological_steering_resilience_floor(tmp_path):
    """High resilience floor increases risk aversion to protect state."""
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    options = ["risky_action", "safe_action"]
    arbiter._save_option("risky_action", {"q_value": 0.9, "uncertainty": 0.1, "risk": 0.5, "cost": 0.1})
    arbiter._save_option("safe_action", {"q_value": 0.5, "uncertainty": 0.1, "risk": 0.0, "cost": 0.1})
    
    _, _, sel_normal = arbiter.select_action("test", options, {}, world_model="dummy")
    _, _, sel_resilient = arbiter.select_action("test", options, {}, resilience_floor=0.10, world_model="dummy")
    
    score_normal = sel_normal["all_details"]["risky_action"]["computed_score"]
    score_resilient = sel_resilient["all_details"]["risky_action"]["computed_score"]
    
    assert score_resilient < score_normal, "Resilience floor should penalize risky options"
    assert sel_resilient["biological_steering"]["risk_weight"] > 1.0


def test_biological_steering_calm_owner_alignment(tmp_path):
    """Low frustration + high alignment boosts owner signal weight."""
    arbiter = PFCBasalGangliaArbiter(root=tmp_path)
    options = ["aligned_action", "unaligned_action"]
    arbiter._save_option("aligned_action", {"q_value": 0.5, "uncertainty": 0.1, "risk": 0.1, "cost": 0.1})
    arbiter._save_option("unaligned_action", {"q_value": 0.6, "uncertainty": 0.1, "risk": 0.1, "cost": 0.1})
    
    _, _, sel_normal = arbiter.select_action("test", options, {}, owner_signal=1.0, world_model="dummy", hysteresis_margin=0.0)
    _, _, sel_calm = arbiter.select_action("test", options, {}, owner_signal=1.0, owner_frustration=0.1, goal_alignment=0.9, world_model="dummy", hysteresis_margin=0.0)
    
    score_normal = sel_normal["all_details"]["aligned_action"]["computed_score"]
    score_calm = sel_calm["all_details"]["aligned_action"]["computed_score"]
    
    assert score_calm > score_normal, "Calm/aligned owner state should boost owner signal weight"
    assert sel_calm["biological_steering"]["owner_weight"] > sel_normal["biological_steering"]["owner_weight"]

