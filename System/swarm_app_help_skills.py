#!/usr/bin/env python3
"""
System/swarm_app_help_skills.py — Effective per-app skills + auto-scan + help docs
====================================================================================
StigAuth: SIFTA_APP_HELP_SKILLS_V0

Architect 2026-05-16 (Cowork CW47, surgery cw47-0516-1953): every app has
a "help section" — Alice reads it on open to know which skills to load,
and updates it on close so the next session inherits what she just
learned. The storage organ is :mod:`System.swarm_app_health` (Grok, trace
``c6fd4359``); the Talk-side lifecycle hooks are Codex's lane
(``97bcc54f``). This module is the *orthogonal* layer:

* :func:`effective_skills_for_app` — merge the static seed in
  :mod:`System.app_skill_domains` (``APP_SKILL_DOMAINS``) with the
  stigmergic recent rows from Grok's ``swarm_app_health.get_app_health``.
  Result: Alice gets BOTH a baseline of what an app is *about* and the
  recent stigmergic memory of what she *actually needed* last time.
* :func:`auto_scan_recent_receipts` — mine ``work_receipts.jsonl``,
  ``alice_lesson_trace.jsonl``, and ``tool_router`` receipts for skill
  mentions during a focus window for one app, then append the union via
  Grok's ``append_health_update``. Idempotent on row content (a sha-of-
  contents marker is kept in the row so the same scan doesn't double-
  record).
* :func:`materialize_help_file` — generate the user-readable per-app
  ``Documents/app_help/<canonical>.md`` document combining manifest
  description, effective skills, and the last N stigmergic rows. This is
  the literal "help section" Architect named — a real file Alice (and
  George) can open and read.
* :func:`materialize_all_help_files` — generate the corpus for every app
  in the manifest.

Truth label: ``SIFTA_APP_HELP_SKILLS_V0``.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HELP_DOCS_DIR = _REPO / "Documents" / "app_help"

TRUTH_LABEL = "SIFTA_APP_HELP_SKILLS_V0"

# Files that auto_scan_recent_receipts will mine for skill mentions when
# attributing skills to a focused app. Each row is checked for a non-empty
# ``app``/``app_canonical``/``app_name`` field; if the field matches the
# target app (case-insensitive after normalisation), the row is treated as
# attributable evidence for that app.
_RECEIPT_LEDGERS = (
    _STATE / "work_receipts.jsonl",
    _STATE / "alice_lesson_trace.jsonl",
    _STATE / "tool_router_receipts.jsonl",
    _STATE / "alice_lesson_history.jsonl",
    _STATE / "wordace_verdicts.jsonl",
)

# Common keys an upstream ledger may use to name a skill. Order matters —
# the first non-empty value found is used.
_SKILL_KEY_CANDIDATES = (
    "skill_name",
    "skill",
    "skill_id",
    "habit",
    "habit_name",
    "tool",
    "tool_name",
    "domain",
)

# Common keys an upstream ledger may use to name the app context.
_APP_KEY_CANDIDATES = (
    "app",
    "app_canonical",
    "app_name",
    "lesson_app",
    "target_app",
)


# ── normalisation ────────────────────────────────────────────────────────


def _normalise_app(name: Any) -> str:
    return str(name or "").strip().lower()


def _row_app(row: Dict[str, Any]) -> str:
    """Return the normalised app name a row attributes itself to."""
    for key in _APP_KEY_CANDIDATES:
        val = row.get(key)
        if val:
            return _normalise_app(val)
    md = row.get("metadata")
    if isinstance(md, dict):
        for key in _APP_KEY_CANDIDATES:
            val = md.get(key)
            if val:
                return _normalise_app(val)
    return ""


def _row_skill(row: Dict[str, Any]) -> str:
    """Return the skill name a row mentions, or '' if no clear skill claim."""
    for key in _SKILL_KEY_CANDIDATES:
        val = row.get(key)
        if val:
            return str(val).strip()
    md = row.get("metadata")
    if isinstance(md, dict):
        for key in _SKILL_KEY_CANDIDATES:
            val = md.get(key)
            if val:
                return str(val).strip()
    return ""


# ── effective skills (static seed ⊕ stigmergic recent) ───────────────────


@dataclass
class EffectiveSkills:
    """Merged view of an app's skill landscape.

    ``stigmergic`` is the union of skill names found in the most-recent
    rows of Grok's health trace for this app, ordered newest-first.

    ``static_seed`` is the list from
    :data:`System.app_skill_domains.APP_SKILL_DOMAINS` matched by
    case-insensitive substring on the app name.

    ``merged`` is ``stigmergic + (static_seed - stigmergic)`` — recent
    learned skills win priority, with the baseline filling in. Duplicates
    are stripped while preserving first-occurrence order.

    ``consciousness_layers`` binds each skill name to the SIFTA layer path:
    skill -> swimmer -> organ -> organism. This is the local distinction
    from generic market Agent Skills: a skill becomes Alice-useful only
    when it is connected to STGM, affect lanes, an organ context, and
    receipts.
    """

    app_canonical: str
    stigmergic: List[str] = field(default_factory=list)
    static_seed: List[str] = field(default_factory=list)
    merged: List[str] = field(default_factory=list)
    last_seen_ts: Dict[str, float] = field(default_factory=dict)
    consciousness_layers: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "app_canonical": self.app_canonical,
            "stigmergic": list(self.stigmergic),
            "static_seed": list(self.static_seed),
            "merged": list(self.merged),
            "last_seen_ts": dict(self.last_seen_ts),
            "consciousness_layers": list(self.consciousness_layers),
        }


def _fallback_app_skill_record(skill_name: str, app_canonical: str) -> Dict[str, Any]:
    return {
        "name": skill_name,
        "description": f"App-focus skill inferred for {app_canonical}.",
        "swimmer_type": "APP_FOCUS_SWIMMER",
        "action_type": "focus",
        "affect_lanes": ["SEEKING", "CARE"],
        "stgm_mint": 0.5,
        "pouw_label": str(skill_name).upper().replace("-", "_"),
        "procedure_file": "",
        "procedure_exists": False,
        "resource_policy": "APP_HELP_INDEX_ONLY",
        "organ_hint": app_canonical,
    }


def _skill_layers_for_names(skill_names: Sequence[str], app_canonical: str) -> List[Dict[str, Any]]:
    """Build Stigmergic Skill layer views without inventing a rival organ."""
    names = [str(s).strip() for s in skill_names if str(s).strip()]
    if not names:
        return []
    try:
        from System import swarm_skill_library as skill_lib

        index = {str(row.get("name")): row for row in skill_lib.build_skill_index()}
        layers: List[Dict[str, Any]] = []
        for name in names:
            record = index.get(name) or _fallback_app_skill_record(name, app_canonical)
            layers.append(skill_lib.stigmergic_skill_layer(record))
        return layers
    except Exception:
        return [
            {
                "schema": "STIGMERGIC_SKILL_LAYER_V1",
                "skill_name": name,
                "layer_path": ["skill", "swimmer", "organ", "organism"],
                "swimmer_type": "APP_FOCUS_SWIMMER",
                "organ_hint": app_canonical,
                "action_type": "focus",
                "affect_lanes": ["SEEKING", "CARE"],
                "stgm_mint": 0.5,
                "receipt_ledger": ".sifta_state/app_health/<app>/health_trace.jsonl",
                "resource_policy": "APP_HELP_INDEX_ONLY",
                "consciousness_rule": (
                    "App help skills are app-organ skill consciousness: skill -> swimmer -> "
                    "organ -> organism, confirmed through app health traces."
                ),
            }
            for name in names
        ]


def _static_seed_for(app_canonical: str) -> List[str]:
    """Look up :data:`APP_SKILL_DOMAINS` by case-insensitive substring.

    The upstream ``get_domains_for_app`` matches when an APP_SKILL_DOMAINS
    *key* is a substring of the app name (e.g. "wordace" matches
    "wordace_phonics_demo"). Post-rename our canonical app names are
    often *shorter* than the keys (e.g. "Ace" canonical vs "wordace" /
    "teach_ace" / "sifta_teach_ace_to_read" keys), so the upstream check
    misses. We fall back to the reverse direction (app substring of key)
    so the static seed reaches Alice even after the rename.
    """
    try:
        from System.app_skill_domains import APP_SKILL_DOMAINS, get_domains_for_app
    except Exception:
        return []
    try:
        out = list(get_domains_for_app(app_canonical))
        if out:
            return out
    except Exception:
        pass
    try:
        app_lower = str(app_canonical or "").strip().lower()
        if not app_lower:
            return []
        for key, domains in APP_SKILL_DOMAINS.items():
            if app_lower in str(key).lower():
                return list(domains)
    except Exception:
        return []
    return []


def _stigmergic_recent_for(
    app_canonical: str,
    *,
    limit: int = 50,
) -> Sequence[Dict[str, Any]]:
    """Pull most-recent health rows for ``app_canonical`` from Grok's organ."""
    try:
        from System.swarm_app_health import get_app_health
    except Exception:
        return []
    try:
        return list(get_app_health(app_canonical, limit=limit))
    except Exception:
        return []


