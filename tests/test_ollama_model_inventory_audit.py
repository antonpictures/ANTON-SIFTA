import json
from pathlib import Path

from System.ollama_model_inventory_audit import (
    append_cleanup_receipt,
    delete_orphaned_blobs,
    render_report,
    scan_inventory,
)


def _manifest(path: Path, model_digest: str, model_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "layers": [
                    {
                        "mediaType": "application/vnd.ollama.image.model",
                        "digest": model_digest,
                        "size": model_size,
                    },
                    {
                        "mediaType": "application/vnd.ollama.image.params",
                        "digest": "sha256:params",
                        "size": 42,
                    },
                ],
                "config": {
                    "mediaType": "application/vnd.docker.container.image.v1+json",
                    "digest": "sha256:config",
                    "size": 123,
                },
            }
        )
    )


def _blob(root: Path, digest: str, size: int = 1) -> None:
    blob = root / "blobs" / digest.replace(":", "-", 1)
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"x" * size)


def test_inventory_detects_shared_model_blobs_and_orphans(tmp_path):
    root = tmp_path / "models"
    manifests = root / "manifests" / "registry.ollama.ai" / "library"

    _manifest(manifests / "alice" / "latest", "sha256:shared", 1000)
    _manifest(manifests / "rawbase" / "latest", "sha256:shared", 1000)
    _manifest(manifests / "classifier" / "latest", "sha256:classifier", 2000)

    _blob(root, "sha256:shared", 1000)
    _blob(root, "sha256:classifier", 2000)
    _blob(root, "sha256:params")
    _blob(root, "sha256:config")
    _blob(root, "sha256:orphan", 3000)

    inv = scan_inventory(root)

    assert inv.shared_model_blobs == {
        "sha256-shared": ["alice:latest", "rawbase:latest"]
    }
    assert inv.orphaned_blobs == {"sha256-orphan": 3000}

    report = render_report(inv)
    assert "alice:latest" in report
    assert "rawbase:latest" in report
    assert "sha256-orphan" in report


def test_delete_orphaned_blobs_only_removes_unreferenced_files(tmp_path):
    root = tmp_path / "models"
    manifests = root / "manifests" / "registry.ollama.ai" / "library"

    _manifest(manifests / "alice" / "latest", "sha256:shared", 1000)
    _blob(root, "sha256:shared", 1000)
    _blob(root, "sha256:orphan", 3000)

    inv = scan_inventory(root)
    deleted = delete_orphaned_blobs(inv)

    assert deleted == [
        {
            "blob": "sha256-orphan",
            "size": 3000,
            "path": str(root / "blobs" / "sha256-orphan"),
        }
    ]
    assert (root / "blobs" / "sha256-shared").exists()
    assert not (root / "blobs" / "sha256-orphan").exists()


def test_cleanup_receipt_records_deleted_bytes(tmp_path):
    receipt = tmp_path / "receipts.jsonl"
    root = tmp_path / "models"
    root.mkdir()
    inv = scan_inventory(root)
    deleted = [{"blob": "sha256-orphan", "size": 3000, "path": "/tmp/blob"}]

    append_cleanup_receipt(receipt, inv, deleted)

    row = json.loads(receipt.read_text().strip())
    assert row["event"] == "ollama_orphan_blob_cleanup"
    assert row["deleted_count"] == 1
    assert row["deleted_bytes"] == 3000
    assert row["truth_label"] == "OBSERVED_LOCAL_FILESYSTEM_DELETE"


def test_scan_inventory_skips_non_utf8_manifest_like_files(tmp_path):
    root = tmp_path / "models"
    manifests = root / "manifests" / "registry.ollama.ai" / "library"

    _manifest(manifests / "alice" / "latest", "sha256:shared", 1000)
    bad = manifests / "broken" / "latest"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\x86\x00not-json")
    _blob(root, "sha256:shared", 1000)

    inv = scan_inventory(root)

    assert "alice:latest" in inv.model_tags
    assert "broken:latest" not in inv.model_tags
