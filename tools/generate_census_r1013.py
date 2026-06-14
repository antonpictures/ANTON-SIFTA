#!/usr/bin/env python3
"""Generate r1013 repo census bundle under Documents/census_r1013/."""
from __future__ import annotations

import ast
import json
import os
import re
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "Documents" / "census_r1013"
CAP_PER_FILE = 400
CAP_TOTAL = 2000

SCAN_DIRS = [
    REPO / "System",
    REPO / "tests",
    REPO / "scripts",
    REPO / "Documents",
    REPO / ".sifta_state",
]

ORGAN_KEYWORDS = {
    "memory": ["hippocampus", "memory", "engram", "jsonl_file_lock"],
    "voice": ["tts", "voice", "speak", "broca"],
    "vision": ["camera", "gaze", "screenshot", "browser_context", "face"],
    "tools": ["mcp", "slash_commands", "effector", "tool"],
    "protection": ["guard", "gate", "predator", "oauth", "permission"],
    "heart": ["heartbeat", "hardware_heart", "thermal", "metabolism", "battery"],
    "arms": ["cortex", "gemini_brain", "external_brain", "grok", "claude"],
    "owner": ["owner_heartbeat", "owner_genesis", "primary_operator"],
}

PY_GLOB_DIRS = [REPO / "System", REPO / "tests", REPO / "scripts", REPO / "Applications"]


def _cap_lines(lines: list[str], max_lines: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    head = max_lines - 3
    return lines[:head] + ["", f"... truncated at {max_lines} line cap ({len(lines)} total) ...", ""]


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("rb"))
    except Exception:
        return 0


def _mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except Exception:
        return "?"


def _build_reference_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for root in PY_GLOB_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = str(path.relative_to(REPO))
            for token in set(re.findall(r"[\w./_-]+\.jsonl?|[\w./_-]+\.ya?ml", text)):
                index.setdefault(token, []).append(rel)
    return index


def gen_tree() -> str:
    lines = ["# CENSUS_1_tree.md", f"Generated: {datetime.now().isoformat(timespec='seconds')}", ""]
    for root in SCAN_DIRS:
        if not root.exists():
            continue
        lines.append(f"## {root.relative_to(REPO)}")
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                if fn.startswith("."):
                    continue
                p = Path(dirpath) / fn
                if p.suffix in {".pyc", ".pyo"}:
                    continue
                rel = p.relative_to(REPO)
                loc = _count_lines(p)
                lines.append(f"- `{rel}` | loc={loc} | mtime={_mtime(p)}")
                if len(lines) >= CAP_PER_FILE - 2:
                    return "\n".join(_cap_lines(lines, CAP_PER_FILE))
    return "\n".join(_cap_lines(lines, CAP_PER_FILE))


def _module_info(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except Exception:
        return {"purpose": "parse failed", "entries": [], "imports": []}
    entries = []
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                entries.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("System."):
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "System" or node.module.startswith("System.")):
                imports.append(node.module)
    doc = ast.get_docstring(tree) or ""
    purpose = " ".join(doc.split())[:220] if doc else "(no module docstring)"
    return {"purpose": purpose, "entries": entries[:12], "imports": sorted(set(imports))[:10]}


def gen_modules() -> str:
    lines = ["# CENSUS_2_modules.md", ""]
    system = REPO / "System"
    for path in sorted(system.glob("*.py")):
        info = _module_info(path)
        lines.append(f"## {path.name}")
        lines.append(info["purpose"])
        if info["entries"]:
            lines.append(f"Entry points: {', '.join(info['entries'])}")
        if info["imports"]:
            lines.append(f"Internal imports: {', '.join(info['imports'])}")
        lines.append("")
        if len(lines) >= CAP_PER_FILE - 2:
            break
    return "\n".join(_cap_lines(lines, CAP_PER_FILE))


def gen_organs() -> str:
    lines = ["# CENSUS_3_organs.md", ""]
    assigned: set[str] = set()
    system = REPO / "System"
    for organ, keys in ORGAN_KEYWORDS.items():
        hits = []
        for path in sorted(system.glob("*.py")):
            name = path.name.lower()
            if any(k in name for k in keys):
                hits.append(path.name)
                assigned.add(path.name)
        lines.append(f"## {organ}")
        lines.append(", ".join(hits) if hits else "(no direct filename hits)")
        lines.append("")
    orphans = sorted(p.name for p in system.glob("*.py") if p.name not in assigned)
    lines.append("## orphans (no keyword organ match)")
    lines.append(", ".join(orphans[:80]))
    if len(orphans) > 80:
        lines.append(f"... and {len(orphans)-80} more")
    return "\n".join(_cap_lines(lines, CAP_PER_FILE))


