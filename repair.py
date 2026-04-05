#!/usr/bin/env python3
"""
ANTON-SIFTA Code Repair Agent
Traverses files sequentially, maintains minimal context,
performs localized edits, logs every action with diffs.

Surgical Bite Protocol:
  - Detects fault line via AST
  - Extracts only 30 lines around the error (not the whole file)
  - Sends the bite to qwen3.5:0.8b (the 1GB laser scalpel)
  - Validates the fix
  - Stitches it back into the original file
"""

import ast
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from body_state import SwarmBody, parse_body_state, apply_damage, bury

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11434/api/generate"
REPAIR_MODEL  = "qwen3.5:0.8b"   # laser scalpel — 1GB, fast
FALLBACK_MODEL = "qwen3.5:4b"    # fallback if 0.8b hallucinates
LOG_PATH     = Path(__file__).parent / "repair_log.jsonl"

SURGICAL_PROMPT = """\
You are a pure Python syntax linter. You have no personality.
I will give you a numbered chunk of Python code that contains a syntax error.
Fix the error. 
OUTPUT RULES:
1. Output ONLY the corrected Python lines, without line numbers.
2. Do not include markdown formatting (no ```python).
3. Do not explain your fix.
4. Do not add or remove lines — fix only what is broken.
If you speak instead of outputting code, the system crashes.\
"""

# ─── LOGGING ─────────────────────────────────────────────────────────────────
def log(event: dict):
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")


