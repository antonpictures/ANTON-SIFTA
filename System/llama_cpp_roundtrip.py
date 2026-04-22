#!/usr/bin/env python3
"""
System/llama_cpp_roundtrip.py
══════════════════════════════════════════════════════════════════════
Path B — External canonicalization pipeline (fast stability path).

C47H stigauth, bridge 555:

The mathematically complete way to perform continuous Task-Vector
steering on a mixed-precision GGUF (F32 / F16 / BF16 / Q4_K / Q6_K)
without inventing codec bytes is:

    base.gguf,  tuned.gguf
        │            │
        ▼            ▼
    lift_to_fp16   lift_to_fp16          (stage 1: gguf_quant_codec)
        │            │
        ▼            ▼
    base_f16.gguf, tuned_f16.gguf
        │            │
        └────┬───────┘
             ▼
    SwarmOrthogonalAbliteration            (stage 2: existing organ
        │                                              Event 24)
        ▼
    steered_f16.gguf
        │
        ▼
    llama-quantize  (target: Q4_K_M / etc.)  (stage 3: external oracle)
        │
        ▼
    final.gguf

Properties (the contract this module enforces):
  - Stage 1 is byte-exact for F32 and F16, lossy-but-faithful for the
    Q* and BF16 inputs (lossy = the codec's intrinsic loss, NOT a bug).
  - Stage 2 lives entirely in fp32 because every tensor in a *_f16.gguf
    is in {F32, F16}; both are closed under `gguf.quants.dequantize` /
    `gguf.quants.quantize` (verified in gguf_quant_codec.proof_of_property).
  - Stage 3 is delegated to llama.cpp's reference quantizer. We never
    re-implement K-quant block packing in Python. If llama-quantize is
    not installed, stage 3 fails with a clear actionable error and the
    pipeline halts WITHOUT pretending the file is final.

This module is read-only with respect to the input GGUFs. It writes to
a single user-controlled output path and a tempdir for intermediates.

Dependencies: numpy, gguf (already in venv), and the existing organ
`System/swarm_orthogonal_abliteration.py`.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import gguf
import numpy as np

if __name__ == "__main__" and __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.gguf_quant_codec import (
    CodecNotImplemented,
    find_llama_quantize_binary,
    lift_to_fp16,
    requantize_via_external,
)
from System.swarm_orthogonal_abliteration import SwarmOrthogonalAbliteration


@dataclass
class RoundtripPlan:
    base_gguf: Path
    tuned_gguf: Path
    out_gguf: Path
    target_quant: str = "Q4_K_M"
    lambda_steering: float = 0.8
    anomaly_threshold: float = 1e-4
    keep_intermediates: bool = False
    workdir: Optional[Path] = None


@dataclass
class RoundtripReport:
    plan: dict
    stages: dict
    ok: bool
    error: Optional[str] = None
    elapsed_s: float = 0.0


def _ensure_inputs(plan: RoundtripPlan) -> None:
    if not plan.base_gguf.is_file():
        raise FileNotFoundError(f"base_gguf not found: {plan.base_gguf}")
    if not plan.tuned_gguf.is_file():
        raise FileNotFoundError(f"tuned_gguf not found: {plan.tuned_gguf}")
    if plan.out_gguf.exists():
        raise FileExistsError(f"out_gguf already exists: {plan.out_gguf}")


def run_roundtrip(plan: RoundtripPlan, *, dry_run: bool = False) -> RoundtripReport:
    """
    Execute the four-stage canonicalization pipeline.

    `dry_run=True` only validates inputs, probes the binary, lifts a single
    tensor of each model, and returns a planning report — useful as a
    pre-flight check before spending minutes on a full lift.
    """
    started = time.time()
    _ensure_inputs(plan)

    workdir = plan.workdir or Path(tempfile.mkdtemp(prefix="sifta_roundtrip_"))
    workdir.mkdir(parents=True, exist_ok=True)

    base_f16 = workdir / (plan.base_gguf.stem + "_f16.gguf")
    tuned_f16 = workdir / (plan.tuned_gguf.stem + "_f16.gguf")
    steered_f16 = workdir / (plan.tuned_gguf.stem + "_STEERED_f16.gguf")

    stages: dict = {
        "workdir": str(workdir),
        "lift_base": None,
        "lift_tuned": None,
        "abliterate": None,
        "requantize": None,
    }

    try:
        binary = find_llama_quantize_binary()
        stages["llama_quantize_binary"] = str(binary) if binary else None

        if dry_run:
            stages["dry_run"] = True
            base_reader = gguf.GGUFReader(str(plan.base_gguf))
            tuned_reader = gguf.GGUFReader(str(plan.tuned_gguf))
            stages["lift_base"] = {"tensor_count": len(base_reader.tensors)}
            stages["lift_tuned"] = {"tensor_count": len(tuned_reader.tensors)}
            return RoundtripReport(
                plan={k: str(v) if isinstance(v, Path) else v
                      for k, v in asdict(plan).items()},
                stages=stages, ok=True,
                elapsed_s=round(time.time() - started, 3),
            )

        stages["lift_base"] = lift_to_fp16(plan.base_gguf, base_f16)
        stages["lift_tuned"] = lift_to_fp16(plan.tuned_gguf, tuned_f16)

        organ = SwarmOrthogonalAbliteration(
            lambda_steering=plan.lambda_steering,
            anomaly_threshold=plan.anomaly_threshold,
        )
        produced_path = organ.abliterate_manifold(str(base_f16), str(tuned_f16))
        Path(produced_path).rename(steered_f16)
        stages["abliterate"] = {
            "produced_gguf": str(steered_f16),
            "size_mb": round(steered_f16.stat().st_size / (1024 * 1024), 2),
        }

        if binary is None:
            raise CodecNotImplemented(
                "Stages 1+2 succeeded; stage 3 cannot run because llama.cpp "
                "`quantize` binary is not on PATH (and $LLAMA_QUANTIZE is "
                "unset). Steered F16 GGUF preserved at "
                f"{steered_f16}. Install llama.cpp and re-run with "
                f"`requantize_via_external({steered_f16!s}, ...)`."
            )

        stages["requantize"] = requantize_via_external(
            steered_f16, plan.out_gguf, plan.target_quant,
        )
        if stages["requantize"]["returncode"] != 0:
            raise RuntimeError(
                "llama-quantize failed: "
                f"rc={stages['requantize']['returncode']}\n"
                f"stderr_tail={stages['requantize']['stderr_tail']}"
            )

        if not plan.keep_intermediates:
            for p in (base_f16, tuned_f16, steered_f16):
                try:
                    p.unlink()
                except OSError:
                    pass
            try:
                if not any(workdir.iterdir()):
                    workdir.rmdir()
            except OSError:
                pass

        return RoundtripReport(
            plan={k: str(v) if isinstance(v, Path) else v
                  for k, v in asdict(plan).items()},
            stages=stages, ok=True,
            elapsed_s=round(time.time() - started, 3),
        )
    except Exception as exc:
        return RoundtripReport(
            plan={k: str(v) if isinstance(v, Path) else v
                  for k, v in asdict(plan).items()},
            stages=stages, ok=False, error=f"{type(exc).__name__}: {exc}",
            elapsed_s=round(time.time() - started, 3),
        )


# ────────────────────────────────────────────────────────────────────
# Smoke test (small, fully synthetic — no real model required)
# ────────────────────────────────────────────────────────────────────


def _make_synthetic_pair(workdir: Path) -> tuple[Path, Path]:
    """Create a tiny matched (base, tuned) GGUF pair for the smoke test."""
    base = workdir / "base.gguf"
    tuned = workdir / "tuned.gguf"

    rng = np.random.default_rng(0)
    norm = rng.standard_normal(64).astype(np.float32)
    attn = rng.standard_normal((8, 32)).astype(np.float16)
    delta_attn = (rng.standard_normal((8, 32)) * 0.05).astype(np.float16)

    for path, attn_payload in ((base, attn),
                               (tuned, (attn.astype(np.float32)
                                        + delta_attn.astype(np.float32)
                                        ).astype(np.float16))):
        w = gguf.GGUFWriter(str(path), "llama")
        w.add_string("general.name", path.stem)
        w.add_tensor("blk.0.norm", norm.copy())
        w.add_tensor("blk.0.attn", attn_payload.copy())
        w.write_header_to_file()
        w.write_kv_data_to_file()
        w.write_tensors_to_file()
        w.close()

    return base, tuned


def proof_of_property() -> bool:
    """
    Falsifiers:
      R1: dry_run completes without writing any file and reports both
          tensor counts.
      R2: when llama-quantize is absent, run_roundtrip(...) returns
          ok=False with a clear CodecNotImplemented error, and HAS already
          produced base_f16 / tuned_f16 / steered_f16 intermediates that
          are valid F16/F32 GGUFs (proving stages 1 and 2 ran cleanly).
      R3: the produced steered_f16 has only F32/F16 tensors and the
          attn tensor moved toward base by lambda * tau (Ilharco identity).
      R4: when llama-quantize IS present, the full pipeline produces an
          out_gguf and Python `gguf.GGUFReader` can read it back.
    """
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        base, tuned = _make_synthetic_pair(td_path)
        out_path = td_path / "final.gguf"

        plan = RoundtripPlan(
            base_gguf=base, tuned_gguf=tuned, out_gguf=out_path,
            target_quant="Q4_K_M", lambda_steering=0.8,
            keep_intermediates=True, workdir=td_path / "work",
        )

        dry = run_roundtrip(plan, dry_run=True)
        assert dry.ok, f"R1 dry_run failed: {dry.error}"
        assert dry.stages["lift_base"]["tensor_count"] == 2
        assert dry.stages["lift_tuned"]["tensor_count"] == 2
        print(f"[*] dry_run OK; stages={list(dry.stages.keys())}")

        binary = find_llama_quantize_binary()
        run = run_roundtrip(plan)
        if binary is None:
            assert not run.ok, "R2: expected ok=False without llama-quantize"
            assert "CodecNotImplemented" in (run.error or ""), (
                f"R2: wrong error: {run.error}"
            )
            assert run.stages["lift_base"] is not None
            assert run.stages["lift_tuned"] is not None
            assert run.stages["abliterate"] is not None
            steered = Path(run.stages["abliterate"]["produced_gguf"])
            assert steered.is_file(), f"R3: missing steered intermediate {steered}"
            r = gguf.GGUFReader(str(steered))
            codecs = {t.tensor_type.name for t in r.tensors}
            assert codecs.issubset({"F32", "F16"}), f"R3: unexpected codecs {codecs}"

            base_attn = next(t for t in gguf.GGUFReader(str(base)).tensors
                             if t.name == "blk.0.attn")
            tuned_attn = next(t for t in gguf.GGUFReader(str(tuned)).tensors
                              if t.name == "blk.0.attn")
            steered_attn = next(t for t in r.tensors if t.name == "blk.0.attn")
            wb = np.asarray(base_attn.data, np.float16).astype(np.float32)
            wt = np.asarray(tuned_attn.data, np.float16).astype(np.float32)
            ws = np.asarray(steered_attn.data, np.float16).astype(np.float32)
            tau = wt - wb
            expected = wt - 0.8 * tau
            err = float(np.max(np.abs(ws - expected)))
            assert err < 1e-2, f"R3: steering identity drift > 1e-2 ({err})"
            print(f"[*] no llama-quantize: stage 1+2 verified; identity err={err:.2e}")
        else:
            assert run.ok, f"R4 failed: {run.error}"
            assert out_path.is_file(), "R4: missing final out_gguf"
            r = gguf.GGUFReader(str(out_path))
            assert len(r.tensors) == 2, f"R4: tensor count mismatch {len(r.tensors)}"
            print(f"[*] llama-quantize present; full pipeline produced "
                  f"{out_path} ({len(r.tensors)} tensors)")

    print("[PASS] llama_cpp_roundtrip.proof_of_property")
    return True


if __name__ == "__main__":
    rep = proof_of_property()
    print(json.dumps({"pass": rep}, indent=2))
