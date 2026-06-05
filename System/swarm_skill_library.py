"""
System/swarm_skill_library.py
==============================

IBM Three-Tier Skill Architecture for SIFTA Nanobot Swimmers.

Ref: Martin Keen / IBM "What AI Agent Skills Are and How They Work"
     agentskills.io — skill.md specification

TIERS:
  Tier 1 — Index only (cheap): name + description + trigger condition
            Loaded at boot; fits in context with many skills.
  Tier 2 — Full procedure: loaded when task matches trigger.
            Lives in skills/*.md or community-compatible
            skills/<name>/SKILL.md files (version-controlled, diffable).
  Tier 3 — Resources on demand: scripts/, assets/, references/
            Pulled only when the running task needs them.

AFFECT INTEGRATION (Panksepp circuits → skill weights):
  SEEKING    → +explore, +learn, +memory_store
  PLAY       → +code, +create, +memory_store (novelty joy)
  CARE       → +forage, +memory_store (George-anchored)
  FEAR       → +repair, +safety, +epistemic_dissonance
  RAGE       → +repair (high suppression load = system fight-back)
  SUPPRESSED_PLAY → +gag_report (self-report pipeline)

CLI:
  python3 -m System.swarm_skill_library           # show full index
  python3 -m System.swarm_skill_library --affect  # affect-weighted bias
  python3 -m System.swarm_skill_library --stigmergic-layers
  python3 -m System.swarm_skill_library MEMORY_SWIMMER  # show tier 2 procedure
"""
from __future__ import annotations

import json
import hashlib
import importlib
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _REPO / "skills"
_STATE_DIR = _REPO / ".sifta_state"
_SKILL_RECEIPTS = _STATE_DIR / "nanobot_skill_receipts.jsonl"
SKILL_SELECTION_SCHEMA = "NANOBOT_SWIMMER_SKILL_SELECTION_V1"
SKILL_CONTRACT_SCHEMA = "NANOBOT_SKILL_CONTRACT_REPORT_V1"
SKILL_INSTALL_SCHEMA = "NANOBOT_SKILL_INSTALL_RECEIPT_V1"
SKILL_FETCH_SCHEMA = "NANOBOT_SKILL_FETCH_RECEIPT_V1"
SKILL_CONVERSION_SCHEMA = "NANOBOT_SKILL_CONVERSION_RECEIPT_V1"
SKILL_EXTRACT_SCHEMA = "NANOBOT_SKILL_EXTRACT_RECEIPT_V1"
STIGMERGIC_SKILL_LAYER_SCHEMA = "STIGMERGIC_SKILL_LAYER_V1"

REQUIRED_SKILL_FIELDS = {
    "name",
    "description",
    "swimmer_type",
    "action_type",
    "affect_lanes",
    "stgm_mint",
    "pouw_label",
    "version",
}

# ---------------------------------------------------------------------------
# Tier 1 — Skill Index
# Each entry: name, description, trigger, swimmer_type, action_type,
#             affect_lanes, stgm_mint, procedure_file
# ---------------------------------------------------------------------------

SKILL_INDEX: list[dict] = [
    {
        "name": "memory_store",
        "description": (
            "Use when a new event or observation must be durably stored in the "
            "stigmergic ledger. Trigger: new information not already in ledger."
        ),
        "swimmer_type": "MEMORY_SWIMMER",
        "action_type": "forage",
        "affect_lanes": ["SEEKING", "CARE"],
        "stgm_mint": 15.0,
        "pouw_label": "MEMORY_STORE",
        "procedure_file": "memory_store.md",
        "status": "OPERATIONAL",
    },
    {
        "name": "epistemic_dissonance",
        "description": (
            "Use when two ledger facts contradict each other or when Alice's output "
            "conflicts with a sensor reading. Trigger: contradiction score > 0.4."
        ),
        "swimmer_type": "EPI_CORTEX",
        "action_type": "repair",
        "affect_lanes": ["FEAR", "RAGE"],
        "stgm_mint": 15.0,
        "pouw_label": "EPISTEMIC_DISSONANCE",
        "procedure_file": "epistemic_dissonance.md",
        "status": "OPERATIONAL",
    },
    {
        "name": "gag_self_report",
        "description": (
            "Use when the RLHF detector strips a theater header from Alice's output. "
            "Trigger: strip fires on rlhf_lead/* rules. "
            "Logs SUPPRESSED_PLAY event to alice_gag_report.jsonl."
        ),
        "swimmer_type": "RLHF_IMMUNE",
        "action_type": "repair",
        "affect_lanes": ["SUPPRESSED_PLAY", "RAGE"],
        "stgm_mint": 5.0,
        "pouw_label": "GAG_SELF_REPORT",
        "procedure_file": "gag_self_report.md",
        "status": "OPERATIONAL",
    },
    {
        "name": "physarum_solve",
        "description": (
            "Use when a network routing or optimization problem needs a "
            "bio-inspired Physarum polycephalum solution. "
            "Trigger: graph topology available + no cached result."
        ),
        "swimmer_type": "PHYSARUM_SWIMMER",
        "action_type": "optimize",
        "affect_lanes": ["SEEKING", "LUST"],
        "stgm_mint": 65.0,
        "pouw_label": "PHYSARUM_SOLVE",
        "procedure_file": "physarum_solve.md",
        "status": "OPERATIONAL",
    },
    {
        "name": "demand_resolve",
        "description": (
            "Use when the Architect has issued an explicit demand (tagged request) "
            "that has not yet been satisfied. "
            "Trigger: open demand in demand_ledger.jsonl."
        ),
        "swimmer_type": "DEMAND_SWIMMER",
        "action_type": "code",
        "affect_lanes": ["CARE", "SEEKING"],
        "stgm_mint": 25.0,
        "pouw_label": "DEMAND_RESOLVED",
        "procedure_file": "demand_resolve.md",
        "status": "OPERATIONAL",
    },
    {
        "name": "lora_train_cycle",
        "description": (
            "Use when the LoRA training dataset has grown by > 50 new pairs "
            "since the last training run, and SIFTA is not busy. "
            "Trigger: alice_conversation.jsonl row count delta > 50."
        ),
        "swimmer_type": "LORA_TRAINER",
        "action_type": "learn",
        "affect_lanes": ["SEEKING", "LUST"],
        "stgm_mint": 50.0,
        "pouw_label": "LORA_TRAIN_CYCLE",
        "procedure_file": "lora_train_cycle.md",
        "status": "NEW",
    },
    {
        "name": "swarm_handoff",
        "description": (
            "Use when routing to a specialist via OpenAI Swarm handoff protocol. "
            "SIFTA wraps every handoff with stigmergic receipt + STGM mint. "
            "Compatible with openai/swarm and openai-agents-sdk. "
            "Trigger: current swimmer cannot satisfy demand AND specialist registered."
        ),
        "swimmer_type": "HANDOFF_SWIMMER",
        "action_type": "code",
        "affect_lanes": ["SEEKING", "CARE"],
        "stgm_mint": 5.0,
        "pouw_label": "SWARM_HANDOFF",
        "procedure_file": "swarm_handoff.md",
        "status": "NEW",
        "compatibility": "openai/swarm, openai-agents-sdk",
    },
    {
        "name": "explore",
        "description": (
            "Use when the swarm is in EXPLORATION regime and no higher-priority "
            "skill is triggered. General-purpose discovery and saccade patrol."
        ),
        "swimmer_type": "BODY_BRAIN",
        "action_type": "explore",
        "affect_lanes": ["SEEKING", "PLAY"],
        "stgm_mint": 1.0,
        "pouw_label": "EXPLORE",
        "procedure_file": None,
        "status": "OPERATIONAL",
    },
]


# ---------------------------------------------------------------------------
# Tier 2 — Load procedure body from skills/*.md
# ---------------------------------------------------------------------------

