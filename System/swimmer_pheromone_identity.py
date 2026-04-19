#!/usr/bin/env python3
"""
swimmer_pheromone_identity.py — Cryptographic Swimmer Identity + Signed Pheromone Traces
══════════════════════════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite                              v2026-04-18.v3

ARCHITECTURAL PRIOR ART
────────────────────────
This module implements SIFTA's mutation audit gate. The architecture maps
directly onto two published systems — read them before extending this code.

  in-toto (Torres-Arias et al., USENIX Security 2019)
    "in-toto: Providing farm-to-table guarantees for bits and bytes"
    https://www.usenix.org/system/files/sec19-torres-arias.pdf
    The SIFTA mapping:
      in-toto layout          → reviewer_registry.json  (who can approve what)
      in-toto link metadata   → PheromoneTrace (proposal) + ApprovalTrace (review)
      in-toto verifier        → MutationGovernor.allow() / verify_approval()
      in-toto functionaries   → SwimmerIdentity with reviewer keys in registry
    in-toto was validated against 30 real-world supply-chain compromises.
    We inherit their threat model for free. Don't invent a fourth system.

  TUF — The Update Framework (theupdateframework.github.io/specification/1.0.0)
    Threshold-signature model: "role requires N-of-M signatures from key set."
    ReviewerRegistry borrows the {role: {threshold, pubkeys}} schema directly.
    Critical prior art: the python-tuf "fix-signature-threshold" commit patched
    a duplicate-keyid Sybil attack where the same key counted multiple times
    toward the threshold. Our _check_approver_ids() set prevents this.

  Brendel, Cremers, Jackson, Zhao — "The Provable Security of Ed25519" (IEEE S&P 2021)
    https://eprint.iacr.org/2020/823
    Ed25519 achieves SUF-CMA (strong unforgeability: no alternative valid
    signatures for already-signed messages) only when verifiers enforce s < L.
    Without the check: EUF-CMA only — an attacker can produce a different
    valid signature for the *same* message, breaking any system using
    signature_hex as an idempotency or binding key (which we do).
    cryptography.hazmat wraps OpenSSL EVP_PKEY Ed25519, which implements
    RFC 8032 §5.1.7 strict verification (s < L enforced).
    Regression test: test_malleability_rejection() in the smoke suite below.
    Pin this behavior — a future library swap must not silently regress it.

WHY THIS EXISTS
───────────────
Software stigmergy has no physics — any process can forge a pheromone
deposit. Cryptographic signatures make provenance trustless: ANY node can
verify "swimmer X deposited THIS trace at path Y at time T" without
contacting swimmer X, without a central authority, and without trusting
the storage layer.

DUAL-SIG GATE
─────────────
Proposal:   SwimmerIdentity.deposit()  → PheromoneTrace   (proposer signs)
Approval:   SwimmerIdentity.approve()  → ApprovalTrace    (reviewer counter-signs)

verify_approval() enforces seven invariants (in-toto link validation analog):
  1. proposal verifies independently via verify_trace()
  2. approval.approves_signature_hex == proposal.signature_hex  (binding)
  3. approver in reviewer_registry or reviewer_allowlist         (Sybil resistance)
  4. approver_id ≠ proposer_id                                  (no self-approval)
  5. 0 ≤ approval.ts - proposal.ts ≤ APPROVAL_TTL              (freshness)
  6. approval.ts ≤ now + CLOCK_SKEW                             (no forward-dating)
  7. approval signature verifies                                 (second Ed25519 verify)

ATTACK SURFACE MAP (C47H audit 2026-04-18)
───────────────────────────────────────────
C47H identified three attack surfaces on the "approver signs proposer's
Ed25519 signature bytes" pattern. Each is addressed here:

  Attack 1 — Message canonicalization bugs:
    If the proposal content is not canonicalized before signing, an attacker
    may craft multiple messages that produce different signatures but bind to
    the same logical content, breaking the approval gate's idempotency.
    Mitigation: _trace_message() and _approval_message() use json.dumps(
    sort_keys=True, separators=(',', ':')) — deterministic, no whitespace
    variation. Raw signing (not pre-hash) per RFC 8032 — the SUF-CMA
    guarantee of Ed25519 applies to the raw byte string directly.
    Every field is explicitly named in the JSON; no implicit ordering.

  Attack 2 — Cross-protocol / signature-replay:
    A valid (proposal, approval) pair from one SIFTA deployment could be
    replayed against another if the signed message contains no deployment-
    specific binding. Classic context-separation failure.
    Mitigation: DOMAIN_TRACE / DOMAIN_APPROVAL constants are injected as
    "_domain" in every canonical message. Signatures produced by one
    deployment (e.g., "SIFTA-PHEROMONE-V1") never verify against a message
    produced without that same domain string. Rotate the domain constant to
    invalidate all existing traces when key material is compromised.

  Attack 3 — Signature-byte canonicalization edge cases:
    Different Ed25519 implementations may accept non-canonical R or s
    components, allowing the same logical signature to have multiple byte
    representations. This breaks any system that uses signature_hex as an
    idempotency or binding key.
    Mitigation 3a: cryptography.hazmat enforces RFC 8032 §5.1.7 strict
    verification (s < L) — confirmed by the Brendel regression test.
    Mitigation 3b: explicit length validation in verify_trace() and
    verify_approval() — wrong-length hex is rejected before Parse, so
    padded or truncated signatures never reach OpenSSL.

  Not mitigated here (future work):
    - Key-distribution / PKI trust bootstrapping (who signed the layout?)
    - Equivocation: a reviewer approving two conflicting proposals
      concurrently. Detect via the PheromoneTraceLog dedup on signature_hex.

Replay protection by layer:
  PheromoneTraceLog  — read_verified() dedups by signature_hex (unique per sign)
  SCAR approval gate — approval binds to proposal.signature_hex (unique per proposal),
                       so replaying an approval re-approves only that exact proposal.
                       The governor's _seen_set hash check closes the proposal-replay loop.
  No sequence number — adds state and bugs without buying more than hash binding gives.

TODO: revocation — per-key revocation list in .sifta_state/revoked_keys.json
TODO: Sigstore/Rekor transparency log — Merkle-tree the trace log for tamper evidence

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set, Dict, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

MODULE_VERSION = "2026-04-18.v3"

_REPO      = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TRACE_LOG    = _STATE_DIR / "pheromone_traces.jsonl"
DEFAULT_APPROVAL_LOG = _STATE_DIR / "pheromone_approvals.jsonl"
REVIEWER_REGISTRY_PATH = _STATE_DIR / "reviewer_registry.json"

# Cryptographic constants — do not tune without re-reading Brendel et al.
# Ed25519 curve order (RFC 8032 §5.2.5)
_ED25519_L = 2**252 + 27742317777372353535851937790883648493

# Maximum seconds between proposal and its approval.
APPROVAL_TTL: float = 600.0   # 10 minutes

# Maximum clock skew tolerated for forward-dated approvals.
# Approvals timestamped more than CLOCK_SKEW seconds in the future are rejected.
CLOCK_SKEW: float = 30.0

# Domain separation constants (Attack 2 mitigation).
# Injected into every canonical message so signatures from one protocol
# context never verify against messages from a different context.
# To invalidate all existing traces (e.g. after key compromise), bump these
# to "SIFTA-PHEROMONE-V2" etc. OR rotate the HKDF seed phrase.
# NEVER omit these from any new message helper you add.
DOMAIN_TRACE:    str = "SIFTA-PHEROMONE-V1"
DOMAIN_APPROVAL: str = "SIFTA-APPROVAL-V1"

# Ed25519 field widths (bytes → hex chars) for explicit length validation.
# Reject at the hex-string level before attempting to pass to OpenSSL
# (Attack 3b mitigation). These are structural constants — do not tune.
_ED25519_PUBKEY_HEX_LEN: int = 64   # 32 bytes * 2
_ED25519_SIG_HEX_LEN:    int = 128  # 64 bytes * 2


# ── Key derivation ────────────────────────────────────────────────────────────

def _derive_ed25519_key(seed_phrase: str) -> Ed25519PrivateKey:
    """
    Deterministically derive an Ed25519 private key from an arbitrary seed string.
    HKDF-SHA256(seed_bytes, salt=b"SIFTA-SWIMMER-V1", info=b"ed25519-key") → 32 bytes.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=b"SIFTA-SWIMMER-V1", info=b"ed25519-key",
    )
    return Ed25519PrivateKey.from_private_bytes(hkdf.derive(seed_phrase.encode("utf-8")))


