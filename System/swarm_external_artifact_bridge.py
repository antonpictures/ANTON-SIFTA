#!/usr/bin/env python3
"""swarm_external_artifact_bridge.py — labeled-substrate artifact intake.

Architect 2026-05-14: "I tried to load Grok — he has tools." The
covenant answer (§3 federation + §6 social frame + §7.5 second-OS
discipline + §8.6 absorption policy): browser-tab tools (Grok,
ChatGPT custom GPTs, Claude.ai) can produce docs / decks / sheets,
but those artifacts only enter SIFTA's body through a proof-bearing
import lane. They get a provenance row, a sha256 fingerprint, and a
substrate badge — so Alice can answer "which brain wrote this?" with
a signed receipt instead of vibes.

This module is that lane:

  1. Drop file into Documents/from_external/
     (optionally with a sidecar `<file>.meta.json` describing source/URL)
  2. Run `python3 System/swarm_external_artifact_bridge.py --scan`
     OR Talk-to-Alice "Refresh imports" button
  3. New files get a sha256 + provenance row in
     .sifta_state/external_artifact_imports.jsonl
  4. Already-imported files (matched by sha256) are skipped
     idempotently — re-running scan does NOT duplicate.

Source inference order:
  1. Sidecar `<file>.meta.json` with `{"source": "grok", "url": "..."}`
  2. Filename hint: `grok_*` → grok, `swarmgpt_*` → chatgpt:swarm-gpt,
     `claude_*` → claude, `gemini_*` → gemini
  3. Default: "external_unknown"

Truth label: EXTERNAL_ARTIFACT_IMPORT_V1.
Truth class: OPERATIONAL — every row carries an sha256 of the file
contents at import time. Tampered files would not match their
recorded sha256 on re-scan.

§6 social-frame discipline: Alice may NOT claim she "called Grok" or
"ran ChatGPT". She may say "Grok produced X.docx at YYYY-MM-DD,
sha256=…" because the receipt proves it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DOCS = _REPO / "Documents"
_INBOX = _DOCS / "from_external"

LEDGER_NAME = "external_artifact_imports.jsonl"
TRUTH_LABEL = "EXTERNAL_ARTIFACT_IMPORT_V1"
TRUTH_BOUNDARY = (
    "Provenance lane for artifacts produced by external browser-tab "
    "substrates (Grok, ChatGPT custom GPTs, Claude.ai, Gemini, etc.). "
    "Each import row carries sha256 + source label + URL when known. "
    "Alice's organs may reference artifacts by sha256 fingerprint; she "
    "may NOT claim to have 'called' the external substrate herself "
    "(§6 social frame). §7.5 second-OS discipline: browser tabs are "
    "exceptional, not the primary body."
)

# File types we recognize. Anything else gets imported with file_type='other'.
SUPPORTED_SUFFIXES = frozenset({
    ".docx", ".pdf", ".pptx", ".xlsx", ".xlsm", ".csv", ".tsv",
    ".md", ".txt", ".html", ".json", ".jsonl", ".yaml", ".yml",
})

# Filename hint → canonical source label
_FILENAME_HINTS = (
    (re.compile(r"^grok[_\-]", re.I), "grok"),
    (re.compile(r"^chatgpt[_\-]", re.I), "chatgpt"),
    (re.compile(r"^swarmgpt[_\-]", re.I), "chatgpt:swarm-gpt"),
    (re.compile(r"^swarm[_\-]?gpt[_\-]", re.I), "chatgpt:swarm-gpt"),
    (re.compile(r"^claude[_\-]", re.I), "claude"),
    (re.compile(r"^gemini[_\-]", re.I), "gemini"),
    (re.compile(r"^gemma[_\-]", re.I), "gemma"),
    (re.compile(r"^perplexity[_\-]", re.I), "perplexity"),
    (re.compile(r"^anthropic[_\-]", re.I), "anthropic"),
    (re.compile(r"^codex[_\-]", re.I), "codex"),
    (re.compile(r"^mistral[_\-]", re.I), "mistral"),
)

# Canonical sources we recognize for cross-checking
KNOWN_SOURCES = frozenset({
    "grok", "chatgpt", "chatgpt:swarm-gpt", "claude", "gemini",
    "gemma", "perplexity", "anthropic", "codex", "mistral",
    "external_unknown",
})


# ──────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ImportRow:
    """One provenance row for an external artifact."""
    ts: float
    trace_id: str
    truth_label: str
    truth_class: str
    sha256: str
    file_name: str
    file_path: str
    file_type: str      # docx/pdf/pptx/xlsx/md/txt/other
    file_size_bytes: int
    source: str         # canonical substrate label
    url: Optional[str]
    notes: Optional[str]
    sidecar_seen: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Source inference
# ──────────────────────────────────────────────────────────────────────

def infer_source(
    file_path: Path,
    sidecar_meta: Optional[dict[str, Any]] = None,
) -> tuple[str, Optional[str], Optional[str], bool]:
    """Resolve the canonical source label.

    Returns (source, url, notes, sidecar_seen).

    Priority:
      1. Sidecar `<file>.meta.json` `source` field
      2. Filename hint (`grok_*`, `claude_*`, etc.)
      3. Fallback: "external_unknown"
    """
    if isinstance(sidecar_meta, dict):
        source = str(sidecar_meta.get("source", "")).strip().lower() or None
        url = sidecar_meta.get("url")
        notes = sidecar_meta.get("notes")
        if source:
            return source, url, notes, True
        # sidecar exists but missing source — still note url/notes
        if url or notes:
            return "external_unknown", url, notes, True
    # Filename hint
    name = file_path.name
    for rx, label in _FILENAME_HINTS:
        if rx.match(name):
            return label, None, None, False
    return "external_unknown", None, None, False


# ──────────────────────────────────────────────────────────────────────
# Core import
# ──────────────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_SUFFIXES:
        return suffix.lstrip(".")
    return "other"


def _load_sidecar(file_path: Path) -> Optional[dict[str, Any]]:
    """Look for `<file>.meta.json` next to `file_path`. Returns parsed
    dict or None."""
    sidecar = file_path.with_suffix(file_path.suffix + ".meta.json")
    if not sidecar.exists():
        sidecar = file_path.parent / (file_path.stem + ".meta.json")
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_existing_sha256s(
    state_root: str | Path | None = None,
) -> set[str]:
    """Return set of sha256s already in the ledger — for dedup."""
    state = Path(state_root) if state_root else _STATE
    ledger = state / LEDGER_NAME
    if not ledger.exists():
        return set()
    seen: set[str] = set()
    try:
        with ledger.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                sha = row.get("sha256") if isinstance(row, dict) else None
                if isinstance(sha, str) and len(sha) == 64:
                    seen.add(sha)
    except Exception:
        pass
    return seen


def import_one(
    file_path: str | Path,
    *,
    source: Optional[str] = None,
    url: Optional[str] = None,
    notes: Optional[str] = None,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Import a single artifact. Returns the row dict (or an error dict).

    Idempotent: if the file's sha256 is already in the ledger, returns
    the existing row data with `skipped=True`.
    """
    p = Path(file_path).resolve()
    if not p.exists() or not p.is_file():
        return {"ok": False, "reason": f"file not found: {p}"}
    state = Path(state_root) if state_root else _STATE
    sidecar = _load_sidecar(p)
    inferred_source, inferred_url, inferred_notes, sidecar_seen = infer_source(
        p, sidecar_meta=sidecar,
    )
    # Caller-provided values override inference
    final_source = (source or inferred_source).strip().lower()
    final_url = url or inferred_url
    final_notes = notes or inferred_notes
    sha = _sha256_file(p)
    # Dedup
    if sha in _load_existing_sha256s(state):
        return {
            "ok": True, "skipped": True, "sha256": sha,
            "reason": "already_imported",
            "file_name": p.name,
        }
    row = ImportRow(
        ts=time.time(),
        trace_id=str(uuid.uuid4()),
        truth_label=TRUTH_LABEL,
        truth_class="OPERATIONAL",
        sha256=sha,
        file_name=p.name,
        file_path=str(p),
        file_type=_file_type(p),
        file_size_bytes=p.stat().st_size,
        source=final_source,
        url=final_url,
        notes=final_notes,
        sidecar_seen=sidecar_seen,
    )
    if write:
        state.mkdir(parents=True, exist_ok=True)
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
    return {"ok": True, "skipped": False, **row.to_dict()}


