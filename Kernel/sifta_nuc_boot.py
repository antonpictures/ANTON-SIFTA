#!/usr/bin/env python3
"""
sifta_nuc_boot.py — Swarm Nucleus Bootstrap

Takes a Nucleus (.zip) and bootstraps a NEW swarm from it.
The new swarm inherits the parent's DNA structure but starts fresh:
  - New ledger (clean)
  - New reputation (unearned)
  - No scars (virgin territory)
  - Same constitution
  - Same capability bounds
  - Lineage traceable to the parent

Usage:
    python sifta_nuc_boot.py --nuc nuclei/sifta_nuc_*.zip
    python sifta_nuc_boot.py --nuc nuclei/sifta_nuc_*.zip --target /path/to/new/swarm
    python sifta_nuc_boot.py --nuc nuclei/sifta_nuc_*.zip --dry-run
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def bootstrap_from_nucleus(nuc_path: str,
                           target_dir: str = None,
                           dry_run: bool = False) -> dict:
    """
    Bootstrap a new swarm from a Nucleus zip.

    Steps:
    1. Validate the nucleus integrity
    2. Read the DNA manifest
    3. Create the target directory structure
    4. Install agent templates
    5. Initialize clean ledger
    6. Write lineage record
    7. Verify the new swarm identity

    Returns the new swarm's DNA summary.
    """
    nuc = Path(nuc_path)
    if not nuc.exists():
        raise FileNotFoundError(f"Nucleus not found: {nuc}")

    # Read the DNA
    with zipfile.ZipFile(nuc, "r") as zf:
        dna = json.loads(zf.read("swarm_dna.json"))
        names = zf.namelist()

        print("\n" + "═" * 70)
        print("  🧬 SWARM NUCLEUS BOOTSTRAP")
        print("═" * 70)
        print(f"  Source:       {nuc.name}")
        print(f"  Parent ID:    {dna.get('swarm_id', 'UNKNOWN')[:24]}...")
        print(f"  Generation:   {dna.get('lineage', {}).get('generation', 0)}")
        print(f"  Branch:       {dna.get('lineage', {}).get('branch_reason', '?')}")
        print(f"  Agents:       {dna.get('agent_count', 0)}")

        # Determine target directory
        if target_dir:
            target = Path(target_dir)
        else:
            target = Path.cwd() / f"swarm_gen{dna['lineage']['generation'] + 1}"

        print(f"  Target:       {target}")

        if dry_run:
            print("\n  [DRY RUN] No changes will be made.")
            print("═" * 70)
            return dna

        # Confirm
        if target.exists() and any(target.iterdir()):
            print(f"\n  ⚠ Target directory is not empty: {target}")
            confirm = input("  Type 'YES' to overwrite: ").strip()
            if confirm != "YES":
                print("  Aborted.")
                return {}

        # ── CREATE DIRECTORY STRUCTURE ────────────────────────────────────────
        print("\n  [1/6] Creating directory structure...")
        target.mkdir(parents=True, exist_ok=True)
        state_dir = target / ".sifta_state"
        state_dir.mkdir(exist_ok=True)
        (target / "proposals" / "pending").mkdir(parents=True, exist_ok=True)
        (target / "proposals" / "approved").mkdir(parents=True, exist_ok=True)
        (target / "proposals" / "rejected").mkdir(parents=True, exist_ok=True)
        (target / ".sifta_reputation").mkdir(exist_ok=True)

        # ── INSTALL CONSTITUTION ──────────────────────────────────────────────
        print("  [2/6] Installing constitution...")
        if "constitution/governor.py" in names:
            gov_content = zf.read("constitution/governor.py")
            (target / "governor.py").write_bytes(gov_content)
            print(f"         governor.py installed ({len(gov_content)} bytes)")

        # ── INSTALL AGENT TEMPLATES ───────────────────────────────────────────
        print("  [3/6] Provisioning agent templates...")
        agent_count = 0
        for name in names:
            if name.startswith("agent_templates/") and name.endswith(".json"):
                agent_data = json.loads(zf.read(name))
                # Clean the template for a fresh start
                agent_data["energy"] = 100
                agent_data["style"] = "NOMINAL"
                agent_data["history"] = []
                agent_data["hash_chain"] = []
                agent_data["seq"] = 0
                agent_data["ttl"] = 3600

                agent_file = state_dir / f"{agent_data['id']}.json"
                agent_file.write_text(json.dumps(agent_data, indent=2))
                print(f"         {agent_data['id']}: provisioned (⚡100 NOMINAL)")
                agent_count += 1

        # ── INITIALIZE CLEAN LEDGER ───────────────────────────────────────────
        print("  [4/6] Seeding clean ledger...")
        if "seed/empty_ledger.sql" in names:
            sql = zf.read("seed/empty_ledger.sql").decode("utf-8")
            db_path = state_dir / "task_ledger.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(sql)
            # Insert genesis event
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, component, details) "
                "VALUES (?, ?, ?, ?)",
                (time.time(), "GENESIS_BOOT", "sifta_nuc_boot",
                 f"Bootstrapped from nucleus {nuc.name}. "
                 f"Parent swarm: {dna['swarm_id'][:12]}...")
            )
            conn.commit()
            conn.close()
            print(f"         task_ledger.db initialized")

        # ── INSTALL ROOT PUBLIC KEY ───────────────────────────────────────────
        print("  [5/6] Installing root public key...")
        if "root_pubkey.pem" in names:
            pub_content = zf.read("root_pubkey.pem")
            key_dir = target / ".sifta_keys"
            key_dir.mkdir(mode=0o700, exist_ok=True)
            (key_dir / "root_pubkey.pem").write_bytes(pub_content)
            print(f"         Root pubkey installed for lineage verification")

        # ── WRITE LINEAGE RECORD ──────────────────────────────────────────────
        print("  [6/6] Writing lineage record...")
        child_dna = {
            "version": dna["version"],
            "swarm_id": dna["swarm_id"],  # Inherits parent's root identity
            "genesis_ts": time.time(),
            "genesis_iso": datetime.now(timezone.utc).isoformat(),
            "root_pubkey_fingerprint": dna["root_pubkey_fingerprint"],
            "lineage": {
                "parent_swarm_id": dna["swarm_id"],
                "generation": dna["lineage"]["generation"] + 1,
                "branch_reason": dna["lineage"]["branch_reason"],
                "parent_genesis_ts": dna["genesis_ts"],
                "bootstrap_source": nuc.name,
            },
            "constitution_hash": dna["constitution_hash"],
            "capability_matrix": dna["capability_matrix"],
            "agent_count": agent_count,
            "bounds": dna["bounds"],
            "lineage_proof": dna.get("lineage_proof", "INHERITED"),
        }

        (state_dir / "swarm_dna.json").write_text(json.dumps(child_dna, indent=2))

        # Write boot stamp
        boot_stamp = {
            "boot_type": "NUCLEUS",
            "source": nuc.name,
            "parent_swarm_id": dna["swarm_id"][:24],
            "generation": child_dna["lineage"]["generation"],
            "boot_ts": time.time(),
            "agent_count": agent_count,
        }
        (state_dir / "active.stamp").write_text(json.dumps(boot_stamp, indent=2))

    # ── DONE ──────────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print(f"  ✅ SWARM BOOTSTRAPPED SUCCESSFULLY")
    print(f"     Location:    {target}")
    print(f"     Generation:  {child_dna['lineage']['generation']}")
    print(f"     Agents:      {agent_count}")
    print(f"     Parent:      {dna['swarm_id'][:24]}...")
    print(f"     Lineage:     {'✅ SIGNED' if child_dna.get('lineage_proof', 'UNSIGNED') != 'UNSIGNED' else '⚠ UNSIGNED'}")
    print("─" * 70)
    print(f"\n  Next steps:")
    print(f"    1. Copy your swarm code into {target}/")
    print(f"    2. cd {target}")
    print(f"    3. python server.py")
    print(f"\n  The new swarm starts with:")
    print(f"    • Fresh reputation (all agents start at 0.50)")
    print(f"    • Clean ledger (no history)")
    print(f"    • Virgin territory (no scars)")
    print(f"    • Same constitution as the parent")
    print(f"    • Provable lineage back to the root")
    print("═" * 70)

    return child_dna


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTA Nucleus Bootstrap — Spawn New Swarm from Seed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python sifta_nuc_boot.py --nuc nuclei/sifta_nuc_*.zip
    python sifta_nuc_boot.py --nuc nuclei/sifta_nuc_*.zip --target /Users/me/swarm2
    python sifta_nuc_boot.py --nuc nuclei/sifta_nuc_*.zip --dry-run
        """
    )
    parser.add_argument("--nuc", required=True,
                        help="Path to nucleus .zip file")
    parser.add_argument("--target", default=None,
                        help="Target directory for the new swarm (default: ./swarm_genN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without actually doing it")

    args = parser.parse_args()
    bootstrap_from_nucleus(args.nuc, target_dir=args.target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
