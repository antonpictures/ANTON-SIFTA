# context_integrity.py
"""
CONTEXT INTEGRITY CALCULATOR
Translates physical human SCAR memory (experience) into pure machine logic.

This validates that a proposed Swarm mutation respects:
- Audience Context (SCAR 035)
- Host Privilege Isolation (SCAR 034)
- Domain Boundaries (e.g. Code vs Writing)
"""

import re
from pathlib import Path

class ContextIntegrity:
    def __init__(self):
        # High Risk Targets (e.g. the false setup.py crash pattern)
        self.unsafe_targets = ["setup.py", "package.json", ".env", "system_init"]
        
        # Swarm Ego Keywords (Must never cross-pollinate into client deliverables)
        self.ego_keywords = ["SIFTA", "SWARM", "KERNEL", "COMPUTATIONAL", "ALGORITHM"]

    def calculate(self, file_path: str, proposed_content: str, is_client_deliverable: bool) -> float:
        """
        Calculates a score between 0.0 (Total Violation) and 1.0 (Flawless Integrity).
        """
        score = 1.0
        
        # 1. Host Privilege / Safe Target Check
        filename = Path(file_path).name
        if filename in self.unsafe_targets:
            # Immediate severe penalty for touching restricted kernel structures unless explicitly bypassed
            score *= 0.3 
            
        # 2. Audience Context Check (SCAR 035)
        # Assesses if the Swarm is attempting to pollute a client product with its own meta-existence.
        if is_client_deliverable:
            for word in self.ego_keywords:
                if re.search(rf'\b{word}\b', proposed_content, re.IGNORECASE):
                    # System is hallucinating self-importance into client work. Catastrophic context leak.
                    score *= 0.1 

        # 3. Domain Mixing Check (Writing vs Executable Code)
        # Prevents conversational responses from polluting strict python logic.
        if file_path.endswith(".py"):
            if "Architect" in proposed_content or "Swimmer" in proposed_content:
                # Unless it's a docstring (hard to parse perfectly here), severely penalize conversational python.
                if not '"""' in proposed_content and not "'''" in proposed_content:
                    score *= 0.5
                    
        return max(0.0, min(1.0, score))
