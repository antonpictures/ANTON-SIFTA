from __future__ import annotations

import unittest


class TestLogisticsHijackWaybill(unittest.TestCase):
    def test_waybill_verify_rejects_forgery(self):
        from Applications.sifta_logistics_swarm_sim import WaybillKeys, _waybill_payload

        owners = ["ARCHITECT_M1", "ARCHITECT_M5"]
        keys = WaybillKeys(owners, seed=123)

        owner = "ARCHITECT_M1"
        payload = _waybill_payload(owner, 0, (1, 2), (3, 4), 111)
        sig = keys.sign(owner, payload)
        self.assertTrue(keys.verify(owner, payload, sig))

        forged = b"\x00" * 64
        self.assertFalse(keys.verify(owner, payload, forged))

