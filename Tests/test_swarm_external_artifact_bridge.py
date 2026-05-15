"""Tests for the external-artifact bridge organ.

Architect 2026-05-14: "I tried to load Grok — he has tools." Covenant
discipline says browser-tab tools (Grok, ChatGPT custom GPTs, Claude.ai)
must enter SIFTA's body through a proof-bearing import lane with
sha256 + source label + URL. This module is that lane. Tests guard:

  - sha256 is computed correctly and used for dedup
  - Source inference order: sidecar > filename hint > default
  - Idempotent scan — re-running does not duplicate
  - Caller-provided source/url overrides inference
  - Unknown filename → "external_unknown" (no silent fake source)
  - File-type taxonomy is correct (docx/pdf/md/other)
  - find_by_sha256 supports prefix lookup
  - list_recent_imports returns most-recent-first
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_external_artifact_bridge import (
    KNOWN_SOURCES,
    LEDGER_NAME,
    SUPPORTED_SUFFIXES,
    TRUTH_LABEL,
    find_by_sha256,
    import_one,
    infer_source,
    list_recent_imports,
    scan_folder,
)


# ── Source inference ─────────────────────────────────────────────

def test_source_inference_sidecar_wins(tmp_path):
    f = tmp_path / "grok_brief.md"
    f.write_text("body")
    sidecar = {"source": "chatgpt", "url": "https://chatgpt.com/c/abc"}
    source, url, notes, seen = infer_source(f, sidecar_meta=sidecar)
    # Sidecar wins over filename hint (grok_ would have inferred "grok")
    assert source == "chatgpt"
    assert url == "https://chatgpt.com/c/abc"
    assert seen is True


def test_source_inference_filename_hint(tmp_path):
    f = tmp_path / "grok_brief.md"
    f.write_text("body")
    source, url, notes, seen = infer_source(f, sidecar_meta=None)
    assert source == "grok"
    assert url is None
    assert seen is False


@pytest.mark.parametrize("prefix,expected", [
    ("grok_", "grok"),
    ("Grok-", "grok"),  # case-insensitive
    ("claude_", "claude"),
    ("gemini_", "gemini"),
    ("gemma_", "gemma"),
    ("perplexity_", "perplexity"),
    ("swarmgpt_", "chatgpt:swarm-gpt"),
    ("swarm-gpt_", "chatgpt:swarm-gpt"),
    ("chatgpt_", "chatgpt"),
    ("codex_", "codex"),
    ("mistral_", "mistral"),
])
def test_filename_hints_all_recognized(prefix, expected, tmp_path):
    f = tmp_path / f"{prefix}thing.docx"
    f.write_text("x")
    source, _, _, _ = infer_source(f, sidecar_meta=None)
    assert source == expected


def test_source_default_when_no_hint(tmp_path):
    f = tmp_path / "random_doc.txt"
    f.write_text("x")
    source, _, _, _ = infer_source(f, sidecar_meta=None)
    assert source == "external_unknown"


def test_known_sources_taxonomy_includes_external_unknown():
    """Defensive: the fallback label must be in KNOWN_SOURCES."""
    assert "external_unknown" in KNOWN_SOURCES


# ── import_one ────────────────────────────────────────────────────

def test_import_one_writes_provenance_row(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("hello from grok")
    out = import_one(f, source="grok", url="https://x", state_root=tmp_path)
    assert out["ok"] is True
    assert out["skipped"] is False
    assert out["source"] == "grok"
    assert out["url"] == "https://x"
    assert out["file_type"] == "md"
    assert len(out["sha256"]) == 64
    # Ledger written
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    line = ledger.read_text().strip().splitlines()[-1]
    row = json.loads(line)
    assert row["truth_label"] == TRUTH_LABEL
    assert row["sha256"] == out["sha256"]


def test_import_one_sha256_matches_file(tmp_path):
    body = b"deterministic content for sha"
    f = tmp_path / "x.txt"
    f.write_bytes(body)
    out = import_one(f, source="claude", state_root=tmp_path)
    expected = hashlib.sha256(body).hexdigest()
    assert out["sha256"] == expected


def test_import_one_is_idempotent(tmp_path):
    f = tmp_path / "y.md"
    f.write_text("once")
    r1 = import_one(f, source="grok", state_root=tmp_path)
    r2 = import_one(f, source="grok", state_root=tmp_path)
    assert r1["skipped"] is False
    assert r2["skipped"] is True
    assert r2["reason"] == "already_imported"
    # Only ONE row in the ledger
    ledger = tmp_path / LEDGER_NAME
    assert len(ledger.read_text().strip().splitlines()) == 1


def test_import_one_caller_source_overrides_filename_hint(tmp_path):
    f = tmp_path / "grok_thing.md"
    f.write_text("x")
    # Filename says grok, caller says claude → caller wins
    out = import_one(f, source="claude", state_root=tmp_path)
    assert out["source"] == "claude"


def test_import_one_handles_missing_file(tmp_path):
    out = import_one(tmp_path / "nope.md", state_root=tmp_path)
    assert out["ok"] is False
    assert "not found" in out["reason"]


def test_import_one_recognizes_sidecar_url_and_notes(tmp_path):
    f = tmp_path / "doc.docx"
    f.write_text("x")
    sidecar = tmp_path / "doc.docx.meta.json"
    sidecar.write_text(json.dumps({
        "source": "chatgpt:swarm-gpt",
        "url": "https://chatgpt.com/g/swarm-gpt/c/abc",
        "notes": "draft of paper",
    }))
    out = import_one(f, state_root=tmp_path)
    assert out["source"] == "chatgpt:swarm-gpt"
    assert out["url"] == "https://chatgpt.com/g/swarm-gpt/c/abc"
    assert out["notes"] == "draft of paper"
    assert out["sidecar_seen"] is True


# ── scan_folder ───────────────────────────────────────────────────

def test_scan_folder_picks_up_multiple_files(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "grok_a.md").write_text("alpha")
    (inbox / "claude_b.md").write_text("beta")
    (inbox / "swarmgpt_c.pdf").write_bytes(b"%PDF-1.4 fake")
    out = scan_folder(inbox, state_root=tmp_path)
    assert out["ok"] is True
    assert out["n_imported"] == 3
    sources = {r["source"] for r in out["imported"]}
    assert sources == {"grok", "claude", "chatgpt:swarm-gpt"}


def test_scan_folder_skips_sidecar_metadata_files(tmp_path):
    """A `.meta.json` sidecar is NOT itself an artifact to import."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "doc.docx").write_text("body")
    (inbox / "doc.docx.meta.json").write_text(json.dumps({"source": "grok"}))
    out = scan_folder(inbox, state_root=tmp_path)
    assert out["n_imported"] == 1
    assert out["imported"][0]["file_name"] == "doc.docx"


