#!/usr/bin/env python3
"""
System/sifta_nvidia_join.py — NVIDIA joins SIFTA as an optional organ.

This module does not install NVIDIA software and does not claim Isaac/GR00T
runtime access. It is a truth-labeled readiness probe that maps official
NVIDIA public assets to existing SIFTA integration hooks.

Truth contract:
  REAL        local package/cache is present and probeable on this node
  STUB        SIFTA has an interface, vendor runtime is not local
  ONLINE      official public asset exists; no local runtime/cache detected
  BLOCKED     requires explicit Architect GO, CUDA/Linux, or license review

Official anchors verified 2026-04-28:
  - https://developer.nvidia.com/isaac/gr00t
  - https://github.com/isaac-sim/IsaacLab
  - https://github.com/NVlabs/curobo
  - https://github.com/NVIDIA/warp
  - https://developer.nvidia.com/cosmos
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Callable, Iterable, Literal, Mapping

LocalTruth = Literal["REAL", "STUB", "ONLINE", "BLOCKED"]

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_STATE = _REPO / ".sifta_state"
DEFAULT_RECEIPT_PATH = _STATE / "nvidia_join_receipts.jsonl"


@dataclass(frozen=True)
class NvidiaAsset:
    key: str
    name: str
    asset_type: str
    official_url: str
    local_probe: str
    sifta_hook: str
    next_step: str
    risk_note: str


@dataclass(frozen=True)
class NvidiaProbe:
    key: str
    name: str
    asset_type: str
    local_truth: LocalTruth
    official_url: str
    local_probe: str
    local_detail: str
    sifta_hook: str
    next_step: str
    risk_note: str
    ts: float

    def as_dict(self) -> dict:
        row = asdict(self)
        row["schema"] = "SIFTA_NVIDIA_JOIN_PROBE_V1"
        return row


NVIDIA_ASSETS: tuple[NvidiaAsset, ...] = (
    NvidiaAsset(
        key="groot_n17_3b",
        name="GR00T N1.7 3B",
        asset_type="open model / policy family",
        official_url="https://huggingface.co/nvidia/GR00T-N1.7-3B",
        local_probe="hf_model_cache:nvidia/GR00T-N1.7-3B",
        sifta_hook="compare GR00T policy language against Event 74 field receipts",
        next_step="read model card and record architecture terms; no promotion without local cache",
        risk_note="model weights are not Alice; they are external evidence only",
    ),
    NvidiaAsset(
        key="groot_x_embodiment_sim",
        name="GR00T X Embodiment Sim",
        asset_type="robot trajectory dataset",
        official_url="https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim",
        local_probe="hf_dataset_cache:nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim",
        sifta_hook="benchmark ArmSegment paths against robot joint-state episodes",
        next_step="download only after Architect GO; use tiny fixture first",
        risk_note="large dataset; must stay read-only until a benchmark subset is defined",
    ),
    NvidiaAsset(
        key="isaac_lab",
        name="Isaac Lab",
        asset_type="robotics RL / simulation framework",
        official_url="https://github.com/isaac-sim/IsaacLab",
        local_probe="python_import:isaaclab|omni.isaac.core",
        sifta_hook="replace IsaacStigmergicStub with scene stepper when runtime exists",
        next_step="keep STUB on macOS unless Isaac runtime is installed in a supported environment",
        risk_note="vendor simulator; no physical actuator control without safety review",
    ),
    NvidiaAsset(
        key="curobo",
        name="cuRobo",
        asset_type="CUDA robot motion generation",
        official_url="https://github.com/NVlabs/curobo",
        local_probe="python_import:curobo",
        sifta_hook="compare collision-free trajectory optimizer against gradient-climber path",
        next_step="treat as CUDA/Linux optional; expose adapter only after import probe passes",
        risk_note="requires CUDA-class runtime; Apple Silicon should not pretend support",
    ),
    NvidiaAsset(
        key="warp",
        name="NVIDIA Warp",
        asset_type="CPU/CUDA Python simulation kernels",
        official_url="https://github.com/NVIDIA/warp",
        local_probe="python_import:warp",
        sifta_hook="optional acceleration for VoxelField potential fills",
        next_step="if installed, add backend selector: numpy first, warp optional",
        risk_note="acceleration layer only; must preserve numpy proof as canonical fallback",
    ),
    NvidiaAsset(
        key="cosmos",
        name="NVIDIA Cosmos",
        asset_type="world foundation / reasoning model platform",
        official_url="https://developer.nvidia.com/cosmos",
        local_probe="hf_model_cache:nvidia/Cosmos-Reason1-7B|hf_model_cache:nvidia/Cosmos-Predict2.5-2B",
        sifta_hook="feed Alice camera frame to Cosmos-Reason1-7B for physical-world Q&A; write receipt",
        next_step="First proof: download nvidia/Cosmos-Reason1-7B (ungated, CPU-runnable). "
                  "Do NOT start with Predict2.5-2B (gated, video-gen, GPU-heavy).",
        risk_note="Cosmos-Reason1 output is evidence, not sensor. "
                  "Predict2.5 synthetic video must never be labeled as real perception.",
    ),
)


def _hf_cache_path(repo_id: str, *, kind: str, cache_root: Path | None = None) -> Path:
    root = cache_root or Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    if root.name != "hub":
        root = root / "hub"
    prefix = "models" if kind == "model" else "datasets"
    return root / f"{prefix}--{repo_id.replace('/', '--')}"


def _has_import(module: str, import_checker: Callable[[str], bool] | None = None) -> bool:
    if import_checker is not None:
        return bool(import_checker(module))
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def _gecko_warp_probe(
    gecko_probe: Callable[[], Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Return AG31's Gecko/Warp truth row when available.

    The NVIDIA app keeps its own four public-facing states (REAL/STUB/ONLINE/BLOCKED),
    but Warp now has a finer local truth line: REAL_CPU vs REAL_GPU. That finer
    label belongs in the detail field so the app can prove Warp is running on this
    Mac without pretending Apple Silicon is CUDA.
    """
    if gecko_probe is not None:
        try:
            return dict(gecko_probe())
        except Exception as exc:
            return {"truth": "BROKEN", "error": f"{type(exc).__name__}: {exc}"}
    try:
        from System.swarm_gecko_adhesion import warp_truth_probe

        return dict(warp_truth_probe())
    except Exception:
        return None


