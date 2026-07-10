#!/usr/bin/env python3
"""r1608 Gift 2 — prion shape propagation detector."""
from __future__ import annotations

from System.swarm_prion_drift_detector import (
    shape_fingerprint,
    shape_similarity,
    detect_prion_run,
    write_receipt,
)


THEATER = (
    "TELEMETRY RECEIPT CONFIRMED. The multimodal ingress path is live. "
    "The observation stream successfully ingested the kitchen audio."
)
THEATER2 = (
    "PHYSICAL TELEMETRY RECEIPT shows multimodal ingress. "
    "Observation stream successfully ingested ambient context."
)
CLEAN = "I heard a podcast about MMA and I am observing, not answering the host."


def test_fingerprint_stable_for_same_text():
    a = shape_fingerprint(THEATER)
    b = shape_fingerprint(THEATER)
    assert a["digest"] == b["digest"]
    assert a["motif_count"] >= 1


def test_theater_shapes_are_similar():
    fa, fb = shape_fingerprint(THEATER), shape_fingerprint(THEATER2)
    assert shape_similarity(fa, fb) >= 0.5


def test_prion_run_hits_on_repeated_theater():
    lines = [THEATER, THEATER2, THEATER, THEATER2]
    r = detect_prion_run(lines, similarity_threshold=0.55, min_run=3)
    assert r["hit"] is True
    assert r["run_length"] >= 3
    assert r["reason"] == "shape_propagation"


def test_clean_replies_do_not_prion():
    lines = [
        "Sure — Instagram is open.",
        CLEAN,
        "Local cortex first; I will escalate only if empty.",
        "Voice enroll clip 2 of 5 received.",
    ]
    r = detect_prion_run(lines, similarity_threshold=0.78, min_run=3)
    assert r["hit"] is False


def test_write_receipt(tmp_path):
    r = detect_prion_run([THEATER, THEATER, THEATER], min_run=3, similarity_threshold=0.5)
    row = write_receipt(r, state_dir=tmp_path, source="test")
    assert row["hit"] is True
    ledger = tmp_path / "prion_drift_receipts.jsonl"
    assert ledger.exists()
