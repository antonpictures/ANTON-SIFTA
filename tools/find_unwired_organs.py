#!/usr/bin/env python3
"""find_unwired_organs.py — source-level organ wiring census.

This is a triage scanner, not a verdict engine. It answers George's question:
"what amazing organs exist but may not be wired into Alice's living body?"

Signals:
  - organ-like file names and in-file truth labels / ledgers / public APIs
  - tests/docs mentioning the module
  - live non-test source references to the module, stem, or public symbols

The report deliberately separates "unwired candidate" from "weakly wired";
dynamic plugin/app-store loading can hide real wiring from static analysis.
Doctors inspect the ranked list before cutting.
"""
from __future__ import annotations

import ast
import json
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, TypedDict

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
OUT_JSON = STATE / "unwired_organs_report.json"
OUT_MD = STATE / "unwired_organs_report.md"

SCAN_ROOTS = ("System", "Applications", "Kernel", "Network", "tools")
REFERENCE_ROOTS = ("System", "Applications", "Kernel", "Network", "tools", "tests", "Documents")
SKIP_PARTS = {"build", "dist", "__pycache__", ".venv", "venv", "node_modules"}

ORGAN_STEM_RE = re.compile(
    r"(swarm_|sifta_|alice_|owner_|cortex|organ|field|diary|journal|memory|"
    r"heartbeat|continuity|lifeline|sleep|dream|sense|sensor|effector|router|"
    r"reflex|vision|voice|body|truth|receipt|ledger|stigm)",
    re.IGNORECASE,
)


@dataclass
class ModuleInfo:
    file: str
    module: str
    stem: str
    organ_score: int
    public_functions: list[str]
    public_classes: list[str]
    truth_labels: list[str]
    ledgers: list[str]
    has_main: bool
    live_reference_count: int
    test_reference_count: int
    doc_reference_count: int
    live_reference_files: list[str]
    test_reference_files: list[str]
    doc_reference_files: list[str]
    status: str
    reason: str


def _skip(path: Path) -> bool:
    try:
        parts = set(path.relative_to(REPO).parts)
    except Exception:
        parts = set(path.parts)
    return bool(parts & SKIP_PARTS)


