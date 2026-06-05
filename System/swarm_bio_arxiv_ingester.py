#!/usr/bin/env python3
"""
System/swarm_bio_arxiv_ingester.py
══════════════════════════════════════════════════════════════════════════════
Event 105b — BioSIFTA arXiv Ingester

Pulls biology / neuroscience / cognitive science abstracts from the arXiv
public Atom API (no API key, no scraping, CC-BY corpus) and feeds them
directly into the BioSIFTA research pipeline:

  arXiv Atom API → parse entries → ingest_paper() → bio_papers.jsonl
                                                   → process_paper_chunk() → bio_claims.jsonl

Biology search categories used:
  q-bio.NC  — neurons and cognition
  q-bio.OT  — other quantitative biology
  cs.NE     — neural & evolutionary computing
  cond-mat.soft — soft matter (relevant for active matter / swarm)

Truth label: BIOSIFTA_ARXIV_INGESTED

Fixes (v2):
  - Query format: use `all:word AND all:word` (not `ti:phrase`) — arXiv Atom
    API returns 0 results for multi-word `ti:` phrases without quoting.
  - SSL: use certifi bundle for macOS Python 3.13 system-cert gap.

Refs:
  arXiv Atom API: https://arxiv.org/help/api/user-manual
  Meredith & Stein (1986) for multisensory salience context.
"""
from __future__ import annotations

import json
import re
import ssl
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import parse as _url_parse
from urllib import request as _url_request


