#!/usr/bin/env python3
"""
NVIDIA Warp organ scanner — truth labels for SIFTA + first NVIDIA kernel path.

Scanner line progression (UI / receipts):
  STUB   — no `warp` module in this interpreter (install `warp-lang` from PyPI).
  ONLINE — `import warp` + `wp.init()` + `wp.__version__` succeeded; **kernel not yet probed**.
  REAL_CPU / REAL_GPU — one-element `@wp.kernel` smoke launch succeeded; GPU iff CUDA available.
  BROKEN — import/init or kernel raised.

Apple Silicon: Warp is often **REAL_CPU** (official CPU device); that is **green**, not second-class.

Research (gecko / adhesion / contact — cite in receipts, not lore):
  - Autumn, K. et al. (2000) Evidence for van der Waals adhesion in gecko setae.
    *Nature* **405**, 681–685. https://doi.org/10.1038/35073974
  - Autumn, K. et al. (2002) Evidence for self-cleaning in gecko setae.
    *PNAS* **99**, 12252–12256. https://doi.org/10.1073/pnas.252462899
  - Arzt, E., Gorb, S., Spolenak, R. (2003) From micro to nano contacts in biological attachment devices.
    *PNAS* **100**, 10603–10606. https://doi.org/10.1073/pnas.1534701100
  - Persson, B. N. J. (2001) Elastoplastic contact between randomly rough surfaces.
    *Physical Review Letters* **87**, 116101. https://doi.org/10.1103/PhysRevLett.87.116101
  - Israelachvili, J. N. (2011) *Intermolecular and Surface Forces*, 3rd ed. Academic Press.

Vendor:
  - NVIDIA Warp: https://developer.nvidia.com/warp-python
  - Devices / CUDA notes: https://nvidia.github.io/warp/user_guide/devices.html
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Optional

TRUTH_STUB: str = "STUB"
TRUTH_ONLINE: str = "ONLINE"
TRUTH_REAL_CPU: str = "REAL_CPU"
TRUTH_REAL_GPU: str = "REAL_GPU"
TRUTH_BROKEN: str = "BROKEN"


@dataclass(frozen=True)
class WarpScanResult:
    truth: str
    version: Optional[str]
    scanner_line: str
    cuda_reported: bool
    kernel_ok: bool
    error: Optional[str]


_CACHE: dict[bool, WarpScanResult] = {}


def _cuda_available(wp) -> bool:
    if hasattr(wp, "is_cuda_available"):
        try:
            return bool(wp.is_cuda_available())
        except Exception:
            pass
    try:
        return any("cuda" in str(d).lower() for d in wp.get_devices())
    except Exception:
        return False


def _kernel_smoke(wp, device) -> None:
    @wp.kernel
    def _smoke() -> None:
        pass

    wp.launch(_smoke, dim=1, device=device)
    wp.synchronize()


def probe_nvidia_warp(*, run_kernel: bool = True) -> WarpScanResult:
    """
    Probe Warp in this venv.

    ``run_kernel=False`` stops after import/init → **ONLINE** (fast path for asset scanners).
    ``run_kernel=True`` runs a 1-thread kernel → **REAL_CPU** or **REAL_GPU**, or **BROKEN**.
    """
    if importlib.util.find_spec("warp") is None:
        return WarpScanResult(
            truth=TRUTH_STUB,
            version=None,
            scanner_line="Warp: STUB",
            cuda_reported=False,
            kernel_ok=False,
            error=None,
        )
    try:
        import warp as wp

        wp.init()
        version = str(wp.__version__)
    except Exception as e:
        return WarpScanResult(
            truth=TRUTH_BROKEN,
            version=None,
            scanner_line="Warp: BROKEN",
            cuda_reported=False,
            kernel_ok=False,
            error=str(e)[:500],
        )

    if not run_kernel:
        return WarpScanResult(
            truth=TRUTH_ONLINE,
            version=version,
            scanner_line=f"Warp: ONLINE ({version})",
            cuda_reported=_cuda_available(wp),
            kernel_ok=False,
            error=None,
        )

    try:
        dev = wp.get_device()
        cuda = _cuda_available(wp)
        _kernel_smoke(wp, dev)
        truth = TRUTH_REAL_GPU if cuda else TRUTH_REAL_CPU
        tag = "REAL_GPU" if cuda else "REAL_CPU"
        return WarpScanResult(
            truth=truth,
            version=version,
            scanner_line=f"Warp: {tag} ({version})",
            cuda_reported=cuda,
            kernel_ok=True,
            error=None,
        )
    except Exception as e:
        return WarpScanResult(
            truth=TRUTH_BROKEN,
            version=version,
            scanner_line="Warp: BROKEN",
            cuda_reported=False,
            kernel_ok=False,
            error=str(e)[:500],
        )


def get_cached_warp_scan(*, run_kernel: bool = True, force_refresh: bool = False) -> WarpScanResult:
    """Cached probe per ``run_kernel`` flag — used by Gecko organ import."""
    global _CACHE
    if force_refresh or run_kernel not in _CACHE:
        _CACHE[run_kernel] = probe_nvidia_warp(run_kernel=run_kernel)
    return _CACHE[run_kernel]


def warp_truth_probe_dict() -> dict:
    """JSON-friendly row for Asset Scanner / ledgers."""
    r = get_cached_warp_scan(run_kernel=True)
    return {
        "truth": r.truth,
        "version": r.version,
        "scanner_line": r.scanner_line,
        "cuda_reported": r.cuda_reported,
        "kernel_ok": r.kernel_ok,
        "error": r.error,
    }


__all__ = [
    "TRUTH_STUB",
    "TRUTH_ONLINE",
    "TRUTH_REAL_CPU",
    "TRUTH_REAL_GPU",
    "TRUTH_BROKEN",
    "WarpScanResult",
    "probe_nvidia_warp",
    "get_cached_warp_scan",
    "warp_truth_probe_dict",
]
