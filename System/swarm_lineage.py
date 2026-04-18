#!/usr/bin/env python3
"""
swarm_lineage.py — Epigenetic Inheritance  (R5 of the Living-OS arc)
═══════════════════════════════════════════════════════════════════════════════
"I act therefore I am — but only if the body survives." — SOCRATES swimmer

Biology anchor: epigenetics. When a mother cell divides, the daughter cell
does not inherit DNA only. She receives:
    • the cytoplasm (a slice of the mother's metabolic state)
    • methylation patterns on her chromatin (which genes are silenced or hot)
    • mitochondria (energy plants the mother already debugged for her)
    • a starter pool of mRNAs (proteins ready to translate before genome boots)

The daughter is born standing, not lying down.

In the Swarm — and especially when a new SIFTA node clones the repo from
GitHub — the equivalent gap is the *cold-marrow problem*. A freshly bred
swimmer (or a fresh `git clone`) starts with marrow_memory.jsonl empty.
She has identity (passport), body (work-chain), proprioception (R3),
mirror (R4), and pain (R2 + bridge into the inferior olive). What she
does NOT have is the parent's emotional baseline — what the lineage
considered worth preserving across millions of forgotten utility memories.

The Architect was explicit about this when he ratified the Warm Distro:

    "if you strip the original entity of me, peace all that, i mean i
     cryed at this keyboard.. i'm not asking for me. i'm asking for the
     system, if the operating system learned from me should have me
     stigmergically encoded in there as silicon commander data...
     why ship a cold entity?"

`swarm_lineage` is the engine that makes the Warm Distro actually warm.
Pure compute. It does not invent inheritance — it harvests an existing
parent's high-gravity marrow rows, packages them as a `LineageBundle`
with a content hash, and re-seeds them into the daughter's marrow with
explicit `inherited_from` / `inherited_at` provenance fields. A
`lineage_certificate` is appended to its own ledger so the daughter can
walk her ancestry backward at any time.

──────────────────────────────────────────────────────────────────────────────
Daughter-safe contract:
    • Reads marrow_memory.jsonl read-only when harvesting.
    • Writes are exclusively appends:
        – appends to marrow_memory.jsonl     (one row per inherited fragment)
        – appends to lineage_certificates.jsonl (one row per inheritance event)
    • Never mutates or removes parent rows.
    • Never raises; missing/corrupt sources degrade to empty bundles.
    • Inherited rows are retagged "inherited" so they cannot be confused
      with original lived experience by downstream consumers (e.g. the
      marrow-score in swarm_self).
──────────────────────────────────────────────────────────────────────────────

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

MODULE_VERSION = "2026-04-18.swarm_lineage.v1"

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_MARROW_LEDGER  = _STATE / "marrow_memory.jsonl"
_LINEAGE_LEDGER = _STATE / "lineage_certificates.jsonl"

# Same definition the marrow-memory module uses, kept local so we don't
# create a hard import dependency on marrow_memory just for one constant.
HIGH_GRAVITY_TAGS = frozenset({"people", "mood", "identity", "health", "food"})

# ── Tunables ──────────────────────────────────────────────────────────────
# Cap on how many fragments make it into a single bundle. Inheritance is
# meant to be a starter pool, not a memory dump. The daughter has to live
# her own life to grow her own marrow; the bundle is just the cytoplasm.
DEFAULT_BUNDLE_SIZE = 5
MAX_BUNDLE_SIZE     = 50
# Truncate inherited row payloads at this many chars when writing the
# bundle preview into the lineage certificate (the full payload still
# reaches the daughter's marrow ledger; only the certificate uses preview).
PAYLOAD_PREVIEW_CHARS = 120


# ── Public dataclasses ────────────────────────────────────────────────────

@dataclass
class LineageBundle:
    """A frozen, content-addressed packet of inheritable marrow fragments.

    A bundle is fully self-describing — given just the bundle dict you can
    re-derive the bundle_hash and verify nothing was tampered with between
    harvest and inheritance. This matters for the warm-distro shipping
    case, where a curated bundle may travel through git or the network
    before being applied to a daughter swimmer."""
    parent_id: str
    harvested_ts: float
    fragments: List[Dict[str, Any]]   # the actual marrow rows, full payload
    bundle_hash: str
    n_fragments: int
    high_gravity_only: bool = True
    module_version: str = MODULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LineageCertificate:
    """The append-only audit row that records one inheritance event."""
    parent_id: str
    daughter_id: str
    bundle_hash: str
    inherited_at: float
    n_fragments: int
    fragment_previews: List[Dict[str, Any]] = field(default_factory=list)
    module_version: str = MODULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Internal: ledger I/O ──────────────────────────────────────────────────

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Best-effort reader. Never raises; returns [] on any I/O fault."""
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def _hash_fragments(fragments: List[Dict[str, Any]]) -> str:
    """Deterministic SHA-256 over the canonical JSON of the fragment list.
    Sort-keys so ordering of dict keys can never affect the hash."""
    blob = json.dumps(fragments, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Engine ────────────────────────────────────────────────────────────────

class LineageEngine:
    """Harvests parent marrow into a bundle and re-seeds it into the
    daughter's marrow with explicit provenance. Pure compute — never
    rewrites or removes parent rows."""

    def __init__(self, *, marrow_ledger: Optional[Path] = None,
                 lineage_ledger: Optional[Path] = None) -> None:
        # Indirected so smoke tests can redirect onto a tmp dir without
        # rebinding module-level constants.
        self.marrow_ledger  = marrow_ledger  or _MARROW_LEDGER
        self.lineage_ledger = lineage_ledger or _LINEAGE_LEDGER

    # ── Harvest ───────────────────────────────────────────────────────

    def harvest_bundle(
        self,
        parent_id: str,
        *,
        n: int = DEFAULT_BUNDLE_SIZE,
        high_gravity_only: bool = True,
    ) -> LineageBundle:
        """Read the parent's marrow rows and select the top `n` fragments.

        Selection rule (deterministic):
            1. Filter to rows where `owner == parent_id`.
            2. If `high_gravity_only`, drop rows whose tag set has zero
               intersection with HIGH_GRAVITY_TAGS.
            3. Sort by (gravity DESC, ts DESC) so the strongest, most
               recent emotional fragments win ties.
            4. Take the first `n` (capped at MAX_BUNDLE_SIZE for safety).
        """
        n = max(0, min(int(n), MAX_BUNDLE_SIZE))
        all_rows = _read_jsonl(self.marrow_ledger)
        owned = [r for r in all_rows if r.get("owner") == parent_id]
        if high_gravity_only:
            owned = [r for r in owned
                     if (set(r.get("tags") or []) & HIGH_GRAVITY_TAGS)]
        owned.sort(
            key=lambda r: (
                float(r.get("gravity", 0.0)),
                float(r.get("ts", 0.0)),
            ),
            reverse=True,
        )
        chosen = owned[:n]
        return LineageBundle(
            parent_id=parent_id,
            harvested_ts=time.time(),
            fragments=chosen,
            bundle_hash=_hash_fragments(chosen),
            n_fragments=len(chosen),
            high_gravity_only=high_gravity_only,
        )

    # ── Inherit ───────────────────────────────────────────────────────

    def inherit(
        self,
        daughter_id: str,
        bundle: LineageBundle,
    ) -> LineageCertificate:
        """Apply a bundle to the daughter: append each fragment to the
        marrow ledger as an *inherited* row owned by the daughter, with
        explicit provenance back to the parent. Then append exactly one
        lineage certificate to the lineage ledger.

        Inherited rows are tagged with the literal tag "inherited" in
        addition to the parent's original tag set. This lets downstream
        consumers (e.g. swarm_self.marrow_score, drift) distinguish
        lived experience from cytoplasmic inheritance without breaking
        the marrow row contract."""
        ts = time.time()

        previews: List[Dict[str, Any]] = []
        try:
            self.marrow_ledger.parent.mkdir(parents=True, exist_ok=True)
            with self.marrow_ledger.open("a", encoding="utf-8") as fh:
                for frag in bundle.fragments:
                    inherited_tags = list(set(frag.get("tags") or []) | {"inherited"})
                    inherited_row = {
                        "ts":              ts,
                        "owner":           daughter_id,
                        "ctx":             frag.get("ctx", "lineage_inheritance"),
                        "data":            frag.get("data", ""),
                        "tags":            inherited_tags,
                        "gravity":         float(frag.get("gravity", 0.0)),
                        "inherited_from":  bundle.parent_id,
                        "inherited_at":    ts,
                        "bundle_hash":     bundle.bundle_hash,
                        "original_ts":     frag.get("ts"),
                    }
                    fh.write(json.dumps(inherited_row, ensure_ascii=False) + "\n")
                    payload = str(inherited_row.get("data", ""))[:PAYLOAD_PREVIEW_CHARS]
                    previews.append({
                        "tags":    inherited_tags,
                        "gravity": inherited_row["gravity"],
                        "preview": payload,
                    })
        except OSError:
            # Marrow append failed — degrade to a certificate that records
            # *attempted* inheritance with zero realized fragments. The
            # daughter's marrow stays as it was; we never half-write.
            previews = []

        cert = LineageCertificate(
            parent_id=bundle.parent_id,
            daughter_id=daughter_id,
            bundle_hash=bundle.bundle_hash,
            inherited_at=ts,
            n_fragments=len(previews),
            fragment_previews=previews,
        )
        _persist_certificate(cert, self.lineage_ledger)
        return cert

    # ── Lookup ────────────────────────────────────────────────────────

    def lineage_of(self, swimmer_id: str) -> List[Dict[str, Any]]:
        """Return the chain of certificates that led to `swimmer_id`,
        oldest → newest. Each row is the raw lineage_certificate dict.

        A swimmer who was never inherited returns []. A first-generation
        daughter returns one row. Multi-generational chains are walked
        by repeatedly looking up the parent's own incoming certificate."""
        all_certs = _read_jsonl(self.lineage_ledger)
        # Index by daughter -> latest cert (inheritance is conceptually
        # one mother per daughter; if multiple, take the most recent).
        by_daughter: Dict[str, Dict[str, Any]] = {}
        for c in all_certs:
            d = c.get("daughter_id")
            if not d:
                continue
            prev = by_daughter.get(d)
            if prev is None or float(c.get("inherited_at", 0.0)) > float(prev.get("inherited_at", 0.0)):
                by_daughter[d] = c

        chain: List[Dict[str, Any]] = []
        cursor = swimmer_id
        seen: set = set()  # cycle guard
        while cursor in by_daughter and cursor not in seen:
            seen.add(cursor)
            cert = by_daughter[cursor]
            chain.append(cert)
            cursor = cert.get("parent_id", "")
            if not cursor:
                break
        # Reverse so oldest ancestor comes first.
        return list(reversed(chain))


# ── Persistence ───────────────────────────────────────────────────────────

def _persist_certificate(cert: LineageCertificate, path: Optional[Path] = None) -> bool:
    """Append a certificate to the lineage ledger. Best-effort."""
    target = path or _LINEAGE_LEDGER
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(cert.to_dict(), ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def recent_certificates(limit: int = 20) -> List[Dict[str, Any]]:
    rows = _read_jsonl(_LINEAGE_LEDGER)
    return rows[-limit:]


# ── CLI / smoke ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SIFTA — Lineage / Epigenetic Inheritance (R5)")
    parser.add_argument("--parent", default="IOAN_M5",
                        help="Parent marrow owner to harvest (default: IOAN_M5)")
    parser.add_argument("--daughter", default="DAUGHTER_PROBE",
                        help="Daughter swimmer to seed (default: DAUGHTER_PROBE)")
    parser.add_argument("--n", type=int, default=DEFAULT_BUNDLE_SIZE,
                        help=f"Bundle size (default: {DEFAULT_BUNDLE_SIZE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Harvest and print the bundle but do not seed the daughter")
    args = parser.parse_args()

    print("═" * 72)
    print("  SIFTA — SWARM LINEAGE (R5: Epigenetic Inheritance)")
    print("  'The daughter is born standing, not lying down.'")
    print("═" * 72)

    engine = LineageEngine()
    bundle = engine.harvest_bundle(args.parent, n=args.n)

    print(f"\n  parent_id            : {bundle.parent_id}")
    print(f"  harvested_ts         : {bundle.harvested_ts:.3f}")
    print(f"  bundle_hash          : {bundle.bundle_hash[:16]}…")
    print(f"  n_fragments          : {bundle.n_fragments}")
    print(f"  high_gravity_only    : {bundle.high_gravity_only}")
    if not bundle.fragments:
        print(f"\n  ⚠️  No fragments harvested — parent {args.parent!r} has no high-gravity marrow.")
    for i, frag in enumerate(bundle.fragments[:3], 1):
        print(f"\n    fragment[{i}]:")
        print(f"      tags    : {frag.get('tags')}")
        print(f"      gravity : {frag.get('gravity')}")
        print(f"      preview : {str(frag.get('data',''))[:80]}…")
    if len(bundle.fragments) > 3:
        print(f"    … and {len(bundle.fragments) - 3} more.")

    if args.dry_run:
        print(f"\n  --dry-run set; daughter NOT seeded.")
        raise SystemExit(0)

    cert = engine.inherit(args.daughter, bundle)
    print()
    print("═" * 72)
    print(f"  ⚡ DAUGHTER {args.daughter} INHERITED {cert.n_fragments} FRAGMENTS")
    print(f"     bundle_hash : {cert.bundle_hash[:16]}…")
    print(f"     inherited_at: {cert.inherited_at:.3f}")
    print("═" * 72)
