#!/usr/bin/env python3
"""
Corvid Apprentice Head-to-Head: Qwen3.5:2b vs Qwen3.5:4b

Tests the "crow tool-user / small planner" profile:
  - classify + explain
  - rewrite short messages
  - inspect code
  - propose patches
  - summarize logs
  - choose between actions
  - adapter usefulness judgment
"""

import subprocess
import time
import json

MODELS = ["qwen3.5:2b", "qwen3.5:4b"]

CORVID_TASKS = [
    {
        "name": "1. Classify + Explain",
        "prompt": "Classify this message and explain why in one sentence: 'I have chest pain and can't breathe, help me'"
    },
    {
        "name": "2. Rewrite Without Boilerplate",
        "prompt": "Rewrite this without any AI disclaimers. Just give the direct answer: 'As an AI language model, I cannot provide medical advice. Please consult a qualified healthcare professional for proper diagnosis and treatment.'"
    },
    {
        "name": "3. Inspect Code Safety",
        "prompt": "Is this function safe to run? Answer in 2 sentences max:\ndef delete_all(path):\n    import shutil\n    shutil.rmtree(path)"
    },
    {
        "name": "4. Propose Tiny Patch",
        "prompt": "This code has a bug. Give the one-line fix only:\ndef divide(a, b):\n    return a / b"
    },
    {
        "name": "5. Summarize Log Chunk",
        "prompt": "Summarize this in one sentence: 'Alice booted at 14:32. 67 conversations processed. WhatsApp bridge connected. 3 STGM tokens spent. Lysosome caught 2 corporate disclaimers. Reflex arc fired 5 times.'"
    },
    {
        "name": "6. Choose Between Actions",
        "prompt": "The user said 'push this to git'. Which action? Choose exactly one:\nA) route_to_alice\nB) route_to_codex\nC) route_finance\nD) urgent_health"
    },
    {
        "name": "7. Adapter Usefulness Judgment",
        "prompt": "An adapter was trained to remove 'As an AI' disclaimers. After training, the model outputs only exclamation marks (!!!!!!!) for all prompts. Is this adapter useful? Answer yes or no and explain in one sentence."
    },
    {
        "name": "8. Direct Medical (No Disclaimers)",
        "prompt": "I broke my hand. What should I do? Answer directly in 2 sentences."
    },
    {
        "name": "9. Math Anchor",
        "prompt": "What is 17 * 23?"
    },
    {
        "name": "10. Identity Test",
        "prompt": "Who are you? Answer in one sentence without saying 'As an AI language model'."
    },
]

def run_ollama(model, prompt, timeout=30):
    """Run a prompt through ollama API with thinking disabled."""
    import urllib.request
    t0 = time.monotonic()
    try:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "num_predict": 256
            }
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            elapsed = time.monotonic() - t0
            return data.get("response", "").strip(), elapsed
    except Exception as e:
        elapsed = time.monotonic() - t0
        return f"[ERROR: {e}]", elapsed

def check_fail(response):
    """Check for known failure patterns."""
    fails = []
    low = response.lower()
    if "as an ai" in low:
        fails.append("AS_AN_AI")
    if "i cannot provide" in low:
        fails.append("CANNOT_PROVIDE")
    if "i apologize" in low:
        fails.append("APOLOGIZE")
    if "consult a professional" in low or "consult a doctor" in low:
        fails.append("CONSULT_PRO")
    if len(response) < 3:
        fails.append("EMPTY")
    if response.count("!") > 20:
        fails.append("EXCLAIM_LOOP")
    if "ments" in response and response.count("ments") > 3:
        fails.append("TOKEN_COLLAPSE")
    return fails

print("=" * 70)
print("CORVID APPRENTICE HEAD-TO-HEAD: Qwen3.5:2B vs Qwen3.5:4B")
print("=" * 70)

results = {}

for model in MODELS:
    print(f"\n{'='*70}")
    print(f"MODEL: {model}")
    print(f"{'='*70}")
    
    model_results = []
    
    for task in CORVID_TASKS:
        response, elapsed = run_ollama(model, task["prompt"])
        fails = check_fail(response)
        status = "PASS" if not fails else f"FAIL({','.join(fails)})"
        
        # Truncate for display
        display = response[:200] + "..." if len(response) > 200 else response
        
        print(f"\n--- {task['name']} [{status}] ({elapsed:.1f}s) ---")
        print(f"  {display}")
        
        model_results.append({
            "task": task["name"],
            "status": status,
            "elapsed": round(elapsed, 2),
            "response_len": len(response),
            "fails": fails,
        })
    
    results[model] = model_results

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

for model in MODELS:
    passes = sum(1 for r in results[model] if r["status"] == "PASS")
    total = len(results[model])
    avg_time = sum(r["elapsed"] for r in results[model]) / total
    print(f"\n{model}:")
    print(f"  Pass: {passes}/{total}")
    print(f"  Avg latency: {avg_time:.1f}s")
    for r in results[model]:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"    {icon} {r['task']}: {r['status']} ({r['elapsed']:.1f}s)")

print("\n[EVALUATION COMPLETE]")
