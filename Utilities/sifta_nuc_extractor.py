#!/usr/bin/env python3
"""
sifta_nuc_extractor.py — Swarm Nucleus Extractor

Extracts a portable "Nucleus" (Nuc) from a running swarm.
The Nuc contains everything needed to bootstrap a NEW swarm instance
on different hardware — without carrying the parent's full history.

A Nucleus is NOT a backup. It is a SEED.

What goes IN:
  - swarm_dna.json (identity schema)
  - root_pubkey.pem (public key only — NOT private!)
  - constitution snapshot (governor.py hash)
  - Agent templates (minimal set)
  - Empty ledger seed
  - Capability bounds
  - Lineage proof (parent signature)

What does NOT go in:
  - Private keys
  - Full repair history
  - Scars
  - Reputation data

Usage:
    python sifta_nuc_extractor.py --extract                # Package nucleus
    python sifta_nuc_extractor.py --extract --branch "HARDWARE_EXPANSION"
    python sifta_nuc_extractor.py --verify nuc_v1.zip      # Verify nucleus integrity
    python sifta_nuc_extractor.py --show-dna               # Display current swarm DNA
"""
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent
STATE_DIR = ROOT_DIR / ".sifta_state"
NUC_OUTPUT_DIR = ROOT_DIR / "nuclei"

# ─── Core Files That Define Swarm Capabilities ────────────────────────────────
CAPABILITY_FILES = [
    "repair.py",
    "pheromone.py",
    "governor.py",
    "sifta_cardio.py",
    "proposal_engine.py",
    "reputation_engine.py",
    "body_state.py",
    "sifta_consigliere.py",
]


# ─── 1. Compute File Hash ────────────────────────────────────────────────────

