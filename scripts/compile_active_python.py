#!/usr/bin/env python3
"""Syntax-check active SIFTA Python without scanning dead/generated trees.

This intentionally does not use py_compile because py_compile writes .pyc
files. We parse and compile source in memory, so the check is read-only.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parent.parent

SKIP_DIR_NAMES = {
    ".git",
    ".cursor",
    ".distro_build",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".sifta_state",
    ".simulation_publicpush_sandbox",
    ".venv",
    "__pycache__",
    "Archive",
    "ANTON-SIFTA",  # accidental nested clone of this repository
    "build",
    "dist",
    "node_modules",
    "venv",
}

SKIP_DIR_PARTS = {
    ("Library", "llama.cpp"),
    ("surgery", "qwen_test"),
    ("surgery", "qwen35_experiments", "adapters"),
    ("surgery", "qwen35_experiments", "merged"),
    ("surgery", "alice_phc_cure", "adapters"),
    ("surgery", "alice_phc_cure", "merged"),
    ("surgery", "alice_phc_cure", "receipts"),
}

SKIP_FILE_NAMES = {
    "fix.py",
    "patch.py",
    "scratch.py",
}

SKIP_FILE_SUFFIXES = {
    ".bak",
    ".orig",
}


def _rel_parts(path: Path) -> tuple[str, ...]:
    try:
        return path.relative_to(REPO).parts
    except ValueError:
        return path.parts


def _has_skip_part(path: Path) -> bool:
    parts = _rel_parts(path)
    for skip in SKIP_DIR_PARTS:
        if len(parts) >= len(skip) and parts[: len(skip)] == skip:
            return True
    return False


def iter_python_files(root: Path = REPO) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [
            d
            for d in dirs
            if d not in SKIP_DIR_NAMES and not _has_skip_part(current_path / d)
        ]
        for filename in files:
            path = current_path / filename
            if filename in SKIP_FILE_NAMES:
                continue
            if filename.startswith("patch") and filename.endswith(".py"):
                continue
            if path.suffix != ".py":
                continue
            if filename.startswith("."):
                continue
            if any(filename.endswith(suffix) for suffix in SKIP_FILE_SUFFIXES):
                continue
            yield path


def check_file(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            warnings.simplefilter("ignore", DeprecationWarning)
            compile(source, str(path), "exec")
    except SyntaxError as exc:
        line = exc.lineno or "?"
        msg = exc.msg or type(exc).__name__
        return f"{path.relative_to(REPO)}:{line}: {msg}"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only syntax check for active SIFTA Python files."
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="Print every active Python file considered by the checker.",
    )
    args = parser.parse_args()

    files = sorted(iter_python_files())
    failures = []
    for path in files:
        if args.list_files:
            print(path.relative_to(REPO))
        failure = check_file(path)
        if failure:
            failures.append(failure)

    print(f"checked={len(files)} skipped_policy=archive/runtime/nested-clones/generated-surgery")
    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("OK: active Python syntax clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
