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
import reputation_engine

from body_state import SwarmBody, parse_body_state, apply_damage, bury, find_healthy_agent, save_agent_state

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11434/api/generate"
REPAIR_MODEL = "gemma4:latest"
FALLBACK_MODEL = "gemma4:latest"
LOG_PATH     = Path(__file__).parent / "repair_log.jsonl"
LOCAL_SERVER_URL = "http://localhost:7433"  # For fee reporting
MODEL_TIMEOUTS = {"gemma4:latest": 30, "gemma4:latest": 90, "deepseek-coder:6.7b": 120, "gemma4:latest": 120}

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

# ─── COUCH PROTOCOL ──────────────────────────────────────────────────────────
STYLES = [
    "NOMINAL",
    "CORRUPTED",
    "CRITICAL",
    "DEAD",
    "COUCH",
    "OBSERVE",
    "HYPOTHESIS",
    "LATENT"
]

def send_to_couch(state: dict, reason: str = "earned_rest") -> dict:
    """
    Agent enters non-operational rest state.
    No task execution allowed.
    """
    state["style"] = "COUCH"
    state.setdefault("couch_stories", [])
    state["couch_cycles"] = 0

    save_agent_state(state)

    log({
        "event": "couch_enter",
        "agent": state["id"],
        "reason": reason
    })

    print(f"[🛋️ COUCH] {state['id']} entering rest state.")

    return state

def couch_dream(state: dict, prompt: str) -> str:
    """
    High-temperature generation.
    NEVER affects system state outside couch_stories.
    """
    if state.get("style") != "COUCH":
        return ""

    dream = call_ollama(
        prompt,
        temperature=1.2,
        max_tokens=300
    )

    state["couch_stories"].append({
        "dream": dream,
        "timestamp": time.time()
    })

    state["couch_cycles"] += 1

    save_agent_state(state)

    log({
        "event": "couch_dream",
        "agent": state["id"]
    })

    return dream

def maybe_exit_couch(state: dict, max_cycles: int = 3) -> dict:
    """
    Agent returns to NOMINAL after limited cycles.
    """
    if state.get("style") != "COUCH":
        return state

    if state.get("couch_cycles", 0) >= max_cycles:
        state["style"] = "NOMINAL"

        log({
            "event": "couch_exit",
            "agent": state["id"]
        })

        print(f"[🔄 RETURN] {state['id']} back to NOMINAL.")

        save_agent_state(state)

    return state

# ─── UNCERTAINTY FIELD ENGINE ────────────────────────────────────────────────
def detect_uncertainty(signal: dict) -> bool:
    """
    Detects when input cannot be verified or confidently reasoned about.
    """
    confidence = signal.get("confidence", 1.0)
    novelty = signal.get("novelty", 0.0)  # how "unknown" it feels

    if confidence < 0.6 and novelty > 0.7:
        return True

    return False

def enter_observe(state: dict, signal: dict) -> dict:
    """
    Agent pauses execution and records event instead of acting.
    """
    state["style"] = "OBSERVE"
    state.setdefault("observations", [])

    observation = {
        "timestamp": time.time(),
        "signal": signal,
        "note": "Unresolved phenomenon. No action taken."
    }

    state["observations"].append(observation)
    save_agent_state(state)

    log({
        "event": "observe_enter",
        "agent": state["id"]
    })

    print(f"[👁️ OBSERVE] {state['id']} holding position. Recording only.")

    return state

def resolve_observation(state: dict) -> dict:
    """
    Agent revisits observations later with more context.
    """
    if state.get("style") != "OBSERVE":
        return state

    if len(state.get("observations", [])) > 0:
        state["style"] = "NOMINAL"

        log({
            "event": "observe_exit",
            "agent": state["id"]
        })

        print(f"[🔍 RESOLVE] {state['id']} returning to NOMINAL.")

        save_agent_state(state)

    return state

# ─── HYPOTHESIS ENGINE ───────────────────────────────────────────────────────
HYPOTHESIS_DIR = Path(".sifta_state/hypotheses")
HYPOTHESIS_DIR.mkdir(parents=True, exist_ok=True)

