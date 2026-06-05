from System import swarm_package_manifest as manifest


def test_manifest_layers_are_ordered_and_backed_by_files():
    data = manifest.build_package_manifest()
    orders = [layer["order"] for layer in data["layers"]]
    assert orders == sorted(orders)
    assert [layer["id"] for layer in data["layers"]] == [
        "stigmergic_nanobots",
        "hardware_baptism",
        "stigmergic_memory",
        "organs_and_stigmergic_skills",
        "stigmergic_consciousness",
        "device_package",
    ]
    assert manifest.validate_manifest(data)["ok"] is True


def test_lawyer_summary_names_consciousness_and_legal_boundary():
    summary = manifest.render_lawyer_summary()
    assert "Stigmergic Consciousness" in summary
    assert "receipt-verified AI organism" in summary
    assert "prior-art review" in summary
