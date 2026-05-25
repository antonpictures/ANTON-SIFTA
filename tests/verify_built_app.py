#!/usr/bin/env python3
"""verify_built_app.py — objective build verifier for cortex-built SIFTA apps.

George 2026-05-24: the three-cortex build tournament (Claude→Sudoku, Grok→Go,
Hermes→Calculator) must be MEASURABLE, not vibes. After a cortex claims it built
an app, this closes the loop from "LLM said it built something" to "the app
actually exists, registers, compiles, and survives a headless import."

Checks, in order (each independent, all receipted):
  1. file_exists      — the app .py is on disk under Applications/
  2. manifest_entry   — apps_manifest.json has an entry (entry_point + widget_class)
  3. py_compile       — the app file compiles
  4. manifest_valid   — apps_manifest.json as a whole still parses
  5. headless_import  — QT_QPA_PLATFORM=offscreen import of the module + widget class
                        (SKIPPED, not FAILED, if PyQt6 is unavailable in this env)

Verdict BUILD_VERIFIED iff file_exists + manifest_entry + py_compile + manifest_valid
all pass (headless_import is a bonus; SKIPPED never fails the build). Otherwise
BUILD_FAILED with the exact failing checks. A receipt row is appended to
.sifta_state/build_verification.jsonl every run — that row is the tournament score.

Usage (run from the repo root or anywhere):
    python3 tests/verify_built_app.py "Stigmergic Sudoku"
    python3 tests/verify_built_app.py --file Applications/sifta_stigmergic_sudoku.py
    python3 tests/verify_built_app.py --newest        # newest Applications/*.py
    python3 tests/verify_built_app.py --all-games     # the 3 tournament titles

Honest by design: it NEVER prints VERIFIED unless the concrete checks passed.
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "Applications" / "apps_manifest.json"
RECEIPTS = REPO / ".sifta_state" / "build_verification.jsonl"

GAME_TITLES = ["Stigmergic Sudoku", "Stigmergic Go", "Stigmergic Calculator"]


def _load_manifest() -> tuple[dict, str]:
    """Return (manifest_dict, error). error == '' means it parsed cleanly."""
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _find_manifest_entry(manifest: dict, *, title: str = "", file: str = "") -> tuple[str, dict]:
    """Find a manifest entry by title (key) or by entry_point file. Returns (key, entry)."""
    if title and title in manifest:
        return title, manifest[title]
    # case-insensitive / normalized title match
    if title:
        norm = title.strip().casefold()
        for k, v in manifest.items():
            if k.strip().casefold() == norm:
                return k, v
    if file:
        fnorm = file.replace("\\", "/").lstrip("./")
        for k, v in manifest.items():
            ep = str((v or {}).get("entry_point") or "").replace("\\", "/").lstrip("./")
            if ep and (ep == fnorm or ep.endswith(fnorm) or fnorm.endswith(ep)):
                return k, v
    return "", {}


def verify(*, title: str = "", file: str = "") -> dict:
    checks: dict[str, dict] = {}
    manifest, manifest_err = _load_manifest()

    # 4. manifest_valid (run first; needed by manifest_entry)
    checks["manifest_valid"] = {
        "ok": manifest_err == "",
        "detail": manifest_err or "apps_manifest.json parses",
    }

    key, entry = _find_manifest_entry(manifest, title=title, file=file)
    entry_point = str((entry or {}).get("entry_point") or "")
    widget_class = str((entry or {}).get("widget_class") or "")

    # 2. manifest_entry
    checks["manifest_entry"] = {
        "ok": bool(key and entry_point),
        "detail": (
            f"key={key!r} entry_point={entry_point!r} widget_class={widget_class!r}"
            if key else f"no manifest entry for title={title!r} file={file!r}"
        ),
    }

    # resolve the app file
    app_path = ""
    if file:
        app_path = file
    elif entry_point:
        app_path = entry_point
    abs_app = (REPO / app_path).resolve() if app_path else None

    # 1. file_exists
    file_ok = bool(abs_app and abs_app.exists())
    checks["file_exists"] = {
        "ok": file_ok,
        "detail": (str(abs_app) if abs_app else "no file path resolved") + (" — present" if file_ok else " — MISSING"),
    }

    # 3. py_compile
    if file_ok:
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(abs_app)],
            capture_output=True, text=True,
        )
        checks["py_compile"] = {
            "ok": proc.returncode == 0,
            "detail": "compiles" if proc.returncode == 0 else (proc.stderr.strip()[-400:] or "compile failed"),
        }
    else:
        checks["py_compile"] = {"ok": False, "detail": "skipped — file missing"}

    # 5. headless_import (bonus; SKIPPED if PyQt6 unavailable)
    if file_ok and entry_point.endswith(".py"):
        module = entry_point.replace("/", ".").replace("\\", ".")[:-3]
        snippet = (
            "import importlib,sys\n"
            f"m=importlib.import_module({module!r})\n"
            + (f"getattr(m,{widget_class!r})\n" if widget_class else "")
            + "print('IMPORT_OK')\n"
        )
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(REPO)}
        try:
            proc = subprocess.run(
                [sys.executable, "-c", snippet],
                capture_output=True, text=True, cwd=str(REPO), env=env, timeout=60,
            )
            out = (proc.stdout + proc.stderr)
            if "No module named 'PyQt6'" in out or "No module named \"PyQt6\"" in out:
                checks["headless_import"] = {"ok": True, "skipped": True, "detail": "SKIPPED — PyQt6 not in this env (run on the Mac)"}
            elif proc.returncode == 0 and "IMPORT_OK" in out:
                checks["headless_import"] = {"ok": True, "detail": "imported + widget class present"}
            else:
                checks["headless_import"] = {"ok": False, "detail": out.strip()[-500:] or "import failed"}
        except subprocess.TimeoutExpired:
            checks["headless_import"] = {"ok": False, "detail": "import hung > 60s (likely starts a blocking loop at import)"}
        except Exception as exc:
            checks["headless_import"] = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    else:
        checks["headless_import"] = {"ok": False, "skipped": True, "detail": "skipped — file missing or non-.py"}

    # Verdict: the four hard checks must pass; import is bonus (SKIPPED is fine).
    hard = ["file_exists", "manifest_entry", "py_compile", "manifest_valid"]
    passed = all(checks[c]["ok"] for c in hard)
    verdict = "BUILD_VERIFIED" if passed else "BUILD_FAILED"

    receipt = {
        "ts": time.time(),
        "kind": "BUILD_VERIFICATION",
        "verdict": verdict,
        "title": key or title,
        "file": app_path,
        "widget_class": widget_class,
        "checks": checks,
        "truth_label": "OBSERVED_BUILD_VERIFICATION_V1",
    }
    try:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return receipt


def _print(receipt: dict) -> None:
    v = receipt["verdict"]
    mark = "✅" if v == "BUILD_VERIFIED" else "❌"
    print(f"\n{mark} {v}  —  {receipt.get('title') or receipt.get('file')}")
    for name, c in receipt["checks"].items():
        if c.get("skipped"):
            sym = "·"
        else:
            sym = "✓" if c["ok"] else "✗"
        print(f"   {sym} {name}: {c['detail']}")
    print(f"   receipt → {RECEIPTS}\n")


def _newest_app_file() -> str:
    apps = sorted((REPO / "Applications").glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True)
    return f"Applications/{apps[0].name}" if apps else ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify a cortex-built SIFTA app")
    ap.add_argument("title", nargs="?", default="", help="manifest title, e.g. 'Stigmergic Sudoku'")
    ap.add_argument("--file", default="", help="app file, e.g. Applications/sifta_stigmergic_sudoku.py")
    ap.add_argument("--newest", action="store_true", help="verify the newest Applications/*.py")
    ap.add_argument("--all-games", action="store_true", help="verify the 3 tournament titles")
    args = ap.parse_args()

    if args.all_games:
        results = [verify(title=t) for t in GAME_TITLES]
        for r in results:
            _print(r)
        n_ok = sum(1 for r in results if r["verdict"] == "BUILD_VERIFIED")
        print(f"=== Tournament: {n_ok}/{len(results)} apps BUILD_VERIFIED ===")
        sys.exit(0 if n_ok == len(results) else 1)

    file = args.file or (_newest_app_file() if args.newest else "")
    if not args.title and not file:
        ap.error("give a title, --file, --newest, or --all-games")
    r = verify(title=args.title, file=file)
    _print(r)
    sys.exit(0 if r["verdict"] == "BUILD_VERIFIED" else 1)


if __name__ == "__main__":
    main()
