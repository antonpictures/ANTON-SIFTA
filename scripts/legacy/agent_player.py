#!/usr/bin/env python3
import sys
import time
import subprocess
import json
import urllib.request
import argparse
from pathlib import Path
import os

def call_llm(grid_text, model, provider_url="http://localhost:11434"):
    """
    Calls the LLM with the current grid frame and asks for a single move.
    """
    prompt = f"""You are an autonomous AI playing a grid exploration survival game.
You must navigate the fog-of-war to reach the goal.

LEGEND:
P = You (Player)
G = Goal
X = Trap (Avoid!)
. = Visited safe tile
# = Unexplored fog-of-war

CONTROLS:
w = up
s = down
a = left
d = right

CURRENT GAME STATE:
{grid_text}

Calculate the best route to G, avoiding X. If G is not visible, explore # systematically.
Respond with EXACTLY ONE LETTER (w, a, s, or d). No markdown, no explanation, no punctuation.
"""
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1} # low temp for reliable structured output
    }
    req = urllib.request.Request(
        f"{provider_url}/api/generate",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "w").strip().lower()
    except Exception as e:
        print(f"\n[LLM ERROR] {e}")
        return "w" # Fallback move just to keep loop alive

def main():
    parser = argparse.ArgumentParser(description="Autonomous LLM Game Player")
    parser.add_argument("--agent", default="ANTIALICE", help="Agent ID")
    parser.add_argument("--model", default="sifta-gemma4-alice:latest", help="Ollama model to use")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama API base URL")
    args = parser.parse_args()

    print(f"\n=============================================================")
    print(f" [O_O] SIFTA AUTONOMOUS PLAYER INITIALIZED")
    print(f" Agent: {args.agent}")
    print(f" Model: {args.model}")
    print(f"=============================================================\n")

    # Start the game subprocess
    # We use pty or just standard subprocess. subprocess with stdin=PIPE, stdout=PIPE
    # Note: python standard input/output buffering might cause an issue, 
    # so we run python with -u to unbuffer stdout.
    game_path = Path(__file__).parent / "test_environment" / "game.py"
    
    proc = subprocess.Popen(
        [sys.executable, "-u", str(game_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1 # line buffered
    )

    buffer = ""
    turns_played = 0

    while True:
        # Read character by character so we don't block waiting for a newline after "> "
        char = proc.stdout.read(1)
        if not char:
            break
        
        buffer += char
        sys.stdout.write(char) # Echo to our own terminal so user can watch
        sys.stdout.flush()

        # Did we hit the prompt?
        if buffer.endswith("> "):
            turns_played += 1
            print(f"\n[AGENT THOUGHT] Turn {turns_played}... Asking {args.model} for a move...")
            
            # Send the buffer to LLM
            chosen_move = call_llm(buffer, args.model, args.base_url)
            
            # Sanitize the output to just the first target character
            move = "w"
            for c in chosen_move:
                if c in "wasd":
                    move = c
                    break
            
            print(f"[{args.agent}] Decided to move: '{move}'")
            time.sleep(1) # Visual delay so user can observe
            
            # Write back to game
            proc.stdin.write(move + "\n")
            proc.stdin.flush()
            
            # Reset buffer for the next frame
            buffer = ""

    proc.wait()
    print(f"\n[SYSTEM] Game process exited with code {proc.returncode}")

    # Dropping a scar: (Optional stigmergy)
    try:
        import pheromone
        scent = "CLEAN" if "You win" in buffer else "BLEEDING"
        # Since we use buffer to detect win/loss at the end, let's hope it's still in the buffer
        # Or you can do simple text matching.
        pheromone.drop_scar(
            Path(__file__).parent / "test_environment",
            {"id": args.agent, "face": "[O_O]", "raw": f"<///[O_O]///::ID[{args.agent}]::>"},
            "PLAY_GAME",
            "Played benchmark game",
            scent,
            f"Agent survived {turns_played} turns. Result: Process exited."
        )
        print(f"[STIGMERGY] Action logged into territory chronicle.")
    except Exception as e:
        print(f"Failed to drop scar: {e}")

if __name__ == "__main__":
    main()
