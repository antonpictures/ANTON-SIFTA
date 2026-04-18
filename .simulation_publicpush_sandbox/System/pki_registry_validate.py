#!/usr/bin/env python3
"""Validate .sifta_state/node_pki_registry.json shape (Ed25519 raw pubkeys as 64-char hex)."""
from __future__ import annotations

from typing import Any, List

_MAX_SERIAL_LEN = 128
_PUBKEY_HEX_LEN = 64  # 32-byte Ed25519 raw


def validate_node_pki_registry(obj: Any) -> List[str]:
    """Return a list of human-readable errors; empty list means OK."""
    errs: List[str] = []
    if not isinstance(obj, dict):
        return ["Registry must be a JSON object mapping serial -> hex public key."]
    if not obj:
        errs.append("Registry is empty — mesh verification will fail until nodes bootstrap.")
    for serial, pubkey in obj.items():
        if not isinstance(serial, str) or not serial.strip():
            errs.append(f"Invalid serial key (non-string or empty): {serial!r}")
            continue
        s = serial.strip()
        if len(s) > _MAX_SERIAL_LEN:
            errs.append(f"Serial too long ({len(s)} > {_MAX_SERIAL_LEN}): {s[:32]}…")
        if not isinstance(pubkey, str) or not pubkey.strip():
            errs.append(f"Missing pubkey for serial {s!r}")
            continue
        h = pubkey.strip()
        if len(h) != _PUBKEY_HEX_LEN:
            errs.append(
                f"Pubkey for {s!r} must be {_PUBKEY_HEX_LEN} hex chars (32-byte Ed25519 raw), got {len(h)}"
            )
        elif not all(c in "0123456789abcdefABCDEF" for c in h):
            errs.append(f"Pubkey for {s!r} contains non-hex characters")
    return errs