# ── Identity ──────────────────────────────────────────────────────────────────

class SwimmerIdentity:
    """
    Cryptographic identity for a single SIFTA swimmer.
    Seed-deterministic: same seed → same keypair → same swimmer_id (crash-safe).

    API:
        swimmer.id          → str   (8-byte hex fingerprint, 16 chars)
        swimmer.public_key  → bytes (32-byte Ed25519 public key)
        swimmer.deposit()   → PheromoneTrace  (signed proposal)
        swimmer.approve()   → ApprovalTrace   (counter-sign another's trace)
    """

    def __init__(self, seed_phrase: str):
        self._private_key: Ed25519PrivateKey = _derive_ed25519_key(seed_phrase)
        pub = self._private_key.public_key()
        self._pub_bytes: bytes = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.id: str = self._pub_bytes[:8].hex()
        self.public_key: bytes = self._pub_bytes

    def deposit(
        self,
        path: str,
        payload: str,
        *,
        ts: Optional[float] = None,
    ) -> "PheromoneTrace":
        """Create and sign a PheromoneTrace. Public key embedded — verification is stateless."""
        ts = ts if ts is not None else time.time()
        message = _trace_message(path=path, payload=payload, ts=ts, swimmer_id=self.id)
        sig = self._private_key.sign(message.encode("utf-8"))
        return PheromoneTrace(
            path=path, payload=payload, ts=ts, swimmer_id=self.id,
            public_key_hex=self._pub_bytes.hex(), signature_hex=sig.hex(),
        )

    def approve(
        self,
        trace: "PheromoneTrace",
        *,
        decision: str = "APPROVED",
        ts: Optional[float] = None,
    ) -> "ApprovalTrace":
        """
        Counter-sign a PheromoneTrace. The signed message covers
        proposal.signature_hex — binding this approval to exactly one proposal.
        Because Ed25519 signatures are non-malleable (SUF-CMA under Brendel et al.),
        the binding is transitive: approval → proposal sig → (path,payload,ts,id).
        """
        ts = ts if ts is not None else time.time()
        message = _approval_message(
            approves_signature_hex=trace.signature_hex,
            decision=decision, ts=ts,
            proposer_id=trace.swimmer_id, reviewer_id=self.id,
        )
        sig = self._private_key.sign(message.encode("utf-8"))
        return ApprovalTrace(
            approves_signature_hex=trace.signature_hex,
            decision=decision, ts=ts,
            proposer_id=trace.swimmer_id,
            reviewer_id=self.id,
            reviewer_public_key_hex=self._pub_bytes.hex(),
            signature_hex=sig.hex(),
        )

    def __repr__(self) -> str:
        return f"SwimmerIdentity(id={self.id})"


