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
  python3 -m System.swarm_skill_library MEMORY_SWIMMER  # show tier 2 procedure
"""
from __future__ import annotations

import json
import hashlib
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _REPO / "skills"
_STATE_DIR = _REPO / ".sifta_state"
_SKILL_RECEIPTS = _STATE_DIR / "nanobot_skill_receipts.jsonl"
SKILL_SELECTION_SCHEMA = "NANOBOT_SWIMMER_SKILL_SELECTION_V1"
SKILL_CONTRACT_SCHEMA = "NANOBOT_SKILL_CONTRACT_REPORT_V1"

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
