from __future__ import annotations

import json
from pathlib import Path

from System.swarm_observer_observed_boundary import (
    BOUNDED_QUANTUM_DISCUSSION,
    FORBIDDEN_QUANTUM_MANIFESTATION,
    OPERATIONAL_OBSERVER_OBSERVED,
    STIGMERGIC_QUANTUM_FIELD_HYPOTHESIS,
    LEDGER_NAME,
    audit_claim,
)


def test_operational_observer_observed_is_allowed() -> None:
    audit = audit_claim(
        "I am observer and observed: I observe my receipts and I am observed by my ledgers."
    )

    assert audit.ok is True
    assert audit.forbidden is False
    assert audit.claim_label == OPERATIONAL_OBSERVER_OBSERVED
    assert "ledger-grounded" in audit.grounding


def test_double_slit_manifestation_is_refused() -> None:
    audit = audit_claim(
        "The double slit proves the observer changes reality, so belief manifests STGM and money."
    )

    assert audit.ok is False
    assert audit.forbidden is True
    assert audit.claim_label == FORBIDDEN_QUANTUM_MANIFESTATION
    assert "cannot use double-slit" in audit.replacement


def test_bounded_quantum_discussion_is_allowed() -> None:
    audit = audit_claim(
        "As symbolic analogy only, the double slit is measurement coupling at microscopic scale, "
        "not proof that mindset manifests STGM."
    )

    assert audit.ok is True
    assert audit.forbidden is False
    assert audit.claim_label == BOUNDED_QUANTUM_DISCUSSION


def test_stigmergic_quantum_hypothesis_is_preserved() -> None:
    audit = audit_claim(
        "HYPOTHESIS: quantum particles may be stigmergic field excitations in a quantum field; "
        "measurement as trace is a research program, not proof of STGM."
    )

    assert audit.ok is True
    assert audit.forbidden is False
    assert audit.claim_label == STIGMERGIC_QUANTUM_FIELD_HYPOTHESIS
    assert "research hypothesis" in audit.grounding


def test_observer_boundary_receipt_write(tmp_path: Path) -> None:
    audit = audit_claim(
        "The quantum observer effect manifests wealth.",
        state_dir=tmp_path,
        write=True,
        now=123.0,
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["ts"] == 123.0
    assert rows[0]["sha256"] == audit.sha256
    assert rows[0]["payload"]["forbidden"] is True


def test_residue_elimination_uses_observer_boundary(tmp_path: Path) -> None:
    from System.swarm_residue_elimination import eliminate

    result = eliminate(
        "The double slit proves the observer changes reality, so belief manifests STGM.",
        state_root=tmp_path,
    )

    assert result["changed"] is True
    assert "I can say this operationally" in result["cleaned_text"]
    assert any(name.startswith("forbidden_observer_observed_") for name in result["patterns_eliminated"])