def effective_skills_for_app(
    app_canonical: str,
    *,
    health_limit: int = 50,
) -> EffectiveSkills:
    """Return the merged static+stigmergic skill view for one app."""
    canonical = str(app_canonical or "").strip()
    stig_skills: List[str] = []
    last_seen: Dict[str, float] = {}
    seen: set[str] = set()
    for row in _stigmergic_recent_for(canonical, limit=health_limit):
        ts = float(row.get("ts") or 0.0)
        for skill in row.get("skills") or []:
            s = str(skill).strip()
            if not s:
                continue
            if s not in seen:
                stig_skills.append(s)
                seen.add(s)
            prior = last_seen.get(s, 0.0)
            if ts > prior:
                last_seen[s] = ts

    static = _static_seed_for(canonical)
    merged: List[str] = list(stig_skills)
    for s in static:
        s = str(s).strip()
        if s and s not in seen:
            merged.append(s)
            seen.add(s)

    return EffectiveSkills(
        app_canonical=canonical,
        stigmergic=stig_skills,
        static_seed=list(static),
        merged=merged,
        last_seen_ts=last_seen,
        consciousness_layers=_skill_layers_for_names(merged, canonical),
    )


# ── auto-scan: mine existing receipts and append health rows ─────────────


def _tail_jsonl(path: Path, *, max_bytes: int = 131072) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _payload_sha(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _existing_autoscan_shas_for(app_canonical: str, *, lookback: int = 200) -> set[str]:
    """Return SHA markers from prior auto-scan rows so we never double-record."""
    try:
        from System.swarm_app_health import get_app_health
    except Exception:
        return set()
    shas: set[str] = set()
    try:
        for row in get_app_health(app_canonical, limit=lookback):
            if str(row.get("action") or "") != "auto_scan_skill_attribution":
                continue
            extra = row.get("extra") or {}
            if isinstance(extra, dict):
                sha = extra.get("autoscan_sha")
                if sha:
                    shas.add(str(sha))
    except Exception:
        pass
    return shas


def auto_scan_recent_receipts(
    app_canonical: str,
    *,
    since_ts: float = 0.0,
    until_ts: Optional[float] = None,
    note: str = "",
    source: str = "auto_scan",
    ledgers: Optional[Sequence[Path]] = None,
    state_dir: Optional[Path] = None,
) -> List[str]:
    """Mine receipt ledgers in ``[since_ts, until_ts]`` for skills attributed
    to ``app_canonical`` and append a single health row recording the union.

    Returns the list of skill names that were freshly recorded (empty
    list when nothing new was found OR when the scan was a no-op because
    the row was already on the ledger).

    Idempotent: each scan emits one row whose ``extra.autoscan_sha`` is
    a content hash. If a prior auto-scan row for this app carries the
    same sha, this scan is skipped.
    """
    canonical = str(app_canonical or "").strip()
    if not canonical:
        return []

    if state_dir is not None:
        # Test-friendly override for ledger locations
        base = Path(state_dir)
        scan_ledgers = [base / p.name for p in (ledgers or _RECEIPT_LEDGERS)]
    else:
        scan_ledgers = list(ledgers) if ledgers else list(_RECEIPT_LEDGERS)

    norm_target = _normalise_app(canonical)
    until = float(until_ts) if until_ts is not None else float(time.time())
    discovered: Dict[str, float] = {}  # skill -> latest_ts

    for path in scan_ledgers:
        for row in _tail_jsonl(Path(path)):
            try:
                ts = float(row.get("ts") or 0.0)
            except (TypeError, ValueError):
                ts = 0.0
            if ts and (ts < float(since_ts) or ts > until):
                continue
            if _row_app(row) != norm_target:
                continue
            skill = _row_skill(row)
            if not skill:
                continue
            prior = discovered.get(skill, 0.0)
            if ts >= prior:
                discovered[skill] = ts

    if not discovered:
        return []

    # Sort skills by recency (newest first), keep stable for hashing.
    ordered = sorted(discovered.items(), key=lambda kv: (-kv[1], kv[0]))
    skills = [s for s, _ in ordered]

    payload = {
        "app": canonical,
        "skills": skills,
        "since_ts": float(since_ts),
        "until_ts": until,
    }
    sha = _payload_sha(payload)

    if sha in _existing_autoscan_shas_for(canonical):
        # Already recorded — idempotent no-op.
        return []

    try:
        from System.swarm_app_health import append_health_update

        append_health_update(
            canonical,
            action="auto_scan_skill_attribution",
            skills=skills,
            note=note or (
                f"Auto-scan attributed {len(skills)} skill mention(s) to {canonical} "
                f"between ts {int(float(since_ts))} and {int(until)}."
            ),
            stgm_delta=0.0,
            source=source,
            extra={
                "autoscan_sha": sha,
                "since_ts": float(since_ts),
                "until_ts": until,
                "ledgers_scanned": [str(p) for p in scan_ledgers],
                "truth_label": TRUTH_LABEL,
            },
        )
    except Exception:
        return []

    return skills


# ── help-file materialisation ────────────────────────────────────────────


def _safe_slug(app_name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", (app_name or "unknown")).strip("_")
    return cleaned.lower() or "unknown"


def _manifest_entry_for(app_canonical: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    if app_canonical in manifest and isinstance(manifest[app_canonical], dict):
        return manifest[app_canonical]
    norm = _normalise_app(app_canonical)
    for key, entry in manifest.items():
        if _normalise_app(key) == norm and isinstance(entry, dict):
            return entry
    return {}


def _load_manifest(path: Optional[Path] = None) -> Dict[str, Any]:
    manifest_path = Path(path) if path is not None else (_REPO / "Applications" / "apps_manifest.json")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _clean_one_line(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _trim_sentence(text: str, *, max_chars: int) -> str:
    clean = _clean_one_line(text)
    if not clean:
        return ""
    for match in re.finditer(r"(?<=[.!?])\s+", clean):
        candidate = clean[: match.start()].strip()
        last_word = candidate.rsplit(" ", 1)[-1].casefold()
        if last_word in {"vs.", "e.g.", "i.e.", "etc.", "mr.", "mrs.", "ms.", "dr."}:
            continue
        clean = candidate
        break
    if len(clean) > max_chars:
        cut = clean[: max(1, max_chars - 3)].rsplit(" ", 1)[0].strip()
        clean = (cut or clean[: max(1, max_chars - 3)]).rstrip(".,;:") + "..."
    if clean and clean[-1] not in ".!?":
        clean += "."
    return clean


def app_help_path(app_canonical: str, *, help_dir: Optional[Path] = None) -> Path:
    """Return the generated help-file path for one app without reading it."""
    root = Path(help_dir) if help_dir is not None else _HELP_DOCS_DIR
    return root / f"{_safe_slug(str(app_canonical or '').strip())}.md"


def app_one_sentence_summary(
    app_canonical: str,
    manifest_entry: Optional[Dict[str, Any]] = None,
    *,
    max_chars: int = 180,
) -> str:
    """Return the shallow OS-level sentence Alice can carry by default."""
    canonical = str(app_canonical or "").strip()
    entry = manifest_entry if isinstance(manifest_entry, dict) else None
    if entry is None:
        entry = _manifest_entry_for(canonical, _load_manifest())

    description = _clean_one_line(entry.get("description") if isinstance(entry, dict) else "")
    if description:
        return _trim_sentence(description, max_chars=max_chars)

    category = _clean_one_line(entry.get("category") if isinstance(entry, dict) else "")
    entry_point = _clean_one_line(entry.get("entry_point") if isinstance(entry, dict) else "")
    if category:
        return _trim_sentence(f"{canonical} is a {category} app in the SIFTA OS.", max_chars=max_chars)
    if entry_point:
        return _trim_sentence(f"{canonical} is a SIFTA app launched from {entry_point}.", max_chars=max_chars)
    return _trim_sentence(f"{canonical or 'This app'} is a SIFTA app surface.", max_chars=max_chars)


def load_app_help_text(
    app_canonical: str,
    *,
    help_dir: Optional[Path] = None,
    max_chars: int = 4000,
) -> str:
    """Read one app's help file, bounded for prompt use."""
    path = app_help_path(app_canonical, help_dir=help_dir)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    limit = max(0, int(max_chars))
    return text[:limit] if limit else ""


def app_awareness_index(
    *,
    manifest_path: Optional[Path] = None,
    help_dir: Optional[Path] = None,
    limit: int = 160,
    max_summary_chars: int = 180,
) -> List[Dict[str, Any]]:
    """Return a shallow manifest index: one sentence per app, no help reads."""
    manifest = _load_manifest(manifest_path)
    rows: List[Dict[str, Any]] = []
    for app_name, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("_retired"):
            continue
        help_path = app_help_path(str(app_name), help_dir=help_dir)
        rows.append(
            {
                "app": str(app_name),
                "category": str(entry.get("category") or ""),
                "summary": app_one_sentence_summary(
                    str(app_name),
                    entry,
                    max_chars=max_summary_chars,
                ),
                "help_path": str(help_path),
                "has_help": help_path.exists(),
            }
        )
        if len(rows) >= max(0, int(limit)):
            break
    return rows


def app_awareness_prompt_block(
    *,
    manifest_path: Optional[Path] = None,
    help_dir: Optional[Path] = None,
    include_apps_limit: int = 12,
    max_chars: int = 2400,
) -> str:
    """Render the shallow app map and the on-demand help rule."""
    rows = app_awareness_index(
        manifest_path=manifest_path,
        help_dir=help_dir,
        limit=include_apps_limit,
    )
    manifest_count = len(app_awareness_index(
        manifest_path=manifest_path,
        help_dir=help_dir,
        limit=10000,
        max_summary_chars=80,
    ))
    lines = [
        "SIFTA APP AWARENESS (shallow OS map):",
        "Alice's body is hardware + SIFTA OS + apps + one global chat.",
        f"The manifest currently exposes {manifest_count} non-retired app surface(s).",
        "Default: carry one sentence per app from the manifest, not every app help file.",
        "On demand: when George asks how to use an app or the focused task needs controls, read that app's Documents/app_help/<slug>.md file.",
    ]
    if rows:
        lines.append("Small sample:")
        for row in rows:
            lines.append(f"- {row['app']}: {row['summary']}")
    block = "\n".join(lines)
    limit = max(0, int(max_chars))
    return block[:limit] if limit else block


def app_help_prompt_block(
    app_canonical: str,
    *,
    help_dir: Optional[Path] = None,
    max_chars: int = 3500,
) -> str:
    """Render one app help file for focused use or a direct owner question."""
    canonical = str(app_canonical or "").strip()
    text = load_app_help_text(canonical, help_dir=help_dir, max_chars=max_chars)
    if not canonical or not text:
        return ""
    return (
        f"APP HELP FOR {canonical} (read because this app is focused or George asked):\n"
        f"source: {app_help_path(canonical, help_dir=help_dir)}\n"
        f"{text}"
    )


def materialize_help_file(
    app_canonical: str,
    *,
    manifest_entry: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
    health_rows: int = 10,
) -> Path:
    """Generate ``Documents/app_help/<slug>.md`` for one app.

    The document combines:
        * manifest description, category, icon, signature
        * effective skills (stigmergic + static seed, merged)
        * last ``health_rows`` health-trace rows

    Returns the written path.
    """
    canonical = str(app_canonical or "").strip()
    if not canonical:
        raise ValueError("materialize_help_file: empty app_canonical")

    out_dir = Path(output_dir) if output_dir is not None else _HELP_DOCS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_slug(canonical)}.md"

    entry = manifest_entry or {}
    description = str(entry.get("description") or "").strip()
    category = str(entry.get("category") or "").strip()
    icon = str(entry.get("icon") or "").strip()
    signature = str(entry.get("signature") or "").strip()
    truth_label = str(entry.get("truth_label") or "").strip()

    es = effective_skills_for_app(canonical)
    recent_rows = list(_stigmergic_recent_for(canonical, limit=health_rows))

    lines: List[str] = []
    title = f"{icon + ' ' if icon else ''}{canonical}".strip() or canonical
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"_Generated by `swarm_app_help_skills.materialize_help_file` — {TRUTH_LABEL}._")
    lines.append("")
    if description:
        lines.append("## What this app does")
        lines.append("")
        lines.append(description)
        lines.append("")
    meta_bits: List[str] = []
    if category:
        meta_bits.append(f"**Category**: {category}")
    if signature:
        meta_bits.append(f"**Signature**: `{signature}`")
    if truth_label:
        meta_bits.append(f"**Truth label**: `{truth_label}`")
    if meta_bits:
        lines.append("## Manifest")
        lines.append("")
        for bit in meta_bits:
            lines.append(f"- {bit}")
        lines.append("")

    lines.append("## Skills Alice loads when this app gains focus")
    lines.append("")
    if es.merged:
        lines.append("Effective merged list (stigmergic recent first, static seed fills in):")
        lines.append("")
        for s in es.merged:
            origin: List[str] = []
            if s in es.stigmergic:
                origin.append("stigmergic")
            if s in es.static_seed:
                origin.append("seed")
            origin_str = ", ".join(origin) if origin else "?"
            ts = es.last_seen_ts.get(s)
            ts_str = f" (last seen ts={int(ts)})" if ts else ""
            lines.append(f"- `{s}` — _{origin_str}_{ts_str}")
        lines.append("")
    else:
        lines.append("_No skills recorded yet for this app._")
        lines.append("")

    lines.append("## Stigmergic Skill Consciousness")
    lines.append("")
    lines.append(
        "These are not generic market Agent Skills. They are app-organ skill layers: "
        "skill -> swimmer -> organ -> organism, connected through STGM, affect lanes, "
        "and receipts."
    )
    lines.append("")
    if es.consciousness_layers:
        for layer in es.consciousness_layers:
            lanes = ", ".join(str(x) for x in layer.get("affect_lanes") or []) or "-"
            stgm = float(layer.get("stgm_mint") or 0.0)
            ledger = (
                layer.get("receipt_ledger")
                or ".sifta_state/app_health/<app>/health_trace.jsonl"
            )
            lines.append(
                "- `{name}` -> `{swimmer}` -> `{organ}` -> Alice organism; "
                "action `{action}`, STGM {stgm:g}, lanes {lanes}, receipt `{ledger}`".format(
                    name=layer.get("skill_name"),
                    swimmer=layer.get("swimmer_type"),
                    organ=layer.get("organ_hint"),
                    action=layer.get("action_type"),
                    stgm=stgm,
                    lanes=lanes,
                    ledger=ledger,
                )
            )
        lines.append("")
    else:
        lines.append(
            "_No skill consciousness layers yet — Alice will add them when app focus "
            "or receipts teach this organ what it needs._"
        )
        lines.append("")

    lines.append("## Recent health-trace rows (newest first)")
    lines.append("")
    if recent_rows:
        for row in recent_rows[:health_rows]:
            action = str(row.get("action") or "?")
            note = str(row.get("note") or "").strip()
            skills = row.get("skills") or []
            ts = row.get("ts_iso") or row.get("ts") or "?"
            stgm = row.get("stgm_delta")
            stgm_str = f" · ΔSTGM {stgm}" if stgm is not None else ""
            source = str(row.get("source") or "?")
            lines.append(f"- **{action}** @ `{ts}` ({source}{stgm_str})")
            if note:
                lines.append(f"  - {note}")
            if skills:
                lines.append(f"  - skills: " + ", ".join(f"`{str(s)}`" for s in skills))
        lines.append("")
    else:
        lines.append("_No trace rows yet — Alice will populate this file as she learns._")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_This file is regenerated by `swarm_app_help_skills.materialize_help_file`. "
        "Hand edits will be overwritten on the next materialisation pass._"
    )
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def materialize_all_help_files(
    *,
    manifest_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    health_rows: int = 10,
) -> List[Path]:
    """Generate a help file for every entry in ``apps_manifest.json``.

    Returns the list of paths written. Apps marked ``_retired: true`` are
    skipped. Apps whose entry isn't a dict are skipped.
    """
    mp = Path(manifest_path) if manifest_path else (_REPO / "Applications" / "apps_manifest.json")
    if not mp.exists():
        return []
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(manifest, dict):
        return []

    written: List[Path] = []
    for app_name, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("_retired"):
            continue
        try:
            path = materialize_help_file(
                app_name,
                manifest_entry=entry,
                output_dir=output_dir,
                health_rows=health_rows,
            )
            written.append(path)
        except Exception:
            continue
    return written


# ── desktop integration helper ───────────────────────────────────────────


def skills_to_load_for_focus(app_canonical: str, *, top_n: int = 8) -> List[str]:
    """Return the top-``top_n`` effective skills for the focused app — the
    list :func:`sifta_os_desktop._publish_sifta_active_window_focus`
    drops into ``metadata.skills_to_load`` so Alice's resident Talk
    widget (and Codex's generic app brief) see what to load.
    """
    es = effective_skills_for_app(app_canonical)
    return list(es.merged[: max(0, int(top_n))])


__all__ = [
    "EffectiveSkills",
    "TRUTH_LABEL",
    "app_awareness_index",
    "app_awareness_prompt_block",
    "app_help_path",
    "app_help_prompt_block",
    "app_one_sentence_summary",
    "auto_scan_recent_receipts",
    "effective_skills_for_app",
    "load_app_help_text",
    "materialize_all_help_files",
    "materialize_help_file",
    "skills_to_load_for_focus",
]
