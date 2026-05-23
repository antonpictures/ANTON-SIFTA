import json
from pathlib import Path
from unittest.mock import patch

import pytest

from System.swarm_extended_phenotype import (
    Bolus,
    BolusManifest,
    CastleHealth,
    CastleHomeostasis,
    emit_bolus,
)
from System.swarm_publish_daemon import (
    GithubTransport,
    IpfsTransport,
    MockTransport,
    S3Transport,
    STATUS_BLOCKED_PII,
    STATUS_DRY_RUN,
    STATUS_FAILURE,
    STATUS_HOMEOSTASIS_ABORT,
    STATUS_PREFLIGHT_FAILED,
    STATUS_SKIPPED_UNCHANGED,
    STATUS_SUCCESS,
    _emit_distro_bolus,
    _last_successful_manifest_sha,
    _pii_audit,
    get_transport,
    publish_castle,
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


def _healthy_pair(tmp_path: Path):
    """Build a (manifest, health, castle_root) tuple for healthy publishing."""
    castle_root = tmp_path / "castle"
    castle_root.mkdir()
    (castle_root / "castle_manifest.json").write_text("{}", encoding="utf-8")
    manifest = BolusManifest(boluses=(_bolus("commit", "x", "M5", 100.0),), built_ts=100.0)
    health = CastleHealth(
        ok=True,
        score=0.9,
        issues=(),
        checked_ts=100.0,
        manifest_sha256="DEADBEEF" * 8,
        diversity_score=0.5,
        federation_breadth=1,
        freshness_s=10.0,
    )
    return manifest, health, castle_root


# ─────────────────────────────────────────────────────────────────────────
# AG31 baseline contract (preserved)
# ─────────────────────────────────────────────────────────────────────────

def test_get_transport():
    assert isinstance(get_transport("github://org/repo"), GithubTransport)
    assert isinstance(get_transport("s3://my-bucket/path"), S3Transport)
    assert isinstance(get_transport("ipfs://local"), IpfsTransport)
    assert isinstance(get_transport("mock://x"), MockTransport)
    with pytest.raises(ValueError):
        get_transport("ftp://nope")


@patch("System.swarm_publish_daemon.CastleBuilder")
def test_publish_aborts_on_homeostasis_failure(mock_builder_cls, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest = BolusManifest(boluses=(), built_ts=100.0)
    health = CastleHealth(
        ok=False, score=0.1, issues=("empty_mound",), checked_ts=100.0,
        manifest_sha256="abc", diversity_score=0.0, federation_breadth=0, freshness_s=0.0,
    )
    mock_builder.build.return_value = (manifest, health)

    receipts = publish_castle(
        ["mock://test"], allow_publish=True, now=100.0,
        receipts_ledger=tmp_path / "receipts.jsonl",
    )

    assert len(receipts) == 1
    assert receipts[0]["status"] == STATUS_HOMEOSTASIS_ABORT
    mock_builder.publish_local.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# C47H acid-blood guards
# ─────────────────────────────────────────────────────────────────────────

@patch("System.swarm_publish_daemon._pii_audit", return_value=[])
@patch("System.swarm_publish_daemon.CastleBuilder")
def test_dry_run_is_default_when_allow_publish_absent(mock_builder_cls, _audit, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    with patch("System.swarm_publish_daemon.MockTransport.push") as mock_push:
        receipts = publish_castle(
            ["mock://target"], allow_publish=False, now=100.0,
            receipts_ledger=tmp_path / "receipts.jsonl",
        )
        mock_push.assert_not_called()
        assert len(receipts) == 1
        assert receipts[0]["status"] == STATUS_DRY_RUN
        assert receipts[0]["bytes_transferred"] == 0


@patch("System.swarm_publish_daemon.CastleBuilder")
def test_pii_audit_blocks_publish(mock_builder_cls, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    with patch("System.swarm_publish_daemon._pii_audit", return_value=["ioanganton::manifest.json"]):
        with patch("System.swarm_publish_daemon.MockTransport.push") as mock_push:
            receipts = publish_castle(
                ["mock://target"], allow_publish=True, now=100.0,
                receipts_ledger=tmp_path / "receipts.jsonl",
            )
            mock_push.assert_not_called()
            assert len(receipts) == 1
            assert receipts[0]["status"] == STATUS_BLOCKED_PII


@patch("System.swarm_publish_daemon._pii_audit", return_value=[])
@patch("System.swarm_publish_daemon.CastleBuilder")
def test_idempotent_skip_on_unchanged_manifest_sha(mock_builder_cls, _audit, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    receipts_path = tmp_path / "receipts.jsonl"

    with patch("System.swarm_publish_daemon.MockTransport.push") as mock_push:
        mock_push.return_value = (True, 42)
        with patch("System.swarm_publish_daemon._emit_distro_bolus", return_value="bolus"):
            first = publish_castle(
                ["mock://m1"], allow_publish=True, now=100.0,
                receipts_ledger=receipts_path,
            )
            assert first[0]["status"] == STATUS_SUCCESS
            assert mock_push.call_count == 1

            second = publish_castle(
                ["mock://m1"], allow_publish=True, now=200.0,
                receipts_ledger=receipts_path,
            )
            assert second[0]["status"] == STATUS_SKIPPED_UNCHANGED
            assert second[0]["bytes_transferred"] == 0
            assert mock_push.call_count == 1


@patch("System.swarm_publish_daemon._pii_audit", return_value=[])
@patch("System.swarm_publish_daemon.CastleBuilder")
def test_successful_publish_emits_stigmergic_distro_bolus(mock_builder_cls, _audit, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    bolus_ledger = tmp_path / "boluses.jsonl"

    with patch("System.swarm_publish_daemon.MockTransport.push", return_value=(True, 99)):
        with patch("System.swarm_publish_daemon.emit_bolus") as mock_emit:
            publish_castle(
                ["mock://stigmergic"], allow_publish=True, now=100.0,
                receipts_ledger=tmp_path / "receipts.jsonl",
            )
            assert mock_emit.call_count == 1
            emitted_bolus = mock_emit.call_args.args[0]
            assert emitted_bolus.kind == "distro"
            assert emitted_bolus.ref_path == "castle/published/mock://stigmergic"
            assert emitted_bolus.payload["transport_uri"] == "mock://stigmergic"


@patch("System.swarm_publish_daemon._pii_audit", return_value=[])
@patch("System.swarm_publish_daemon.CastleBuilder")
def test_failure_does_not_emit_distro_bolus(mock_builder_cls, _audit, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    with patch("System.swarm_publish_daemon.MockTransport.push", return_value=(False, 0)):
        with patch("System.swarm_publish_daemon.emit_bolus") as mock_emit:
            receipts = publish_castle(
                ["mock://broken"], allow_publish=True, now=100.0,
                receipts_ledger=tmp_path / "receipts.jsonl",
            )
            assert receipts[0]["status"] == STATUS_FAILURE
            mock_emit.assert_not_called()


@patch("System.swarm_publish_daemon._pii_audit", return_value=[])
@patch("System.swarm_publish_daemon.CastleBuilder")
def test_preflight_failure_blocks_transport_push(mock_builder_cls, _audit, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    with patch("System.swarm_publish_daemon.MockTransport.dry_check", return_value=(False, "offline")):
        with patch("System.swarm_publish_daemon.MockTransport.push") as mock_push:
            with patch("System.swarm_publish_daemon.emit_bolus") as mock_emit:
                receipts = publish_castle(
                    ["mock://offline"], allow_publish=True, now=100.0,
                    receipts_ledger=tmp_path / "receipts.jsonl",
                )
                assert receipts[0]["status"] == STATUS_PREFLIGHT_FAILED
                assert receipts[0]["bytes_transferred"] == 0
                mock_push.assert_not_called()
                mock_emit.assert_not_called()


def test_last_successful_manifest_sha_helper(tmp_path):
    ledger = tmp_path / "receipts.jsonl"
    rows = [
        {"destination_uri": "mock://x", "status": STATUS_SUCCESS, "manifest_sha256": "old"},
        {"destination_uri": "mock://x", "status": STATUS_FAILURE, "manifest_sha256": "skipme"},
        {"destination_uri": "mock://x", "status": STATUS_SUCCESS, "manifest_sha256": "newest"},
        {"destination_uri": "mock://y", "status": STATUS_SUCCESS, "manifest_sha256": "different"},
    ]
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    assert _last_successful_manifest_sha("mock://x", ledger_path=ledger) == "newest"
    assert _last_successful_manifest_sha("mock://y", ledger_path=ledger) == "different"
    assert _last_successful_manifest_sha("mock://nothing", ledger_path=ledger) is None


def test_pii_audit_detects_hard_token(tmp_path):
    castle = tmp_path / "castle"
    castle.mkdir()
    (castle / "leak.txt").write_text("hello /Users/ioanganton/something\n", encoding="utf-8")
    hits = _pii_audit(castle)
    assert any("ioanganton" in h for h in hits)


def test_pii_audit_passes_clean_castle(tmp_path):
    castle = tmp_path / "castle"
    castle.mkdir()
    (castle / "clean.txt").write_text("nothing sensitive here\n", encoding="utf-8")
    assert _pii_audit(castle) == []


@patch("System.swarm_publish_daemon._pii_audit", return_value=[])
@patch("System.swarm_publish_daemon.CastleBuilder")
def test_preflight_failure_aborts_publish(mock_builder_cls, _audit, tmp_path):
    mock_builder = mock_builder_cls.return_value
    manifest, health, castle_root = _healthy_pair(tmp_path)
    mock_builder.build.return_value = (manifest, health)
    mock_builder.castle_root = castle_root

    with patch("System.swarm_publish_daemon.MockTransport.dry_check", return_value=(False, "mock_preflight_failed")):
        with patch("System.swarm_publish_daemon.MockTransport.push") as mock_push:
            receipts = publish_castle(
                ["mock://broken_preflight"], allow_publish=True, now=100.0,
                receipts_ledger=tmp_path / "receipts.jsonl",
            )
            assert receipts[0]["status"] == "PREFLIGHT_FAILED"
            mock_push.assert_not_called()


def test_publish_distro_script_uses_canonical_daemon():
    script = Path("scripts/publish_distro.sh").read_text(encoding="utf-8")
    assert "System.swarm_publish_daemon" in script
    assert "System.swarm_castle_publisher" not in script
    assert " --allow-publish --transport github" not in script