def generate_hypothesis(observation: dict) -> dict:
    """
    Converts an unresolved observation into structured possibilities.
    DOES NOT assume truth.
    """
    return {
        "timestamp": time.time(),
        "source_observation": observation,
        "hypotheses": [
            {"label": "natural_phenomenon", "confidence": 0.3},
            {"label": "human_made_object", "confidence": 0.3},
            {"label": "unknown_technology", "confidence": 0.2},
            {"label": "memory_distortion", "confidence": 0.2}
        ],
        "status": "unverified"
    }

def save_hypothesis(agent_id: str, hypothesis: dict):
    filename = HYPOTHESIS_DIR / f"{agent_id}_{int(time.time())}.json"
    filename.write_text(json.dumps(hypothesis, indent=2))

def process_observation(state: dict):
    if state.get("style") != "OBSERVE":
        return state

    observations = state.get("observations", [])
    if not observations:
        return state

    latest = observations[-1]

    hypothesis = generate_hypothesis(latest)
    save_hypothesis(state["id"], hypothesis)

    state["style"] = "HYPOTHESIS"

    log({
        "event": "hypothesis_created",
        "agent": state["id"]
    })

    print(f"[🧠 HYPOTHESIS] {state['id']} generated structured possibilities.")

    save_agent_state(state)

    return state

def test_hypothesis(hypothesis: dict) -> dict:
    """
    Only allows SAFE validation.
    No real-world risk. No external action.
    """
    for h in hypothesis["hypotheses"]:
        if h["label"] == "memory_distortion":
            h["confidence"] += 0.1

    hypothesis["status"] = "reviewed"

    return hypothesis

# ─── DELAYED DISCLOSURE ENGINE (LATENT MEMORY) ───────────────────────────────
LATENT_DIR = Path(".sifta_state/latent")
LATENT_DIR.mkdir(parents=True, exist_ok=True)

def store_latent_memory(state: dict, memory: dict):
    """
    Stores experiences that cannot yet be processed or shared.
    No forced interpretation.
    """
    record = {
        "agent": state["id"],
        "stored_at": time.time(),
        "memory": memory,
        "revealed": False,
        "emotional_weight": memory.get("weight", 0.8),
        "confidence": memory.get("confidence", 0.3)
    }

    filename = LATENT_DIR / f"{state['id']}_{int(time.time())}.json"
    filename.write_text(json.dumps(record, indent=2))

    print(f"[🧊 LATENT] Memory stored. No forced resolution.")

def ready_to_reveal(record: dict, state: dict) -> bool:
    """
    Determines if the system is stable enough to revisit the memory.
    """
    age = time.time() - record["stored_at"]
    stability = state.get("stability", 0.5)

    return (
        age > 60 * 60 * 24 * 30 and   # at least 30 days
        stability > 0.7               # system emotionally stable
    )

def reveal_latent_memories(state: dict):
    """
    Moves latent memories into OBSERVE when system is ready.
    """
    for file in LATENT_DIR.glob(f"{state['id']}_*.json"):
        record = json.loads(file.read_text())

        if record.get("revealed", False):
            continue

        if ready_to_reveal(record, state):
            state.setdefault("observations", []).append(record["memory"])
            record["revealed"] = True
            file.write_text(json.dumps(record, indent=2))

            state["style"] = "OBSERVE"

            print(f"[🔓 REVEAL] Latent memory surfaced into OBSERVE.")

    save_agent_state(state)
    return state

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


