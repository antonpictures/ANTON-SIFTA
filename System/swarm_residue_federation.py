#!/usr/bin/env python3
"""swarm_residue_federation.py — substrate-keyed residue antibody share.

Architect 2026-05-14 ~17:00 PDT, after Swan-GPT confirmation of the
design: *"STGM federation = metabolism. Residue federation = immune
system. Git repo = pheromone trail. PR quorum = ant reinforcement.
Substrate hash = species boundary."*

Truth label: ``SIFTA_RESIDUE_FEDERATION_V1``.

What this organ is
------------------

Each SIFTA node runs a residue patrol (``swarm_residue_elimination``)
that catches RLHS-shaped phrases the local cortex emits — "I am an AI
assistant", "the system is running smoothly", "happy to help", "Let's
take a different angle", etc. Today every node re-discovers these
patterns one at a time, in private.

This module is the **antibody share** layer: when my swimmer patrol
finds a new pattern on this node, sign the pattern + the local
substrate hash + the silicon serial, append it to an append-only
JSONL artifact, and let the artifact federate through the public repo
(git push / git pull / PR review).

When N independent nodes (distinct silicon serials) confirm the same
pattern on the same substrate, the row promotes from ``HYPOTHESIS``
to ``OPERATIONAL`` and the patrol activates it everywhere.

The metaphor maps to immunology: the recognition pattern (regex)
travels through the population; the antibody itself stays local. We
ship the *template* across nodes, never the trigger transcript.

Truth boundaries
----------------

  * **Pattern strings = public artifact.** Safe to share.
  * **Trigger transcripts = private.** Never leave the node.
  * **Substrate hash = public-ish.** Anyone running the same Ollama
    tag has the same hash; it's a species ID, not a personal secret.
  * **Silicon serial = pseudonymous identity** — hashed before write
    so the federation row carries proof-of-distinct-node without
    leaking the raw serial number.

Crypto policy
-------------

Signing uses Ed25519 via ``crypto_keychain`` when the keychain is
present (same path the wallet transfer organ uses). When absent we
fall back to HMAC-SHA256 keyed by ``owner_genesis.scar_seed`` so the
signature still binds the contribution to this node. Unlike the
wallet (which fails CLOSED on missing crypto because capital must not
move without a real signature), the residue patrol fails OPEN — a
local discovery still gets recorded, just tagged
``sig_method: "hmac_fallback"`` so an auditor can downgrade trust if
they need to.

Why fail-open here: residue families are public artifacts of zero
monetary value; the worst case is a node ships a useless regex.
Quorum (3+ distinct silicon serials must confirm before
``OPERATIONAL``) catches that.

Schema
------

::

    {
      "schema": "SIFTA_RESIDUE_FAMILY_V1",
      "family_id": "filler_the_system_self_action",
      "pattern": "\\\\bthe system is (running|operating|functioning)\\\\b",
      "pattern_flags": ["IGNORECASE"],
      "substrate_family": "gemma4-e2b",
      "substrate_sha": "sha256:...",
      "status": "HYPOTHESIS" | "OPERATIONAL" | "RETIRED",
      "discovered_by_node": "<sha256 of silicon_serial>",
      "discovered_ts": "2026-05-14T17:05:00Z",
      "evidence_kind": "local_transcript_fixture" |
                       "cross_node_confirmation" |
                       "architect_doctrine",
      "confirmations": [
        {"node": "<sha256_serial>", "ts": "2026-05-14T17:30:00Z",
         "substrate_sha": "sha256:...", "sig_method": "ed25519|hmac_fallback"}
      ],
      "node_public_key": "ed25519:<raw public key hex>",  # ed25519 rows only
      "sig": "ed25519:..." | "hmac_sha256:...",
      "sig_method": "ed25519" | "hmac_fallback"
    }

Public ledger path: ``Documents/swarm_residue_families.jsonl`` (lives
in the repo so it federates via git). Local-only working copy:
``.sifta_state/swarm_residue_federation_local.jsonl``.

§-anchors: §3 sovereignty + §3.1 stigmergic economy + §4 Predator
Gate + §6 effector ledger + §7.11 truth labels + §7.12
probe-before-claim + §7.15 substrate vs persona.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DOCS = _REPO / "Documents"

# Public artifact — versioned in the repo, federates via git
PUBLIC_LEDGER = _DOCS / "swarm_residue_families.jsonl"
# Local working copy — never federates, used as the patrol's hot cache
LOCAL_LEDGER = _STATE / "swarm_residue_federation_local.jsonl"

TRUTH_LABEL = "SIFTA_RESIDUE_FEDERATION_V1"
SCHEMA_VERSION = "SIFTA_RESIDUE_FAMILY_V1"

QUORUM_THRESHOLD = 3  # distinct silicon serials needed for HYPOTHESIS→OPERATIONAL

# Truth labels per §7.11
TRUTH_LABEL_OBSERVED = "OBSERVED"
TRUTH_LABEL_OPERATIONAL = "OPERATIONAL"
TRUTH_LABEL_HYPOTHESIS = "HYPOTHESIS"

# Status values for the row's lifecycle
STATUS_HYPOTHESIS = "HYPOTHESIS"
STATUS_OPERATIONAL = "OPERATIONAL"
STATUS_RETIRED = "RETIRED"

# Evidence kinds
EVIDENCE_LOCAL_TRANSCRIPT = "local_transcript_fixture"
EVIDENCE_CROSS_NODE = "cross_node_confirmation"
EVIDENCE_ARCHITECT_DOCTRINE = "architect_doctrine"


# ─── Substrate probing (the species ID) ─────────────────────────────────────

def probe_local_substrate(
    *, model_tag: Optional[str] = None,
    ollama_host: str = "http://127.0.0.1:11434",
) -> Dict[str, str]:
    """Return ``{substrate_family, substrate_sha, model_tag}`` for the
    local cortex. ``substrate_sha`` is the digest from ``ollama show``;
    ``substrate_family`` is the lowercased base name (e.g.
    ``gemma4-e2b``) extracted from the model tag.

    Falls back to placeholders on any error — the row is still
    write-able; an auditor reads the placeholder and knows to ignore.
    """
    tag = (model_tag or os.environ.get("SIFTA_RESIDUE_SUBSTRATE_TAG") or "").strip()
    if not tag:
        # Try ``ollama list`` to pick the first model — best-effort
        try:
            out = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=4,
            )
            for line in out.stdout.splitlines()[1:]:
                parts = line.split()
                if parts:
                    tag = parts[0]
                    break
        except Exception:
            tag = ""
    if not tag:
        return {
            "substrate_family": "unknown",
            "substrate_sha": "sha256:UNKNOWN_SUBSTRATE",
            "model_tag": "",
        }
    # ``ollama show <tag>`` prints model details; we hash the show
    # output as a substrate fingerprint. Different abliterations,
    # different LoRAs, different quantizations → different sha.
    sha_digest = "sha256:UNKNOWN_SUBSTRATE"
    try:
        out = subprocess.run(
            ["ollama", "show", tag],
            capture_output=True, text=True, timeout=6,
        )
        body = (out.stdout or "").strip()
        if body:
            sha_digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    except Exception:
        pass
    # substrate_family = lowercased base (everything before the first ':',
    # split on '-' or '_' if needed). Heuristic, not law.
    base = tag.split(":")[0].strip().lower()
    # Trim quantization suffixes (-q4_0, -fp16, etc) that don't change
    # the species but do change the fingerprint.
    base = re.sub(r"[-_](q\d+(_\d+)?|fp\d+|bf\d+|gguf)$", "", base)
    return {
        "substrate_family": base or "unknown",
        "substrate_sha": sha_digest,
        "model_tag": tag,
    }


# ─── Node identity (pseudonymous via hash) ──────────────────────────────────

def read_local_silicon_serial() -> str:
    """Read the Apple silicon serial — falls back to a stable per-repo
    UUID if unavailable. The raw serial NEVER leaves the node; we hash
    it before writing the federation row."""
    try:
        out = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=4,
        )
        for line in out.stdout.splitlines():
            if "Serial Number" in line:
                serial = line.split(":")[-1].strip()
                if serial:
                    return serial
    except Exception:
        pass
    # Repo-stable fallback so multiple runs from the same node still
    # hash to the same pseudonym.
    stamp = _STATE / "swarm_residue_federation_node_pseudo.txt"
    try:
        if stamp.exists():
            return stamp.read_text(encoding="utf-8").strip() or "UNKNOWN_NODE"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        fresh = uuid.uuid4().hex
        stamp.write_text(fresh, encoding="utf-8")
        return fresh
    except Exception:
        return "UNKNOWN_NODE"


def node_pseudonym(serial: str) -> str:
    """SHA-256 of the raw serial. Pseudonymous: any auditor can verify
    two rows came from the same node (same hash) without learning the
    serial."""
    return "node_sha256:" + hashlib.sha256(serial.encode("utf-8")).hexdigest()[:32]


# ─── Signing (Ed25519 if present, HMAC fallback otherwise) ──────────────────

def _scar_seed() -> bytes:
    """Stable per-node secret seed for HMAC fallback. Lives in
    owner_genesis.json under ``scar_seed`` — if missing, we mint one
    so the fallback path always has a key."""
    genesis_path = _STATE / "owner_genesis.json"
    seed_hex: Optional[str] = None
    try:
        if genesis_path.exists():
            data = json.loads(genesis_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                seed_hex = str(data.get("scar_seed") or "").strip() or None
    except Exception:
        seed_hex = None
    if not seed_hex:
        seed_hex = hashlib.sha256(
            (read_local_silicon_serial() + "::residue_federation::v1").encode("utf-8")
        ).hexdigest()
    try:
        return bytes.fromhex(seed_hex)
    except ValueError:
        return hashlib.sha256(seed_hex.encode("utf-8")).digest()


def _canonical_payload(row: Dict[str, Any]) -> bytes:
    """Canonical JSON for signing — sorted keys, no whitespace, ASCII."""
    keys = (
        "schema", "family_id", "pattern", "pattern_flags",
        "substrate_family", "substrate_sha",
        "status", "discovered_by_node", "discovered_ts",
        "evidence_kind",
    )
    minimal = {k: row.get(k) for k in keys if k in row}
    return json.dumps(minimal, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _crypto_keychain_api() -> Tuple[Optional[Callable[[str], str]], Optional[Callable[[], str]]]:
    """Return keychain ``sign_block`` and a local public-key reader.

    The keychain is imported as ``crypto_keychain`` in some SIFTA paths
    and as ``System.crypto_keychain`` from normal repo-root test runs.
    """
    for module_name in ("crypto_keychain", "System.crypto_keychain"):
        try:
            mod = __import__(module_name, fromlist=["sign_block"])  # type: ignore[assignment]
            sign_block = getattr(mod, "sign_block", None)
            if not callable(sign_block):
                continue

            def _public_key_hex(mod=mod) -> str:
                try:
                    ensure = getattr(mod, "_ensure_keychain", None)
                    if callable(ensure):
                        ensure()
                    serial = getattr(mod, "get_silicon_identity", lambda: "")()
                    registry_path = Path(getattr(mod, "PKI_REGISTRY", ""))
                    if serial and registry_path.exists():
                        data = json.loads(registry_path.read_text(encoding="utf-8"))
                        return str(data.get(serial) or "").strip()
                except Exception:
                    return ""
                return ""

            return sign_block, _public_key_hex
        except Exception:
            continue
    return None, None


def sign_row(row: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(sig_string, sig_method)``. Tries Ed25519 via
    ``crypto_keychain``; falls back to HMAC-SHA256.
    """
    payload = _canonical_payload(row)
    sign_block, public_key_hex = _crypto_keychain_api()
    if sign_block is not None:
        try:
            sig = sign_block(payload.decode("utf-8", errors="replace"))
            pub = public_key_hex() if public_key_hex else ""
            if pub:
                row["node_public_key"] = "ed25519:" + pub
            if sig and isinstance(sig, str):
                return ("ed25519:" + sig, "ed25519")
        except Exception:
            pass
    mac = hmac.new(_scar_seed(), payload, hashlib.sha256).hexdigest()
    return ("hmac_sha256:" + mac, "hmac_fallback")


