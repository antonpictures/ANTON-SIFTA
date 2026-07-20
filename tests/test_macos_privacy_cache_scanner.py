from __future__ import annotations

import json
from pathlib import Path

from System.swarm_macos_privacy_cache_scanner import (
    scan_macos_privacy_cache_surfaces,
    summarize_for_owner,
)


def test_scanner_classifies_sifta_apple_and_delete_candidates(tmp_path: Path) -> None:
    cache = tmp_path / "Caches"
    state = tmp_path / "state"
    (cache / "SIFTA OS").mkdir(parents=True)
    (cache / "SIFTA OS" / "body.cache").write_bytes(b"alice")
    (cache / "CloudKit").mkdir()
    (cache / "com.apple.HomeKit").mkdir()
    (cache / "com.apple.AssistantServices").mkdir()
    (cache / "RandomAppCache").mkdir()
    (cache / "RandomAppCache" / "junk.bin").write_bytes(b"x" * 10)

    scan = scan_macos_privacy_cache_surfaces(cache_root=cache, state_dir=state, write_receipt=True)
    by_name = {entry["name"]: entry for entry in scan["entries"]}

    assert by_name["SIFTA OS"]["relation_to_sifta"] == "SIFTA_CACHE"
    assert by_name["SIFTA OS"]["recommendation"] == "KEEP"
    assert by_name["CloudKit"]["relation_to_sifta"] == "APPLE_OS_SERVICE_CACHE"
    assert by_name["CloudKit"]["content_read"] is False
    assert "iCloud" in by_name["CloudKit"]["service"]
    assert by_name["com.apple.HomeKit"]["relation_to_sifta"] == "APPLE_OS_SERVICE_CACHE"
    assert by_name["com.apple.AssistantServices"]["relation_to_sifta"] == "APPLE_OS_SERVICE_CACHE"
    assert "Siri" in by_name["com.apple.AssistantServices"]["service"]
    assert by_name["RandomAppCache"]["relation_to_sifta"] == "NON_SIFTA_CACHE"
    assert by_name["RandomAppCache"]["recommendation"] == "DELETE_CANDIDATE_IF_OWNER_DOES_NOT_USE_APP"

    ledger = state / "macos_privacy_cache_scan.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert rows[-1]["truth_label"] == "OBSERVED"
    assert rows[-1]["privacy_mode"] == "metadata_only_no_payload_contents"


def test_summary_is_grounded_and_mentions_receipt(tmp_path: Path) -> None:
    cache = tmp_path / "Caches"
    state = tmp_path / "state"
    (cache / "SIFTA OS").mkdir(parents=True)
    (cache / "familycircled").mkdir()

    scan = scan_macos_privacy_cache_surfaces(cache_root=cache, state_dir=state, write_receipt=True)
    summary = summarize_for_owner(scan)

    assert "metadata_only_no_payload_contents" in summary
    assert "SIFTA cache: 1" in summary
    assert "Apple service stubs: 1" in summary
    assert "Receipt:" in summary
