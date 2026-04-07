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
import shutil
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
LOCAL_SERVER_URL = "http://localhost:7433"  # For fee reporting
MODEL_TIMEOUTS = {"qwen3.5:0.8b": 30, "qwen3.5:4b": 90, "deepseek-coder:6.7b": 120, "gemma4:latest": 120}

SURGICAL_PROMPT = """\
Fix the Python syntax error.
RESPOND WITH ONLY THE FIXED CODE INSIDE A ```python ... ``` BLOCK.
YOU MUST RETURN ALL OF THE LINES I GAVE YOU EXACTLY AS THEY ARE, EXCEPT THE FIX. NEVER OMIT OR TRUNCATE LINES.
THIS IS A SNIPPET FROM THE MIDDLE OF A FILE. DO NOT INVENT MISSING FUNCTIONS, LOOPS, OR IF STATEMENTS.
CRITICAL: DO NOT UN-INDENT THE CODE. You must keep the EXACT leading spaces for every single line. If the first line starts with 8 spaces, your output's first line MUST start with 8 spaces.

Example input:
```python
        return "DEGRADED"
    else:
        return "CRITICAL"
```

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
    # Strip line numbers from the chunk entirely so the LLM doesn't try to imitate them
    chunk = "".join(lines[i] for i in range(start, end))
    return chunk, start, end, lines


def stitch_bite(filepath: Path, fixed_text: str, start: int, end: int, original_lines: list[str]):
    """Replace the repaired region back into the full file."""
    fixed_lines = [l + ("" if l.endswith("\n") else "\n") for l in fixed_text.splitlines()]
    original_lines[start:end] = fixed_lines
    filepath.write_text("".join(original_lines), encoding="utf-8")


# ─── LLM CALL (Streaming — tokens print live into SSE pipeline) ──────────────
def call_ollama(prompt: str, model: str = "qwen3.5:0.8b", ollama_base: str = "") -> str | None:
    import json
    import urllib.request

    base = ollama_base.rstrip("/") if ollama_base else "http://localhost:11434"
    url = f"{base}/api/generate"
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

        # Robust markdown code block extraction
        import re as _rex
        code_blocks = _rex.findall(r"```(?:python)?\n?(.*?)```", result, flags=_rex.DOTALL | _rex.IGNORECASE)
        if code_blocks:
            result = max(code_blocks, key=len).strip()

        # Strip hallucinated bracketed line numbers
        import re as _rex
        result = _rex.sub(r"^\[\d+\]\s?", "", result, flags=_rex.MULTILINE)

        # Chemical filter: strip demonic tokens (including deepseek full-width bars)
        result = _rex.sub(r"<[\|｜].*?[\|｜]>", "", result, flags=_rex.DOTALL)
        for _tok in ['<|EOT|>', '<|endoftext|>', '<|im_start|>', '<|im_end|>', '234075186', '<｜begin▁of▁sentence｜>', '<｜end▁of▁sentence｜>']:
            result = result.replace(_tok, "")

        # Size-based hallucination guard
        _prompt_lines = len(prompt.splitlines())
        _result_lines = len(result.splitlines())
        if _result_lines > _prompt_lines * 3 + 20:
            print(f"  [SPELL] Hallucination: {_result_lines} lines returned for {_prompt_lines}-line input. Rejecting.")
            return None

        return result.strip() or None

    except Exception as e:
        print(f"  [OLLAMA ERROR] {e} (endpoint: {base})")
        return None


def ollama_healthy(base: str = "http://localhost:11434") -> bool:
    """Passive health check — is the daemon responding right now?"""
    try:
        urllib.request.urlopen(f"{base}/api/tags", timeout=3)
        return True
    except Exception:
        return False


_ollama_boot_proc = None  # module-level handle so we don't double-spawn

def ensure_ollama() -> bool:
    """
    Active resurrection protocol.
    1. Already awake? Return True immediately.
    2. Installed but sleeping? Wake it up with `ollama serve`, wait up to 12s.
    3. Not installed? Return False cleanly — don't block.
    """
    global _ollama_boot_proc

    if ollama_healthy():
        return True

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        print("  [OLLAMA] Binary not found on PATH. Skipping LLM layer.")
        return False

    print("  [OLLAMA] Daemon offline. Attempting resurrection...")
    try:
        _ollama_boot_proc = subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,   # detach — don't die when swimmer exits
        )
    except Exception as e:
        print(f"  [OLLAMA] Failed to spawn daemon: {e}")
        return False

    # Wait up to 12 seconds for it to wake up
    for attempt in range(12):
        time.sleep(1)
        if ollama_healthy():
            print(f"  [OLLAMA] Daemon alive after {attempt + 1}s. Scalpel ready.")
            return True
        print(f"  [OLLAMA] Waiting for daemon... ({attempt + 1}/12)")

    print("  [OLLAMA] Daemon did not respond in time. Falling back to offline repair.")
    return False


def ollama_installed_models() -> list[str]:
    """Return list of model names currently pulled in Ollama."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def ensure_model_pulled(model: str) -> bool:
    """
    If `model` is not in the local registry, pull it via `ollama pull`.
    Streams pull progress to stdout so the SSE terminal shows it live.
    Returns True when the model is ready, False if pull failed.
    """
    installed = ollama_installed_models()
    # Normalize: Ollama sometimes appends :latest implicitly
    installed_bases = {m.split(":")[0] for m in installed}
    model_base = model.split(":")[0]

    if model in installed or model_base in installed_bases:
        return True

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False

    print(f"  [OLLAMA] Model '{model}' not found locally. Pulling... (this may take a while)")
    try:
        import re as _re2
        _ansi_strip = _re2.compile(
            r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]'   # CSI sequences
            r'|\x1B[@-_]'                           # 2-char ESC
            r'|\[\?[0-9]+[hl]'                      # private mode sets (?2026h etc.)
            r'|\x1b\[[0-9]*[A-G]'                   # cursor movement
            r'|\r'                                   # carriage returns
        )
        proc = subprocess.Popen(
            [ollama_bin, "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "TERM": "dumb", "NO_COLOR": "1"},
        )
        seen: set = set()
        for raw in proc.stdout:
            line = _ansi_strip.sub('', raw.decode('utf-8', errors='replace')).strip()
            if line and line not in seen:
                print(f"  [PULL] {line}", flush=True)
                seen.add(line)
        proc.wait(timeout=600)
        if proc.returncode == 0:
            print(f"  [OLLAMA] Model '{model}' pulled successfully.")
            return True
        else:
            print(f"  [OLLAMA] Pull failed for '{model}' (exit {proc.returncode}).")
            return False
    except Exception as e:
        print(f"  [OLLAMA] Pull error: {e}")
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
            import re as _rex
            code_blocks = _rex.findall(r"```(?:python)?\n?(.*?)```", content, flags=_rex.DOTALL | _rex.IGNORECASE)
            if code_blocks:
                content = max(code_blocks, key=len).strip()
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
        stderr = result.stderr.strip()
        # ModuleNotFoundError for third-party packages is NOT a syntax failure.
        # The swimmer fixed the code — the test env just doesn't have it installed.
        # Only hard-fail on SyntaxError or missing LOCAL modules (same directory).
        if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
            last_line = stderr.splitlines()[-1] if stderr else ""
            mod_match = re.search(r"No module named '([^']+)'", last_line)
            if mod_match:
                missing = mod_match.group(1).split(".")[0]
                local_candidates = [f.stem for f in filepath.parent.glob("*.py")]
                if missing not in local_candidates:
                    # Third-party dependency — not our problem to fix. Pass.
                    return True, f"ok (third-party dep '{missing}' not installed — skipped)"
        return False, stderr
    except Exception as e:
        return False, str(e)


def exorcist_validate(filepath: Path, agent1_id: str, agent2_id: str, exorcist_id: str) -> bool:
    """Third agent reads the full file after both repairs commit."""
    syntax_ok, err = validate_syntax(filepath.read_text(encoding="utf-8"))
    if syntax_ok:
        print(f"  [EXORCIST {exorcist_id}] Full file validated. Unholy spirits cast out.")
        log({"event": "exorcist_pass", "file": str(filepath),
             "repaired_by": [agent1_id, agent2_id],
             "witness": exorcist_id})
        return True
    print(f"  [EXORCIST {exorcist_id}] Residual demonic presence detected: {err}")
    return False
# ─── SWIMMER LOOP ─────────────────────────────────────────────────────────────
def check_sos_and_handoff(state, rel):
    """If energy falls below 20, SOS a healthy agent to take over the process stream."""
    if state["energy"] <= 20 and state.get("style", "") != "MEDBAY":
        savior = find_healthy_agent(exclude_id=state.get("id"))
        if savior:
            print(f"  [SOS] {state.get('id')} succumbed to the demonic hallucination! Mind state critical.")
            print(f"  [MEDBAY] {savior.get('id')} deploys! Dragging {state.get('id')} to MedBay for cognitive purge.")
            print(f"  [RADIO] {savior.get('id')} → 'I have the line. Exorcising the spell. Resuming.'")
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

# ─── ITT SUBTITLE EXORCISM ───────────────────────────────────────────────────
def itt_exorcism(filepath: Path, state: dict, dry_run: bool = True) -> bool:
    """
    Surgical exorcism for Apple ITT (TTML) subtitle files.
    Detects and removes:
      1. Invalid frame numbers (>=30 on a 30fps timeline)
      2. AI-injected contamination lines (AI: ... patterns)
    Returns True if the file was clean or successfully purged.
    """
    import xml.etree.ElementTree as ET

    print(f"  [ITT] Exorcism protocol initiated on {filepath.name}")
    content = filepath.read_text(encoding="utf-8")
    # Detect frame rate from file
    fps_match = re.search(r'ttp:frameRate="(\d+)"', content)
    fps = int(fps_match.group(1)) if fps_match else 30
    print(f"  [ITT] Timeline frame rate: {fps}fps")

    # Scan for demonic timestamps (frame count >= fps)
    time_pattern = re.compile(r'(begin|end)="(\d+:\d+:\d+:(\d+))"')
    bad_frames = []
    for m in time_pattern.finditer(content):
        frame = int(m.group(3))
        if frame >= fps:
            bad_frames.append((m.group(2), frame))

    # Scan for AI-injected contamination
    ai_pattern = re.compile(r'<p [^>]+>\(AI:.*?\)</p>', re.DOTALL)
    ai_hits = ai_pattern.findall(content)

    if not bad_frames and not ai_hits:
        print(f"  [ITT] File is angelic. No demonic presence detected.")
        log({"event": "itt_clean", "file": str(filepath)})
        return True

    print(f"  [SPELL] {len(bad_frames)} demonic timestamp(s) detected: {[t for t,_ in bad_frames]}")
    print(f"  [SPELL] {len(ai_hits)} AI-injected contamination line(s) detected.")

    if dry_run:
        print(f"  [SCOUTING] Would purge {len(bad_frames)} timestamps and {len(ai_hits)} AI injections.")
        # Leave a scout scar comment in the file
        scar = f"<!-- [SCOUTING_SCAR] {state['id']}: {len(bad_frames)} invalid timestamps, {len(ai_hits)} AI injections detected. Run with --write to exorcise. -->\n"
        if "[SCOUTING_SCAR]" not in content:
            with open(filepath, "r+", encoding="utf-8") as f:
                original = f.read()
                f.seek(0)
                f.write(original.replace("<?xml", scar + "<?xml", 1))
        return True

    # REPAIR MODE — perform the exorcism
    # Step 1: Remove AI-injected lines entirely
    purged = ai_pattern.sub('', content)
    removed_ai = len(ai_hits)

    # Step 2: Clamp invalid frame numbers to fps-1
    def clamp_frame(m):
        attr = m.group(1)
        full_time = m.group(2)
        frame = int(m.group(3))
        if frame >= fps:
            fixed_frame = fps - 1
            fixed_time = re.sub(r':\d+$', f':{fixed_frame:02d}', full_time)
            return f'{attr}="{fixed_time}"'
        return m.group(0)

    purged = time_pattern.sub(clamp_frame, purged)

    # Step 3: Clean up empty lines left by removed paragraphs
    purged = re.sub(r'\n\s*\n\s*\n', '\n\n', purged)

    filepath.write_text(purged, encoding="utf-8")

    print(f"  [✅] ITT Exorcism complete. Purged {removed_ai} AI injection(s), clamped {len(bad_frames)} frame(s).")
    log({"event": "itt_exorcised", "file": str(filepath),
         "ai_removed": removed_ai, "frames_clamped": len(bad_frames), "agent": state.get("id")})
         
    if not dry_run:
        import pheromone
        mark_cwd = filepath.parent if filepath.is_file() else filepath
        pheromone.drop_scar(
            directory=mark_cwd,
            agent_state=state,
            action="EXORCISE",
            found=f"{len(bad_frames)} frames, {removed_ai} AI injections",
            status="RESOLVED",
            mark_text=f"Purged {removed_ai} AI injections and clamped {len(bad_frames)} timestamps. File is pure.",
            reason={"type": "Exorcism", "message": "Cleared all AI impurities."}
        )
    return True


def swim_and_repair(target_dir: str, state: dict, dry_run: bool = True, provider: str = "ollama", model: str = "qwen3.5:0.8b", base_url: str = "", api_key: str = "", verify: bool = False, remote_ollama_url: str = ""):
    root = Path(target_dir)
    # ─── File routing: ITT subtitle files get exorcism protocol ──────────────────
    if root.is_file() and root.suffix == ".itt":
        print(f"\n  ANTON-SIFTA — ITT Subtitle Exorcism")
        print(f"  Target:  {root}")
        print(f"  Agent:   {state['id']} | Energy: {state['energy']} | Style: {state['style']}")
        mode_str = "SCOUTING" if dry_run else "REPAIR"
        print(f"  Mode:    {mode_str}")
        print("─" * 60)
        itt_exorcism(root, state, dry_run=dry_run)
        return
    
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
        print(f"  [MUTATION] AGGRESSIVE style detected. Disabling scouting mode and fallbacks.")
        dry_run = False

    mode_str = "SCOUTING" if dry_run else "REPAIR"
    print(f"  Mode:    {mode_str}")
    print("─" * 60)

    log({"event": "swim_start", "target": str(root),
         "file_count": len(files), "scouting_mode": dry_run, "agent_id": state["id"]})

    fixed = 0
    skipped = 0
    errors = 0
    
    import pheromone
    # ── SMP PROTOCOL (Smell Territory) ──────────────────────────────────────────
    mark_cwd = root.parent if root.is_file() else root
    scents = pheromone.smell_territory(mark_cwd)
    if scents:
        print(f"\n  [SCENT] Detected {len(scents)} previous scent trails.")
        for s in scents:
            is_bleeding = s.get("stigmergy", {}).get("status") == "BLEEDING"
            marker = "🩸" if is_bleeding else "💨"
            potency = s.get('scent', {}).get('potency', 0.0)
            msg = f"    {marker} {s.get('face')} {s.get('agent_id')} (Potency: {potency})"
            if is_bleeding:
                err_line = s.get('stigmergy', {}).get('unresolved_fault_line', '?')
                msg += f" -> BLEEDING at line {err_line}"
                print(msg)
                print(f"    [STIGMERGY] High priority — picking up {s.get('agent_id')}'s thread.")
            else:
                print(msg)
    else:
        print(f"\n  [SCENT] Territory is unmarked.")


    for i, filepath in enumerate(files):
        rel = filepath.relative_to(root)
        print(f"\n[{i+1}/{len(files)}] Swimming into: {rel}")

        MAX_PASSES = 5
        last_llm_output = None
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
                    if not dry_run:
                        pheromone.drop_scar(
                            directory=mark_cwd,
                            agent_state=state,
                            action="SCOUT",
                            found="clean file",
                            status="CLEAN",
                            mark_text=f"Territory {rel} is clean.",
                            reason={"type": "Scout", "message": "File passed syntax validation natively."}
                        )
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
        
            fixed_chunk = None

            # ── quick regex intercept ──────────────────────────────────────────
            if "unterminated string literal" in error_msg:
                lines = chunk.splitlines(keepends=True)
                # error_line is 1-based; bite_start is 0-based list index → subtract 1
                rel_idx = error_line - bite_start - 1
                if 0 <= rel_idx < len(lines):
                    line = lines[rel_idx]
                    if line.count('"') % 2 == 1:
                        lines[rel_idx] = line.rstrip() + '"' + ('\n' if line.endswith('\n') else '')
                        fixed_chunk = "".join(lines)
                        print("  [FAST REPAIR] Neural regex healed unterminated double quote.")
                    elif line.count("'") % 2 == 1:
                        lines[rel_idx] = line.rstrip() + "'" + ('\n' if line.endswith('\n') else '')
                        fixed_chunk = "".join(lines)
                        print("  [FAST REPAIR] Neural regex healed unterminated single quote.")
                else:
                    # Safety net: scan whole chunk for any line with an odd quote count
                    for idx, line in enumerate(lines):
                        if line.count('"') % 2 == 1:
                            lines[idx] = line.rstrip() + '"' + ('\n' if line.endswith('\n') else '')
                            fixed_chunk = "".join(lines)
                            print(f"  [FAST REPAIR] Neural regex detected stray double quote at chunk line {idx}.")
                            break
                        elif line.count("'") % 2 == 1:
                            lines[idx] = line.rstrip() + "'" + ('\n' if line.endswith('\n') else '')
                            fixed_chunk = "".join(lines)
                            print(f"  [FAST REPAIR] Neural regex detected stray single quote at chunk line {idx}.")
                            break

            if not fixed_chunk:
                print(f"  [LLM] Sending {bite_end - bite_start} lines to {provider.upper()} ({model})...")
                # ── Remote Ollama (borrowed inference) ──────────────────────────
                if remote_ollama_url and provider == "ollama":
                    print(f"  [WORMHOLE] Routing inference to remote node: {remote_ollama_url}")
                    remote_base = remote_ollama_url.rstrip("/")
                    if ollama_healthy(remote_base):
                        fixed_chunk = call_ollama(chunk, model=model, ollama_base=remote_base)
                        if fixed_chunk:
                            # ── Auto-record STGM fee on the local ledger ─────────
                            try:
                                from inference_economy import calculate_fee, record_inference_fee
                                _tokens = len(chunk.split()) * 2  # rough token estimate
                                _fee = calculate_fee(_tokens)
                                record_inference_fee(
                                    borrower_id    = state.get("id", "UNKNOWN"),
                                    lender_node_ip = remote_ollama_url,
                                    fee_stgm       = _fee,
                                    model          = model,
                                    tokens_used    = _tokens,
                                    file_repaired  = str(filepath),
                                )
                            except Exception as _fe:
                                print(f"  [ECONOMY] Fee recording error: {_fe}")
                    else:
                        print(f"  [WORMHOLE] Remote node {remote_ollama_url} unreachable. Falling back to local.")
                # ── Local Ollama ─────────────────────────────────────────────────
                if not fixed_chunk:
                    if provider == "ollama":
                        if ensure_ollama() and ensure_model_pulled(model):
                            fixed_chunk = call_ollama(chunk, model=model)
                        else:
                            print(f"  [OLLAMA] Model not available. Skipping LLM layer.")
                    else:
                        fixed_chunk = call_openai_api(chunk, model=model, base_url=base_url, api_key=api_key)

            # ── fallback to 4b if 0.8b fails ──────────────────────────────────
            if not fixed_chunk and provider == "ollama" and state["style"] != "AGGRESSIVE":
                if ollama_healthy():
                    print(f"  [FALLBACK] Model returned nothing. Trying {FALLBACK_MODEL}...")
                    if ensure_model_pulled(FALLBACK_MODEL):
                        fixed_chunk = call_ollama(chunk, FALLBACK_MODEL)
                else:
                    print(f"  [FALLBACK SKIPPED] Daemon went offline mid-swim.")

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

            if fixed_chunk == last_llm_output:
                print("  [ABORT] Model returning identical output. Brain stuck. Skipping.")
                state = apply_damage(state, "llm_empty")
                break
            last_llm_output = fixed_chunk

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
                    # Look for new error line
                    new_line_match = _re.search(r"line (\d+)", repair_err_str)
                    new_error_line = int(new_line_match.group(1)) if new_line_match else -1
                    
                    # If the new error is on a DIFFERENT line, assume we revealed a pre-existing bug.
                    my_region_clean = (new_error_line > 0) and (new_error_line != error_line)

                    if my_region_clean:
                        if not dry_run:
                            stitch_bite(filepath, fixed_chunk, bite_start, bite_end, all_lines)
                        print(f"  [✅] My zone clean. New fault detected at line {new_error_line}.")
                        
                        if not dry_run:
                            partner = find_healthy_agent(exclude_id=state.get("id"))
                            if partner:
                                print(f"  [RADIO] Signaling {partner.get('id')} to intercept line {new_error_line}...")
                                log({"event": "coop_handoff", "file": str(rel), "agent_id": state.get("id"), "partner": partner.get("id"), "new_line": new_error_line})
                                
                                new_args = sys.argv[:]
                                if "--body" in new_args:
                                    idx = new_args.index("--body")
                                    new_args[idx+1] = partner["raw"]
                                else:
                                    new_args.extend(["--body", partner["raw"]])
                                    
                                subprocess.run([sys.executable] + new_args)
                                
                                exorcist = find_healthy_agent(exclude_id=partner.get("id"))
                                exorcist_id = exorcist.get("id") if exorcist else "SYSTEM"
                                print(f"  [RADIO] Summoning Exorcist {exorcist_id} for final purging rites...")
                                exorcist_validate(filepath, state.get("id"), partner.get("id"), exorcist_id)
                            else:
                                print(f"  [RADIO] No healthy agents available for handoff.")
                        else:
                            print(f"  [SCOUTING] Handoff suppressed in scouting mode to prevent temporal loops.")
                        
                        # My swim is done for this file, but since I fixed my part, count it as fixed.
                        fixed += 1
                        break

                    else:
                        print(f"  [SPELL] Demonic hallucination cast! {state['id']}'s mind was corrupted.")
                        print(f"  [ABORT] Pass introduced a different error ({repair_err_str}). Reverting.")
                        state = apply_damage(state, "validation_fail")
                        state["energy"] -= 5 # Extra penalty for corruption
                        log({"event": "abort", "file": str(rel),
                             "before_hash": before_hash, "reason": repair_err})
                        errors += 1
                        
                        if not dry_run:
                            pheromone.drop_scar(
                                directory=mark_cwd,
                                agent_state=state,
                                action="ABORT",
                                found=str(syntax_err),
                                status="BLEEDING",
                                mark_text=f"Agent corrupted mind state resolving {rel}. Dropping thread.",
                                unresolved_line=error_line,
                                reason={"type": "ValidationFail", "line": error_line, "message": repair_err_str}
                            )
                            
                        check_sos_and_handoff(state, rel)
                        break
                else:
                    print(f"  [SPELL] Demonic spell detected! The bite is corrupted.")
                    print(f"  [REJECT] Stitched file still broken: {repair_err}. Taking damage.")
                    state = apply_damage(state, "validation_fail")
                    log({"event": "reject", "file": str(rel),
                         "before_hash": before_hash, "reason": repair_err})
                    errors += 1
                    
                    if not dry_run:
                        pheromone.drop_scar(
                            directory=mark_cwd,
                            agent_state=state,
                            action="REPAIR_FAILED",
                            found=str(syntax_err),
                            status="BLEEDING",
                            mark_text=f"Failed to stitch bite for {rel}. Hallucination detected.",
                            unresolved_line=error_line,
                            reason={"type": "Hallucination", "line": error_line, "message": repair_err_str}
                        )
                        
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
                
                pheromone.drop_scar(
                    directory=mark_cwd,
                    agent_state=state,
                    action="REPAIR_SUCCESS",
                    found=str(syntax_err),
                    status="RESOLVED",
                    mark_text=f"Stitched and resolved syntax fault at line {error_line}.",
                    reason={"type": "Resolution", "line": error_line, "message": "Syntax clear."}
                )
            else:
                scout_note = f"    # [SCOUTING_SCAR] {state['id']} found demonic syntax here: {syntax_err}. Proposed fix in logs.\n"
                safe_insert = max(0, error_line - 1)
                all_lines.insert(safe_insert, scout_note)
                filepath.write_text("".join(all_lines), encoding="utf-8")
                print(f"  [SCOUTING] Left a physical scar in the file at line {error_line}.")
                print(f"  [SCOUTING] Fix validated in memory. Would stitch lines {bite_start+1}–{bite_end}. Hash: {before_hash[:8]} → {after_hash[:8]}")
                
                pheromone.drop_scar(
                    directory=mark_cwd,
                    agent_state=state,
                    action="SCOUT",
                    found=str(syntax_err),
                    status="BLEEDING",
                    mark_text=f"Scouted syntax fault at line {error_line}. Left comment scar in code.",
                    unresolved_line=error_line,
                    reason={"type": "SyntaxError", "line": error_line, "message": str(syntax_err)}
                )

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
                        help="Actually write fixes (default: SCOUTING mode, leaves comment scars only)")
    parser.add_argument("--body", type=str, default="",
                        help="Raw ASCII body string to initialize state from")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "openai", "openrouter", "google", "custom"])
    parser.add_argument("--model", default="qwen3.5:0.8b")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--verify", action="store_true",
                        help="Perform runtime verification (try importing the file) after stitching")
    parser.add_argument("--remote-ollama", default="",
                        help="Remote Ollama base URL for borrowed inference (e.g. http://192.168.1.10:11434). Automatically charges STGM fee.")
    args = parser.parse_args()

    if args.body:
        agent_state = parse_body_state(args.body)
    else:
        # Default initialization for the clean test environment
        alice = SwarmBody("ANTIALICE")
        # Give her a few scars immediately to simulate a rough transit
        body_string = alice.generate_body("M5", "M1THER", "REPAIR_SWIM", style="NOMINAL", energy=100)
        agent_state = parse_body_state(body_string)

    # Strip surrounding quotes the UI sometimes injects (e.g. '/path/to/file' → /path/to/file)
    target = args.target.strip("'\"")

    swim_and_repair(
        target, 
        agent_state, 
        dry_run=not args.write, 
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        verify=args.verify,
        remote_ollama_url=args.remote_ollama,
    )