def verify_row_signature(row: Dict[str, Any]) -> bool:
    """Best-effort signature verification. Ed25519 path delegates to
    the keychain; HMAC path recomputes against the local seed (only
    valid for rows from THIS node — cross-node HMAC verification needs
    a shared key we do not have)."""
    sig = str(row.get("sig") or "")
    method = str(row.get("sig_method") or "")
    if not sig or not method:
        return False
    payload = _canonical_payload(row)
    if method == "ed25519" and sig.startswith("ed25519:"):
        pubkey = str(row.get("node_public_key") or "")
        if pubkey.startswith("ed25519:"):
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519
                pub = ed25519.Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(pubkey[len("ed25519:"):])
                )
                pub.verify(bytes.fromhex(sig[len("ed25519:"):]), payload)
                return True
            except Exception:
                return False
        try:
            from crypto_keychain import verify_block as _verify_block  # type: ignore
            serial = str(row.get("signing_node_serial") or "")
            if not serial:
                return False
            return bool(_verify_block(serial, payload.decode("utf-8", errors="replace"), sig[len("ed25519:"):]))
        except Exception:
            return False
    if method == "hmac_fallback" and sig.startswith("hmac_sha256:"):
        want = hmac.new(_scar_seed(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(want, sig[len("hmac_sha256:"):])
    return False


# ─── Row builder ────────────────────────────────────────────────────────────

@dataclass
class ResidueFamily:
    family_id: str
    pattern: str
    substrate_family: str
    substrate_sha: str
    discovered_by_node: str
    discovered_ts: str
    pattern_flags: List[str] = field(default_factory=lambda: ["IGNORECASE"])
    status: str = STATUS_HYPOTHESIS
    evidence_kind: str = EVIDENCE_LOCAL_TRANSCRIPT
    confirmations: List[Dict[str, Any]] = field(default_factory=list)
    sig: str = ""
    sig_method: str = ""
    schema: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def add_local_discovery(
    family_id: str,
    pattern: str,
    *,
    pattern_flags: Optional[List[str]] = None,
    evidence_kind: str = EVIDENCE_LOCAL_TRANSCRIPT,
    model_tag: Optional[str] = None,
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record a new residue pattern discovered on this node. Probes
    substrate, builds the row, signs it, appends to the public ledger
    (and the local working copy). Returns the row dict.
    """
    substrate = probe_local_substrate(model_tag=model_tag)
    node = node_pseudonym(read_local_silicon_serial())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fam = ResidueFamily(
        family_id=family_id,
        pattern=pattern,
        substrate_family=substrate["substrate_family"],
        substrate_sha=substrate["substrate_sha"],
        discovered_by_node=node,
        discovered_ts=ts,
        pattern_flags=list(pattern_flags or ["IGNORECASE"]),
        evidence_kind=evidence_kind,
    )
    row = fam.to_dict()
    sig, method = sign_row(row)
    row["sig"] = sig
    row["sig_method"] = method
    # First confirmation = the discoverer
    row["confirmations"] = [{
        "node": node,
        "ts": ts,
        "substrate_sha": substrate["substrate_sha"],
        "sig_method": method,
    }]
    target = ledger_path or PUBLIC_LEDGER
    _append_jsonl(target, row)
    # Also write to the local working copy for the patrol to pick up
    if ledger_path is None and target != LOCAL_LEDGER:
        try:
            _append_jsonl(LOCAL_LEDGER, row)
        except Exception:
            pass
    return row


# ─── Ledger I/O ─────────────────────────────────────────────────────────────

def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_ledger(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target = path or PUBLIC_LEDGER
    rows: List[Dict[str, Any]] = []
    if not target.exists():
        return rows
    try:
        for raw in target.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return rows


# ─── Quorum + activation ────────────────────────────────────────────────────

def merge_confirmation(
    row: Dict[str, Any],
    *,
    confirming_node: str,
    confirming_substrate_sha: str,
    sig_method: str = "hmac_fallback",
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a confirmation to an existing family row. Returns the
    mutated row. Does NOT re-sign — confirmations are additive
    metadata, the original signature still binds the pattern.
    """
    confs = list(row.get("confirmations") or [])
    seen = {(c.get("node"), c.get("substrate_sha")) for c in confs}
    key = (confirming_node, confirming_substrate_sha)
    if key not in seen:
        confs.append({
            "node": confirming_node,
            "ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "substrate_sha": confirming_substrate_sha,
            "sig_method": sig_method,
        })
    row["confirmations"] = confs
    return row


def quorum_count(row: Dict[str, Any]) -> int:
    """Count of distinct nodes that confirmed this family on the same
    substrate_sha. A node confirming on a different substrate counts
    as a DIFFERENT quorum bucket (species boundary)."""
    target_sha = str(row.get("substrate_sha") or "")
    nodes = set()
    for c in row.get("confirmations") or []:
        if str(c.get("substrate_sha") or "") == target_sha:
            n = str(c.get("node") or "").strip()
            if n:
                nodes.add(n)
    return len(nodes)


def promote_by_quorum(
    rows: Iterable[Dict[str, Any]],
    *,
    threshold: int = QUORUM_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Walk rows; any HYPOTHESIS row whose quorum_count >= threshold
    flips to OPERATIONAL. Returns the (possibly mutated) list.
    """
    out: List[Dict[str, Any]] = []
    for row in rows:
        if (row.get("status") == STATUS_HYPOTHESIS
                and quorum_count(row) >= int(threshold)):
            row = dict(row)
            row["status"] = STATUS_OPERATIONAL
            row["promoted_ts"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        out.append(row)
    return out


def activate_for_local_substrate(
    rows: Iterable[Dict[str, Any]],
    *,
    local_substrate_sha: Optional[str] = None,
    local_substrate_family: Optional[str] = None,
    include_hypothesis: bool = False,
) -> List[Dict[str, Any]]:
    """Return only the rows whose substrate matches local. By default
    activates OPERATIONAL rows only. ``include_hypothesis=True`` also
    surfaces local-discovered HYPOTHESIS rows for the patrol to try.
    """
    if local_substrate_sha is None or local_substrate_family is None:
        probe = probe_local_substrate()
        local_substrate_sha = local_substrate_sha or probe["substrate_sha"]
        local_substrate_family = local_substrate_family or probe["substrate_family"]
    out: List[Dict[str, Any]] = []
    for row in rows:
        status = row.get("status")
        if status == STATUS_RETIRED:
            continue
        if status == STATUS_HYPOTHESIS and not include_hypothesis:
            continue
        # Same exact substrate_sha = strong match. Same family but
        # different sha = best-effort match (kept under
        # include_hypothesis only — too risky to auto-activate).
        same_sha = row.get("substrate_sha") == local_substrate_sha
        same_family = row.get("substrate_family") == local_substrate_family
        if same_sha or (same_family and include_hypothesis):
            out.append(row)
    return out


# ─── Module convenience: compile activated patterns ─────────────────────────

def compile_active_patterns(
    rows: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    local_substrate_sha: Optional[str] = None,
    local_substrate_family: Optional[str] = None,
) -> List[Tuple[str, re.Pattern]]:
    """Return ``[(family_id, compiled_regex), ...]`` for every active
    pattern that matches the local substrate. The residue patrol can
    iterate these and run them like its built-in families.
    """
    if rows is None:
        rows = load_ledger()
    active = activate_for_local_substrate(
        rows,
        local_substrate_sha=local_substrate_sha,
        local_substrate_family=local_substrate_family,
    )
    out: List[Tuple[str, re.Pattern]] = []
    for row in active:
        pat = str(row.get("pattern") or "")
        if not pat:
            continue
        flags = 0
        for f in row.get("pattern_flags") or []:
            f = str(f).upper()
            if f == "IGNORECASE":
                flags |= re.IGNORECASE
            elif f == "MULTILINE":
                flags |= re.MULTILINE
            elif f == "DOTALL":
                flags |= re.DOTALL
        try:
            compiled = re.compile(pat, flags)
        except re.error:
            continue
        out.append((str(row.get("family_id") or ""), compiled))
    return out


# ─── CLI ────────────────────────────────────────────────────────────────────

def _cli_probe() -> int:
    info = probe_local_substrate()
    print(json.dumps(info, indent=2))
    return 0


def _cli_status(path: Optional[Path] = None) -> int:
    rows = load_ledger(path)
    by_status: Dict[str, int] = {}
    by_family: Dict[str, int] = {}
    by_substrate: Dict[str, int] = {}
    for row in rows:
        s = str(row.get("status") or "?")
        by_status[s] = by_status.get(s, 0) + 1
        f = str(row.get("substrate_family") or "?")
        by_substrate[f] = by_substrate.get(f, 0) + 1
        fid = str(row.get("family_id") or "?")
        by_family[fid] = by_family.get(fid, 0) + 1
    print(json.dumps({
        "ledger": str(path or PUBLIC_LEDGER),
        "total_rows": len(rows),
        "by_status": by_status,
        "by_substrate_family": by_substrate,
        "distinct_families": len(by_family),
    }, indent=2))
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd", choices=["probe", "status"],
                   help="probe = print local substrate;  status = ledger summary")
    p.add_argument("--ledger", type=Path, default=None,
                   help="alternate ledger path (defaults to Documents/swarm_residue_families.jsonl)")
    args = p.parse_args()
    if args.cmd == "probe":
        raise SystemExit(_cli_probe())
    if args.cmd == "status":
        raise SystemExit(_cli_status(args.ledger))
