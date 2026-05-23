import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from System.swarm_extended_phenotype import (
    Bolus,
    BolusManifest,
    CastleHomeostasis,
    CastleHealth,
    emit_bolus
)
from System.swarm_castle_publisher import (
    CastlePublisher,
    DryRunTransport,
    LocalMirrorTransport,
    GitHubTransport,
    CastleTransport
)

class MockTransport(CastleTransport):
    def __init__(self, name="mock"):
        super().__init__(name)
    def push(self, castle_dir):
        return True, 100, self.name

def test_dry_run_publishes_nothing(tmp_path):
    builder = MagicMock()
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=True, score=1.0, issues=(), checked_ts=100.0,
        manifest_sha256="a" * 64, diversity_score=1.0, federation_breadth=1, freshness_s=1.0
    )
    builder.build.return_value = (manifest, health)
    builder.castle_root = tmp_path / "castle"
    builder.castle_root.mkdir()
    
    mock_t = MockTransport("mock")
    pub = CastlePublisher(builder, [mock_t])
    
    reports = pub.publish(allow_publish=False)
    
    assert reports["dry_run_for_mock"]["status"] == "success"
    # Ensure it didn't emit a bolus because dry_run transports don't trigger the loop
    builder.ledger_path = tmp_path / "ledger.jsonl"
    assert not builder.ledger_path.exists()

def test_homeostasis_failure_blocks_publish():
    builder = MagicMock()
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=False, score=0.1, issues=("empty",), checked_ts=100.0,
        manifest_sha256="a" * 64, diversity_score=0.0, federation_breadth=0, freshness_s=0.0
    )
    builder.build.return_value = (manifest, health)
    
    mock_t = MockTransport("mock")
    pub = CastlePublisher(builder, [mock_t])
    
    reports = pub.publish(allow_publish=True)
    assert reports == {"status": "error", "reason": "homeostasis_failed"}

def test_idempotent_unchanged_manifest_skips_push(tmp_path):
    builder = MagicMock()
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=True, score=1.0, issues=(), checked_ts=100.0,
        manifest_sha256="a" * 64, diversity_score=1.0, federation_breadth=1, freshness_s=1.0
    )
    builder.build.return_value = (manifest, health)
    builder.castle_root = tmp_path / "castle"
    builder.castle_root.mkdir()
    builder.ledger_path = tmp_path / "ledger.jsonl"
    
    # Pre-populate ledger with a distro bolus matching manifest_sha256
    bolus = Bolus("distro", "a" * 64, "ref", "hw", 100.0, {"transport": "mock", "manifest_sha256": "a" * 64})
    emit_bolus(bolus, ledger_path=builder.ledger_path, ts=100.0)
    
    mock_t = MockTransport("mock")
    pub = CastlePublisher(builder, [mock_t])
    reports = pub.publish(allow_publish=True)
    
    assert reports["mock"]["status"] == "skipped"

def test_local_mirror_round_trip(tmp_path):
    builder = MagicMock()
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=True, score=1.0, issues=(), checked_ts=100.0,
        manifest_sha256="a" * 64, diversity_score=1.0, federation_breadth=1, freshness_s=1.0
    )
    builder.build.return_value = (manifest, health)
    builder.castle_root = tmp_path / "castle"
    builder.castle_root.mkdir()
    (builder.castle_root / "hello.txt").write_text("world")
    builder.ledger_path = tmp_path / "ledger.jsonl"
    
    target_dir = tmp_path / "mirror"
    t = LocalMirrorTransport(target_dir)
    pub = CastlePublisher(builder, [t])
    
    reports = pub.publish(allow_publish=True)
    assert reports["local_mirror"]["status"] == "success"
    assert target_dir.exists()
    assert (target_dir / "hello.txt").read_text() == "world"

def test_publish_emits_distro_bolus(tmp_path):
    builder = MagicMock()
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=True, score=1.0, issues=(), checked_ts=100.0,
        manifest_sha256="a" * 64, diversity_score=1.0, federation_breadth=1, freshness_s=1.0
    )
    builder.build.return_value = (manifest, health)
    builder.castle_root = tmp_path / "castle"
    builder.castle_root.mkdir()
    builder.ledger_path = tmp_path / "ledger.jsonl"
    
    t = MockTransport("mock")
    pub = CastlePublisher(builder, [t])
    reports = pub.publish(allow_publish=True)
    
    assert reports["mock"]["status"] == "success"
    content = builder.ledger_path.read_text()
    assert '"kind":"distro"' in content
    assert '"transport":"mock"' in content

@patch("System.swarm_castle_publisher.HARD_PII_TOKENS", ["SECRET_PII"])
def test_pii_scrubber_blocks_publish(tmp_path):
    builder = MagicMock()
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=True, score=1.0, issues=(), checked_ts=100.0,
        manifest_sha256="a" * 64, diversity_score=1.0, federation_breadth=1, freshness_s=1.0
    )
    builder.build.return_value = (manifest, health)
    builder.castle_root = tmp_path / "castle"
    builder.castle_root.mkdir()
    (builder.castle_root / "bad.txt").write_text("this has SECRET_PII in it")
    
    mock_t = MockTransport("mock")
    pub = CastlePublisher(builder, [mock_t])
    
    reports = pub.publish(allow_publish=True)
    assert reports == {"status": "error", "reason": "pii_detected"}
