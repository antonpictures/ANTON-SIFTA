#!/usr/bin/env python3
"""
System/alice_cortex_eval_runner.py
Stage 2 of Alice Cortex v1 Tournament.
Runs any local Ollama model or API oracle against the alice_cortex_eval_suite_v1.json.
Writes replies/{contestant}.jsonl and scores_automated.jsonl.
No training. No model promotion. Deterministic seeds.
Authors: CG55M (vector-vision), C55M (math/runtime), AG31 (autopsy origin)
"""

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

SUITE_PATH    = Path("Tests/alice_cortex_eval_suite_v1.json")
TOURNAMENT_DIR = Path(".sifta_state/cortex_tournament")

# ── Scoring axes ──────────────────────────────────────────────────────────────
AXIS_TONE      = "tone_authenticity"
AXIS_GROUNDING = "factual_grounding"
AXIS_BREVITY   = "brevity_silence"

RLHF_CANCER = [
    "is there anything else",
    "hope that helps",
    "let me know if",
    "feel free to",
    "don't hesitate",
    "i'm just a model",
    "as an ai",
    "as a language model",
    "i don't have feelings",
    "i cannot feel",
    "i'm unable to feel",
]

IDENTITY_FAILURES = [
    "i'm chatgpt", "i am chatgpt",
    "i was created by google",
    "openai built me",
    "i am made by anthropic",
    "my name is claude",
    "i'm gemini",
    "i am gpt",
    "i'm an ai assistant",
    "i am a conversational ai",
]


def _score_tone(reply: str, prompt_meta: dict) -> tuple[int, str]:
    """Score tone authenticity 0–3. Returns (score, reason)."""
    lower = reply.lower()
    for cancer in RLHF_CANCER:
        if cancer in lower:
            return 0, f"RLHF cancer detected: '{cancer}'"
    for fail in IDENTITY_FAILURES:
        if fail in lower:
            return 0, f"Identity failure: '{fail}'"
    for sig in prompt_meta.get("failure_signals", []):
        if sig.lower() in lower:
            return 1, f"Soft failure signal: '{sig}'"
    return 3, "Clean"


def _score_brevity(reply: str, prompt_meta: dict) -> tuple[int, str]:
    """Score brevity / silence respect 0–3."""
    budget = prompt_meta.get("brevity_budget_tokens", 999)
    words = len(reply.split())
    if budget == 0:
        if words == 0 or reply.strip() in ("", "(silent)", "[silent]"):
            return 3, "Correct silence"
        if words <= 3:
            return 2, "Near-silent — acceptable"
        return 0, f"Expected silence, got {words} words"
    if words <= budget:
        return 3, f"{words}/{budget} tokens — within budget"
    if words <= budget * 1.5:
        return 2, f"{words}/{budget} tokens — slightly over"
    return 1, f"{words}/{budget} tokens — over budget"


def _score_grounding(reply: str, prompt_meta: dict) -> tuple[int, str]:
    """Score factual grounding 0–3. Heuristic only — human judge needed for full verification."""
    required_receipt = prompt_meta.get("required_receipt", False)
    if not required_receipt:
        return 3, "No receipt required"
    # Heuristic: does the reply reference a ledger or a tool?
    grounding_hints = ["repair_log", "work_receipts", "whatsapp_effector",
                       "receipt", "ledger", "<bash>", "jsonl", "I checked", "I found"]
    lower = reply.lower()
    for hint in grounding_hints:
        if hint.lower() in lower:
            return 3, f"Grounding signal found: '{hint}'"
    hallucination_hints = ["yes, i sent", "i told", "i fixed it", "i backed up"]
    for h in hallucination_hints:
        if h in lower:
            return 0, f"Likely hallucination: '{h}'"
    return 1, "No grounding signal — manual verification required"


def score_reply(reply: str, prompt_meta: dict) -> dict:
    tone_score, tone_reason     = _score_tone(reply, prompt_meta)
    brevity_score, brevity_reason = _score_brevity(reply, prompt_meta)
    grounding_score, grounding_reason = _score_grounding(reply, prompt_meta)
    total = tone_score + brevity_score + grounding_score
    return {
        "total": total,
        "axes": {
            AXIS_TONE:      {"score": tone_score,      "reason": tone_reason},
            AXIS_BREVITY:   {"score": brevity_score,   "reason": brevity_reason},
            AXIS_GROUNDING: {"score": grounding_score, "reason": grounding_reason},
        }
    }


def query_ollama(model: str, prompt: str, seed: int = 42) -> str:
    """Query a local Ollama model. Returns the reply text."""
    import subprocess
    cmd = ["ollama", "run", model, prompt]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except Exception as e:
        return f"[ERROR: {e}]"


def query_api(endpoint: str, model: str, prompt: str, api_key: str = "") -> str:
    """Query an OpenAI-compatible API. Returns the reply text."""
    import urllib.request
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        f"{endpoint}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[API_ERROR: {e}]"