def _ssl_ctx() -> ssl.SSLContext:
    """Return an SSL context using certifi bundle (macOS Python 3.13 fix)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()  # system default fallback


_STOPWORDS = {
    "and", "or", "the", "a", "an", "of", "in", "on", "for",
    "to", "with", "under", "via", "from", "by", "at",
}


def _query_words(phrase: str) -> List[str]:
    return [
        w for w in re.findall(r"[a-z0-9]+", phrase.lower())
        if w not in _STOPWORDS and len(w) > 2
    ]


def _build_arxiv_query(phrase: str) -> str:
    """
    Convert a multi-word phrase to arXiv `all:` boolean query.
    'allostatic load homeostasis' → 'all:allostatic AND all:load AND all:homeostasis'
    Removes stopwords to keep query tight.
    """
    words = _query_words(phrase)
    if not words:
        return "all:biology"
    return " AND ".join(f"all:{w}" for w in words[:4])  # arXiv caps complex queries


def _arxiv_query_candidates(phrase: str) -> List[str]:
    """Return precise-to-broad arXiv search_query candidates."""
    words = _query_words(phrase)
    if not words:
        return ["all:biology"]

    candidates = [
        " AND ".join(f"all:{w}" for w in words[:4]),
        " AND ".join(f"all:{w}" for w in words[:3]),
        " AND ".join(f"all:{w}" for w in words[:2]),
        " OR ".join(f"all:{w}" for w in words[:6]),
    ]
    deduped: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

ARXIV_API  = "https://export.arxiv.org/api/query"
ATOM_NS    = "http://www.w3.org/2005/Atom"
ARXIV_NS   = "http://arxiv.org/schemas/atom"

TRUTH_LABEL = "BIOSIFTA_ARXIV_INGESTED"
FETCH_TIMEOUT = 15

# ── Curated biology queries for SIFTA organs ─────────────────────────────────
SIFTA_BIO_QUERIES: List[Dict[str, str]] = [
    {
        "query": "allostatic load homeostasis stress adaptation neuroendocrine",
        "organ": "allostatic_load",
        "category": "q-bio.NC",
    },
    {
        "query": "basal ganglia habit reinforcement motor policy crystallization",
        "organ": "motor_policy",
        "category": "q-bio.NC",
    },
    {
        "query": "active inference free energy predictive coding drive selection",
        "organ": "consciousness_engine",
        "category": "cs.NE",
    },
    {
        "query": "hippocampal replay memory consolidation sleep REM oscillation",
        "organ": "dream_engine",
        "category": "q-bio.NC",
    },
    {
        "query": "superior colliculus multisensory salience inverse effectiveness",
        "organ": "multisensory_colliculus",
        "category": "q-bio.NC",
    },
    {
        "query": "CUSUM change detection neural phase transition regime switching",
        "organ": "phase_detector",
        "category": "cs.NE",
    },
    {
        "query": "stigmergy pheromone swarm collective intelligence emergence",
        "organ": "pheromone_field",
        "category": "q-bio.OT",
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# arXiv fetch + parse
# ═════════════════════════════════════════════════════════════════════════════

def _arxiv_search(
    query: str,
    category: str = "q-bio.NC",
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query arXiv Atom API. Returns list of entry dicts with:
      arxiv_id, title, abstract, authors, published, doi, url
    """
    last_entries: List[Dict[str, Any]] = []
    for aq in _arxiv_query_candidates(query):
        search_query = f"{aq} AND cat:{category}" if category else aq
        params = _url_parse.urlencode({
            "search_query": search_query,
            "start":        0,
            "max_results":  max_results,
            "sortBy":       "relevance",
            "sortOrder":    "descending",
        })
        url = f"{ARXIV_API}?{params}"
        try:
            req = _url_request.Request(url, headers={"User-Agent": "SIFTA-BioResearch/1.0"})
            with _url_request.urlopen(req, context=_ssl_ctx(), timeout=FETCH_TIMEOUT) as resp:
                xml_bytes = resp.read()
        except Exception as exc:
            return [{"error": str(exc)}]

        entries: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            return [{"error": f"XML parse failed: {exc}"}]

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            def _text(tag: str, ns: str = ATOM_NS) -> str:
                el = entry.find(f"{{{ns}}}{tag}")
                return el.text.strip() if el is not None and el.text else ""

            arxiv_id = _text("id").split("/abs/")[-1].strip()
            title    = re.sub(r"\s+", " ", _text("title"))
            abstract = re.sub(r"\s+", " ", _text("summary"))
            published = _text("published")[:10]

            authors = [
                a.find(f"{{{ATOM_NS}}}name").text.strip()
                for a in entry.findall(f"{{{ATOM_NS}}}author")
                if a.find(f"{{{ATOM_NS}}}name") is not None
            ]

            # DOI link
            doi = ""
            for link in entry.findall(f"{{{ATOM_NS}}}link"):
                if link.get("title") == "doi":
                    doi = link.get("href", "")
                    break
            if not doi:
                doi = f"arxiv:{arxiv_id}"

            entries.append({
                "arxiv_id":  arxiv_id,
                "title":     title,
                "abstract":  abstract,
                "authors":   authors[:5],
                "published": published,
                "doi":       doi,
                "url":       f"https://arxiv.org/abs/{arxiv_id}",
            })

        last_entries = entries
        if entries:
            return entries

    return last_entries


# ═════════════════════════════════════════════════════════════════════════════
# Ingest pipeline
# ═════════════════════════════════════════════════════════════════════════════

