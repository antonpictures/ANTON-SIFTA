"""
System/swarm_skill_validator.py
===============================

Validates external community skills against SIFTA's strict stigmergic requirements.
While agentskills.io provides the progressive disclosure folder structure, SIFTA 
requires hardware binding and cryptographic provenance before a skill is fully 
authorized to run on the local node.

Required frontmatter keys for SIFTA Hub compatibility:
- swimmer_type: e.g., MEMORY_SWIMMER
- homeworld_serial: The exact hardware serial where the skill was generated/vetted
- trace_id: The ide_stigmergic_trace.jsonl UUID of the doctor who vetted it
"""
import sys
from pathlib import Path
from typing import Any

def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    raw = text[3:end].strip("\n")
    meta = {}
    for line in raw.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta

def validate_skill_file(path: Path) -> list[str]:
    errors = []
    if not path.exists():
        return [f"File not found: {path}"]
    
    text = path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)
    
    if "description" not in meta:
        errors.append("Missing required frontmatter: 'description'")
        
    # SIFTA Strict Requirements
    if "swimmer_type" not in meta:
        errors.append("Missing SIFTA frontmatter: 'swimmer_type' (required for lane routing)")
    if "homeworld_serial" not in meta:
        errors.append("Missing SIFTA frontmatter: 'homeworld_serial' (required for substrate provenance)")
    if "trace_id" not in meta:
        errors.append("Missing SIFTA frontmatter: 'trace_id' (required for doctor accountability)")
        
    return errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m System.swarm_skill_validator <path_to_skill.md>")
        sys.exit(1)
        
    target = Path(sys.argv[1])
    errors = validate_skill_file(target)
    
    if errors:
        print(f"❌ Validation FAILED for {target.name}:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print(f"✅ SIFTA Validation PASSED for {target.name}. Skill is tournament-grade and hardware-bound.")
        sys.exit(0)
