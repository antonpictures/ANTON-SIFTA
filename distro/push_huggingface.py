#!/usr/bin/env python3
"""
distro/push_huggingface.py
══════════════════════════════════════════════════════════════════
Push the current public SIFTA model blobs + metadata to HuggingFace.

Core repos pushed:
  1. georgeanton/alice-m5-cortex-8b-6.3gb   — M5 primary multimodal cortex
  2. georgeanton/alice-m1-cortex-4.5b-3.4gb — 8GB-safe M1 cortex
  3. georgeanton/sifta-corvid-qwen35        — fast Corvid scout/reflex arm
  4. georgeanton/sifta-classifier-c1-3.1b-6.2gb — C1 intent classifier

Usage:
  python3 distro/push_huggingface.py           # dry-run (shows what would be pushed)
  python3 distro/push_huggingface.py --push     # actually push

Prerequisites:
  pip install huggingface_hub
  huggingface-cli login  (or set HF_TOKEN env)
"""

import os
import sys
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_BLOBS = Path.home() / ".ollama" / "models" / "blobs"
_DISTRO = _REPO / "distro" / "huggingface_release"

# ── Model definitions ─────────────────────────────────────────────────
MODELS = {
    "alice-m5-cortex-8b-6.3gb:latest": {
        "blob_sha": "sha256-ef5523975d644e47293960b8b87c83b11a6d50253a544e35addca72af33e13c6",
        "output_name": "alice-m5-cortex-8b-6.3gb.gguf",
        "hf_repo": "georgeanton/alice-m5-cortex-8b-6.3gb",
        "local_dir": _DISTRO / "alice-m5-cortex-8b-6.3gb",
        "size_hint": "~6.3 GB",
    },
    "alice-m1-cortex-4.5b-3.4gb:latest": {
        "blob_sha": "sha256-464c1dda6a052d909b11d20c31bcb21060e969e334716ba8ed7abf64ca1be10f",
        "output_name": "alice-m1-cortex-4.5b-3.4gb.gguf",
        "hf_repo": "georgeanton/alice-m1-cortex-4.5b-3.4gb",
        "local_dir": _DISTRO / "alice-m1-cortex-4.5b-3.4gb",
        "size_hint": "~3.4 GB",
    },
    "alice-m1-scout-2.3b-2.7gb:latest": {
        "blob_sha": "sha256-b709d81508a078a686961de6ca07a953b895d9b286c46e17f00fb267f4f2d297",
        "output_name": "qwen35-2b-corvid.gguf",
        "hf_repo": "georgeanton/sifta-corvid-qwen35",
        "local_dir": _DISTRO / "sifta-corvid-qwen35",
        "size_hint": "~2.6 GB",
    },
    "sifta-classifier-c1-3.1b-6.2gb:latest": {
        "blob_sha": "sha256-0b1622df663cb7dfcd39baaefb9719ceed926422360cfe1c3493818fc39ff0eb",
        "output_name": "sifta-classifier-c1-3.1b-6.2gb.gguf",
        "hf_repo": "georgeanton/sifta-classifier-c1-3.1b-6.2gb",
        "local_dir": _DISTRO / "sifta-classifier-c1-3.1b-6.2gb",
        "size_hint": "~6.2 GB",
    },
}


def sha256_file(path: Path, chunk_size: int = 8192) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_blobs():
    """Check all Ollama blobs exist locally."""
    print("🔍 Verifying local Ollama blobs...")
    ok = True
    for name, info in MODELS.items():
        blob = _BLOBS / info["blob_sha"]
        if blob.exists():
            size_gb = blob.stat().st_size / (1024**3)
            print(f"  ✅ {name}: {blob.name[:20]}... ({size_gb:.1f} GB)")
        else:
            print(f"  ❌ {name}: MISSING — run 'ollama pull {name}'")
            ok = False
    return ok


def prepare_staging(staging: Path):
    """Copy blobs + metadata to staging dirs."""
    print("\n📦 Staging files for upload...")

    # Group by HF repo
    repos = {}
    for name, info in MODELS.items():
        repo = info["hf_repo"]
        if repo not in repos:
            repos[repo] = {"files": [], "local_dir": info["local_dir"]}
        blob = _BLOBS / info["blob_sha"]
        target = staging / info["output_name"]
        repos[repo]["files"].append((blob, target, info["output_name"]))

    for repo, data in repos.items():
        repo_dir = staging / repo.split("/")[-1]
        repo_dir.mkdir(parents=True, exist_ok=True)

        # Copy metadata from local distro dir
        local_dir = data["local_dir"]
        if local_dir.exists():
            for f in local_dir.iterdir():
                if f.name.startswith("."):
                    continue
                dst = repo_dir / f.name
                if f.is_file():
                    shutil.copy2(f, dst)
                    print(f"  📄 {repo}: {f.name}")

        # Symlink blobs (to avoid doubling disk usage)
        for blob, target, out_name in data["files"]:
            dst = repo_dir / out_name
            if not dst.exists():
                os.symlink(blob, dst)
                size_gb = blob.stat().st_size / (1024**3)
                print(f"  🔗 {repo}: {out_name} ({size_gb:.1f} GB → symlink)")

    return repos


def push_repos(staging: Path, repos: dict, dry_run: bool):
    """Push each repo to HuggingFace."""
    from huggingface_hub import HfApi, create_repo

    api = HfApi()

    for repo_id, data in repos.items():
        repo_name = repo_id.split("/")[-1]
        repo_dir = staging / repo_name

        print(f"\n{'🏗️' if dry_run else '🚀'} {'[DRY RUN]' if dry_run else 'PUSHING'} {repo_id}")

        # List files
        files = sorted(repo_dir.iterdir())
        for f in files:
            if f.is_symlink():
                real = f.resolve()
                size = real.stat().st_size / (1024**3)
                print(f"  📦 {f.name} ({size:.1f} GB — real blob)")
            elif f.is_file():
                size = f.stat().st_size / 1024
                print(f"  📄 {f.name} ({size:.0f} KB)")

        if dry_run:
            print(f"  ⏭️  Skipped (dry run)")
            continue

        # Create repo if needed
        try:
            create_repo(repo_id, repo_type="model", exist_ok=True)
        except Exception as e:
            print(f"  ⚠️  create_repo: {e}")

        # Upload everything
        api.upload_folder(
            folder_path=str(repo_dir),
            repo_id=repo_id,
            repo_type="model",
            commit_message="SIFTA public cortex distro update - 2026-05-09",
        )
        print(f"  ✅ Pushed to https://huggingface.co/{repo_id}")


def main():
    dry_run = "--push" not in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN — add --push to actually upload to HuggingFace")
        print("=" * 60)

    # Step 1: Verify blobs
    if not verify_blobs():
        print("\n❌ Missing blobs. Pull them with ollama first.")
        sys.exit(1)

    # Step 2: Stage
    staging = Path(tempfile.mkdtemp(prefix="sifta_hf_"))
    repos = prepare_staging(staging)

    # Step 3: Push
    push_repos(staging, repos, dry_run)

    # Cleanup
    if dry_run:
        print(f"\nStaging dir (inspect if needed): {staging}")
    else:
        # Don't delete staging on success — symlinks only, no space wasted
        print(f"\n✅ ALL REPOS PUSHED.")
        print(f"   Staging dir: {staging}")

    print("\nHuggingFace links:")
    seen = set()
    for info in MODELS.values():
        r = info["hf_repo"]
        if r not in seen:
            print(f"  https://huggingface.co/{r}")
            seen.add(r)


if __name__ == "__main__":
    main()
