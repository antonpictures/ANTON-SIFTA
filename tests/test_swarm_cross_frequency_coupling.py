#!/usr/bin/env python3
"""Tests for the cross-frequency coupling organ."""

import json
import math
import time
from pathlib import Path

import numpy as np

from System import swarm_cross_frequency_coupling as cfc


def _append_events(path: Path, times: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for ts in times:
            handle.write(json.dumps({"ts": ts, "kind": "test_event"}) + "\n")


def test_modulation_index_detects_direct_phase_amplitude_locking():
    phase = np.linspace(-math.pi, math.pi, 4096)
    locked_amp = 1.0 + 0.95 * np.cos(phase)
    flat_amp = np.ones_like(phase)

    locked = cfc.modulation_index(phase, locked_amp)
    flat = cfc.modulation_index(phase, flat_amp)

    assert 0.0 <= flat < 0.001
    assert locked > flat + 0.01
    assert 0.0 <= locked <= 1.0


def test_hilbert_backend_has_numpy_fallback_or_scipy():
    assert cfc.hilbert_backend() in {
        "scipy.signal.hilbert",
        "numpy.fft.hilbert_fallback",
    }


def test_organ_names_resolve_to_real_ledger_filenames(tmp_path):
    state = tmp_path / ".sifta_state"
    now = time.time()
    _append_events(
        state / "fiction_organ_events.jsonl",
        [now - 50, now - 40, now - 30, now - 20, now - 10],
    )

    assert cfc.ledger_filename_for("fiction") == "fiction_organ_events.jsonl"
    times = cfc.load_event_times("fiction", state_dir=state, window_s=60, now=now)
    amp = cfc.extract_signal_from_ledger(
        "fiction",
        60,
        0.01,
        0.1,
        state_dir=state,
        now=now,
    )

    assert len(times) == 5
    assert isinstance(amp, np.ndarray)


def test_measure_cfc_reports_skip_reason_when_ledgers_are_sparse(tmp_path):
    state = tmp_path / ".sifta_state"
    now = time.time()
    _append_events(state / "fiction_organ_events.jsonl", [now - 10])
    _append_events(state / "work_receipts.jsonl", [now - 20])

    receipt = cfc.measure_cfc(
        "fiction",
        "work_receipts",
        window_s=60,
        state_dir=state,
        now=now,
        write_receipt=True,
    )
    rows = [
        json.loads(line)
        for line in (state / "cfc_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert receipt["max_MI"] == 0.0
    assert "insufficient_events" in receipt["skipped_reason"]
    assert rows[-1]["scope_limit"] == cfc.SCOPE_LIMIT
    assert rows[-1]["slow_ledger"] == "fiction_organ_events.jsonl"


def test_cfc_matrix_shape_scope_and_ledger_map(tmp_path):
    state = tmp_path / ".sifta_state"
    now = time.time()
    for idx, filename in enumerate(("fiction_organ_events.jsonl", "work_receipts.jsonl", "ide_stigmergic_trace.jsonl")):
        _append_events(
            state / filename,
            [now - 55 + idx, now - 45 + idx, now - 35 + idx, now - 25 + idx, now - 15 + idx],
        )

    receipt = cfc.cfc_matrix(
        window_s=60,
        organs=["fiction", "work_receipts", "ide_doctor"],
        state_dir=state,
        now=now,
        write_receipt=True,
    )
    rows = [
        json.loads(line)
        for line in (state / "cfc_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert receipt["matrix_shape"] == [3, 3]
    assert len(receipt["cfc_matrix"]) == 3
    assert len(receipt["cfc_matrix"][0]) == 3
    assert receipt["ledger_map"]["ide_doctor"] == "ide_stigmergic_trace.jsonl"
    assert receipt["scope_limit"] == cfc.SCOPE_LIMIT
    assert rows[-1]["truth_label"] == cfc.TRUTH_LABEL


def test_real_data_smoke():
    receipt = cfc.cfc_matrix(window_s=1800, write_receipt=True)

    assert receipt["truth_label"] == cfc.TRUTH_LABEL
    assert receipt["matrix_shape"] == [receipt["n_organs"], receipt["n_organs"]]
    assert 0.0 <= receipt["max_MI"] <= 1.0
    assert receipt["scope_limit"] == cfc.SCOPE_LIMIT
