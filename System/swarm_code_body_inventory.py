"""Alice code-body inventory — every living-substrate line counted (r1020)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

_REPO = Path(__file__).resolve().parents[1]
_SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "build",
        "dist",
    }
)
_LIVING_ROOTS: Tuple[str, ...] = (
    "System",
    "Applications",
    "tools",
    "Kernel",
    "Network",
    "tests",
    "scripts",
)
_TRUTH = "CODE_BODY_INVENTORY_V1"


def _line_count(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except Exception:
        return 0


def _walk_living_python(repo: Path) -> List[Tuple[str, int, str]]:
    """Deterministic top-down walk: living roots, alpha dirs, alpha files."""
    rows: List[Tuple[str, int, str]] = []
    for root_name in _LIVING_ROOTS:
        base = repo / root_name
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base, topdown=True):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for fn in sorted(filenames):
                if not fn.endswith(".py"):
                    continue
                path = Path(dirpath) / fn
                rel = path.relative_to(repo).as_posix()
                rows.append((rel, _line_count(path), root_name))
    for fn in sorted(repo.glob("*.py")):
        rel = fn.name
        rows.append((rel, _line_count(fn), "(repo_root)"))
    return rows


def _count_tree(repo: Path, rel_root: str) -> Dict[str, int]:
    base = repo / rel_root
    if not base.exists():
        return {"files": 0, "loc": 0}
    files = 0
    loc = 0
    for dirpath, dirnames, filenames in os.walk(base, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            files += 1
            loc += _line_count(Path(dirpath) / fn)
    return {"files": files, "loc": loc}


def build_code_inventory(
    *,
    repo: Path | str | None = None,
    state_dir: Path | str | None = None,
    write_appearance_ledger: bool = True,
) -> Dict[str, Any]:
    """Count Alice's living body and optional full-repo Python rollup."""
    root = Path(repo) if repo is not None else _REPO
    sd = Path(state_dir) if state_dir is not None else root / ".sifta_state"
    if sd.name != ".sifta_state":
        sd = sd / ".sifta_state"

    appearance = _walk_living_python(root)
    by_dir_summary: Dict[str, Dict[str, int]] = {}
    total_loc = 0
    for rel, loc, bucket in appearance:
        total_loc += loc
        by_dir_summary.setdefault(bucket, {"files": 0, "loc": 0})
        by_dir_summary[bucket]["files"] += 1
        by_dir_summary[bucket]["loc"] += loc

    all_ex_vendor_loc = 0
    all_ex_vendor_files = 0
    try:
        import subprocess

        _find_prune = (
            "*/Vendor/*",
            "*/node_modules/*",
            "*/.git/*",
            "*/__pycache__/*",
            "*/.venv/*",
            "*/venv/*",
            "*/.pytest_cache/*",
            "*/.mypy_cache/*",
            "*/build/*",
            "*/dist/*",
            "*/.sifta_state/*",
        )
        find_args = [
            "find",
            str(root),
            "-type",
            "f",
            "-name",
            "*.py",
        ]
        for pat in _find_prune:
            find_args.extend(["!", "-path", pat])
        proc = subprocess.run(
            find_args,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        paths = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        all_ex_vendor_files = len(paths)
        for p in paths:
            all_ex_vendor_loc += _line_count(Path(p))
    except Exception:
        pass

    vendor = _count_tree(root, "Vendor")
    inv: Dict[str, Any] = {
        "schema": _TRUTH,
        "ts": time.time(),
        "truth_label": "OBSERVED",
        "total_files": len(appearance),
        "total_loc": total_loc,
        "by_dir_summary": by_dir_summary,
        "appearance_order": [rel for rel, _, _ in appearance[:40]],
        "living_substrate": {
            "roots": list(_LIVING_ROOTS),
            "py_files": len(appearance),
            "py_loc": total_loc,
        },
        "repo_rollups": {
            "all_python_ex_vendor": {
                "files": all_ex_vendor_files,
                "loc": all_ex_vendor_loc,
            },
            "vendor_python": vendor,
            "grand_total_python_estimate": all_ex_vendor_loc + int(vendor.get("loc") or 0),
        },
        "r1020_note": (
            "Living substrate = organs Alice admires for tip-top body work. "
            "Vendor/node_modules excluded from appearance walk; rollup kept separate."
        ),
    }

    if write_appearance_ledger:
        eval_dir = sd / "eval"
        eval_dir.mkdir(parents=True, exist_ok=True)
        ledger = eval_dir / "code_body_appearance_order.jsonl"
        lines = []
        for rel, loc, bucket in appearance:
            lines.append(
                json.dumps(
                    {
                        "schema": _TRUTH,
                        "path": rel,
                        "loc": loc,
                        "bucket": bucket,
                        "ts": inv["ts"],
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )
        ledger.write_text("".join(lines), encoding="utf-8")
        inv["appearance_ledger"] = str(ledger.relative_to(root))

    return inv