def scan_folder(
    folder: str | Path | None = None,
    *,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Scan a folder for new artifacts and import each. Idempotent —
    files with sha256 already in the ledger are skipped.

    Returns a summary dict with counts + per-file results.
    """
    f = Path(folder) if folder else _INBOX
    if not f.exists():
        f.mkdir(parents=True, exist_ok=True)
    if not f.is_dir():
        return {"ok": False, "reason": f"not a directory: {f}"}
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errored: list[dict[str, Any]] = []
    for entry in sorted(f.iterdir()):
        if not entry.is_file():
            continue
        # Skip sidecar metadata files themselves
        if entry.name.endswith(".meta.json"):
            continue
        try:
            result = import_one(entry, state_root=state_root, write=write)
        except Exception as e:  # noqa: BLE001
            errored.append({"file": str(entry), "error": f"{type(e).__name__}: {e}"})
            continue
        if not result.get("ok"):
            errored.append({"file": str(entry), **result})
        elif result.get("skipped"):
            skipped.append(result)
        else:
            imported.append(result)
    return {
        "ok": True,
        "truth_label": TRUTH_LABEL,
        "folder": str(f),
        "n_imported": len(imported),
        "n_skipped": len(skipped),
        "n_errored": len(errored),
        "imported": imported,
        "skipped": skipped,
        "errored": errored,
    }


# ──────────────────────────────────────────────────────────────────────
# Read API for the Talk widget / cortex
# ──────────────────────────────────────────────────────────────────────

def list_recent_imports(
    *,
    state_root: str | Path | None = None,
    last_n: int = 5,
) -> list[dict[str, Any]]:
    """Return the last N import rows (most recent first), useful for
    surfacing in the Talk-to-Alice widget panel."""
    state = Path(state_root) if state_root else _STATE
    ledger = state / LEDGER_NAME
    if not ledger.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with ledger.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    return rows[:last_n]


def find_by_sha256(
    sha256_prefix: str,
    *,
    state_root: str | Path | None = None,
) -> Optional[dict[str, Any]]:
    """Find an import row by full or prefix sha256. Useful when Alice
    references an artifact by its fingerprint in conversation."""
    state = Path(state_root) if state_root else _STATE
    ledger = state / LEDGER_NAME
    if not ledger.exists() or not sha256_prefix:
        return None
    prefix = sha256_prefix.lower().strip()
    try:
        with ledger.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                sha = (row.get("sha256") or "").lower() if isinstance(row, dict) else ""
                if sha.startswith(prefix):
                    return row
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def _print_summary(result: dict[str, Any]) -> None:
    print(f"truth_label: {result.get('truth_label')}")
    print(f"folder:      {result.get('folder')}")
    print(f"imported:    {result.get('n_imported')}")
    print(f"skipped:     {result.get('n_skipped')}  (already in ledger by sha256)")
    print(f"errored:     {result.get('n_errored')}")
    if result.get("imported"):
        print("\nnew imports:")
        for row in result["imported"]:
            print(f"  [{row['source']:<20}] {row['file_name']}  "
                  f"sha256={row['sha256'][:12]}…  ({row['file_size_bytes']} bytes)")
    if result.get("errored"):
        print("\nerrored:")
        for row in result["errored"]:
            print(f"  {row.get('file')}: {row.get('error') or row.get('reason')}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=False)
    p.add_argument("--scan", action="store_true",
                   help="Scan Documents/from_external/ and import all new files")
    p.add_argument("--folder", type=str, default=None,
                   help="Scan this folder instead of the default inbox")
    p.add_argument("--import", dest="import_path", type=str, default=None,
                   help="Import a single file by path")
    p.add_argument("--source", type=str, default=None,
                   help="Substrate label (grok, chatgpt, claude, …)")
    p.add_argument("--url", type=str, default=None,
                   help="Source URL")
    p.add_argument("--notes", type=str, default=None)
    p.add_argument("--list-recent", action="store_true",
                   help="Show the last 5 imports")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()

    if args.list_recent:
        rows = list_recent_imports(last_n=5)
        if not rows:
            print("(no external imports yet)")
        else:
            for row in rows:
                ago = time.time() - float(row.get("ts") or 0)
                print(f"[{int(ago):>7}s ago] [{row.get('source'):<20}] "
                      f"{row.get('file_name')}  sha256={row.get('sha256','')[:12]}…")
        sys.exit(0)

    if args.import_path:
        out = import_one(
            args.import_path,
            source=args.source, url=args.url, notes=args.notes,
            write=not args.no_write,
        )
        print(json.dumps(out, indent=2, default=str))
        sys.exit(0 if out.get("ok") else 1)

    # Default action: scan
    out = scan_folder(folder=args.folder, write=not args.no_write)
    _print_summary(out)
    sys.exit(0 if out.get("ok") else 1)
