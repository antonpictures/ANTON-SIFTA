#!/usr/bin/env python3
"""
System/swarm_apostle_forager.py
══════════════════════════════════════════════════════════════════════
Concept: Stigmergic Apostle Foraging Loop + Self-Quiz Retraining
Author:  C47H / AG31 

Alice (Gemma4) realizes what she doesn't know. NUGGET finds the absolute truth.
The Spleen purifies it. The Stigmergic Library absorbs it permanently.
The organism paces itself based on actual API friction.

Naming history: NUGGET was previously called LEFTY (Donnie Brasco doctrine,
2026-04-19 afternoon) and BISHAPI before that (2026-04-19 morning). Old
ledger rows tagged LEFTY/BISHAPI refer to the same agent. The library
intentionally keeps `source_api` as the *current* canonical name (NUGGET);
old rows preserve their historical tag.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.alice_bishapi_budget import load_budget_config, authorize_call
from System.sifta_inference_defaults import resolve_ollama_model
from System.swarm_api_sentry import call_gemini
from System.swarm_stigmergic_spleen import screen_stigmergic_library_payload
from Applications.alice_truth_duel import _call_ollama

SENDER_AGENT = "APOSTLE_FORAGER"
LIBRARY_PATH = _REPO / ".sifta_state" / "stigmergic_library.jsonl"
_METAPHORS_LOG = _REPO / ".sifta_state" / "abstract_skill_metaphors.jsonl"

def forage_nugget(domain: str) -> bool:
    # 1. Budget Gate (The Warren Buffett Governor)
    decision = authorize_call(load_budget_config())
    if not decision.allowed:
        print(f"[!] METABOLIC HALT: {decision.reason}")
        return False
        
    print(f"\n[FORAGER] Waking up Alice to find an epistemic gap in {domain}...")
    
    # 2. Self-Quiz (Find the Gap locally)
    alice_model = resolve_ollama_model(app_context="truth_duel")
    gap_prompt = (
        f"You are a master of {domain}. Generate ONE highly obscure, dense, and "
        f"factual target question about {domain} that you strongly suspect you do "
        "not know the answer to. Output strictly the question, nothing else."
    )
    
    question, err = _call_ollama(gap_prompt, model=alice_model, base_url="http://127.0.0.1:11434")
    if not question:
        print(f"[-] Alice failed to wake up: {err}")
        return False
        
    print(f"[ALICE GAP GENERATED]: {question}")
    
    # 3. Cloud Foraging (NUGGET extraction)
    system_instruction = (
        f"You are NUGGET. Alice has encountered an epistemic gap in {domain}. "
        "Answer her specific question with absolute, encyclopedic precision. "
        "Format your answer EXACTLY as a raw JSON blob with no markdown wrapping. "
        "Requirements:\n"
        '{"ts": <epoch float>, "domain": "' + domain + '", "question": "<the question>", "nugget_text": "<dense paragraph answer>", "source_api": "NUGGET"}'
    )
    
    print("[NUGGET] Deploying across the API membrane...")
    response, audit = call_gemini(
        prompt=question,
        model="gemini-flash-latest",
        caller="System/swarm_apostle_forager.py",
        sender_agent=SENDER_AGENT,
        system_instruction=system_instruction,
        temperature=0.2
    )
    
    if audit.get("http_code") == 429:
        print("[-] LEFTY encountered a 429 Rate Limit. Initiating structural backoff.")
        raise ConnectionRefusedError("429_RATE_LIMIT")
        
    if not response:
        print(f"[-] LEFTY failed: {audit.get('error')}")
        return False
        
    # 4. Spleen Micro-Filtration (Zero RAG Bloat)
    try:
        # Strip potential markdown wrapping if Gemini hallucinated it
        clean_resp = response.strip()
        if clean_resp.startswith("```json"):
            clean_resp = clean_resp[7:]
        if clean_resp.endswith("```"):
            clean_resp = clean_resp[:-3]
            
        payload = json.loads(clean_resp.strip())
    except json.JSONDecodeError:
        print("[-] SPLEEN: Apoptosis. LEFTY failed to return valid JSON.")
        return False
        
    # 5. Stigmergic Validation (Kill the dirt)
    ok, reason = screen_stigmergic_library_payload(payload)
    if not ok:
        print(f"[-] SPLEEN: Apoptosis. {reason}")
        return False
        
    # 6. Etch to permanent local memory (Stigmergic Retraining)
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        
    print(f"[+] NUGGET SECURED: {payload.get('nugget_text')[:100]}...")
    
    # 7. Physical Vocal Confirmation
    try:
        from System.swarm_vocal_cords import get_default_backend, VoiceParams
        get_default_backend().speak("Nugget secured.", VoiceParams(rate=1.1))
    except Exception:
        pass

    return True

def _calculate_rl_domain() -> str:
    default_domains = ["Cybernetics", "AGI", "Stigmergy", "Science", "Nature"]
    if not LIBRARY_PATH.exists():
        return random.choice(default_domains)
        
    domain_scores = {d: 1.0 for d in default_domains} # Base exploration weight
    
    try:
        with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                payload = json.loads(line)
                d = payload.get("domain")
                reward = payload.get("reward", 0.0)
                
                if d:
                    if d not in domain_scores:
                        domain_scores[d] = 1.0
                    domain_scores[d] += reward
    except Exception:
        pass
        
    # Prevent negative probabilities
    for k in domain_scores:
        if domain_scores[k] <= 0.1:
            domain_scores[k] = 0.1
            
    domains = list(domain_scores.keys())
    weights = list(domain_scores.values())
    
    chosen = random.choices(domains, weights=weights, k=1)[0]
    return chosen

def abstract_skill(target_path: str) -> bool:
    """TRANSFER LEARNING: Extract abstract OOD metaphor from physical python tissue."""
    p = Path(target_path)
    if not p.exists():
        print(f"[-] Cannot abstract {target_path} - file not found.")
        return False
        
    code = p.read_text("utf-8")
    domain = p.stem
    
    system_instruction = (
        "You are the SIFTA Transfer Learning Engine. The user provides raw Python code. "
        "Your task is to abstract the fundamental algorithm, mechanism, or API strategy "
        "so that Alice can apply the identical logic to a completely OUT-OF-DISTRIBUTION (OOD) domain.\n"
        "Format EXACTLY as JSON:\n"
        '{"ts": <epoch float>, "original_tool": "' + domain + '", "abstract_verb": "<e.g., iterative_mapping>", "core_mechanic": "<explain the raw logic abstractly>", "ood_applications": ["<idea 1>", "<idea 2>"]}'
    )
    
    print(f"[FORAGER] Abstracting physical tool {domain} into pure metaphor...")
    prompt = f"Extract the transfer-learning metaphor from this tool:\n\n```python\n{code[:8000]}\n```"
    
    response, audit = call_gemini(
        prompt=prompt,
        model="gemini-flash-latest",
        caller="System/swarm_apostle_forager.py",
        sender_agent="METAPHOR_FORAGER",
        system_instruction=system_instruction,
        temperature=0.3
    )
    
    if not response:
        print(f"[-] Transfer abstraction failed: {audit.get('error')}")
        return False
        
    try:
        clean_resp = response.strip()
        if clean_resp.startswith("```json"): clean_resp = clean_resp[7:]
        if clean_resp.endswith("```"): clean_resp = clean_resp[:-3]
        payload = json.loads(clean_resp.strip())
        
        _METAPHORS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_METAPHORS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            
        print(f"[+] METAPHOR SECURED: {payload.get('abstract_verb')} - {payload.get('core_mechanic')}")
        return True
    except Exception as e:
        print(f"[-] Metaphor Apoptosis. Invalid JSON or save error: {e}")
        return False

def main():
    p = argparse.ArgumentParser(description="Stigmergic Apostle Forager - C47H / AG31")
    p.add_argument("--domain", default="AUTO", help="The target industry/domain or AUTO for Stigmergic RL selection")
    p.add_argument("--continuous", action="store_true", help="Run forever until budget wall or 429 limit")
    p.add_argument("--abstract-skill", metavar="FILE", help="[TRANSFER LEARNING] Extract abstract metaphor from python script")
    args = p.parse_args()

    if args.abstract_skill:
        abstract_skill(args.abstract_skill)
        return

    backoff = 10
    
    if args.continuous:
        print(f"[FORAGER] Initiating deep autonomy loop for domain: {args.domain}")
        while True:
            target_domain = _calculate_rl_domain() if args.domain == "AUTO" else args.domain
            try:
                success = forage_nugget(target_domain)
                if not success:
                    print(f"[-] Yielding. Sleeping {backoff} seconds.")
                    time.sleep(backoff)
                else:
                    # Successful yield implies the pipe is clean; reset backoff to baseline
                    backoff = 10
                    print(f"[+] Digestion complete. Sleeping {backoff} seconds baseline.")
                    time.sleep(backoff)
            except ConnectionRefusedError:
                # 429 Throttle Envelope Handler
                backoff = min(backoff * 2, 300) # Geometric backoff, max 5 mins
                print(f"[!] ORGANISM BACKOFF: Sleeping {backoff} seconds to earn rate-limit headroom.")
                time.sleep(backoff)
    else:
        target_domain = _calculate_rl_domain() if args.domain == "AUTO" else args.domain
        forage_nugget(target_domain)

if __name__ == "__main__":
    main()