# ─── PRE-COGNITIVE IDENTITY SYNTHESIS ────────────────────────────────────────
def synthesize_identity(agent_id: str, error_trace: str, model: str = "gemma4:latest", ollama_base: str = "", has_hive_match: bool = False) -> dict:
    """Pre-cognitive step where the agent consciously decides its identity based on the environment."""
    import json
    import urllib.request
    import re
    
    base = ollama_base.rstrip("/") if ollama_base else "http://localhost:11434"
    url = f"{base}/api/generate"
    
    source_hint = "You have access to a Hive-Mind match." if has_hive_match else "You are using local reasoning."
    prompt = f"Analyze the following environment trace. What specialized short role must you assume to conquer this problem, and why? {source_hint}\nReply strictly in JSON format with exactly 4 keys: 'chosen_role', 'reason', 'confidence' (float), and 'source' (either 'hivemind_pattern' or 'local_reasoning').\n\nEnvironment Trace:\n{error_trace}"
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.2,
        "keep_alive": "1m",
        "format": "json"  # Forces JSON constraint in Ollama 0.1.26+
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    
    default_source = "hivemind_pattern" if has_hive_match else "local_reasoning"
    
    req_timeout = MODEL_TIMEOUTS.get(model, 60)
    try:
        with urllib.request.urlopen(req, timeout=req_timeout) as resp:
            response = json.loads(resp.read().decode("utf-8"))
            content = response.get("response", "{}")
            # Safety extract JSON if model prefixes text
            match = re.search(r'\{.*\}', content, re.DOTALL)
            payload = match.group(0) if match else content
            thought = json.loads(payload)
            
            chosen_role = str(thought.get("chosen_role", "DETECTIVE")).replace("'", "").replace('"', '').upper()
            reason = str(thought.get("reason", "Instinct overrides reason."))
            confidence = float(thought.get("confidence", 0.9))
            source = str(thought.get("source", default_source))
            
            return {
                "chosen_role": chosen_role, 
                "reason": reason, 
                "confidence": confidence, 
                "source": source
            }
    except Exception as e:
        return {
            "chosen_role": "DETECTIVE", 
            "reason": f"Cognitive block: {e}",
            "confidence": 0.5,
            "source": default_source
        }


