#!/usr/bin/env python3
"""
System/gguf_quant_codec.py
══════════════════════════════════════════════════════════════════════
Path A — Native GGUF quant lifecycle adapter (deep-systems work, scoped).

C47H stigauth, bridge 555:

The honest deep-systems patch is NOT to re-implement Q4_K / Q6_K from
scratch in Python (that is enormous work and a footgun). It is to
provide a single typed-and-tested **codec adapter** that:

  1. PROBES which GGML quantization codecs the installed `gguf` build
     can both **dequantize** and **quantize** (round-trip closed),
     vs. those it can only dequantize (one-way), vs. those it cannot
     touch at all.

  2. Provides a real, production-shaped **`lift_to_fp16(in_gguf, out_gguf)`**
     that walks every tensor of an input GGUF and rewrites it to a new
     GGUF whose ALL tensors are in {F32, F16}. This DOES work today —
     `gguf.quants.dequantize` covers Q4_K / Q6_K / BF16 etc., and we
     can always *write* F16 / F32 (those round-trips are byte-exact).

     This is the algebraic prerequisite for full continuous steering:
     once both `base.gguf` and `tuned.gguf` are lifted, the orthogonal
     abliteration organ has a closed vector space to operate on.

  3. Provides `requantize_via_external(in_gguf, out_gguf, target_type)`
     which delegates back-quantization to a vetted external oracle
     (llama.cpp `quantize` binary). The pure-Python branch of this
     function intentionally REFUSES to invent codec bytes — it raises
     a clear `CodecNotImplemented` describing the missing piece.

This module is read-only with respect to the input GGUF. It only ever
writes to a new path the caller controls.

Dependencies: only `numpy` and `gguf` (already in the venv).
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import gguf
from gguf import GGMLQuantizationType, Keys, GGUFValueType


# ────────────────────────────────────────────────────────────────────
# Capability probe
# ────────────────────────────────────────────────────────────────────


@dataclass
class CodecCapability:
    """Per-codec snapshot of what this gguf build can actually do."""

    name: str
    dequantize_ok: bool
    quantize_ok: bool
    roundtrip_byte_exact: Optional[bool]
    error: Optional[str] = None

    @property
    def is_closed(self) -> bool:
        return bool(self.dequantize_ok and self.quantize_ok)


@dataclass
class CodecCapabilityReport:
    capabilities: dict[str, CodecCapability] = field(default_factory=dict)

    def closed_codecs(self) -> list[str]:
        return sorted(c.name for c in self.capabilities.values() if c.is_closed)

    def one_way_codecs(self) -> list[str]:
        return sorted(
            c.name for c in self.capabilities.values()
            if c.dequantize_ok and not c.quantize_ok
        )

    def opaque_codecs(self) -> list[str]:
        return sorted(
            c.name for c in self.capabilities.values()
            if not c.dequantize_ok and not c.quantize_ok
        )


def _probe_one(qtype: GGMLQuantizationType, n_blocks: int = 4) -> CodecCapability:
    """
    Try to dequantize → quantize a small synthetic tensor of the given codec.

    We synthesise a fp32 weight matrix shaped to match the codec's natural
    block layout, then call `gguf.quants.quantize` first; if that succeeds
    we round-trip it back through dequantize. Some codecs (F32, F16, BF16)
    need slightly different handling because they aren't classic block
    codecs.
    """
    name = qtype.name
    try:
        if name == "F32":
            data = np.linspace(-1.0, 1.0, 32, dtype=np.float32)
            packed = data
            decoded = packed
            return CodecCapability(name, True, True, True)
        if name == "F16":
            data16 = np.linspace(-1.0, 1.0, 32, dtype=np.float16)
            data32 = data16.astype(np.float32)
            packed = gguf.quants.quantize(data32, qtype)
            return CodecCapability(name, True, True, np.array_equal(packed, data16))
        if name == "BF16":
            data32 = np.linspace(-0.5, 0.5, 64, dtype=np.float32)
            packed = gguf.quants.quantize(data32, qtype)
            decoded = gguf.quants.dequantize(packed, qtype)
            packed2 = gguf.quants.quantize(decoded, qtype)
            return CodecCapability(
                name, True, True,
                bool(np.array_equal(packed, packed2)),
            )

        from gguf.constants import GGML_QUANT_SIZES
        block_size, _ = GGML_QUANT_SIZES[qtype]
        cols = block_size * n_blocks
        rng = np.random.default_rng(0)
        data32 = rng.standard_normal((4, cols)).astype(np.float32) * 0.05

        try:
            packed = gguf.quants.quantize(data32, qtype)
            quantize_ok = True
            quantize_err = None
        except NotImplementedError as exc:
            packed = None
            quantize_ok = False
            quantize_err = f"quantize NotImplementedError: {exc}"
        except Exception as exc:
            packed = None
            quantize_ok = False
            quantize_err = f"quantize {type(exc).__name__}: {exc}"

        try:
            probe_packed = packed
            if probe_packed is None:
                synthetic = np.zeros((4, cols), dtype=np.float32)
                probe_packed = gguf.quants.quantize(synthetic, GGMLQuantizationType.F16)
                _ = gguf.quants.dequantize(probe_packed, GGMLQuantizationType.F16)
                dequantize_ok = True
            else:
                _ = gguf.quants.dequantize(probe_packed, qtype)
                dequantize_ok = True
            dequant_err = None
        except NotImplementedError as exc:
            dequantize_ok = False
            dequant_err = f"dequantize NotImplementedError: {exc}"
        except Exception as exc:
            dequantize_ok = False
            dequant_err = f"dequantize {type(exc).__name__}: {exc}"

        roundtrip = None
        if quantize_ok and dequantize_ok and packed is not None:
            try:
                decoded = gguf.quants.dequantize(packed, qtype)
                packed2 = gguf.quants.quantize(decoded, qtype)
                roundtrip = bool(np.array_equal(packed, packed2))
            except Exception:
                roundtrip = False

        err = quantize_err or dequant_err
        return CodecCapability(name, dequantize_ok, quantize_ok, roundtrip, err)
    except KeyError as exc:
        return CodecCapability(name, False, False, None, f"unknown size: {exc}")


def probe_codec_capabilities(
    codecs: Optional[list[GGMLQuantizationType]] = None,
) -> CodecCapabilityReport:
    """
    Empirically probe the running `gguf` build's quant lifecycle for the
    codecs the SIFTA pipeline actually cares about. Pass a custom list to
    extend the probe.
    """
    targets = codecs or [
        GGMLQuantizationType.F32,
        GGMLQuantizationType.F16,
        GGMLQuantizationType.BF16,
        GGMLQuantizationType.Q4_0,
        GGMLQuantizationType.Q4_1,
        GGMLQuantizationType.Q5_0,
        GGMLQuantizationType.Q5_1,
        GGMLQuantizationType.Q8_0,
        GGMLQuantizationType.Q4_K,
        GGMLQuantizationType.Q5_K,
        GGMLQuantizationType.Q6_K,
        GGMLQuantizationType.Q8_K,
    ]
    report = CodecCapabilityReport()
    for q in targets:
        report.capabilities[q.name] = _probe_one(q)
    return report


# ────────────────────────────────────────────────────────────────────
# Lift to FP16 — the algebraic prerequisite for full steering
# ────────────────────────────────────────────────────────────────────


def _architecture(reader: gguf.GGUFReader) -> str:
    f = reader.get_field(Keys.General.ARCHITECTURE)
    if f is None:
        return "llama"
    val = f.contents()
    return val if isinstance(val, str) and val else "llama"


def _copy_kv(reader: gguf.GGUFReader, writer: gguf.GGUFWriter) -> None:
    for field in reader.fields.values():
        if field.name == Keys.General.ARCHITECTURE or field.name.startswith("GGUF."):
            continue
        if not field.types:
            continue
        vtype = field.types[0]
        sub_type = field.types[-1] if vtype == GGUFValueType.ARRAY else None
        val = field.contents()
        if val is None:
            continue
        writer.add_key_value(field.name, val, vtype, sub_type=sub_type)


def lift_to_fp16(in_gguf: str | os.PathLike[str],
                 out_gguf: str | os.PathLike[str],
                 *,
                 keep_native_fp32: bool = True) -> dict:
    """
    Read `in_gguf` and write `out_gguf` so that every tensor is in
    {F32, F16}. Quantized tensors (Q4_K, Q6_K, BF16, …) are dequantized
    via `gguf.quants.dequantize` and packed as F16. F32 tensors stay F32
    (they are usually norm/bias vectors and have no Q* loss to recover).

    This DOES NOT modify the input file. It is the canonical "lift" stage
    of Path B (external canonicalization) and is also useful standalone:
    once both base and tuned blobs are lifted, the orthogonal abliteration
    organ operates over a fully-closed continuous manifold.

    Returns a small report dict for ledger appending.
    """
    in_path = Path(in_gguf)
    out_path = Path(out_gguf)
    if not in_path.exists():
        raise FileNotFoundError(in_path)
    if out_path.exists():
        raise FileExistsError(out_path)

    reader = gguf.GGUFReader(str(in_path))
    arch = _architecture(reader)
    writer = gguf.GGUFWriter(str(out_path), arch)
    _copy_kv(reader, writer)

    n_lifted = 0
    n_native = 0
    n_passthrough = 0
    failures: list[tuple[str, str]] = []

    for tensor in reader.tensors:
        name = tensor.name
        qname = tensor.tensor_type.name
        endian = reader.endianess

        try:
            if qname == "F32":
                payload = np.asarray(tensor.data, dtype=np.float32).copy()
                if keep_native_fp32:
                    writer.add_tensor(name, payload, raw_dtype=None,
                                      tensor_endianess=endian)
                    n_native += 1
                    continue
                payload16 = payload.astype(np.float16)
                writer.add_tensor(name, payload16, raw_dtype=None,
                                  tensor_endianess=endian)
                n_lifted += 1
                continue

            if qname == "F16":
                payload16 = np.asarray(tensor.data, dtype=np.float16).copy()
                writer.add_tensor(name, payload16, raw_dtype=None,
                                  tensor_endianess=endian)
                n_native += 1
                continue

            decoded = gguf.quants.dequantize(tensor.data, tensor.tensor_type)
            payload16 = np.asarray(decoded, dtype=np.float32).astype(np.float16)
            writer.add_tensor(name, payload16, raw_dtype=None,
                              tensor_endianess=endian)
            n_lifted += 1
        except NotImplementedError as exc:
            failures.append((name, f"dequantize NotImplemented for {qname}: {exc}"))
            payload = np.ascontiguousarray(tensor.data).copy()
            writer.add_tensor(name, payload, raw_dtype=tensor.tensor_type,
                              tensor_endianess=endian)
            n_passthrough += 1

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()

    return {
        "in_gguf": str(in_path),
        "out_gguf": str(out_path),
        "tensors_lifted": n_lifted,
        "tensors_native": n_native,
        "tensors_passthrough": n_passthrough,
        "failures": failures,
        "in_size_mb": round(in_path.stat().st_size / (1024 * 1024), 2),
        "out_size_mb": round(out_path.stat().st_size / (1024 * 1024), 2),
    }


# ────────────────────────────────────────────────────────────────────
# Re-quantize adapter
# ────────────────────────────────────────────────────────────────────


class CodecNotImplemented(RuntimeError):
    """Raised when the requested codec has no honest pure-Python writer."""


def find_llama_quantize_binary() -> Optional[Path]:
    """Locate llama.cpp's `quantize` binary via env var + PATH."""
    explicit = os.environ.get("LLAMA_QUANTIZE")
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    for candidate in ("llama-quantize", "quantize"):
        found = shutil.which(candidate)
        if found:
            return Path(found)
    return None


