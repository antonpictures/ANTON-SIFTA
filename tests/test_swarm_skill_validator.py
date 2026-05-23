from pathlib import Path


def test_skill_validator_requires_hardware_provenance(tmp_path: Path):
    from System.swarm_skill_validator import validate_skill_file

    skill = tmp_path / "SKILL.md"
    skill.write_text(
        """---
name: camera_switch
description: Use when George asks Alice to switch cameras.
swimmer_type: SENSOR_GATE
---
# Camera
Switch with receipts.
""",
        encoding="utf-8",
    )

    errors = validate_skill_file(skill)

    assert "Missing SIFTA frontmatter: 'homeworld_serial' (required for substrate provenance)" in errors
    assert "Missing SIFTA frontmatter: 'trace_id' (required for doctor accountability)" in errors


def test_skill_validator_accepts_packaged_skill(tmp_path: Path):
    from System.swarm_skill_validator import validate_skill_file

    skill = tmp_path / "SKILL.md"
    skill.write_text(
        """---
name: camera_switch
description: Use when George asks Alice to switch cameras.
swimmer_type: SENSOR_GATE
homeworld_serial: GTH4921YP3
trace_id: abc-123
---
# Camera
Switch with receipts.
""",
        encoding="utf-8",
    )

    assert validate_skill_file(skill) == []
