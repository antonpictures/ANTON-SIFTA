from System.swarm_kv_cache_continuity import continuity_prompt_block, rehydrate_mind_snapshot


def test_rehydrate_ledger_mode(tmp_path):
    snap = rehydrate_mind_snapshot(state_dir=tmp_path)
    assert snap["mode"] == "ledger_rehydrate_not_gpu_kv"
    assert snap["vllm_pegaflow"]["enabled"] is False
    block = continuity_prompt_block(state_dir=tmp_path)
    assert "MIND CONTINUITY" in block
