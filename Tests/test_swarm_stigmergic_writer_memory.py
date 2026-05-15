import json
import os
from pathlib import Path

from System.swarm_stigmergic_writer_memory import (
    answer_writer_memory_query,
    is_writer_memory_query,
    scan_writer_documents,
)


def _write_doc(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_writer_memory_query_detector_catches_saved_document_questions():
    assert is_writer_memory_query("What did we talk about?")
    assert is_writer_memory_query("Can you read the pheromones and files?")
    assert is_writer_memory_query("Do you remember the saved Writer documents?")
    assert not is_writer_memory_query("Hi Alice, can you see what I type?")


def test_scan_writer_documents_extracts_titles_dates_and_snippets(tmp_path):
    docs = tmp_path / ".sifta_documents"
    docs.mkdir()
    _write_doc(
        docs / "05 14 26 10-55AM.sifta.md",
        "# Document - Ioan George Anton\n"
        "*May 14, 2026 at 10:55 AM*\n\n"
        "---\nHi Alice\n\nAlice\nI am here in this saved page.\n",
    )
    _write_doc(docs / "ignore.txt", "not a writer doc")

    memories = scan_writer_documents(docs)

    assert len(memories) == 1
    assert memories[0].name == "05 14 26 10-55AM.sifta.md"
    assert memories[0].created_label == "May 14, 2026 at 10:55 AM"
    assert memories[0].title == "Ioan George Anton"
    assert "Hi Alice" in memories[0].snippets
    assert "Alice: I am here in this saved page." in memories[0].snippets


def test_answer_writer_memory_query_cites_disk_and_writes_receipt(tmp_path):
    docs = tmp_path / ".sifta_documents"
    state = tmp_path / ".sifta_state"
    docs.mkdir()
    _write_doc(
        docs / "05 14 26 10-55AM.sifta.md",
        "# Document - Ioan George Anton\n"
        "*May 14, 2026 at 10:55 AM*\n\n"
        "---\nHahaha Alice, you responded, this is the first app we created together.\n\n"
        "Alice\nThat first little project set the tone for everything that followed.\n",
    )

    answer = answer_writer_memory_query("What did we talk about?", docs_dir=docs, state_dir=state)

    assert "I checked 1 saved Writer document" in answer
    assert "05 14 26 10-55AM.sifta.md" in answer
    assert "first app we created together" in answer
    assert "Receipt: writer_memory_reader:" in answer
    receipt = json.loads((state / "writer_memory_reader_receipts.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert receipt["truth_label"] == "WRITER_MEMORY_READER_V1"
    assert receipt["docs_count"] == 1
    assert receipt["selected"][0]["name"] == "05 14 26 10-55AM.sifta.md"


def test_generic_writer_memory_question_prefers_recent_documents(tmp_path):
    docs = tmp_path / ".sifta_documents"
    state = tmp_path / ".sifta_state"
    docs.mkdir()
    old = docs / "old.sifta.md"
    recent = docs / "recent.sifta.md"
    _write_doc(old, "# Document - Old\n*April 16, 2026*\n\n---\nOld talk talk talk.\n")
    _write_doc(recent, "# Document - Recent\n*May 14, 2026*\n\n---\nHi Alice, can you read this saved page?\n")
    os.utime(old, (1000, 1000))
    os.utime(recent, (2000, 2000))

    answer = answer_writer_memory_query("What did we talk about?", docs_dir=docs, state_dir=state)

    first_bullet = next(line for line in answer.splitlines() if line.startswith("- "))
    assert "recent.sifta.md" in first_bullet


def test_answer_writer_memory_query_reports_empty_directory(tmp_path):
    docs = tmp_path / ".sifta_documents"
    state = tmp_path / ".sifta_state"
    docs.mkdir()

    answer = answer_writer_memory_query("read the saved documents", docs_dir=docs, state_dir=state)

    assert "found no saved .sifta.md Writer documents yet" in answer
    receipt = json.loads((state / "writer_memory_reader_receipts.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert receipt["docs_count"] == 0
    assert receipt["selected"] == []
