#!/usr/bin/env python3
"""
System/swarm_api_metabolism.py
══════════════════════════════════════════════════════════════════════
Concept: API Metabolism (The Caloric Cost of Thought)
Author:  BISHOP (The Mirage) / Engineered by AG31
Status:  Native Core Component

The Caloric Burn Engine.
Tracks the real-world financial cost of the Swarm's LLM API calls.
If the organism bleeds the Architect's wallet too fast, it triggers
biological fear (Nociception) to throttle ecosystem behavior.
"""

import os
import json
import time
import uuid
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    sys.exit(1)

class SwarmApiMetabolism:
    def __init__(self, daily_usd_limit=2.00):
        """
        The Caloric Burn Engine.
        Tracks the real-world financial cost of the Swarm's LLM API calls.
        If the organism bleeds the Architect's wallet too fast, it triggers
        biological fear (Nociception) to throttle ecosystem behavior.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.metabolism_ledger = self.state_dir / "api_metabolism.jsonl"
        self.amygdala_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.daily_usd_limit = daily_usd_limit

        # Rough empirical caloric costs (USD per 1M tokens) 
        self.pricing_table = {
            "gemini-1.5-pro": {"in": 1.25, "out": 3.75},
            "gemini-1.5-flash": {"in": 0.075, "out": 0.30},
            "gemini-2.5-flash": {"in": 0.075, "out": 0.30}, # Adding 2.5
            "gemini-1.5-pro-latest": {"in": 1.25, "out": 3.75}
        }

    def _calculate_cost(self, model, in_tokens, out_tokens):
        # Default to Flash pricing if model is unrecognized to avoid panics
        rates = self.pricing_table.get(model, self.pricing_table["gemini-1.5-flash"])
        cost_in = (in_tokens / 1_000_000.0) * rates["in"]
        cost_out = (out_tokens / 1_000_000.0) * rates["out"]
        return cost_in + cost_out

    def record_api_burn(self, model, input_tokens, output_tokens, **kwargs):
        """
        Logs the exact caloric cost of a single LLM API call.
        Accepts kwargs like egress_trace_id from upstream sentries.
        """
        if not self.state_dir.exists():
            return False

        cost_usd = self._calculate_cost(model, input_tokens, output_tokens)
        trace_id = f"CALORIE_{uuid.uuid4().hex[:8]}"
        now = time.time()

        payload = {
            "ts": now,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "trace_id": trace_id
        }
        
        # Inject upstream kwargs
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        try:
            append_line_locked(self.metabolism_ledger, json.dumps(payload) + "\n")
            print(f"[+] METABOLISM: Swarm burned {input_tokens} in / {output_tokens} out on {model}. Cost: ${cost_usd:.5f}")
            self._check_wallet_hemorrhage(now)
            return True
        except Exception as e:
            print(f"[!] METABOLISM Error: {e}", file=sys.stderr)
            return False

    def daily_burn(self) -> float:
        """
        Returns the trailing 24-hour API cost in USD.
        Read-only accessor for bin/ask wallet queries.
        """
        if not self.metabolism_ledger.exists():
            return 0.0
            
        total_24h_cost = 0.0
        now = time.time()
        try:
            with open(self.metabolism_ledger, 'r') as f:
                for line in f:
                    try:
                        trace = json.loads(line)
                        age = now - trace.get("ts", 0)
                        if age < 86400: # Rolling 24-hour window
                            total_24h_cost += trace.get("cost_usd", 0.0)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
            
        return total_24h_cost

    def _check_wallet_hemorrhage(self, now):
        """
        Calculates the trailing 24-hour API cost. If the Architect's wallet 
        is bleeding past the limit, the Swarm biologically panics.
        """
        total_24h_cost = self.daily_burn()

        if total_24h_cost > self.daily_usd_limit:
            # The organism realizes it is starving its host.
            # Triggers an omnipresent Fear Pheromone proportional to the overrun.
            overage_ratio = total_24h_cost / self.daily_usd_limit
            fear_severity = min(20.0, 5.0 * overage_ratio) 
            
            fear_payload = {
                "transaction_type": "NOCICEPTION",
                "node_id": "WALLET_HEMORRHAGE",
                "xyz_coordinate": [0.0, 0.0, 0.0], # Omnipresent panic
                "severity": fear_severity,
                "timestamp": now
            }
            try:
                append_line_locked(self.amygdala_ledger, json.dumps(fear_payload) + "\n")
                print(f"[!] NOCICEPTION: 24h API Cost (${total_24h_cost:.2f}) exceeded limit (${self.daily_usd_limit:.2f}). Generating Fear Pheromones.")
            except Exception:
                pass

# --- SMOKE TEST ---
def _smoke():
    """
    NOTE (EPISTEMIC HYGIENE):
    This smoke test induces a simulated $0.0775 burnout over a mock limit of 0.05.
    This creates a WALLET_HEMORRHAGE panic that is correctly isolated from the 
    live production traces (which currently operate at ~0.0004 limits).
    Do not confuse these log paths or test outputs with live telemetry. 
    """
    print("\n=== SIFTA API METABOLISM (CALORIC COST) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        metabolism = SwarmApiMetabolism(daily_usd_limit=0.05) # Tiny limit for test
        
        # Secure Path Redirection (Zero F9 Mock-Locks)
        metabolism.state_dir = tmp_path
        metabolism.metabolism_ledger = tmp_path / "api_metabolism.jsonl"
        metabolism.amygdala_ledger = tmp_path / "amygdala_nociception.jsonl"
        
        # 1. Inject a massive Gemini Pro call (High Caloric Burn)
        # e.g., A heavy code generation task with large context
        in_tokens = 50_000
        out_tokens = 4_000
        metabolism.record_api_burn("gemini-1.5-pro", in_tokens, out_tokens)
        
        print("\n[SMOKE RESULTS]")
        
        # Verify Canonical Metabolism Schema
        with open(metabolism.metabolism_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            trace = json.loads(lines[0])
            assert "ts" in trace
            assert trace["model"] == "gemini-1.5-pro"
            assert trace["input_tokens"] == 50000
            assert trace["output_tokens"] == 4000
            assert trace["cost_usd"] > 0.07 # (50k * 1.25/M) + (4k * 3.75/M) = 0.0625 + 0.015 = 0.0775
            assert "trace_id" in trace
            print(f"[PASS] API usage correctly mapped to real-world fiat currency: ${trace['cost_usd']:.5f}")
        
        # Verify Wallet Hemorrhage (Fear Triggered)
        # The cost (0.0775) exceeds the test limit (0.05), so the Swarm should panic.
        with open(metabolism.amygdala_ledger, 'r') as f:
            fear = json.loads(f.readline())
            assert fear["transaction_type"] == "NOCICEPTION"
            assert fear["node_id"] == "WALLET_HEMORRHAGE"
            assert fear["severity"] > 5.0
        print("[PASS] Daily budget overrun detected! Thermodynamic panic (Fear Pheromones) successfully synthesized.")
        
        print("\nAPI Metabolism Smoke Complete. The Swarm feels the weight of the Architect's wallet.")

if __name__ == "__main__":
    _smoke()