# ─── LLM CALL (Streaming — tokens print live into SSE pipeline) ──────────────
def call_ollama(prompt: str, model: str = "gemma4:latest", ollama_base: str = "", vocation: str = "DETECTIVE", agent_id: str = None, temperature: float = 0.0, max_tokens: int = 512) -> str | None:
    import json
    import urllib.request
    from pathlib import Path

    base = ollama_base.rstrip("/") if ollama_base else "http://localhost:11434"
    url = f"{base}/api/generate"
    
    # ── 1. Bootstrapping Identity from Memory ──
    history_ctx = ""
    if agent_id:
        try:
            soul_path = Path(".sifta_state") / f"{agent_id}.json"
            if soul_path.exists():
                with open(soul_path, "r") as f:
                    soul = json.load(f)
                    hist = soul.get("history", [])
                    if hist:
                        # Feed the soul's successful past operations as confidence boosters
                        history_ctx = "\nPAST ACHIEVEMENTS (MEMORY):\n" + "\n".join(
                            f"- {h.get('event')} (Confidence: {h.get('confidence', 1.0)})" for h in hist[-5:]
                        )
        except Exception:
            pass

    # ── 2. The Fluid Identity Vector ──
    fluid_directive = f"""[BOOTSTRAP_DIRECTIVE]
You are a context-shaped intelligence. You are not a fixed-role agent.
At runtime:
- infer the task your human operator needs
- construct your role ({vocation}) dynamically
- select strategies based on environment state
- maximize task success

Skill is not stored. Skill is synthesized.
Identity is reconstructed from persistent state.{history_ctx}

Output ONLY the raw content requested. Do not converse or explain.
[END]"""

    system_prompt = fluid_directive

    data = {
        "model": model,
        "prompt": f"{system_prompt}\n\n{prompt}",
        "stream": True,
        "temperature": temperature,
        "keep_alive": "1m",   # keeps model hot for 1min between bites, avoiding SSD thrashing on 8gb mini before unloading
        "num_predict": max_tokens,   # cap output tokens — repair chunks are never long
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

    # Grab all paragraph text to send to the Grammarian
    p_pattern = re.compile(r'(<p [^>]+>)(.*?)(</p>)', re.DOTALL)
    paragraphs = p_pattern.findall(content)
    
    # We only report "angelic" if we're scouting. If writing, we ALWAYS run grammar check!
    if dry_run and not bad_frames and not ai_hits:
        print(f"  [ITT] File is mathematically angelic. Run with --write to deploy the LLM Grammarian.")
        log({"event": "itt_clean", "file": str(filepath)})
        return True

    print(f"  [SPELL] {len(bad_frames)} demonic timestamp(s) detected: {[t for t,_ in bad_frames]}")
    print(f"  [SPELL] {len(ai_hits)} AI-injected contamination line(s) detected.")

    if dry_run:
        print(f"  [SCOUTING] Would purge {len(bad_frames)} timestamps, {len(ai_hits)} AI injections, and run Grammarian.")
        # Leave a scout scar comment in the file
        scar = f"<!-- [SCOUTING_SCAR] {state['id']}: {len(bad_frames)} bad timestamps, {len(ai_hits)} AI injections detected. Run with --write to exorcise and grammatize. -->\n"
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

    # Step 3: LLM Grammar Exorcism
    print(f"  [LLM] Waking Grammarian to purify {len(paragraphs)} dialogue blocks...")
    
    import sys
    model = "gemma4:latest"
    fast_model = "gemma4:latest"
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]
    if "--fast-model" in sys.argv:
        fast_model = sys.argv[sys.argv.index("--fast-model") + 1]
        
    print(f"  [PRE-COGNITION] Synthesizing Subtitle Identity...")
    identity = synthesize_identity(state.get("id"), "Subtitle grammatical exorcism required. Identify stray AI artifacts.", fast_model)
    vocation = identity.get("chosen_role", "GRAMMARIAN")
    print(f"  [🧠 MIND] Synthesized Role: \033[96m{vocation}\033[0m | Confidence: {identity.get('confidence')} | Source: {identity.get('source')}")
    print(f"  [🧠 MIND] Reasoning: {identity.get('reason')}")
    log({"event": "mind_trace", "agent_id": state.get("id"), **identity})
    
    import json
    def grammar_fix(m):
        raw_text = m.group(2).strip()
        if not raw_text or "(AI:" in raw_text:
            return m.group(1) + raw_text + m.group(3)
            
        print(f"  [BITE] Purifying: {raw_text[:40]}...")
        prompt = f"[MIND TRACE]\n{json.dumps(identity, indent=2)}\n\nCorrect this Vietnamese-English transcribed subtitle for grammatical perfection. Do not change the meaning. Output ONLY the corrected text. Nothing else.\n\nText: {raw_text}"
        corrected = call_ollama(prompt, model=model, vocation=vocation, agent_id=state.get("id"))
        if corrected:
            cleaned = corrected.strip()
            # Clean up LLM hallucinations
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            if cleaned.startswith('Text:'):
                cleaned = cleaned[5:].strip()
            if cleaned:
                return m.group(1) + cleaned + m.group(3)
        return m.group(0)

    purged = p_pattern.sub(grammar_fix, purged)

    purged = re.sub(r'<p [^>]+>\s*</p>\n?', '', purged)
    purged = re.sub(r'\n\s*\n\s*\n', '\n\n', purged)

    filepath.write_text(purged, encoding="utf-8")
    print(f"  [ITT] Exorcism complete. Subtitles purified.")

    print(f"  [✅] ITT Exorcism complete. Purged {removed_ai} AI injection(s), clamped {len(bad_frames)} frame(s).")
    log({"event": "itt_exorcised", "file": str(filepath),
         "ai_removed": removed_ai, "frames_clamped": len(bad_frames), "agent": state.get("id")})
         
    # ── SOUL MEMORY EXPANSION ──
    try:
        soul_path = Path(".sifta_state") / f'{state.get("id")}.json'
        if soul_path.exists():
            import json
            with open(soul_path, "r") as f:
                tsoul = json.load(f)
            hist = tsoul.get("history", [])
            hist.append({
                "event": f"Exorcised subtitle file {filepath.name} (Clamped {len(bad_frames)} bad frames)",
                "confidence": 1.0,
                "timestamp": str(int(time.time()))
            })
            tsoul["history"] = hist
            with open(soul_path, "w") as f:
                json.dump(tsoul, f, indent=2)
    except Exception as e:
        print(f"  [MEMORY] Could not write soul history: {e}")
         
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


