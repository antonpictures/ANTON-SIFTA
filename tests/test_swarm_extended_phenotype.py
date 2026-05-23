from pathlib import Path

from System.swarm_extended_phenotype import (
    Bolus,
    BolusManifest,
    CastleBuilder,
    CastleHomeostasis,
    emit_bolus,
    load_boluses,
    proof_of_property,
)


def _bolus(kind: str, ref: str, homeworld: str, ts: float) -> Bolus:
    return Bolus(
        kind=kind,
        ref_sha256="a" * 64,
        ref_path=ref,
        source_homeworld=homeworld,
        deposited_ts=ts,
        payload={"note": ref},
    )


def test_emit_and_load_round_trip(tmp_path):
    ledger = tmp_path / "boluses.jsonl"
    a = _bolus("commit", "git@self/abc", "M5", 1_777_777_001.0)
    b = _bolus("recipe", ".sifta_state/recipe.json", "M5", 1_777_777_002.0)

    emit_bolus(a, ledger_path=ledger, ts=a.deposited_ts)
    emit_bolus(b, ledger_path=ledger, ts=b.deposited_ts)

    loaded = load_boluses(ledger_path=ledger)
    assert [x.kind for x in loaded] == ["commit", "recipe"]
    assert all(x.bolus_sha256() for x in loaded)


def test_emit_is_idempotent_in_manifest(tmp_path):
    ledger = tmp_path / "boluses.jsonl"
    bolus = _bolus("dirt", "Archive/foo.dirt", "M1", 1_777_777_010.0)

    emit_bolus(bolus, ledger_path=ledger, ts=bolus.deposited_ts)
    emit_bolus(bolus, ledger_path=ledger, ts=bolus.deposited_ts)
    emit_bolus(bolus, ledger_path=ledger, ts=bolus.deposited_ts)

    manifest = BolusManifest.from_ledger(ledger_path=ledger, now=1_777_777_020.0)
    assert len(manifest.boluses) == 1
    assert manifest.merkle_root() == manifest.merkle_root()


def test_merkle_root_is_deterministic_and_order_independent(tmp_path):
    """Two ledgers with same boluses written in different orders must share merkle_root."""
    ledger_a = tmp_path / "a.jsonl"
    ledger_b = tmp_path / "b.jsonl"
    boluses = [
        _bolus("commit", "g/abc", "M5", 1_777_777_001.0),
        _bolus("recipe", "r.json", "M1", 1_777_777_002.0),
        _bolus("dirt", "d.dirt", "M5", 1_777_777_003.0),
    ]
    for b in boluses:
        emit_bolus(b, ledger_path=ledger_a, ts=b.deposited_ts)
    for b in reversed(boluses):
        emit_bolus(b, ledger_path=ledger_b, ts=b.deposited_ts)

    m_a = BolusManifest.from_ledger(ledger_path=ledger_a, now=1_777_777_010.0)
    m_b = BolusManifest.from_ledger(ledger_path=ledger_b, now=1_777_777_010.0)
    assert m_a.merkle_root() == m_b.merkle_root()


def test_homeostasis_flags_empty_mound():
    manifest = BolusManifest(boluses=(), built_ts=1_777_777_000.0)
    health = CastleHomeostasis().evaluate(manifest, now=1_777_777_000.0)
    assert not health.ok
    assert "empty_mound" in health.issues


def test_homeostasis_flags_stale_mound(tmp_path):
    ledger = tmp_path / "boluses.jsonl"
    for kind, hw in (("commit", "M5"), ("recipe", "M1")):
        b = _bolus(kind, f"x_{kind}", hw, 1_777_700_000.0)
        emit_bolus(b, ledger_path=ledger, ts=b.deposited_ts)

    manifest = BolusManifest.from_ledger(ledger_path=ledger, now=1_777_777_777.0)
    health = CastleHomeostasis(freshness_window_s=60.0).evaluate(manifest, now=1_777_777_777.0)
    assert not health.ok
    assert any(i.startswith("stale_mound:") for i in health.issues)


def test_castle_builder_writes_local_artifact(tmp_path):
    ledger = tmp_path / "boluses.jsonl"
    for i, (kind, hw) in enumerate((("commit", "M5"), ("recipe", "M1"), ("dirt", "M5"), ("receipt", "M1"))):
        b = _bolus(kind, f"ref_{kind}", hw, 1_777_777_000.0 + i)
        emit_bolus(b, ledger_path=ledger, ts=b.deposited_ts)

    builder = CastleBuilder(castle_root=tmp_path / "castle", ledger_path=ledger)
    summary = builder.publish_local(now=1_777_777_010.0)
    castle_root = Path(summary["castle_root"])

    assert (castle_root / "castle_manifest.json").exists()
    assert (castle_root / "index.html").exists()
    assert (castle_root / "boluses").is_dir()
    assert summary["bolus_count"] == 4
    assert summary["health_ok"] is True
    assert summary["merkle_root"]


def test_proof_of_property_passes():
    result = proof_of_property()
    assert result["ok"] is True
    assert result["bolus_count"] == 4
    assert result["federation_breadth"] == 2
    assert result["health_ok"] is True
    assert result["stale_detected"] is True
    assert result["merkle_root"]
