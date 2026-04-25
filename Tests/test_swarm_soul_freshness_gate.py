from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_composite_identity import IdentitySnapshot, identity_system_block
from System.swarm_soul_freshness_gate import (
    StaleSoulDigest,
    extract_generated_at,
    has_somatic_source_metadata,
    latest_soma_source,
    read_fresh_soul,
)


def _soul_text(ts: float) -> str:
    return "\n".join([
        "# ALICE SOUL DIGEST",
        "",
        "## Metadata",
        f"- **Generated At**: {ts}",
        "- **Soul SHA-256 Scope**: content above this line",
    ]) + "\n"


def test_extract_generated_at_from_digest_metadata():
    assert extract_generated_at(_soul_text(123.5)) == 123.5
    assert extract_generated_at("no metadata") is None


def test_somatic_source_metadata_required_when_somatic_line_exists():
    old = "- somatic: soma_score=0.18 soma_label=CRITICAL age_s=1\n"
    new = "- somatic: soma_score=0.18 soma_label=CRITICAL source_ledger=visceral_field.jsonl age_seconds=1.0\n"

    assert has_somatic_source_metadata("no somatic line") is True
    assert has_somatic_source_metadata(old) is False
    assert has_somatic_source_metadata(new) is True


def test_stale_soul_fails_closed_when_regeneration_disabled(tmp_path: Path):
    soul = tmp_path / "alice_soul.md"
    soul.write_text(_soul_text(100.0), encoding="utf-8")

    with pytest.raises(StaleSoulDigest):
        read_fresh_soul(
            soul_path=soul,
            now=2000.0,
            max_age_s=10.0,
            auto_regenerate=False,
        )


def test_stale_soul_auto_regenerates(tmp_path: Path):
    soul = tmp_path / "alice_soul.md"
    soul.write_text(_soul_text(100.0), encoding="utf-8")

    def generator(*, dry_run: bool = False):
        assert dry_run is False
        content = _soul_text(1999.0)
        soul.write_text(content, encoding="utf-8")
        return {"content": content, "generated_at": 1999.0}

    result = read_fresh_soul(
        soul_path=soul,
        now=2000.0,
        max_age_s=10.0,
        auto_regenerate=True,
        generator=generator,
    )

    assert result.regenerated is True
    assert result.generated_at == 1999.0
    assert result.age_seconds == 1.0
    assert soul.read_text(encoding="utf-8") == result.content


def test_fresh_soul_does_not_regenerate(tmp_path: Path):
    soul = tmp_path / "alice_soul.md"
    soul.write_text(_soul_text(1995.0), encoding="utf-8")
    called = False

    def generator(*, dry_run: bool = False):
        nonlocal called
        called = True
        return {"content": _soul_text(2000.0), "generated_at": 2000.0}

    result = read_fresh_soul(
        soul_path=soul,
        now=2000.0,
        max_age_s=10.0,
        generator=generator,
    )

    assert result.regenerated is False
    assert called is False
    assert result.age_seconds == 5.0


def test_fresh_soul_with_old_somatic_format_regenerates(tmp_path: Path):
    soul = tmp_path / "alice_soul.md"
    soul.write_text(
        _soul_text(1995.0) + "- somatic: soma_score=0.18 soma_label=CRITICAL age_s=1\n",
        encoding="utf-8",
    )

    def generator(*, dry_run: bool = False):
        content = (
            _soul_text(1999.0)
            + "- somatic: soma_score=0.18 soma_label=CRITICAL "
            + "source_ledger=visceral_field.jsonl age_seconds=1.0\n"
        )
        soul.write_text(content, encoding="utf-8")
        return {"content": content, "generated_at": 1999.0}

    result = read_fresh_soul(
        soul_path=soul,
        now=2000.0,
        max_age_s=10.0,
        generator=generator,
    )

    assert result.regenerated is True
    assert "source_ledger=visceral_field.jsonl" in result.content


def test_latest_soma_source_carries_ledger_and_age(tmp_path: Path):
    ledger = tmp_path / "visceral_field.jsonl"
    ledger.write_text(
        json.dumps({"ts": 100.0, "soma_score": 0.5, "soma_label": "STRESSED"}) + "\n",
        encoding="utf-8",
    )

    source = latest_soma_source(state_dir=tmp_path, now=130.0)

    assert source is not None
    assert source["source_ledger"] == "visceral_field.jsonl"
    assert source["age_seconds"] == 30.0
    assert source["row"]["soma_label"] == "STRESSED"


def test_identity_system_block_somatic_line_has_source_and_age():
    snap = IdentitySnapshot(
        soma_score=0.568,
        soma_label="STRESSED",
        cardiac_stress=0.0,
        pain_intensity=0.0,
        thermal_stress=0.0,
        metabolic_burn=0.0,
        energy_reserve=0.0122,
        visceral_source="visceral_field.jsonl",
        visceral_age_s=12.34,
    )

    block = identity_system_block(snap)

    assert "- somatic:" in block
    assert "source_ledger=visceral_field.jsonl" in block
    assert "age_seconds=12.3" in block
