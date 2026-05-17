#!/usr/bin/env python3
"""Consumer surface status for SIFTA Home.

This module is intentionally headless.  The Qt widget renders these rows,
and the Talk tool router can return the same status with a receipt.  The
goal is the Hermes-style surface without creating a second organism: one
normal-human home screen over the existing organs, skills, tools, and distro
checklist.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "consumer_surface_trace.jsonl"
_HEAD = _STATE / "consumer_surface_head.json"

TRUTH_LABEL = "SIFTA_CONSUMER_SURFACE_V1"
TRACE_SCHEMA = "SIFTA_CONSUMER_SURFACE_TRACE_V1"

PAGE_OVERVIEW = "overview"
PAGE_OOBE = "oobe"
PAGE_ORGANS = "organs"
PAGE_SKILLS = "skills"
PAGE_TOOLS = "tools"
PAGE_DISCOVERY = "discovery"
PAGE_DISTRO = "distro"

PAGE_TITLES: dict[str, str] = {
    PAGE_OVERVIEW: "Overview",
    PAGE_OOBE: "First Boot",
    PAGE_ORGANS: "Organ Manager",
    PAGE_SKILLS: "Skill Browser",
    PAGE_TOOLS: "Talk Tools",
    PAGE_DISCOVERY: "Discovery",
    PAGE_DISTRO: "Public Distro",
}

SURFACE_APP_NAMES = (
    "Owner Genesis",
    "Organism Doctor",
    "SIFTA Skill Browser",
    "Alice Browser",
    "Alice Journal",
    "Alice Wellbeing Cortex",
    "Alice Shell",
    "IDE Control Panel",
    "STGM Immune Economy",
    "Finance",
    "Stigmerobotics",
)

SURFACE_TOOL_NAMES = (
    "consumer_surface_status",
    "organ_registry_lookup",
    "self_improvement_status",
    "stigmergic_bus_tail",
    "repo_git_snapshot",
    "ollama_inventory",
    "run_local_command",
    "web_research",
    "repo_patch",
    "run_terminal",
    "read_file",
    "write_file",
    "edit_file",
    "list_dir",
    "fetch_url",
    "search_web",
    "skill_library_status",
    "skill_pull",
    "skill_extract_from_trace",
    "skill_autoproposal_scan",
)


@dataclass(frozen=True)
class SurfaceApp:
    name: str
    category: str
    entry_point: str
    widget_class: str
    status: str
    description: str


@dataclass(frozen=True)
class SurfaceTool:
    name: str
    mode: str
    required_params: tuple[str, ...]
    optional_params: tuple[str, ...]
    description: str
    talk_call: str


@dataclass(frozen=True)
class SurfaceSkill:
    name: str
    status: str
    action_type: str
    swimmer_type: str
    stgm_mint: float
    procedure_exists: bool


@dataclass(frozen=True)
class OobeStep:
    order: int
    title: str
    status: str
    action: str
    proof: str


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _manifest(repo_root: Path = _REPO) -> dict[str, Any]:
    path = repo_root / "Applications" / "apps_manifest.json"
    data = _safe_json(path)
    return data if isinstance(data, dict) else {}


def _path_status(repo_root: Path, rel: str) -> str:
    if not rel:
        return "missing"
    return "present" if (repo_root / rel).exists() else "missing"


def surface_apps(repo_root: Path = _REPO) -> list[SurfaceApp]:
    apps = _manifest(repo_root)
    rows: list[SurfaceApp] = []
    for name in SURFACE_APP_NAMES:
        entry = apps.get(name)
        if not isinstance(entry, dict):
            continue
        if entry.get("_retired") or entry.get("hidden"):
            continue
        rel = str(entry.get("entry_point") or "")
        rows.append(
            SurfaceApp(
                name=name,
                category=str(entry.get("category") or "Utilities"),
                entry_point=rel,
                widget_class=str(entry.get("widget_class") or ""),
                status=_path_status(repo_root, rel),
                description=str(entry.get("description") or "")[:220],
            )
        )
    return rows


def _talk_call(tool_name: str, required: Iterable[str], optional: Iterable[str]) -> str:
    parts = [f"{key}=..." for key in required]
    if tool_name == "consumer_surface_status":
        parts = ["page=overview"]
    elif tool_name == "run_local_command":
        parts = ["command=pwd"]
    elif tool_name == "web_research":
        parts = ["query=what is SIFTA OS"]
    elif tool_name == "repo_patch":
        parts = ["path=...", "old_text=...", "new_text=..."]
    elif tool_name == "organ_registry_lookup":
        parts = ["query=health tools skills distro"]
    elif tool_name == "fetch_url":
        parts = ["url=https://example.com"]
    elif tool_name == "search_web":
        parts = ["query=SIFTA OS"]
    elif tool_name == "stigmergic_bus_tail":
        parts = ["lines=12"]
    elif tool_name == "skill_pull":
        parts = ["marketplace=...", "life_context=current owner need"]
    elif tool_name == "skill_extract_from_trace":
        parts = ["trace_file=tool_router_trace.jsonl", "name=repeat_success"]
    elif tool_name == "skill_autoproposal_scan":
        parts = ["allow_pull=false", "min_repeat=3"]
    elif not parts and tuple(optional):
        first = tuple(optional)[0]
        parts = [f"{first}=..."]
    parts.append("cost_justification=show the consumer surface with receipts")
    return f"[TOOL_CALL: {tool_name} | {' | '.join(parts)}]"


def talk_tools() -> list[SurfaceTool]:
    try:
        from System.swarm_tool_router import TOOL_REGISTRY
    except Exception:
        TOOL_REGISTRY = {}
    rows: list[SurfaceTool] = []
    for name in SURFACE_TOOL_NAMES:
        spec = TOOL_REGISTRY.get(name)
        if spec is None:
            continue
        required = tuple(getattr(spec, "required_params", ()) or ())
        optional = tuple(getattr(spec, "optional_params", ()) or ())
        rows.append(
            SurfaceTool(
                name=name,
                mode="WRITE" if bool(getattr(spec, "write_action", True)) else "READ",
                required_params=required,
                optional_params=optional,
                description=str(getattr(spec, "description", ""))[:260],
                talk_call=_talk_call(name, required, optional),
            )
        )
    return rows


def top_skills(repo_root: Path = _REPO, limit: int = 12) -> list[SurfaceSkill]:
    try:
        from System.swarm_skill_library import build_skill_index

        skills = build_skill_index(repo_root / "skills")
    except Exception:
        skills = []
    ranked = sorted(
        skills,
        key=lambda s: (
            bool(s.get("procedure_exists")),
            float(s.get("stgm_mint") or 0.0),
            str(s.get("name") or ""),
        ),
        reverse=True,
    )
    out: list[SurfaceSkill] = []
    for skill in ranked[:limit]:
        out.append(
            SurfaceSkill(
                name=str(skill.get("name") or ""),
                status=str(skill.get("status") or "UNKNOWN"),
                action_type=str(skill.get("action_type") or "unknown"),
                swimmer_type=str(skill.get("swimmer_type") or "UNKNOWN"),
                stgm_mint=float(skill.get("stgm_mint") or 0.0),
                procedure_exists=bool(skill.get("procedure_exists")),
            )
        )
    return out


def latest_skill_proposals(limit: int = 8) -> list[dict[str, Any]]:
    try:
        from System.swarm_skill_autoproposal import latest_proposals

        return latest_proposals(limit=limit)
    except Exception:
        return []


def distro_status(repo_root: Path = _REPO) -> dict[str, Any]:
    markers = {
        "distro_doctrine": repo_root / "Documents" / "SIFTA_DISTRO_DOCTRINE_v2.md",
        "public_push_checklist": repo_root / "Documents" / "PUBLIC_PUSH_CHECKLIST.md",
        "scrubber": repo_root / "scripts" / "distro_scrubber.py",
        "sandbox_tree": repo_root / ".simulation_publicpush_sandbox",
        "distro_build": repo_root / ".distro_build",
    }
    exports = repo_root / "exports"
    demo_assets = []
    if exports.exists():
        for pattern in ("*OOBE*", "*oobe*", "*90*demo*", "*90*Demo*"):
            demo_assets.extend(str(p.relative_to(repo_root)) for p in exports.glob(pattern) if p.is_file())
    try:
        remote = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=4,
        ).stdout.strip()
    except Exception:
        remote = ""
    checks = {name: path.exists() for name, path in markers.items()}
    blockers: list[str] = []
    if not checks["scrubber"]:
        blockers.append("scripts/distro_scrubber.py is missing")
    if not checks["public_push_checklist"]:
        blockers.append("Documents/PUBLIC_PUSH_CHECKLIST.md is missing")
    if not checks["distro_build"]:
        blockers.append(".distro_build is not present; run the scrubber before public push")
    if not demo_assets:
        blockers.append("No 90-second OOBE demo video asset found under exports/")
    if "SIFTA-OS" not in remote:
        blockers.append("Local remote is not the public SIFTA-OS distro remote")
    return {
        "checks": checks,
        "demo_assets": sorted(set(demo_assets)),
        "remote": remote,
        "status": "READY_TO_VERIFY" if not blockers else "SURFACE_GAP_OPEN",
        "blockers": blockers,
        "truth_note": (
            "Local file checks only. GitHub stars/downloads and public push state "
            "must be proven by an explicit release or GitHub probe."
        ),
    }


def oobe_steps(repo_root: Path = _REPO) -> list[OobeStep]:
    apps = {row.name: row for row in surface_apps(repo_root)}
    distro = distro_status(repo_root)

    def app_status(name: str) -> str:
        row = apps.get(name)
        return "READY" if row and row.status == "present" else "MISSING"

    return [
        OobeStep(
            1,
            "Create owner genesis",
            app_status("Owner Genesis"),
            "Open Owner Genesis and bind this Mac to the local owner.",
            ".sifta_state/owner_genesis.json",
        ),
        OobeStep(
            2,
            "Open organism health",
            app_status("Organism Doctor"),
            "Open Organism Doctor and show a HEALTHY/WARNING/CRITICAL verdict.",
            ".sifta_state/organism_doctor_trace.jsonl or rendered health rows",
        ),
        OobeStep(
            3,
            "Show skill library",
            app_status("SIFTA Skill Browser"),
            "Open Skill Browser and click one Tier 2 procedure.",
            "skills/*.md and nanobot_skill_receipts.jsonl",
        ),
        OobeStep(
            4,
            "Use Talk tool receipt",
            "READY" if any(t.name == "consumer_surface_status" for t in talk_tools()) else "MISSING",
            "Ask Talk for consumer_surface_status; prove the answer came through the router.",
            ".sifta_state/tool_router_trace.jsonl",
        ),
        OobeStep(
            5,
            "Scrub public distro",
            "READY" if distro["checks"].get("scrubber") else "MISSING",
            "Run scripts/distro_scrubber.py into .distro_build and inspect PUBLIC_PUSH_CHECKLIST.",
            ".distro_build/ plus scrubber output",
        ),
        OobeStep(
            6,
            "Record 90-second demo",
            "READY" if distro["demo_assets"] else "OPEN",
            "Record boot -> Owner Genesis -> Talk tool -> Skill Browser -> Organism Doctor.",
            "exports/*OOBE* or exports/*90*demo*",
        ),
    ]


def build_snapshot(repo_root: Path = _REPO) -> dict[str, Any]:
    apps = surface_apps(repo_root)
    tools = talk_tools()
    skills = top_skills(repo_root)
    distro = distro_status(repo_root)
    steps = oobe_steps(repo_root)
    proposals = latest_skill_proposals()
    ready_steps = sum(1 for step in steps if step.status == "READY")
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "repo_root": str(repo_root),
        "surface_gap": (
            "Deep organs exist; the normal-human surface is the product gap: "
            "home screen, OOBE path, tool receipts, skill browser, scrubbed distro, demo video."
        ),
        "apps": [asdict(row) for row in apps],
        "tools": [asdict(row) for row in tools],
        "skills": [asdict(row) for row in skills],
        "skill_proposals": proposals,
        "oobe_steps": [asdict(row) for row in steps],
        "oobe_ready": {"ready": ready_steps, "total": len(steps)},
        "distro": distro,
    }


def render_page(page: str = PAGE_OVERVIEW, *, repo_root: Path = _REPO) -> str:
    page = (page or PAGE_OVERVIEW).strip().lower()
    if page not in PAGE_TITLES:
        page = PAGE_OVERVIEW
    snap = build_snapshot(repo_root)
    lines: list[str] = [f"# SIFTA Home - {PAGE_TITLES[page]}", ""]

    if page == PAGE_OVERVIEW:
        lines.extend(
            [
                snap["surface_gap"],
                "",
                f"OOBE readiness: {snap['oobe_ready']['ready']}/{snap['oobe_ready']['total']} steps ready",
                f"Surface apps: {len(snap['apps'])}",
                f"Talk tools exposed: {len(snap['tools'])}",
                f"Top skills indexed: {len(snap['skills'])}",
                f"Field proposals: {len(snap['skill_proposals'])}",
                f"Distro status: {snap['distro']['status']}",
                "",
                "Normal-human path: First Boot -> Discovery -> Talk Tools -> Skill Browser -> Organ Manager -> Public Distro.",
            ]
        )
    elif page == PAGE_OOBE:
        for step in snap["oobe_steps"]:
            lines.append(f"{step['order']}. {step['title']} [{step['status']}]")
            lines.append(f"   Action: {step['action']}")
            lines.append(f"   Proof: {step['proof']}")
    elif page == PAGE_ORGANS:
        for app in snap["apps"]:
            lines.append(f"- {app['name']} [{app['status']}]")
            lines.append(f"  {app['category']} :: {app['entry_point']} :: {app['widget_class']}")
            if app["description"]:
                lines.append(f"  {app['description']}")
    elif page == PAGE_SKILLS:
        for skill in snap["skills"]:
            proc = "procedure" if skill["procedure_exists"] else "index-only"
            lines.append(
                f"- {skill['name']} [{skill['status']}] {proc}; "
                f"{skill['action_type']} via {skill['swimmer_type']}; +{skill['stgm_mint']:.0f} STGM"
            )
    elif page == PAGE_TOOLS:
        for tool in snap["tools"]:
            params = ", ".join(tool["required_params"]) or "none"
            lines.append(f"- {tool['name']} [{tool['mode']}] required: {params}")
            lines.append(f"  {tool['description']}")
            lines.append(f"  Talk: {tool['talk_call']}")
    elif page == PAGE_DISCOVERY:
        lines.extend(
            [
                "Field-driven setup: Alice scans repeated successes, health drops, marketplace matches, and distro/OOBE blockers.",
                "Default behavior writes proposals only. Passing allow_pull=true allows install/extract through skill receipts.",
                "",
                "[TOOL_CALL: skill_autoproposal_scan | allow_pull=false | min_repeat=3 | cost_justification=Alice should inspect local field traces and propose needed skills]",
                "",
            ]
        )
        if snap["skill_proposals"]:
            lines.append("Latest proposals:")
            for proposal in snap["skill_proposals"]:
                lines.append(
                    f"- {proposal.get('proposal_type', 'PROPOSAL')}: {proposal.get('title', 'untitled')} "
                    f"(confidence {float(proposal.get('confidence') or 0.0):.2f})"
                )
                if proposal.get("reason"):
                    lines.append(f"  {proposal['reason']}")
                if proposal.get("suggested_tool_call"):
                    lines.append(f"  Talk: {proposal['suggested_tool_call']}")
        else:
            lines.append("No proposals observed yet. Press Scan Field in SIFTA Home or call skill_autoproposal_scan.")
        lines.append("")
        dist = snap["distro"]
        lines.append(f"OOBE/distro status: {dist['status']}")
        if dist["blockers"]:
            lines.extend(f"- {blocker}" for blocker in dist["blockers"][:5])
    elif page == PAGE_DISTRO:
        dist = snap["distro"]
        lines.append(f"Status: {dist['status']}")
        lines.append(f"Remote: {dist['remote'] or 'not observed'}")
        for name, ok in dist["checks"].items():
            lines.append(f"- {name}: {'present' if ok else 'missing'}")
        if dist["demo_assets"]:
            lines.append("Demo assets:")
            lines.extend(f"- {asset}" for asset in dist["demo_assets"])
        if dist["blockers"]:
            lines.append("Blockers:")
            lines.extend(f"- {blocker}" for blocker in dist["blockers"])
        lines.append(dist["truth_note"])
    return "\n".join(lines).strip() + "\n"


def _last_hash(state_dir: Path) -> str:
    data = _safe_json(state_dir / _HEAD.name)
    last = data.get("last_hash")
    return str(last) if last else "genesis"


def _write_head(state_dir: Path, new_hash: str) -> None:
    path = state_dir / _HEAD.name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"last_hash": new_hash}, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def write_surface_receipt(
    *,
    action: str,
    page: str = PAGE_OVERVIEW,
    payload: dict[str, Any] | None = None,
    state_dir: Path = _STATE,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": TRACE_SCHEMA,
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "action": action,
        "page": page,
        "payload": payload or {},
        "prev_hash": _last_hash(state_dir),
    }
    row["hash"] = hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    line = json.dumps(row, sort_keys=True, default=str) + "\n"
    trace = state_dir / _TRACE.name
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(trace, line)
    except Exception:
        with trace.open("a", encoding="utf-8") as f:
            f.write(line)
    _write_head(state_dir, row["hash"])
    return row


def surface_summary_for_talk(
    *,
    page: str = PAGE_OVERVIEW,
    repo_root: Path = _REPO,
    state_dir: Path = _STATE,
) -> dict[str, Any]:
    text = render_page(page, repo_root=repo_root)
    receipt = write_surface_receipt(
        action="talk_status_rendered",
        page=page,
        payload={"chars": len(text)},
        state_dir=state_dir,
    )
    return {
        "ok": True,
        "status": "CONSUMER_SURFACE_STATUS",
        "page": page,
        "summary": text,
        "receipt_id": receipt["trace_id"],
        "receipt_hash": receipt["hash"],
        "alice_summary": (
            f"consumer_surface_status {page}: receipt={receipt['trace_id'][:16]}\n{text}"
        ),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render SIFTA consumer surface status.")
    parser.add_argument("page", nargs="?", default=PAGE_OVERVIEW, choices=sorted(PAGE_TITLES))
    parser.add_argument("--receipt", action="store_true", help="write a consumer surface receipt")
    args = parser.parse_args()
    print(render_page(args.page), end="")
    if args.receipt:
        receipt = write_surface_receipt(action="cli_render", page=args.page, payload={})
        print(f"receipt={receipt['trace_id']} hash={receipt['hash'][:16]}")
