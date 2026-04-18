"""
Property tests for System/identity_field_crdt.py.

Locks the three CRDT invariants that every layer above the identity field
depends on:

    1. merge is commutative  (merge(A,B).counts == merge(B,A).counts)
    2. merge is associative  (((A.B).C) == (A.(B.C)))
    3. merge is idempotent   (A.merge(A) does not change state)

Plus the two safety invariants from the threat model:

    4. HUMAN_INTUITION_MAX_BOOST cannot flip the top hypothesis against
       a 3+ classifier-observation majority.
    5. deposit_llm_registry_entry silently caps self-attested rows at 0.7.
"""
from __future__ import annotations

import copy
import random

import pytest

from identity_field_crdt import (
    IdentityField,
    HumanIntuitionSignal,
    deposit_llm_registry_entry,
    HUMAN_INTUITION_MAX_BOOST,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _field_with_evidence(node: str, vec: dict, weight: float = 2.0) -> IdentityField:
    f = IdentityField()
    f.update_from_classifier(node, vec, weight=weight)
    return f


def _counts_eq(a: IdentityField, b: IdentityField) -> bool:
    """Structural equality on the G-counter payload only."""
    if set(a.counts) != set(b.counts):
        return False
    for node in a.counts:
        if a.counts[node].keys() != b.counts[node].keys():
            return False
        for m, v in a.counts[node].items():
            if abs(v - b.counts[node][m]) > 1e-12:
                return False
    return True


# ─── 1. Commutativity ──────────────────────────────────────────────────────


def test_merge_is_commutative():
    a = _field_with_evidence("C47H", {"opus": 0.7, "gpt": 0.2, "gem": 0.1}, weight=3)
    b = _field_with_evidence("AG31", {"gem": 0.6, "opus": 0.3, "gpt": 0.1}, weight=2)

    ab = IdentityField()
    ab.merge(a)
    ab.merge(b)

    ba = IdentityField()
    ba.merge(b)
    ba.merge(a)

    assert _counts_eq(ab, ba)
    assert ab.distribution() == ba.distribution()


# ─── 2. Associativity ──────────────────────────────────────────────────────


def test_merge_is_associative():
    a = _field_with_evidence("A", {"x": 0.5, "y": 0.5}, weight=2)
    b = _field_with_evidence("B", {"y": 0.8, "z": 0.2}, weight=2)
    c = _field_with_evidence("C", {"x": 0.1, "z": 0.9}, weight=2)

    # (A . B) . C
    left = IdentityField()
    left.merge(a); left.merge(b); left.merge(c)

    # A . (B . C)
    bc = IdentityField()
    bc.merge(b); bc.merge(c)
    right = IdentityField()
    right.merge(a); right.merge(bc)

    assert _counts_eq(left, right)


# ─── 3. Idempotence ────────────────────────────────────────────────────────


def test_merge_is_idempotent():
    f = _field_with_evidence("N1", {"u": 0.3, "v": 0.7}, weight=4)
    snap = copy.deepcopy(f.counts)
    f.merge(f)
    assert f.counts == snap


def test_merge_idempotent_random_streams():
    rng = random.Random(42)
    nodes = ["N0", "N1", "N2", "N3"]
    models = ["mA", "mB", "mC", "mD"]
    fields = []
    for n in nodes:
        vec = {m: rng.random() for m in models}
        f = IdentityField()
        f.update_from_classifier(n, vec, weight=rng.randint(1, 4))
        fields.append(f)

    merged = IdentityField()
    for f in fields:
        merged.merge(f)
    snap = copy.deepcopy(merged.counts)

    # Merging any subset a second time must not change counts.
    for f in fields:
        merged.merge(f)
    assert merged.counts == snap


# ─── 4. Human intuition cannot flip a classifier majority ──────────────────


def test_intuition_cannot_flip_classifier_majority():
    """
    Three classifier observations at weight=3 stack mass on 'opus-4.7'.
    One intuition signal at confidence=1.0 pushes toward 'gpt-5.3'.
    The CRDT top must stay 'opus-4.7'.
    """
    f = IdentityField()
    for _ in range(3):
        f.update_from_classifier(
            "C47H", {"opus-4.7": 0.9, "gpt-5.3": 0.1}, weight=3
        )
    intuition = HumanIntuitionSignal(
        label="gpt-5.3", confidence=1.0, observer="architect",
    )
    f.update_from_human_intuition("ARCHITECT", intuition, weight=0.25)

    top, _ = f.top()
    assert top == "opus-4.7", f"intuition hijacked the field: top={top}"


def test_human_intuition_boost_is_capped():
    """
    Even at confidence=1.0 and weight=10, the pseudo-count added per call
    must not exceed HUMAN_INTUITION_MAX_BOOST.
    """
    f = IdentityField()
    intuition = HumanIntuitionSignal(label="x", confidence=1.0)
    before = f.counts.get("ARCHITECT", {}).get("x", 0.0)
    f.update_from_human_intuition("ARCHITECT", intuition, weight=10.0)
    after = f.counts["ARCHITECT"]["x"]
    delta = after - before
    assert delta <= HUMAN_INTUITION_MAX_BOOST + 1e-9, (
        f"intuition added {delta}, cap is {HUMAN_INTUITION_MAX_BOOST}"
    )


# ─── 5. Self-attestation cap on deposits ───────────────────────────────────


def test_deposit_caps_self_attested_confidence(tmp_path, monkeypatch):
    """deposited_by == trigger_code and confidence > 0.7 must be capped to 0.7."""
    log = tmp_path / "reg.jsonl"
    row = deposit_llm_registry_entry(
        trigger_code="NODE",
        model_family="fam",
        model_version="v1",
        substrate="test",
        confidence_attestation=0.99,
        deposited_by="NODE",
        session_id="cap-test",
        anomaly_flag=False,
        behavior_fingerprint="CAP-TEST",
        notes="",
        path=log,
    )
    assert row["llm_signature"]["confidence_attestation"] == 0.7


def test_deposit_does_not_cap_external_rows(tmp_path):
    """deposited_by != trigger_code may exceed 0.7 (externally observed)."""
    log = tmp_path / "reg.jsonl"
    row = deposit_llm_registry_entry(
        trigger_code="NODE",
        model_family="fam",
        model_version="v1",
        substrate="test",
        confidence_attestation=0.95,
        deposited_by="OBSERVER",
        session_id="ext-test",
        anomaly_flag=False,
        behavior_fingerprint="EXT-TEST",
        notes="",
        path=log,
    )
    assert row["llm_signature"]["confidence_attestation"] == pytest.approx(0.95)
