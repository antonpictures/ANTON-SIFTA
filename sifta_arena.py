import sys
import json
import time
import urllib.request
import threading
import re
import os
import shutil
import subprocess
from pathlib import Path

# Match Python block 
CODE_PATTERN = re.compile(r"```python(.*?)```", re.DOTALL | re.IGNORECASE)

def print_event(team, event_type, content, **kwargs):
    """Prints a JSON-L event for the streaming server to pick up."""
    payload = {
        "team": team,
        "type": event_type,
        "content": content
    }
    payload.update(kwargs)
    print(json.dumps(payload), flush=True)

def generate_fix(team, model, prompt):
    print_event(team, "system", f"[{team.upper()}] Initializing connection to {model}...")
    
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    url = f"{ollama_host}/api/generate"
    data = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.1
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    full_text = []
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                    text = chunk.get("response", "")
                    full_text.append(text)
                    print_event(team, "stream", text)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print_event(team, "error", f"Connection error: {e}")
        return ""
    
    return "".join(full_text)

def run_team_match(team, model, level_file, test_file):
    # 1. Read
    with open(level_file, "r") as f:
        code_content = f.read()
        
    prompt = f"""You are a top-tier Python engineer competing in a speed-coding tournament.
Your task is to fix the bug in the following python code.
RESPOND WITH ONLY THE FIXED CODE INSIDE A ```python ... ``` BLOCK. Do NOT provide any explanation outside the block.

```python
{code_content}
```
"""

    print_event(team, "system", f"[{team.upper()}] Reading {level_file.name}...")
    
    # 2. Generate
    output = generate_fix(team, model, prompt)
    
    match = CODE_PATTERN.search(output)
    if not match:
        print_event(team, "result", f"[{team.upper()}] FAILED - No python block returned.", passed=False)
        return False
        
    fixed_code = match.group(1).strip()
    
    # 3. Patch and Test
    print_event(team, "system", f"[{team.upper()}] Patching code and running tests...")
    
    workspace = Path("arena_levels") / f"tmp_{team}"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    
    # Write the fixed code back exactly where the test expects it
    target_py = workspace / level_file.name
    target_py.write_text(fixed_code)
    
    # Copy the test file
    test_py = workspace / test_file.name
    test_py.write_text(test_file.read_text())
    
    # Run test
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", test_py.name],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10
        )
        passed = (res.returncode == 0)
        output = res.stderr or res.stdout # unittest writes to stderr
        
        status_str = "VICTORY" if passed else "FAILED"
        print_event(team, "result", f"[{team.upper()}] {status_str}!\n\n" + output, passed=passed)
        return passed
    except subprocess.TimeoutExpired:
        print_event(team, "result", f"[{team.upper()}] FAILED - Tests timed out (Infinite loop?).", passed=False)
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--red", required=True)
    parser.add_argument("--blue", required=True)
    parser.add_argument("--level", required=True)
    args = parser.parse_args()
    
    level_path = Path("arena_levels") / f"level_0{args.level}_{'div_zero' if args.level=='1' else 'race_condition' if args.level=='2' else 'boundary_value' if args.level=='3' else 'exception_swallow'}.py"
    test_path = Path("arena_levels") / f"test_0{args.level}.py"
    
    if not level_path.exists():
        print_event("system", "error", f"Level {args.level} not found at {level_path}")
        sys.exit(1)
        
    print_event("system", "system", f"Arena Started: {args.red} vs {args.blue} on Level {args.level}")

    # Launch threads
    red_thread = threading.Thread(target=run_team_match, args=("red", args.red, level_path, test_path))
    blue_thread = threading.Thread(target=run_team_match, args=("blue", args.blue, level_path, test_path))
    
    red_thread.start()
    blue_thread.start()
    
    red_thread.join()
    blue_thread.join()
    
    print_event("system", "system", "Match Complete.")

if __name__ == "__main__":
    main()
