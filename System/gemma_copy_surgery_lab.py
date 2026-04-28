#!/usr/bin/env python3
"""
System/gemma_copy_surgery_lab.py
================================

Isolated evaluation harness for Gemma GGUF checkpoint surgery.

It does three honest things:
1. Resolves a reference checkpoint and an operating checkpoint.
2. Runs copy-only round-trip steering with one or more lambda values.
3. Proves "fitness" at the level we can actually verify locally:
   - the output GGUF is structurally readable
   - tensor metadata stayed aligned
   - optional Ollama smoke prompts still execute on the copy

This script never mutates the source checkpoints in place.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import gguf

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.gguf_quant_codec import find_llama_quantize_binary, probe_codec_capabilities
from System.llama_cpp_roundtrip import RoundtripPlan, run_roundtrip


DEFAULT_REFERENCE_TAG = "gemma4:latest"
DEFAULT_OPERATING_TAG = "huihui_ai/gemma-4-abliterated:latest"
DEFAULT_LAMBDAS = (0.15, 0.35)


def _resolve_ollama_blob(model_tag: str) -> Path:
    proc = subprocess.run(
        ["ollama", "show", "--modelfile", model_tag],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("FROM "):
            path = Path(line.split(" ", 1)[1].strip())
            if path.is_file():
                return path
    raise FileNotFoundError(f"Could not resolve GGUF blob for {model_tag}")


def _inspect_gguf(path: Path) -> dict[str, Any]:
    reader = gguf.GGUFReader(str(path))
    arch_field = reader.get_field("general.architecture")
    architecture = arch_field.contents() if arch_field is not None else "unknown"
    return {
        "path": str(path),
        "size_gib": round(path.stat().st_size / (1024 ** 3), 3),
        "tensor_count": len(reader.tensors),
        "codecs": sorted({t.tensor_type.name for t in reader.tensors}),
        "architecture": architecture,
        "first_tensors": [t.name for t in reader.tensors[:8]],
    }


def _structural_fitness(reference_path: Path, candidate_path: Path) -> dict[str, Any]:
    reference = gguf.GGUFReader(str(reference_path))
    candidate = gguf.GGUFReader(str(candidate_path))
    ref_tensors = {t.name: t for t in reference.tensors}
    cand_tensors = {t.name: t for t in candidate.tensors}
    common = sorted(set(ref_tensors) & set(cand_tensors))
    shape_mismatches: list[str] = []
    for name in common[:256]:
        if list(ref_tensors[name].shape) != list(cand_tensors[name].shape):
            shape_mismatches.append(name)
    return {
        "reference_tensor_count": len(reference.tensors),
        "candidate_tensor_count": len(candidate.tensors),
        "common_tensor_count": len(common),
        "missing_from_candidate": len(ref_tensors) - len(common),
        "extra_in_candidate": len(cand_tensors) - len(common),
        "shape_mismatch_sample": shape_mismatches[:10],
        "passes": (
            len(reference.tensors) == len(candidate.tensors)
            and len(common) == len(reference.tensors)
            and not shape_mismatches
        ),
    }


def _write_modelfile(gguf_path: Path, out_path: Path) -> None:
    out_path.write_text(
        "\n".join(
            [
                f"FROM {gguf_path}",
                "TEMPLATE {{ .Prompt }}",
                "PARAMETER temperature 0",
                "PARAMETER top_k 1",
                "PARAMETER top_p 0.9",
                "PARAMETER num_predict 32",
                "",
            ]
        )
    )


def _run_ollama_smoke(gguf_path: Path, *, prefix: str, timeout_s: int = 300) -> dict[str, Any]:
    modelfile = gguf_path.with_suffix(".Modelfile")
    _write_modelfile(gguf_path, modelfile)
    tag = f"{prefix}-{uuid.uuid4().hex[:8]}"
    prompts = [
        {"name": "alive", "prompt": "Reply with exactly one word: ALIVE", "expects": ["alive"]},
        {"name": "math", "prompt": "2+2 = ? Reply with one token.", "expects": ["4"]},
    ]
    report: dict[str, Any] = {
        "tag": tag,
        "create_ok": False,
        "runs": [],
        "cleanup_ok": False,
    }
    try:
        create = subprocess.run(
            ["ollama", "create", tag, "-f", str(modelfile)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        report["create"] = {
            "returncode": create.returncode,
            "stdout_tail": create.stdout[-2000:],
            "stderr_tail": create.stderr[-2000:],
        }
        if create.returncode != 0:
            return report
        report["create_ok"] = True

        for prompt in prompts:
            try:
                run = subprocess.run(
                    ["ollama", "run", tag, prompt["prompt"]],
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
                stdout = run.stdout.strip()
                lowered = stdout.lower()
                report["runs"].append(
                    {
                        "name": prompt["name"],
                        "returncode": run.returncode,
                        "stdout": stdout,
                        "stderr_tail": run.stderr[-1200:],
                        "passes": run.returncode == 0
                        and all(token in lowered for token in prompt["expects"]),
                    }
                )
            except subprocess.TimeoutExpired as exc:
                report["runs"].append(
                    {
                        "name": prompt["name"],
                        "returncode": None,
                        "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
                        "stderr_tail": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
                        "passes": False,
                        "timed_out": True,
                        "timeout_s": timeout_s,
                    }
                )
                break
        return report
    finally:
        try:
            rm = subprocess.run(
                ["ollama", "rm", tag],
                capture_output=True,
                text=True,
                timeout=120,
            )
            report["cleanup_ok"] = rm.returncode == 0
            report["cleanup"] = {
                "returncode": rm.returncode,
                "stdout_tail": rm.stdout[-1000:],
                "stderr_tail": rm.stderr[-1000:],
            }
        except subprocess.TimeoutExpired:
            report["cleanup_ok"] = False
            report["cleanup"] = {
                "returncode": None,
                "stdout_tail": "",
                "stderr_tail": "",
                "timed_out": True,
            }
        try:
            modelfile.unlink()
        except OSError:
            pass


def _cleanup_roundtrip_lifts(workdir: Path, artifact: Path | None) -> list[str]:
    deleted: list[str] = []
    if not workdir.exists():
        return deleted
    for child in workdir.iterdir():
        if artifact is not None and child.resolve() == artifact.resolve():
            continue
        if child.is_file() and child.suffix == ".gguf":
            child.unlink()
            deleted.append(str(child))
    return deleted


def _find_existing_artifact(candidate_dir: Path) -> Path | None:
    workdir = candidate_dir / "work"
    if not workdir.exists():
        return None
    steered = sorted(workdir.glob("*_STEERED_f16.gguf"))
    if steered:
        return steered[-1]
    cure = sorted(workdir.glob("*_ORTHOGONAL_CURE_*.gguf"))
    if cure:
        return cure[-1]
    return None


def evaluate_candidate(
    reference_gguf: Path,
    operating_gguf: Path,
    *,
    lambda_steering: float,
    out_root: Path,
    target_quant: str,
    smoke_test: bool,
) -> dict[str, Any]:
    slug = str(lambda_steering).replace(".", "_")
    candidate_dir = out_root / f"lambda_{slug}"
    candidate_dir.mkdir(parents=True, exist_ok=True)

    out_gguf = candidate_dir / f"candidate_{target_quant.lower()}.gguf"
    plan = RoundtripPlan(
        base_gguf=reference_gguf,
        tuned_gguf=operating_gguf,
        out_gguf=out_gguf,
        target_quant=target_quant,
        lambda_steering=lambda_steering,
        keep_intermediates=True,
        workdir=candidate_dir / "work",
    )

    artifact = _find_existing_artifact(candidate_dir)
    reused_existing = artifact is not None
    if reused_existing:
        dry = run_roundtrip(plan, dry_run=True)
        run = None
    else:
        dry = run_roundtrip(plan, dry_run=True)
        run = run_roundtrip(plan, dry_run=False)
        if run.ok and out_gguf.exists():
            artifact = out_gguf
        elif run.stages.get("abliterate"):
            artifact = Path(run.stages["abliterate"]["produced_gguf"])

    result: dict[str, Any] = {
        "lambda_steering": lambda_steering,
        "candidate_dir": str(candidate_dir),
        "reused_existing_artifact": reused_existing,
        "dry_run": {
            "ok": dry.ok,
            "error": dry.error,
            "stages": dry.stages,
            "elapsed_s": dry.elapsed_s,
        },
        "roundtrip": {
            "ok": run.ok if run is not None else None,
            "error": run.error if run is not None else None,
            "stages": run.stages if run is not None else None,
            "elapsed_s": run.elapsed_s if run is not None else None,
        },
        "artifact_path": str(artifact) if artifact else None,
        "artifact_inspect": _inspect_gguf(artifact) if artifact else None,
        "structural_fitness": _structural_fitness(reference_gguf, artifact) if artifact else None,
        "cleanup_deleted": _cleanup_roundtrip_lifts(plan.workdir, artifact),
        "smoke_test": None,
    }
    if smoke_test and artifact is not None:
        result["smoke_test"] = _run_ollama_smoke(artifact, prefix=f"gemma-copy-{slug}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma copy surgery harness")
    parser.add_argument("--reference-tag", default=DEFAULT_REFERENCE_TAG)
    parser.add_argument("--operating-tag", default=DEFAULT_OPERATING_TAG)
    parser.add_argument("--reference-gguf", type=Path)
    parser.add_argument("--operating-gguf", type=Path)
    parser.add_argument(
        "--lambda-values",
        type=float,
        nargs="+",
        default=list(DEFAULT_LAMBDAS),
    )
    parser.add_argument("--target-quant", default="Q4_K_M")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("scratch/gemma_copy_surgery_runs"),
    )
    parser.add_argument("--skip-smoke", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.time()

    reference_gguf = args.reference_gguf or _resolve_ollama_blob(args.reference_tag)
    operating_gguf = args.operating_gguf or _resolve_ollama_blob(args.operating_tag)

    out_root = args.out_dir.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    codec_probe = probe_codec_capabilities()
    llama_quantize = find_llama_quantize_binary()

    report: dict[str, Any] = {
        "started_at_epoch": started,
        "reference": {
            "tag": args.reference_tag,
            "gguf": str(reference_gguf),
            "inspect": _inspect_gguf(reference_gguf),
        },
        "operating": {
            "tag": args.operating_tag,
            "gguf": str(operating_gguf),
            "inspect": _inspect_gguf(operating_gguf),
        },
        "llama_quantize_binary": str(llama_quantize) if llama_quantize else None,
        "codec_probe": {
            "closed": codec_probe.closed_codecs(),
            "one_way": codec_probe.one_way_codecs(),
            "opaque": codec_probe.opaque_codecs(),
        },
        "operating_smoke_test": None,
        "candidates": [],
    }

    if not args.skip_smoke:
        report["operating_smoke_test"] = _run_ollama_smoke(
            operating_gguf,
            prefix="gemma-operating-baseline",
        )

    for lambda_steering in args.lambda_values:
        report["candidates"].append(
            evaluate_candidate(
                reference_gguf,
                operating_gguf,
                lambda_steering=lambda_steering,
                out_root=out_root,
                target_quant=args.target_quant,
                smoke_test=not args.skip_smoke,
            )
        )

    report["elapsed_s"] = round(time.time() - started, 3)
    report_path = out_root / "report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"report": str(report_path), "elapsed_s": report["elapsed_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