def gen_ledgers(index: dict[str, list[str]]) -> str:
    lines = ["# CENSUS_4_ledgers.md", ""]
    state = REPO / ".sifta_state"
    for path in sorted(state.rglob("*.jsonl")):
        rel = path.relative_to(REPO)
        count = _count_lines(path)
        sample = ""
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                for ln in f:
                    if not ln.strip():
                        continue
                    obj = json.loads(ln)
                    if isinstance(obj, dict):
                        redacted = {k: ("<redacted>" if k in {"api_key", "token", "secret", "password"} else v)
                                    for k, v in obj.items()}
                        sample = json.dumps(redacted)[:200]
                    break
        except Exception as e:
            sample = f"read error: {e}"
        name = path.name
        rel_s = str(rel)
        readers = sorted(set(index.get(name, []) + index.get(rel_s, [])))[:5]
        lines.append(f"## `{rel}`")
        lines.append(f"rows≈{count} append_only=yes")
        lines.append(f"sample: {sample}")
        lines.append(f"readers: {', '.join(readers) or '?'}")
        lines.append("")
        if len(lines) >= CAP_PER_FILE - 2:
            break
    return "\n".join(_cap_lines(lines, CAP_PER_FILE))


def gen_health() -> str:
    lines = ["# CENSUS_5_health.md", ""]
    system_mods = {p.stem for p in (REPO / "System").glob("*.py")}
    tested = set()
    for t in (REPO / "tests").glob("test_*.py"):
        tested.add(t.stem.replace("test_", "", 1))
    lines.append("## test coverage (filename heuristic)")
    lines.append(f"System modules: {len(system_mods)} | modules with test_* file: {len(tested)}")
    untested = sorted(system_mods - tested)[:40]
    lines.append("zero-coverage sample: " + ", ".join(untested))
    lines.append("")
    lines.append("## TODO/FIXME/HACK (first 40)")
    count = 0
    for path in sorted((REPO / "System").glob("*.py")):
        try:
            for i, ln in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if re.search(r"TODO|FIXME|HACK", ln):
                    lines.append(f"- `{path.relative_to(REPO)}:{i}` {ln.strip()[:100]}")
                    count += 1
                    if count >= 40:
                        break
        except Exception:
            pass
        if count >= 40:
            break
    lines.append("")
    lines.append("## config census (top-level .sifta_state json, first 25)")
    state = REPO / ".sifta_state"
    for cfg in sorted(state.glob("*.json"))[:25]:
        lines.append(f"- `{cfg.relative_to(REPO)}` size={cfg.stat().st_size}")
    return "\n".join(_cap_lines(lines, CAP_PER_FILE))


def gen_hotpath() -> str:
    spine = """# CENSUS_6_hotpath.md

## Boot spine
1. sifta_os_desktop.py — SiftaDesktop boots; organs embedded (covenant §7.6).
2. swarm_boot.py — brainstem called by desktop.
3. sifta_talk_to_alice_widget.py — owner ingress / MDI mouth.
4. alice_conversation.jsonl — global chat append.
5. cortex_attached_models.json + swarm_alice_slash_commands.py — cortex/llm pins.
6. swarm_gemini_brain.py — grok_cli_model_for / arm dispatch.
7. work_receipts.jsonl + organ ledgers — receipt write.
8. Talk widget — reply egress.

## Heart tick (r1011+)
1. sifta_os_desktop._heartbeat_timer → _tick_heartbeat (~1 Hz).
2. swarm_alice_self_continuity.record_heartbeat(desktop_heartbeat).
3. pulse_hardware_heart(privileged_probe=False, source=desktop_heartbeat).
4. Tier ladder: alice_hardware_body → battery_metabolism → thermal_state.jsonl → powermetrics.
5. hardware_heart.jsonl + hardware_heart.json snapshot.
6. /heart slash — on-demand; may privileged_probe=True.

## Grok alias chain
- Settings/cortex: grok:grok-4.3
- grok_cli_model_for: alias grok-4.3 → grok-build unless SIFTA_GROK_CLI_MODEL pin or demoted.
- grok_cli_model_health.jsonl records timeout demotions (8fba3a76 lane).
"""
    return "\n".join(_cap_lines(spine.strip().splitlines(), CAP_PER_FILE))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = _build_reference_index()
    files = {
        "CENSUS_1_tree.md": gen_tree(),
        "CENSUS_2_modules.md": gen_modules(),
        "CENSUS_3_organs.md": gen_organs(),
        "CENSUS_4_ledgers.md": gen_ledgers(index),
        "CENSUS_5_health.md": gen_health(),
        "CENSUS_6_hotpath.md": gen_hotpath(),
    }
    total_lines = 0
    for name, content in files.items():
        path = OUT / name
        path.write_text(content + "\n", encoding="utf-8")
        n = content.count("\n") + 1
        total_lines += n
        print(f"Wrote {path} ({n} lines)")
    print(f"TOTAL_LINES={total_lines} (cap {CAP_TOTAL})")


if __name__ == "__main__":
    main()