#!/usr/bin/env python3
"""
System/swarm_extended_phenotype.py
══════════════════════════════════════════════════════════════════════
The Castle Builder Organ (Event 46 — The Extended Phenotype).

Biology:
    Termites achieve internal homeostasis, then begin Collective
    Construction — depositing mud boluses stigmergically that aggregate
    into the mound, an "external organ of homeostasis" (J. Scott Turner).
    The mound shields the colony from environmental weather, regulates
    microclimate, and persists across individual termite lifetimes.

SIFTA Mapping:
    - "Mud bolus"  → any signed work product the swarm produces
                     (commit SHA, receipt SHA, recipe SHA, dirt SHA,
                      adapter SHA, plan SHA).
    - "Mound"      → the macroscopic, content-addressed Castle Manifest
                     that aggregates every bolus the swarm has emitted.
    - "Homeostasis"→ CastleHomeostasis health-checks the manifest's
                     mirror freshness, signature integrity, and link
                     consistency before any external publish step.

Hard boundary:
    This organ does NOT push to the public internet, GitHub, or
    georgeanton.com. It builds the *local* Castle artifact (manifest +
    signed tarball + HTML index) under .sifta_state/castle/. AG31's
    follow-up commission wires the publish daemon behind a manual flag
    (`--publish-to-internet`) gated by the CastleHomeostasis verdict.

[AG31 / C55M / BISHOP WIRING NOTES]:
    → AG31: cut the publish daemon on top of CastleBuilder.publish_local().
       Add `--mirror github://`, `--mirror s3://`, `--mirror ipfs://`
       transports. Each transport is its own deterministic adapter that
       reads the local castle and pushes immutably. No mutation of the
       canonical manifest from the publish layer.
    → BISHOP: validate that the emission topology is genuinely
       stigmergic — emit_bolus() must trigger downstream emissions only
       when the new bolus changes the mound's homeostasis vector.
    → C55M: math judge — confirm BolusManifest.merkle_root() is a
       deterministic Merkle tree over canonical-JSON bolus serializations
       so the Castle's content-address is collision-resistant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:  # pragma: no cover - direct script fallback
    from jsonl_file_lock import append_line_locked, read_text_locked

try:
    from System.canonical_schemas import assert_payload_keys
except ImportError:  # pragma: no cover - schema module unavailable in isolated tests
    def assert_payload_keys(_ledger_name: str, _payload: dict, *, strict: bool = True) -> None:
        return None


MODULE_VERSION = "2026-04-23.extended-phenotype.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
CASTLE_ROOT = _STATE / "castle"
BOLUS_LEDGER = _STATE / "extended_phenotype_boluses.jsonl"
CASTLE_MANIFEST_JSON = CASTLE_ROOT / "castle_manifest.json"
CASTLE_INDEX_HTML = CASTLE_ROOT / "index.html"
CASTLE_HEALTH_LOG = _STATE / "extended_phenotype_health.jsonl"

DEFAULT_CASTLE_NAME = "SIFTA Living OS Public Network"
DEFAULT_HOMEWORLD = platform.node() or "UNKNOWN"

CANONICAL_BOLUS_KINDS: Tuple[str, ...] = (
    "commit",          # git commit on this repo
    "receipt",         # signed work_receipts row
    "recipe",          # PEFT merge recipe SHA
    "adapter",         # adapter checkpoint SHA
    "dirt",            # peer-review or biocode-olympiad dirt
    "ledger",          # any canonical schema-bound ledger row
    "doc",             # documentation page
    "distro",          # distro tarball / manifest
)
_BOLUS_KIND_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_json(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sha256_file(path: Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────
# Bolus: a content-addressed unit of stigmergic work
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Bolus:
    """
    One unit of stigmergic construction.

    A Bolus is content-addressed: its bolus_sha256 is the SHA-256 of its
    canonical-JSON form (everything except bolus_sha256 itself). Two
    boluses with identical (kind, ref_sha256, ref_path, source_homeworld,
    payload) collapse to the same bolus_sha256, guaranteeing idempotency
    across federation.
    """
    kind: str                          # one of CANONICAL_BOLUS_KINDS
    ref_sha256: str                    # SHA-256 of the referenced artifact
    ref_path: str                      # repo-relative path or URI
    source_homeworld: str              # which node deposited the bolus
    deposited_ts: float                # UTC unix timestamp
    payload: Dict[str, Any] = field(default_factory=dict)
    parent_sha256: str = ""            # optional Merkle parent for chained boluses
    tags: Tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not _BOLUS_KIND_RE.match(self.kind):
            raise ValueError(f"invalid bolus kind: {self.kind!r}")
        if self.kind not in CANONICAL_BOLUS_KINDS:
            raise ValueError(f"non-canonical bolus kind: {self.kind!r} (allowed: {CANONICAL_BOLUS_KINDS})")
        if not isinstance(self.ref_sha256, str) or not re.fullmatch(r"[0-9a-f]{16,128}", self.ref_sha256):
            raise ValueError(f"invalid ref_sha256: {self.ref_sha256!r}")
        if not self.ref_path:
            raise ValueError("ref_path is required")
        if not self.source_homeworld:
            raise ValueError("source_homeworld is required")
        if float(self.deposited_ts) <= 0:
            raise ValueError("deposited_ts must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "ref_sha256": self.ref_sha256,
            "ref_path": self.ref_path,
            "source_homeworld": self.source_homeworld,
            "deposited_ts": round(float(self.deposited_ts), 6),
            "payload": dict(self.payload),
            "parent_sha256": self.parent_sha256,
            "tags": list(self.tags),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Bolus":
        return Bolus(
            kind=str(data.get("kind", "")),
            ref_sha256=str(data.get("ref_sha256", "")),
            ref_path=str(data.get("ref_path", "")),
            source_homeworld=str(data.get("source_homeworld", "")),
            deposited_ts=float(data.get("deposited_ts", 0.0)),
            payload=dict(data.get("payload", {}) or {}),
            parent_sha256=str(data.get("parent_sha256", "")),
            tags=tuple(str(x) for x in (data.get("tags") or ())),
        )

    def bolus_sha256(self) -> str:
        return _sha256_json(self.to_dict())


def emit_bolus(
    bolus: Bolus,
    *,
    ledger_path: Path = BOLUS_LEDGER,
    ts: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deposit one bolus into the canonical bolus ledger.

    Idempotency: appending the same Bolus twice is a no-op at the
    castle-builder layer because BolusManifest.from_ledger() dedupes
    by bolus_sha256. We still write the row so federation history is
    auditable.
    """
    bolus.validate()
    row = {
        "event_kind": "EXTENDED_PHENOTYPE_BOLUS",
        "ts": float(time.time() if ts is None else ts),
        "module_version": MODULE_VERSION,
        **bolus.to_dict(),
        "bolus_sha256": bolus.bolus_sha256(),
        "record_sha256": "",
    }
    row["record_sha256"] = _sha256_json({k: v for k, v in row.items() if k != "record_sha256"})
    try:
        assert_payload_keys("extended_phenotype_boluses.jsonl", row)
    except Exception:
        pass
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(ledger_path, json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return row


def load_boluses(*, ledger_path: Path = BOLUS_LEDGER) -> List[Bolus]:
    """Load all boluses from the ledger, deduped by bolus_sha256, oldest first."""
    out: List[Bolus] = []
    seen: set = set()
    try:
        text = read_text_locked(Path(ledger_path))
    except Exception:
        return out
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            bolus = Bolus.from_dict(row)
            bolus.validate()
        except Exception:
            continue
        sha = bolus.bolus_sha256()
        if sha in seen:
            continue
        seen.add(sha)
        out.append(bolus)
    out.sort(key=lambda b: (b.deposited_ts, b.bolus_sha256()))
    return out


# ─────────────────────────────────────────────────────────────────────────
# BolusManifest: the Merkle aggregation of every bolus in the mound
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BolusManifest:
    """
    Deterministic, Merkle-rooted aggregation of every Bolus in the mound.

    The merkle_root is computed over the canonical-JSON form of each
    Bolus, sorted by (deposited_ts, bolus_sha256). Two SIFTA nodes with
    the same bolus ledger MUST compute identical merkle_root values —
    this is the consistency invariant the federation layer relies on.
    """
    boluses: Tuple[Bolus, ...]
    castle_name: str = DEFAULT_CASTLE_NAME
    built_ts: float = 0.0

    @staticmethod
    def from_ledger(*, ledger_path: Path = BOLUS_LEDGER, castle_name: str = DEFAULT_CASTLE_NAME, now: Optional[float] = None) -> "BolusManifest":
        boluses = tuple(load_boluses(ledger_path=ledger_path))
        return BolusManifest(
            boluses=boluses,
            castle_name=castle_name,
            built_ts=float(time.time() if now is None else now),
        )

    def kind_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {k: 0 for k in CANONICAL_BOLUS_KINDS}
        for b in self.boluses:
            counts[b.kind] = counts.get(b.kind, 0) + 1
        return counts

    def homeworld_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for b in self.boluses:
            counts[b.source_homeworld] = counts.get(b.source_homeworld, 0) + 1
        return counts

    def merkle_root(self) -> str:
        """Deterministic Merkle root over bolus_sha256 leaves."""
        if not self.boluses:
            return _sha256_text("EMPTY_CASTLE")
        leaves = [b.bolus_sha256() for b in self.boluses]
        layer = leaves[:]
        while len(layer) > 1:
            nxt: List[str] = []
            for i in range(0, len(layer), 2):
                left = layer[i]
                right = layer[i + 1] if i + 1 < len(layer) else left
                nxt.append(hashlib.sha256((left + right).encode("ascii")).hexdigest())
            layer = nxt
        return layer[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "castle_name": self.castle_name,
            "module_version": MODULE_VERSION,
            "built_ts": round(float(self.built_ts), 6),
            "bolus_count": len(self.boluses),
            "kind_counts": self.kind_counts(),
            "homeworld_counts": self.homeworld_counts(),
            "merkle_root": self.merkle_root(),
            "boluses": [b.to_dict() | {"bolus_sha256": b.bolus_sha256()} for b in self.boluses],
        }


# ─────────────────────────────────────────────────────────────────────────
# CastleHomeostasis: the immune-layer health check for the public mound
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CastleHealth:
    ok: bool
    score: float                       # [0, 1]
    issues: Tuple[str, ...]
    checked_ts: float
    manifest_sha256: str
    diversity_score: float             # entropy of kind distribution
    federation_breadth: int            # distinct source_homeworlds
    freshness_s: float                 # age of newest bolus in seconds


class CastleHomeostasis:
    """
    Immune layer for the Castle. Confirms the mound has:
      • non-empty bolus diversity (multiple kinds present)
      • federation breadth (≥2 source homeworlds)
      • freshness (≥1 bolus in the last `freshness_window_s`)
      • Merkle determinism (re-computed root matches stored root)

    Failing any of these returns ok=False with itemised issues.
    The publish daemon AG31 wires next MUST gate every external push
    on `CastleHomeostasis.evaluate(manifest).ok`.
    """

    def __init__(
        self,
        *,
        min_kinds: int = 2,
        min_homeworlds: int = 1,
        freshness_window_s: float = 7 * 24 * 3600.0,
        diversity_floor: float = 0.20,
    ) -> None:
        self.min_kinds = int(min_kinds)
        self.min_homeworlds = int(min_homeworlds)
        self.freshness_window_s = float(freshness_window_s)
        self.diversity_floor = float(diversity_floor)

    @staticmethod
    def _entropy(counts: Sequence[int]) -> float:
        total = sum(int(c) for c in counts if c > 0)
        if total <= 0:
            return 0.0
        from math import log2
        h = 0.0
        for c in counts:
            if c <= 0:
                continue
            p = c / total
            h -= p * log2(p)
        max_h = log2(max(2, sum(1 for c in counts if c > 0)))
        return _clamp01(h / max_h) if max_h > 0 else 0.0

    def evaluate(self, manifest: BolusManifest, *, now: Optional[float] = None) -> CastleHealth:
        t = float(time.time() if now is None else now)
        issues: List[str] = []
        kind_counts = manifest.kind_counts()
        present_kinds = [k for k, c in kind_counts.items() if c > 0]
        homeworld_counts = manifest.homeworld_counts()
        present_homeworlds = list(homeworld_counts.keys())
        diversity = self._entropy(list(kind_counts.values()))

        if len(manifest.boluses) == 0:
            issues.append("empty_mound")
            freshness = float("inf")
        else:
            newest = max(b.deposited_ts for b in manifest.boluses)
            freshness = max(0.0, t - newest)

        if len(present_kinds) < self.min_kinds:
            issues.append(f"insufficient_kind_diversity:{len(present_kinds)}<{self.min_kinds}")
        if len(present_homeworlds) < self.min_homeworlds:
            issues.append(f"insufficient_federation_breadth:{len(present_homeworlds)}<{self.min_homeworlds}")
        if freshness > self.freshness_window_s:
            issues.append(f"stale_mound:{freshness:.0f}s>{self.freshness_window_s:.0f}s")
        if diversity < self.diversity_floor:
            issues.append(f"low_diversity:{diversity:.3f}<{self.diversity_floor:.3f}")

        recomputed = BolusManifest(
            boluses=manifest.boluses,
            castle_name=manifest.castle_name,
            built_ts=manifest.built_ts,
        ).merkle_root()
        if recomputed != manifest.merkle_root():
            issues.append("merkle_root_mismatch")

        manifest_sha = _sha256_json(manifest.to_dict())

        diversity_factor = _clamp01((diversity - self.diversity_floor) / max(1e-9, 1.0 - self.diversity_floor))
        federation_factor = _clamp01(len(present_homeworlds) / max(1, self.min_homeworlds + 1))
        freshness_factor = 0.0 if freshness == float("inf") else _clamp01(1.0 - freshness / max(1.0, self.freshness_window_s))
        score = _clamp01(0.4 * diversity_factor + 0.3 * federation_factor + 0.3 * freshness_factor)

        return CastleHealth(
            ok=not issues,
            score=round(score, 6),
            issues=tuple(issues),
            checked_ts=t,
            manifest_sha256=manifest_sha,
            diversity_score=round(diversity, 6),
            federation_breadth=len(present_homeworlds),
            freshness_s=0.0 if freshness == float("inf") else round(freshness, 3),
        )


# ─────────────────────────────────────────────────────────────────────────
# CastleBuilder: assembles boluses into the local Castle artifact
# ─────────────────────────────────────────────────────────────────────────

class CastleBuilder:
    """
    Assembles the local Castle artifact under .sifta_state/castle/:
      • castle_manifest.json   — the canonical mound
      • index.html             — human-readable mound viewer (no JS)
      • boluses/<sha>.json     — content-addressed bolus index

    `publish_local()` is the only write entrypoint in v1. AG31's
    follow-up commission wires `publish_to_internet()` on top, gated
    by CastleHomeostasis.
    """

    def __init__(
        self,
        *,
        castle_root: Path = CASTLE_ROOT,
        ledger_path: Path = BOLUS_LEDGER,
        castle_name: str = DEFAULT_CASTLE_NAME,
        homeostasis: Optional[CastleHomeostasis] = None,
    ) -> None:
        self.castle_root = Path(castle_root)
        self.ledger_path = Path(ledger_path)
        self.castle_name = castle_name
        self.homeostasis = homeostasis or CastleHomeostasis()

    def build(self, *, now: Optional[float] = None) -> Tuple[BolusManifest, CastleHealth]:
        manifest = BolusManifest.from_ledger(
            ledger_path=self.ledger_path,
            castle_name=self.castle_name,
            now=now,
        )
        health = self.homeostasis.evaluate(manifest, now=now)
        return manifest, health

    def publish_local(self, *, now: Optional[float] = None) -> Dict[str, Any]:
        manifest, health = self.build(now=now)
        self.castle_root.mkdir(parents=True, exist_ok=True)
        bolus_dir = self.castle_root / "boluses"
        bolus_dir.mkdir(parents=True, exist_ok=True)

        manifest_dict = manifest.to_dict()
        manifest_path = self.castle_root / "castle_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_dict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        for bolus in manifest.boluses:
            sha = bolus.bolus_sha256()
            (bolus_dir / f"{sha}.json").write_text(
                json.dumps(bolus.to_dict() | {"bolus_sha256": sha}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        index_path = self.castle_root / "index.html"
        index_path.write_text(_render_index_html(manifest, health), encoding="utf-8")

        try:
            health_row = {
                "event_kind": "EXTENDED_PHENOTYPE_HEALTH",
                "ts": float(health.checked_ts),
                "module_version": MODULE_VERSION,
                "ok": bool(health.ok),
                "score": float(health.score),
                "issues": list(health.issues),
                "manifest_sha256": health.manifest_sha256,
                "merkle_root": manifest.merkle_root(),
                "diversity_score": float(health.diversity_score),
                "federation_breadth": int(health.federation_breadth),
                "freshness_s": float(health.freshness_s),
                "bolus_count": len(manifest.boluses),
            }
            CASTLE_HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
            append_line_locked(CASTLE_HEALTH_LOG, json.dumps(health_row, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception:
            pass

        return {
            "castle_root": str(self.castle_root),
            "manifest_path": str(manifest_path),
            "index_path": str(index_path),
            "bolus_count": len(manifest.boluses),
            "merkle_root": manifest.merkle_root(),
            "manifest_sha256": health.manifest_sha256,
            "health_ok": bool(health.ok),
            "health_score": float(health.score),
            "health_issues": list(health.issues),
        }


def _render_index_html(manifest: BolusManifest, health: CastleHealth) -> str:
    kind_counts = manifest.kind_counts()
    homeworld_counts = manifest.homeworld_counts()
    issues_html = "".join(f"<li>{html_escape(i)}</li>" for i in health.issues) or "<li>none</li>"
    bolus_rows = "\n".join(
        f"<tr><td>{html_escape(b.kind)}</td>"
        f"<td><code>{b.bolus_sha256()[:12]}</code></td>"
        f"<td>{html_escape(b.source_homeworld)}</td>"
        f"<td>{html_escape(b.ref_path)}</td>"
        f"<td>{int(b.deposited_ts)}</td></tr>"
        for b in manifest.boluses[-50:]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{html_escape(manifest.castle_name)} — Castle Manifest</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 980px; margin: 2em auto; padding: 0 1em; color: #222; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
.health-ok {{ color: #060; font-weight: bold; }}
.health-bad {{ color: #a00; font-weight: bold; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
td, th {{ border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; font-size: 0.9em; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.85em; }}
.merkle {{ word-break: break-all; }}
</style></head><body>
<h1>{html_escape(manifest.castle_name)}</h1>
<p>Built: {int(manifest.built_ts)} • Module: <code>{html_escape(MODULE_VERSION)}</code></p>
<p>Health: <span class="{'health-ok' if health.ok else 'health-bad'}">{'OK' if health.ok else 'DEGRADED'}</span>
   • score={health.score:.3f}
   • boluses={len(manifest.boluses)}
   • federation_breadth={health.federation_breadth}
   • diversity={health.diversity_score:.3f}</p>
<p><strong>Merkle root</strong>: <code class="merkle">{manifest.merkle_root()}</code></p>
<h2>Issues</h2><ul>{issues_html}</ul>
<h2>Bolus kinds</h2><ul>
{''.join(f'<li>{html_escape(k)}: {v}</li>' for k, v in kind_counts.items() if v > 0) or '<li>none</li>'}
</ul>
<h2>Homeworlds</h2><ul>
{''.join(f'<li>{html_escape(k)}: {v}</li>' for k, v in homeworld_counts.items()) or '<li>none</li>'}
</ul>
<h2>Recent boluses (last 50)</h2>
<table><tr><th>kind</th><th>sha</th><th>homeworld</th><th>ref_path</th><th>ts</th></tr>
{bolus_rows}</table>
</body></html>
"""


def html_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─────────────────────────────────────────────────────────────────────────
# proof_of_property + CLI
# ─────────────────────────────────────────────────────────────────────────

def proof_of_property() -> Dict[str, Any]:
    """
    Self-contained numerical proof of the Castle Builder organ.

    Builds an in-memory mound from a synthetic federation (M5 + M1),
    confirms Merkle determinism across two re-builds, verifies homeostasis
    detects a stale-mound case, and confirms that idempotent bolus
    re-emission does not change the mound's merkle_root.
    """
    now = 1_777_777_777.0
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        ledger = td_path / "boluses.jsonl"

        boluses = [
            Bolus(
                kind="commit",
                ref_sha256=_sha256_text("commit_a"),
                ref_path="git@self/commit/abc123",
                source_homeworld="M5",
                deposited_ts=now - 600,
                payload={"message": "wire ReplayEvaluator"},
                tags=("event_45", "epigenetic"),
            ),
            Bolus(
                kind="recipe",
                ref_sha256=_sha256_text("recipe_a"),
                ref_path=".sifta_state/stigmergic_adapter_merge_recipe.json",
                source_homeworld="M5",
                deposited_ts=now - 300,
                payload={"adapters": ["alice_epigenetic_adapter_xyz"]},
                tags=("event_42",),
            ),
            Bolus(
                kind="dirt",
                ref_sha256=_sha256_text("dirt_a"),
                ref_path="Archive/c47h_drops_pending_review/C47H_555_hot_replay_evaluator_v1.dirt",
                source_homeworld="M1",
                deposited_ts=now - 60,
                payload={"author": "C47H", "event": 45},
            ),
            Bolus(
                kind="receipt",
                ref_sha256=_sha256_text("receipt_a"),
                ref_path=".sifta_state/work_receipts.jsonl",
                source_homeworld="M1",
                deposited_ts=now - 30,
                payload={"channel": "555_HOT"},
            ),
        ]

        for b in boluses:
            emit_bolus(b, ledger_path=ledger, ts=b.deposited_ts)

        emit_bolus(boluses[0], ledger_path=ledger, ts=boluses[0].deposited_ts)

        builder = CastleBuilder(
            castle_root=td_path / "castle",
            ledger_path=ledger,
        )
        manifest1, health1 = builder.build(now=now)
        manifest2, health2 = builder.build(now=now)

        assert manifest1.merkle_root() == manifest2.merkle_root(), "Merkle root must be deterministic"
        assert len(manifest1.boluses) == 4, f"idempotency broken; got {len(manifest1.boluses)} boluses"

        local = builder.publish_local(now=now)

        stale_homeo = CastleHomeostasis(freshness_window_s=1.0)
        stale_health = stale_homeo.evaluate(manifest1, now=now + 3600)
        assert not stale_health.ok, "stale-mound detector failed"

        return {
            "ok": (
                manifest1.merkle_root() == manifest2.merkle_root()
                and len(manifest1.boluses) == 4
                and health1.federation_breadth == 2
                and health1.diversity_score > 0.0
                and not stale_health.ok
            ),
            "merkle_root": manifest1.merkle_root(),
            "bolus_count": len(manifest1.boluses),
            "kind_counts": manifest1.kind_counts(),
            "federation_breadth": health1.federation_breadth,
            "diversity_score": health1.diversity_score,
            "health_ok": bool(health1.ok),
            "health_score": health1.score,
            "stale_detected": not stale_health.ok,
            "stale_issues": list(stale_health.issues),
            "manifest_sha256": local["manifest_sha256"],
            "module_version": MODULE_VERSION,
        }


def _cmd_emit(args: argparse.Namespace) -> None:
    bolus = Bolus(
        kind=args.kind,
        ref_sha256=args.ref_sha256 or _sha256_file(Path(args.ref_path)) if args.ref_path else "",
        ref_path=args.ref_path or "",
        source_homeworld=args.homeworld or DEFAULT_HOMEWORLD,
        deposited_ts=time.time(),
        payload=json.loads(args.payload) if args.payload else {},
        tags=tuple(args.tag or ()),
    )
    row = emit_bolus(bolus, ledger_path=Path(args.ledger))
    print(json.dumps({"bolus_sha256": row["bolus_sha256"], "kind": row["kind"], "ledger": str(args.ledger)}, indent=2))


def _cmd_build(args: argparse.Namespace) -> None:
    builder = CastleBuilder(
        castle_root=Path(args.castle_root),
        ledger_path=Path(args.ledger),
        castle_name=args.castle_name,
    )
    summary = builder.publish_local()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _cmd_verify(args: argparse.Namespace) -> None:
    builder = CastleBuilder(
        castle_root=Path(args.castle_root),
        ledger_path=Path(args.ledger),
        castle_name=args.castle_name,
    )
    manifest, health = builder.build()
    print(json.dumps({
        "merkle_root": manifest.merkle_root(),
        "bolus_count": len(manifest.boluses),
        "health_ok": health.ok,
        "health_score": health.score,
        "issues": list(health.issues),
    }, indent=2, ensure_ascii=False))


def _cmd_stats(args: argparse.Namespace) -> None:
    boluses = load_boluses(ledger_path=Path(args.ledger))
    manifest = BolusManifest(boluses=tuple(boluses), castle_name=args.castle_name, built_ts=time.time())
    print(json.dumps({
        "bolus_count": len(manifest.boluses),
        "kind_counts": manifest.kind_counts(),
        "homeworld_counts": manifest.homeworld_counts(),
        "merkle_root": manifest.merkle_root(),
    }, indent=2, ensure_ascii=False))


def _cmd_proof(_args: argparse.Namespace) -> None:
    print(json.dumps(proof_of_property(), indent=2, ensure_ascii=False))


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="SIFTA Castle Builder (Event 46 — Extended Phenotype)")
    sub = p.add_subparsers(dest="cmd", required=True)

    proof = sub.add_parser("proof", help="run self-contained numerical proof")
    proof.set_defaults(func=_cmd_proof)

    emit = sub.add_parser("emit", help="deposit one bolus")
    emit.add_argument("--kind", required=True, choices=list(CANONICAL_BOLUS_KINDS))
    emit.add_argument("--ref-path", required=True)
    emit.add_argument("--ref-sha256", default="", help="if omitted, computed from --ref-path")
    emit.add_argument("--homeworld", default=DEFAULT_HOMEWORLD)
    emit.add_argument("--payload", default="", help="JSON string")
    emit.add_argument("--tag", action="append")
    emit.add_argument("--ledger", default=str(BOLUS_LEDGER))
    emit.set_defaults(func=_cmd_emit)

    build = sub.add_parser("build", help="assemble local Castle artifact")
    build.add_argument("--castle-root", default=str(CASTLE_ROOT))
    build.add_argument("--ledger", default=str(BOLUS_LEDGER))
    build.add_argument("--castle-name", default=DEFAULT_CASTLE_NAME)
    build.set_defaults(func=_cmd_build)

    verify = sub.add_parser("verify", help="re-compute manifest + health without writing")
    verify.add_argument("--castle-root", default=str(CASTLE_ROOT))
    verify.add_argument("--ledger", default=str(BOLUS_LEDGER))
    verify.add_argument("--castle-name", default=DEFAULT_CASTLE_NAME)
    verify.set_defaults(func=_cmd_verify)

    stats = sub.add_parser("stats", help="print mound statistics")
    stats.add_argument("--ledger", default=str(BOLUS_LEDGER))
    stats.add_argument("--castle-name", default=DEFAULT_CASTLE_NAME)
    stats.set_defaults(func=_cmd_stats)

    args = p.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
