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
