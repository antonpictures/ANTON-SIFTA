#!/usr/bin/env python3
"""
Kernel/path_resolver.py — single source of truth for repo paths, state dir, node identity.

Removes all /Users/ioanganton hardcodes.

Usage:
    from Kernel.path_resolver import get_repo_root, get_state_dir, get_node_id
    state = get_state_dir()
    repo = get_repo_root()

Respects:
  SIFTA_HOME (root of checkout or ~/.sifta)
  SIFTA_NODE_ID
  SIFTA_NODE_ROLE (queen/worker/edge)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_DEFAULT_STATE_NAME = ".sifta_state"
_MARKER_FILES = ("sifta_os_desktop.py", "README.md", "pyproject.toml", ".git")

_repo_root_cache: Optional[Path] = None


def get_repo_root() -> Path:
    """Return the SIFTA checkout root. Never returns a user-specific absolute path."""
    global _repo_root_cache
    if _repo_root_cache is not None:
        return _repo_root_cache

    # 1. Explicit env (portable across machines)
    env_home = os.environ.get("SIFTA_HOME")
    if env_home:
        p = Path(env_home).expanduser().resolve()
        if p.exists():
            _repo_root_cache = p
            return p

    # 2. Walk up from this file (Kernel/ is inside repo)
    here = Path(__file__).resolve()
    for candidate in (here.parent.parent, here.parent.parent.parent, here.parent):
        if any((candidate / m).exists() for m in _MARKER_FILES):
            _repo_root_cache = candidate
            return candidate

    # 3. Fallback to user home (still portable name, not hardcoded user)
    fallback = Path.home() / ".sifta"
    fallback.mkdir(parents=True, exist_ok=True)
    _repo_root_cache = fallback
    return fallback


def get_state_dir() -> Path:
    """Return the canonical .sifta_state directory (portable)."""
    root = get_repo_root()
    state = root / _DEFAULT_STATE_NAME
    state.mkdir(parents=True, exist_ok=True)
    return state


def get_node_id() -> str:
    """Portable node identifier. Never bakes a specific owner's serial."""
    env = os.environ.get("SIFTA_NODE_ID") or os.environ.get("SIFTA_HOMEWORLD_SERIAL")
    if env:
        return str(env).strip()
    # Fallback: hash of hostname or generic
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "unknown-node"


def get_node_role() -> str:
    """queen | worker | edge (default worker)."""
    return os.environ.get("SIFTA_NODE_ROLE", "worker").strip().lower()


def resolve_relative(path: str | Path) -> Path:
    """Resolve a path relative to repo root (use this instead of absolute literals)."""
    return get_repo_root() / str(path).lstrip("/")


# Convenience for legacy _state_root() callers during migration
def _legacy_state_root() -> Path:
    """Temporary bridge. Call sites should migrate to get_state_dir()."""
    return get_state_dir()
