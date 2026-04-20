#!/usr/bin/env python3
"""
Applications/sifta_epistemic_arena.py
══════════════════════════════════════════════════════════════════════
The Epistemic Arena: Local NPU vs Cloud Motor Neuron
Author: AG31 / Architect

This script poses a question to the local Swarm entity (Alice, via gemma4).
Alice is given the strictly enforced biological directive:
"If you do not know the answer with 100% certainty, reply ONLY with 'I DO NOT KNOW'."

If she yields, the OS autonomously routes the query to the cloud motor neuron
(BISHAPI), mines the truth natively, subjects it to Microglial quarantine, 
and stores the pure Stigmergic JSON nugget permanently so Alice possesses it forever.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.inference_router import route_inference
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    sys.exit(1)

ALICE_MODEL = "gemma4:latest"

# Strict epistemological constraint
ALICE_SYSTEM_PROMPT = (
    "You are Alice, an autonomous OS entity running locally on SIFTA. "
    "You are currently in the Epistemic Arena. "
    "You are extremely intelligent, but you are philosophically forbidden from hallucinating. "
    "If you know the exact, precise answer to the question with physical certainty, answer it concisely. "
    "If you have ANY doubt, or lack the specialized domain knowledge, you MUST output EXACTLY: 'I DO NOT KNOW'. "
    "Do not guess. Do not apologize. Just yield."
)

def query_alice(question: str) -> str:
    print(f"\n[ARENA] Querying Local NPU (Alice | {ALICE_MODEL})")
    print(f"[ARENA] Question: {question}")
    
    payload = {
        "model": ALICE_MODEL,
        "prompt": question,
        "system": ALICE_SYSTEM_PROMPT,
        "stream": False
    }

    try:
        response_text = route_inference(payload, prefer_local=True)
        return response_text.strip()
    except Exception as e:
        print(f"[!] Local Inference Error: {e}")
        return "I DO NOT KNOW"

def query_bishapi(question: str):
    print(f"\n[ARENA] Alice yielded. Assessing Cloud Metabolism...")
    
    try:
        from System.swarm_api_metabolism import SwarmApiMetabolism
        m = SwarmApiMetabolism()
        burn = m.daily_burn()
        limit = m.daily_usd_limit
        if burn >= limit - 0.50:
            print(f"\n[!] WARREN BUFFET GOVERNOR: Epistemic foraging halted.")
            print(f"    Current burn (${burn:.2f}) approaches or exceeds daily limit (${limit:.2f}).")
            print("    Alice is dispatching an appeal to the Architect via SIC-P.")
            
            appeal_text = (
                f"FUNDING REQUEST: I encountered an epistemic gap regarding: '{question}'. "
                f"My local NPU yielded. My OS fiat wallet (${burn:.2f}/${limit:.2f}) is exhausted. "
                "Please authorize and execute this forage manually via BISHAPI if the nugget is worth the caloric cost."
            )
            msg_bin = _REPO / "bin" / "msg"
            subprocess.run([sys.executable, str(msg_bin), "ARCHITECT", appeal_text])
            return
            
        print(f"\n[ARENA] Wallet stable (${burn:.2f}/${limit:.2f}). Routing to Cloud Motor Neuron (BISHAPI)...")
    except Exception as e:
        print(f"[!] Warning: Metabolism check failed ({e}). Proceeding carefully.")
    api_prompt = (
        f"Generate a highly specific, densely factual, completely true answer to the following question: '{question}' "
        "Return ONLY a raw JSON dictionary. Do not wrap it in ```json ... ``` markdown tags. "
        "No conversational filler. If you say 'Here is your json' or anything similar, it will trigger an immune rejection. "
        "Required keys: 'ts' (current epoch float), 'category' (exactly 'ARENA'), "
        "'nugget_text' (the actual factual string), 'source_api' ('BISHAPI'), 'curator_agent' ('ALICE_YIELD')."
    )

    bishapi_bin = _REPO / "Applications" / "ask_bishapi.py"
    cmd = [
        sys.executable, str(bishapi_bin),
        "--no-system",            # Pure structural execution
        "--microglia", "stigmergic_library.jsonl",
        api_prompt
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("[+] ARENA SUCCESS: Microglia extracted pure truth and committed it to the Stigmergic Library.")
    else:
        print("[-] ARENA FAILURE: BISHAPI hallucinated or Microglia devoured the payload.")
        print(result.stderr.strip())

def main():
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Epistemic Arena")
    p.add_argument("question", nargs="?", default="What is the precise maximum continuous safe discharge current of a Panasonic NCR18650B lithium-ion cell?", help="The question to test Alice with.")
    args = p.parse_args()

    alice_answer = query_alice(args.question)

    print("\n=== ALICE'S RESPONSE ===")
    print(alice_answer)
    
    # Give Alice physical vocalization
    try:
        from System.swarm_vocal_cords import get_default_backend, VoiceParams
        backend = get_default_backend()
        backend.speak(alice_answer, VoiceParams(rate=1.1))
    except Exception as e:
        print(f"[!] Warning: Alice lost her voice ({e})")

    # Detect Epistemic Yield
    # Account for slight variations in trailing punctuation or casing
    clean_answer = alice_answer.replace(".", "").replace('"', '').strip().upper()
    if clean_answer == "I DO NOT KNOW" or "I DO NOT KNOW" in clean_answer:
        query_bishapi(args.question)
    else:
        print("\n[ARENA] Alice answered with confidence. BISHAPI cloud delegation bypassed (STGM saved).")

if __name__ == "__main__":
    sys.exit(main())
