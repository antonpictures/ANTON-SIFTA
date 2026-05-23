import json
import os

from System import swarm_persistent_owner_history as poh


def test_owner_history_roundtrip(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    monkeypatch.setenv("SIFTA_STATE_DIR", str(state))

    m = poh.record_owner_moment(
        "test continuity beat",
        importance="high",
        context={"lane": "pytest"},
        interaction_seconds=30.0,
        root=state,
    )
    assert m["moment_id"]
    assert m["human_owner"]  # from genesis or <unclaimed>

    summary = poh.get_owner_life_summary(root=state)
    assert summary["last_moment"]["description"] == "test continuity beat"
    assert summary["total_moments_logged"] == 1

    manifest = poh.get_owner_manifest(root=state)
    assert manifest.get("total_interaction_seconds", 0) >= 30.0

    log = state / "owner_life_history.jsonl"
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["moment_id"] == m["moment_id"]

    monkeypatch.delenv("SIFTA_STATE_DIR", raising=False)


def test_state_dir_prefers_explicit_over_env(tmp_path, monkeypatch):
    other = tmp_path / "other_state"
    monkeypatch.setenv("SIFTA_STATE_DIR", str(tmp_path / "ignored"))
    assert poh.state_dir(explicit=other) == other
