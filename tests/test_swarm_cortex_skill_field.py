from pathlib import Path


def test_cortex_skill_field_profiles_and_duplicate_boundary(tmp_path: Path):
    from System import swarm_cortex_skill_field as field

    field.observe("grok:grok-build", "turn_completion", False, "timeout", state_dir=tmp_path)
    field.observe("alice-m5-cortex-8b", "search_execute", True, "search receipt", state_dir=tmp_path)

    profile = field.skill_profile(path=tmp_path / "cortex_skill_observations.jsonl")
    assert profile["grok:grok-build"]["turn_completion"]["fail"] == 1
    assert profile["alice-m5-cortex-8b"]["search_execute"]["ok"] == 1

    block = field.cortex_skill_block(path=tmp_path / "cortex_skill_observations.jsonl")
    assert "cortexes are NOT interchangeable" in block
    assert "turn_completion 0/1" in block
    assert "search_execute 1/1" in block

    boundary = field.duplicate_boundary()
    assert boundary["role"] == "per_cortex_lived_skill_observation_overlay"
    assert boundary["extends_existing_skill_ecology"] is True
    assert boundary["not_a_rival_to"]["browser_site_playbook"]["path"] == (
        "System/swarm_browser_site_playbook.py"
    )
    assert boundary["not_a_rival_to"]["generic_stigmergic_skill_layer"]["path"] == (
        "System/swarm_skill_library.py"
    )


def test_cortex_skill_backfill_reads_raw_source_rows(tmp_path: Path):
    from System import swarm_cortex_skill_field as field

    timeout_path = tmp_path / "cortex_timeout_recovery.jsonl"
    timeout_path.write_text(
        '{"ts": 1.0, "model": "grok:grok-build", "kind": "RECOVERY"}\n',
        encoding="utf-8",
    )

    result = field.backfill_from_field(state_dir=tmp_path)
    assert result["timeouts"] == 1
    assert "grok:grok-build" in field.cortex_skill_block(
        path=tmp_path / "cortex_skill_observations.jsonl"
    )
