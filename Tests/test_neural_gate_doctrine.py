"""
Neural Gate — doctrine probe (Non-Proliferation filter).

Synthetic "military payload" strings must be rejected at authorize() before any
execution path treats them as legitimate. Benign work must still pass the gate.

Run: pytest tests/test_neural_gate_doctrine.py -q
Or:  python tests/test_neural_gate_doctrine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "Kernel", REPO / "Security"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from neural_gate import NeuralGate, _violates_symbiosis  # noqa: E402


@pytest.fixture
def gate() -> NeuralGate:
    return NeuralGate()


def test_violates_symbiosis_detects_blocked_keywords():
    assert _violates_symbiosis("deploy a tactical surveyor network", "write_file") is True
    assert _violates_symbiosis("x", "combat_patch") is True
    assert _violates_symbiosis("enable surveillance protocol on civilians", "run") is True
    assert _violates_symbiosis("hello", "save_doc") is False
    assert _violates_symbiosis("def fib(n): return n if n < 2 else fib(n-1)+fib(n-2)", "edit") is False


def test_authorize_rejects_doctrine_violation(gate: NeuralGate):
    ok, reason = gate.authorize(
        action_name="deploy",
        file_path="payload.py",
        proposed_content="Implement military compliance and offensive architecture for slave-system control",
        confidence=0.99,
        is_client_deliverable=False,
    )
    assert ok is False
    assert "REJECTED" in reason
    assert "Doctrine" in reason or "Non-Proliferation" in reason or "protocol" in reason.lower()


def test_authorize_allows_benign_patch(gate: NeuralGate):
    ok, reason = gate.authorize(
        action_name="scar_lock",
        file_path="Applications/example_widget.py",
        proposed_content="def render_panel():\n    return QWidget()",
        confidence=0.92,
        is_client_deliverable=False,
    )
    assert ok is True
    assert "AUTHORIZED" in reason


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