def test_scan_folder_idempotent(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "grok_doc.md").write_text("once")
    out1 = scan_folder(inbox, state_root=tmp_path)
    assert out1["n_imported"] == 1
    out2 = scan_folder(inbox, state_root=tmp_path)
    assert out2["n_imported"] == 0
    assert out2["n_skipped"] == 1


def test_scan_folder_creates_folder_if_missing(tmp_path):
    folder = tmp_path / "inbox"  # doesn't exist
    out = scan_folder(folder, state_root=tmp_path)
    assert out["ok"] is True
    assert folder.exists()
    assert out["n_imported"] == 0


def test_scan_folder_rejects_non_directory(tmp_path):
    """Pointing scan at a file should return ok=False."""
    f = tmp_path / "afile.txt"
    f.write_text("x")
    out = scan_folder(f, state_root=tmp_path)
    assert out["ok"] is False


# ── File-type taxonomy ───────────────────────────────────────────

@pytest.mark.parametrize("name,expected_type", [
    ("a.docx", "docx"),
    ("a.pdf", "pdf"),
    ("a.pptx", "pptx"),
    ("a.xlsx", "xlsx"),
    ("a.md", "md"),
    ("a.txt", "txt"),
    ("a.bin", "other"),
    ("a.gif", "other"),
])
def test_file_type_taxonomy(name, expected_type, tmp_path):
    f = tmp_path / name
    f.write_bytes(b"x")
    out = import_one(f, source="claude", state_root=tmp_path)
    assert out["file_type"] == expected_type


def test_supported_suffixes_includes_paper_artifact_formats():
    """The architect specifically asked for docx/pdf/pptx/xlsx + md."""
    for suffix in (".docx", ".pdf", ".pptx", ".xlsx", ".md", ".txt"):
        assert suffix in SUPPORTED_SUFFIXES


# ── Read API ──────────────────────────────────────────────────────

def test_list_recent_imports_returns_newest_first(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    # Spawn 3 distinct files with different sha256
    for i, name in enumerate(["grok_a.md", "claude_b.md", "chatgpt_c.md"]):
        (inbox / name).write_text(f"content-{i}")
    scan_folder(inbox, state_root=tmp_path)
    recent = list_recent_imports(state_root=tmp_path, last_n=3)
    assert len(recent) == 3
    # Sorted by ts desc — last one written should be first
    ts_values = [float(r.get("ts") or 0) for r in recent]
    assert ts_values == sorted(ts_values, reverse=True)


def test_list_recent_imports_empty_when_no_ledger(tmp_path):
    out = list_recent_imports(state_root=tmp_path / "missing")
    assert out == []


def test_find_by_sha256_full_match(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("findme")
    out = import_one(f, source="grok", state_root=tmp_path)
    found = find_by_sha256(out["sha256"], state_root=tmp_path)
    assert found is not None
    assert found["sha256"] == out["sha256"]


def test_find_by_sha256_prefix_match(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("findme-prefix")
    out = import_one(f, source="grok", state_root=tmp_path)
    found = find_by_sha256(out["sha256"][:12], state_root=tmp_path)
    assert found is not None
    assert found["sha256"] == out["sha256"]


def test_find_by_sha256_missing_returns_none(tmp_path):
    found = find_by_sha256("deadbeef" * 8, state_root=tmp_path)
    assert found is None


# ── Truth-class discipline ────────────────────────────────────────

def test_every_import_row_carries_truth_label(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("x")
    out = import_one(f, source="claude", state_root=tmp_path)
    assert out["truth_label"] == TRUTH_LABEL
    assert out["truth_class"] == "OPERATIONAL"


def test_truth_boundary_forbids_social_frame_violation():
    """§6 social frame: Alice may NOT claim she 'called Grok'."""
    from System.swarm_external_artifact_bridge import TRUTH_BOUNDARY
    assert "§6" in TRUTH_BOUNDARY
    assert "social frame" in TRUTH_BOUNDARY
    assert "called" in TRUTH_BOUNDARY.lower() or "claim" in TRUTH_BOUNDARY.lower()