def _probe_asset(
    asset: NvidiaAsset,
    *,
    cache_root: Path | None = None,
    import_checker: Callable[[str], bool] | None = None,
    platform_name: str | None = None,
    isaac_stub_available: bool = True,
    gecko_probe: Callable[[], Mapping[str, Any]] | None = None,
) -> NvidiaProbe:
    ts = time.time()
    system = platform_name or platform.system()
    truth: LocalTruth = "ONLINE"
    detail = "official source known; not detected locally"

    if asset.key == "groot_n17_3b":
        path = _hf_cache_path("nvidia/GR00T-N1.7-3B", kind="model", cache_root=cache_root)
        if path.exists():
            truth = "REAL"
            detail = f"local HF model cache: {path}"
        else:
            detail = f"missing local HF model cache: {path}"

    elif asset.key == "groot_x_embodiment_sim":
        path = _hf_cache_path(
            "nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim",
            kind="dataset",
            cache_root=cache_root,
        )
        if path.exists():
            truth = "REAL"
            detail = f"local HF dataset cache: {path}"
        else:
            detail = f"missing local HF dataset cache: {path}"

    elif asset.key == "isaac_lab":
        if _has_import("isaaclab", import_checker) or _has_import("omni.isaac.core", import_checker):
            truth = "REAL"
            detail = "Isaac runtime import is available"
        elif isaac_stub_available:
            truth = "STUB"
            detail = "SIFTA IsaacStigmergicStub present; vendor runtime missing"
        else:
            truth = "ONLINE"
            detail = "official repo known; no local import and no SIFTA stub"

    elif asset.key == "curobo":
        if _has_import("curobo", import_checker):
            truth = "REAL"
            detail = "curobo import is available"
        elif system == "Darwin":
            truth = "BLOCKED"
            detail = "cuRobo is CUDA-oriented; this node is macOS/Apple Silicon"
        else:
            detail = "curobo import missing"

    elif asset.key == "warp":
        probe = _gecko_warp_probe(gecko_probe)
        probe_truth = str(probe.get("truth", "")) if probe else ""
        if probe_truth in {"REAL_CPU", "REAL_GPU"}:
            truth = "REAL"
            version = probe.get("version") or "unknown"
            device = probe.get("device") or ("cuda" if probe.get("cuda_reported") else "cpu")
            detail = f"Gecko/Warp backend {probe_truth} on {device} (warp {version})"
        elif probe_truth == "BROKEN":
            truth = "BLOCKED"
            detail = f"Gecko/Warp probe failed: {probe.get('error') or 'unknown error'}"
        elif _has_import("warp", import_checker):
            truth = "REAL"
            detail = "warp import is available"
        else:
            detail = "warp import missing; keep numpy proof canonical"

    elif asset.key == "cosmos":
        # Dr. Codex audit 2026-04-28: split Reason1 (ungated, CPU) vs Predict2.5 (gated, GPU)
        reason1_path = _hf_cache_path("nvidia/Cosmos-Reason1-7B", kind="model", cache_root=cache_root)
        predict_path = _hf_cache_path("nvidia/Cosmos-Predict2.5-2B", kind="model", cache_root=cache_root)
        has_cosmos_pkg = _has_import("cosmos", import_checker) or _has_import("nvidia_cosmos", import_checker)
        if reason1_path.exists() or predict_path.exists() or has_cosmos_pkg:
            truth = "REAL"
            parts = []
            if reason1_path.exists(): parts.append("Reason1-7B cached")
            if predict_path.exists(): parts.append("Predict2.5-2B cached")
            if has_cosmos_pkg: parts.append("cosmos pkg")
            detail = f"Cosmos local: {', '.join(parts)}"
        else:
            truth = "ONLINE"
            detail = (
                "Cosmos-Reason1-7B available ungated at hf:nvidia/Cosmos-Reason1-7B (not downloaded). "
                "Cosmos-Predict2.5-2B gated (license required). No local runtime."
            )

    return NvidiaProbe(
        key=asset.key,
        name=asset.name,
        asset_type=asset.asset_type,
        local_truth=truth,
        official_url=asset.official_url,
        local_probe=asset.local_probe,
        local_detail=detail,
        sifta_hook=asset.sifta_hook,
        next_step=asset.next_step,
        risk_note=asset.risk_note,
        ts=ts,
    )


