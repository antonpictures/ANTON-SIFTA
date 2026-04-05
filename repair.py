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
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from body_state import SwarmBody, parse_body_state, apply_damage, bury, find_healthy_agent, save_agent_state

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11434/api/generate"
REPAIR_MODEL = "qwen3.5:0.8b"
FALLBACK_MODEL = "qwen3.5:4b"
LOG_PATH     = Path(__file__).parent / "repair_log.jsonl"
MODEL_TIMEOUTS = {"qwen3.5:0.8b": 15, "qwen3.5:4b": 60, "gemma4:latest": 120}

SURGICAL_PROMPT = """\
Fix the Python syntax error. 
RESPOND WITH ONLY THE FIXED CODE.
NO line numbers. NO brackets. NO markdown. NO explanation.
PRESERVE THE EXACT ORIGINAL INDENTATION OF EVERY LINE.
Just raw Python lines, nothing else.
If a line contains only random non-Python words with no operators or structure, DELETE THAT LINE ENTIRELY.

Example correct response:
    def foo():
        return 1

Example WRONG response:
[4] def foo():
    return 1
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


# ─── LLM CALL (Streaming — tokens print live into SSE pipeline) ──────────────
def call_ollama(prompt: str, model: str = "qwen3.5:0.8b") -> str | None:
    import json
    import urllib.request

    url = "http://localhost:11434/api/generate"
    data = {
        "model": model,
        "prompt": (
            "You are a Python syntax repair module. "
            "Output ONLY the corrected Python code lines. No explanation.\n\n"
            f"{prompt}"
        ),
        "stream": True,
        "temperature": 0.0,
        "keep_alive": 0,      # release model slot immediately after — no VRAM lock
        "num_predict": 512,   # cap output tokens — repair chunks are never long
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    full_response = []
    in_think = False

    try:
        req_timeout = MODEL_TIMEOUTS.get(model, 60)
        with urllib.request.urlopen(req, timeout=req_timeout) as resp:
            for raw_line in resp:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                token = chunk.get("response", "")

                # ── detect <think> blocks and stream them with a prefix ──
                if "<think>" in token:
                    in_think = True
                    
                if in_think:
                    # Send token line-by-line so SSE doesn't buffer it
                    print(f"[THINK] {token}", flush=True)
                else:
                    print(f"[TOKEN] {token}", flush=True)
                    full_response.append(token)

                if "</think>" in token:
                    in_think = False

                if chunk.get("done"):
                    break

        result = "".join(full_response).strip()
        
        # Strip markdown fences if model wraps output anyway
        if result.startswith("```"):
            result = result.split("\n", 1)[-1]
        if result.endswith("```"):
            result = result.rsplit("```", 1)[0]
            
        # Strip bracketed line numbers if model hallucinates them anyway
        result = re.sub(r'^\[\d+\]\s?', '', result, flags=re.MULTILINE)
        
        return result.strip() or None

    except Exception as e:
        print(f"  [OLLAMA ERROR] {e}")
        return None


def ollama_healthy() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return True
    except Exception:
        return False


# ─── DIFF LOG ─────────────────────────────────────────────────────────────────
def hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def call_openai_api(chunk: str, model: str = "gpt-4o-mini", base_url: str = "", api_key: str = "") -> str | None:
    url = base_url or "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SURGICAL_PROMPT},
            {"role": "user", "content": f"---CHUNK---\n{chunk}\n---END---"}
        ],
        "temperature": 0.0,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"].strip()
            if content.startswith("```python"): content = content[9:]
            elif content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            return content.strip()
    except Exception as e:
        print(f"  [API ERROR] {e}")
        return None


def verify_runtime(filepath: Path) -> tuple[bool, str]:
    import subprocess
    target_dir = filepath.parent.absolute()
    module_name = filepath.stem
    try:
        result = subprocess.run(
            ["python3", "-c", f"import sys; sys.path.insert(0, '{target_dir}'); import {module_name}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, "ok"
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)



# ─── SWIMMER LOOP ─────────────────────────────────────────────────────────────
def check_sos_and_handoff(state, rel):
    """If energy falls below 20, SOS a healthy agent to take over the process stream."""
    if state["energy"] <= 20 and state.get("style", "") != "MEDBAY":
        savior = find_healthy_agent(exclude_id=state.get("id"))
        if savior:
            print(f"  [SOS] {state.get('id')} is critical! {savior.get('id')} intercepts mission -> MEDBAY.")
            log({"event": "sos", "file": str(rel), "agent_id": state.get("id"), "model": savior.get("id")})
            state["style"] = "MEDBAY"
            save_agent_state(state)
            
            # Reconstruct args
            new_args = sys.argv[:]
            if "--body" in new_args:
                idx = new_args.index("--body")
                new_args[idx+1] = savior["raw"]
            else:
                new_args.extend(["--body", savior["raw"]])
                
            os.execv(sys.executable, [sys.executable] + new_args)

def swim_and_repair(target_dir: str, state: dict, dry_run: bool = True, provider: str = "ollama", model: str = "qwen3.5:0.8b", base_url: str = "", api_key: str = "", verify: bool = False):
    root = Path(target_dir)
    if root.is_file() and root.suffix == ".py":
        files = [root]
    else:
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

        MAX_PASSES = 5
        for pass_num in range(MAX_PASSES):
            # ── read ──────────────────────────────────────────────────────────
            try:
                original = filepath.read_text(encoding="utf-8")
            except Exception as e:
                print(f"  [SKIP] Cannot read: {e}")
                log({"event": "skip", "file": str(rel), "reason": str(e)})
                skipped += 1
                break

            before_hash = hash_str(original)

            # ── pre-check (skip clean files) ──────────────────────────────────
            syntax_ok, syntax_err = validate_syntax(original)
            if syntax_ok:
                if pass_num == 0:
                    print(f"  [OK] Syntax clean — scout mark left, moving on.")
                else:
                    print(f"  [CLEAN] File successfully repaired after {pass_num} sweeps.")
                log({"event": "scout", "file": str(rel),
                     "status": "clean", "hash": before_hash})
                break

            # ── extract error line number from exception message ───────────────
            import re as _re
            line_match = _re.search(r"line (\d+)", syntax_err)
            error_line = int(line_match.group(1)) if line_match else 1
            print(f"  [FAULT] {syntax_err}")
            
            # DYNAMIC BITE SIZING
            error_msg = str(syntax_err).lower()
            if "indent" in error_msg or "block" in error_msg:
                buffer = 25
                print(f"  [BITE] Structural error detected. Widening jaw for context ({buffer*2} lines)...")
            else:
                buffer = 10
                print(f"  [BITE] Localized syntax fault. Tightening jaw ({buffer*2} lines)...")

            # ── surgical bite — only the broken region ─────────────────────────
            chunk, bite_start, bite_end, all_lines = extract_bite(filepath, error_line, buffer=buffer)
        
            print(f"  [LLM] Sending {bite_end - bite_start} lines to {provider.upper()} ({model})...")
            if provider == "ollama":
                fixed_chunk = call_ollama(chunk, model=model)
            else:
                fixed_chunk = call_openai_api(chunk, model=model, base_url=base_url, api_key=api_key)

            # ── fallback to 4b if 0.8b fails ──────────────────────────────────
            if not fixed_chunk and provider == "ollama" and state["style"] != "AGGRESSIVE":
                if not ollama_healthy():
                    print(f"  [SKIP FALLBACK] Ollama daemon unresponsive. Aborting to save energy.")
                else:
                    print(f"  [FALLBACK] Model returned nothing. Trying {FALLBACK_MODEL}...")
                    fixed_chunk = call_ollama(chunk, FALLBACK_MODEL)

            if not fixed_chunk:
                print(f"  [FAIL] All models returned nothing. Taking damage.")
                state = apply_damage(state, "llm_empty")
                log({"event": "fail", "file": str(rel), "reason": "llm_empty"})
                errors += 1
                check_sos_and_handoff(state, rel)
                if state["energy"] <= 0:
                    print("  [FATAL] Agent energy depleted during repair simulation.")
                    bury(state, cause="llm_empty")
                    return
                continue

            # ── stitch back and validate the whole file ───────────────────────
            # Write to a temp validation path first
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", prefix="sifta_verify_", suffix=".py",
                                             dir=filepath.parent, delete=False, encoding="utf-8") as tmp:
                fixed_lines = [l + ("" if l.endswith("\n") else "\n")
                               for l in fixed_chunk.splitlines()]
                test_lines = all_lines[:]
                test_lines[bite_start:bite_end] = fixed_lines
                tmp.write("".join(test_lines))
                tmp_path = tmp.name

            repaired_ok, repair_err = validate_syntax(open(tmp_path).read())
        
            if repaired_ok and verify:
                print("  [VERIFY] Running runtime import verification...")
                repaired_ok, repair_err = verify_runtime(Path(tmp_path))
                if not repaired_ok:
                    short_err = repair_err.splitlines()[-1] if repair_err else ""
                    print(f"  [RUNTIME REJECT] Stitched file fails to import: {short_err}")
                    repair_err = f"Runtime verification failed: {short_err}"

            os.unlink(tmp_path)

            if not repaired_ok:
                repair_err_str = str(repair_err).lower()
                prev_err_str = str(syntax_err).lower()
                
                if repair_err_str != prev_err_str:
                    print(f"  [ABORT] Pass introduced a different error ({repair_err_str}). Reverting.")
                    state = apply_damage(state, "validation_fail")
                    state["energy"] -= 5 # Extra penalty for corruption
                    log({"event": "abort", "file": str(rel),
                         "before_hash": before_hash, "reason": repair_err})
                    errors += 1
                    check_sos_and_handoff(state, rel)
                    break
                else:
                    print(f"  [REJECT] Stitched file still broken: {repair_err}. Taking damage.")
                    state = apply_damage(state, "validation_fail")
                    log({"event": "reject", "file": str(rel),
                         "before_hash": before_hash, "reason": repair_err})
                    errors += 1
                    check_sos_and_handoff(state, rel)
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
                "model":       model,
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
    parser.add_argument("--provider", default="ollama", choices=["ollama", "openai", "openrouter", "google", "custom"])
    parser.add_argument("--model", default="qwen3.5:0.8b")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--verify", action="store_true",
                        help="Perform runtime verification (try importing the file) after stitching")
    args = parser.parse_args()

    if args.body:
        agent_state = parse_body_state(args.body)
    else:
        # Default initialization for the clean test environment
        alice = SwarmBody("ANTIALICE")
        # Give her a few scars immediately to simulate a rough transit
        body_string = alice.generate_body("M5", "M1THER", "REPAIR_SWIM", style="NOMINAL", energy=100)
        agent_state = parse_body_state(body_string)

    swim_and_repair(
        args.target, 
        agent_state, 
        dry_run=not args.write, 
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        verify=args.verify
    )
