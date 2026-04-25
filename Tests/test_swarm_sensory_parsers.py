import unittest
from unittest.mock import patch, MagicMock
from System import swarm_ble_radar, swarm_awdl_mesh

class TestSensoryParsers(unittest.TestCase):
    def test_ble_band(self):
        self.assertEqual(swarm_ble_radar._band(-50, True), "near-strong")
        self.assertEqual(swarm_ble_radar._band(-60, True), "near-medium")
        self.assertEqual(swarm_ble_radar._band(-80, True), "near-weak")
        self.assertEqual(swarm_ble_radar._band(-60, False), "near-absent-medium")
        self.assertEqual(swarm_ble_radar._band(None, True), "connected-no-rssi")
        self.assertEqual(swarm_ble_radar._band(None, False), "paired-absent")

    @patch("subprocess.run")
    def test_ble_read_state(self, mock_run):
        mock_p = MagicMock()
        mock_p.returncode = 0
        mock_p.stdout = '{"SPBluetoothDataType": [{"device_connected": [{"test_dev": {"device_rssi": -60}}], "device_not_connected": [{"absent_dev": {}}]}]}'
        mock_run.return_value = mock_p
        
        state = swarm_ble_radar.read_state()
        self.assertTrue(state["ok"])
        self.assertEqual(state["device_count"], 2)
        bands = state["proximity_bands"]
        self.assertEqual(bands.get("near-medium"), 1)
        self.assertEqual(bands.get("paired-absent"), 1)

    @patch("subprocess.run")
    def test_awdl_ifconfig(self, mock_run):
        mock_p = MagicMock()
        mock_p.returncode = 0
        mock_p.stdout = "awdl0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> mtu 1484\n\tether 12:34:56:78:90:ab\n\tinet6 fe80::1234:5678:90ab:cdef%awdl0 prefixlen 64 scopeid 0x9"
        mock_run.return_value = mock_p
        
        res = swarm_awdl_mesh._ifconfig_awdl()
        self.assertTrue(res["ok"])
        self.assertTrue(res["up"])
        self.assertTrue(res["running"])
        self.assertEqual(res["ether"], "12:34:56:78:90:ab")

    @patch("subprocess.Popen")
    def test_awdl_browse_one(self, mock_popen):
        mock_p = MagicMock()
        mock_p.communicate.return_value = (
            "Timestamp     A/R Flags if Domain Service Type Instance Name\n"
            "23:38:51.123  Add  3  4 local. _airdrop._tcp. SomeName\n"
            "23:38:51.124  Rmv  3  4 local. _airdrop._tcp. OldName\n", ""
        )
        mock_popen.return_value = mock_p
        
        peers = swarm_awdl_mesh._browse_one("_airdrop._tcp", 0.1)
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0]["instance"], "SomeName")

if __name__ == "__main__":
    unittest.main()
