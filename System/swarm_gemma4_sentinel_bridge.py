#!/usr/bin/env python3
"""
System/swarm_gemma4_sentinel_bridge.py
══════════════════════════════════════════════════════════════════════
Concept: Vector-space sentinels inside Gemma4 GGUF weights (dequantized fp32)
Author:  Cursor Auto (bridge) — hardens AG31 byte-scan with real manifold probes
Status:  Active bridge organ (NOT raw-byte entropy)

Resolves ~/.ollama/models/blobs for architecture == gemma4, dequantizes
Q4_K / Q6_K / F32 blocks, then runs:
  • Rayleigh sentinels — random Gaussian directions, projection variance
  • Spectral sentinels — truncated SVD on a corner block, Shannon entropy
    of normalized singular values + effective rank (exp(entropy))

Run:  python3 System/swarm_gemma4_sentinel_bridge.py
       python3 System/swarm_gemma4_sentinel_bridge.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import gguf
    from gguf import quants
except ImportError as e:  # pragma: no cover
    print("[-] pip install gguf", file=sys.stderr)
    raise e


def _blob_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS", Path.home() / ".ollama/models")).expanduser() / "blobs"


def find_gemma4_gguf() -> Optional[Path]:
    """Pick the largest GGUF whose general.architecture decodes to gemma4."""
    d = _blob_dir()
    if not d.is_dir():
        return None
    candidates: List[Tuple[int, Path]] = []
    for p in d.glob("sha256-*"):
        try:
            if p.stat().st_size < 500_000_000:
                continue
        except OSError:
            continue
        try:
            r = gguf.GGUFReader(str(p))
        except Exception:
            continue
        arch = ""
        for fld in r.fields.values():
            if fld.name == "general.architecture":
                arch = bytes(fld.parts[-1]).decode("utf-8", errors="ignore").strip().lower()
                break
        if arch == "gemma4":
            candidates.append((p.stat().st_size, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def tensor_to_fp32_matrix(tensor: Any) -> np.ndarray:
    """Return 2-D float32 weights (rows, cols). 1-D tensors become (N, 1)."""
    shape = tuple(int(x) for x in tensor.shape)
    name = tensor.tensor_type.name
    if name == "F32":
        arr = np.frombuffer(tensor.data, dtype=np.float32).copy()
        arr = arr.reshape(shape)
    else:
        arr = np.asarray(quants.dequantize(tensor.data, tensor.tensor_type), dtype=np.float32)
        if arr.ndim != len(shape):
            arr = arr.reshape(shape)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"expected 1D/2D after reshape, got {arr.shape} for {tensor.name}")
    return arr


def spectral_sentinel(W: np.ndarray, block: int = 256, topk: int = 128) -> Dict[str, float]:
    """Shannon entropy (bits) of normalized singular values on a leading corner (fast)."""
    m, n = W.shape
    b = min(block, m, n)
    if b < 8:
        return {
            "spectral_entropy_bits": float("nan"),
            "effective_rank_nat": float("nan"),
            "smax_over_smin": float("nan"),
            "block": float(b),
        }
    sub = W[:b, :b].astype(np.float64, copy=False)
    s = np.linalg.svd(sub, compute_uv=False, full_matrices=False)
    s = s[: min(topk, s.size)]
    s = np.maximum(s, 0.0)
    if s.sum() <= 0:
        return {
            "spectral_entropy_bits": float("nan"),
            "effective_rank_nat": float("nan"),
            "smax_over_smin": float("nan"),
            "block": float(b),
        }
    p = s / s.sum()
    p = p[p > 1e-15]
    H_bits = float(-np.sum(p * np.log2(p)))
    H_nat = float(-np.sum(p * np.log(p)))
    eff_rank = float(np.exp(H_nat))
    smax_ratio = float(s[0] / s[-1]) if s[-1] > 1e-12 else float("inf")
    return {
        "spectral_entropy_bits": H_bits,
        "effective_rank_nat": eff_rank,
        "smax_over_smin": smax_ratio,
        "block": float(b),
    }


def rayleigh_sentinels(W: np.ndarray, n_draws: int = 48, rng: Optional[np.random.Generator] = None) -> Dict[str, float]:
    """Project W onto random directions in the smaller ambient dimension."""
    rng = rng or np.random.default_rng(0)
    m, n = W.shape
    if m == 0 or n == 0:
        return {"rayleigh_var": 0.0, "rayleigh_mean_abs": 0.0}
    # y = W @ g  with g ~ N(0,1) in R^n — captures column mixing
    g = rng.standard_normal((n, n_draws)).astype(np.float64)
    y = (W.astype(np.float64) @ g) / np.sqrt(n)
    v = float(np.var(y))
    ma = float(np.mean(np.abs(y)))
    return {"rayleigh_var": v, "rayleigh_mean_abs": ma}


def scan_gemma4_sentinels(
    gguf_path: Optional[Path] = None,
    max_tensors: int = 12,
    seed: int = 0,
) -> Dict[str, Any]:
    path = gguf_path or find_gemma4_gguf()
    if path is None:
        return {"ok": False, "error": "no gemma4 GGUF found under OLLAMA_MODELS blobs"}

    reader = gguf.GGUFReader(str(path))
    rng = np.random.default_rng(seed)
    needles = ("blk.0.", "blk.8.", "blk.16.", "blk.24.")
    rows: List[Dict[str, Any]] = []

    for tensor in reader.tensors:
        if "weight" not in tensor.name:
            continue
        if not any(ns in tensor.name for ns in needles):
            continue
        if tensor.tensor_type.name not in ("F32", "Q4_K", "Q6_K", "Q4_0", "Q8_0"):
            continue
        try:
            W = tensor_to_fp32_matrix(tensor)
        except Exception as ex:
            rows.append({"tensor": tensor.name, "error": str(ex)})
            continue
        spec = spectral_sentinel(W, block=256, topk=128)
        ray = rayleigh_sentinels(W, n_draws=48, rng=rng)
        rows.append(
            {
                "tensor": tensor.name,
                "qtype": tensor.tensor_type.name,
                "shape": [int(x) for x in tensor.shape],
                "fp32_mean": float(np.mean(W)),
                "fp32_std": float(np.std(W)),
                **spec,
                **ray,
            }
        )
        if len(rows) >= max_tensors:
            break

    return {
        "ok": True,
        "path": str(path),
        "tensor_count": len(reader.tensors),
        "sentinel_rows": rows,
    }


def proof_of_property() -> bool:
    """
    Numerical gate: dequantized fp32 has sane scale; spectral entropy nontrivial;
    Rayleigh projection variance strictly positive on a real Gemma4 block.
    """
    rep = scan_gemma4_sentinels(max_tensors=6, seed=42)
    assert rep.get("ok"), rep.get("error", "mount failed")

    usable = [r for r in rep["sentinel_rows"] if "fp32_std" in r and "error" not in r]
    assert usable, "[FAIL] no tensors dequantized"

    r0 = usable[0]
    assert r0["fp32_std"] > 1e-4, "[FAIL] fp32_std collapsed — dequant bug?"
    assert r0["rayleigh_var"] > 0.0, "[FAIL] Rayleigh variance zero — frozen weights?"

    spectral_ok = [r for r in usable if np.isfinite(r.get("spectral_entropy_bits", float("nan")))]
    assert spectral_ok, "[FAIL] no matrix large enough for corner SVD"
    r1 = max(spectral_ok, key=lambda x: x["spectral_entropy_bits"])
    assert r1["spectral_entropy_bits"] > 0.5, "[FAIL] spectral entropy degenerate on largest block"

    # Corner SVD on random matrix control: entropy upper bounded by rank
    rng = np.random.default_rng(7)
    R = rng.standard_normal((128, 128)).astype(np.float64)
    s = spectral_sentinel(R.astype(np.float32), block=128, topk=128)
    assert s["spectral_entropy_bits"] < 7.5, "[FAIL] control SVD entropy sanity"

    print("[PASS] swarm_gemma4_sentinel_bridge.proof_of_property")
    return True


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):  # NaN / inf
            return None
    return obj


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemma4 fp32 sentinel bridge")
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    ap.add_argument("--path", type=str, default="", help="explicit GGUF path")
    args = ap.parse_args()
    p = Path(args.path) if args.path else None
    rep = scan_gemma4_sentinels(gguf_path=p, max_tensors=16, seed=0)
    if args.json:
        print(json.dumps(_json_safe(rep), indent=2))
        return
    print("\n=== GEMMA4 SENTINEL BRIDGE (fp32 / dequant) ===")
    if not rep.get("ok"):
        print("[-]", rep.get("error"))
        sys.exit(1)
    print(f"[*] Mounted: {rep['path']}")
    print(f"[*] Tensors in file: {rep['tensor_count']}")
    for r in rep["sentinel_rows"]:
        if "error" in r:
            print(f"  [!] {r['tensor']}: {r['error']}")
            continue
        h = r["spectral_entropy_bits"]
        er = r["effective_rank_nat"]
        hs = f"{h:.3f}" if np.isfinite(h) else "n/a"
        ers = f"{er:.2f}" if np.isfinite(er) else "n/a"
        print(
            f"  {r['tensor']:<42} {r['qtype']:<6} "
            f"H_svd={hs} "
            f"eff_rank={ers} "
            f"std={r['fp32_std']:.5f} "
            f"ray_var={r['rayleigh_var']:.6f}"
        )
    print("\n[+] Sentinel ingress complete (vector manifold, not byte codec).")


if __name__ == "__main__":
    main()