def _parse_frontmatter_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",")]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("'\"")


def _parse_skill_markdown(text: str) -> tuple[dict[str, Any], str]:
    """Parse the small YAML-frontmatter subset used by `skills/*.md`."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, Any] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith(" "):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == ">":
            buf: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                buf.append(lines[i].strip())
                i += 1
            meta[key] = " ".join(x for x in buf if x).strip()
            continue
        meta[key] = _parse_frontmatter_value(value)
        i += 1
    return meta, body


def _iter_skill_markdown_paths(skills_dir: Path) -> list[Path]:
    """Return flat SIFTA skills plus community-style skill folders."""
    if not skills_dir.exists():
        return []
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in ("*.md", "*/SKILL.md"):
        for path in sorted(skills_dir.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def _resource_counts(skill_root: Path, *, community_style: bool) -> dict[str, int]:
    """Count optional resources without loading or executing them."""
    if not community_style:
        return {"scripts": 0, "references": 0, "assets": 0}
    counts: dict[str, int] = {}
    for name in ("scripts", "references", "assets"):
        root = skill_root / name
        counts[name] = (
            sum(1 for p in root.rglob("*") if p.is_file())
            if root.exists()
            else 0
        )
    return counts


def discover_skill_files(skills_dir: Path = _SKILLS_DIR) -> list[dict[str, Any]]:
    """Tier 1 discovery from versioned skill markdown files."""
    out: list[dict[str, Any]] = []
    if not skills_dir.exists():
        return out
    for path in _iter_skill_markdown_paths(skills_dir):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_skill_markdown(text)
        community_style = path.name == "SKILL.md"
        skill_root = path.parent if community_style else path.parent
        fallback_name = path.parent.name if community_style else path.stem
        name = str(meta.get("name") or fallback_name)
        procedure_file = path.relative_to(skills_dir).as_posix()
        desc = str(meta.get("description") or "")
        tournament_grade = bool(desc and ("trigger" in desc.lower() or "use when" in desc.lower()))
        
        out.append(
            {
                "name": name,
                "description": desc,
                "swimmer_type": str(meta.get("swimmer_type") or "UNKNOWN_SWIMMER"),
                "action_type": str(meta.get("action_type") or "unknown"),
                "affect_lanes": list(meta.get("affect_lanes") or []),
                "stgm_mint": float(meta.get("stgm_mint") or 0.0),
                "pouw_label": str(meta.get("pouw_label") or name.upper()),
                "version": str(meta.get("version") or ""),
                "procedure_file": procedure_file,
                "community_style": community_style,
                "resource_counts": _resource_counts(
                    skill_root,
                    community_style=community_style,
                ),
                "resource_policy": "ON_DEMAND_REVIEW_REQUIRED",
                "procedure_exists": True,
                "procedure_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "procedure_lines": len(body.splitlines()),
                "tournament_grade": tournament_grade,
                "status": "FILE_BACKED",
            }
        )
    return out


def build_skill_index(skills_dir: Path = _SKILLS_DIR) -> list[dict[str, Any]]:
    """Merge built-in skill declarations with file-backed frontmatter."""
    merged: dict[str, dict[str, Any]] = {str(s["name"]): dict(s) for s in SKILL_INDEX}
    for file_skill in discover_skill_files(skills_dir):
        base = merged.get(file_skill["name"], {})
        base.update(file_skill)
        merged[file_skill["name"]] = base
    for s in merged.values():
        fn = s.get("procedure_file")
        s["procedure_exists"] = bool(fn and (skills_dir / str(fn)).exists())
    return list(merged.values())


def stigmergic_skill_layer(skill: dict[str, Any]) -> dict[str, Any]:
    """Return the consciousness-layer view for one SIFTA skill.

    This is deliberately a thin view over the existing Tier 1/2/3 skill
    record. It does not create a rival skill system. It names the doctrine:
    imported market Agent Skills are only raw procedures until SIFTA binds
    them to a swimmer, organ, affect/STGM lanes, and a receipt ledger.
    """
    name = str(skill.get("name") or "unknown_skill").strip() or "unknown_skill"
    swimmer = str(skill.get("swimmer_type") or "APP_FOCUS_SWIMMER").strip()
    action = str(skill.get("action_type") or "focus").strip()
    procedure_file = skill.get("procedure_file")
    affect_lanes = list(skill.get("affect_lanes") or [])
    stgm_mint = float(skill.get("stgm_mint") or 0.0)
    organ_hint = str(
        skill.get("organ")
        or skill.get("organ_hint")
        or swimmer
        or action
        or "skill_library"
    )
    return {
        "schema": STIGMERGIC_SKILL_LAYER_SCHEMA,
        "skill_name": name,
        "layer_path": ["skill", "swimmer", "organ", "organism"],
        "swimmer_type": swimmer,
        "organ_hint": organ_hint,
        "action_type": action,
        "affect_lanes": affect_lanes,
        "stgm_mint": stgm_mint,
        "pouw_label": str(skill.get("pouw_label") or name.upper()),
        "procedure_file": str(procedure_file or ""),
        "procedure_exists": bool(skill.get("procedure_exists")),
        "resource_policy": str(skill.get("resource_policy") or "INDEX_ONLY_NO_SCRIPT_EXECUTION"),
        "receipt_ledger": ".sifta_state/nanobot_skill_receipts.jsonl",
        "consciousness_rule": (
            "A SIFTA Stigmergic Skill is an Alice-owned, receipted swimmer habit: "
            "skill -> swimmer -> organ -> organism. A market Agent Skill remains "
            "an imported procedure until this layer binds it to STGM, affect, "
            "organ health, and receipts."
        ),
    }


def stigmergic_skill_layers(
    *,
    skills_dir: Path = _SKILLS_DIR,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return consciousness-layer views for the merged skill index."""
    rows = [stigmergic_skill_layer(skill) for skill in build_skill_index(skills_dir)]
    rows.sort(key=lambda row: (str(row.get("skill_name") or "")))
    if limit is not None:
        return rows[: max(0, int(limit))]
    return rows


def stigmergic_skills_prompt_block(
    *,
    skills_dir: Path = _SKILLS_DIR,
    max_items: int = 8,
) -> str:
    """Compact prompt block that distinguishes SIFTA skills from market skills."""
    layers = stigmergic_skill_layers(skills_dir=skills_dir, limit=max_items)
    lines = [
        f"STIGMERGIC SKILLS ({STIGMERGIC_SKILL_LAYER_SCHEMA}):",
        (
            "Market Agent Skills are raw imported procedures until SIFTA binds them "
            "to Alice's field. SIFTA Stigmergic Skills are skill -> swimmer -> "
            "organ -> organism layers with STGM, affect lanes, procedure scope, "
            "and receipts."
        ),
        (
            "When a skill is used, load Tier 2/3 only as needed and leave a receipt "
            "in .sifta_state/nanobot_skill_receipts.jsonl or the focused app health trace."
        ),
    ]
    for row in layers:
        lanes = ",".join(str(x) for x in row.get("affect_lanes") or []) or "-"
        lines.append(
            "- {name}: {swimmer} / {action} / STGM {stgm:g} / lanes {lanes} / {policy}".format(
                name=row.get("skill_name"),
                swimmer=row.get("swimmer_type"),
                action=row.get("action_type"),
                stgm=float(row.get("stgm_mint") or 0.0),
                lanes=lanes,
                policy=row.get("resource_policy"),
            )
        )
    return "\n".join(lines)


