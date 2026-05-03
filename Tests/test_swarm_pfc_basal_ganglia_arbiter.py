import json
from pathlib import Path
import pytest
from System.swarm_pfc_basal_ganglia_arbiter import PFCBasalGangliaArbiter

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
