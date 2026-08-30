#!/usr/bin/env python3
"""Receipted pre-silicon intake for a model-specific inference chip.

This organ verifies a local Ollama model and creates the evidence package a
hardware team would need to begin model-to-silicon work. It never claims that
software export, RTL work, tapeout, or fabrication has happened without a
separate external receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


REPO = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "krishairnd/Gemma-4-Uncensored:latest"
DEFAULT_OUTPUT_ROOT = REPO / "outputs" / "model_silicon_foundry"
DEFAULT_LEDGER = REPO / ".sifta_state" / "model_silicon_foundry.jsonl"
TRUTH_LABEL = "PRE_SILICON_DEVELOPMENT_ONLY"

JsonRequester = Callable[[str, dict[str, Any] | None], dict[str, Any]]


@dataclass(frozen=True)
class ModelEvidence:
    model: str
    installed: bool
    model_id: str = ""
    digest: str = ""
    size_bytes: int = 0
    format: str = ""
    architecture: str = ""
    parameter_size: str = ""
    parameter_count: int = 0
    quantization: str = ""
    context_length: int = 0
    embedding_length: int = 0
    block_count: int = 0
    capabilities: tuple[str, ...] = ()
    parent_model: str = ""
    license_text: str = ""
    modified_at: str = ""
    error: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_requester(endpoint: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    url = f"http://127.0.0.1:11434{endpoint}"
    if payload is None:
        request = urllib.request.Request(url)
    else:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    with urllib.request.urlopen(request, timeout=8.0) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def _blob_digest(modelfile: str) -> str:
    match = re.search(r"sha256-([0-9a-fA-F]{64})", modelfile or "")
    return f"sha256:{match.group(1).lower()}" if match else ""


def _normalize_digest(value: str) -> str:
    digest = str(value or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", digest):
        return f"sha256:{digest}"
    return digest


def probe_ollama_model(
    model: str = DEFAULT_MODEL,
    *,
    requester: JsonRequester | None = None,
) -> ModelEvidence:
    """Read model identity from Ollama's live local API."""

    request_json = requester or _default_requester
    try:
        tags = request_json("/api/tags", None)
        installed_rows = [row for row in tags.get("models", []) if isinstance(row, dict)]
        selected = next(
            (row for row in installed_rows if str(row.get("name") or row.get("model") or "") == model),
            None,
        )
        if selected is None:
            return ModelEvidence(model=model, installed=False, error="Model is not installed in local Ollama.")

        shown = request_json("/api/show", {"model": model})
        details = shown.get("details") if isinstance(shown.get("details"), dict) else {}
        info = shown.get("model_info") if isinstance(shown.get("model_info"), dict) else {}
        architecture = str(details.get("family") or info.get("general.architecture") or "")
        digest = _normalize_digest(str(selected.get("digest") or "")) or _blob_digest(
            str(shown.get("modelfile") or "")
        )
        capabilities = shown.get("capabilities") if isinstance(shown.get("capabilities"), list) else []
        license_value = shown.get("license")
        if isinstance(license_value, list):
            license_text = "\n".join(str(item) for item in license_value if item)
        else:
            license_text = str(license_value or "")

        return ModelEvidence(
            model=model,
            installed=True,
            model_id=str(selected.get("model") or selected.get("name") or model),
            digest=digest,
            size_bytes=int(selected.get("size") or 0),
            format=str(details.get("format") or ""),
            architecture=architecture,
            parameter_size=str(details.get("parameter_size") or ""),
            parameter_count=int(info.get("general.parameter_count") or 0),
            quantization=str(details.get("quantization_level") or ""),
            context_length=int(info.get(f"{architecture}.context_length") or 0),
            embedding_length=int(info.get(f"{architecture}.embedding_length") or 0),
            block_count=int(info.get(f"{architecture}.block_count") or 0),
            capabilities=tuple(str(item) for item in capabilities),
            parent_model=str(details.get("parent_model") or ""),
            license_text=license_text.strip(),
            modified_at=str(shown.get("modified_at") or selected.get("modified_at") or ""),
        )
    except Exception as exc:
        return ModelEvidence(
            model=model,
            installed=False,
            error=f"Ollama probe failed: {type(exc).__name__}: {exc}",
        )


