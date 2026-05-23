import json

from System.temporal_identity_compression import TemporalIdentityCompressionEngine


def _tick(action_type: str, target: str, td_value: float, *, status: str = "completed") -> dict:
    return {
        "event": "body_brain_tick",
        "tick_id": f"{action_type}-{target}-{td_value}",
        "action": {"type": action_type, "target": target},
        "result": {"status": status, "latency": 0.1},
        "td_value": td_value,
        "drive_state": target,
        "metabolic_mode": "GREEN_GROW",
        "ts": 100.0 + td_value,
    }


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_body_brain_success_patterns_crystallize_into_skill_primitives(tmp_path):
    engine = TemporalIdentityCompressionEngine(tmp_path, min_pattern_count=3)
    rows = [_tick("explore", "physics", 1.0), _tick("explore", "physics", 1.2), _tick("explore", "physics", 0.9)]

    stats = engine.process_body_brain_ticks(rows, source_hash="abc123", cycle_id="cycle-a")

    assert stats["skills_created"] == 1
    skills = list(engine.skills.values())
    assert len(skills) == 1
    skill = skills[0]
    assert skill.pattern_signature == "body_brain:explore:physics|SIFTA_BODY"
    assert skill.success_rate == 1.0
    assert skill.positive_examples == 3
    assert skill.source_hash == "abc123"
    assert skill.cycle_id == "cycle-a"
    assert "physics" in skill.pattern_signature
    assert engine.retrieve_skill("physics") == [skill]

    receipts = _read_jsonl(tmp_path / "skill_crystallization_receipts.jsonl")
    assert receipts[-1]["action"] == "SKILL_CRYSTALLIZED"
    assert receipts[-1]["skill_id"] == skill.id


def test_low_success_patterns_are_rejected_not_promoted(tmp_path):
    engine = TemporalIdentityCompressionEngine(tmp_path, min_pattern_count=3)
    rows = [
        _tick("explore", "fragile", 1.0),
        _tick("explore", "fragile", -0.2, status="error"),
        _tick("explore", "fragile", -0.5, status="failed"),
    ]

    stats = engine.process_body_brain_ticks(rows, source_hash="low", cycle_id="cycle-b")

    assert stats["skills_created"] == 0
    assert engine.skills == {}
    receipts = _read_jsonl(tmp_path / "skill_crystallization_receipts.jsonl")
    assert receipts[-1]["action"] == "SKILL_REJECTED_LOW_SUCCESS"
    assert receipts[-1]["success_rate"] < 0.67


def test_repeated_skill_updates_existing_primitive_without_duplicate(tmp_path):
    engine = TemporalIdentityCompressionEngine(tmp_path, min_pattern_count=3)
    rows = [_tick("forage", "pouw_work", 1.0), _tick("forage", "pouw_work", 1.1), _tick("forage", "pouw_work", 1.2)]
    engine.process_body_brain_ticks(rows, source_hash="one", cycle_id="cycle-1")
    first_id = next(iter(engine.skills))

    stats = engine.process_body_brain_ticks(rows, source_hash="two", cycle_id="cycle-2")

    assert stats["skills_created"] == 0
    assert stats["skills_updated"] == 1
    assert list(engine.skills) == [first_id]
    skill = engine.skills[first_id]
    assert skill.usage_count == 6
    assert skill.positive_examples == 6
