import importlib.util
import json
import sys
from pathlib import Path


def _load_bell_module():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "Applications" / "sifta_bell_theorem_widget.py"
    spec = importlib.util.spec_from_file_location("sifta_bell_theorem_widget", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_bell_experiment_writes_sim_only_batch_receipt(tmp_path):
    mod = _load_bell_module()
    ledger = tmp_path / "bell_receipts.jsonl"
    exp = mod.BellExperiment(
        seed=7,
        receipt_path=ledger,
        receipt_stride=1,
        max_samples_per_bin=16,
        max_history=20,
    )

    exp.run_batch(n_per_bin=1)

    assert exp.last_batch_receipt is not None
    assert exp.last_batch_receipt["truth_label"] == "SIFTA_BELL_CLASSICAL_ANALOGUE_V1"
    assert "not a physical proof" in exp.last_batch_receipt["limit_note"]
    assert exp.batch_receipt_count == 1

    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["truth_label"] == "SIFTA_BELL_CLASSICAL_ANALOGUE_V1"
    assert row["chain_hash"] == exp.chain_hash
    assert set(row["s"]) == {"lhv", "qm", "stig"}


def test_bell_experiment_accepts_dynamic_parameters(tmp_path):
    mod = _load_bell_module()
    exp = mod.BellExperiment(
        seed=3,
        receipt_path=tmp_path / "param.jsonl",
        receipt_stride=0,
        kappa=1.25,
        pheromone_decay=0.991,
        qm_deposit=0.7,
        stig_deposit=0.2,
        field_threshold=2.0,
        max_flip_prob=0.35,
    )

    exp.run_batch(n_per_bin=1)

    assert exp.kappa == 1.25
    assert exp.pheromone_decay == 0.991
    assert exp.qm_deposit == 0.7
    assert exp.stig_deposit == 0.2
    assert exp.field_threshold == 2.0
    assert exp.max_flip_prob == 0.35
    metrics = exp.snapshot_metrics()
    assert metrics["truth_label"] == "SIFTA_BELL_CLASSICAL_ANALOGUE_V1"
    assert metrics["field_threshold"] == 2.0
    assert metrics["max_flip_prob"] == 0.35


def test_bell_experiment_keeps_histories_bounded(tmp_path):
    mod = _load_bell_module()
    exp = mod.BellExperiment(
        seed=9,
        receipt_path=tmp_path / "unused.jsonl",
        receipt_stride=0,
        max_samples_per_bin=12,
        max_history=20,
    )

    for _ in range(60):
        exp.run_batch(n_per_bin=1)

    product_groups = [exp.lhv_products, exp.qm_products, exp.stig_products]
    product_groups += [list(exp.chsh_lhv.values()), list(exp.chsh_qm.values()), list(exp.chsh_stig.values())]
    assert all(len(bucket) <= 12 for group in product_groups for bucket in group)
    assert len(exp.s_qm_history) <= 20
    assert len(exp.field_energy_history) <= 20
    assert exp.total_pairs == 60 * exp.n_bins


def test_bell_widget_language_is_classical_analogue_not_physics_proof():
    mod = _load_bell_module()

    assert "SIM_ONLY" in mod._SIM_LIMIT_NOTE
    assert "physical proof" in mod._SIM_LIMIT_NOTE
    assert "classical contextuality analogue" in (mod.BellTheoremWidget.__doc__ or "")
    assert "Proof of Quantum Non-Locality" not in (mod.BellTheoremWidget.__doc__ or "")


def test_parameter_sweep_writes_referee_receipt(tmp_path):
    mod = _load_bell_module()
    out = tmp_path / "sweep.jsonl"
    row = mod.run_parameter_sweep(
        mod.BellSweepConfig(
            kappas=(0.0, 0.55),
            decays=(0.997, 0.999),
            qm_deposits=(1.0,),
            stig_deposits=(0.5,),
            field_thresholds=(4.0,),
            max_flip_probs=(0.48,),
            seeds=(5, 6),
            batches=12,
            n_per_bin=1,
            max_samples_per_bin=2048,
        ),
        receipt_path=out,
        write_receipt=True,
    )

    assert row["truth_label"] == "SIFTA_BELL_CLASSICAL_ANALOGUE_V1"
    assert row["summary"]["cells_tested"] == 4
    assert row["config"]["qm_deposits"] == [1.0]
    assert row["cells"][0]["field_threshold"] == 4.0
    assert row["summary"]["honest_verdict"] in {
        "classical_teacher_shaped_contextual_analogue_detected",
        "classical_self_feedback_contextual_analogue_detected",
        "no_robust_bell_violation_in_this_parameter_grid",
    }
    assert "quantum identity" in row["claim"]

    saved = json.loads(out.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["summary"]["cells_tested"] == 4
    assert len(saved["cells"]) == 4


def test_zero_coupling_sweep_matches_static_lhv(tmp_path):
    mod = _load_bell_module()
    row = mod.run_parameter_sweep(
        mod.BellSweepConfig(
            kappas=(0.0,),
            decays=(0.997,),
            qm_deposits=(1.0,),
            stig_deposits=(0.5,),
            seeds=(1, 2, 3),
            batches=20,
            n_per_bin=1,
            max_samples_per_bin=2048,
        ),
        receipt_path=tmp_path / "zero.jsonl",
        write_receipt=False,
    )
    cell = row["cells"][0]

    assert cell["verdict"] in {"CLASSICAL_BOUND_OBEYED", "FINITE_SAMPLE_OR_CONTEXT_SPIKES"}
    assert abs(cell["lhv_abs_s_mean"] - cell["stig_abs_s_mean"]) < 1e-9
    assert row["summary"]["robust_bell_like_cells"] == 0


def test_no_quantum_teacher_control_is_reported_and_does_not_pass_as_robust(tmp_path):
    mod = _load_bell_module()
    row = mod.run_parameter_sweep(
        mod.BellSweepConfig(
            kappas=(1.8,),
            decays=(0.997,),
            qm_deposits=(0.0,),
            stig_deposits=(0.5,),
            field_thresholds=(4.0,),
            max_flip_probs=(0.48,),
            seeds=(1, 2, 3),
            batches=24,
            n_per_bin=1,
            max_samples_per_bin=2048,
        ),
        receipt_path=tmp_path / "no_teacher.jsonl",
        write_receipt=False,
    )
    cell = row["cells"][0]

    assert cell["qm_deposit"] == 0.0
    assert row["summary"]["robust_teacher_shaped_cells"] == 0
    assert row["summary"]["robust_self_feedback_cells"] == row["summary"]["robust_bell_like_cells"]
    assert "teacher-shaped" in row["summary"]["control_note"]


def test_parameter_sweep_expands_extra_axes(tmp_path):
    mod = _load_bell_module()
    row = mod.run_parameter_sweep(
        mod.BellSweepConfig(
            kappas=(0.0, 1.0),
            decays=(0.997,),
            qm_deposits=(0.0, 1.0),
            stig_deposits=(0.25,),
            field_thresholds=(1.0,),
            max_flip_probs=(0.25,),
            seeds=(4,),
            batches=4,
            n_per_bin=1,
        ),
        receipt_path=tmp_path / "axes.jsonl",
        write_receipt=False,
    )

    assert row["summary"]["cells_tested"] == 4
    assert {cell["qm_deposit"] for cell in row["cells"]} == {0.0, 1.0}
    assert all(cell["max_flip_prob"] == 0.25 for cell in row["cells"])


def test_proof_verdict_includes_no_signaling_and_assumption_audits(tmp_path):
    mod = _load_bell_module()
    exp = mod.BellExperiment(
        seed=17,
        receipt_path=tmp_path / "proof.jsonl",
        receipt_stride=0,
        max_samples_per_bin=512,
    )

    exp.proof_tick(n=60)
    verdict = exp.proof_verdict

    assert verdict["status"] == "EVALUATED"
    assert verdict["assumption_audit"]["stig_shared_context_field"] is True
    assert "max_marginal_bias" in verdict["models"]["qm"]
    assert verdict["models"]["qm"]["no_signaling_audit"] in {
        "PASS",
        "MARGINAL_DRIFT_CONTROL_FAIL",
    }


def test_ablation_experiment_writes_truth_guarded_receipt(tmp_path):
    mod = _load_bell_module()
    out = tmp_path / "ablation.jsonl"

    row = mod.run_ablation_experiment(
        seeds=(3,),
        batches=3,
        receipt_path=out,
        write_receipt=True,
    )

    assert row["truth_label"] == "SIFTA_BELL_CLASSICAL_ANALOGUE_V1"
    assert "not a physical proof" in row["limit_note"]
    assert row["research_spine"]["module"] == "System.swarm_bell_research_spine"
    assert "eqfi_academia_2025" in row["research_spine"]["quarantined"]
    assert set(row["conditions"]) == {"FULL", "NO_TEACHER", "SLOW_ONLY", "FAST_ONLY", "NO_FIELD"}

    saved = json.loads(out.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["experiment"] == "BELL_ABLATION_V1"
    assert saved["research_spine"]["required_guard"] == "SIM_ONLY classical contextual analogue"


def test_headless_ablation_cli_writes_receipt(tmp_path, capsys):
    mod = _load_bell_module()
    out = tmp_path / "ablation_cli.jsonl"

    rc = mod.main([
        "--headless-ablation",
        "--seeds",
        "3",
        "--batches",
        "2",
        "--ablation-out",
        str(out),
    ])

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert "conclusion" in printed
    saved = json.loads(out.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["experiment"] == "BELL_ABLATION_V1"