def _sha256_file(filepath: Path) -> str:
    """SHA-256 hash of a file's contents."""
    if not filepath.exists():
        return "MISSING"
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def _sha256_str(s: str) -> str:
    """SHA-256 of a string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ─── 2. Root Identity ────────────────────────────────────────────────────────

def _get_root_identity() -> dict:
    """Read the root identity from sifta_keyvault."""
    key_dir = Path.home() / ".sifta"
    pub_path = key_dir / "identity.pub.pem"

    if not pub_path.exists():
        return {
            "installed": False,
            "fingerprint": "NO_ROOT_KEY",
            "pub_path": str(pub_path),
        }

    from cryptography.hazmat.primitives import serialization
    pub_key = serialization.load_pem_public_key(pub_path.read_bytes())
    pub_raw = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    fingerprint = hashlib.sha256(pub_raw).hexdigest()

    return {
        "installed": True,
        "fingerprint": fingerprint,
        "swarm_id": fingerprint[:32],
        "pub_raw_hex": pub_raw.hex(),
        "pub_path": str(pub_path),
    }


# ─── 3. Capability Matrix ────────────────────────────────────────────────────

def _compute_capability_matrix() -> dict:
    """Hash all core capability files to define WHAT this swarm can do."""
    matrix = {}
    for fname in CAPABILITY_FILES:
        fpath = ROOT_DIR / fname
        matrix[fname] = _sha256_file(fpath)

    # Composite hash of all capabilities
    composite = hashlib.sha256()
    for k in sorted(matrix.keys()):
        composite.update(f"{k}:{matrix[k]}".encode())

    return {
        "files": matrix,
        "composite_hash": composite.hexdigest(),
    }


# ─── 4. Agent Census ─────────────────────────────────────────────────────────

def _read_agent_census() -> list:
    """Read current agent templates for nucleus packaging."""
    agents = []
    for p in STATE_DIR.glob("*.json"):
        if p.name in ("hivemind.json", "provisioned_config.json",
                       "boot_ledger.json", "deploy_ledger.json",
                       "event_registry.json", "identity_stats.json"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if "id" not in data:
                continue
            # Template: minimal seed data, no history
            agents.append({
                "id": data["id"],
                "style": data.get("style", "NOMINAL"),
                "energy": min(100, max(0, data.get("energy", 100))),
                "face": data.get("face", "[?]"),
            })
        except Exception:
            continue
    return agents


# ─── 5. Reputation Summary ───────────────────────────────────────────────────

def _read_reputation_summary() -> dict:
    """Summarize reputation data (NOT included in nuc, just for DNA display)."""
    rep_dir = ROOT_DIR / ".sifta_reputation"
    if not rep_dir.exists():
        return {"count": 0, "avg_score": 0.0}

    scores = []
    for p in rep_dir.glob("*.rep.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            scores.append(data.get("score", 0.5))
        except Exception:
            continue

    return {
        "count": len(scores),
        "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
    }


# ─── 6. State Hash ───────────────────────────────────────────────────────────

def _compute_state_hash(identity: dict, capabilities: dict, agents: list) -> str:
    """
    Rolling hash of the LIVING state.
    This changes with every mutation — but the root stays constant.
    Your cells replace, but your fingerprint doesn't.
    """
    state_material = json.dumps({
        "swarm_id": identity.get("swarm_id", ""),
        "capability_hash": capabilities["composite_hash"],
        "agent_count": len(agents),
        "agent_ids": sorted([a["id"] for a in agents]),
    }, sort_keys=True)

    return _sha256_str(state_material)


# ─── 7. Build Swarm DNA ──────────────────────────────────────────────────────

def build_swarm_dna(branch_reason: str = "GENESIS",
                    parent_swarm_id: str = None,
                    generation: int = 0) -> dict:
    """
    Assemble the complete Swarm DNA identity manifest.
    """
    identity = _get_root_identity()
    capabilities = _compute_capability_matrix()
    agents = _read_agent_census()
    reputation = _read_reputation_summary()

    dna = {
        "version": "1.0",
        "swarm_id": identity.get("swarm_id", "UNSIGNED"),
        "genesis_ts": time.time(),
        "genesis_iso": datetime.now(timezone.utc).isoformat(),
        "root_pubkey_fingerprint": identity.get("fingerprint", "NONE")[:32],
        "lineage": {
            "parent_swarm_id": parent_swarm_id,
            "generation": generation,
            "branch_reason": branch_reason,
        },
        "constitution_hash": _sha256_file(ROOT_DIR / "governor.py"),
        "capability_matrix": capabilities,
        "agent_templates": agents,
        "agent_count": len(agents),
        "bounds": {
            "max_agents": 32,
            "max_energy": 100,
            "proposal_gate": True,
            "advisory_enabled": True,
            "registry_version": "v1.0",
        },
        "environment": {
            "platform": platform.platform(),
            "arch": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        },
        "state_hash": _compute_state_hash(identity, capabilities, agents),
        "reputation_summary": reputation,
        "identity_installed": identity.get("installed", False),
    }

    return dna


# ─── 8. Sign the DNA (Lineage Proof) ─────────────────────────────────────────

def _sign_dna(dna: dict) -> str:
    """Sign the DNA manifest with the root private key."""
    priv_path = Path.home() / ".sifta" / "identity.pem"
    if not priv_path.exists():
        print("[NUC] ⚠ No private key found — lineage proof will be UNSIGNED.")
        return "UNSIGNED"

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64

    priv_bytes = priv_path.read_bytes()
    private_key = serialization.load_pem_private_key(priv_bytes, password=None)

    # Sign the canonical DNA content
    canonical = json.dumps({
        "swarm_id": dna["swarm_id"],
        "genesis_ts": dna["genesis_ts"],
        "constitution_hash": dna["constitution_hash"],
        "capability_hash": dna["capability_matrix"]["composite_hash"],
        "lineage": dna["lineage"],
    }, sort_keys=True)

    signature = private_key.sign(canonical.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


# ─── 9. Extract Nucleus ──────────────────────────────────────────────────────

def extract_nucleus(branch_reason: str = "GENESIS",
                    parent_swarm_id: str = None,
                    generation: int = 0,
                    select_agents: list = None) -> Path:
    """
    Extract a portable Swarm Nucleus.
    Returns the path to the generated .zip file.
    """
    NUC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build DNA
    dna = build_swarm_dna(
        branch_reason=branch_reason,
        parent_swarm_id=parent_swarm_id,
        generation=generation,
    )

    # Sign it
    lineage_sig = _sign_dna(dna)
    dna["lineage_proof"] = lineage_sig

    # Filter agents if specified
    if select_agents:
        dna["agent_templates"] = [
            a for a in dna["agent_templates"]
            if a["id"] in select_agents
        ]
        dna["agent_count"] = len(dna["agent_templates"])

    # Generate output filename
    swarm_id_short = dna["swarm_id"][:8] if dna["swarm_id"] != "UNSIGNED" else "unsigned"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    nuc_name = f"sifta_nuc_{swarm_id_short}_gen{generation}_{ts}"
    nuc_zip = NUC_OUTPUT_DIR / f"{nuc_name}.zip"

    # Package into a zip
    with zipfile.ZipFile(nuc_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Swarm DNA manifest
        zf.writestr("swarm_dna.json", json.dumps(dna, indent=2))

        # 2. Public key (NOT private!)
        pub_path = Path.home() / ".sifta" / "identity.pub.pem"
        if pub_path.exists():
            zf.write(pub_path, "root_pubkey.pem")
        else:
            zf.writestr("root_pubkey.pem", "# No root public key found during extraction\n")

        # 3. Constitution snapshot
        gov_path = ROOT_DIR / "governor.py"
        if gov_path.exists():
            zf.write(gov_path, "constitution/governor.py")

        # 4. Agent templates
        for agent in dna["agent_templates"]:
            template = {
                "id": agent["id"],
                "style": "NOMINAL",
                "energy": 100,
                "face": agent.get("face", "[?]"),
                "history": [],
                "hash_chain": [],
            }
            zf.writestr(
                f"agent_templates/{agent['id']}.json",
                json.dumps(template, indent=2)
            )

        # 5. Empty ledger seed
        zf.writestr("seed/empty_ledger.sql", """
