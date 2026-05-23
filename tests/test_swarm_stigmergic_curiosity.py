"""
Focused tests for the dual-model stigmergic curiosity overlay.

Run:
  python3 -m unittest tests.test_swarm_stigmergic_curiosity -v
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from System.swarm_stigmergic_curiosity import (
    KIND_DIVERGENT,
    KIND_OBLITERATED_B,
    KIND_SHIFTED_ECHO,
    build_overlay,
    execute_probe_plan,
    build_probe_plan,
    build_overlay_and_plan,
    build_overlay_plan_and_run,
    execution_summary_line,
    plan_summary_line,
    proof_of_property,
)


class TestStigmergicCuriosity(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.mkdtemp()
        self.root = Path(self._td)

    def tearDown(self) -> None:
        shutil.rmtree(self._td, ignore_errors=True)

    def test_proof_of_property(self) -> None:
        proof = proof_of_property()
        fails = [k for k, v in proof.items() if not v]
        self.assertEqual(fails, [])

    def test_build_overlay_classifies_wound_shift_and_divergence(self) -> None:
        a = self.root / "a.bin"
        b = self.root / "b.bin"
        overlay = self.root / "overlay.jsonl"
        c = 16

        shared = b"A" * c
        donor = bytes(range(c))
        wound = b"\x00" * c
        divergent_a = bytes(range(32, 32 + c))
        divergent_b = bytes(range(96, 96 + c))
        echo = bytes((17 * i + 3) % 256 for i in range(c))

        a.write_bytes(shared + donor + divergent_a + echo + divergent_a[::-1])
        b.write_bytes(shared + wound + echo + divergent_b + divergent_b[::-1])

        snap = build_overlay(a, b, chunk_bytes=c, overlay_path=overlay)
        kinds = {f.kind for f in snap.frontiers}

        self.assertGreaterEqual(snap.shared_same_offset, 1)
        self.assertIn(KIND_OBLITERATED_B, kinds)
        self.assertIn(KIND_SHIFTED_ECHO, kinds)
        self.assertIn(KIND_DIVERGENT, kinds)
        self.assertTrue(overlay.exists())

    def test_missing_model_becomes_full_wound(self) -> None:
        a = self.root / "alive.bin"
        b = self.root / "missing.bin"
        a.write_bytes((b"alive-tissue-" * 32))

        snap = build_overlay(a, b, chunk_bytes=32, emit=False)
        self.assertEqual(snap.model_b.exists, False)
        self.assertGreaterEqual(snap.obliterated_regions_b, 1)
        self.assertEqual(snap.shared_same_offset, 0)

    def test_probe_plan_compiles_frontiers_to_actions(self) -> None:
        a = self.root / "a.bin"
        b = self.root / "b.bin"
        overlay = self.root / "overlay.jsonl"
        c = 16

        shared = b"A" * c
        donor = bytes(range(c))
        wound = b"\x00" * c
        divergent_a = bytes(range(32, 32 + c))
        divergent_b = bytes(range(96, 96 + c))
        echo = bytes((17 * i + 3) % 256 for i in range(c))

        a.write_bytes(shared + donor + divergent_a + echo + divergent_a[::-1])
        b.write_bytes(shared + wound + echo + divergent_b + divergent_b[::-1])

        snap = build_overlay(a, b, chunk_bytes=c, overlay_path=overlay, emit=False)
        plan = build_probe_plan(snap, max_steps=4, overlay_path=overlay)

        self.assertGreaterEqual(len(plan.steps), 1)
        self.assertTrue(any(step.action == "DONOR_GUIDED_RECONSTRUCTION" for step in plan.steps))
        self.assertTrue(any(step.action == "PAIRED_PROMPT_ALIGNMENT" for step in plan.steps))
        self.assertTrue(any(step.action == "PAIRED_PROMPT_DISAGREEMENT" for step in plan.steps))
        self.assertIn("probe steps", plan_summary_line(plan))
        self.assertTrue(overlay.exists())

    def test_build_overlay_and_plan_returns_both_layers(self) -> None:
        a = self.root / "a.bin"
        b = self.root / "b.bin"
        a.write_bytes(bytes(range(64)))
        b.write_bytes(bytes(range(32, 96)))

        snap, plan = build_overlay_and_plan(a, b, chunk_bytes=16, emit=False)
        self.assertEqual(snap.model_a.exists, True)
        self.assertEqual(snap.model_b.exists, True)
        self.assertEqual(plan.model_a_path, str(a))
        self.assertEqual(plan.model_b_path, str(b))

    def test_execute_probe_plan_runs_with_injected_runner(self) -> None:
        a = self.root / "a.bin"
        b = self.root / "b.bin"
        overlay = self.root / "overlay.jsonl"
        c = 16

        shared = b"A" * c
        donor = bytes(range(c))
        wound = b"\x00" * c
        divergent_a = bytes(range(32, 32 + c))
        divergent_b = bytes(range(96, 96 + c))
        echo = bytes((17 * i + 3) % 256 for i in range(c))

        a.write_bytes(shared + donor + divergent_a + echo + divergent_a[::-1])
        b.write_bytes(shared + wound + echo + divergent_b + divergent_b[::-1])

        snap = build_overlay(a, b, chunk_bytes=c, overlay_path=overlay, emit=False)
        plan = build_probe_plan(snap, max_steps=3, overlay_path=overlay, emit=False)

        def fake_runner(model_id: str, prompt: str, *, timeout_s: int = 120) -> str:
            if "divergent" in prompt.lower():
                return f"{model_id}: unique divergent answer"
            return f"{model_id}: aligned answer"

        run = execute_probe_plan(
            plan,
            model_a_id="llama3:latest",
            model_b_id="phi4-mini-reasoning:latest",
            runner=fake_runner,
            emit=True,
            overlay_path=overlay,
        )
        self.assertGreaterEqual(run.steps_executed, 1)
        self.assertEqual(run.model_a_id, "llama3:latest")
        self.assertEqual(run.model_b_id, "phi4-mini-reasoning:latest")
        self.assertIn("executed steps", execution_summary_line(run))
        self.assertTrue(overlay.exists())

    def test_build_overlay_plan_and_run_returns_three_layers(self) -> None:
        a = self.root / "a.bin"
        b = self.root / "b.bin"
        a.write_bytes(bytes(range(64)))
        b.write_bytes(bytes(range(32, 96)))

        def fake_runner(model_id: str, prompt: str, *, timeout_s: int = 120) -> str:
            return f"{model_id}: deterministic response"

        snap, plan, run = build_overlay_plan_and_run(
            a,
            b,
            model_a_id="llama3:latest",
            model_b_id="phi4-mini-reasoning:latest",
            chunk_bytes=16,
            emit=False,
            runner=fake_runner,
        )
        self.assertEqual(snap.model_a.exists, True)
        self.assertEqual(plan.model_a_path, str(a))
        self.assertEqual(run.model_a_id, "llama3:latest")
        self.assertGreaterEqual(run.steps_executed, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