# ─── VALIDATION LAYER (no garbage through) ───────────────────────────────────
def validate_syntax(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, "ok"
    except SyntaxError as e:
        return False, str(e)


def validate_ruff(path: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["ruff", "check", str(path), "--select=E,F", "--quiet"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0, result.stdout.strip()
    except FileNotFoundError:
        return True, "ruff not installed — skipped"


# ─── SURGICAL BITE ────────────────────────────────────────────────────────────
def extract_bite(filepath: Path, error_line: int, buffer: int = 15) -> tuple[str, int, int, list[str]]:
    """Extract only the lines around the fault. The swimmer takes a precise bite."""
    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
    start = max(0, error_line - buffer - 1)
    end   = min(len(lines), error_line + buffer)
    # Number the lines so the model knows where it is
    chunk = "".join(f"[{i+1}] {lines[i]}" for i in range(start, end))
    return chunk, start, end, lines


def stitch_bite(filepath: Path, fixed_text: str, start: int, end: int, original_lines: list[str]):
    """Replace the repaired region back into the full file."""
    fixed_lines = [l + ("" if l.endswith("\n") else "\n") for l in fixed_text.splitlines()]
    original_lines[start:end] = fixed_lines
    filepath.write_text("".join(original_lines), encoding="utf-8")


# ─── LLM CALL (Surgical — small model, small chunk) ──────────────────────────
def call_ollama(chunk: str, model: str = REPAIR_MODEL) -> str | None:
    payload = {
        "model":      model,
        "prompt":     f"{SURGICAL_PROMPT}\n\n---CHUNK---\n{chunk}\n---END---",
        "stream":     False,
        "keep_alive": 0,   # evict immediately after call — no VRAM traffic jam
    }
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(OLLAMA_URL, data=data,
                                   headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:   # 30s is plenty for 30 lines
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        print(f"  [OLLAMA ERROR] {e}")
        return None


# ─── DIFF LOG ─────────────────────────────────────────────────────────────────
def hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ─── SWIMMER LOOP ─────────────────────────────────────────────────────────────
def swim_and_repair(target_dir: str, state: dict, dry_run: bool = True):
    root = Path(target_dir)
    files = sorted(
        [f for f in root.rglob("*.py") if ".git" not in str(f)],
        key=lambda f: f.stat().st_ctime  # ordered by creation time — linear swim
    )

    print(f"\n  ANTON-SIFTA — Repair & Survival Mode")
    print(f"  Target:  {root}")
    print(f"  Files:   {len(files)}")
    print(f"  Agent:   {state['id']} | Energy: {state['energy']} | Style: {state['style']}")
    
    # Aggressive mutation check
    if state["style"] == "AGGRESSIVE":
        print(f"  [MUTATION] AGGRESSIVE style detected. Disabling dry run and fallbacks.")
        dry_run = False

    print(f"  Dry run: {dry_run}")
    print("─" * 60)

    log({"event": "swim_start", "target": str(root),
         "file_count": len(files), "dry_run": dry_run, "agent_id": state["id"]})

    fixed = 0
    skipped = 0
    errors = 0

    for i, filepath in enumerate(files):
        rel = filepath.relative_to(root)
        print(f"\n[{i+1}/{len(files)}] Swimming into: {rel}")

        # ── read ──────────────────────────────────────────────────────────
        try:
            original = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [SKIP] Cannot read: {e}")
            log({"event": "skip", "file": str(rel), "reason": str(e)})
            skipped += 1
            continue

        before_hash = hash_str(original)

        # ── pre-check (skip clean files) ──────────────────────────────────
        syntax_ok, syntax_err = validate_syntax(original)
        if syntax_ok:
            print(f"  [OK] Syntax clean — scout mark left, moving on.")
            log({"event": "scout", "file": str(rel),
                 "status": "clean", "hash": before_hash})
            continue

        # ── extract error line number from exception message ───────────────
        import re as _re
        line_match = _re.search(r"line (\d+)", syntax_err)
        error_line = int(line_match.group(1)) if line_match else 1
        print(f"  [FAULT] {syntax_err}")
        print(f"  [BITE]  Extracting 30 lines around line {error_line}...")

        # ── surgical bite — only the broken region ─────────────────────────
        chunk, bite_start, bite_end, all_lines = extract_bite(filepath, error_line)
        print(f"  [LLM]   Sending {bite_end - bite_start} lines to {REPAIR_MODEL}...")
        fixed_chunk = call_ollama(chunk, REPAIR_MODEL)

        # ── fallback to 4b if 0.8b fails ──────────────────────────────────
        if not fixed_chunk and state["style"] != "AGGRESSIVE":
            print(f"  [FALLBACK] 0.8b returned nothing. Trying {FALLBACK_MODEL}...")
            fixed_chunk = call_ollama(chunk, FALLBACK_MODEL)

        if not fixed_chunk:
            print(f"  [FAIL] All models returned nothing. Taking damage.")
            state = apply_damage(state, "llm_empty")
            log({"event": "fail", "file": str(rel), "reason": "llm_empty"})
            errors += 1
            if state["energy"] <= 0:
                print("  [FATAL] Agent energy depleted during repair simulation.")
                bury(state, cause="llm_empty")
                return
            continue

        # ── stitch back and validate the whole file ───────────────────────
        # Write to a temp validation path first
        import tempfile, shutil
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                         delete=False, encoding="utf-8") as tmp:
            fixed_lines = [l + ("" if l.endswith("\n") else "\n")
                           for l in fixed_chunk.splitlines()]
            test_lines = all_lines[:]
            test_lines[bite_start:bite_end] = fixed_lines
            tmp.write("".join(test_lines))
            tmp_path = tmp.name

        repaired_ok, repair_err = validate_syntax(open(tmp_path).read())
        os.unlink(tmp_path)

        if not repaired_ok:
            print(f"  [REJECT] Stitched file still broken: {repair_err}. Taking damage.")
            state = apply_damage(state, "validation_fail")
            log({"event": "reject", "file": str(rel),
                 "before_hash": before_hash, "reason": repair_err})
            errors += 1
            if state["energy"] <= 0:
                print("  [FATAL] Agent energy depleted from validation failures.")
                bury(state, cause="validation_fail")
                return
            continue

        after_lines = all_lines[:]
        after_lines[bite_start:bite_end] = fixed_lines
        after_hash = hash_str("".join(after_lines))

        # ── write (if not dry run) ─────────────────────────────────────────
        if not dry_run:
            stitch_bite(filepath, fixed_chunk, bite_start, bite_end, all_lines)
            print(f"  [✅] Stitched and written.")
        else:
            print(f"  [DRY] Fix validated. Would stitch lines {bite_start+1}–{bite_end}. Hash: {before_hash[:8]} → {after_hash[:8]}")

        log({
            "event":       "fix",
            "file":        str(rel),
            "before_hash": before_hash,
            "after_hash":  after_hash,
            "dry_run":     dry_run,
            "model":       REPAIR_MODEL,
        })
        fixed += 1

    print("\n" + "━" * 60)
    print(f"  SWIM COMPLETE")
    print(f"  Fixed:   {fixed}")
    print(f"  Clean:   {len(files) - fixed - skipped - errors}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"  Log:     {LOG_PATH}")
    print("━" * 60)
    log({"event": "swim_complete", "fixed": fixed,
         "skipped": skipped, "errors": errors})


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ANTON-SIFTA Code Repair Agent")
    parser.add_argument("target", help="Directory to swim through and repair")
    parser.add_argument("--write", action="store_true",
                        help="Actually write fixes (default: dry run)")
    parser.add_argument("--body", type=str, default="",
                        help="Raw ASCII body string to initialize state from")
    args = parser.parse_args()

    if args.body:
        agent_state = parse_body_state(args.body)
    else:
        # Default initialization for the clean test environment
        alice = SwarmBody("ANTIALICE")
        # Give her a few scars immediately to simulate a rough transit
        body_string = alice.generate_body("M5", "M1THER", "REPAIR_SWIM", style="NOMINAL", energy=100)
        agent_state = parse_body_state(body_string)

    swim_and_repair(args.target, agent_state, dry_run=not args.write)