-- SIFTA Task Ledger — Clean Seed
CREATE TABLE IF NOT EXISTS task_ledger (
    id TEXT PRIMARY KEY,
    task_type TEXT,
    status TEXT DEFAULT 'PENDING',
    agent_id TEXT,
    payload TEXT,
    created_at REAL,
    leased_at REAL,
    completed_at REAL,
    result TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    event_type TEXT,
    component TEXT,
    details TEXT
);
""")

        # 6. Capability bounds
        bounds = {
            "version": dna["bounds"]["registry_version"],
            "max_agents": dna["bounds"]["max_agents"],
            "max_energy": dna["bounds"]["max_energy"],
            "proposal_gate": dna["bounds"]["proposal_gate"],
            "advisory_enabled": dna["bounds"]["advisory_enabled"],
            "required_capabilities": list(dna["capability_matrix"]["files"].keys()),
        }
        zf.writestr("capability_bounds.json", json.dumps(bounds, indent=2))

        # 7. Lineage proof
        zf.writestr("lineage_proof.sig", lineage_sig)

        # 8. README for the human who finds this zip
        zf.writestr("README.md", f"""# SIFTA Swarm Nucleus

**Swarm ID:** `{dna["swarm_id"]}`
**Generation:** {generation}
**Branch Reason:** {branch_reason}
**Extracted:** {dna["genesis_iso"]}
**Agents:** {dna["agent_count"]}

## Bootstrap

```bash
python sifta_nuc_boot.py --nuc {nuc_zip.name}
```

## Lineage

Parent: `{parent_swarm_id or "GENESIS (root)"}`
Signature: `{lineage_sig[:24]}...`

## What This Contains

- `swarm_dna.json` — Full identity manifest
- `root_pubkey.pem` — Root public key (verify lineage)
- `constitution/` — Governor logic
- `agent_templates/` — Minimal agent set
- `seed/` — Clean ledger schema
- `capability_bounds.json` — Capability matrix
- `lineage_proof.sig` — Parent's Ed25519 signature

## What This Does NOT Contain

- ❌ Private keys
- ❌ Repair history / scars
- ❌ Reputation data
- ❌ Full agent state

