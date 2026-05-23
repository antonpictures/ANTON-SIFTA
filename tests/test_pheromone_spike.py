import unittest
import time
from System.swarm_pheromone import deposit_pheromone, PHEROMONE_FIELD

class TestPheromoneSpike(unittest.TestCase):
    def test_spike_focus(self):
        # Reset field to baseline
        for organ in list(PHEROMONE_FIELD.P.keys()):
            PHEROMONE_FIELD.P[organ] = 0.0
            
        # Deposit high intensity as requested: "deposit a high intensity to stig_awdl_mesh, wait 2 s, assert IdentitySnapshot.pheromone_focus == 'stig_awdl_mesh'"
        deposit_pheromone("stig_awdl_mesh", 1000.0)
        time.sleep(2.0)
        
        focus, intensity = PHEROMONE_FIELD.chemotaxis()
        self.assertEqual(focus, "stig_awdl_mesh")
        self.assertGreater(intensity, 100.0)

if __name__ == "__main__":
    unittest.main()
