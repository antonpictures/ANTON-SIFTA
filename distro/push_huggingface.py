#!/usr/bin/env python3
"""
distro/push_huggingface.py
══════════════════════════════════════════════════════════════════
Push all SIFTA model blobs + metadata to HuggingFace.

Repos pushed:
  1. georgeanton/alice-phc-cure     — Gemma4 PHC brain (Alice cortex)
  2. georgeanton/sifta-corvid-qwen35 — Qwen 3.5 2B + 4B (corvid ganglion)

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
    "gemma4-phc": {
        "blob_sha": "sha256-4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a",
        "output_name": "alice-phc-cure.gguf",
        "hf_repo": "georgeanton/alice-phc-cure",
        "local_dir": _DISTRO / "alice-phc-cure",
        "size_hint": "~8.9 GB",
    },
    "qwen3.5:2b": {
        "blob_sha": "sha256-b709d81508a078a686961de6ca07a953b895d9b286c46e17f00fb267f4f2d297",
        "output_name": "qwen35-2b-corvid.gguf",
        "hf_repo": "georgeanton/sifta-corvid-qwen35",
        "local_dir": _DISTRO / "sifta-corvid-qwen35",
        "size_hint": "~2.6 GB",
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
            commit_message=f"SIFTA distro update — Event 45 Swarm Bestiary",
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
