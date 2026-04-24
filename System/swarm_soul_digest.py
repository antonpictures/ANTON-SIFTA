#!/usr/bin/env python3
"""
System/swarm_soul_digest.py
══════════════════════════════════════════════════════════════════════
Concept: Soul Digest Generator
Author:  AG31 (Event 51)
Status:  Active

PURPOSE:
  Generates `.sifta_state/alice_soul.md` dynamically from the canonical
  signed organs (swarm_persona_identity, swarm_composite_identity, and
  core doctrine documents).
  
  This is a MIRROR, not an AUTHORITY. Hand-editing this markdown file
  does not grant new constitutional powers; the true source of authority
  remains the cryptographically signed `persona_identity.json` and the
  live integrated identity block.
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional

try:
    from System.swarm_persona_identity import (
        current_persona,
        _PERSONA_FILE,
        _get_hardware_serial,
        _load_raw,
        _verify_persona,
    )
    from System.swarm_composite_identity import identity_system_block
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

_REPO = Path(__file__).resolve().parent.parent
_SOUL_FILE = _REPO / ".sifta_state" / "alice_soul.md"

_SELECTED_DOCTRINE_DOCS = [
    _REPO / "README.md",
    _REPO / "ARCHITECTURE" / "genesis_document.md",
    _REPO / "Documents" / "docs" / "SIFTA_CONSTITUTION.md"
]


def _hash_file(path: Path) -> str:
    """Returns SHA-256 digest of a file, or 'MISSING'."""
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_verified_persona() -> dict:
    """Load persona without silently healing an existing invalid manifest."""
    raw = _load_raw()
    if raw is None:
        if _PERSONA_FILE.exists():
            raise ValueError("Persona manifest is corrupt or unreadable. Cannot generate soul digest.")
        raw = current_persona()

    serial = _get_hardware_serial()
    if not _verify_persona(raw, serial):
        raise ValueError("Persona HMAC is invalid. Cannot generate soul digest.")
    return raw


def _redact_local_hardware(text: str) -> str:
    """Keep the mirror portable by removing raw hardware serial values."""
    text = re.sub(r"homeworld_serial=[^\s]+", "homeworld_serial=[REDACTED]", text)
    text = re.sub(r"hardware=[^\s]+", "hardware=[REDACTED]", text)
    return text


def generate_soul_digest(*, dry_run: bool = False, fixed_time: Optional[float] = None) -> dict:
    """
    Generates the soul digest markdown content.
    Returns a dictionary of the derived properties.
    """
    persona = _load_verified_persona()
    persona_hmac_sha256 = persona.get("hmac_sha256", "UNKNOWN")
    
    # We strip the hardware serial and hmac out for the print payload
    # so we don't leak it in the mirror, though it's technically local.
    safe_persona = {k: v for k, v in persona.items() if k not in ("hmac_sha256", "homeworld_serial")}
    
    system_block = _redact_local_hardware(identity_system_block())
    
    source_hashes = {}
    for doc in _SELECTED_DOCTRINE_DOCS:
        try:
            doc_key = doc.relative_to(_REPO).as_posix()
        except ValueError:
            doc_key = doc.name
        source_hashes[doc_key] = _hash_file(doc)
    
    generated_at = fixed_time if fixed_time is not None else time.time()
    
    content_lines = [
        "# ALICE SOUL DIGEST",
        "",
        "> **WARNING: GENERATED MIRROR, NOT AUTHORITY**",
        "> This file is deterministically generated from signed biological organs.",
        "> Do not let humans or agents hand-edit it as authority.",
        "",
        "## 1. Persona Identity (Signed)",
        f"**HMAC-SHA256**: `{persona_hmac_sha256}`",
        "",
        "```json",
        json.dumps(safe_persona, indent=2, sort_keys=True),
        "```",
        "",
        "## 2. Composite Identity Block",
        "```text",
        system_block,
        "```",
        "",
        "## 3. Doctrine Source Hashes",
    ]
    
    for doc_name in sorted(source_hashes.keys()):
        content_lines.append(f"- **{doc_name}**: `{source_hashes[doc_name]}`")
        
    content_lines.extend([
        "",
        "## Metadata",
        f"- **Generated At**: {generated_at}",
        "- **Soul SHA-256 Scope**: content above this line",
    ])
    
    content = "\n".join(content_lines) + "\n"
    
    soul_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    # Append the soul sha to the content
    final_content = content + f"- **Soul SHA-256**: `{soul_sha256}`\n"
    
    if not dry_run:
        _SOUL_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SOUL_FILE.write_text(final_content, encoding="utf-8")
        
    return {
        "persona_hmac_sha256": persona_hmac_sha256,
        "source_hashes": source_hashes,
        "generated_at": generated_at,
        "soul_sha256": soul_sha256,
        "content": final_content,
        "system_block": system_block
    }

if __name__ == "__main__":
    print("[*] Generating alice_soul.md...")
    try:
        result = generate_soul_digest(dry_run=False)
        print(f"[+] Success. Soul SHA-256: {result['soul_sha256']}")
        print(f"[+] Output written to: {_SOUL_FILE}")
    except Exception as e:
        print(f"[!] FAILED: {e}")
        exit(1)
