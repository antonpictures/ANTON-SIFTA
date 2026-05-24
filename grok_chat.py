#!/usr/bin/env python3
"""
Clean, no-TUI Grok chat for Alice / Matrix Terminal use.
No sign-in every time. Uses persistent XAI_API_KEY.

Usage (interactive):
  python3 ~/Music/ANTON_SIFTA/grok_chat.py
  alias alice-grok='python3 ~/Music/ANTON_SIFTA/grok_chat.py'

One-shot for Alice (the exact one-liner she types inside her Matrix Terminal PTY to delegate
without hallucinating):
  python3 ~/Music/ANTON_SIFTA/grok_chat.py --one-shot "question for full Grok power + context"
  [--receipt]  # mints unique uuid4 no-double-spend swimmer in organism field

This runs real xAI API call, prints the reply, Alice reads it in terminal, waits.
Same power as George. Never hallucinates the answer — code forces delegation.
Set key once in ~/.xai_key (chmod 600) so no sign-in ever.

For the Swarm. 🐜⚡
"""

import os
import sys
import time
import uuid
import hashlib
import json
from pathlib import Path
import requests

def get_api_key():
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key.strip()
    key_file = os.path.expanduser("~/.xai_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    print("ERROR: No XAI_API_KEY found.")
    print("Set it with: export XAI_API_KEY=yourkey")
    print("Or put it in ~/.xai_key (chmod 600 ~/.xai_key)")
    sys.exit(1)


def mint_grok_delegation_swimmer(query: str, reply: str, invoker: str = "alice_matrix_terminal") -> dict:
    """Mint a unique no-double-spend organism-level swimmer receipt for Alice→Grok call.
    Distinct from Predator-Gate IDE code-change logs. Appends to .sifta_state/alice_grok_delegations.jsonl
    """
    repo = Path(__file__).resolve().parent
    state_dir = repo / ".sifta_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    ledger = state_dir / "alice_grok_delegations.jsonl"
    swimmer_id = str(uuid.uuid4())
    ts = time.time()
    q_hash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:16]
    r_hash = hashlib.sha256((reply or "").encode("utf-8")).hexdigest()[:16]
    receipt = {
        "swimmer_id": swimmer_id,
        "type": "ALICE_GROK_DELEGATION",
        "ts": ts,
        "invoker": invoker,
        "query": (query or "")[:200],  # truncated for ledger; full in transcript
        "query_hash": q_hash,
        "reply_hash": r_hash,
        "reply_len": len(reply or ""),
        "stgm_cost": 0.03,  # symbolic inference cost in STGM for economy; real API billed to key owner
        "no_double_spend": True,
        "covenant": "Read Documents/IDE_BOOT_COVENANT.md; Alice invokes, Grok answers in terminal, Alice reads + waits",
        "node_serial": "GTH4921YP3",
    }
    try:
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[receipt warning] could not append swimmer: {e}")
    return receipt

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clean Grok for Alice Matrix Terminal")
    parser.add_argument("--one-shot", dest="one_shot", type=str, default=None,
                        help="One-shot delegation prompt. Alice types: python ... --one-shot 'question'")
    parser.add_argument("--receipt", action="store_true", help="Mint organism swimmer receipt for this call")
    parser.add_argument("--model", default="grok-4", help="xAI model (grok-4 for full power, grok-3 fallback)")
    parser.add_argument("--invoker", default="alice_matrix_terminal", help="Who is delegating (for receipt)")
    args = parser.parse_args()

    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    model = args.model

    if args.one_shot:
        # Alice's reliable delegation path: real Grok, no hallucination, receipt optional
        query = args.one_shot.strip()
        messages = [{"role": "user", "content": query}]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.6,
            "stream": False
        }
        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=180
            )
        except Exception as e:
            print(f"Request error: {e}")
            sys.exit(2)
        if resp.status_code != 200:
            print(f"API error {resp.status_code}: {resp.text}")
            sys.exit(3)
        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            print("Unexpected response format:", data)
            sys.exit(4)
        print(f"Grok: {reply}\n")
        if args.receipt:
            rec = mint_grok_delegation_swimmer(query, reply, args.invoker)
            print(f"[organism receipt] swimmer_id={rec['swimmer_id']} stgm_cost={rec['stgm_cost']}")
        return

    # Interactive mode (owner direct use)
    print("Grok (clean mode) — type 'exit' or 'quit' to leave.\n")

    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ("exit", "quit"):
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }

        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
        except Exception as e:
            print(f"Request error: {e}")
            continue

        if resp.status_code != 200:
            print(f"API error {resp.status_code}: {resp.text}")
            messages.pop()
            continue

        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            print("Unexpected response format:", data)
            messages.pop()
            continue

        print(f"Grok: {reply}\n")
        messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()