def readiness_stages(evidence: ModelEvidence) -> list[dict[str, str]]:
    """Return truth-preserving development stages for the selected model."""

    license_ready = bool(evidence.license_text.strip())
    return [
        {
            "id": "local_model_identity",
            "state": "READY" if evidence.installed and evidence.digest else "BLOCKED",
            "label": "Exact local model and weight fingerprint",
            "evidence": evidence.digest or evidence.error or "No immutable model digest observed.",
        },
        {
            "id": "license_clearance",
            "state": "READY" if license_ready else "BLOCKED",
            "label": "Weight and model license clearance",
            "evidence": "License text is attached." if license_ready else "No license text is attached to this Ollama model.",
        },
        {
            "id": "golden_numerics",
            "state": "PENDING",
            "label": "Golden prompts, logits, modalities, and tolerance corpus",
            "evidence": "The package includes a test plan; reference tensors have not been captured.",
        },
        {
            "id": "hardware_compiler",
            "state": "EXTERNAL_REQUIRED",
            "label": "Model-aware ASIC compiler and operator mapping",
            "evidence": "A GGUF runtime blob is not RTL or a foundry netlist.",
        },
        {
            "id": "rtl_verification",
            "state": "EXTERNAL_REQUIRED",
            "label": "RTL, formal checks, simulation, timing, and power closure",
            "evidence": "No EDA or verification receipt is present.",
        },
        {
            "id": "tapeout_fabrication",
            "state": "NOT_DONE",
            "label": "Tapeout, wafer fabrication, packaging, and bring-up",
            "evidence": "No foundry order, GDSII handoff, wafer, package, or measured chip exists.",
        },
    ]


def _safe_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model).strip("_") or "model"


def build_development_package(evidence: ModelEvidence, *, receipt_id: str | None = None) -> dict[str, Any]:
    """Build the portable pre-silicon intake document."""

    stages = readiness_stages(evidence)
    rid = receipt_id or str(uuid.uuid4())
    package: dict[str, Any] = {
        "schema": "SIFTA_MODEL_SILICON_INTAKE_V1",
        "truth_label": TRUTH_LABEL,
        "receipt_id": rid,
        "created_at": _utc_now(),
        "target_model": evidence.model,
        "model_evidence": asdict(evidence),
        "development_stages": stages,
        "silicon_intent": {
            "workload": "fixed-weight local generative inference",
            "reference_runtime": "Ollama/GGUF",
            "model_specific_weights": True,
            "fine_tuning_requirement": "Define adapter or patchable-memory budget before architecture freeze.",
            "modalities": list(evidence.capabilities),
        },
        "verification_plan": [
            "Freeze one exact source weight digest and tokenizer/media preprocessing contract.",
            "Resolve the base-model and derivative-weight licenses for hardware embodiment and distribution.",
            "Capture deterministic reference inputs, token IDs, selected layer tensors, logits, and outputs.",
            "Define quantized operator semantics and acceptable error per layer and end-to-end task.",
            "Compare software reference, RTL simulation, emulation, first silicon, and production silicon.",
            "Measure latency, tokens per second, energy per token, thermals, and failure recovery.",
        ],
        "required_external_deliverables": [
            "licensed source model graph and preprocessing assets",
            "supported operator inventory and hardware compiler",
            "architecture specification and RTL/netlist",
            "verification coverage and numerical equivalence reports",
            "physical design sign-off and GDSII handoff receipt",
            "foundry, package, board, firmware, driver, and bring-up receipts",
        ],
        "research_basis": [
            {
                "name": "Taalas - The Model is The Computer",
                "url": "https://taalas.com/",
                "scope": "Public model-specific custom-silicon concept; no Taalas compiler or foundry access is present here.",
            },
            {
                "name": "Taalas HC1 Technology Demonstrator",
                "url": "https://taalas.com/products/",
                "scope": "Public hardware demonstrator reference, not a specification for this Gemma derivative.",
            },
            {
                "name": "Google Gemma 4 model card",
                "url": "https://ai.google.dev/gemma/docs/core/model_card_4",
                "scope": "Base-family capabilities and license reference; derivative-weight clearance remains separate.",
            },
        ],
        "physical_silicon_status": "NOT_FABRICATED",
        "boundary": (
            "This export prepares evidence and requirements only. It does not burn weights into this Mac, "
            "produce RTL, place a foundry order, tape out a design, or fabricate a chip."
        ),
    }
    unsigned = json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    package["package_sha256"] = hashlib.sha256(unsigned).hexdigest()
    return package


