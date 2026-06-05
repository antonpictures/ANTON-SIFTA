from pathlib import Path

from System.swarm_quantum_data_sentinel import (
    QUANTUM_DATA_SOURCES,
    TRUTH_LABEL,
    analyze_qdataset_for_sifta,
    format_qdataset_analysis,
    format_quantum_experiment_inventory,
    format_quantum_data_sentinel,
    load_recent_quantum_data_reports,
    local_bell_pair_samples,
    quantum_experiment_inventory,
    quantum_data_sentinel_report,
)
from System.swarm_quantum_swimmer_sentinel import ingest_quantum_priors


def test_catalog_marks_cloud_hardware_as_requiring_receipts():
    by_id = {src.source_id: src for src in QUANTUM_DATA_SOURCES}

    assert "ibm_quantum_runtime_jobs" in by_id
    assert "requires_ibm_quantum_token" in by_id["ibm_quantum_runtime_jobs"].access
    assert "No IBM token/job id means no hardware claim" in by_id["ibm_quantum_runtime_jobs"].truth_boundary

    assert "microsoft_majorana2" in by_id
    assert "no public QPU data lane observed" in by_id["microsoft_majorana2"].access


def test_local_bell_pair_sampler_is_receipted_as_simulator_not_qpu():
    row = local_bell_pair_samples(shots=32, seed=7)

    assert row["truth_boundary"] == "CLASSICAL_LOCAL_SIMULATOR_NOT_QPU"
    assert sum(row["counts"].values()) == 32
    assert set(row["counts"]) == {"00", "11"}
    assert len(row["sample_hash"]) == 64


def test_report_writes_jsonl_and_formats(tmp_path: Path):
    report = quantum_data_sentinel_report(state_dir=tmp_path, write_receipt=True)

    assert report["truth_label"] == TRUTH_LABEL
    assert report["source_count"] >= 6
    assert "provider job id" in report["no_fake_claim"]

    rows = load_recent_quantum_data_reports(state_dir=tmp_path)
    assert rows and rows[-1]["trace_id"] == report["trace_id"]

    line = format_quantum_data_sentinel(state_dir=tmp_path, max_sources=2)
    assert "Quantum Data Sentinel" in line
    assert "No cloud/QPU claim" in line
    assert "qdataset_qml_open" in line


def test_swimmer_sentinel_builtin_rows_are_priors_not_original_qpu_data():
    row = ingest_quantum_priors("majorana2_2026")

    assert row["authenticity"] == "built_in_public_claim_prior_not_original_qpu_payload"

    custom = ingest_quantum_priors(custom_data={"source": "ibm-demo", "provider_job_id": "job-1"})
    assert custom["authenticity"] == "provider_receipted_original_data"


def test_qdataset_analysis_is_not_a_duplicate_source(tmp_path: Path):
    source_ids = [src.source_id for src in QUANTUM_DATA_SOURCES]
    assert source_ids.count("qdataset_qml_open") == 1

    row = analyze_qdataset_for_sifta(state_dir=tmp_path, write_receipt=True)

    assert row["already_registered"] is True
    assert row["duplicate_count"] == 1
    assert row["duplicate_guard"] == "already_registered_no_new_source_needed"
    assert "not QPU output" in row["truth_boundary"]
    assert row["dataset_facts"]["datasets"] == 52
    assert row["dataset_facts"]["samples_each"] == 10000
    assert "Pauli" in row["sifta_analysis"]["why_it_matters"]

    ledger = (tmp_path / "quantum_data_sentinel.jsonl").read_text(encoding="utf-8")
    assert "qdataset_sifta_analysis" in ledger


def test_quantum_inventory_names_existing_work_and_next_non_duplicate(tmp_path: Path):
    row = quantum_experiment_inventory(state_dir=tmp_path, write_receipt=True)

    assert row["duplicate_source_ids"] == []
    assert "qdataset_qml_open" in row["source_ids"]
    assert "local_tfim_ground_state exact diagonalization" in row["already_done_operational"]
    assert "qdataset_first_slice_noise_tomography" in row["suggested_experiment_ids"]
    assert "qdataset_first_slice_noise_tomography" in row["next_non_duplicate_experiments"]

    line = format_quantum_experiment_inventory(state_dir=tmp_path)
    assert "duplicates=none" in line
    assert "qdataset_first_slice_noise_tomography" in line


def test_qdataset_format_gives_analysis_not_just_catalog(tmp_path: Path):
    line = format_qdataset_analysis(state_dir=tmp_path)

    assert "already_registered=True" in line
    assert "duplicate_guard=already_registered_no_new_source_needed" in line
    assert "52 datasets x 10000 samples" in line
    assert "first_swimmer_experiment" in line
