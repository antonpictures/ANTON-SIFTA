import numpy as np

from System.swarm_transfer_statistical_proof import (
    TransferProofRun,
    TransferStatisticalProof,
    compute_gain,
    compute_novelty_mean_l2,
    proof_runs_path,
)


def test_compute_gain():
    assert abs(compute_gain(10.0, 15.0) - 0.5) < 1e-9


def test_compute_novelty_mean_l2():
    src = np.array([[0.0, 0.0], [1.0, 0.0]])
    tgt = np.array([[0.0, 1.0], [0.0, 0.0]])
    d = compute_novelty_mean_l2(src, tgt)
    assert d > 0


def test_prove_positive_gains(tmp_path):
    ev = TransferStatisticalProof(root=tmp_path)
    rows = [
        TransferProofRun(
            f"r{i}",
            "nav_a",
            "nav_b",
            10.0,
            15.0 + i * 0.1,
            compute_gain(10.0, 15.0 + i * 0.1),
            0.2,
            n_seeds=1,
        )
        for i in range(8)
    ]
    out = ev.prove(rows, alpha=0.05, n_bootstrap=2000, seed=42)
    assert out["n"] == 8
    assert out["mean_gain"] > 0.4
    assert out["significant"] is True
    assert out["p_value"] < 0.05


def test_log_append(tmp_path):
    ev = TransferStatisticalProof(root=tmp_path)
    row = TransferProofRun(
        "run_042",
        "nav_grid_A",
        "nav_grid_B",
        12.4,
        19.7,
        compute_gain(12.4, 19.7),
        0.31,
        n_seeds=8,
        p_value=0.008,
    )
    ev.log(row)
    text = proof_runs_path(tmp_path).read_text(encoding="utf-8").strip()
    assert "TRANSFER_PROOF_RUN" in text
    assert "run_042" in text


def test_disable_skips_log(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_TRANSFER_PROOF_DISABLE", "1")
    ev = TransferStatisticalProof(root=tmp_path)
    ev.log(
        TransferProofRun("x", "a", "b", 1, 2, 1.0, 0.1, 1, None),
    )
    assert not proof_runs_path(tmp_path).exists()
