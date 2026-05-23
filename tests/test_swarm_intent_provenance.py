"""Intent provenance — who decided, with consent and decision path."""

from System import swarm_intent_provenance as ip


def test_owner_explicit():
    src, con, note = ip.normalize_legacy_source("owner_explicit")
    assert src == "owner"
    assert con == "explicit"
    assert note == ""


def test_alice_autonomous_router_vs_gate():
    m, c, _ = ip.normalize_legacy_source(
        "alice_autonomous", routed_via_tool_router=True
    )
    assert m == "model"
    assert c == "implicit"
    r, c2, _ = ip.normalize_legacy_source(
        "alice_autonomous", routed_via_tool_router=False
    )
    assert r == "reflex"
    assert c2 == "implicit"


def test_merge_into_receipt_adds_block():
    row = {"source": "alice_autonomous", "ok": True, "tool": "send_whatsapp"}
    out = ip.merge_into_receipt(
        row,
        legacy_source="alice_autonomous",
        routed_via_tool_router=True,
        decision_path=["cosmos", "tool_router", "effector"],
    )
    assert out["intent_provenance"]["intent_source"] == "model"
    assert out["intent_provenance"]["decision_path"] == [
        "cosmos",
        "tool_router",
        "effector",
    ]
    assert out["intent_provenance"]["receipt_proof"] is True


def test_intent_provenance_classify():
    d = ip.IntentProvenance.classify(
        legacy_source="alice_tool_router_architect_consent",
    )
    assert d["intent_source"] == "owner"
    assert d["consent"] == "explicit"
