#!/usr/bin/env python3
"""
reviewer_registry.py — TUF-Adapted Reviewer Allowlist with Per-Role/Per-Step Thresholds
══════════════════════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Provides a stable, never-raises interface to the reviewer registry JSON that
governs the dual-sig audit gate in MutationGovernor.

Schema (.sifta_state/reviewer_registry.json):
    {
      "_schema": "SIFTA-reviewer-registry-v1",
      "roles": {
        "auditor":   {"threshold": 1, "pubkeys": ["<64-char-hex>", ...]},
        "architect": {"threshold": 1, "pubkeys": ["<64-char-hex>", ...]}
      },
      "steps": {
        "propose": {"authorized_roles": ["architect"], "threshold": 1},
        "review":  {"authorized_roles": ["auditor"],   "threshold": 1}
      },
      "revoked": ["<pubkey-hex-to-block>", ...]
    }

Architecture:
    The "steps" section maps to in-toto layout format (Torres-Arias et al.,
    USENIX Security 2019). Each step declares which roles can authorize it and
    how many signatures are required. This is closer to in-toto's actual schema
    than a flat role-only allowlist:

      in-toto layout step field:
        { "name": "review", "threshold": 1, "pubkeys": [keyid, ...] }
        → Threshold lives directly inside steps[], NOT in a signing subsection.
        (See in-toto/docs/spec/layout.md — verify this against the live spec.)

      SIFTA mapping:
        steps["propose"] ←→ proposer deposits PheromoneTrace
        steps["review"]  ←→ reviewer deposits ApprovalTrace
        threshold        ←→ minimum ApprovalTraces required
        authorized_roles ←→ which role's pubkeys may sign this step

    Threshold is enforced by MutationGovernor._check_dual_sig() which uses
    _dual_sig_quorum (default 1, bumped after ≥2 keys registered).

    TUF prior art: python-tuf fix-signature-threshold (duplicate-keyid
    Sybil attack). This registry's caller prevents duplicates via
    seen_reviewer_ids set in _check_dual_sig().

NOTE on pymdp package name (verified 2026-04-19):
    pip install pymdp ← installs a 2018 MDP stub (Minqi Jiang, v0.0.1).
    The active inference library is a different package:
    pip install inferactively-pymdp
    GitHub: https://github.com/infer-actively/pymdp
    Always use 'inferactively-pymdp' in requirements. The name collision is
    a confirmed pymdp packaging trap — flagged here so it doesn't silently
    install the wrong library.

Usage:
    # Simple: get auditor pubkeys, never raises
    keys = load_default_registry()   # Set[str]

    # Full object: for threshold-aware quorum
    reg = ReviewerRegistry()
    keys = reg.pubkeys_for_role("auditor")
    threshold = reg.threshold_for_role("auditor")
    step_threshold = reg.get_step_threshold("review")  # in-toto step analog

    # Wire into MutationGovernor
    gov = MutationGovernor(require_dual_sig=False)
    gov.set_reviewer_registry(reg)

TODOs:
    - Atomic write (write-then-rename) for _save()
    - Per-key revocation list in .sifta_state/revoked_keys.json
    - Persist add/remove operations with audit log

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Set

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_REGISTRY_PATH = _STATE_DIR / "reviewer_registry.json"


class ReviewerRegistry:
    """
    TUF-adapted allowlist. Never raises into callers — safe-degrades to empty.

    Revocation: any pubkey listed in the top-level "revoked" array is excluded
    from all role lookups, regardless of which role lists it. Same semantics
    as TUF's revoked-key pattern.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or _REGISTRY_PATH
        self._data: dict = {"roles": {}, "revoked": []}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text())
        except Exception:
            self._data = {"roles": {}, "revoked": []}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            out = {
                "_schema": "SIFTA-reviewer-registry-v1",
                "_cite": (
                    "TUF spec §4.3 — theupdateframework.github.io/specification/1.0.0. "
                    "Sybil fix: see python-tuf fix-signature-threshold commit."
                ),
                "_warn": "Never add the proposer's key as a reviewer for the same role.",
                "roles": self._data.get("roles", {}),
                "revoked": self._data.get("revoked", []),
            }
            self._path.write_text(json.dumps(out, indent=2))
        except Exception:
            pass

    def _revoked(self) -> Set[str]:
        return set(self._data.get("revoked", []))

    # ── Read API ──────────────────────────────────────────────────────────────

    def pubkeys_for_role(self, role: str = "auditor") -> Set[str]:
        """Active pubkeys for a role, minus revoked. Never raises."""
        try:
            revoked = self._revoked()
            keys = self._data.get("roles", {}).get(role, {}).get("pubkeys", [])
            return {k for k in keys if k not in revoked}
        except Exception:
            return set()

    def threshold_for_role(self, role: str = "auditor") -> int:
        """Minimum approvals required for this role. Defaults to 1."""
        try:
            return int(self._data.get("roles", {}).get(role, {}).get("threshold", 1))
        except Exception:
            return 1

    def all_pubkeys(self) -> Set[str]:
        """All registered pubkeys across all roles, minus revoked."""
        try:
            revoked = self._revoked()
            result: Set[str] = set()
            for role_data in self._data.get("roles", {}).values():
                result.update(role_data.get("pubkeys", []))
            return result - revoked
        except Exception:
            return set()

    def is_registered(self, pubkey_hex: str) -> bool:
        return pubkey_hex in self.all_pubkeys()

    def get_step_threshold(self, step: str = "review") -> int:
        """
        Return the required approval count for a named step.
        Analogous to in-toto layout steps[i].threshold.

        Steps declared in schema:
          "propose" — PheromoneTrace production step (proposer)
          "review"  — ApprovalTrace production step (reviewer)

        Falls back to the auditor role threshold if step not declared.
        Never raises.
        """
        try:
            step_threshold = self._data.get("steps", {}).get(step, {}).get("threshold")
            if step_threshold is not None:
                return int(step_threshold)
            return self.threshold_for_role("auditor")
        except Exception:
            return 1

    def get_step_authorized_roles(self, step: str = "review") -> list:
        """Return the roles authorized to sign a given step."""
        try:
            return self._data.get("steps", {}).get(step, {}).get("authorized_roles", ["auditor"])
        except Exception:
            return ["auditor"]

    def pubkeys_for_step(self, step: str = "review") -> "Set[str]":
        """Union of pubkeys for all roles authorized for a given step, minus revoked."""
        try:
            roles = self.get_step_authorized_roles(step)
            result: Set[str] = set()
            for role in roles:
                result.update(self.pubkeys_for_role(role))
            return result
        except Exception:
            return set()

    # ── Write API ─────────────────────────────────────────────────────────────

    def add_pubkey(self, role: str, pubkey_hex: str, *, threshold: int = 1) -> None:
        """Register a reviewer public key under a role."""
        roles = self._data.setdefault("roles", {})
        if role not in roles:
            roles[role] = {"threshold": threshold, "pubkeys": []}
        if pubkey_hex not in roles[role]["pubkeys"]:
            roles[role]["pubkeys"].append(pubkey_hex)
        self._save()

    def remove_pubkey(self, role: str, pubkey_hex: str) -> None:
        """Revoke a key from a specific role."""
        try:
            self._data["roles"][role]["pubkeys"] = [
                k for k in self._data["roles"][role]["pubkeys"] if k != pubkey_hex
            ]
            self._save()
        except Exception:
            pass

    def revoke_globally(self, pubkey_hex: str) -> None:
        """Block a key across all roles (compromise/rotation)."""
        revoked = self._data.setdefault("revoked", [])
        if pubkey_hex not in revoked:
            revoked.append(pubkey_hex)
        self._save()


# ── Convenience ───────────────────────────────────────────────────────────────

def load_default_registry() -> Set[str]:
    """
    Return the auditor pubkey set from the default registry path.
    Never raises — returns empty set if registry missing or malformed.
    Used by territory_swim_adapter and mutation_governor_loop at init time.
    """
    try:
        return ReviewerRegistry().pubkeys_for_role("auditor")
    except Exception:
        return set()


def get_default_registry() -> ReviewerRegistry:
    """
    Return the full ReviewerRegistry object (threshold-aware).
    Never raises — returns an empty registry if path missing.
    Use this when wiring MutationGovernor.set_reviewer_registry().
    """
    try:
        return ReviewerRegistry()
    except Exception:
        return ReviewerRegistry.__new__(ReviewerRegistry)