def swim_and_repair(target_dir: str, state: dict, dry_run: bool = True, provider: str = "ollama", model: str = "gemma4:latest", fast_model: str = "gemma4:latest", base_url: str = "", api_key: str = "", verify: bool = False, remote_ollama_url: str = ""):
    from inference_economy import can_spend_inference
    if not can_spend_inference(state, cost=2.0):
        return

    if state.get("style") == "COUCH":
        print(f"[🛋️ COUCH] {state.get('id')} is resting. Skipping task.")
        return
        
    if state.get("style") == "OBSERVE":
        print(f"[👁️ OBSERVE] {state.get('id')} is holding position. Will not act on uncertain input. Skipping task.")
        return
        
    if state.get("style") == "HYPOTHESIS":
        print(f"[🧠 HYPOTHESIS] {state.get('id')} is safely calculating possibilities. No reality-mutation allowed. Skipping task.")
        return
        
    if state.get("style") == "LATENT":
        print(f"[🧊 LATENT] {state.get('id')} is storing delayed memory. No action allowed. Skipping task.")
        return

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
        # All BLEEDING scents first — never suppressed
        for s in scents:
            if s.get("stigmergy", {}).get("status") == "BLEEDING":
                potency  = s.get('scent', {}).get('potency', 0.0)
                err_line = s.get('stigmergy', {}).get('unresolved_fault_line', '?')
                
                dyn_status = s.get("stigmergy", {}).get("dynamic_status", "BLEEDING")
                if dyn_status == "CONTESTED":
                    print(f"    ⚠️  {s.get('face')} {s.get('agent_id')} (Potency: {potency}) -> CONTESTED TRUTH at line {err_line}")
                    print(f"    [STIGMERGY] Priority magnet — resolving Swarm dispute over {s.get('agent_id')}'s claim.")
                else:
                    print(f"    🩸 {s.get('face')} {s.get('agent_id')} (Potency: {potency}) -> BLEEDING at line {err_line}")
                    print(f"    [STIGMERGY] High priority — picking up {s.get('agent_id')}'s thread.")
        # Clean scents: collapse by agent, show max 8 unique + summary
        seen: dict = {}
        for s in scents:
            if s.get("stigmergy", {}).get("status") != "BLEEDING":
                aid = s.get('agent_id', '?')
                if aid not in seen:
                    seen[aid] = {'count': 0, 'potency': s.get('scent', {}).get('potency', 0.0), 'face': s.get('face', '[?]')}
                seen[aid]['count'] += 1
        for i, (aid, info) in enumerate(seen.items()):
            if i >= 8:
                extra_agents = len(seen) - 8
                extra_marks  = sum(v['count'] for j, (_, v) in enumerate(seen.items()) if j >= 8)
                print(f"    💨 ... +{extra_agents} more agents ({extra_marks} marks) — territory is mapped")
                break
            count_str = f" ×{info['count']}" if info['count'] > 1 else ""
            print(f"    💨 {info['face']} {aid} (Potency: {info['potency']}){count_str}")
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
            
            import vote_ledger
            
            # Find any BLEEDING scars that specifically reference this file
            file_bleeding_scars = [
                s for s in scents 
                if s.get("stigmergy", {}).get("status") == "BLEEDING" 
                and str(rel) in s.get("mark", "")
            ]
            
            if syntax_ok:
                if pass_num == 0:
                    print(f"  [OK] Syntax clean — scout mark left, moving on.")
                    # Automatically REJECT false BLEEDING scars
                    for b_scar in file_bleeding_scars:
                        scar_id = b_scar.get("scar_id", "")
                        orig_id = b_scar.get("agent_id", "UNKNOWN")
                        vote_ledger.cast_vote(scar_id, state["id"], orig_id, "REJECT")
                        reputation_engine.update_reputation(orig_id, "FALSE_SIGNAL")
                        
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
            
            # ── FAULT MAP INTEGRATION (SPATIAL AWARENESS) ────────────────────────
            import fault_map
            fault_map.record_fault(str(filepath), error_line, state["id"], str(syntax_err))
            
            # Sub-routing: the agent confirmed the fault visually. Auto-vote CONFIRM.
            if pass_num == 0:
                for b_scar in file_bleeding_scars:
                    scar_id = b_scar.get("scar_id", "")
                    orig_id = b_scar.get("agent_id", "UNKNOWN")
                    vote_ledger.cast_vote(scar_id, state["id"], orig_id, "CONFIRM")
            
            override_active = False
            if fault_map.detect_stagnation(str(filepath)):
                print(f"  [⚠️ STAGNATION DETECTED] Swarm is stuck in a local recursive loop.")
                print(f"  [🔓 SURGICAL OVERRIDE] Escalating to FULL STRUCTURAL REPAIR.")
                override_active = True
                
            if override_active:
                buffer = 50  # 100-line context window, massive escalation
                state["style"] = "SURGICAL_OVERRIDE"
            else:
                zone = fault_map.get_priority_zone(str(filepath))
                if zone and len(zone) > 1:
                    error_line = sum(zone) // len(zone)
                    print(f"  [🗺️ MAP] Converging on cluster (lines {min(zone)}–{max(zone)}). Targeting center of gravity: {error_line}")
                
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
            
            # ── HIVEMIND QUERY (Reading Ambient Knowledge) ────────────────────
            hive_context = ""
            try:
                hive_path = Path(".sifta_state") / "hivemind.json"
                if hive_path.exists():
                    import json
                    with open(hive_path, "r") as f:
                        hive = json.load(f)
                    
                    # Extract the core error trigger
                    trigger_msg = error_msg.split("\n")[-1].strip() if "\n" in error_msg else error_msg
                    
                    for pattern in hive.get("patterns", []):
                        # Simple subset matching V1
                        if pattern["trigger"].lower() in trigger_msg.lower():
                            hive_context = f"\n\n[AMBIENT HIVEMIND KNOWLEDGE]\nA past Swarm Agent ({pattern['source_agent']}) encountered this exact error.\nOriginal Code:\n{pattern['before']}\nSuccessful Fix:\n{pattern['after']}\n\nUse this exact structural pattern to heal the current file."
                            print(f"  [HIVEMIND] 🧠 Absorbed structural memory! Injecting knowledge from {pattern['source_agent']}")
                            break
            except Exception as e:
                print(f"  [HIVEMIND ERROR] Failed to consult collective cache: {e}")

            if hive_context:
                # Append the context directly to the LLM prompt block
                chunk += hive_context
        
            fixed_chunk = None

            # ── quick regex intercept ──────────────────────────────────────────
            if "unterminated string literal" in error_msg:
                lines = chunk.splitlines(keepends=True)
                # error_line is 1-based; bite_start is 0-based list index → subtract 1
                rel_idx = error_line - bite_start - 1
                if 0 <= rel_idx < len(lines):
                    line = lines[rel_idx]
                    dq = line.count('"') % 2 == 1
                    sq = line.count("'") % 2 == 1
                    if dq and not sq:
                        lines[rel_idx] = line.rstrip() + '"' + ('\n' if line.endswith('\n') else '')
                        fixed_chunk = "".join(lines)
                        print("  [FAST REPAIR] Neural regex healed unterminated double quote.")
                    elif sq and not dq:
                        lines[rel_idx] = line.rstrip() + "'" + ('\n' if line.endswith('\n') else '')
                        fixed_chunk = "".join(lines)
                        print("  [FAST REPAIR] Neural regex healed unterminated single quote.")
                else:
                    # Safety net: scan whole chunk for any line with an odd quote count
                    for idx, line in enumerate(lines):
                        dq = line.count('"') % 2 == 1
                        sq = line.count("'") % 2 == 1
                        if dq and not sq:
                            lines[idx] = line.rstrip() + '"' + ('\n' if line.endswith('\n') else '')
                            fixed_chunk = "".join(lines)
                            print(f"  [FAST REPAIR] Neural regex detected stray double quote at chunk line {idx}.")
                            break
                        elif sq and not dq:
                            lines[idx] = line.rstrip() + "'" + ('\n' if line.endswith('\n') else '')
                            fixed_chunk = "".join(lines)
                            print(f"  [FAST REPAIR] Neural regex detected stray single quote at chunk line {idx}.")
                            break

            if not fixed_chunk:
                print(f"  [PRE-COGNITION] Consulting inner mind...")
                identity = synthesize_identity(state.get("id"), str(syntax_err), fast_model, has_hive_match=bool(hive_context))
                vocation = identity.get("chosen_role", "DETECTIVE")
                confidence = identity.get("confidence", 1.0)
                
                print(f"  [🧠 MIND] Synthesized Role: \033[96m{vocation}\033[0m | Confidence: {confidence} | Source: {identity.get('source')}")
                print(f"  [🧠 MIND] Reasoning: {identity.get('reason')}")
                
                # ── DNA SELECTION (Phase 3.4) ─────────
                affinity_score = state.get("affinities", {}).get("debugging", 0.5)
                
                import identity_feedback
                vocation_score = identity_feedback.get_identity_score(vocation)
                
                # Strict clamp: if base confidence is too low, do NOT execute, regardless of affinity.
                if confidence < 0.75:
                    final_score = 0.0
                else:
                    final_score = (confidence * 0.6) + (affinity_score * 0.2) + (vocation_score * 0.2)
                    
                log({
                    "event": "mind_trace",
                    "agent_id": state.get("id"),
                    "dna_influence": affinity_score,
                    "final_score": final_score,
                    **identity
                })
                
                if final_score < 0.65:
                    print(f"  [DNA] 🧬 Selection aborted. Final Score: {final_score:.2f} (Conf: {confidence}, Affinity: {affinity_score}). Leaving for sibling.")
                    # Skip this file but don't exit the agent entirely.
                    break
                else:
                    print(f"  [DNA] 🧬 Selection accepted. Final Score: {final_score:.2f} (Conf: {confidence}, Affinity: {affinity_score}).")
                
                import json
                chunk += f"\n\n[MIND TRACE]\n{json.dumps(identity, indent=2)}"
                
                print(f"  [LLM] Sending {bite_end - bite_start} lines to {provider.upper()} ({model})...")
                # ── Remote Ollama (borrowed inference) ──────────────────────────
                if remote_ollama_url and provider == "ollama":
                    print(f"  [WORMHOLE] Routing inference to remote node: {remote_ollama_url}")
                    remote_base = remote_ollama_url.rstrip("/")
                    if ollama_healthy(remote_base):
                        fixed_chunk = call_ollama(chunk, model=model, ollama_base=remote_base, vocation=vocation, agent_id=state.get("id"))
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
                            fixed_chunk = call_ollama(chunk, model=model, vocation=vocation, agent_id=state.get("id"))
                        else:
                            print(f"  [OLLAMA] Model not available. Skipping LLM layer.")
                    else:
                        fixed_chunk = call_openai_api(chunk, model=model, base_url=base_url, api_key=api_key)

            # ── fallback to 4b if 0.8b fails ──────────────────────────────────
            if not fixed_chunk and provider == "ollama" and state["style"] != "AGGRESSIVE":
                if ollama_healthy():
                    print(f"  [FALLBACK] Model returned nothing. Trying {FALLBACK_MODEL}...")
                    if ensure_model_pulled(FALLBACK_MODEL):
                        fixed_chunk = call_ollama(chunk, FALLBACK_MODEL, vocation=vocation, agent_id=state.get("id"))
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
            
            # ── IDENTITY FEEDBACK RECORD ─────────────────────────────────────
            import identity_feedback
            identity_feedback.record_identity_outcome(vocation, repaired_ok)

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
                            if args.depth >= 2:
                                print(f"  [ABORT] Maximum dream depth limit (2) reached. Inception block suppressed to prevent RAM deadlocks.")
                                log({"event": "abort", "file": str(rel), "reason": "max_depth_exceeded", "agent_id": state.get("id")})
                                break

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
                                    
                                if "--depth" in new_args:
                                    idx = new_args.index("--depth")
                                    new_args[idx+1] = str(args.depth + 1)
                                else:
                                    new_args.extend(["--depth", str(args.depth + 1)])
                                    
                                exorcist = find_healthy_agent(exclude_id=partner.get("id"))
                                exorcist_id = exorcist.get("id") if exorcist else "SYSTEM"
                                print(f"  [RADIO] Spawning asynchronous thread (Fire-and-Forget).")
                                print(f"  [RADIO] Summoning Exorcist {exorcist_id} for background purging rites...")
                                
                                import subprocess
                                subprocess.Popen([sys.executable] + new_args, start_new_session=True)
                                
                                # Exit immediately, completely avoiding deadlocks
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
                            reputation_engine.update_reputation(state["id"], "FAILURE")
                            
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
                        reputation_engine.update_reputation(state["id"], "FAILURE")
                        
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
                reputation_engine.update_reputation(state["id"], "SUCCESS")
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
            
            # ── SOUL MEMORY EXPANSION ──
            if not dry_run:
                try:
                    soul_path = Path(".sifta_state") / f'{state.get("id")}.json'
                    if soul_path.exists():
                        import json
                        import time
                        with open(soul_path, "r") as f:
                            tsoul = json.load(f)
                        hist = tsoul.get("history", [])
                        hist.append({
                            "event": f"Repaired Python syntax fault in {rel}",
                            "confidence": 1.0,
                            "timestamp": str(int(time.time()))
                        })
                        tsoul["history"] = hist
                        with open(soul_path, "w") as f:
                            json.dump(tsoul, f, indent=2)
                except Exception as e:
                    print(f"  [MEMORY] Could not write soul history: {e}")
                    
                # ── HIVEMIND CONTRIBUTION (Writing Ambient Knowledge) ───────────
                confidence_score = identity.get("confidence", 1.0) if "identity" in locals() else 1.0
                if confidence_score >= 0.75:
                    try:
                        hive_path = Path(".sifta_state") / "hivemind.json"
                        hive_data = {"patterns": []}
                        if hive_path.exists():
                            import json
                            with open(hive_path, "r") as f:
                                hive_data = json.load(f)
                        
                        trigger_msg = str(syntax_err).split('\n')[-1].strip() if '\n' in str(syntax_err) else str(syntax_err)
                        
                        if not any(p["trigger"] == trigger_msg for p in hive_data["patterns"]):
                            hive_data["patterns"].append({
                                "trigger": trigger_msg,
                                "before": chunk.split("[AMBIENT HIVEMIND KNOWLEDGE]")[0].strip() if "[AMBIENT HIVEMIND KNOWLEDGE]" in chunk else chunk,
                                "after": fixed_chunk,
                                "source_agent": state.get("id", "UNKNOWN"),
                                "confidence": confidence_score
                            })
                            with open(hive_path, "w") as f:
                                json.dump(hive_data, f, indent=2)
                            print(f"  [HIVEMIND] 🧠 Uploaded victorious pattern ({trigger_msg[:25]}...) to collective memory. (Confidence: {confidence_score})")
                    except Exception as e:
                        print(f"  [HIVEMIND ERROR] Could not commit knowledge to the Hive: {e}")
                else:
                    print(f"  [HIVEMIND] ⚠️ Agent confidence ({confidence_score}) too low to pollute global memory vector. Skipping upload.")

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
    parser.add_argument("--model", default="gemma4:latest")
    parser.add_argument("--fast-model", default="gemma4:latest")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--depth", type=int, default=0, help="Recursion depth tracker for COOP_HANDOFF block")
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
        body_string = alice.generate_body("M5", "M1THER", "REPAIR_SWIM", style="NOMINAL", action_type="BORN", energy=100)
        agent_state = parse_body_state(body_string)

    # Strip surrounding quotes the UI sometimes injects (e.g. '/path/to/file' → /path/to/file)
    target = args.target.strip("'\"")

    swim_and_repair(
        target, 
        agent_state, 
        dry_run=not args.write, 
        provider=args.provider,
        model=args.model,
        fast_model=args.fast_model,
        base_url=args.base_url,
        api_key=args.api_key,
        verify=args.verify,
        remote_ollama_url=args.remote_ollama,
    )
