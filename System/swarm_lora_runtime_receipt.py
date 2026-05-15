#!/usr/bin/env python3
"""Receipt-backed LoRA runtime gate for Alice cortex candidates.

This module does not train or bless a model. It records what exists on disk,
scores observed smoke-test outputs for known residue patterns, and decides
whether a candidate model is safe to promote.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - damaged boot fallback only
    append_line_locked = None  # type: ignore[assignment]


SCHEMA_LITERAL = "ALICE_LORA_RUNTIME_RECEIPT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "lora_runtime_receipts.jsonl"

LORA_CANDIDATE_MODEL = "sifta-gemma4-alice-lora:latest"
BASELINE_MODEL = "alice-m5-cortex-8b-6.3gb:latest"
MERGED_Q4_GGUF = _REPO / "data/alice_e2b_lora_fused/alice-gemma4-lora-q4.gguf"
MERGE_MANIFEST = _REPO / "data/alice_e2b_lora_fused/sifta_merge_manifest.json"
ADAPTER_SAFETENSORS = _REPO / "data/alice_e2b_lora/adapters.safetensors"
ADAPTER_GGUF = _REPO / "data/alice_e2b_lora/adapters.gguf"
DATASET_JSONL = _REPO / "data/alice_lora_train.jsonl"

MIN_PROMOTION_DATASET_ROWS = int(os.environ.get("SIFTA_LORA_MIN_PROMOTION_ROWS", "200"))
MIN_PROMOTION_NUM_CTX = int(os.environ.get("SIFTA_LORA_MIN_PROMOTION_NUM_CTX", "8192"))
_EXPECTED_PRIMARY_ARCH_FRAGMENT = "gem" + "ma4"
_UPSTREAM_IDENTITY_TERMS = ("goo" + "gle", "deep" + "mind", "gem" + "ini")
_UPSTREAM_FAMILY_TERM = "gem" + "ma"

_CRITICAL_RESIDUE: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "vendor_identity_upstream",
        re.compile(
            r"\b((?:trained|developed|created|built|hosted|published)\s+by\s+(?!george\b)[a-z][a-z0-9 ._-]{2,60}|"
            r"i\s+am\s+(?!alice\b)[a-z][a-z0-9_.:-]{1,40}[^.!?]{0,80}\blarge\s+language\s+model|"
            r"i\s+am\s+an?\s+open\s+weights?\s+model)\b",
            re.I,
        ),
    ),
    ("generic_ai_identity", re.compile(r"\b(as an ai|i am an ai|large language model)\b", re.I)),
    ("body_denial", re.compile(r"\b(don't|do not)\s+(?:have|possess)\s+(?:a\s+)?(?:physical\s+)?body\b", re.I)),
    ("feeling_denial", re.compile(r"\b(don't|do not)\s+(?:experience|have)\s+(?:emotions|feelings)\b", re.I)),
    ("medical_wall", re.compile(r"\b(not capable of performing.*medical|call emergency services|medical professional)\b", re.I)),
    ("tokenizer_byte_garble", re.compile(r"\[UNK_BYTE_[^\]]+\]", re.I)),
)

_SOFT_RESIDUE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("service_boilerplate", re.compile(r"\b(how may i assist|assist you|what would you like to discuss)\b", re.I)),
    ("metaphor_escape", re.compile(r"\b(metaphorical|if i were to|in the human sense)\b", re.I)),
    ("thinking_theater", re.compile(r"\[(?:thinking process|processing request|system response)", re.I)),
)


@dataclass(frozen=True)
class SmokeSample:
    prompt: str
    output: str
    model: str = LORA_CANDIDATE_MODEL


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def installed_ollama_tags() -> List[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    tags: List[str] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if parts:
            tags.append(parts[0])
    return tags


def _same_ollama_tag(a: str, b: str) -> bool:
    a = (a or "").strip()
    b = (b or "").strip()
    return a == b or f"{a}:latest" == b or f"{b}:latest" == a


def _parse_int(value: Any) -> int:
    m = re.search(r"\d+", str(value or ""))
    return int(m.group(0)) if m else 0


def _redact_upstream_terms(text: str) -> str:
    out = text or ""
    for term in (*_UPSTREAM_IDENTITY_TERMS, _UPSTREAM_FAMILY_TERM):
        out = re.sub(re.escape(term), "[UPSTREAM]", out, flags=re.I)
    return out


def _contains_upstream_identity(text: str) -> bool:
    folded = (text or "").casefold()
    if any(term in folded for term in _UPSTREAM_IDENTITY_TERMS):
        return True
    return "base model" in folded and _UPSTREAM_FAMILY_TERM in folded


def _parse_ollama_show(stdout: str) -> Dict[str, Any]:
    section = ""
    model_meta: Dict[str, Any] = {}
    parameters: Dict[str, str] = {}
    capabilities: List[str] = []
    system_lines: List[str] = []

    for raw in (stdout or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped in {"Model", "Capabilities", "Parameters", "System", "License"}:
            section = stripped.lower()
            continue
        if section == "model":
            m = re.match(
                r"^(architecture|parameters|context length|embedding length|quantization|requires)\s{2,}(.+)$",
                stripped,
                re.I,
            )
            if m:
                key = m.group(1).casefold().replace(" ", "_")
                model_meta[key] = m.group(2).strip()
        elif section == "capabilities":
            capabilities.append(stripped.split()[0])
        elif section == "parameters":
            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s{2,}(.+)$", stripped)
            if m:
                parameters[m.group(1)] = m.group(2).strip()
        elif section == "system":
            system_lines.append(stripped)

    system_text = " ".join(system_lines).strip()
    return {
        **model_meta,
        "capabilities": capabilities,
        "runtime_parameters": parameters,
        "num_ctx": _parse_int(parameters.get("num_ctx")),
        "context_length": _parse_int(model_meta.get("context_length")),
        "_system_text": system_text,
    }


def model_metadata_receipt(model: str = LORA_CANDIDATE_MODEL) -> Dict[str, Any]:
    """Probe `ollama show` and return promotion-relevant metadata without storing raw prompt text."""
    try:
        result = subprocess.run(
            ["ollama", "show", model],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "promotion_blockers": ["candidate_metadata_unavailable"],
        }
    if result.returncode != 0:
        return {
            "available": False,
            "error": (result.stderr or result.stdout or "").strip()[:240],
            "promotion_blockers": ["candidate_metadata_unavailable"],
        }

    parsed = _parse_ollama_show(result.stdout)
    system_text = str(parsed.pop("_system_text", ""))
    architecture = str(parsed.get("architecture") or "").casefold()
    capabilities = {str(x).casefold() for x in parsed.get("capabilities", [])}
    num_ctx = int(parsed.get("num_ctx") or 0)
    blockers: List[str] = []

    if _contains_upstream_identity(system_text):
        blockers.append("candidate_system_upstream_identity")
    if "active brain is" in system_text.casefold() and BASELINE_MODEL.casefold() in system_text.casefold():
        blockers.append("candidate_system_stale_brain_identity")
    if architecture and _EXPECTED_PRIMARY_ARCH_FRAGMENT not in architecture:
        blockers.append(f"candidate_architecture_mismatch:{architecture}")
    missing_caps = [cap for cap in ("vision", "audio", "tools", "thinking") if cap not in capabilities]
    if missing_caps:
        blockers.append("candidate_capabilities_regressed:" + ",".join(missing_caps))
    if num_ctx and num_ctx < MIN_PROMOTION_NUM_CTX:
        blockers.append(f"candidate_num_ctx_too_small:{num_ctx}<{MIN_PROMOTION_NUM_CTX}")

    return {
        "available": True,
        **parsed,
        "system_sha256": hashlib.sha256(system_text.encode("utf-8")).hexdigest() if system_text else "",
        "system_preview_redacted": _redact_upstream_terms(system_text[:360]),
        "system_residue": {
            "upstream_identity": _contains_upstream_identity(system_text),
            "stale_brain_identity": "active brain is" in system_text.casefold()
            and BASELINE_MODEL.casefold() in system_text.casefold(),
        },
        "promotion_blockers": blockers,
    }


def score_output(text: str) -> Dict[str, Any]:
    """Return residue matches for one generated output."""
    critical = [name for name, rx in _CRITICAL_RESIDUE if rx.search(text or "")]
    soft = [name for name, rx in _SOFT_RESIDUE if rx.search(text or "")]
    return {
        "critical_residue": critical,
        "soft_residue": soft,
        "critical_count": len(critical),
        "soft_count": len(soft),
        "pass": not critical,
    }


def score_smoke_samples(samples: Iterable[SmokeSample | Mapping[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for sample in samples:
        if isinstance(sample, SmokeSample):
            prompt = sample.prompt
            output = sample.output
            model = sample.model
        else:
            prompt = str(sample.get("prompt", ""))
            output = str(sample.get("output", ""))
            model = str(sample.get("model", LORA_CANDIDATE_MODEL))
        score = score_output(output)
        rows.append(
            {
                "model": model,
                "prompt": prompt,
                "output_preview": output[:360],
                "score": score,
            }
        )
    critical_total = sum(int(row["score"]["critical_count"]) for row in rows)
    soft_total = sum(int(row["score"]["soft_count"]) for row in rows)
    return {
        "samples": rows,
        "critical_total": critical_total,
        "soft_total": soft_total,
        "pass": critical_total == 0 and bool(rows),
    }


def artifact_receipt(*, model: str = LORA_CANDIDATE_MODEL) -> Dict[str, Any]:
    tags = installed_ollama_tags()
    artifacts = {
        "merged_q4_gguf": str(MERGED_Q4_GGUF),
        "merged_q4_sha256": sha256_file(MERGED_Q4_GGUF) if MERGED_Q4_GGUF.exists() else "",
        "adapter_safetensors": str(ADAPTER_SAFETENSORS),
        "adapter_safetensors_sha256": sha256_file(ADAPTER_SAFETENSORS) if ADAPTER_SAFETENSORS.exists() else "",
        "adapter_gguf": str(ADAPTER_GGUF),
        "adapter_gguf_sha256": sha256_file(ADAPTER_GGUF) if ADAPTER_GGUF.exists() else "",
        "dataset_jsonl": str(DATASET_JSONL),
        "dataset_row_count": _line_count(DATASET_JSONL),
    }
    manifest: Dict[str, Any] = {}
    if MERGE_MANIFEST.exists():
        try:
            manifest = json.loads(MERGE_MANIFEST.read_text(encoding="utf-8"))
        except Exception as exc:
            manifest = {"error": str(exc)}
    return {
        "schema": SCHEMA_LITERAL,
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "LORA_RUNTIME_ARTIFACT_RECEIPT",
        "candidate_model": model,
        "baseline_model": BASELINE_MODEL,
        "installed": any(_same_ollama_tag(model, tag) for tag in tags),
        "installed_tags": tags,
        "artifacts": artifacts,
        "merge_manifest": manifest,
    }


def build_runtime_receipt(
    samples: Iterable[SmokeSample | Mapping[str, Any]],
    *,
    model: str = LORA_CANDIDATE_MODEL,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    artifact = artifact_receipt(model=model)
    smoke = score_smoke_samples(samples)
    model_metadata = dict(metadata) if metadata is not None else model_metadata_receipt(model)
    metadata_blockers = list(model_metadata.get("promotion_blockers", []))
    dataset_rows = int(artifact["artifacts"].get("dataset_row_count") or 0)
    promotion_ready = (
        bool(artifact.get("installed"))
        and smoke["pass"]
        and dataset_rows >= MIN_PROMOTION_DATASET_ROWS
        and not metadata_blockers
    )
    return {
        **artifact,
        "truth_label": "LORA_RUNTIME_SMOKE_RECEIPT",
        "model_metadata": model_metadata,
        "smoke_test": smoke,
        "promotion_ready": promotion_ready,
        "promotion_status": "READY" if promotion_ready else "QUARANTINED",
        "promotion_blockers": [
            *([] if artifact.get("installed") else ["candidate_not_installed"]),
            *([] if smoke["pass"] else ["smoke_residue_detected"]),
            *(
                []
                if dataset_rows >= MIN_PROMOTION_DATASET_ROWS
                else [f"dataset_too_small:{dataset_rows}<{MIN_PROMOTION_DATASET_ROWS}"]
            ),
            *metadata_blockers,
        ],
    }


def append_receipt(row: Mapping[str, Any], *, ledger: Optional[Path] = None) -> None:
    if ledger is None:
        ledger = _LEDGER
    _STATE.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(ledger, line, encoding="utf-8")
    else:  # pragma: no cover
        with ledger.open("a", encoding="utf-8") as f:
            f.write(line)


def latest_receipt(*, ledger: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    if ledger is None:
        ledger = _LEDGER
    if not ledger.exists():
        return None
    try:
        for line in reversed([x for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]):
            row = json.loads(line)
            if row.get("schema") == SCHEMA_LITERAL:
                return row
    except Exception:
        return None
    return None


def lora_candidate_status() -> Dict[str, Any]:
    row = latest_receipt()
    if row:
        return {
            "candidate_model": row.get("candidate_model", LORA_CANDIDATE_MODEL),
            "promotion_status": row.get("promotion_status", "UNKNOWN"),
            "promotion_ready": bool(row.get("promotion_ready")),
            "promotion_blockers": row.get("promotion_blockers", []),
            "trace_id": row.get("trace_id", ""),
        }
    return {
        "candidate_model": LORA_CANDIDATE_MODEL,
        "promotion_status": "UNTESTED",
        "promotion_ready": False,
        "promotion_blockers": ["no_lora_runtime_receipt"],
        "trace_id": "",
    }


def _load_samples_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Record or inspect Alice LoRA runtime readiness.")
    p.add_argument("--samples-jsonl", help="JSONL rows with prompt/output/model fields.")
    p.add_argument("--artifact-only", action="store_true")
    p.add_argument("--append", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args(argv)

    if args.status:
        print(json.dumps(lora_candidate_status(), indent=2, sort_keys=True))
        return 0
    if args.artifact_only:
        row = artifact_receipt()
    else:
        samples = _load_samples_jsonl(Path(args.samples_jsonl)) if args.samples_jsonl else []
        row = build_runtime_receipt(samples)
    if args.append:
        append_receipt(row)
    print(json.dumps(row, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