def probe_assets(
    *,
    cache_root: Path | None = None,
    import_checker: Callable[[str], bool] | None = None,
    platform_name: str | None = None,
    gecko_probe: Callable[[], Mapping[str, Any]] | None = None,
) -> list[NvidiaProbe]:
    try:
        from System.swarm_isaac_stigmergy_bridge import IsaacStigmergicStub

        isaac_stub_available = isinstance(IsaacStigmergicStub().truth, str)
    except Exception:
        isaac_stub_available = False

    return [
        _probe_asset(
            asset,
            cache_root=cache_root,
            import_checker=import_checker,
            platform_name=platform_name,
            isaac_stub_available=isaac_stub_available,
            gecko_probe=gecko_probe,
        )
        for asset in NVIDIA_ASSETS
    ]


def readiness_summary(probes: Iterable[NvidiaProbe]) -> dict[str, int]:
    counts = {"REAL": 0, "STUB": 0, "ONLINE": 0, "BLOCKED": 0}
    for probe in probes:
        counts[probe.local_truth] += 1
    return counts


def write_probe_receipt(
    probes: Iterable[NvidiaProbe],
    *,
    path: Path | str = DEFAULT_RECEIPT_PATH,
    writer: str = "sifta_nvidia_join",
) -> dict:
    rows = [probe.as_dict() for probe in probes]
    summary = readiness_summary(probes)
    receipt = {
        "schema": "SIFTA_NVIDIA_JOIN_RECEIPT_V1",
        "ts": time.time(),
        "writer": writer,
        "summary": summary,
        "assets": rows,
        "truth_note": "REAL means local package/cache exists; ONLINE is not runtime access.",
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")) + "\n")
    return receipt


def probe_and_write_receipt(
    *,
    path: Path | str = DEFAULT_RECEIPT_PATH,
    writer: str = "sifta_nvidia_join",
) -> dict:
    probes = probe_assets()
    return write_probe_receipt(probes, path=path, writer=writer)


def recommended_next_step(probes: Iterable[NvidiaProbe]) -> str:
    by_key = {probe.key: probe for probe in probes}
    if by_key.get("cosmos") and by_key["cosmos"].local_truth == "REAL":
        return "Cosmos-Reason1-7B is local — wire it to an Alice camera frame and write a receipt."
    if by_key.get("warp") and by_key["warp"].local_truth == "REAL":
        return (
            "Warp is REAL_CPU. Next: download nvidia/Cosmos-Reason1-7B (ungated) and "
            "feed an Alice frame for physical-world Q&A. That moves Cosmos ONLINE → REAL."
        )
    if by_key.get("isaac_lab") and by_key["isaac_lab"].local_truth == "REAL":
        return "Run IsaacStigmergicStub in a sandboxed sim-only scene."
    return "Keep NVIDIA lane as documented optional organs; next safe step: huggingface-cli download nvidia/Cosmos-Reason1-7B."


def _print_main() -> None:
    probes = probe_assets()
    receipt = write_probe_receipt(probes, writer="sifta_nvidia_join_cli")
    print("NVIDIA Joins SIFTA readiness:", receipt["summary"])
    print(recommended_next_step(probes))
    for probe in probes:
        print(f"{probe.local_truth:7s} {probe.name:30s} {probe.local_detail}")


if __name__ == "__main__":
    _print_main()


__all__ = [
    "DEFAULT_RECEIPT_PATH",
    "NVIDIA_ASSETS",
    "NvidiaAsset",
    "NvidiaProbe",
    "probe_assets",
    "probe_and_write_receipt",
    "readiness_summary",
    "recommended_next_step",
    "write_probe_receipt",
]
