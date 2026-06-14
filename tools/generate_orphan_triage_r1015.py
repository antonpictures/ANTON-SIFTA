#!/usr/bin/env python3
"""ORPHAN_TRIAGE.md for r1015 — mechanical orphan tagging, no deletions."""
from __future__ import annotations

import ast
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "Documents" / "census_r1013" / "ORPHAN_TRIAGE.md"
APPENDIX = REPO / "Documents" / "census_r1013" / "ORPHAN_TRIAGE_APPENDIX.md"
CAP = 400

ORGAN_KEYS = {
    "memory": ("memory", "hippocampus", "engram"),
    "voice": ("voice", "broca", "wernicke", "speech", "tts"),
    "vision": ("vision", "camera", "gaze", "browser", "face"),
    "heart": ("heart", "thermal", "metabolism", "battery"),
    "protection": ("guard", "gate", "predator", "oauth"),
    "arms": ("cortex", "grok", "gemini", "brain"),
}


def _imports_of(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


def _build_importers() -> dict[str, list[str]]:
    importers: dict[str, list[str]] = defaultdict(list)
    for root in (REPO / "System", REPO / "tests", REPO / "Applications", REPO / "scripts"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            mod = path.stem
            for imp in _imports_of(path):
                if imp == "System":
                    try:
                        rel = path.relative_to(REPO)
                        importers[mod].append(str(rel))
                    except Exception:
                        pass
    return importers


def _tag_module(name: str) -> str:
    low = name.lower()
    for organ, keys in ORGAN_KEYS.items():
        if any(k in low for k in keys):
            return organ
    if "2026-04" in low or name.startswith("swarm_") is False:
        return "apoptosis_candidate"
    return "unassigned"


def main() -> None:
    system = REPO / "System"
    modules = sorted(p.name for p in system.glob("*.py"))
    importers = _build_importers()
    grouped: dict[str, list[str]] = defaultdict(list)
    orphan_count = 0
    for name in modules:
        stem = name[:-3]
        refs = importers.get(stem, [])
        if refs:
            continue
        orphan_count += 1
        grouped[_tag_module(stem)].append(stem)

    lines = [
        "# ORPHAN_TRIAGE.md",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"System modules: {len(modules)} | zero-import orphans: {orphan_count}",
        "",
        "## Grouped counts (triage only — no deletions)",
    ]
    for tag in sorted(grouped):
        lines.append(f"- **{tag}**: {len(grouped[tag])}")
    lines.append("")
    lines.append("## Sample orphans per group (first 8 each)")
    for tag in sorted(grouped):
        lines.append(f"### {tag}")
        lines.append(", ".join(grouped[tag][:8]))
        if len(grouped[tag]) > 8:
            lines.append(f"... +{len(grouped[tag]) - 8} more in appendix")
        lines.append("")

    appendix_lines = ["# ORPHAN_TRIAGE_APPENDIX — full orphan list", ""]
    for tag in sorted(grouped):
        appendix_lines.append(f"## {tag} ({len(grouped[tag])})")
        for stem in grouped[tag]:
            appendix_lines.append(f"- `{stem}.py`")
        appendix_lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(_cap_lines(lines, CAP)) + "\n", encoding="utf-8")
    APPENDIX.write_text("\n".join(appendix_lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} and {APPENDIX}")


def _cap_lines(lines: list[str], max_lines: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    return lines[: max_lines - 2] + ["", f"... truncated at {max_lines} lines"]


if __name__ == "__main__":
    main()