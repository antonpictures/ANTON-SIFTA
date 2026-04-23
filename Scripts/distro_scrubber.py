#!/usr/bin/env python3
"""
distro_scrubber.py

Copies the active SIFTA tree into a target directory (default .distro_build/),
scrubbing any remaining hardcoded identity literals (silicon serials, personal names,
and camera references) to generic placeholders. This ensures no PII is leaked
in the public pushed code.

It REFUSES to write to the active repository tree.
"""

import sys
import os
import shutil
import argparse
from pathlib import Path

SCRUB_MAP = {
    "GTH4921YP3": "<YOUR_SILICON_SERIAL>",
    "C07FL0JAQ6NV": "<YOUR_M1_SERIAL>",
    "Ioan George Anton": "<YOUR_NAME>",
    "George Anton": "<YOUR_NAME>",
    "Ioan's iPhone Camera": "<YOUR_CAMERA_LABEL>",
    "Ioan's": "<YOUR_NAME>'s",
    "Ioan": "<YOUR_NAME>",
    "iantongeorge@gmail.com": "<YOUR_EMAIL>",
    "antonpictures@me.com": "<YOUR_EMAIL>",
    "antonpictures@gmail.com": "<YOUR_EMAIL>",
    "george@antonpictures.com": "<YOUR_EMAIL>",
    "antonpictures.com": "<YOUR_DOMAIN>",
    "/Users/ioanganton": "/Users/<YOUR_USERNAME>",
    "ioanganton": "<YOUR_USERNAME>",
}

# Hard PII tokens that must NEVER appear in the scrubbed build, regardless of
# substitution path. The post-scrub audit greps for these and exits non-zero on
# any hit. This is the immune-system gate so an overstated "100% PII removal"
# claim cannot escape into a public push. Add new high-risk literals here.
HARD_PII_TOKENS = [
    "ioanganton",
    "iantongeorge@gmail.com",
    "antonpictures@me.com",
    "antonpictures@gmail.com",
    "Ioan George Anton",
    "GTH4921YP3",
    "C07FL0JAQ6NV",
]

# Files where third-party upstream emails are expected (open-source attribution,
# public by design). Audit skips these. Keep the list tight — if you add a path
# here, justify it in the comment so future agents can re-evaluate.
AUDIT_ALLOWLIST_SUFFIXES = [
    "Library/llama.cpp/AUTHORS",                   # llama.cpp upstream contributors
    "Library/llama.cpp/vendor/miniaudio/miniaudio.h",  # miniaudio author (David Reid)
    "Library/swarmrl/pyproject.toml",              # swarmrl upstream maintainer (Tovey)
]

def is_subpath(child, parent):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False

def get_ignore_list():
    return [
        ".git",
        ".venv",
        "__pycache__",
        ".distro_build",
        ".DS_Store",
        ".sifta_state", 
        "repair_log.jsonl",
        "m5queen_dead_drop.jsonl",
        "artifacts",
        "pytest.ini",
        "Archive",
        ".personal"
    ]

def scrub_file(src: Path, dst: Path):
    if src.stat().st_size > 5_000_000:
        shutil.copy2(src, dst)
        return
    try:
        content = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shutil.copy2(src, dst)
        return
        
    for bad_str, safe_str in SCRUB_MAP.items():
        content = content.replace(bad_str, safe_str)
        
    dst.write_text(content, encoding="utf-8")
    # Preserve permissions
    shutil.copymode(src, dst)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=".distro_build/", help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output).resolve()
    
    if output_dir == repo_root or is_subpath(repo_root, output_dir):
        print(f"ERROR: Cannot output into the active tree itself! ({output_dir})")
        sys.exit(1)

    if not args.dry_run:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
    ignores = get_ignore_list()
    
    files_processed = 0
    literals_found = 0

    print(f"Scrubbing tree into {output_dir}...")
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignores and not d.startswith(".")]
        
        current_dir = Path(root)
        rel_dir = current_dir.relative_to(repo_root)
        target_dir = output_dir / rel_dir
        
        if not args.dry_run and not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            
        for f in files:
            if f in ignores or f.startswith(".") or f.endswith(".jsonl") or f.endswith(".json"):
                continue
            src_file = current_dir / f
            dst_file = target_dir / f
            
            if src_file.is_symlink():
                if not args.dry_run:
                    shutil.copy2(src_file, dst_file, follow_symlinks=False)
                continue
            
            if args.dry_run:
                try:
                    content = src_file.read_text(encoding="utf-8")
                    for bad in SCRUB_MAP.keys():
                        count = content.count(bad)
                        if count > 0:
                            print(f"[DRY RUN] Would scrub '{bad}' {count} times in {rel_dir / f}")
                            literals_found += count
                except UnicodeDecodeError:
                    pass
            else:
                print(f"Scrubbing: {src_file}")
                scrub_file(src_file, dst_file)
                files_processed += 1
                
    if args.dry_run:
        print(f"Dry run complete. Found {literals_found} hardcoded items remaining in the tree.")
        return

    print(f"Scrubbed {files_processed} files into {output_dir}.")

    # Post-scrub immune-system gate. A SCRUB_MAP miss must not silently leak
    # into a public push. Walk the output and grep for HARD_PII_TOKENS. Any
    # hit outside AUDIT_ALLOWLIST_SUFFIXES is a hard fail.
    print("\nRunning post-scrub PII audit...")
    leaks = []
    for root, dirs, files in os.walk(output_dir):
        dirs[:] = [d for d in dirs if d not in ignores and not d.startswith(".")]
        for f in files:
            path = Path(root) / f
            try:
                rel = path.relative_to(output_dir).as_posix()
            except ValueError:
                continue
            if any(rel.endswith(suf) for suf in AUDIT_ALLOWLIST_SUFFIXES):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for token in HARD_PII_TOKENS:
                if token in content:
                    leaks.append((rel, token, content.count(token)))

    if leaks:
        print(f"\nPII AUDIT FAILED: {len(leaks)} leak(s) detected in {output_dir}:")
        for rel, token, count in leaks[:50]:
            print(f"  {rel}: '{token}' x{count}")
        if len(leaks) > 50:
            print(f"  ... and {len(leaks) - 50} more")
        print("\nFix SCRUB_MAP and re-run before pushing anywhere public.")
        sys.exit(2)

    print(f"PII audit clean. {output_dir} is safe for public push.")

if __name__ == "__main__":
    main()