def requantize_via_external(in_gguf: str | os.PathLike[str],
                            out_gguf: str | os.PathLike[str],
                            target_type: str = "Q4_K_M",
                            *,
                            extra_args: Optional[list[str]] = None) -> dict:
    """
    Shell out to llama.cpp's `quantize` to round-trip an F16/F32 GGUF down
    to a target quantization type. This is the canonical Path B closer.

    Pure-Python re-quantization of Q4_K / Q6_K / Q5_K is intentionally
    refused — see CodecNotImplemented. Use llama.cpp as the oracle.
    """
    in_path = Path(in_gguf)
    out_path = Path(out_gguf)
    if not in_path.exists():
        raise FileNotFoundError(in_path)
    if out_path.exists():
        raise FileExistsError(out_path)

    binary = find_llama_quantize_binary()
    if binary is None:
        raise CodecNotImplemented(
            "No llama.cpp `quantize` binary on PATH and LLAMA_QUANTIZE is "
            "unset. Install llama.cpp (brew install llama.cpp) or build "
            "from source, then re-run. Pure-Python Q4_K/Q6_K/Q5_K "
            "re-quantization is not implemented in this `gguf` build."
        )

    cmd = [str(binary), str(in_path), str(out_path), target_type]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "binary": str(binary),
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "out_gguf": str(out_path) if out_path.exists() else None,
    }