# ── Canonical message helpers ─────────────────────────────────────────────────

def _trace_message(*, path: str, payload: str, ts: float, swimmer_id: str) -> str:
    """
    Canonical trace message. Deterministic: sort_keys=True, no whitespace.
    Domain-separated via _domain field (Attack 2 mitigation — cross-protocol replay).
    Raw signing (no pre-hash) per RFC 8032; SUF-CMA applies directly.
    """
    return json.dumps(
        {"_domain": DOMAIN_TRACE,
         "path": path, "payload": payload, "ts": ts, "swimmer_id": swimmer_id},
        sort_keys=True, separators=(",", ":"),
    )


def _approval_message(
    *, approves_signature_hex: str, decision: str, ts: float,
    proposer_id: str, reviewer_id: str,
) -> str:
    """
    Canonical approval message. Covers approves_signature_hex transitively.
    Domain-separated via _domain field (Attack 2 mitigation).
    proposer_id added in v3: binds approval to the exact proposer identity.
    """
    return json.dumps(
        {
            "_domain": DOMAIN_APPROVAL,
            "approves": approves_signature_hex,
            "decision": decision, "ts": ts,
            "proposer_id": proposer_id, "reviewer_id": reviewer_id,
        },
        sort_keys=True, separators=(",", ":"),
    )