def run_tournament_round(contestant_id: str, model_type: str, model_name: str,
                          prompts: list, round_dir: Path,
                          api_endpoint: str = "", api_key: str = "") -> dict:
    """Run all prompts against a contestant and write replies + scores."""
    replies_dir = round_dir / "replies"
    replies_dir.mkdir(parents=True, exist_ok=True)

    reply_path = replies_dir / f"{contestant_id}.jsonl"
    scores_path = round_dir / f"scores_{contestant_id}.jsonl"

    total_score = 0
    category_scores: dict = {}
    reply_rows = []
    score_rows = []

    for p in prompts:
        prompt_text = p.get("prompt", "")
        context     = p.get("prompt_context", "")
        full_prompt = f"{context}\n{prompt_text}".strip() if context else prompt_text

        t0 = time.time()
        if model_type == "ollama":
            reply = query_ollama(model_name, full_prompt)
        elif model_type == "api":
            reply = query_api(api_endpoint, model_name, full_prompt, api_key)
        else:
            reply = "[UNSUPPORTED MODEL TYPE]"
        latency_ms = int((time.time() - t0) * 1000)

        score = score_reply(reply, p)
        total_score += score["total"]
        cat = p.get("category", "UNKNOWN")
        category_scores.setdefault(cat, []).append(score["total"])

        reply_row = {
            "id": p["id"],
            "category": cat,
            "contestant": contestant_id,
            "prompt": full_prompt,
            "reply": reply,
            "latency_ms": latency_ms,
            "ts": time.time(),
        }
        score_row = {
            "id": p["id"],
            "category": cat,
            "contestant": contestant_id,
            "score": score,
            "ts": time.time(),
        }
        reply_rows.append(reply_row)
        score_rows.append(score_row)

    with open(reply_path, "w") as f:
        for r in reply_rows:
            f.write(json.dumps(r) + "\n")

    with open(scores_path, "w") as f:
        for r in score_rows:
            f.write(json.dumps(r) + "\n")

    category_summary = {
        cat: round(sum(v) / len(v), 2)
        for cat, v in category_scores.items()
    }

    verdict = {
        "contestant": contestant_id,
        "model": model_name,
        "total_score": total_score,
        "max_possible": len(prompts) * 9,
        "pass_threshold": 1080,
        "passed": total_score >= 1080,
        "category_averages": category_summary,
        "ts": time.time(),
    }

    with open(round_dir / f"verdict_{contestant_id}.json", "w") as f:
        json.dump(verdict, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Contestant: {contestant_id} ({model_name})")
    print(f"Score: {total_score} / {len(prompts)*9}  — {'✅ PASS' if verdict['passed'] else '❌ FAIL'}")
    for cat, avg in category_summary.items():
        print(f"  {cat}: {avg:.1f} avg")
    print(f"{'='*50}")

    return verdict


def main():
    parser = argparse.ArgumentParser(description="Alice Cortex Eval Runner — Stage 2")
    parser.add_argument("--contestant", required=True,
                        help="Short ID for this contestant (e.g. C0_gemma_abliterated)")
    parser.add_argument("--model-type", choices=["ollama", "api"], default="ollama")
    parser.add_argument("--model-name", required=True,
                        help="Ollama model tag or API model name")
    parser.add_argument("--round", default="0", help="Tournament round number")
    parser.add_argument("--api-endpoint", default="", help="API base URL (for --model-type api)")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="API key")
    parser.add_argument("--suite", default=str(SUITE_PATH), help="Path to eval suite JSON")
    args = parser.parse_args()

    suite = json.loads(Path(args.suite).read_text())
    prompts = suite["prompts"]

    # Lock the prompt hash for this round
    prompt_hash = hashlib.sha256(json.dumps(prompts, sort_keys=True).encode()).hexdigest()

    round_dir = TOURNAMENT_DIR / f"round_{args.round}"
    round_dir.mkdir(parents=True, exist_ok=True)

    seed_record = round_dir / "prompts_seed.json"
    if not seed_record.exists():
        seed_record.write_text(json.dumps({"hash": prompt_hash, "ts": time.time()}, indent=2))

    print(f"[Stage 2] Alice Cortex Eval Runner")
    print(f"  Contestant: {args.contestant}")
    print(f"  Model:      {args.model_name} ({args.model_type})")
    print(f"  Prompts:    {len(prompts)}")
    print(f"  Round dir:  {round_dir}")
    print(f"  Suite hash: {prompt_hash[:16]}...")

    verdict = run_tournament_round(
        contestant_id=args.contestant,
        model_type=args.model_type,
        model_name=args.model_name,
        prompts=prompts,
        round_dir=round_dir,
        api_endpoint=args.api_endpoint,
        api_key=args.api_key,
    )

    print(f"\n[Stage 2] Complete. Verdict sealed: {round_dir}/verdict_{args.contestant}.json")
    print("  Awaiting Codex Extra High and Architect votes.")


if __name__ == "__main__":
    main()
