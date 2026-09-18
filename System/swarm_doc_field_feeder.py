#!/usr/bin/env python3
"""swarm_doc_field_feeder.py — docling mechanism: provenance-carrying document
chunks feeding the stigmergic field.

Borged from docling-project/docling (66.6k): structured layout/table-aware
parsing with source provenance per chunk, feeding the field rather than a blob.
This organ keeps it dependency-free: plaintext/Markdown natively; .docx via
zipfile XML; .pdf via pdftotext if present (poppler) else skipped with an
honest receipt.

Each chunk lands as a pheromone trace in .sifta_state/document_stigmergy.jsonl
with source path, locator, sha256, truth label. Never rewrites a source file.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from zipfile import ZipFile, BadZipFile

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HEADING_RE = re.compile(r"^#{1,6}\s+.+$", re.M)


def _chunk_markdown(text: str) -> list[dict]:
    lines = str(text).splitlines()
    chunks: list[dict] = []
    current_title = "(top)"
    buf: list[str] = []
    start = 0
    for i, line in enumerate(lines + [""]):
        if (i < len(lines) and _HEADING_RE.match(line)) or i == len(lines):
            body = "\n".join(buf).strip()
            if body:
                chunks.append({"locator": current_title, "text": body})
            if i < len(lines):
                current_title = line.strip()
            buf = []
            start = i
        else:
            buf.append(line)
    return chunks


def _chunk_docx(path: Path) -> list[dict]:
    with ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    texts = re.findall(r"<w:t[^>]*>([^<]+)</w:t>", xml)
    return _chunk_markdown("\n".join(texts)) if texts else []


def _chunk_pdf(path: Path) -> list[dict]:
    try:
        r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return []
        return [{"locator": f"page~{i+1}", "text": chunk.strip()}
                for i, chunk in enumerate(r.stdout.split("\f"))
                if chunk.strip()]
    except (OSError, subprocess.TimeoutExpired):
        return []


def feed_document(path: str | Path, *, state_dir: Path | None = None,
                  ledger: str = "document_stigmergy.jsonl") -> dict:
    """Chunk one document into provenance-carrying pheromone traces. Never raises."""
    state = Path(state_dir) if state_dir else _STATE
    src = Path(path)
    out_rows: list[dict] = []
    suffix = src.suffix.lower()
    skipped = False
    try:
        if suffix in (".md", ".txt", ".log"):
            rows = _chunk_markdown(src.read_text(encoding="utf-8", errors="replace"))
        elif suffix == ".docx":
            rows = _chunk_docx(src)
        elif suffix == ".pdf":
            rows = _chunk_pdf(src)
            skipped = skipped or not rows
        else:
            skipped = True
            rows = []
    except (OSError, BadZipFile, UnicodeDecodeError):
        skipped = True
        rows = []
    for i, chunk in enumerate(rows):
        text = chunk.get("text", "")
        if not text:
            continue
        out_rows.append({
            "ts": time.time(),
            "source_path": str(src),
            "chunk_index": i,
            "locator": chunk.get("locator", ""),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "char_len": len(text),
            "stigmergic_label": "DOCUMENT_CHUNK",
            "truth_label": "DOC_FEED_V1",
        })
    report = {"schema": "DOC_FEED_V1", "ts": time.time(), "path": str(src),
              "chunks": len(out_rows), "skipped": bool(skipped),
              "truth_label": "DOC_FEED_V1"}
    try:
        state.mkdir(parents=True, exist_ok=True)
        with (state / ledger).open("a", encoding="utf-8") as fh:
            for row in out_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.write(json.dumps(report, ensure_ascii=False) + "\n")
    except OSError:
        report["write_error"] = True
    return report