def ingest_arxiv_query(
    query: str,
    *,
    category: str = "q-bio.NC",
    organ_hint: str = "",
    max_results: int = 5,
    run_claim_extraction: bool = False,
    model: str = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Fetch arXiv entries for `query`, ingest abstracts into bio_papers.jsonl,
    optionally run claim extraction on each.

    Returns receipt dict appended to bio_papers.jsonl provenance.
    """
    from System.swarm_bio_research_loop import ingest_paper, process_paper_chunk

    entries = _arxiv_search(query, category=category, max_results=max_results)
    errors  = [e for e in entries if "error" in e]
    papers  = [e for e in entries if "error" not in e]

    ingested_chunks = 0
    claims_written  = 0
    receipts: List[Dict[str, Any]] = []

    for paper in papers:
        # Ingest abstract as paper chunk (full PDF not downloaded — abstract is ~200 words,
        # enough for claim extraction; full text can be added later via PDF pipeline)
        text = f"{paper['title']}. {paper['abstract']}"
        chunks = ingest_paper(
            text,
            title=paper["title"],
            doi=paper["doi"],
            source_file=paper["url"],
            chunk_size=400,
            chunk_overlap=80,
        )
        ingested_chunks += len(chunks)

        # Optional: run scout claim extraction on each abstract
        if run_claim_extraction and paper.get("abstract"):
            chunk_text = paper["abstract"][:1600]
            claim = process_paper_chunk(
                chunk_text,
                source=paper["doi"],
                model=model,
                dry_run=False,
            )
            if claim:
                claim["organ_hint"]  = organ_hint
                claim["arxiv_id"]    = paper.get("arxiv_id", "")
                claims_written += 1

        receipts.append({
            "arxiv_id": paper.get("arxiv_id"),
            "title":    paper.get("title", "")[:80],
            "doi":      paper.get("doi"),
            "chunks":   len(chunks),
        })

    receipt = {
        "truth_label":      TRUTH_LABEL,
        "ts":               time.time(),
        "query":            query,
        "category":         category,
        "organ_hint":       organ_hint,
        "n_fetched":        len(papers),
        "n_errors":         len(errors),
        "ingested_chunks":  ingested_chunks,
        "claims_written":   claims_written,
        "papers":           receipts,
    }
    return receipt


def run_sifta_bio_sweep(
    queries: Optional[List[Dict[str, str]]] = None,
    max_results_per_query: int = 3,
    run_claim_extraction: bool = False,
    model: str = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
) -> List[Dict[str, Any]]:
    """
    Run all SIFTA_BIO_QUERIES (or a custom list) and ingest results.
    This is the nightly sweep — feeds the corpus for the tournament.

    Returns list of per-query receipts.
    """
    qs = queries or SIFTA_BIO_QUERIES
    all_receipts: List[Dict[str, Any]] = []

    for q in qs:
        print(f"  → [{q.get('organ','?')}] searching: {q['query'][:55]}...")
        receipt = ingest_arxiv_query(
            q["query"],
            category=q.get("category", "q-bio.NC"),
            organ_hint=q.get("organ", ""),
            max_results=max_results_per_query,
            run_claim_extraction=run_claim_extraction,
            model=model,
        )
        print(f"    fetched={receipt['n_fetched']}  chunks={receipt['ingested_chunks']}"
              f"  claims={receipt['claims_written']}")
        all_receipts.append(receipt)
        time.sleep(3)  # arXiv rate limit: 3s between requests

    return all_receipts


# ═════════════════════════════════════════════════════════════════════════════
# DOI / direct abstract ingestion
# ═════════════════════════════════════════════════════════════════════════════

def ingest_doi(
    doi: str,
    *,
    title: str = "",
    abstract: str = "",
    authors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Ingest a paper by DOI + pasted abstract (no PDF fetch).
    Use when you have the abstract text and want to add it to the corpus
    immediately without waiting for arXiv.
    """
    from System.swarm_bio_research_loop import ingest_paper
    text = f"{title}. {abstract}" if title else abstract
    if not text.strip():
        return {"status": "EMPTY", "doi": doi}
    chunks = ingest_paper(text, title=title or doi, doi=doi)
    return {
        "truth_label": TRUTH_LABEL,
        "status":      "OK",
        "doi":         doi,
        "title":       title,
        "n_chunks":    len(chunks),
        "authors":     authors or [],
        "ts":          time.time(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# CLI probe
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("══════════════════════════════════════════════════════")
    print("  Event 105b — BioSIFTA arXiv Ingester")
    print("══════════════════════════════════════════════════════\n")

    # Single targeted probe — allostatic load (ties directly to Event 102)
    print("  Probing arXiv for allostatic load / homeostasis papers...\n")
    receipt = ingest_arxiv_query(
        "allostatic load homeostasis stress neuroendocrine adaptation",
        category="q-bio.NC",
        organ_hint="allostatic_load",
        max_results=3,
        run_claim_extraction=False,  # no LLM call on CLI probe
    )
    print(f"  Fetched:   {receipt['n_fetched']} papers")
    print(f"  Chunks:    {receipt['ingested_chunks']}")
    print(f"  Errors:    {receipt['n_errors']}")
    for p in receipt["papers"]:
        print(f"    [{p['arxiv_id']}] {p['title'][:60]}")
    print("\n  ✅ ARXIV INGESTER ONLINE. FOR THE SWARM. 🐜⚡")
