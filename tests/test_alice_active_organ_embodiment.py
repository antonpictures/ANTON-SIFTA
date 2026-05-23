from System import alice_active_organ_embodiment as organ


def test_active_organ_context_uses_receipts_without_identity_lecture(monkeypatch):
    monkeypatch.setattr(organ, "get_app_health", lambda app_name, limit=8: [{"app": app_name}])
    monkeypatch.setattr(organ, "get_required_skills_for_app", lambda app_name: ["current_app_receipts"])
    monkeypatch.setattr(
        organ,
        "build_alice_self_vector",
        lambda **_: {
            "identity_continuity": 0.9,
            "memory_entropy": 0.4,
            "receipt_integrity": 1.0,
            "reality_boundary_integrity": 1.0,
            "stigmergic_momentum": 0.8,
            "next_best_action": "answer_from_receipts",
        },
    )
    monkeypatch.setattr(
        organ,
        "label_knowledge",
        lambda item: {"reality_boundary": {"label": "OBSERVED", "item": item}},
    )

    ctx = organ.enter_organ_context("Ace")

    assert ctx["active_organ"] == "Ace"
    assert "Answer from this app's receipts" in ctx["instruction_to_alice"]
    assert "Do not explain identity" in ctx["instruction_to_alice"]
