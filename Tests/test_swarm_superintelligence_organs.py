import json

import numpy as np

from System import swarm_superintelligence_organs as s


def test_entorhinal_path_integrate_wraps(tmp_path):
    g = s.EntorhinalGridNavigator(grid_size=8, scale=1.0, seed=3)
    g.position[:] = [7.5, 7.5]
    g.path_integrate(np.array([1.0, 1.0]))
    assert np.all(g.position < 8)


def test_global_workspace_ignition():
    gw = s.GlobalWorkspace(num_nodes=3, broadcast_threshold=0.3)
    w = gw.compete(np.array([0.0, 5.0, 0.0]))
    assert w >= 0
    b = gw.broadcast({"msg": "hi"})
    assert b["conscious"] is True


def test_mhc_self_hash():
    m = s.MHCImmuneSystem()
    m.register_self("my_self_pattern")
    assert m.is_self("my_self_pattern") is True
    assert m.immune_response("intruder")["decision"] == "QUARANTINE"


def test_active_inference_policy_pick():
    ai = s.ActiveInferenceEngine(state_dim=4, seed=0)
    policies = [np.array([1, 0, 0, 0], dtype=float), np.array([0, 1, 0, 0], dtype=float)]
    idx = ai.policy_selection(policies)
    assert idx in (0, 1)


def test_run_demo_trace_jsonl(tmp_path):
    summary = s.run_demo_trace(root=tmp_path)
    assert summary["kind"] == "SUPERINTELLIGENCE_ORGANS_DEMO"
    lines = s.organ_trace_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "SUPERINTELLIGENCE_ORGANS_DEMO"


def test_superintelligence_disabled_no_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SUPERINTELLIGENCE_ORGANS_DISABLE", "1")
    s.run_demo_trace(root=tmp_path)
    assert not s.organ_trace_path(tmp_path).exists()
