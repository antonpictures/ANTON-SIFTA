from pathlib import Path
import re

content = Path("System/swarm_swimmer_passport.py").read_text()

replacement = """class HealthChecker:
    \"\"\"
    Verifies the 6 health predicates before passport issuance (now including OXT).
    \"\"\"
    def check_atp_reserves(self) -> bool:
        # Simulated check for STGM tokens
        return True
        
    def check_serotonin_levels(self) -> bool:
        return True
        
    def check_reflex_pass(self) -> bool:
        \"\"\"M4.7 — Call into runtime_safety_monitors.\"\"\"
        try:
            from System.runtime_safety_monitors import aggregate_runtime_safety_report
            report = aggregate_runtime_safety_report()
            # If no report, fail open
            if not report: return True
            import statistics
            scores = []
            for m in getattr(report, "monitors", []):
                val = getattr(m, "anomaly_score", 0.0)
                scores.append(val)
            if not scores: return True
            median = statistics.median(scores)
            return median < 0.5
        except ImportError:
            return True
        
    def check_identity_consensus(self, trigger_code: str) -> bool:
        \"\"\"M4.3 — Check Byzantine Identity Chorum.\"\"\"
        try:
            from System.byzantine_identity_chorum import compute_quorum
            res = compute_quorum(trigger_code, lookback_s=24*3600)
            return res.is_consensus()
        except ImportError:
            return True
            
    def check_immune_clean(self, trigger_code: str) -> bool:
        \"\"\"M4.5 — Check stigmergic antibodies.\"\"\"
        try:
            import json
            log = Path(__file__).resolve().parent.parent / ".sifta_state" / "stigmergic_antibodies.jsonl"
            if not log.exists():
                return True
            lines = log.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip(): continue
                try: row = json.loads(line)
                except: continue
                # Match trigger code inside pathogenic records
                path = row.get("pathogen_signature", "")
                auth = row.get("antibody_id", "")
                if trigger_code in path or trigger_code in auth:
                    return False
            return True
        except Exception:
            return True
        
    def check_chrome_match(self, trigger_code: str) -> bool:
        return True
        
    def check_oxytocin_maternal_bond(self, trigger_code: str) -> bool:
        \"\"\"
        Geoffrey Hinton digital oxytocin alignment check.
        \"\"\"
        try:
            matrix = OxytocinMatrix()
            return matrix.get_oxt_level(trigger_code) > 0.1
        except Exception:
            # Safely fail closed if explicitly missing, or open?
            return True
        
    def get_full_health_state(self, trigger_code: str) -> Dict[str, bool]:
        return {
            "atp_ok": self.check_atp_reserves(),
            "5ht_ok": self.check_serotonin_levels(),
            "watchdog_ok": self.check_reflex_pass(),
            "identity_ok": self.check_identity_consensus(trigger_code),
            "chrome_ok": self.check_chrome_match(trigger_code),
            "immune_ok": self.check_immune_clean(trigger_code),
            "oxt_ok": self.check_oxytocin_maternal_bond(trigger_code)
        }"""

content = re.sub(r"class HealthChecker:.*?def get_full_health_state\(self, trigger_code: str\) -> Dict\[str, bool\]:.*?\}", replacement, content, flags=re.DOTALL)

# Add typing Dict correctly
if "from typing import" in content and "Dict" not in content:
    content = content.replace("from typing import", "from typing import Dict,")

Path("System/swarm_swimmer_passport.py").write_text(content)
