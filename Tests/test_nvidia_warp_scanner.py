#!/usr/bin/env python3
"""Proof bar for ``System/nvidia_warp_scanner`` — portable without ``warp-lang``."""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.nvidia_warp_scanner import (
    TRUTH_STUB,
    TRUTH_ONLINE,
    TRUTH_REAL_CPU,
    TRUTH_REAL_GPU,
    TRUTH_BROKEN,
    probe_nvidia_warp,
    warp_truth_probe_dict,
)


def test_probe_returns_valid_truth_enum():
    r = probe_nvidia_warp(run_kernel=True)
    assert r.truth in (
        TRUTH_STUB,
        TRUTH_REAL_CPU,
        TRUTH_REAL_GPU,
        TRUTH_BROKEN,
    )


def test_lazy_probe_is_online_or_broken_when_spec_present():
    if importlib.util.find_spec("warp") is None:
        r = probe_nvidia_warp(run_kernel=False)
        assert r.truth == TRUTH_STUB
    else:
        r = probe_nvidia_warp(run_kernel=False)
        assert r.truth in (TRUTH_ONLINE, TRUTH_BROKEN)
        if r.truth == TRUTH_ONLINE:
            assert r.version is not None
            assert "ONLINE" in r.scanner_line


def test_warp_truth_probe_dict_shape():
    d = warp_truth_probe_dict()
    assert set(d.keys()) >= {
        "truth",
        "version",
        "scanner_line",
        "cuda_reported",
        "kernel_ok",
        "error",
    }
    assert d["truth"] in (
        TRUTH_STUB,
        TRUTH_REAL_CPU,
        TRUTH_REAL_GPU,
        TRUTH_BROKEN,
    )
