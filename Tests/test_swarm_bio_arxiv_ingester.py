#!/usr/bin/env python3
"""
tests/test_swarm_bio_arxiv_ingester.py
Event 105b — arXiv Ingester test suite.
Uses mocked HTTP to avoid network calls in CI.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# ── Minimal Atom XML fixture ──────────────────────────────────────────────────

_ATOM_ENTRY = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>arXiv Query Results</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Allostatic Load and Hippocampal Neurogenesis Under Chronic Stress</title>
    <summary>Chronic stress elevates allostatic load, suppressing hippocampal
    neurogenesis via glucocorticoid excess. We propose a homeostatic gating
    mechanism that shifts behavioral policy from exploration to repair.</summary>
    <author><name>A. McEwen</name></author>
    <published>2024-01-01T00:00:00Z</published>
    <link title="doi" href="https://doi.org/10.0001/test.2401"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Basal Ganglia Habit Crystallization Under Reward Schedules</title>
    <summary>Basal ganglia loops crystallize motor programs that maximize
    cumulative reward. Regime transitions modulate habit strength via dopamine
    prediction error signals, paralleling CUSUM phase detection.</summary>
    <author><name>B. Greybiel</name></author>
    <published>2024-01-02T00:00:00Z</published>
    <link title="doi" href="https://doi.org/10.0001/test.2402"/>
  </entry>
</feed>"""


class _MockResponse:
    def __init__(self, data: bytes):
        self._data = data
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


# ── 1. _arxiv_search parses Atom XML correctly ───────────────────────────────

def test_arxiv_search_parses_entries(monkeypatch):
    import System.swarm_bio_arxiv_ingester as mod
    def _mock_urlopen(req, timeout=None):
        return _MockResponse(_ATOM_ENTRY.encode())
    monkeypatch.setattr(mod._url_request, "urlopen", _mock_urlopen)
    entries = mod._arxiv_search("allostatic load", category="q-bio.NC", max_results=5)
    assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}: {entries}"
    assert entries[0]["title"] == "Allostatic Load and Hippocampal Neurogenesis Under Chronic Stress"
    assert entries[0]["doi"] == "https://doi.org/10.0001/test.2401"
    assert entries[0]["arxiv_id"] == "2401.00001v1"
    assert "A. McEwen" in entries[0]["authors"]


# ── 2. ingest_arxiv_query creates bio_papers.jsonl rows ──────────────────────

def test_ingest_arxiv_query_creates_chunks(tmp_path, monkeypatch):
    import System.swarm_bio_arxiv_ingester as mod
    import System.swarm_bio_research_loop as brl
    # Redirect state paths
    monkeypatch.setattr(brl, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(brl, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(brl, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(brl, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(brl, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")
    def _mock_urlopen(req, timeout=None):
        return _MockResponse(_ATOM_ENTRY.encode())
    monkeypatch.setattr(mod._url_request, "urlopen", _mock_urlopen)

    receipt = mod.ingest_arxiv_query(
        "allostatic load", category="q-bio.NC",
        organ_hint="allostatic_load", max_results=3,
        run_claim_extraction=False,
    )
    assert receipt["truth_label"] == "BIOSIFTA_ARXIV_INGESTED"
    assert receipt["n_fetched"] == 2
    assert receipt["ingested_chunks"] >= 2
    assert receipt["n_errors"] == 0

    rows = [json.loads(l) for l in (tmp_path / "bio_papers.jsonl").read_text().splitlines()]
    assert len(rows) >= 2
    assert any("McEwen" in r.get("title", "") or "Allostatic" in r.get("title", "")
               for r in rows)


# ── 3. ingest_doi direct ingestion ───────────────────────────────────────────

def test_ingest_doi_direct(tmp_path, monkeypatch):
    import System.swarm_bio_arxiv_ingester as mod
    import System.swarm_bio_research_loop as brl
    monkeypatch.setattr(brl, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(brl, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(brl, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(brl, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(brl, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    result = mod.ingest_doi(
        "10.1016/s0896-6273(00)80484-3",
        title="Stress and the Brain: From Adaptation to Disease",
        abstract="Allostasis and allostatic load describe the adaptive and "
                 "maladaptive aspects of the stress response. Chronic stress "
                 "causes structural changes in hippocampus and prefrontal cortex.",
        authors=["B.S. McEwen"],
    )
    assert result["status"] == "OK"
    assert result["n_chunks"] >= 1
    rows = [json.loads(l) for l in (tmp_path / "bio_papers.jsonl").read_text().splitlines()]
    assert any("McEwen" in r.get("title", "") or "allostatic" in r.get("chunk", "").lower()
               for r in rows)


# ── 4. Empty abstract → EMPTY status ─────────────────────────────────────────

def test_ingest_doi_empty_returns_empty(tmp_path, monkeypatch):
    import System.swarm_bio_arxiv_ingester as mod
    import System.swarm_bio_research_loop as brl
    monkeypatch.setattr(brl, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(brl, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(brl, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(brl, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(brl, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")
    result = mod.ingest_doi("10.0000/empty", title="", abstract="")
    assert result["status"] == "EMPTY"


# ── 5. Network error is captured, not raised ──────────────────────────────────

def test_arxiv_search_network_error(monkeypatch):
    import System.swarm_bio_arxiv_ingester as mod
    def _mock_fail(req, timeout=None):
        raise ConnectionError("no network")
    monkeypatch.setattr(mod._url_request, "urlopen", _mock_fail)
    entries = mod._arxiv_search("allostatic load", max_results=3)
    assert len(entries) == 1
    assert "error" in entries[0]
    assert "no network" in entries[0]["error"]


# ── 6. SIFTA_BIO_QUERIES covers all major organs ─────────────────────────────

def test_sifta_bio_queries_cover_organs():
    from System.swarm_bio_arxiv_ingester import SIFTA_BIO_QUERIES
    organs = {q["organ"] for q in SIFTA_BIO_QUERIES}
    required = {"allostatic_load", "motor_policy", "dream_engine",
                "phase_detector", "pheromone_field"}
    missing = required - organs
    assert not missing, f"Missing organ queries: {missing}"


# ── 7. Receipt truth_label and required fields ────────────────────────────────

def test_receipt_schema(monkeypatch, tmp_path):
    import System.swarm_bio_arxiv_ingester as mod
    import System.swarm_bio_research_loop as brl
    monkeypatch.setattr(brl, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(brl, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(brl, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(brl, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(brl, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")
    def _mock_urlopen(req, timeout=None):
        return _MockResponse(_ATOM_ENTRY.encode())
    monkeypatch.setattr(mod._url_request, "urlopen", _mock_urlopen)
    receipt = mod.ingest_arxiv_query("test", max_results=2, run_claim_extraction=False)
    required_keys = {"truth_label", "ts", "query", "n_fetched",
                     "ingested_chunks", "n_errors", "papers"}
    assert required_keys <= receipt.keys()
    assert receipt["truth_label"] == "BIOSIFTA_ARXIV_INGESTED"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
