#!/usr/bin/env python3
"""Tests: GC/stack hardening (SIFTA r246) — mitigation for the Python-3.14 incremental-GC
(`mark_stacks`) SIGSEGV fired from a QTimer slot. Headless; no Qt."""
import gc
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_gc_stack_hardening as h


def test_should_harden_gates_on_314():
    assert h.should_harden((3, 14)) is True
    assert h.should_harden((3, 15)) is True
    assert h.should_harden((3, 13)) is False
    assert h.should_harden((3, 12)) is False


def test_skip_on_stable_python_leaves_runtime_untouched():
    # force=False on a <3.14 interpreter must NOT freeze/alter gc
    if h.should_harden():
        pytest.skip("running on 3.14+; skip path not exercised here")
    before = gc.isenabled()
    r = h.harden_runtime_for_gc(force=False)
    assert r["applied"] is False and "skipped" in r["notes"][0]
    assert gc.isenabled() == before


def test_force_applies_threshold_and_freeze():
    logs = []
    r = h.harden_runtime_for_gc(force=True, log=logs.append)
    assert r["applied"] is True
    joined = " ".join(r["notes"])
    assert "gc_threshold=" in joined and "gc_frozen_objects=" in joined
    assert logs and logs[0].startswith("[gc_hardening]")
    # threshold actually took
    assert gc.get_threshold()[0] == 50_000
    gc.unfreeze()  # don't leak frozen state into other tests
    gc.set_threshold(700, 10, 10)


def test_idempotent_double_call():
    h.harden_runtime_for_gc(force=True)
    r = h.harden_runtime_for_gc(force=True)
    assert r["applied"] is True
    gc.unfreeze()
    gc.set_threshold(700, 10, 10)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