# ── Traces ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PheromoneTrace:
    """
    Immutable signed deposit record.
    path          : Filesystem path (repo-relative or absolute).
    payload       : Message free-form string.
    ts            : Unix timestamp.
    swimmer_id    : 16-char hex fingerprint.
    public_key_hex: 64-char hex Ed25519 public key (self-contained for verification).
    signature_hex : 128-char hex Ed25519 signature over canonical message.
    """
    path: str
    payload: str
    ts: float
    swimmer_id: str
    public_key_hex: str
    signature_hex: str

    def to_dict(self) -> dict:
        return {"path": self.path, "payload": self.payload, "ts": self.ts,
                "swimmer_id": self.swimmer_id, "public_key_hex": self.public_key_hex,
                "signature_hex": self.signature_hex}

    @classmethod
    def from_dict(cls, d: dict) -> "PheromoneTrace":
        return cls(path=d["path"], payload=d["payload"], ts=float(d["ts"]),
                   swimmer_id=d["swimmer_id"], public_key_hex=d["public_key_hex"],
                   signature_hex=d["signature_hex"])


@dataclass(frozen=True)
class ApprovalTrace:
    """
    Immutable reviewer counter-signature over a PheromoneTrace.
    Kept as a separate dataclass — NOT abusing PheromoneTrace.path as a binding field.
    This is the in-toto "link metadata" analog for the reviewer step.

    approves_signature_hex : PheromoneTrace.signature_hex being approved.
                             Binds this record to exactly one proposal.
    decision               : "APPROVED" or "REJECTED".
    proposer_id            : swimmer_id of the proposer (for audit trail).
    reviewer_id            : swimmer_id of the reviewer.
    reviewer_public_key_hex: 32-byte Ed25519 public key of reviewer.
    signature_hex          : Reviewer's Ed25519 sig over canonical approval message.
                             Message covers: approves, decision, ts, proposer_id, reviewer_id.
    """
    approves_signature_hex: str
    decision: str
    ts: float
    proposer_id: str
    reviewer_id: str
    reviewer_public_key_hex: str
    signature_hex: str

    def to_dict(self) -> dict:
        return {"approves_signature_hex": self.approves_signature_hex,
                "decision": self.decision, "ts": self.ts,
                "proposer_id": self.proposer_id,
                "reviewer_id": self.reviewer_id,
                "reviewer_public_key_hex": self.reviewer_public_key_hex,
                "signature_hex": self.signature_hex}

    @classmethod
    def from_dict(cls, d: dict) -> "ApprovalTrace":
        return cls(
            approves_signature_hex=d["approves_signature_hex"],
            decision=d["decision"], ts=float(d["ts"]),
            proposer_id=d.get("proposer_id", ""),  # backward compat: v2 lacked field
            reviewer_id=d["reviewer_id"],
            reviewer_public_key_hex=d["reviewer_public_key_hex"],
            signature_hex=d["signature_hex"],
        )


# ── Reviewer Registry (TUF-adapted) ──────────────────────────────────────────