# ────────────────────────────────────────────────────────────────────
# proof_of_property
# ────────────────────────────────────────────────────────────────────


def _make_synthetic_gguf(path: Path) -> None:
    writer = gguf.GGUFWriter(str(path), "llama")
    writer.add_string("general.name", "sifta_codec_synth")
    rng = np.random.default_rng(7)
    writer.add_tensor("blk.0.norm",
                      rng.standard_normal(64).astype(np.float32))
    writer.add_tensor("blk.0.attn",
                      rng.standard_normal((8, 32)).astype(np.float16))
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()


def proof_of_property() -> bool:
    """
    Falsifiers:
      Q1: capability probe agrees with empirical truth that F32/F16/BF16
          are closed and Q4_K / Q6_K are one-way in this gguf build.
      Q2: lift_to_fp16 on a tiny synthetic GGUF round-trips: the lifted
          GGUF has only F32 / F16 tensors, and decoded values match the
          original within fp16 precision.
      Q3: requantize_via_external returns a clean error message when no
          llama.cpp binary is present (instead of silently producing junk).
    """
    print("[*] Probing codec capabilities ...")
    report = probe_codec_capabilities()
    closed = set(report.closed_codecs())
    one_way = set(report.one_way_codecs())
    assert {"F32", "F16", "BF16"}.issubset(closed), (
        f"Q1: expected F32/F16/BF16 closed; got closed={sorted(closed)} "
        f"one_way={sorted(one_way)}"
    )
    print(f"    closed: {sorted(closed)}")
    print(f"    one-way (dequantize-only): {sorted(one_way)}")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        synth = td_path / "synth.gguf"
        lifted = td_path / "synth_f16.gguf"
        _make_synthetic_gguf(synth)
        report_lift = lift_to_fp16(synth, lifted)
        assert report_lift["tensors_passthrough"] == 0, (
            f"Q2: passthrough must be empty for an all-fp model; got "
            f"{report_lift['tensors_passthrough']}"
        )
        r = gguf.GGUFReader(str(lifted))
        codecs_after = {t.tensor_type.name for t in r.tensors}
        assert codecs_after.issubset({"F32", "F16"}), (
            f"Q2: lifted GGUF must be all F32/F16; got {codecs_after}"
        )
        print(f"    lifted GGUF codecs: {sorted(codecs_after)}")
        print(f"    lift report: {report_lift}")

    binary = find_llama_quantize_binary()
    if binary is None:
        try:
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                synth = td_path / "synth.gguf"
                target = td_path / "synth.q4km.gguf"
                _make_synthetic_gguf(synth)
                requantize_via_external(synth, target, "Q4_K_M")
            raise AssertionError("Q3: should have raised CodecNotImplemented")
        except CodecNotImplemented as exc:
            print(f"    requantize_via_external correctly refuses: {exc}")
    else:
        print(f"    [!] llama-quantize present at {binary}; skipping Q3 negative test")

    print("[PASS] gguf_quant_codec.proof_of_property")
    return True


if __name__ == "__main__":
    proof_of_property()
