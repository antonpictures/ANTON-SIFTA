"""STGM billing facade for consumer surfaces (``sifta_app``, py2app bundles).

Canonical numbers come from ``stgm_economy.scan_economy`` (repair_log wallet sum).
"""
from __future__ import annotations

from typing import Any


def scan_economy() -> Any:
    try:
        from System.stgm_economy import scan_economy as _scan
    except ImportError:
        from stgm_economy import scan_economy as _scan
    return _scan()


def balance() -> float:
    return float(scan_economy().canonical_wallet_sum)