def _render_markdown(package: dict[str, Any]) -> str:
    evidence = package["model_evidence"]
    size_gb = float(evidence.get("size_bytes") or 0) / 1_000_000_000
    capabilities = ", ".join(evidence.get("capabilities") or []) or "not reported"
    lines = [
        "# SIFTA Model Silicon Intake",
        "",
        f"**Truth label:** `{package['truth_label']}`  ",
        f"**Physical silicon:** `{package['physical_silicon_status']}`  ",
        f"**Receipt:** `{package['receipt_id']}`",
        "",
        "## Exact Model",
        "",
        f"- Ollama tag: `{evidence['model']}`",
        f"- Digest: `{evidence.get('digest') or 'not observed'}`",
        f"- Architecture: `{evidence.get('architecture') or 'unknown'}`",
        f"- Parameters: `{evidence.get('parameter_size') or 'unknown'}`",
        f"- Quantization: `{evidence.get('quantization') or 'unknown'}`",
        f"- Local body size: `{size_gb:.3f} GB`",
        f"- Context: `{evidence.get('context_length') or 'unknown'}` tokens",
        f"- Capabilities: {capabilities}",
        "",
        "## Readiness",
        "",
    ]
    for stage in package["development_stages"]:
        lines.append(f"- **{stage['state']}** - {stage['label']}: {stage['evidence']}")
    lines.extend(
        [
            "",
            "## Verification Plan",
            "",
            *[f"{index}. {item}" for index, item in enumerate(package["verification_plan"], 1)],
            "",
            "## Fabrication Boundary",
            "",
            package["boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def export_development_package(
    evidence: ModelEvidence,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    ledger_path: Path = DEFAULT_LEDGER,
) -> dict[str, Any]:
    """Write a model intake folder and append one body receipt."""

    package = build_development_package(evidence)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = output_root / f"{timestamp}_{_safe_name(evidence.model)}"
    folder.mkdir(parents=True, exist_ok=False)

    intake_path = folder / "silicon_intake.json"
    brief_path = folder / "VENDOR_BRIEF.md"
    vector_path = folder / "golden_vector_plan.json"
    intake_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief_path.write_text(_render_markdown(package), encoding="utf-8")
    vector_path.write_text(
        json.dumps(
            {
                "schema": "SIFTA_GOLDEN_VECTOR_PLAN_V1",
                "truth_label": "TEST_PLAN_NOT_CAPTURED_VECTORS",
                "model_digest": evidence.digest,
                "required_suites": [
                    "tokenizer and chat-template exactness",
                    "short and long text generation",
                    "tool-call serialization",
                    "vision preprocessing and inference",
                    "audio preprocessing and inference",
                    "layer checkpoints and final logits",
                    "malformed input and thermal recovery",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "SIFTA_MODEL_SILICON_RECEIPT_V1",
        "truth_label": TRUTH_LABEL,
        "receipt_id": package["receipt_id"],
        "created_at": package["created_at"],
        "model": evidence.model,
        "model_digest": evidence.digest,
        "package_sha256": package["package_sha256"],
        "physical_silicon_status": "NOT_FABRICATED",
        "folder": str(folder),
    }
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")

    return {
        "package": package,
        "folder": str(folder),
        "intake_path": str(intake_path),
        "brief_path": str(brief_path),
        "golden_vector_plan_path": str(vector_path),
        "ledger_path": str(ledger_path),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    evidence = probe_ollama_model(args.model)
    result: dict[str, Any] = {"evidence": asdict(evidence), "stages": readiness_stages(evidence)}
    if args.export:
        result["export"] = export_development_package(evidence)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Model: {evidence.model}")
        print(f"Installed: {evidence.installed}")
        print(f"Digest: {evidence.digest or 'not observed'}")
        for stage in result["stages"]:
            print(f"[{stage['state']}] {stage['label']}")
        if args.export:
            print(f"Package: {result['export']['folder']}")
        print("Physical silicon: NOT FABRICATED")
    return 0 if evidence.installed else 2


if __name__ == "__main__":
    raise SystemExit(main())
