#!/usr/bin/env python3
"""Deterministic memory reader for saved Stigmergic Writer documents.

This is the local organ behind Writer questions such as "what did we talk
about?" It reads saved ``.sifta.md`` files, returns bounded evidence, and
writes an append-only receipt. It does not infer from vibes when the file
system can answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import time
import uuid


_REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOCS_DIR = _REPO / ".sifta_documents"
DEFAULT_STATE_DIR = _REPO / ".sifta_state"

_QUERY_RE = re.compile(
    r"("
    r"what\s+did\s+we\s+(talk|write|say)\s+about|"
    r"what\s+were\s+we\s+(talking|writing)\s+about|"
    r"read\s+(the\s+)?(pheromones|files|documents|docs|memories)|"
    r"can\s+you\s+read\s+(them|the\s+files|the\s+documents)|"
    r"saved\s+(writer\s+)?(documents|docs|files|memories)|"
    r"stigmergic\s+writer.*(files|documents|memories|talk|conversation)|"
    r"writer\s+(memory|memories|documents|docs|history)|"
    r"conversation[s]?\s+inside|"
    r"pheromone[s]?"
    r")",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r"^\*(?P<label>[^*]+)\*\s*$")
_TITLE_RE = re.compile(r"^#\s+Document\s+[-\u2014]\s+(?P<title>.+?)\s*$", re.IGNORECASE)
_SPEAKER_RE = re.compile(r"^(Alice|Ioan|George|User|Architect)\s*:?$", re.IGNORECASE)


@dataclass(frozen=True)
class WriterDocumentMemory:
    path: Path
    name: str
    title: str
    created_label: str
    mtime: float
    word_count: int
    sha256: str
    text: str
    snippets: tuple[str, ...]


def is_writer_memory_query(text: str) -> bool:
    """Return True when the current Writer turn asks about saved Writer memory."""
    return bool(_QUERY_RE.search(text or ""))


def scan_writer_documents(docs_dir: Path | str | None = None) -> list[WriterDocumentMemory]:
    """Load saved Writer markdown documents from newest to oldest."""
    root = Path(docs_dir) if docs_dir is not None else DEFAULT_DOCS_DIR
    if not root.exists():
        return []

    docs: list[WriterDocumentMemory] = []
    for path in root.glob("*.sifta.md"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            stat = path.stat()
        except OSError:
            continue
        sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        docs.append(
            WriterDocumentMemory(
                path=path,
                name=path.name,
                title=_extract_title(text),
                created_label=_extract_date_label(text) or path.stem,
                mtime=stat.st_mtime,
                word_count=len(text.split()),
                sha256=sha,
                text=text,
                snippets=tuple(_extract_snippets(text)),
            )
        )
    docs.sort(key=lambda doc: (doc.mtime, doc.name), reverse=True)
    return docs


def answer_writer_memory_query(
    query: str,
    docs_dir: Path | str | None = None,
    state_dir: Path | str | None = None,
    limit: int = 4,
) -> str:
    """Answer a Writer-memory query from saved files and write a receipt."""
    docs_root = Path(docs_dir) if docs_dir is not None else DEFAULT_DOCS_DIR
    state_root = Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR
    docs = scan_writer_documents(docs_root)
    selected = _rank_documents(query, docs)[: max(1, limit)]

    if not docs:
        answer = (
            f"I checked {docs_root} and found no saved .sifta.md Writer documents yet. "
            "I will answer from saved files once they exist."
        )
    else:
        lines = [
            f"I checked {len(docs)} saved Writer document(s) in {docs_root.name}. "
            "Here is the grounded memory from disk:"
        ]
        for doc in selected:
            lines.append(f"- {doc.created_label} - {doc.name} ({doc.word_count} words)")
            for snippet in _pick_snippets(query, doc, limit=2):
                lines.append(f"  - {snippet}")
        answer = "\n".join(lines)

    receipt_hash = _write_receipt(
        query=query,
        docs_dir=docs_root,
        state_dir=state_root,
        docs=docs,
        selected=selected,
        answer=answer,
    )
    return f"{answer}\n\nReceipt: writer_memory_reader:{receipt_hash[:12]}"


def _extract_title(text: str) -> str:
    for line in text.splitlines()[:12]:
        match = _TITLE_RE.match(line.strip())
        if match:
            return match.group("title").strip()
    return ""


def _extract_date_label(text: str) -> str:
    for line in text.splitlines()[:16]:
        match = _DATE_RE.match(line.strip())
        if match:
            return match.group("label").strip()
    return ""


def _extract_snippets(text: str, max_snippets: int = 10) -> list[str]:
    snippets: list[str] = []
    pending_speaker = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line in {"---", "----"}:
            continue
        if line.startswith("# Document"):
            continue
        if _DATE_RE.match(line):
            continue
        speaker = _SPEAKER_RE.match(line)
        if speaker:
            pending_speaker = speaker.group(1).capitalize()
            continue
        if len(line) < 3:
            continue
        if pending_speaker:
            line = f"{pending_speaker}: {line}"
            pending_speaker = ""
        snippets.append(_squash(line))
        if len(snippets) >= max_snippets:
            break
    return snippets


def _rank_documents(query: str, docs: list[WriterDocumentMemory]) -> list[WriterDocumentMemory]:
    terms = _terms(query)
    if not docs:
        return []

    newest = max(doc.mtime for doc in docs)

    def score(doc: WriterDocumentMemory) -> tuple[float, float, str]:
        haystack = f"{doc.name} {doc.title} {doc.text}".lower()
        term_hits = sum(haystack.count(term) for term in terms)
        recent_bonus = max(0.0, 1.0 - ((newest - doc.mtime) / (7 * 24 * 3600)))
        direct_bonus = 2.0 if any(term in doc.name.lower() for term in terms) else 0.0
        return (term_hits + recent_bonus + direct_bonus, doc.mtime, doc.name)

    return sorted(docs, key=score, reverse=True)


def _pick_snippets(query: str, doc: WriterDocumentMemory, limit: int = 2) -> list[str]:
    terms = _terms(query)
    snippets = list(doc.snippets)
    if not snippets:
        return ["No readable text snippets survived parsing."]
    if not terms:
        return [_truncate(snippet, 190) for snippet in snippets[:limit]]

    def score(snippet: str) -> tuple[int, int]:
        lower = snippet.lower()
        return (sum(lower.count(term) for term in terms), -len(snippet))

    ranked = sorted(snippets, key=score, reverse=True)
    return [_truncate(snippet, 190) for snippet in ranked[:limit]]


def _terms(query: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9_]{3,}", (query or "").lower())
    stop = {
        "what",
        "were",
        "did",
        "does",
        "can",
        "you",
        "talk",
        "talked",
        "talking",
        "write",
        "wrote",
        "writing",
        "say",
        "said",
        "with",
        "that",
        "this",
        "them",
        "they",
        "inside",
        "about",
        "read",
        "files",
        "docs",
        "document",
        "documents",
        "saved",
        "writer",
        "memory",
        "memories",
        "stigmergic",
        "pheromones",
    }
    terms = [word for word in words if word not in stop]
    return terms[:10]


def _write_receipt(
    query: str,
    docs_dir: Path,
    state_dir: Path,
    docs: list[WriterDocumentMemory],
    selected: list[WriterDocumentMemory],
    answer: str,
) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "WRITER_MEMORY_READER_V1",
        "query": query,
        "docs_dir": str(docs_dir),
        "docs_count": len(docs),
        "selected": [
            {
                "path": str(doc.path),
                "name": doc.name,
                "created_label": doc.created_label,
                "word_count": doc.word_count,
                "sha256": doc.sha256,
            }
            for doc in selected
        ],
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
    }
    receipt_hash = hashlib.sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()
    row["receipt_hash"] = receipt_hash
    with (state_dir / "writer_memory_reader_receipts.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return receipt_hash


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _truncate(text: str, limit: int) -> str:
    text = _squash(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."
