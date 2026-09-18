#!/usr/bin/env python3
"""swarm_context_compression.py — headroom/caveman mechanism: compress evidence
before it reaches a cortex.

Borged from headroomlabs-ai/headroom + JuliusBrussee/caveman: SIFTA's prompt
assembly spends tokens on raw ledger/tool chunks. This organ compresses those
chunks before the boundary: whitespace collapse, dedupe of repeated lines,
head+tail keep with elision marker, protection of receipt ids / hashes / truth
labels (never compress out a receipt).

Pure stdlib. Never raises; returns compressed chunks plus byte accounting so the
STGM economy can measure the saving.
"""
from __future__ import annotations

import re
import time

# Never compress these: receipts, hashes, truth labels, receipt ids.
_PROTECT_RE = re.compile(
    r"truth_label|receipt_id|trace_id|sha256|WDP_V1|MEMORY_CONSOLIDATION_V1|"
    r"WE_CODE_TOGETHER|IDE_BOOT_COVENANT",
    re.I,
)


def _squash(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def compress_chunk(text: str, *, head_lines: int = 6, tail_lines: int = 4,
                   target_chars: int = 4000) -> dict:
    """Compress one chunk with head+tail keep. Returns dict with text + savings."""
    raw = str(text or "")
    if len(raw) <= target_chars or _PROTECT_RE.search(raw):
        return {"text": raw, "in_chars": len(raw), "out_chars": len(raw), "compressed": False}
    squashed = _squash(raw)
    lines = squashed.splitlines()
    if len(lines) <= head_lines + tail_lines + 2:
        return {"text": squashed, "in_chars": len(raw), "out_chars": len(squashed), "compressed": True}
    elided = len(lines) - head_lines - tail_lines
    kept = lines[:head_lines] + [f"[{elided} lines elided]"] + lines[-tail_lines:]
    out = "\n".join(kept)
    return {"text": out, "in_chars": len(raw), "out_chars": len(out), "compressed": True, "elided_lines": elided}


def compress_chunks(chunks: list[str], *, target_chars: int = 4000) -> dict:
    """Compress a list of chunks; returns compressed texts + batch receipt row."""
    outs = [compress_chunk(c, target_chars=target_chars) for c in chunks]
    total_in = sum(o["in_chars"] for o in outs)
    total_out = sum(o["out_chars"] for o in outs)
    return {
        "schema": "CONTEXT_COMPRESSION_V1",
        "ts": time.time(),
        "chunks": [o["text"] for o in outs],
        "in_chars": total_in,
        "out_chars": total_out,
        "saved_chars": total_in - total_out,
        "compressed_any": any(o.get("compressed") for o in outs),
        "truth_label": "CONTEXT_COMPRESSION_V1",
    }
