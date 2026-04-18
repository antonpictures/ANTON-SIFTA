#!/usr/bin/env python3
"""
sifta_save_defaults.py — Default “Save As” names for SIFTA PyQt dialogs.
══════════════════════════════════════════════════════════════════════════════
Qt uses the third argument to QFileDialog.getSaveFileName as directory **or**
full path including basename — then the name is pre-filled.

Pattern matches common `.sifta_documents` naming: ``MM DD YY HH-MMPM.sifta.md``.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def default_sifta_markdown_basename(now: datetime | None = None) -> str:
    """e.g. ``04 17 26 11-18PM.sifta.md``"""
    t = now or datetime.now()
    return t.strftime("%m %d %y %I-%M%p") + ".sifta.md"


def default_sifta_save_path(docs_dir: Path, now: datetime | None = None) -> Path:
    """Full path for QFileDialog pre-fill."""
    return docs_dir / default_sifta_markdown_basename(now=now)


__all__ = ["default_sifta_markdown_basename", "default_sifta_save_path"]