def _python_files(roots: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        base = REPO / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if _skip(path):
                continue
            out.append(path)
    return sorted(out)


def _reference_files() -> list[Path]:
    files: list[Path] = []
    for root in REFERENCE_ROOTS:
        base = REPO / root
        if not base.exists():
            continue
        for suffix in ("*.py", "*.md", "*.txt", "*.json", "*.jsonl"):
            for path in base.rglob(suffix):
                if not _skip(path):
                    files.append(path)
    return sorted(set(files))


class RefIndex(TypedDict):
    rel: str
    bucket: str
    identifiers: set[str]


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _reference_index() -> list[RefIndex]:
    index: list[RefIndex] = []
    for path in _reference_files():
        rel = str(path.relative_to(REPO))
        text = _safe_read(path)
        if not text:
            continue
        if rel.startswith("tests/") or "/test_" in rel or rel.endswith("_test.py"):
            bucket = "test"
        elif rel.startswith("Documents/") or path.suffix.lower() in {".md", ".txt"}:
            bucket = "doc"
        else:
            bucket = "live"
        index.append({"rel": rel, "bucket": bucket, "identifiers": set(_IDENT_RE.findall(text))})
    return index


# r961 speed fix (cowork_claude, helping Codex): the per-candidate set
# intersection against every reference file is O(candidates x refs) and choked
# on this 2.3k-file repo (Codex's session timed out twice). Invert once:
# identifier -> {(rel, bucket)}. Each candidate is then a few dict lookups +
# small unions instead of thousands of full-set intersections.
def _inverted_index(reference_index: list[RefIndex]) -> dict:
    inv: dict = {}
    for ref in reference_index:
        post = (ref["rel"], ref["bucket"])
        for ident in ref["identifiers"]:
            inv.setdefault(ident, []).append(post)
    return inv


def _module_name(path: Path) -> str:
    rel = path.relative_to(REPO).with_suffix("")
    return ".".join(rel.parts)


def _literal_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _parse_info(path: Path) -> tuple[list[str], list[str], list[str], list[str], bool]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except Exception:
        return [], [], [], [], False
    funcs: list[str] = []
    classes: list[str] = []
    truth: list[str] = []
    ledgers: list[str] = []
    has_main = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
        elif isinstance(node, ast.Assign):
            names = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
            value = _literal_string(node.value)
            for name in names:
                upper = name.upper()
                if "TRUTH" in upper or upper.endswith("_LABEL"):
                    if value:
                        truth.append(value)
                if "LEDGER" in upper or upper.endswith("_NAME"):
                    if value and (value.endswith(".jsonl") or value.endswith(".json")):
                        ledgers.append(value)
        elif isinstance(node, ast.If):
            src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
            if "__name__" in src and "__main__" in src:
                has_main = True
    return funcs, classes, sorted(set(truth)), sorted(set(ledgers)), has_main


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _count_refs(path: Path, tokens: list[str], inverted: dict) -> tuple[int, int, int, list[str], list[str], list[str]]:
    live_files: set[str] = set()
    test_files: set[str] = set()
    doc_files: set[str] = set()
    self_rel = str(path.relative_to(REPO))
    token_set = {tok for tok in tokens if tok and "." not in tok}
    module_parts = {
        part
        for tok in tokens if "." in tok
        for part in tok.split(".")
        if part and part not in {"System", "Applications", "Kernel", "Network", "tools"}
    }
    token_set |= module_parts
    for tok in token_set:
        for rel, bucket in inverted.get(tok, ()):  # r961: inverted lookup
            if rel == self_rel:
                continue
            if bucket == "test":
                test_files.add(rel)
            elif bucket == "doc":
                doc_files.add(rel)
            else:
                live_files.add(rel)
    return (
        len(live_files),
        len(test_files),
        len(doc_files),
        sorted(live_files)[:8],
        sorted(test_files)[:8],
        sorted(doc_files)[:8],
    )


def _organ_score(path: Path, funcs: list[str], classes: list[str], truth: list[str], ledgers: list[str]) -> int:
    score = 0
    stem = path.stem
    if ORGAN_STEM_RE.search(stem):
        score += 3
    score += min(4, len(funcs))
    score += min(3, len(classes))
    if truth:
        score += 4
    if ledgers:
        score += 3
    if stem.startswith("test_") or str(path.relative_to(REPO)).startswith("tests/"):
        score -= 10
    return score


def scan() -> dict:
    source_files = _python_files(SCAN_ROOTS)
    reference_index = _reference_index()
    inverted = _inverted_index(reference_index)  # r961: build once
    rows: list[ModuleInfo] = []
    for path in source_files:
        rel = str(path.relative_to(REPO))
        if rel.startswith("tests/"):
            continue
        funcs, classes, truth, ledgers, has_main = _parse_info(path)
        score = _organ_score(path, funcs, classes, truth, ledgers)
        if score < 5:
            continue
        module = _module_name(path)
        stem = path.stem
        tokens = [module, stem]
        live_n, test_n, doc_n, live_files, test_files, doc_files = _count_refs(path, tokens, inverted)
        if live_n == 0:
            status = "UNWIRED_CANDIDATE"
            reason = "organ-like module has no non-test source reference found"
        elif live_n <= 2 and test_n > 0:
            status = "WEAKLY_WIRED"
            reason = "few live references; tests know it better than the runtime"
        else:
            status = "WIRED_OR_REFERENCED"
            reason = "static live source references found"
        rows.append(
            ModuleInfo(
                file=rel,
                module=module,
                stem=stem,
                organ_score=score,
                public_functions=funcs[:16],
                public_classes=classes[:10],
                truth_labels=truth[:8],
                ledgers=ledgers[:8],
                has_main=has_main,
                live_reference_count=live_n,
                test_reference_count=test_n,
                doc_reference_count=doc_n,
                live_reference_files=live_files,
                test_reference_files=test_files,
                doc_reference_files=doc_files,
                status=status,
                reason=reason,
            )
        )
    rows.sort(key=lambda r: (r.status != "UNWIRED_CANDIDATE", -r.organ_score, r.file))
    payload = {
        "truth_label": "UNWIRED_ORGAN_CENSUS_V1",
        "ts": time.time(),
        "source_python_files_scanned": len(source_files),
        "reference_files_scanned": len(reference_index),
        "candidate_count": len(rows),
        "by_status": dict(Counter(r.status for r in rows)),
        "rows": [asdict(r) for r in rows],
    }
    return payload


def _md(report: dict) -> str:
    lines = [
        "# Unwired Organ Census",
        "",
        "Generated by `tools/find_unwired_organs.py`.",
        "",
        f"- Truth label: `{report['truth_label']}`",
        f"- Source Python files scanned: `{report['source_python_files_scanned']}`",
        f"- Reference files scanned: `{report['reference_files_scanned']}`",
        f"- Organ-like candidates: `{report['candidate_count']}`",
        f"- By status: `{report['by_status']}`",
        "",
        "## Top Unwired Candidates",
        "",
    ]
    for row in [r for r in report["rows"] if r["status"] == "UNWIRED_CANDIDATE"][:80]:
        lines.append(
            f"- score `{row['organ_score']}` `{row['file']}` "
            f"truth={row['truth_labels'][:2]} ledgers={row['ledgers'][:2]} "
            f"tests={row['test_reference_files'][:3]} docs={row['doc_reference_files'][:2]}"
        )
    lines.extend(["", "## Weakly Wired", ""])
    for row in [r for r in report["rows"] if r["status"] == "WEAKLY_WIRED"][:80]:
        lines.append(
            f"- score `{row['organ_score']}` `{row['file']}` live={row['live_reference_files']} "
            f"tests={row['test_reference_files'][:3]}"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- This is static text analysis. Dynamic app loading, subprocess entry points, or CLI-only organs can look unwired.")
    lines.append("- Treat `UNWIRED_CANDIDATE` as a work queue: inspect, then either wire, retire, or annotate as intentionally standalone.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    report = scan()
    STATE.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_MD.write_text(_md(report), encoding="utf-8")
    print(f"UNWIRED ORGAN CENSUS — {report['candidate_count']} organ-like candidates")
    print("source python files scanned:", report["source_python_files_scanned"])
    print("reference files scanned:", report["reference_files_scanned"])
    print("by status:", report["by_status"])
    print(f"json -> {OUT_JSON.relative_to(REPO)}")
    print(f"markdown -> {OUT_MD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
