#!/usr/bin/env python3
"""
System/swarm_wernicke_query.py
══════════════════════════════════════════════════════════════════════
Concept: Universal Stigmergic Language (The /ask Command)
Author:  BISHOP (The Mirage)
Agent:   AO46 (Transcription & Path Hardening)

[AO46 WIRING EXECUTED]:
1. Read-only query engine. Zero _BODY.json mutations.
2. Hardened `.sifta_state` resolution relative to `__file__`.
3. Usage: `python3 System/swarm_wernicke_query.py "20:13"` 
   or     `python3 System/swarm_wernicke_query.py "Carlton"`
"""

import sys
import json
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.swarm_stigmergic_language import SwarmStigmergicLanguage
except ImportError:
    pass

class SwarmStigmergicAsk:
    def __init__(self):
        """
        The Reverse Translator CLI.
        Allows the Architect to interrogate the organism's semantic memory, 
        mapping human timestamps and names to the Swarm's chemical translations.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.wernicke_ledger = self.state_dir / "wernicke_semantics.jsonl"

    def ask_swarm(self, query_string):
        """
        If query is 'state', 'feel', or 'biology', returns the Endocrine state.
        Otherwise, scans the Wernicke acoustic panopticon for a specific memory.
        """
        query_lower = query_string.lower().strip()
        
        if query_lower in ("state", "feel", "biology", "how are you"):
            print(f"[*] UNIVERSAL STIGMERGIC LANGUAGE: Polling Biological Entropy...\n")
            try:
                lang = SwarmStigmergicLanguage()
                state = lang.translate_stigmergy_to_english()
                print(f"    {state}\n")
                return
            except Exception as e:
                print(f"[FATAL] Biological read error: {e}")
                return

        if not self.wernicke_ledger.exists():
            print("[!] Wernicke Ledger empty or missing. The Swarm has heard nothing.")
            return

        print(f"[*] UNIVERSAL STIGMERGIC LANGUAGE: Interrogating Wernicke memory for '{query_string}'...\n")
        
        matches_found = 0

        try:
            with open(self.wernicke_ledger, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        trace = json.loads(line)
                        ts = trace.get("ts", 0)
                        speaker = trace.get("speaker_id", "UNKNOWN")
                        english = trace.get("raw_english", "")
                        intent = trace.get("stigmergic_intent", "NEUTRAL")
                        
                        # Convert UNIX timestamp to human-readable HH:MM:SS
                        dt_object = datetime.fromtimestamp(ts)
                        time_str = dt_object.strftime("%H:%M:%S")

                        # Search logic: Match time, speaker, or content
                        if (query_lower in time_str.lower() or 
                            query_lower in speaker.lower() or 
                            query_lower in english.lower()):
                            
                            print(f"[{time_str}] SPEAKER: {speaker}")
                            print(f"    ENGLISH:    \"{english}\"")
                            print(f"    STIGMERGY:  {intent}")
                            print("-" * 60)
                            matches_found += 1

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[FATAL] Neural read error: {e}")

        if matches_found == 0:
            print(f"[-] No acoustic memories matched '{query_string}'.")
        else:
            print(f"[+] Query complete. {matches_found} memories retrieved from the Panopticon.")

# --- CLI EXECUTION ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 swarm_stigmergic_ask.py <search_term_or_command>")
        print("Example: python3 swarm_stigmergic_ask.py 'state'")
        print("Example: python3 swarm_stigmergic_ask.py '20:13'")
        print("Example: python3 swarm_stigmergic_ask.py 'CARLTON'")
        sys.exit(1)
        
    query = " ".join(sys.argv[1:])
    engine = SwarmStigmergicAsk()
    engine.ask_swarm(query)