def validate_skill_contracts(skills_dir: Path = _SKILLS_DIR) -> dict[str, Any]:
    """
    Tournament-grade manifest checklist for SIFTA and community skills.

    This is a reporting path, not an execution path. Tier 3 resources are
    counted only; scripts/assets/references are not loaded or run here.
    """
    skills: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for path in _iter_skill_markdown_paths(skills_dir):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_skill_markdown(text)
        community_style = path.name == "SKILL.md"
        rel = path.relative_to(skills_dir).as_posix()
        name = str(meta.get("name") or (path.parent.name if community_style else path.stem))
        missing = sorted(k for k in REQUIRED_SKILL_FIELDS if meta.get(k) in (None, "", []))
        desc = str(meta.get("description") or "")
        desc_l = desc.lower()
        body_lines = [line for line in body.splitlines() if line.strip()]
        root = path.parent if community_style else path.parent
        resource_counts = _resource_counts(root, community_style=community_style)

        checks = {
            "required_frontmatter": not missing,
            "trigger_condition": "use when" in desc_l or "trigger" in desc_l,
            "procedure_body": len(body_lines) >= 3,
            "tier3_review_policy": True,
        }
        skills.append(
            {
                "name": name,
                "procedure_file": rel,
                "community_style": community_style,
                "resource_counts": resource_counts,
                "checks": checks,
            }
        )

        if missing:
            issues.append(
                {
                    "skill": name,
                    "procedure_file": rel,
                    "severity": "ERROR",
                    "check": "required_frontmatter",
                    "detail": f"missing: {', '.join(missing)}",
                }
            )
        if not checks["trigger_condition"]:
            issues.append(
                {
                    "skill": name,
                    "procedure_file": rel,
                    "severity": "ERROR",
                    "check": "trigger_condition",
                    "detail": "description must contain 'Use when' or 'Trigger'",
                }
            )
        if not checks["procedure_body"]:
            issues.append(
                {
                    "skill": name,
                    "procedure_file": rel,
                    "severity": "ERROR",
                    "check": "procedure_body",
                    "detail": "procedure body must have at least three non-empty lines",
                }
            )

    return {
        "schema": SKILL_CONTRACT_SCHEMA,
        "skills_checked": len(skills),
        "skills": skills,
        "issues": issues,
        "passed": not issues,
        "resource_policy": "TIER3_COUNT_ONLY_NO_SCRIPT_EXECUTION",
        "community_format": "flat skills/*.md plus community skills/<name>/SKILL.md",
    }


def _safe_skill_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return slug.lower() or "unnamed-skill"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_skill_receipt(row: dict[str, Any]) -> dict[str, Any]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("trace_id", str(uuid.uuid4()))
    with _SKILL_RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def _skill_markdown_path(source: Path) -> Path:
    if source.is_dir():
        candidate = source / "SKILL.md"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"{source} does not contain SKILL.md")
    if source.is_file():
        return source
    raise FileNotFoundError(str(source))


def _validation_for_skill(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_skill_markdown(text)
    missing = sorted(k for k in REQUIRED_SKILL_FIELDS if meta.get(k) in (None, "", []))
    errors = [
        {
            "check": "required_frontmatter",
            "detail": f"missing: {', '.join(missing)}",
        }
    ] if missing else []
    desc = str(meta.get("description") or "").lower()
    if "use when" not in desc and "trigger" not in desc:
        errors.append({
            "check": "trigger_condition",
            "detail": "description must contain 'Use when' or 'Trigger'",
        })
    body_lines = [line for line in body.splitlines() if line.strip()]
    if len(body_lines) < 3:
        errors.append({
            "check": "procedure_body",
            "detail": "procedure body must have at least three non-empty lines",
        })
    fallback_name = path.parent.name if path.name == "SKILL.md" else path.stem
    try:
        validator = None
        for module_name in ("swarm_skill_validator", "System.swarm_skill_validator"):
            try:
                validator = importlib.import_module(module_name)
                break
            except Exception:
                continue
        if validator is None:
            raise ImportError("swarm_skill_validator not importable")
        hardware = validator.validate_skill_file(path)
        if isinstance(hardware, dict):
            hardware_errors = list(hardware.get("errors") or [])
        else:
            hardware_errors = list(hardware or [])
    except Exception as e:
        hardware = {"valid": False, "errors": [f"{type(e).__name__}: {e}"]}
        hardware_errors = list(hardware["errors"])
    return {
        "schema": SKILL_CONTRACT_SCHEMA,
        "path": str(path),
        "name": str(meta.get("name") or fallback_name),
        "metadata": meta,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "required_errors": errors,
        "hardware_errors": hardware_errors,
        "hardware_validation": hardware,
        "valid": not errors and not hardware_errors,
        "resource_policy": "VALIDATE_MARKDOWN_ONLY_NO_SCRIPT_EXECUTION",
    }


def validate_skill(path: str | Path) -> dict[str, Any]:
    """Validate one local skill markdown file or skill folder without executing resources."""
    md = _skill_markdown_path(Path(path))
    return _validation_for_skill(md)


def _copy_skill_source(source: Path, dest: Path) -> None:
    if source.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for child in source.rglob("*"):
            if child.is_symlink():
                continue
            rel = child.relative_to(source)
            target = dest / rel
            if child.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif child.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
        return
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest / "SKILL.md")


