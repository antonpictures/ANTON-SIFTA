"""RESA SS-SA unit substation simulation model."""

from Simulations.resa_ss_sa_substation import default_order, proof_of_property


def test_ss_sa_order_has_three_core_sections() -> None:
    order = default_order()
    assert order.order_id == "SS-SA"
    assert len(order.sections) == 3
    assert order.total_breakers == 12


def test_proof_truth_label_is_simulation() -> None:
    proof = proof_of_property()
    assert proof["truth_label"] == "SIMULATION"
    assert proof["total_breakers"] == 12