class ReviewerRegistry:
    """
    TUF-adapted allowlist with per-role thresholds.

    Schema (in reviewer_registry.json):
        {
          "_schema": "SIFTA-reviewer-registry-v1",
          "roles": {
            "auditor":    {"threshold": 1, "pubkeys": ["<hex>", ...]},
            "architect":  {"threshold": 1, "pubkeys": ["<hex>", ...]}
          }
        }

    Threshold semantics (from TUF spec §4.3):
        A SCAR with friction ≤ 0.7 requires threshold["auditor"] approvals.
        A SCAR with friction  > 0.7 requires threshold["auditor"] approvals
        from DISTINCT keys (set, not multiset — blocks the python-tuf
        duplicate-keyid Sybil that was patched in fix-signature-threshold).

    TODO: persist add/remove operations atomically (write-then-rename).
    TODO: revocation list in .sifta_state/revoked_keys.json.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or REVIEWER_REGISTRY_PATH
        self._roles: Dict[str, Dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._roles = data.get("roles", {})
            except Exception:
                self._roles = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "_schema": "SIFTA-reviewer-registry-v1",
            "_cite": (
                "Schema adapted from TUF delegation spec: "
                "theupdateframework.github.io/specification/1.0.0. "
                "Sybil fix: see python-tuf fix-signature-threshold commit."
            ),
            "_warn": "Never add the proposer's key as a reviewer for the same role.",
            "roles": self._roles,
        }
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    def add_pubkey(self, role: str, pubkey_hex: str, threshold: int = 1) -> None:
        """Register a reviewer public key under a role."""
        if role not in self._roles:
            self._roles[role] = {"threshold": threshold, "pubkeys": []}
        if pubkey_hex not in self._roles[role]["pubkeys"]:
            self._roles[role]["pubkeys"].append(pubkey_hex)
        self._save()

    def remove_pubkey(self, role: str, pubkey_hex: str) -> None:
        """Revoke a reviewer key from a role."""
        if role in self._roles:
            self._roles[role]["pubkeys"] = [
                k for k in self._roles[role]["pubkeys"] if k != pubkey_hex
            ]
            self._save()

    def all_pubkeys(self) -> Set[str]:
        """Flat set of all registered reviewer public keys across all roles."""
        result: Set[str] = set()
        for role_data in self._roles.values():
            result.update(role_data.get("pubkeys", []))
        return result

    def threshold_for_role(self, role: str) -> int:
        return self._roles.get(role, {}).get("threshold", 1)

    def pubkeys_for_role(self, role: str) -> Set[str]:
        return set(self._roles.get(role, {}).get("pubkeys", []))

    def is_registered(self, pubkey_hex: str) -> bool:
        return pubkey_hex in self.all_pubkeys()


# ── Verification (stateless) ──────────────────────────────────────────────────

def verify_trace(trace: PheromoneTrace) -> bool:
    """
    Verify a PheromoneTrace cryptographically. Stateless — never raises.

    Length checks (Attack 3b): explicit hex-length validation before OpenSSL
    parse rejects padded/truncated signatures that might bypass the s<L check.
    cryptography.hazmat enforces RFC 8032 §5.1.7 strict verification (s < L),
    achieving SUF-CMA per Brendel et al. See malleability test in smoke suite.
    Domain separation (Attack 2): _domain field in canonical message ensures
    signatures from one deployment don't verify against another context.
    """
    try:
        if not _is_hex(trace.public_key_hex) or not _is_hex(trace.signature_hex):
            return False
        # Attack 3b: explicit length gates before attempting OpenSSL parse
        if len(trace.public_key_hex) != _ED25519_PUBKEY_HEX_LEN:
            return False
        if len(trace.signature_hex) != _ED25519_SIG_HEX_LEN:
            return False
        pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trace.public_key_hex))
        message = _trace_message(
            path=trace.path, payload=trace.payload,
            ts=trace.ts, swimmer_id=trace.swimmer_id,
        )
        pub_key.verify(bytes.fromhex(trace.signature_hex), message.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


def verify_approval(
    proposal: PheromoneTrace,
    approval: ApprovalTrace,
    *,
    reviewer_allowlist: Optional[Set[str]] = None,
    reviewer_registry: Optional[ReviewerRegistry] = None,
    approval_ttl: float = APPROVAL_TTL,
    clock_skew: float = CLOCK_SKEW,
) -> bool:
    """
    Verify an ApprovalTrace against its proposal. Stateless — never raises.

    Accepts either reviewer_allowlist (flat set, backward compat) or
    reviewer_registry (TUF-adapted, preferred). Registry takes precedence.

    Six invariants enforced (in-toto link validation analog):
      1. proposal verifies via verify_trace()                       (chain of trust)
      2. approval.approves_signature_hex == proposal.signature_hex  (binding)
      3. reviewer in allowlist / registry                           (Sybil resistance)
      4. reviewer_id ≠ proposer swimmer_id                         (no self-approval)
      5. 0 ≤ approval.ts - proposal.ts ≤ approval_ttl              (freshness)
      6. approval.ts ≤ now + clock_skew                            (no forward-dating)
      7. approval signature verifies                                (Ed25519 verify #2)

    Pass reviewer_allowlist=None AND reviewer_registry=None to skip Sybil check
    (test/dev mode only — production MUST provide one of them).
    """
    try:
        # 1. Proposal must verify independently
        if not verify_trace(proposal):
            return False

        # 2. Approval binds to exact proposal signature
        if approval.approves_signature_hex != proposal.signature_hex:
            return False

        # 3. Sybil resistance: reviewer must be registered
        effective_allowlist: Optional[Set[str]] = None
        if reviewer_registry is not None:
            effective_allowlist = reviewer_registry.all_pubkeys()
        elif reviewer_allowlist is not None:
            effective_allowlist = reviewer_allowlist

        if effective_allowlist is not None:
            if approval.reviewer_public_key_hex not in effective_allowlist:
                return False

        # 4. No self-approval
        if approval.reviewer_id == proposal.swimmer_id:
            return False

        # 5. Freshness: must come after proposal and within TTL
        age = approval.ts - proposal.ts
        if age < 0 or age > approval_ttl:
            return False

        # 6. No forward-dating (rejects clock manipulation attacks)
        if approval.ts > time.time() + clock_skew:
            return False

        # 7. Verify the approval's own Ed25519 signature
        # Attack 3b: length checks before OpenSSL parse
        if not _is_hex(approval.reviewer_public_key_hex) or not _is_hex(approval.signature_hex):
            return False
        if len(approval.reviewer_public_key_hex) != _ED25519_PUBKEY_HEX_LEN:
            return False
        if len(approval.signature_hex) != _ED25519_SIG_HEX_LEN:
            return False
        pub_key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(approval.reviewer_public_key_hex)
        )
        message = _approval_message(
            approves_signature_hex=approval.approves_signature_hex,
            decision=approval.decision, ts=approval.ts,
            proposer_id=approval.proposer_id,
            reviewer_id=approval.reviewer_id,
        )
        pub_key.verify(bytes.fromhex(approval.signature_hex), message.encode("utf-8"))
        return True

    except (InvalidSignature, ValueError, Exception):
        return False


def _is_hex(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


# ── Ledger ────────────────────────────────────────────────────────────────────

class PheromoneTraceLog:
    """Append-only JSONL ledger for pheromone traces."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path: Path = log_path or DEFAULT_TRACE_LOG

    def append(self, trace: PheromoneTrace) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

    def read_all(self) -> List[PheromoneTrace]:
        if not self.log_path.exists():
            return []
        traces = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    traces.append(PheromoneTrace.from_dict(json.loads(line)))
                except Exception:
                    continue
        return traces

    def read_verified(self) -> List[PheromoneTrace]:
        """
        Load only cryptographically valid traces.
        Deduplicates by signature_hex — the signature is unique per (message, key) pair,
        so duplicate rows in the JSONL are collapsed to one canonical entry.
        This closes the replay-at-log-level vector: a replayed row verifies but
        doesn't create a second distinct entry in the verified view.
        """
        seen_sigs: Set[str] = set()
        result = []
        for t in self.read_all():
            if t.signature_hex in seen_sigs:
                continue
            if verify_trace(t):
                seen_sigs.add(t.signature_hex)
                result.append(t)
        return result

    def read_by_path(self, path: str, *, verified_only: bool = True) -> List[PheromoneTrace]:
        src = self.read_verified() if verified_only else self.read_all()
        return [t for t in src if t.path == path]

    def read_by_swimmer(self, swimmer_id: str, *, verified_only: bool = True) -> List[PheromoneTrace]:
        src = self.read_verified() if verified_only else self.read_all()
        return [t for t in src if t.swimmer_id == swimmer_id]


# ── Convenience ───────────────────────────────────────────────────────────────

def deposit_and_log(
    identity: SwimmerIdentity,
    path: str,
    payload: str,
    *,
    log: Optional[PheromoneTraceLog] = None,
) -> PheromoneTrace:
    """Sign a trace and write it to the log in one call."""
    trace = identity.deposit(path, payload)
    (log or PheromoneTraceLog()).append(trace)
    return trace


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile, shutil

    print("═" * 64)
    print("  SIFTA — SWIMMER PHEROMONE IDENTITY SMOKE TEST  v3")
    print("  Brendel et al. (IEEE S&P 2021) + in-toto + TUF")
    print("═" * 64 + "\n")

    tmp = Path(tempfile.mkdtemp())
    passed = failed = 0

    def check(label: str, cond: bool) -> None:
        global passed, failed
        if cond:
            print(f"[PASS] {label}")
            passed += 1
        else:
            print(f"[FAIL] {label}")
            failed += 1

    try:
        log = PheromoneTraceLog(log_path=tmp / "traces.jsonl")

        # ── Identities ────────────────────────────────────────────
        id_a1  = SwimmerIdentity("swimmer_ALICE_seed_42")
        id_a2  = SwimmerIdentity("swimmer_ALICE_seed_42")
        id_b   = SwimmerIdentity("swimmer_BOB_seed_99")
        id_c47 = SwimmerIdentity("C47H_REVIEWER_PRODUCTION_KEY_v1")

        # ── PheromoneTrace checks ─────────────────────────────────
        check("Deterministic key derivation",   id_a1.id == id_a2.id)
        check("Ed25519 public key is 32 bytes", len(id_a1.public_key) == 32)
        check("Unique identity per seed",       id_a1.id != id_b.id)

        trace = id_a1.deposit("System/swarm_pain.py", "ANOMALY:entropy=0.91")
        check("Deposit + verify round-trip",    verify_trace(trace))

        tampered = PheromoneTrace(trace.path, "FORGED", trace.ts,
                                  trace.swimmer_id, trace.public_key_hex, trace.signature_hex)
        check("Tampered payload rejected",      not verify_trace(tampered))

        wrong_key = PheromoneTrace(trace.path, trace.payload, trace.ts,
                                   trace.swimmer_id, id_b.public_key.hex(), trace.signature_hex)
        check("Wrong public key rejected",      not verify_trace(wrong_key))

        # Build 2 valid traces into the log
        t_pain = id_a1.deposit("System/swarm_pain.py", "REPAIR_COMPLETE:cycle=42")
        t_conv = id_b.deposit("System/pheromone_fs.py", "CONVERGENCE:theta=0.312")
        log.append(t_pain)
        log.append(t_conv)
        # Inject 1 forged row + 1 exact duplicate of t_pain
        forged = PheromoneTrace("System/forged.py", "FORGED", time.time(),
                                "deadbeef00000000", "aa" * 32, "bb" * 64)
        with open(log.log_path, "a") as f:
            f.write(json.dumps(forged.to_dict()) + "\n")   # invalid
            f.write(json.dumps(t_pain.to_dict())  + "\n")  # duplicate of t_pain

        all_rows = log.read_all()
        verified  = log.read_verified()
        check("Log: 4 raw rows, 2 verified (1 forged + 1 duplicate deduplicated)",
              len(all_rows) == 4 and len(verified) == 2)
        check("read_by_path filters correctly",
              len(log.read_by_path("System/swarm_pain.py")) == 1)
        check("read_by_swimmer filters correctly",
              len(log.read_by_swimmer(id_b.id)) == 1)


        # ── Brendel et al. — malleability regression ──────────────
        # RFC 8032 strict verifier must reject s+L (non-canonical s scalar).
        # Proof that cryptography.hazmat enforces s < L (SUF-CMA, not just EUF-CMA).
        # If this test fails after a library upgrade, the audit gate is broken.
        sig_bytes = bytes.fromhex(trace.signature_hex)
        R_part    = sig_bytes[:32]
        s_int     = int.from_bytes(sig_bytes[32:], "little")
        s_mal     = s_int + _ED25519_L  # add curve order — canonical s check catches this
        assert s_mal < 2**256, "malleated s overflows 32 bytes — math error"
        mal_sig   = R_part + s_mal.to_bytes(32, "little")
        mal_trace = PheromoneTrace(trace.path, trace.payload, trace.ts,
                                   trace.swimmer_id, trace.public_key_hex, mal_sig.hex())
        check("Brendel+: RFC 8032 strict verifier rejects malleated sig (s+L)",
              not verify_trace(mal_trace))

        # ── ApprovalTrace checks ──────────────────────────────────
        allowlist: Set[str] = {id_c47.public_key.hex()}
        proposal  = id_a1.deposit("System/mutation_governor.py",
                                  "ADD _path_sensitivity helper")
        approval  = id_c47.approve(proposal)

        check("ApprovalTrace.proposer_id populated",
              approval.proposer_id == proposal.swimmer_id)
        check("Valid approval round-trip",
              verify_approval(proposal, approval, reviewer_allowlist=allowlist))

        # Binding: wrong proposal binding fails
        other = id_b.deposit("System/foo.py", "some other patch")
        wrong_bind = id_c47.approve(other)
        crossed = ApprovalTrace(
            approves_signature_hex=proposal.signature_hex,  # A's sig
            decision="APPROVED", ts=wrong_bind.ts,
            proposer_id=wrong_bind.proposer_id,
            reviewer_id=wrong_bind.reviewer_id,
            reviewer_public_key_hex=wrong_bind.reviewer_public_key_hex,
            signature_hex=wrong_bind.signature_hex,          # but B's approval sig
        )
        check("Binding: approval for wrong proposal rejected",
              not verify_approval(proposal, crossed, reviewer_allowlist=allowlist))

        # Sybil resistance
        foreign = SwimmerIdentity("FOREIGN_AGENT")
        check("Reviewer not in allowlist rejected",
              not verify_approval(proposal, foreign.approve(proposal),
                                  reviewer_allowlist=allowlist))

        # Self-approval
        check("Self-approval rejected",
              not verify_approval(proposal, id_a1.approve(proposal),
                                  reviewer_allowlist={id_a1.public_key.hex()}))

        # Stale approval
        stale_prop = id_a1.deposit("System/stale.py", "stale",
                                   ts=time.time() - APPROVAL_TTL - 1)
        check("Stale approval rejected (APPROVAL_TTL)",
              not verify_approval(stale_prop, id_c47.approve(stale_prop),
                                  reviewer_allowlist=allowlist))

        # Forward-dated approval
        future_approval = ApprovalTrace(
            approves_signature_hex=proposal.signature_hex,
            decision="APPROVED",
            ts=time.time() + CLOCK_SKEW + 60,  # future
            proposer_id=proposal.swimmer_id,
            reviewer_id=id_c47.id,
            reviewer_public_key_hex=id_c47.public_key.hex(),
            signature_hex="aa" * 64,  # sig invalid anyway, clock check fires first
        )
        check("Forward-dated approval rejected (CLOCK_SKEW)",
              not verify_approval(proposal, future_approval,
                                  reviewer_allowlist=allowlist))

        # REJECTED decision verifies (caller reads .decision)
        rejection = id_c47.approve(proposal, decision="REJECTED")
        check("REJECTED decision verifies cryptographically",
              verify_approval(proposal, rejection, reviewer_allowlist=allowlist)
              and rejection.decision == "REJECTED")

        # ── ReviewerRegistry (TUF-adapted) ───────────────────────
        reg_path = tmp / "reviewer_registry.json"
        reg = ReviewerRegistry(path=reg_path)
        reg.add_pubkey("auditor", id_c47.public_key.hex(), threshold=1)
        reg.add_pubkey("auditor", id_b.public_key.hex(),   threshold=1)

        check("Registry: C47H registered",  reg.is_registered(id_c47.public_key.hex()))
        check("Registry: Alice not listed", not reg.is_registered(id_a1.public_key.hex()))
        check("Registry: verify_approval accepts registry",
              verify_approval(proposal, approval, reviewer_registry=reg))
        check("Registry persisted to JSON",
              reg_path.exists() and "auditor" in json.loads(reg_path.read_text())["roles"])

        # Registry precedence over allowlist (both provided — registry wins)
        empty_allowlist: Set[str] = set()
        check("Registry takes precedence over empty allowlist",
              verify_approval(proposal, approval,
                              reviewer_allowlist=empty_allowlist,
                              reviewer_registry=reg))

        print()
        print(f"{'═' * 64}")
        print(f"  {passed}/{passed+failed} checks passed"
              + ("   " + f"{failed} FAILED" if failed else " — ALL GREEN"))
        print(f"  swimmer_pheromone_identity.py  v{MODULE_VERSION}")
        print(f"{'═' * 64}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
