from __future__ import annotations

import numpy as np

from swarmrl.tasks import StigmergicEntropyGate
from Utilities.stigmergic_entropy_gate_demo import run_demo


def test_task_export_and_sense_field():
    task = StigmergicEntropyGate()
    assert task.sense_field(np.array([0.5, 0.5], dtype=np.float32)) == 0.0

    task.step(np.array([[0.1, 0.1], [0.2, 0.2]], dtype=np.float32))
    task.step(np.array([[0.2, 0.1], [0.3, 0.2]], dtype=np.float32))

    assert task.field.max() > 0.0
    assert task.glyph()


def test_standalone_demo_writes_memory():
    result = run_demo(n_agents=8, steps=12, glyph_every=0, seed=123, clear=False)

    assert result["field_max"] > 0.0
    assert result["reward_total"] > 0.0
    assert result["glyph"]
