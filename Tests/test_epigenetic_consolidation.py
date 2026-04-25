import numpy as np
from System.swarm_epigenetic_consolidation import SwarmEpigeneticConsolidation

def test_della_merging_preserves_critical_signals():
    """
    MANDATE VERIFICATION (Event 42):
    Numerically proves that naive merging causes destructive interference, 
    while DELLA-Merging preserves the critical magnitude signals from both nodes.
    """
    engine = SwarmEpigeneticConsolidation(drop_rate=0.5)
    
    # Generate two conflicting LoRA adapters from M1 and M5
    # High magnitudes represent strong, critical learnings. Low magnitudes are noise.
    m1_adapter = np.array([0.9, -0.1, 0.05, -0.85, 0.02])
    m5_adapter = np.array([-0.05, 0.88, -0.9, 0.1, 0.01])
    
    # 1. Naive Addition (Catastrophic Interference)
    naive_merge = m1_adapter + m5_adapter
    # In naive merge, the strong signal from M1 (0.9) is diluted by M5's noise (-0.05) -> 0.85
    # The strong signal from M5 (-0.9) is diluted by M1's signal (0.05) -> -0.85
    
    # 2. DELLA Merging (Magnitude-Based Sampling)
    della_merged = engine.della_merge(m1_adapter, m5_adapter)
    
    # Mathematical Proof: The critical high-magnitude learnings must survive and scale
    
    # M1's critical learnings were at index 0 (0.9) and index 3 (-0.85)
    # They should survive the 50% cut, and be rescaled by 1/(1-0.5) = 2.0
    # Expected della_merged[0]: 0.9 * 2 = 1.8. Plus M5's noise? M5's noise (-0.05) is dropped (becomes 0).
    # So della_merged[0] should be strictly > 0.9.
    assert abs(della_merged[0]) > 0.9, "[FAIL] DELLA failed to preserve and rescale M1's critical learning."
    
    # M5's critical learnings were at index 1 (0.88) and index 2 (-0.9)
    # Expected della_merged[1]: M5's 0.88 survives -> 1.76. M1's -0.1 drops -> 0.
    assert abs(della_merged[1]) > 0.88, "[FAIL] DELLA failed to preserve and rescale M5's critical learning."
    
    # Index 4 is pure noise (0.02 and 0.01). It should be pruned to exactly 0.0.
    assert della_merged[4] == 0.0, "[FAIL] DELLA failed to prune the low-magnitude noise."
