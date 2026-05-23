from pathlib import Path


def test_app_health_lifecycle_creates_trace_and_prompt(tmp_path, monkeypatch):
    from System import swarm_app_health as health

    monkeypatch.setattr(health, "_HEALTH_ROOT", tmp_path / "app_health")

    health.record_app_lifecycle(
        "Network Control Center",
        action="enter_update",
        manifest_entry={
            "category": "Network",
            "description": "Network diagnostics and mesh control.",
        },
        source="test",
    )
    health.record_app_lifecycle(
        "Network Control Center",
        action="exit_update",
        note="Found that mesh diagnostics should load first next time.",
        source="test",
    )

    rows = health.get_app_health("Network Control Center")
    assert [row["action"] for row in rows[:2]] == ["exit_update", "enter_update"]
    assert "networking" in health.get_required_skills_for_app("Network Control Center")

    block = health.app_health_prompt_block("Network Control Center")
    assert "APP HEALTH SECTION FOR Network Control Center" in block
    assert "Required skills from health trace:" in block
    assert "mesh diagnostics should load first" in block
    assert "pulls only the health-listed skills/habits" in block


def test_app_health_slug_is_stable_for_punctuated_names(tmp_path, monkeypatch):
    from System import swarm_app_health as health

    monkeypatch.setattr(health, "_HEALTH_ROOT", tmp_path / "app_health")

    health.append_health_update(
        "Pheromone Symphony (Generative Music)",
        action="enter_update",
        skills=["music_guidance"],
        note="open",
        source="test",
    )

    path = tmp_path / "app_health" / "pheromone_symphony_generative_music" / "health_trace.jsonl"
    assert path.exists()
    assert health.get_required_skills_for_app("Pheromone Symphony (Generative Music)") == [
        "music_guidance"
    ]
