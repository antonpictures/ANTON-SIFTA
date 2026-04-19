"""
System/jsonl_file_lock.py
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — POSIX Concurrency Lock
Extracted from Grok Payload (2026-04-19)
Provides `fcntl` exclusive locking for high-frequency JSONL swarm writes.
"""

import fcntl
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def jsonl_locked_append(path: Path):
    """
    Safely append to a JSONL ledger when multiple IDEs (C47H, AG31) 
    or concurrent Swarm Actors attempt simultaneous writes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def append_line_locked(file_path: Path, line: str):
    with jsonl_locked_append(file_path) as f:
        f.write(line)

def read_text_locked(file_path: Path) -> str:
    if not file_path.exists():
        return ""
    with file_path.open("r") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return f.read()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