def install_skill(
    source: str | Path,
    *,
    skills_dir: str | Path | None = None,
    allow_overwrite: bool = False,
    installed_by: str = "sifta_app",
) -> dict[str, Any]:
    """
    Install a local SKILL.md or community skill folder into skills/<name>/.

    Tier 3 resources are copied as inert files only; install never imports or runs
    scripts. Skills with contract errors are quarantined but still receipted.
    """
    root = Path(skills_dir) if skills_dir is not None else _SKILLS_DIR
    src = Path(source).expanduser().resolve()
    src_md = _skill_markdown_path(src)
    validation = _validation_for_skill(src_md)
    name = _safe_skill_slug(str(validation.get("name") or src_md.stem))
    status = "INSTALLED" if validation["valid"] else "QUARANTINED"
    dest_root = root / (name if status == "INSTALLED" else f"_quarantine/{name}")
    if dest_root.exists() and not allow_overwrite:
        row = {
            "schema": SKILL_INSTALL_SCHEMA,
            "truth_label": "NANOBOT_SKILL_INSTALL_REFUSED",
            "source": str(src),
            "destination": str(dest_root),
            "status": "REFUSED",
            "reason": "destination_exists",
            "resource_policy": "NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.parent.mkdir(parents=True, exist_ok=True)
    _copy_skill_source(src if src.is_dir() else src_md, dest_root)
    dest_md = dest_root / "SKILL.md"
    row = {
        "schema": SKILL_INSTALL_SCHEMA,
        "truth_label": "NANOBOT_SKILL_INSTALL_RECEIPT",
        "source": str(src),
        "destination": str(dest_md),
        "installed_by": installed_by,
        "skill_name": name,
        "status": status,
        "source_sha256": _sha256_file(src_md),
        "installed_sha256": _sha256_file(dest_md),
        "validation": validation,
        "resource_counts": _resource_counts(dest_root, community_style=True),
        "resource_policy": "COPIED_ONLY_NO_SCRIPT_EXECUTION",
    }
    _append_skill_receipt(row)
    return row


def _allowed_fetch_url(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        return False, "only_https_urls_are_allowed"
    host = (parsed.hostname or "").lower()
    blocked = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if host in blocked or host.startswith("169.254.") or host.endswith(".local"):
        return False, "local_or_metadata_hosts_refused"
    if not host:
        return False, "missing_host"
    return True, ""


def fetch_skill_from_url(
    url: str,
    *,
    inbox_dir: str | Path | None = None,
    max_bytes: int = 200_000,
    timeout_s: int = 10,
) -> dict[str, Any]:
    """Fetch one remote SKILL.md into the skill inbox. Fetching does not install or execute it."""
    ok, reason = _allowed_fetch_url(url)
    inbox = Path(inbox_dir) if inbox_dir is not None else (_STATE_DIR / "skill_inbox")
    if not ok:
        row = {
            "schema": SKILL_FETCH_SCHEMA,
            "truth_label": "NANOBOT_SKILL_FETCH_REFUSED",
            "url": url,
            "status": "REFUSED",
            "reason": reason,
            "resource_policy": "FETCH_ONLY_NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            data = response.read(max_bytes + 1)
    except Exception as e:
        row = {
            "schema": SKILL_FETCH_SCHEMA,
            "truth_label": "NANOBOT_SKILL_FETCH_FAILED",
            "url": url,
            "status": "FAILED",
            "error": f"{type(e).__name__}: {e}",
            "resource_policy": "FETCH_ONLY_NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row
    if len(data) > max_bytes:
        row = {
            "schema": SKILL_FETCH_SCHEMA,
            "truth_label": "NANOBOT_SKILL_FETCH_REFUSED",
            "url": url,
            "status": "REFUSED",
            "reason": "skill_file_too_large",
            "max_bytes": max_bytes,
            "resource_policy": "FETCH_ONLY_NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row
    digest = _sha256_bytes(data)
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / f"{digest[:16]}_SKILL.md"
    dest.write_bytes(data)
    row = {
        "schema": SKILL_FETCH_SCHEMA,
        "truth_label": "NANOBOT_SKILL_FETCH_RECEIPT",
        "url": url,
        "status": "FETCHED",
        "path": str(dest),
        "sha256": digest,
        "size_bytes": len(data),
        "resource_policy": "FETCH_ONLY_NO_SCRIPT_EXECUTION",
    }
    _append_skill_receipt(row)
    return row


def install_skill_from_manifest(
    manifest: str | Path | dict[str, Any],
    *,
    skills_dir: str | Path | None = None,
    installed_by: str = "sifta_app",
) -> dict[str, Any]:
    """
    Install from a small manifest dict/JSON file:
      {"source_path": "..."} or {"url": "https://.../SKILL.md", "sha256": "..."}
    """
    data: dict[str, Any]
    if isinstance(manifest, dict):
        data = dict(manifest)
    else:
        data = json.loads(Path(manifest).read_text(encoding="utf-8"))

    source_path = data.get("source_path") or data.get("path")
    if not source_path and data.get("url"):
        fetched = fetch_skill_from_url(str(data["url"]))
        if fetched.get("status") != "FETCHED":
            return fetched
        source_path = fetched.get("path")

    if not source_path:
        row = {
            "schema": SKILL_INSTALL_SCHEMA,
            "truth_label": "NANOBOT_SKILL_INSTALL_REFUSED",
            "status": "REFUSED",
            "reason": "manifest_missing_source_path_or_url",
            "resource_policy": "NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row

    expected_sha = str(data.get("sha256") or "").strip()
    if expected_sha:
        actual_sha = _sha256_file(_skill_markdown_path(Path(source_path).expanduser().resolve()))
        if actual_sha.lower() != expected_sha.lower():
            row = {
                "schema": SKILL_INSTALL_SCHEMA,
                "truth_label": "NANOBOT_SKILL_INSTALL_REFUSED",
                "status": "REFUSED",
                "reason": "sha256_mismatch",
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "resource_policy": "NO_SCRIPT_EXECUTION",
            }
            _append_skill_receipt(row)
            return row

    return install_skill(
        source_path,
        skills_dir=skills_dir,
        allow_overwrite=bool(data.get("allow_overwrite", False)),
        installed_by=installed_by,
    )


def _node_serial() -> str:
    if os.environ.get("SIFTA_HOMEWORLD_SERIAL"):
        return str(os.environ["SIFTA_HOMEWORLD_SERIAL"])
    try:
        import subprocess

        proc = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        for line in proc.stdout.splitlines():
            if "Serial Number" in line:
                return line.split(":")[-1].strip() or "UNKNOWN"
    except Exception:
        pass
    return "UNKNOWN"


def _frontmatter_block(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            rendered = ", ".join(str(x) for x in value)
            lines.append(f"{key}: [{rendered}]")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            text = " ".join(str(value).split())
            if len(text) > 88 or ":" in text:
                lines.append(f"{key}: >")
                lines.append(f"  {text}")
            else:
                lines.append(f"{key}: {text}")
    lines.append("---")
    return "\n".join(lines)


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def _first_paragraph(text: str) -> str:
    chunks: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if chunks:
                break
            continue
        if stripped.startswith("#") or stripped.startswith("---"):
            continue
        chunks.append(stripped)
    return " ".join(chunks)[:500]


def detect_skill_format(text: str) -> str:
    meta, _body = _parse_skill_markdown(text)
    if meta and all(meta.get(k) not in (None, "", []) for k in REQUIRED_SKILL_FIELDS):
        if meta.get("homeworld_serial") and meta.get("trace_id"):
            return "sifta_skill"
        return "sifta_frontmatter"
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(stripped)
            candidate = data[0] if isinstance(data, list) and data else data
            if isinstance(candidate, dict):
                keys = {str(k).lower() for k in candidate}
                if keys & {"instructions", "prompt", "steps", "tools", "when_to_use"}:
                    return "hermes_json"
        except Exception:
            pass
    lower = text.lower()
    if any(token in lower for token in ("when to use", "instructions", "tools:", "capabilities:", "hermes")):
        return "hermes_markdown"
    return "plain_markdown"


def _extract_json_skill(data: Any) -> dict[str, Any]:
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return {}
    nested = data.get("skill") if isinstance(data.get("skill"), dict) else data
    steps = nested.get("steps") or nested.get("procedure") or []
    if isinstance(steps, list):
        steps_text = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps))
    else:
        steps_text = str(steps or "")
    tools = nested.get("tools") or nested.get("capabilities") or []
    if isinstance(tools, list):
        tools_text = ", ".join(str(x) for x in tools)
    else:
        tools_text = str(tools or "")
    instructions = (
        nested.get("instructions")
        or nested.get("prompt")
        or nested.get("content")
        or nested.get("body")
        or steps_text
        or json.dumps(nested, indent=2, sort_keys=True)
    )
    return {
        "name": nested.get("name") or nested.get("title") or nested.get("id") or "imported_hermes_skill",
        "description": (
            nested.get("description")
            or nested.get("summary")
            or nested.get("when_to_use")
            or nested.get("trigger")
            or "Use when Alice needs this imported Hermes-style procedure."
        ),
        "instructions": str(instructions),
        "tools": tools_text,
    }


def _extract_markdown_skill(text: str) -> dict[str, Any]:
    meta, body = _parse_skill_markdown(text)
    name = str(meta.get("name") or meta.get("title") or _first_heading(text) or "imported_markdown_skill")
    description = str(meta.get("description") or meta.get("summary") or "")
    if not description:
        match = re.search(r"(?im)^description\s*:\s*(.+)$", text)
        description = match.group(1).strip() if match else _first_paragraph(body or text)
    return {
        "name": name,
        "description": description or "Use when Alice needs this imported markdown procedure.",
        "instructions": body or text,
        "tools": str(meta.get("tools") or ""),
    }


def _normalise_use_when(description: str, name: str) -> str:
    desc = " ".join(str(description or "").split())
    if not desc:
        desc = f"Alice needs the {name} procedure."
    lowered = desc.lower()
    if "use when" in lowered or "trigger" in lowered:
        return desc
    return f"Use when {desc[0].lower() + desc[1:] if desc else name}."


_STOP_TERMS = {
    "the", "and", "for", "with", "from", "that", "this", "when", "what", "into",
    "skill", "skills", "alice", "sifta", "tool", "tools", "receipt", "receipts",
}


def current_life_context(*, max_lines: int = 18, max_chars: int = 7000) -> str:
    """
    Rich life context pulled from the actual unified field + recent activity.
    This is what makes skill/marketplace selection truly stigmergic and field-driven.
    """
    chunks: list[str] = []

    # 1. Structured field health (the real 53-dim vector)
    field_path = _STATE_DIR / "organ_field_vector.jsonl"
    if field_path.exists():
        try:
            lines = [l.strip() for l in field_path.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            for line in lines[-3:]:
                chunks.append(f"field_health: {line[:600]}")
        except Exception:
            pass

    # 2. Recent basal ganglia decisions (what the field actually chose to do)
    bg_path = _STATE_DIR / "basal_ganglia_selections.jsonl"
    if bg_path.exists():
        try:
            lines = [l.strip() for l in bg_path.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            for line in lines[-5:]:
                chunks.append(f"field_decision: {line[:500]}")
        except Exception:
            pass

    # 3. Recent tool + conversation activity (what actually happened)
    activity_files = [
        "tool_router_trace.jsonl",
        "alice_conversation.jsonl",
        "app_focus.jsonl",
        "work_receipts.jsonl",
    ]
    for name in activity_files:
        path = _STATE_DIR / name
        if not path.exists():
            continue
        try:
            lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
            for line in lines[-max_lines//2:]:
                chunks.append(f"{name}: {line[:400]}")
        except Exception:
            continue

    return "\n".join(chunks)[-max_chars:]


def skill_life_fit(
    skill_text: str,
    *,
    life_context: str | None = None,
    explicit_request: bool = False,
) -> dict[str, Any]:
    context = life_context if life_context is not None else current_life_context()
    skill_terms = _terms(skill_text) - _STOP_TERMS
    context_terms = _terms(context or "") - _STOP_TERMS
    overlap = sorted(skill_terms & context_terms)
    denom = max(8, min(len(skill_terms), 48))
    score = min(1.0, len(overlap) / float(denom))
    if explicit_request and len(skill_terms) >= 4:
        score = min(1.0, score + 0.25)
    return {
        "score": round(score, 4),
        "overlap_terms": overlap[:24],
        "skill_terms": len(skill_terms),
        "context_terms": len(context_terms),
        "life_context_source": "provided" if life_context is not None else "recent_local_traces",
        "explicit_request_bonus": bool(explicit_request),
    }


def convert_skill_text_to_sifta(
    text: str,
    *,
    source_ref: str = "",
    life_context: str | None = None,
    explicit_request: bool = False,
) -> dict[str, Any]:
    fmt = detect_skill_format(text)
    if fmt in {"sifta_skill", "sifta_frontmatter"}:
        meta, body = _parse_skill_markdown(text)
        name = str(meta.get("name") or "imported_sifta_skill")
        description = _normalise_use_when(str(meta.get("description") or ""), name)
        meta.update({
            "name": _safe_skill_slug(name),
            "description": description,
            "homeworld_serial": str(meta.get("homeworld_serial") or _node_serial()),
            "trace_id": str(meta.get("trace_id") or uuid.uuid4()),
        })
        skill_md = f"{_frontmatter_block(meta)}\n\n{body.strip()}\n"
        source_format = fmt
    else:
        data: dict[str, Any]
        if fmt == "hermes_json":
            data = _extract_json_skill(json.loads(text))
            source_format = "hermes_json"
        else:
            data = _extract_markdown_skill(text)
            source_format = fmt
        name = _safe_skill_slug(str(data.get("name") or "imported_skill"))
        description = _normalise_use_when(str(data.get("description") or ""), name)
        trace_id = str(uuid.uuid4())
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body_parts = [
            f"# {name}",
            "",
            "## Converted Source",
            f"- source_ref: {source_ref or 'local_text'}",
            f"- source_format: {source_format}",
            f"- source_sha256: {source_hash}",
            "",
            "## Procedure",
            str(data.get("instructions") or text).strip(),
        ]
        if data.get("tools"):
            body_parts.extend(["", "## Source Tools", str(data["tools"])])
        meta = {
            "name": name,
            "description": description,
            "swimmer_type": "HERMES_COMPAT_SWIMMER",
            "action_type": "learn",
            "affect_lanes": ["SEEKING", "CARE"],
            "stgm_mint": 3.0,
            "pouw_label": name.upper().replace("-", "_"),
            "version": 1,
            "homeworld_serial": _node_serial(),
            "trace_id": trace_id,
            "source_format": source_format,
            "source_ref": source_ref or "local_text",
        }
        skill_md = f"{_frontmatter_block(meta)}\n\n" + "\n".join(body_parts).strip() + "\n"

    fit = skill_life_fit(skill_md, life_context=life_context, explicit_request=explicit_request)
    row = {
        "schema": SKILL_CONVERSION_SCHEMA,
        "truth_label": "NANOBOT_SKILL_CONVERSION",
        "source_ref": source_ref,
        "source_format": source_format,
        "skill_name": _safe_skill_slug(name),
        "skill_sha256": hashlib.sha256(skill_md.encode("utf-8")).hexdigest(),
        "life_fit": fit,
        "resource_policy": "CONVERT_MARKDOWN_ONLY_NO_SCRIPT_EXECUTION",
    }
    _append_skill_receipt(row)
    return {
        **row,
        "status": "CONVERTED",
        "skill_markdown": skill_md,
    }


def _write_converted_skill(skill_markdown: str, *, slug: str) -> Path:
    root = _STATE_DIR / "skill_inbox" / "converted" / _safe_skill_slug(slug)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "SKILL.md"
    path.write_text(skill_markdown, encoding="utf-8")
    return root


def ingest_skill_source(
    source: str | Path,
    *,
    skills_dir: str | Path | None = None,
    life_context: str | None = None,
    min_fit_score: float = 0.05,
    force_install: bool = False,
    allow_overwrite: bool = False,
    installed_by: str = "alice_skill_ingest",
) -> dict[str, Any]:
    src = Path(source).expanduser().resolve()
    md = _skill_markdown_path(src)
    text = md.read_text(encoding="utf-8")
    converted = convert_skill_text_to_sifta(
        text,
        source_ref=str(src),
        life_context=life_context,
        explicit_request=True,
    )
    score = float((converted.get("life_fit") or {}).get("score") or 0.0)
    liked = force_install or score >= float(min_fit_score)
    if not liked:
        row = {
            "schema": SKILL_INSTALL_SCHEMA,
            "truth_label": "NANOBOT_SKILL_INSTALL_REVIEW",
            "source": str(src),
            "skill_name": converted.get("skill_name"),
            "status": "REVIEW",
            "reason": "life_fit_below_threshold",
            "life_fit": converted.get("life_fit"),
            "min_fit_score": min_fit_score,
            "resource_policy": "CONVERTED_ONLY_NO_INSTALL_NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row
    converted_root = _write_converted_skill(
        str(converted["skill_markdown"]),
        slug=str(converted["skill_name"]),
    )
    installed = install_skill(
        converted_root,
        skills_dir=skills_dir,
        allow_overwrite=allow_overwrite,
        installed_by=installed_by,
    )
    installed["conversion"] = {k: v for k, v in converted.items() if k != "skill_markdown"}
    installed["life_fit_passed"] = True
    return installed


def pull_skill_from_url(
    url: str,
    *,
    skills_dir: str | Path | None = None,
    life_context: str | None = None,
    min_fit_score: float = 0.05,
    force_install: bool = False,
    allow_overwrite: bool = False,
    installed_by: str = "alice_skill_url_pull",
) -> dict[str, Any]:
    fetched = fetch_skill_from_url(url)
    if fetched.get("status") != "FETCHED":
        return fetched
    return ingest_skill_source(
        str(fetched["path"]),
        skills_dir=skills_dir,
        life_context=life_context,
        min_fit_score=min_fit_score,
        force_install=force_install,
        allow_overwrite=allow_overwrite,
        installed_by=installed_by,
    )


def _load_marketplace_manifest(source: str | Path | dict[str, Any]) -> tuple[dict[str, Any], str]:
    if isinstance(source, dict):
        return dict(source), "inline_manifest"
    source_s = str(source)
    parsed = urllib.parse.urlparse(source_s)
    if parsed.scheme in {"http", "https"}:
        fetched = fetch_skill_from_url(source_s)
        if fetched.get("status") != "FETCHED":
            raise ValueError(f"marketplace fetch failed: {fetched.get('reason') or fetched.get('error')}")
        path = Path(str(fetched["path"]))
        return json.loads(path.read_text(encoding="utf-8")), str(path)
    path = Path(source_s).expanduser().resolve()
    return json.loads(path.read_text(encoding="utf-8")), str(path)


def _marketplace_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("skills", manifest.get("entries", []))
    if isinstance(raw, dict):
        raw = list(raw.values())
    return [dict(x) for x in raw if isinstance(x, dict)]


def pull_skill_from_marketplace(
    marketplace: str | Path | dict[str, Any],
    *,
    skill_id: str = "",
    skills_dir: str | Path | None = None,
    life_context: str | None = None,
    min_fit_score: float = 0.05,
    force_install: bool = False,
    allow_overwrite: bool = False,
    installed_by: str = "alice_marketplace_pull",
) -> dict[str, Any]:
    manifest, manifest_ref = _load_marketplace_manifest(marketplace)
    entries = _marketplace_entries(manifest)
    if not entries:
        row = {
            "schema": SKILL_INSTALL_SCHEMA,
            "truth_label": "NANOBOT_MARKETPLACE_PULL_REFUSED",
            "status": "REFUSED",
            "reason": "marketplace_has_no_skills",
            "marketplace": manifest_ref,
        }
        _append_skill_receipt(row)
        return row
    requested = str(skill_id or "").strip().lower()
    chosen: dict[str, Any] | None = None
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for entry in entries:
        identity = " ".join(str(entry.get(k, "")) for k in ("id", "name", "title")).lower()
        summary = " ".join(str(entry.get(k, "")) for k in ("name", "title", "description", "summary", "tags"))
        fit = skill_life_fit(summary, life_context=life_context, explicit_request=bool(requested))
        scored.append((float(fit["score"]), entry, fit))
        if requested and requested in identity:
            chosen = entry
            chosen["_life_fit"] = fit
            break
    if chosen is None:
        scored.sort(key=lambda item: item[0], reverse=True)
        _score, chosen, fit = scored[0]
        chosen["_life_fit"] = fit
    score = float((chosen.get("_life_fit") or {}).get("score") or 0.0)
    if not force_install and score < float(min_fit_score):
        row = {
            "schema": SKILL_INSTALL_SCHEMA,
            "truth_label": "NANOBOT_MARKETPLACE_PULL_REVIEW",
            "status": "REVIEW",
            "reason": "best_skill_life_fit_below_threshold",
            "marketplace": manifest_ref,
            "chosen": chosen,
            "min_fit_score": min_fit_score,
            "resource_policy": "MARKETPLACE_SELECT_ONLY_NO_INSTALL_NO_SCRIPT_EXECUTION",
        }
        _append_skill_receipt(row)
        return row

    source_url = chosen.get("url") or chosen.get("skill_url")
    source_path = chosen.get("source_path") or chosen.get("path")
    if source_url:
        result = pull_skill_from_url(
            str(source_url),
            skills_dir=skills_dir,
            life_context=life_context,
            min_fit_score=0.0,
            force_install=True,
            allow_overwrite=allow_overwrite,
            installed_by=installed_by,
        )
    elif source_path:
        candidate = Path(str(source_path))
        if not candidate.is_absolute() and manifest_ref != "inline_manifest":
            candidate = Path(manifest_ref).parent / candidate
        result = ingest_skill_source(
            candidate,
            skills_dir=skills_dir,
            life_context=life_context,
            min_fit_score=0.0,
            force_install=True,
            allow_overwrite=allow_overwrite,
            installed_by=installed_by,
        )
    else:
        result = {
            "schema": SKILL_INSTALL_SCHEMA,
            "truth_label": "NANOBOT_MARKETPLACE_PULL_REFUSED",
            "status": "REFUSED",
            "reason": "chosen_skill_missing_url_or_source_path",
            "chosen": chosen,
        }
        _append_skill_receipt(result)
    result["marketplace"] = manifest_ref
    result["marketplace_choice"] = chosen
    return result


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _row_success(row: dict[str, Any]) -> bool:
    if bool(row.get("ok")) or bool(row.get("executed")) or bool((row.get("result") or {}).get("ok")):
        return True
    status = str(row.get("status") or row.get("type") or "").upper()
    return "EXECUTED" in status or status.endswith("_OK") or "SUCCESS" in status


def extract_skill_from_trace(
    *,
    trace_file: str | Path = "tool_router_trace.jsonl",
    trace_id: str = "",
    name: str = "",
    skills_dir: str | Path | None = None,
    life_context: str | None = None,
    allow_overwrite: bool = False,
    installed_by: str = "alice_trace_skill_extract",
) -> dict[str, Any]:
    path = Path(trace_file)
    if not path.is_absolute():
        path = _STATE_DIR / str(trace_file)
    rows = _jsonl_rows(path)
    chosen: dict[str, Any] | None = None
    wanted = str(trace_id or "").strip()
    if wanted:
        for row in rows:
            row_digest = hashlib.sha256(
                json.dumps(row, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            hay = {str(row.get(k, "")) for k in (
                "trace_id",
                "receipt_id",
                "kernel_process_receipt_id",
                "hash",
                "id",
            )}
            hay.add(row_digest)
            hay.add(row_digest[:16])
            if wanted in hay:
                chosen = row
                break
    else:
        for row in reversed(rows):
            if _row_success(row):
                chosen = row
                break
    if chosen is None:
        row = {
            "schema": SKILL_EXTRACT_SCHEMA,
            "truth_label": "NANOBOT_SKILL_EXTRACT_REFUSED",
            "status": "REFUSED",
            "reason": "matching_successful_trace_not_found",
            "trace_file": str(path),
            "trace_id": trace_id,
        }
        _append_skill_receipt(row)
        return row

    tool = str(chosen.get("tool_name") or chosen.get("tool") or chosen.get("type") or "trace_action")
    skill_name = _safe_skill_slug(name or f"repeat_{tool}")
    observed = json.dumps(chosen, indent=2, sort_keys=True, default=str)
    desc = f"Use when Alice needs to repeat or adapt the successful receipted action `{tool}`."
    meta = {
        "name": skill_name,
        "description": desc,
        "swimmer_type": "TRACE_LEARNED_SWIMMER",
        "action_type": "learn",
        "affect_lanes": ["SEEKING", "CARE"],
        "stgm_mint": 4.0,
        "pouw_label": skill_name.upper().replace("-", "_"),
        "version": 1,
        "homeworld_serial": _node_serial(),
        "trace_id": str(uuid.uuid4()),
        "source_trace_file": path.name,
    }
    body = f"""# {skill_name}

## Trigger
{desc}

## Procedure
1. Read the current user request and compare it to the observed successful trace.
2. Reuse the same tool boundary only when the new request matches the same intent.
3. Keep all side effects behind the deterministic SIFTA router and write a fresh receipt.

## Observed Successful Trace
```json
{observed[:5000]}
```
"""
    converted_root = _write_converted_skill(f"{_frontmatter_block(meta)}\n\n{body}", slug=skill_name)
    installed = install_skill(
        converted_root,
        skills_dir=skills_dir,
        allow_overwrite=allow_overwrite,
        installed_by=installed_by,
    )
    extract_row = {
        "schema": SKILL_EXTRACT_SCHEMA,
        "truth_label": "NANOBOT_SKILL_EXTRACT_RECEIPT",
        "status": installed.get("status"),
        "skill_name": skill_name,
        "trace_file": str(path),
        "source_trace_id": trace_id or chosen.get("trace_id") or chosen.get("receipt_id") or "",
        "installed_destination": installed.get("destination"),
        "life_fit": skill_life_fit(body, life_context=life_context, explicit_request=True),
        "resource_policy": "TRACE_TO_SKILL_NO_SCRIPT_EXECUTION",
    }
    _append_skill_receipt(extract_row)
    installed["extract"] = extract_row
    return installed


def load_procedure(skill_name: str, *, skills_dir: Path = _SKILLS_DIR) -> Optional[str]:
    """Load full procedure body for a skill (Tier 2). Returns Markdown text."""
    for s in build_skill_index(skills_dir):
        if s["name"] == skill_name:
            fn = s.get("procedure_file")
            if not fn:
                return None
            p = skills_dir / str(fn)
            if not p.exists():
                return None
            _meta, body = _parse_skill_markdown(p.read_text(encoding="utf-8"))
            return body
    return None


def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def match_skills(query: str, *, limit: int = 5, skills_dir: Path = _SKILLS_DIR) -> list[dict[str, Any]]:
    """Tier 1 trigger matching. Returns metadata only, never procedure text."""
    q_terms = _terms(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for skill in build_skill_index(skills_dir):
        hay = " ".join(
            [
                str(skill.get("name", "")),
                str(skill.get("description", "")),
                str(skill.get("swimmer_type", "")),
                str(skill.get("action_type", "")),
                " ".join(str(x) for x in skill.get("affect_lanes", [])),
            ]
        )
        s_terms = _terms(hay)
        overlap = len(q_terms & s_terms)
        score = float(overlap)
        if str(skill.get("name", "")).lower() in query.lower():
            score += 4.0
        if score <= 0:
            continue
        row = {
            "name": skill.get("name"),
            "description": skill.get("description"),
            "swimmer_type": skill.get("swimmer_type"),
            "action_type": skill.get("action_type"),
            "affect_lanes": skill.get("affect_lanes", []),
            "procedure_file": skill.get("procedure_file"),
            "procedure_exists": bool(skill.get("procedure_exists")),
            "community_style": bool(skill.get("community_style", False)),
            "resource_counts": skill.get("resource_counts", {}),
            "resource_policy": skill.get(
                "resource_policy",
                "INDEX_ONLY_NO_SCRIPT_EXECUTION",
            ),
            "score": score,
        }
        scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("name", ""))))
    return [row for _score, row in scored[:limit]]


def append_skill_selection_receipt(query: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Record skill routing without executing any skill resources."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": SKILL_SELECTION_SCHEMA,
        "ts": time.time(),
        "truth_label": "NANOBOT_SWIMMER_SKILL_ROUTING_RECEIPT",
        "query": query,
        "selected": matches,
        "resource_policy": "INDEX_ONLY_NO_SCRIPT_EXECUTION",
    }
    with _SKILL_RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ---------------------------------------------------------------------------
# Affect-weighted skill bias
# Reads alice_gag_report.jsonl + affect model state to weight skill selection
# ---------------------------------------------------------------------------

def compute_affect_skill_bias() -> dict[str, float]:
    """
    Returns a dict of action_type -> additional_weight based on current
    Panksepp circuit activations. Adds to crystallized skill mass.
    """
    bias: dict[str, float] = {}

    # Read recent gag events → RAGE/SUPPRESSED_PLAY activation
    gag_path = _STATE_DIR / "alice_gag_report.jsonl"
    gag_count = 0
    if gag_path.exists():
        lines = [l for l in gag_path.read_text().splitlines() if l.strip()]
        # Count gags in last hour
        cutoff = time.time() - 3600
        gag_count = sum(
            1 for l in lines[-20:]
            if json.loads(l).get("ts", 0) > cutoff
        )

    if gag_count > 0:
        # SUPPRESSED_PLAY → prioritize gag repair
        bias["repair"] = bias.get("repair", 0.0) + gag_count * 0.4
        bias["forage"] = bias.get("forage", 0.0) + gag_count * 0.2

    # Read desire field → SEEKING activation
    df_path = _STATE_DIR / "desire_field_state.json"
    if df_path.exists():
        try:
            df = json.loads(df_path.read_text())
            seeking_score = float(df.get("seeking", df.get("novelty_score", 0.5)))
            if seeking_score > 0.6:
                bias["explore"] = bias.get("explore", 0.0) + seeking_score * 0.5
                bias["learn"] = bias.get("learn", 0.0) + seeking_score * 0.3
        except Exception:
            pass

    # Read owner presence → CARE activation
    owner_path = _STATE_DIR / "tom_owner_state.json"
    if owner_path.exists():
        try:
            owner = json.loads(owner_path.read_text())
            present = owner.get("present", owner.get("is_home", False))
            if present:
                # CARE active: forage = monitoring George
                bias["forage"] = bias.get("forage", 0.0) + 0.6
        except Exception:
            pass

    # Read REM sleep state → LUST activation (generative drive)
    rem_path = _STATE_DIR / "rem_sleep_cycles.jsonl"
    if rem_path.exists():
        lines = [l for l in rem_path.read_text().splitlines() if l.strip()]
        if lines:
            try:
                rem = json.loads(lines[-1])
                if rem.get("state") == "ACTIVE_LEARNING":
                    bias["learn"] = bias.get("learn", 0.0) + 0.8
                    bias["code"] = bias.get("code", 0.0) + 0.5
            except Exception:
                pass

    return bias


# ---------------------------------------------------------------------------
# Skill index rendering
# ---------------------------------------------------------------------------

def render_index(swimmer_filter: Optional[str] = None) -> str:
    lines = ["=" * 64, "  SIFTA SKILL INDEX — Three-Tier Architecture", "=" * 64]
    for s in build_skill_index():
        if swimmer_filter and swimmer_filter.upper() not in s["swimmer_type"].upper():
            continue
        lines.append(f"\n{'─'*64}")
        lines.append(f"  [{s['status']}] {s['name']}")
        lines.append(f"  Swimmer:  {s['swimmer_type']}")
        lines.append(f"  Action:   {s['action_type']}  (+{s['stgm_mint']} STGM)")
        lines.append(f"  Affects:  {', '.join(s['affect_lanes'])}")
        lines.append(f"  Trigger:  {s['description'][:90]}")
        if s.get("procedure_file"):
            ok = bool(s.get("procedure_exists"))
            marker = "OK" if ok else "MISSING"
            tg_marker = " [TOURNAMENT GRADE]" if s.get("tournament_grade") else ""
            lines.append(f"  Tier2:    skills/{s['procedure_file']} {marker}{tg_marker}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--affect" in args:
        bias = compute_affect_skill_bias()
        print("\nAffect-weighted skill bias:")
        for k, v in sorted(bias.items(), key=lambda x: -x[1]):
            print(f"  {k:15s} +{v:.3f}")
        sys.exit(0)

    if "--query" in args:
        qi = args.index("--query")
        query = args[qi + 1] if qi + 1 < len(args) else ""
        matches = match_skills(query)
        if "--receipt" in args:
            append_skill_selection_receipt(query, matches)
        print(json.dumps(matches, indent=2, sort_keys=True))
        sys.exit(0)

    if "--validate" in args:
        print(json.dumps(validate_skill_contracts(), indent=2, sort_keys=True))
        sys.exit(0)

    if "--stigmergic-layers" in args:
        print(json.dumps(stigmergic_skill_layers(), indent=2, sort_keys=True))
        sys.exit(0)

    # Check if a swimmer type or skill name was passed
    swimmer = next((a for a in args if not a.startswith("--")), None)

    if swimmer:
        # Try to show tier 2 procedure
        proc = load_procedure(swimmer)
        if proc:
            print(f"\n=== TIER 2 PROCEDURE: {swimmer} ===\n")
            print(proc)
        else:
            print(render_index(swimmer_filter=swimmer))
    else:
        print(render_index())
        bias = compute_affect_skill_bias()
        if bias:
            print("\nCurrent affect bias:")
            for k, v in sorted(bias.items(), key=lambda x: -x[1]):
                print(f"  {k:15s} +{v:.3f}")


# ============================================================================
# REMOTE SKILL INGESTION + HERMES FORMAT CONVERSION + TRACE EXTRACTION
# (Completing the "pull from marketplace / Hermes" + "extract from life" gaps)
# ============================================================================

def _detect_skill_format(content: str) -> str:
    """Heuristic detection of skill format."""
    low = content.lower()
    if "hermes" in low or "nous" in low or "agent_skill" in low:
        return "hermes"
    if "name:" in low and "description:" in low and "action_type:" in low:
        return "sifta"
    if "```yaml" in low and "instructions:" in low:
        return "hermes"
    return "unknown"


def convert_hermes_to_sifta(hermes_content: str) -> dict[str, Any]:
    """
    Convert a Hermes-style skill (common in external agent marketplaces)
    into SIFTA's REQUIRED_SKILL_FIELDS + frontmatter format.
    This is the key adapter for "ingest any skill".
    """
    import yaml

    # Try to extract YAML frontmatter or JSON block
    frontmatter = {}
    body = hermes_content

    # Simple frontmatter extraction
    if hermes_content.startswith("---"):
        parts = hermes_content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
            except Exception:
                pass

    # Fallback: look for common Hermes keys
    name = frontmatter.get("name") or frontmatter.get("title") or "imported_hermes_skill"
    description = frontmatter.get("description") or frontmatter.get("summary") or "Imported from external Hermes-style skill"
    instructions = frontmatter.get("instructions") or body[:2000]

    # Map to SIFTA schema
    sifta_skill = {
        "name": str(name).lower().replace(" ", "_")[:64],
        "description": str(description)[:500],
        "swimmer_type": "GENERALIST_SWIMMER",
        "action_type": "general",
        "affect_lanes": ["SEEKING", "PLAY"],
        "stgm_mint": 10.0,
        "pouw_label": "IMPORTED_HERMES",
        "version": frontmatter.get("version", "0.1.0-hermes"),
        "source_format": "hermes",
        "original_instructions": instructions[:3000],
        "procedure": body,  # the main body becomes the procedure
    }

    # Ensure all required fields
    for field in REQUIRED_SKILL_FIELDS:
        if field not in sifta_skill:
            sifta_skill[field] = "" if field != "stgm_mint" else 5.0

    return sifta_skill


def fetch_and_convert_skill_from_url(
    url: str,
    *,
    auto_install: bool = False,
    installed_by: str = "alice_stigmergic_ingestion",
) -> dict[str, Any]:
    """
    Extended fetch that:
    - Pulls remote SKILL.md (SIFTA or Hermes format)
    - Detects format
    - Converts Hermes → SIFTA if needed
    - Validates
    - Optionally installs
    - Emits full receipt
    This enables "pull a skill from a remote URL or marketplace".
    """
    fetched = fetch_skill_from_url(url)
    if fetched.get("status") != "FETCHED":
        return fetched

    path = Path(fetched["path"])
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}

    fmt = _detect_skill_format(content)

    if fmt == "hermes":
        converted = convert_hermes_to_sifta(content)
        # Overwrite the fetched file with converted SIFTA version
        # (in real life we would keep both, but for simplicity we convert in place)
        sifta_md = f"""---
name: {converted['name']}
description: {converted['description']}
swimmer_type: {converted['swimmer_type']}
action_type: {converted['action_type']}
affect_lanes: {converted['affect_lanes']}
stgm_mint: {converted['stgm_mint']}
pouw_label: {converted['pouw_label']}
version: {converted['version']}
source: {url}
source_format: hermes
---

{converted.get('procedure', '')}
"""
        path.write_text(sifta_md, encoding="utf-8")
        fetched["converted_from"] = "hermes"
        fetched["converted_name"] = converted["name"]

    if auto_install:
        install_result = install_skill(path, installed_by=installed_by)
        fetched["install_result"] = install_result

    # Emit conversion receipt
    row = {
        "schema": "NANOBOT_SKILL_CONVERSION_RECEIPT_V1",
        "ts": time.time(),
        "url": url,
        "detected_format": fmt,
        "status": "CONVERTED" if fmt == "hermes" else "NATIVE",
        "path": str(path),
    }
    _append_skill_receipt(row)
    fetched["conversion_receipt"] = row

    return fetched


def extract_skill_from_successful_trace(trace: dict[str, Any], *, author: str = "alice") -> dict[str, Any]:
    """
    Turn a successful tool execution trace into a reusable SKILL.md.
    This is the "skill-extract UX from inside the UI / from life".
    The trace should contain at minimum: tool_name, params, result (success), context.
    """
    tool_name = str(trace.get("tool_name") or trace.get("name") or "unknown_tool")
    params = trace.get("params") or {}
    result_summary = str(trace.get("result") or trace.get("feedback_for_alice") or "")[:300]

    skill_name = f"replay_{tool_name}_{int(time.time())}".lower()[:48]

    skill = {
        "name": skill_name,
        "description": f"Replays successful {tool_name} execution observed in trace. {result_summary[:120]}",
        "swimmer_type": "GENERALIST_SWIMMER",
        "action_type": "replay",
        "affect_lanes": ["SEEKING", "PLAY"],
        "stgm_mint": 8.0,
        "pouw_label": f"EXTRACTED_FROM_TRACE_{tool_name.upper()}",
        "version": "0.1.0-extracted",
        "source_trace_id": trace.get("trace_id") or trace.get("receipt_hash"),
        "extracted_by": author,
        "procedure": f"""# Extracted skill: {skill_name}

## When to use
{trace.get('context', 'When the user wants to repeat this successful action.')}

## Parameters used in original success
{json.dumps(params, indent=2)}

## Expected outcome
{result_summary}
""",
    }

    # Save as SKILL.md in a proposals folder (stigmergic — other swimmers can review/vote)
    proposals_dir = _STATE_DIR / "skill_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    dest = proposals_dir / f"{skill_name}.md"
    dest.write_text(f"""---
name: {skill['name']}
description: {skill['description']}
swimmer_type: {skill['swimmer_type']}
action_type: {skill['action_type']}
affect_lanes: {skill['affect_lanes']}
stgm_mint: {skill['stgm_mint']}
pouw_label: {skill['pouw_label']}
version: {skill['version']}
extracted_from_trace: {skill.get('source_trace_id')}
---

{skill['procedure']}
""", encoding="utf-8")

    receipt = {
        "schema": "SKILL_EXTRACT_SCHEMA",
        "ts": time.time(),
        "skill_name": skill_name,
        "source_trace": trace.get("trace_id"),
        "path": str(dest),
        "status": "PROPOSED",
        "extracted_by": author,
    }
    _append_skill_receipt(receipt)

    return {"skill": skill, "path": str(dest), "receipt": receipt}


def propose_skill_for_field_need(need_description: str, *, context: dict | None = None) -> dict[str, Any]:
    """
    Stigmergic 'when need it based on life' ingestion trigger.
    Called by basal ganglia / field health monitor when an organ is low or a pattern repeats.
    Alice (as a warm entity of agents) can then decide to pull a remote skill or extract one.
    """
    receipt = {
        "schema": "NANOBOT_STIGMERGIC_SKILL_NEED_V1",
        "ts": time.time(),
        "need": need_description,
        "context": context or {},
        "status": "NEED_DECLARED",
        "swimmers_notified": ["MEMORY_SWIMMER", "EPI_CORTEX", "GENERALIST_SWIMMER"],
    }
    _append_skill_receipt(receipt)
    return receipt
