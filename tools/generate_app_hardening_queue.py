#!/usr/bin/env python3
"""Generate a manifest-grounded hardening queue for SIFTA apps.

This is intentionally static: it does not launch GUI apps. It checks that each
manifest entry points at a file, parses/compiles the file, and optionally finds
the declared widget class. The output is a work queue for IDE arms to harden one
app at a time with receipts.
"""

from __future__ import annotations

import ast
import json
import py_compile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "Applications" / "apps_manifest.json"
OUT_MD = REPO / "Documents" / "APP_HARDENING_QUEUE_2026-06-14.md"
OUT_JSON = REPO / "Documents" / "APP_HARDENING_QUEUE_2026-06-14.json"

OWNERS = ("Codex", "Grok", "MiMo", "Cline", "Cursor")


@dataclass
class AppCheck:
    index: int
    owner: str
    title: str
    entry_point: str
    widget_class: str
    category: str
    exists: bool
    syntax_ok: bool
    class_found: bool | None
    priority: str
    issues: list[str]


def _entry(meta: dict[str, Any]) -> str:
    return str(meta.get("entry_point") or meta.get("path") or "")


def _widget(meta: dict[str, Any]) -> str:
    return str(meta.get("widget_class") or meta.get("class") or "")


def _category(meta: dict[str, Any]) -> str:
    return str(meta.get("category") or "")


def _class_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return set()
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def check_apps() -> list[AppCheck]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows: list[AppCheck] = []
    for idx, (title, meta) in enumerate(sorted(manifest.items()), 1):
        entry = _entry(meta)
        widget = _widget(meta)
        category = _category(meta)
        owner = OWNERS[(idx - 1) % len(OWNERS)]
        issues: list[str] = []

        if not entry:
            issues.append("missing_entry_point")
            rows.append(
                AppCheck(idx, owner, title, entry, widget, category, False, False, None, "P0", issues)
            )
            continue

        path = (REPO / entry).resolve()
        exists = path.exists()
        syntax_ok = False
        class_found: bool | None = None
        if not exists:
            issues.append("missing_file")
        elif path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True)
                syntax_ok = True
            except py_compile.PyCompileError as exc:
                issues.append("syntax_error:" + str(exc.exc_value).replace("\n", " ")[:160])
            if widget:
                class_found = widget in _class_names(path)
                if not class_found:
                    issues.append("widget_class_not_found")
            else:
                class_found = None
                issues.append("missing_widget_class")
        else:
            syntax_ok = True
            if widget:
                class_found = None

        if any(issue.startswith("syntax_error") or issue in {"missing_file", "missing_entry_point"} for issue in issues):
            priority = "P0"
        elif "widget_class_not_found" in issues:
            priority = "P1"
        elif "missing_widget_class" in issues:
            priority = "P2"
        else:
            priority = "P3"

        rows.append(AppCheck(idx, owner, title, entry, widget, category, exists, syntax_ok, class_found, priority, issues))
    return rows


def write_outputs(rows: list[AppCheck]) -> None:
    counts = Counter(row.priority for row in rows)
    owner_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        owner_counts[row.owner][row.priority] += 1

    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": str(MANIFEST.relative_to(REPO)),
        "app_count": len(rows),
        "priority_counts": dict(counts),
        "rows": [asdict(row) for row in rows],
    }
    OUT_JSON.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    lines: list[str] = []
    lines.append("# SIFTA App Hardening Queue - 2026-06-14")
    lines.append("")
    lines.append("Generated from `Applications/apps_manifest.json` without launching GUI apps.")
    lines.append("George types only to Alice in global chat. IDE arms harden apps one by one; WE CODE TOGETHER only shows receipts/STGM.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Manifest apps: `{len(rows)}`")
    for priority in ("P0", "P1", "P2", "P3"):
        lines.append(f"- {priority}: `{counts.get(priority, 0)}`")
    lines.append("")
    lines.append("## Owner Split")
    lines.append("")
    for owner in OWNERS:
        c = owner_counts[owner]
        lines.append(
            f"- {owner}: total `{sum(c.values())}` | P0 `{c.get('P0', 0)}` | "
            f"P1 `{c.get('P1', 0)}` | P2 `{c.get('P2', 0)}` | P3 `{c.get('P3', 0)}`"
        )
    lines.append("")
    lines.append("## Rules")
    lines.append("")
    lines.append("- One app per patch unless a shared helper is required.")
    lines.append("- No owner-click write UI. George types to Alice; apps may display receipts/STGM.")
    lines.append("- Every mutation gets a four-ledger receipt and a tournament row.")
    lines.append("- Tests scale with risk: at minimum py_compile + manifest/class regression for each app.")
    lines.append("- Do not overclaim runtime behavior until launched or covered by a UI smoke harness.")
    lines.append("")
    lines.append("## Queue")
    lines.append("")
    lines.append("| # | Priority | Owner | App | Entry | Widget | Issues |")
    lines.append("|---:|---|---|---|---|---|---|")
    for row in rows:
        issues = ", ".join(row.issues) if row.issues else "ok"
        lines.append(
            f"| {row.index} | {row.priority} | {row.owner} | {row.title} | "
            f"`{row.entry_point}` | `{row.widget_class}` | {issues} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = check_apps()
    write_outputs(rows)
    print(json.dumps({
        "app_count": len(rows),
        "markdown": str(OUT_MD.relative_to(REPO)),
        "json": str(OUT_JSON.relative_to(REPO)),
        "priority_counts": dict(Counter(row.priority for row in rows)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