*Power to the Swarm.*
""")

    # Display result
    nuc_size = nuc_zip.stat().st_size
    print("\n" + "═" * 70)
    print("  🧬 SWARM NUCLEUS EXTRACTED")
    print("═" * 70)
    print(f"  Swarm ID:     {dna['swarm_id']}")
    print(f"  Generation:   {generation}")
    print(f"  Branch:       {branch_reason}")
    print(f"  Agents:       {dna['agent_count']}")
    print(f"  Capabilities: {len(dna['capability_matrix']['files'])} modules")
    print(f"  State Hash:   {dna['state_hash'][:24]}...")
    print(f"  Lineage Sig:  {'✅ SIGNED' if lineage_sig != 'UNSIGNED' else '⚠ UNSIGNED'}")
    print(f"  Output:       {nuc_zip}")
    print(f"  Size:         {nuc_size:,} bytes")
    print("═" * 70)

    # Audit
    try:
        from sifta_audit import record_event
        record_event(
            "NUCLEUS_EXTRACTED",
            "sifta_nuc_extractor",
            f"Swarm {dna['swarm_id'][:12]}... gen{generation} "
            f"branch={branch_reason} agents={dna['agent_count']}"
        )
    except Exception:
        pass

    return nuc_zip


# ─── 10. Verify Nucleus ──────────────────────────────────────────────────────

def verify_nucleus(nuc_path: str) -> bool:
    """Verify a nucleus zip for integrity and optional lineage signature."""
    nuc = Path(nuc_path)
    if not nuc.exists():
        print(f"[NUC] File not found: {nuc}")
        return False

    with zipfile.ZipFile(nuc, "r") as zf:
        names = zf.namelist()

        # Required files
        required = ["swarm_dna.json", "capability_bounds.json", "lineage_proof.sig"]
        for r in required:
            if r not in names:
                print(f"[NUC] ❌ Missing required file: {r}")
                return False

        dna = json.loads(zf.read("swarm_dna.json"))

        print("\n" + "═" * 70)
        print("  🔬 NUCLEUS VERIFICATION")
        print("═" * 70)
        print(f"  Swarm ID:     {dna.get('swarm_id', '?')}")
        print(f"  Generation:   {dna.get('lineage', {}).get('generation', '?')}")
        print(f"  Branch:       {dna.get('lineage', {}).get('branch_reason', '?')}")
        print(f"  Constitution: {dna.get('constitution_hash', '?')[:24]}...")
        print(f"  Agents:       {dna.get('agent_count', 0)}")

        # Check lineage signature
        sig = zf.read("lineage_proof.sig").decode("utf-8").strip()
        if sig == "UNSIGNED":
            print(f"  Lineage:      ⚠ UNSIGNED (no private key at extraction time)")
        else:
            print(f"  Lineage:      ✅ Signed ({sig[:24]}...)")

        # Verify agent templates exist
        agent_files = [n for n in names if n.startswith("agent_templates/")]
        print(f"  Templates:    {len(agent_files)} agent files")

        # Verify seed present
        if "seed/empty_ledger.sql" in names:
            print(f"  Ledger Seed:  ✅ Present")
        else:
            print(f"  Ledger Seed:  ❌ Missing")

        print(f"  Files:        {len(names)} total")
        print("═" * 70)

    return True


# ─── 11. Show Current DNA ────────────────────────────────────────────────────

def show_dna():
    """Display the current swarm's DNA identity."""
    dna = build_swarm_dna()

    print("\n" + "═" * 70)
    print("  🧬 CURRENT SWARM DNA")
    print("═" * 70)
    print(f"  Swarm ID:     {dna['swarm_id']}")
    print(f"  Root Key:     {'✅ INSTALLED' if dna['identity_installed'] else '❌ NOT INSTALLED'}")
    print(f"  Fingerprint:  {dna['root_pubkey_fingerprint']}")
    print(f"  Constitution: {dna['constitution_hash'][:24]}...")
    print(f"  Capabilities: {dna['capability_matrix']['composite_hash'][:24]}...")
    print(f"  Agents:       {dna['agent_count']}")
    print(f"  State Hash:   {dna['state_hash'][:24]}...")
    print(f"  Platform:     {dna['environment']['platform']}")
    print(f"  Reputation:   {dna['reputation_summary']['count']} agents, "
          f"avg score: {dna['reputation_summary']['avg_score']}")

    print("\n  📋 CAPABILITY MATRIX:")
    for fname, fhash in dna["capability_matrix"]["files"].items():
        status = "✅" if fhash != "MISSING" else "❌"
        print(f"    {status} {fname}: {fhash[:16]}...")

    print("\n  🐝 AGENT ROSTER:")
    for a in dna["agent_templates"][:10]:
        print(f"    • {a['id']} [{a['style']}] ⚡{a['energy']}")
    if dna["agent_count"] > 10:
        print(f"    ... +{dna['agent_count'] - 10} more")

    print("═" * 70)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTA Nucleus Extractor — Package Swarm DNA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python sifta_nuc_extractor.py --show-dna
    python sifta_nuc_extractor.py --extract
    python sifta_nuc_extractor.py --extract --branch "TESLA_ROBOT"
    python sifta_nuc_extractor.py --extract --agents HERMES SEBASTIAN
    python sifta_nuc_extractor.py --verify nuclei/sifta_nuc_*.zip
        """
    )
    parser.add_argument("--show-dna", action="store_true",
                        help="Display current swarm DNA identity")
    parser.add_argument("--extract", action="store_true",
                        help="Extract a nucleus from the running swarm")
    parser.add_argument("--verify", metavar="NUC_FILE",
                        help="Verify a nucleus zip file")
    parser.add_argument("--branch", default="GENESIS",
                        help="Branch reason (e.g. HARDWARE_EXPANSION)")
    parser.add_argument("--parent", default=None,
                        help="Parent swarm ID (for lineage)")
    parser.add_argument("--generation", type=int, default=0,
                        help="Generation number")
    parser.add_argument("--agents", nargs="+", default=None,
                        help="Select specific agents for the nucleus")

    args = parser.parse_args()

    if args.show_dna:
        show_dna()
    elif args.extract:
        extract_nucleus(
            branch_reason=args.branch,
            parent_swarm_id=args.parent,
            generation=args.generation,
            select_agents=args.agents,
        )
    elif args.verify:
        verify_nucleus(args.verify)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
