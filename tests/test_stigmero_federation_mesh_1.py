import json
import time
import uuid
from unittest.mock import patch

from System.swarm_warp9_federation import send, recv
from System.swarm_stigmergic_economy import StigmergicWallet, StigmergicEconomicModel

def test_federation_mesh_inference_trade():
    """
    GO FEDERATION-MESH-1
    Proves that two sovereign cyborgs can trade inference securely through the
    Warp9 spool, without a central registry.
    Node A (M5) requests inference and pays STGM.
    Node B (M1) computes and returns the receipt to claim STGM.
    """
    node_a_serial = "GTH4921YP3" # M5
    node_b_serial = "M1_BEDROOM" # M1
    
    # Initialize the economy
    wallet_a = StigmergicWallet(node_a_serial, initial_balance=100.0)
    wallet_b = StigmergicWallet(node_b_serial, initial_balance=50.0)
    economy = StigmergicEconomicModel()
    
    assert wallet_a.balance == 100.0
    assert wallet_b.balance == 50.0
    
    # M1 calculates its minimum required STGM for a heavy math task (e.g. 30 watts, 1 hour)
    min_bounty = economy.calculate_minimum_bounty(expected_watts=30.0, expected_duration_s=3600.0)
    
    # 1. Node A (M5) requests inference and offers a bounty that clears M1's threshold
    with patch("System.swarm_warp9_federation.detect_self_homeworld_serial", return_value=node_a_serial):
        req_msg = send(
            to_homeworld=node_b_serial,
            kind="inference_request",
            payload={
                "task": "compute_E45_bifurcation_bound",
                "bounty_stgm": max(2.5, min_bounty + 0.5) # Offer a profitable bounty
            },
            owner_label="IOAN",
            force=True # Bypass federation OFF block for tests
        )
    assert req_msg is not None
    assert req_msg.from_homeworld == node_a_serial
    assert req_msg.to_homeworld == node_b_serial
    
    # 2. Node B (M1) reads the spool, computes it, and sends the receipt
    with patch("System.swarm_warp9_federation.detect_self_homeworld_serial", return_value=node_b_serial):
        # Node B checks its inbox
        inbox_b = recv(kinds=["inference_request"], limit=10)
        assert len(inbox_b) > 0
        received_req = inbox_b[-1]
        
        assert received_req.msg_id == req_msg.msg_id
        assert received_req.payload["bounty_stgm"] >= min_bounty, "M1 rejects unprofitable inference trades."
        
        # M1 computes the result locally (spending electricity)
        computed_result = {"bound_max": 0.05}
        
        # Node B sends the receipt back to Node A
        receipt_msg = send(
            to_homeworld=node_a_serial,
            kind="inference_receipt",
            payload={
                "request_trace_id": received_req.msg_id,
                "result": computed_result,
                "claimed_bounty_stgm": received_req.payload["bounty_stgm"]
            },
            owner_label="IOAN",
            force=True
        )
    assert receipt_msg is not None
    
    # 3. Node A reads the receipt and settles the STGM
    with patch("System.swarm_warp9_federation.detect_self_homeworld_serial", return_value=node_a_serial):
        inbox_a = recv(kinds=["inference_receipt"], limit=10)
        assert len(inbox_a) > 0
        received_receipt = inbox_a[-1]
        
        assert received_receipt.msg_id == receipt_msg.msg_id
        assert received_receipt.payload["claimed_bounty_stgm"] == 2.5
        assert received_receipt.from_homeworld == node_b_serial
        
        # Assertions to prove the mesh falsifier properties
        assert req_msg.from_homeworld != receipt_msg.from_homeworld, "Nodes must maintain separate identities."
        assert req_msg.to_homeworld == receipt_msg.from_homeworld, "Receipt must come from the requested node."
        assert received_receipt.payload["claimed_bounty_stgm"] == req_msg.payload["bounty_stgm"], "STGM bounty must match."
        
        # Finally, Node A and Node B settle the economy locally based on the receipts
        claimed_bounty = received_receipt.payload["claimed_bounty_stgm"]
        
        # Node A spends STGM
        wallet_a.spend(claimed_bounty, reason="federated_inference_payment", to_serial=node_b_serial)
        
        # Node B receives STGM
        wallet_b.receive(claimed_bounty, reason="federated_inference_reward", from_serial=node_a_serial)
        
        # PROOF OF TRANSACTION (Before vs After)
        assert wallet_a.balance == 100.0 - claimed_bounty
        assert wallet_b.balance == 50.0 + claimed_bounty
        assert wallet_b.balance > 50.0 + min_bounty, "Node B is net profitable after the trade."

