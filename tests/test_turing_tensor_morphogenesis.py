import numpy as np
from System.swarm_turing_tensor_morphogenesis import SwarmTuringTensorMorphogenesis

def test_turing_tensor_morphogenesis():
    """
    Numerically proves:
      - 2D Reaction-Diffusion induces lateral inhibition.
      - Resulting weight matrix achieves biological sparsity (Turing Spots)
        without hardcoded magnitude pruning.
    """
    engine = SwarmTuringTensorMorphogenesis(steps=50)

    np.random.seed(42)
    m1_adapter = np.random.randn(10, 10) * 0.1
    m5_adapter = np.random.randn(10, 10) * 0.1

    # Signal setup
    m1_adapter[2, 2] = 1.5
    m1_adapter[8, 8] = 1.2
    m5_adapter[2, 2] = -0.5
    m5_adapter[5, 5] = 1.8

    # Naive merge
    naive_merge = m1_adapter + m5_adapter
    sparsity_naive = np.mean(np.abs(naive_merge) < 0.05)

    # Turing merge
    turing_merged = engine.turing_tensor_merge(m1_adapter, m5_adapter)
    sparsity_turing = np.mean(np.abs(turing_merged) < 0.05)

    # Asserts
    assert sparsity_turing > sparsity_naive, \
        "[FAIL] Turing diffusion failed to induce structural sparsity."
    assert abs(turing_merged[5, 5]) > 0.5, \
        "[FAIL] Turing diffusion destroyed an isolated critical signal."

