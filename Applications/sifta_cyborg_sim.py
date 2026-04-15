#!/usr/bin/env python3
"""
sifta_cyborg_sim.py — Cyborg Organ Simulation (Swimmers + Immune System)
=======================================================================

A simulation app that models a "cyborg" as a set of organs controlled by
cryptographically signed ASCII swimmers.

Design goals:
- Each swimmer carries an ASCII body + an Ed25519 signature (owner-bound).
- An "immune system" verifies signatures and compatibility before organs apply settings.
- Accepted actions produce small, auditable rewards in a *simulation ledger* JSONL.

Usage:
  python3 Applications/sifta_cyborg_sim.py --demo
  python3 Applications/sifta_cyborg_sim.py --ticks 200 --out .sifta/cyborg/cyborg_ledger.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519


REPO_ROOT = Path(__file__).resolve().parent.parent
SYS_DIR = REPO_ROOT / "System"


def _now() -> int:
    return int(time.time())


def _canon_payload(swimmer_id: str, owner_id: str, organ: str, action: str, params: Dict[str, Any], ts: int) -> str:
    # Stable, explicit canonicalization: JSON params sorted with compact separators.
    blob = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"SWIMMER::{swimmer_id}::OWNER[{owner_id}]::ORGAN[{organ}]::ACTION[{action}]::TS[{ts}]::PARAMS[{blob}]"


def _hex_pubkey(pub: ed25519.Ed25519PublicKey) -> str:
    return pub.public_bytes_raw().hex()


def _hex_sig(sig: bytes) -> str:
    return sig.hex()


def _ascii_swimmer(swimmer_id: str, owner_id: str, organ: str) -> str:
    return f"<///[S_W]///::ID[{swimmer_id}]::OWNER[{owner_id}]::ORGAN[{organ}]>"


@dataclass(frozen=True)
class SwimmerToken:
    swimmer_id: str
    owner_id: str
    organ: str
    action: str
    params: Dict[str, Any]
    ts: int
    ascii: str
    owner_pubkey_hex: str
    sig_hex: str

    def payload(self) -> str:
        return _canon_payload(self.swimmer_id, self.owner_id, self.organ, self.action, self.params, self.ts)


class OwnerKeyring:
    """Simulation-only keyring: generates per-owner Ed25519 keys in memory."""

    def __init__(self) -> None:
        self._priv: Dict[str, ed25519.Ed25519PrivateKey] = {}

    def ensure(self, owner_id: str) -> ed25519.Ed25519PrivateKey:
        if owner_id not in self._priv:
            self._priv[owner_id] = ed25519.Ed25519PrivateKey.generate()
        return self._priv[owner_id]

    def pubkey_hex(self, owner_id: str) -> str:
        priv = self.ensure(owner_id)
        return _hex_pubkey(priv.public_key())

    def sign(self, owner_id: str, payload: str) -> str:
        priv = self.ensure(owner_id)
        return _hex_sig(priv.sign(payload.encode("utf-8")))


class SimulationLedger:
    """Append-only JSONL ledger for simulation economics (NOT the real repair_log)."""

    def __init__(self, out_path: Path) -> None:
        self.path = out_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Import locked append from System at runtime, without requiring package installs.
        import sys

        if str(SYS_DIR) not in sys.path:
            sys.path.insert(0, str(SYS_DIR))
        from ledger_append import append_jsonl_line  # type: ignore

        self._append = append_jsonl_line

    def append(self, row: Dict[str, Any]) -> None:
        self._append(self.path, row)


class Organ:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.settings: Dict[str, Any] = {}

    def allowed_actions(self) -> Dict[str, Tuple[str, ...]]:
        """action -> tuple of allowed param keys"""
        raise NotImplementedError

    def apply(self, token: SwimmerToken) -> Dict[str, Any]:
        allow = self.allowed_actions().get(token.action)
        if not allow:
            raise ValueError(f"Organ {self.name} rejects action {token.action}")
        for k in token.params.keys():
            if k not in allow:
                raise ValueError(f"Organ {self.name} rejects param '{k}' for action {token.action}")
        # Apply settings (simple merge)
        self.settings.update(token.params)
        return {"ok": True, "organ": self.name, "applied": dict(token.params)}


class Pacemaker(Organ):
    def __init__(self) -> None:
        super().__init__("pacemaker")
        self.settings = {"bpm_target": 70, "pacing_mode": "DDD"}

    def allowed_actions(self) -> Dict[str, Tuple[str, ...]]:
        return {"set": ("bpm_target", "pacing_mode")}


class CochlearImplant(Organ):
    def __init__(self) -> None:
        super().__init__("cochlear")
        self.settings = {"gain_db": 10, "noise_gate": True}

    def allowed_actions(self) -> Dict[str, Tuple[str, ...]]:
        return {"set": ("gain_db", "noise_gate")}


class NfcChip(Organ):
    def __init__(self) -> None:
        super().__init__("nfc")
        self.settings = {"access_level": "LOW", "enabled": True}

    def allowed_actions(self) -> Dict[str, Tuple[str, ...]]:
        return {"set": ("access_level", "enabled")}


class ImmuneSystem:
    """Verification membrane: rejects unsigned/invalid/foreign swimmers."""

    def __init__(self, organ_map: Dict[str, Organ]) -> None:
        self.organs = organ_map
        # allowlist owner -> pubkey hex (owners are the cryptographic identity)
        self.owner_registry: Dict[str, str] = {}

    def register_owner(self, owner_id: str, pubkey_hex: str) -> None:
        self.owner_registry[owner_id] = pubkey_hex.lower()

    def verify(self, token: SwimmerToken) -> None:
        if token.organ not in self.organs:
            raise ValueError(f"Unknown organ '{token.organ}'")
        reg = self.owner_registry.get(token.owner_id)
        if not reg:
            raise ValueError(f"Unregistered owner '{token.owner_id}'")
        if reg != token.owner_pubkey_hex.lower():
            raise ValueError("Owner pubkey mismatch vs registry")

        pub_bytes = bytes.fromhex(token.owner_pubkey_hex)
        sig_bytes = bytes.fromhex(token.sig_hex)
        pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        try:
            pub.verify(sig_bytes, token.payload().encode("utf-8"))
        except InvalidSignature as e:
            raise ValueError("Invalid swimmer signature") from e

        # Freshness check (simple anti-replay in sim)
        if abs(_now() - int(token.ts)) > 3600:
            raise ValueError("Token timestamp outside freshness window")

    def route(self, token: SwimmerToken) -> Dict[str, Any]:
        self.verify(token)
        organ = self.organs[token.organ]
        return organ.apply(token)


class Cyborg:
    def __init__(self, ledger: SimulationLedger) -> None:
        self.ledger = ledger
        self.organs: Dict[str, Organ] = {
            "pacemaker": Pacemaker(),
            "cochlear": CochlearImplant(),
            "nfc": NfcChip(),
        }
        self.immune = ImmuneSystem(self.organs)

    def submit(self, token: SwimmerToken) -> Dict[str, Any]:
        out = self.immune.route(token)
        # Reward owner for providing a valid, compatible configuration update.
        self.ledger.append(
            {
                "event": "UTILITY_MINT",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "miner_id": token.owner_id,
                "amount_stgm": 0.1,
                "reason": f"CYBORG_ORGAN_TUNE::{token.organ}::{token.action}",
                "swimmer_id": token.swimmer_id,
                "ascii": token.ascii,
            }
        )
        return out


def mint_swimmer_token(
    keyring: OwnerKeyring,
    swimmer_id: str,
    owner_id: str,
    organ: str,
    action: str,
    params: Dict[str, Any],
    ts: Optional[int] = None,
) -> SwimmerToken:
    ts_i = int(ts if ts is not None else _now())
    ascii = _ascii_swimmer(swimmer_id, owner_id, organ)
    pub_hex = keyring.pubkey_hex(owner_id)
    payload = _canon_payload(swimmer_id, owner_id, organ, action, params, ts_i)
    sig_hex = keyring.sign(owner_id, payload)
    return SwimmerToken(
        swimmer_id=swimmer_id,
        owner_id=owner_id,
        organ=organ,
        action=action,
        params=dict(params),
        ts=ts_i,
        ascii=ascii,
        owner_pubkey_hex=pub_hex,
        sig_hex=sig_hex,
    )


def show_cyborg_lab(cy: Cyborg, ok: int, rej: int) -> None:
    import sys

    if str(SYS_DIR) not in sys.path:
        sys.path.insert(0, str(SYS_DIR))
    import matplotlib.pyplot as plt
    from sim_lab_theme import LAB_BAD, LAB_CYAN, LAB_OK, apply_matplotlib_lab_style, neon_suptitle, style_axis_lab

    apply_matplotlib_lab_style()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    neon_suptitle(fig, "CYBORG ORGAN LAB", f"accepted={ok}  rejected={rej}  (immune + Ed25519)")
    pm = cy.organs["pacemaker"].settings
    co = cy.organs["cochlear"].settings
    nf = cy.organs["nfc"].settings
    axes[0].barh(["bpm"], [float(pm.get("bpm_target", 0))], color=LAB_BAD, height=0.45)
    style_axis_lab(axes[0], "Pacemaker")
    axes[1].barh(["gain_dB"], [float(co.get("gain_db", 0))], color=LAB_CYAN, height=0.45)
    style_axis_lab(axes[1], "Cochlear")
    axes[2].barh(["access"], [1.0 if str(nf.get("access_level", "")).upper() == "HIGH" else 0.3], color=LAB_OK, height=0.45)
    style_axis_lab(axes[2], "NFC gate")
    axes[0].set_xlim(40, 130)
    axes[1].set_xlim(0, 24)
    axes[2].set_xlim(0, 1.2)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    plt.show()


def run_demo(ticks: int, out_path: Path) -> tuple[int, int, int, Cyborg]:
    ledger = SimulationLedger(out_path)
    cy = Cyborg(ledger)
    keyring = OwnerKeyring()

    # Register owners (the "immune system" only trusts registered keys)
    cy.immune.register_owner("ARCHITECT_M5", keyring.pubkey_hex("ARCHITECT_M5"))
    cy.immune.register_owner("ARCHITECT_M1", keyring.pubkey_hex("ARCHITECT_M1"))

    # Two swimmers, two owners, tuning different organs.
    swimmers = [
        ("SWIMMER_HEART_01", "ARCHITECT_M5", "pacemaker"),
        ("SWIMMER_EAR_01", "ARCHITECT_M1", "cochlear"),
        ("SWIMMER_NFC_01", "ARCHITECT_M5", "nfc"),
    ]

    ok = 0
    rej = 0
    for i in range(ticks):
        sid, oid, organ = swimmers[i % len(swimmers)]
        if organ == "pacemaker":
            params = {"bpm_target": 60 + (i % 40)}
        elif organ == "cochlear":
            params = {"gain_db": 8 + (i % 6), "noise_gate": bool(i % 2)}
        else:
            params = {"access_level": "HIGH" if (i % 10 == 0) else "LOW"}
        tok = mint_swimmer_token(keyring, sid, oid, organ, "set", params)
        try:
            cy.submit(tok)
            ok += 1
        except Exception:
            rej += 1

    # One intentional invalid signature injection (should be rejected)
    bad = mint_swimmer_token(keyring, "EVIL_SWIMMER", "ARCHITECT_M5", "pacemaker", "set", {"bpm_target": 999})
    bad2 = SwimmerToken(**{**bad.__dict__, "sig_hex": "00" * 64})  # type: ignore[arg-type]
    try:
        cy.submit(bad2)
    except Exception:
        rej += 1

    print(f"[CYBORG] ticks={ticks} ok={ok} rejected={rej} ledger={out_path}")
    print(f"[CYBORG] pacemaker={cy.organs['pacemaker'].settings}")
    print(f"[CYBORG] cochlear={cy.organs['cochlear'].settings}")
    print(f"[CYBORG] nfc={cy.organs['nfc'].settings}")
    return 0, ok, rej, cy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="Run a deterministic demo workload.")
    ap.add_argument("--ticks", type=int, default=50, help="Number of control ticks.")
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / ".sifta" / "cyborg" / "cyborg_ledger.jsonl"))
    ap.add_argument("--visual", action="store_true", help="Open matplotlib organ dashboard after demo.")
    args = ap.parse_args()

    out = Path(args.out).expanduser()
    rc, ok, rej, cy = run_demo(args.ticks, out)
    if args.visual:
        show_cyborg_lab(cy, ok, rej)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

