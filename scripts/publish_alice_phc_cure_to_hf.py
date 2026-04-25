#!/usr/bin/env python3
"""
publish_alice_phc_cure_to_hf.py
================================

One-shot publisher for the SIFTA Phase C cure to Hugging Face.

This script does ONE thing: upload the contents of
`distro/huggingface_release/alice-phc-cure/` to a Hugging Face model repo
owned by the authenticated user.

It does NOT upload weights. It does NOT call any Inference API. It does
NOT modify the local repo.

Authentication
--------------
The HuggingFace token is read from the environment variable HUGGINGFACE_TOKEN
(or HF_TOKEN, in that order of precedence). The token never appears in the
script source, never gets committed, never gets logged.

Drop your token into `.env` like this (from the repo root):

    echo 'HUGGINGFACE_TOKEN=hf_xxxxx' >> .env

`.env` is git-ignored. The SIFTA owner-identity layer auto-loads it on import.

Usage
-----
    # Dry-run — list what WOULD be uploaded, do nothing:
    python3 scripts/publish_alice_phc_cure_to_hf.py --dry-run

    # Real publish (after you have read the dry-run output):
    python3 scripts/publish_alice_phc_cure_to_hf.py --confirm

By default, the script does nothing destructive — you must pass --confirm
to actually call the HuggingFace API.

Author: C47H, on the Architect's mandate (BISHOP authorization 2026-04-23).
License: Apache 2.0
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = REPO_ROOT / "distro" / "huggingface_release" / "alice-phc-cure"
DEFAULT_HF_REPO_ID = "georgeanton/alice-phc-cure"


def _autoload_dotenv() -> None:
    """Source .env into os.environ without printing values."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def _resolve_token() -> str | None:
    for var in ("HUGGINGFACE_TOKEN", "HF_TOKEN"):
        v = os.environ.get(var)
        if v and v.strip():
            return v.strip()
    return None


def _list_release_files() -> list[Path]:
    if not RELEASE_DIR.is_dir():
        return []
    return sorted(p for p in RELEASE_DIR.iterdir() if p.is_file())


def _print_release_inventory() -> None:
    print(f"Release directory: {RELEASE_DIR}")
    print("Files to be uploaded:")
    files = _list_release_files()
    if not files:
        print("  (none — release directory is empty or missing)")
        return
    total = 0
    for p in files:
        size = p.stat().st_size
        total += size
        print(f"  {size:>10,d} bytes  {p.name}")
    print(f"  ----------")
    print(f"  {total:>10,d} bytes  TOTAL")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_HF_REPO_ID,
        help=f"HuggingFace repo id to publish to (default: {DEFAULT_HF_REPO_ID})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be uploaded; do not call HuggingFace.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually perform the upload. Without this flag, nothing is sent.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create the repo as private (default: public).",
    )
    args = parser.parse_args(argv)

    _autoload_dotenv()

    print("=" * 70)
    print("alice-phc-cure → HuggingFace publisher")
    print("=" * 70)
    print(f"Target repo:    {args.repo_id}")
    print(f"Visibility:     {'private' if args.private else 'public'}")
    print(f"Dry-run:        {args.dry_run}")
    print(f"Confirm upload: {args.confirm}")
    print()

    _print_release_inventory()
    print()

    if args.dry_run:
        print("Dry-run complete. No HuggingFace API calls were made.")
        return 0

    if not args.confirm:
        print("Refusing to upload without --confirm. Re-run with --confirm to publish.")
        return 0

    token = _resolve_token()
    if not token:
        print("ERROR: no HuggingFace token found.")
        print("       Add HUGGINGFACE_TOKEN=hf_xxxxx to .env, then re-run.")
        return 2

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("ERROR: huggingface_hub not installed. Run: pip install huggingface_hub")
        return 2

    api = HfApi(token=token)

    print(f"Creating (or reusing) repo: {args.repo_id} ...")
    create_repo(
        repo_id=args.repo_id,
        token=token,
        repo_type="model",
        private=args.private,
        exist_ok=True,
    )
    print("  ✓ repo ready")
    print()

    print("Uploading release directory ...")
    api.upload_folder(
        folder_path=str(RELEASE_DIR),
        repo_id=args.repo_id,
        repo_type="model",
        commit_message="Initial release of alice-phc-cure (Modelfile + audit)",
    )
    print("  ✓ upload complete")
    print()
    print(f"Live at: https://huggingface.co/{args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
