#!/usr/bin/env python3
"""
ANTON-SIFTA: The Settings Biter
──────────────────────────────────────────────────────────────────────────────
A specialized biological Agent born to attack Configuration Files.

It "bites into" text-based code blocks (YAML, JSON, ENV) and mathematically 
locks the correct state without relying on fragile external parser packages 
like PyYAML. It targets blocks, rips them out, and injects the Swarm truth.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

# THE ABSOLUTE TRUTH: 5 SWARM NODES
SWARM_INGRESS = """ingress:
  - hostname: googlemapscoin.com
    service: http://localhost:3000
  - hostname: www.googlemapscoin.com
    service: http://localhost:3000
  - hostname: stigmergicode.com
    service: http://localhost:3001
  - hostname: www.stigmergicode.com
    service: http://localhost:3001
  - hostname: stigmergicoin.com
    service: http://localhost:3002
  - hostname: www.stigmergicoin.com
    service: http://localhost:3002
  - hostname: georgeanton.com
    service: http://localhost:3003
  - hostname: www.georgeanton.com
    service: http://localhost:3003
  - hostname: imperialdaily.com
    service: http://localhost:3005
  - hostname: www.imperialdaily.com
    service: http://localhost:3005
  - service: http_status:404
"""

def bite_cloudflare_config(file_path_str):
    path = Path(file_path_str).expanduser()
    if not path.exists():
        print(f"  [X] The Settings Biter could not find flesh at {path}")
        sys.exit(1)
        
    print(f"  [>] The Settings Biter is sinking fangs into: {path}")
    raw_text = path.read_text(encoding="utf-8")
    
    # Locate the "ingress:" block and rip everything from it to EOF
    if "ingress:" not in raw_text:
        print("  [DEBUG] No ingress block found. I will spawn a new tail.")
        clean_header = raw_text.strip()
    else:
        # Split on the word ingress:
        clean_header = raw_text.split("ingress:")[0].strip()
        
    # Build the final biological structure: Header + The Swarm Truth
    bitten_text = clean_header + "\n\n" + SWARM_INGRESS
    
    if raw_text.strip() == bitten_text.strip():
        print("  [-] The configuration is already mathematically pure. No bite required.")
        return

    # Commit the bite
    path.write_text(bitten_text + "\n", encoding="utf-8")
    
    print(f"  [+] BITE EXECUTED. {path.name} now maps the 5 Stigmergic Node ports.")
    print(f"  [!] RESTART REQUIRED: Restart your cloudflared tunnel daemon so it digests the change.")

if __name__ == "__main__":
    print(f" {'━'*60}")
    print(f"  ANTON-SIFTA — SETTINGS BITER AGENT")
    print(f" {'━'*60}")
    
    if len(sys.argv) < 3:
        print("Usage: python3 settings_biter.py <file_path> --bite-ports")
        print("Example: python3 settings_biter.py ~/.cloudflared/config.yml --bite-ports")
        sys.exit(1)
        
    target = sys.argv[1]
    cmd = sys.argv[2]
    
    if cmd == "--bite-ports":
        bite_cloudflare_config(target)
    else:
        print(f"  [?] Unknown bite command: {cmd}")
