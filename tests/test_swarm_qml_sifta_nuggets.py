#!/usr/bin/env python3
"""Tests for QML-to-SIFTA nuggets and truth boundaries."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from System.swarm_qml_sifta_nuggets import (  # noqa: E402
    format_qml_sifta_nuggets,
    latest_qml_sifta_nugget,
    qml_sifta_nuggets_report,
)


def test_report_deposits_nuggets_and_targets(tmp_path: Path):
    report = qml_sifta_nuggets_report(state_dir=tmp_path, write_receipt=True)
    assert report["truth_label"] == "QML_SIFTA_NUGGETS_V1"
    nugget_ids = {n["id"] for n in report["nuggets"]}
    assert "quantum_data_first" in nugget_ids
    assert "trainability_is_the_bottleneck" in nugget_ids
    target_ids = {t["id"] for t in report["research_targets"]}
    assert "stigmergic_qml_trainability_controller" in target_ids
    assert "qec_swimmer_decoder" in target_ids
    assert "content_sha256" in report and len(report["content_sha256"]) == 64

    latest = latest_qml_sifta_nugget(state_dir=tmp_path)
    assert latest is not None
    assert latest["content_sha256"] == report["content_sha256"]


def test_format_says_no_breakthrough_claim_without_benchmark():
    line = format_qml_sifta_nuggets(max_targets=3)
    assert "Cerezo" in line
    assert "Quantum" in line or "QML" in line
    assert "no 'nobody solved it' claim until benchmark receipt" in line
    assert "local TFIM solve" in line


def test_research_targets_are_not_overclaimed():
    report = qml_sifta_nuggets_report(write_receipt=False)
    labels = {t["truth_label"] for t in report["research_targets"]}
    assert "HYPOTHESIS" in labels
    assert "No claim" in report["truth_boundary"]
    for target in report["research_targets"]:
        assert target["benchmark_required"]
        if target["id"] != "quantum_data_truth_boundary":
            assert target["truth_label"] == "HYPOTHESIS"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            if test.__name__ == "test_report_deposits_nuggets_and_targets":
                import tempfile

                with tempfile.TemporaryDirectory() as td:
                    test(Path(td))
            else:
                test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
