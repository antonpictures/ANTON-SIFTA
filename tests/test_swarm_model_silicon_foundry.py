import json
from pathlib import Path

from System.swarm_model_silicon_foundry import (
    ModelEvidence,
    build_development_package,
    export_development_package,
    probe_ollama_model,
    readiness_stages,
)


MODEL = "krishairnd/Gemma-4-Uncensored:latest"
DIGEST = "sha256:" + "a" * 64


def _requester(endpoint, payload):
    if endpoint == "/api/tags":
        return {
            "models": [
                {
                    "name": MODEL,
                    "model": MODEL,
                    "digest": DIGEST,
                    "size": 6_300_000_000,
                    "modified_at": "2026-06-06T00:00:00Z",
                }
            ]
        }
    assert endpoint == "/api/show"
    assert payload == {"model": MODEL}
    return {
        "details": {
            "format": "gguf",
            "family": "gemma4",
            "parameter_size": "8.0B",
            "quantization_level": "Q4_K_M",
            "parent_model": "parent/model:latest",
        },
        "model_info": {
            "general.parameter_count": 7_996_157_674,
            "gemma4.context_length": 131_072,
            "gemma4.embedding_length": 2_560,
            "gemma4.block_count": 42,
        },
        "capabilities": ["completion", "vision", "audio", "tools", "thinking"],
    }


def test_probe_reads_exact_live_ollama_identity():
    evidence = probe_ollama_model(MODEL, requester=_requester)

    assert evidence.installed is True
    assert evidence.digest == DIGEST
    assert evidence.architecture == "gemma4"
    assert evidence.parameter_size == "8.0B"
    assert evidence.parameter_count == 7_996_157_674
    assert evidence.quantization == "Q4_K_M"
    assert evidence.context_length == 131_072
    assert "vision" in evidence.capabilities


def test_missing_model_is_blocked_without_fabrication_claim():
    evidence = probe_ollama_model("missing:latest", requester=_requester)
    stages = readiness_stages(evidence)

    assert evidence.installed is False
    assert stages[0]["state"] == "BLOCKED"
    assert stages[-1]["state"] == "NOT_DONE"


def test_package_keeps_license_and_physical_silicon_blocked():
    evidence = probe_ollama_model(MODEL, requester=_requester)
    package = build_development_package(evidence, receipt_id="test-receipt")

    states = {stage["id"]: stage["state"] for stage in package["development_stages"]}
    assert package["truth_label"] == "PRE_SILICON_DEVELOPMENT_ONLY"
    assert package["physical_silicon_status"] == "NOT_FABRICATED"
    assert states["local_model_identity"] == "READY"
    assert states["license_clearance"] == "BLOCKED"
    assert states["hardware_compiler"] == "EXTERNAL_REQUIRED"
    assert len(package["package_sha256"]) == 64


def test_export_writes_vendor_package_and_append_only_receipt(tmp_path: Path):
    evidence = ModelEvidence(
        model=MODEL,
        installed=True,
        digest=DIGEST,
        size_bytes=6_300_000_000,
        format="gguf",
        architecture="gemma4",
        parameter_size="8.0B",
        parameter_count=7_996_157_674,
        quantization="Q4_K_M",
        context_length=131_072,
        capabilities=("completion", "vision", "audio", "tools", "thinking"),
    )
    ledger = tmp_path / "state" / "ledger.jsonl"
    result = export_development_package(
        evidence,
        output_root=tmp_path / "packages",
        ledger_path=ledger,
    )

    folder = Path(result["folder"])
    assert (folder / "silicon_intake.json").is_file()
    assert (folder / "VENDOR_BRIEF.md").is_file()
    assert (folder / "golden_vector_plan.json").is_file()
    assert "**Physical silicon:** `NOT_FABRICATED`" in (folder / "VENDOR_BRIEF.md").read_text()
    plan = json.loads((folder / "golden_vector_plan.json").read_text())
    assert plan["truth_label"] == "TEST_PLAN_NOT_CAPTURED_VECTORS"
    receipt = json.loads(ledger.read_text().strip())
    assert receipt["physical_silicon_status"] == "NOT_FABRICATED"
    assert receipt["model_digest"] == DIGEST


def test_model_silicon_foundry_is_registered_as_developer_app():
    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "Applications" / "apps_manifest.json").read_text())
    entry = manifest["Model Silicon Foundry"]

    assert entry["category"] == "Developer"
    assert entry["entry_point"] == "Applications/sifta_model_silicon_foundry.py"
    assert entry["widget_class"] == "ModelSiliconFoundryWidget"
    assert entry["truth_label"] == "PRE_SILICON_DEVELOPMENT_ONLY"
