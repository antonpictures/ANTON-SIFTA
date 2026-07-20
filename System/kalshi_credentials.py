#!/usr/bin/env python3
"""Load Kalshi API credentials from Keychain / local secrets.

George r1644: **PRODUCTION ONLY.** No demo Keychain service. No demo env for keys.

Owner material:
  - private key PEM → Keychain (prod) + .sifta_state/secrets/kalshi_private.pem
  - api key id → Keychain (prod) + secrets/kalshi_api_key_id.txt

Never print secrets into chat, logs, or receipts.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
SECRETS = STATE / "secrets"

# Production only — demo service name kept only for cleanup of old installs
PROD_SERVICE = "sifta.kalshi.prod"
LEGACY_DEMO_SERVICE = "sifta.kalshi.demo"
SERVICES = (PROD_SERVICE,)  # install/load: prod only


def _keychain_get(service: str, account: str) -> Optional[str]:
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return None
        return (out.stdout or "").strip() or None
    except Exception:
        return None


def _keychain_delete(service: str, account: str) -> None:
    if sys.platform != "darwin":
        return
    try:
        subprocess.run(
            ["security", "delete-generic-password", "-s", service, "-a", account],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def _keychain_set(service: str, account: str, value: str) -> None:
    if sys.platform != "darwin":
        return
    _keychain_delete(service, account)
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-s",
            service,
            "-a",
            account,
            "-w",
            value,
            "-U",
        ],
        capture_output=True,
        timeout=5,
    )


def purge_demo_keychain() -> dict:
    """Remove any legacy demo Keychain entries. Prod untouched."""
    accounts = ("private_key_pem_b64", "private_key_pem", "api_key_id")
    for acc in accounts:
        _keychain_delete(LEGACY_DEMO_SERVICE, acc)
    return {"purged_service": LEGACY_DEMO_SERVICE, "accounts": list(accounts)}


def load_private_key_pem() -> Optional[str]:
    # 1) Prod Keychain base64 (multiline-safe)
    b64 = _keychain_get(PROD_SERVICE, "private_key_pem_b64")
    if b64:
        try:
            raw = base64.b64decode(b64).decode("utf-8")
            if "BEGIN" in raw:
                return raw
        except Exception:
            pass
    pem = _keychain_get(PROD_SERVICE, "private_key_pem")
    if pem and "BEGIN" in pem:
        return pem
    # 2) Local secrets file mode 600
    p = SECRETS / "kalshi_private.pem"
    if p.exists():
        try:
            raw = p.read_text(encoding="utf-8")
            if "BEGIN" in raw:
                return raw
        except Exception:
            pass
    # 3) Env (CI only) — production key only; ignore demo env names
    env = os.environ.get("SIFTA_KALSHI_PRIVATE_KEY_PEM")
    if env and "BEGIN" in env:
        return env
    return None


def load_api_key_id() -> Optional[str]:
    kid = _keychain_get(PROD_SERVICE, "api_key_id")
    if kid:
        return kid.strip()
    p = SECRETS / "kalshi_api_key_id.txt"
    if p.exists():
        try:
            kid = p.read_text(encoding="utf-8").strip()
            if kid:
                return kid
        except Exception:
            pass
    # Production env only — do NOT fall back to DEMO_API_KEY_ID
    return os.environ.get("SIFTA_KALSHI_API_KEY_ID") or None


def credentials_status() -> dict:
    pem = load_private_key_pem()
    kid = load_api_key_id()
    return {
        "private_key": bool(pem),
        "api_key_id": bool(kid),
        "api_key_id_len": len(kid) if kid else 0,
        "ready": bool(pem and kid),
        "env": "prod",
        "note": (
            "ready (prod)"
            if (pem and kid)
            else (
                "have private key — still need API Key ID (Kalshi Profile → API Keys)"
                if pem and not kid
                else "missing private key"
                if kid
                else "missing both"
            )
        ),
    }


def install_private_key_pem(pem: str) -> None:
    """Install production private key only. Never demo."""
    pem = str(pem or "").strip() + "\n"
    if "BEGIN" not in pem or "PRIVATE KEY" not in pem:
        raise ValueError("not a private key PEM")
    SECRETS.mkdir(parents=True, exist_ok=True)
    SECRETS.chmod(0o700)
    p = SECRETS / "kalshi_private.pem"
    p.write_text(pem, encoding="utf-8")
    p.chmod(0o600)
    b64 = base64.b64encode(pem.encode("utf-8")).decode("ascii")
    _keychain_set(PROD_SERVICE, "private_key_pem_b64", b64)
    purge_demo_keychain()


def install_api_key_id(key_id: str) -> None:
    """Install API key id to prod Keychain + secrets. Never demo."""
    key_id = str(key_id or "").strip()
    if not key_id or len(key_id) < 8:
        raise ValueError("api_key_id too short")
    SECRETS.mkdir(parents=True, exist_ok=True)
    SECRETS.chmod(0o700)
    p = SECRETS / "kalshi_api_key_id.txt"
    p.write_text(key_id + "\n", encoding="utf-8")
    p.chmod(0o600)
    _keychain_set(PROD_SERVICE, "api_key_id", key_id)
    purge_demo_keychain()


__all__ = [
    "PROD_SERVICE",
    "load_private_key_pem",
    "load_api_key_id",
    "credentials_status",
    "install_api_key_id",
    "install_private_key_pem",
    "purge_demo_keychain",
]
