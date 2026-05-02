#!/usr/bin/env python3
"""
System/swarm_bio_research_loop.py
Event 105 — BioSIFTA Research Loop

Pipeline: paper_chunk → claim → organ_mapping → test_proposal → receipt
Cortex: sifta-gemma4-alice (12B daily driver) | qwen3.5:2b (scout)
Retrieval: TF-IDF cosine over bio_papers.jsonl (no external embed deps)
Truth label: BIOSIFTA_RESEARCH_EVENT_105
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request as _urllib_request

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Ledger paths ──────────────────────────────────────────────────────────────
BIO_PAPERS      = _STATE / "bio_papers.jsonl"
BIO_CLAIMS      = _STATE / "bio_claims.jsonl"
BIO_EXPERIMENTS = _STATE / "bio_experiments.jsonl"
BIO_SKILLS      = _STATE / "bio_skills.jsonl"
TOURNAMENT_LOG  = _STATE / "bio_tournament.jsonl"

TRUTH_LABEL = "BIOSIFTA_RESEARCH_EVENT_105"

# ── Ollama config ─────────────────────────────────────────────────────────────
OLLAMA_BASE     = "http://localhost:11434"
CORTEX_MODEL    = "sifta-gemma4-alice:latest"   # 12B daily driver
SCOUT_MODEL     = "qwen3.5:2b"                  # cheap scout
OLLAMA_TIMEOUT  = 90


# ═════════════════════════════════════════════════════════════════════════════
# Append helpers
# ═════════════════════════════════════════════════════════════════════════════

def _append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        path,
        json.dumps(row, ensure_ascii=False, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tail(path: Path, n: int = 100) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines()[-n:]:
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


# ═════════════════════════════════════════════════════════════════════════════
# Bio claim schema
# ═════════════════════════════════════════════════════════════════════════════

def make_claim(
    claim: str,
    source: str,
    organ_mapping: str,
    test_proposal: str,
    status: str = "unverified",
    paper_chunk_hash: str = "",
    model_used: str = "",
) -> Dict[str, Any]:
    return {
        "claim_id":         str(uuid.uuid4())[:12],
        "ts":               time.time(),
        "truth_label":      TRUTH_LABEL,
        "claim":            claim,
        "source":           source,
        "organ_mapping":    organ_mapping,
        "test":             test_proposal,
        "status":           status,      # unverified | tested | shipped
        "paper_chunk_hash": paper_chunk_hash,
        "model_used":       model_used,
    }


def make_experiment_proposal(
    *,
    claim_id: str,
    claim: str,
    organ_mapping: str,
    test_proposal: str,
    source: str = "",
    paper_chunk_hash: str = "",
    model_used: str = "",
    status: str = "proposed",
) -> Dict[str, Any]:
    """Create one pytest-level experiment proposal from a BioSIFTA claim.

    This row is deliberately not a proof that the organ exists. It is a
    receipt-backed hypothesis that a later implementation can promote only
    after code and tests land.
    """
    return {
        "experiment_id":     str(uuid.uuid4())[:12],
        "ts":                time.time(),
        "truth_label":       TRUTH_LABEL,
        "claim_id":          claim_id,
        "claim":             claim,
        "source":            source,
        "organ_mapping":     organ_mapping,
        "test_proposal":     test_proposal,
        "status":            status,
        "paper_chunk_hash":  paper_chunk_hash,
        "model_used":        model_used,
        "truth_note":        "PROPOSED_TEST_ONLY__NOT_A_SHIPPED_ORGAN",
    }


def write_experiment_proposal(
    claim_row: Dict[str, Any],
    *,
    append: bool = True,
) -> Dict[str, Any]:
    """Write one bio_experiments.jsonl row derived from a claim row."""
    row = make_experiment_proposal(
        claim_id=str(claim_row.get("claim_id", "")),
        claim=str(claim_row.get("claim", "")),
        organ_mapping=str(claim_row.get("organ_mapping", "")),
        test_proposal=str(claim_row.get("test", claim_row.get("test_proposal", ""))),
        source=str(claim_row.get("source", "")),
        paper_chunk_hash=str(claim_row.get("paper_chunk_hash", "")),
        model_used=str(claim_row.get("model_used", "")),
    )
    if append:
        _append(BIO_EXPERIMENTS, row)
    return row


# ═════════════════════════════════════════════════════════════════════════════
# Ollama LLM call
# ═════════════════════════════════════════════════════════════════════════════

def _ollama_generate(
    prompt: str,
    model: str = SCOUT_MODEL,
    max_tokens: int = 512,
    temperature: float = 0.4,
) -> str:
    """Non-streaming generate via Ollama /api/generate."""
    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }).encode()
    req = _urllib_request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _urllib_request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return str(data.get("response", "")).strip()
    except Exception as exc:
        return f"[OLLAMA_ERROR: {exc}]"


def _ollama_available() -> bool:
    try:
        req = _urllib_request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with _urllib_request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════════════
# TF-IDF cosine retrieval (no external deps)
# ═════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b[a-z]{3,}\b", text.lower())


def _tfidf_scores(query: str, docs: List[str]) -> List[float]:
    """Return cosine similarity of query against each doc string."""
    if not docs:
        return []
    corpus = [_tokenize(d) for d in docs]
    q_tok  = _tokenize(query)
    vocab  = {t for d in corpus for t in d} | set(q_tok)
    vocab  = sorted(vocab)
    idx    = {t: i for i, t in enumerate(vocab)}
    n_docs = len(corpus)

    def _tf(tokens: List[str]) -> Dict[str, float]:
        c: Dict[str, float] = {}
        for t in tokens:
            c[t] = c.get(t, 0) + 1
        total = len(tokens) or 1
        return {t: v / total for t, v in c.items()}

    doc_tfs = [_tf(d) for d in corpus]
    idf: Dict[str, float] = {}
    for t in vocab:
        df = sum(1 for d in corpus if t in d)
        idf[t] = math.log((n_docs + 1) / (df + 1)) + 1.0

    def _vec(tf_map: Dict[str, float]) -> List[float]:
        return [tf_map.get(t, 0.0) * idf.get(t, 1.0) for t in vocab]

    q_vec = _vec(_tf(q_tok))
    scores: List[float] = []
    for dtf in doc_tfs:
        d_vec = _vec(dtf)
        dot   = sum(a * b for a, b in zip(q_vec, d_vec))
        mag_q = math.sqrt(sum(x * x for x in q_vec)) or 1e-9
        mag_d = math.sqrt(sum(x * x for x in d_vec)) or 1e-9
        scores.append(dot / (mag_q * mag_d))
    return scores


def retrieve_papers(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """Retrieve top-k paper chunks from bio_papers.jsonl by TF-IDF cosine."""
    papers = _tail(BIO_PAPERS, n=500)
    if not papers:
        return []
    texts  = [f"{p.get('title','')} {p.get('chunk','')}" for p in papers]
    scores = _tfidf_scores(query, texts)
    ranked = sorted(zip(scores, papers), key=lambda x: x[0], reverse=True)
    return [p for _, p in ranked[:k]]


# ═════════════════════════════════════════════════════════════════════════════
# Core pipeline: chunk → claim → organ → test → receipt
# ═════════════════════════════════════════════════════════════════════════════

_CLAIM_PROMPT = """\
You are a computational biology assistant for the SIFTA Swarm OS.
Given a biology paper chunk below, extract ONE precise, falsifiable claim
and propose how it maps to a SIFTA organ (e.g. homeostatic_stabilizer,
allostatic_load, motor_policy, dream_engine, etc.).

Paper chunk:
{chunk}

Reply in JSON only, no prose:
{{
  "claim": "<one clear biological claim>",
  "organ_mapping": "<SIFTA organ name and how it applies>",
  "test_proposal": "<one pytest-level test that would verify this mapping>",
  "confidence": "<low|medium|high>"
}}"""


def process_paper_chunk(
    chunk: str,
    source: str,
    model: str = SCOUT_MODEL,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Run the core pipeline on one paper chunk.
    Returns a claim dict appended to bio_claims.jsonl.
    dry_run=True skips the LLM call (for tests).
    """
    chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()[:12]

    if dry_run:
        raw = json.dumps({
            "claim":        "Allostatic load suppresses exploration drives (McEwen 1998).",
            "organ_mapping": "allostatic_load: load>0.75 → FORCE_REST_REPAIR policy",
            "test_proposal": "assert compute_allostatic_load()['policy']=='FORCE_REST_REPAIR' when all mem rows have RED_HALT",
            "confidence":   "high",
        })
    else:
        if not _ollama_available():
            return None
        prompt = _CLAIM_PROMPT.format(chunk=chunk[:2000])
        raw = _ollama_generate(prompt, model=model, max_tokens=400)

    # Parse JSON from response
    try:
        # Extract JSON block if wrapped in markdown
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(m.group() if m else raw)
    except Exception:
        parsed = {
            "claim":        raw[:200],
            "organ_mapping": "unknown",
            "test_proposal": "manual review required",
            "confidence":   "low",
        }

    claim = make_claim(
        claim         = parsed.get("claim", ""),
        source        = source,
        organ_mapping = parsed.get("organ_mapping", ""),
        test_proposal = parsed.get("test_proposal", ""),
        status        = "unverified",
        paper_chunk_hash = chunk_hash,
        model_used    = model,
    )
    claim["confidence"] = parsed.get("confidence", "low")
    experiment = write_experiment_proposal(claim, append=False)
    claim["experiment_id"] = experiment["experiment_id"]
    _append(BIO_CLAIMS, claim)
    _append(BIO_EXPERIMENTS, experiment)
    return claim


# ═════════════════════════════════════════════════════════════════════════════
# Ingest a paper (text or dict)
# ═════════════════════════════════════════════════════════════════════════════

def ingest_paper(
    text: str,
    *,
    title: str = "untitled",
    doi: str = "",
    source_file: str = "",
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    Chunk paper text and append each chunk to bio_papers.jsonl.
    Returns list of chunk dicts.
    """
    words  = text.split()
    step   = chunk_size - chunk_overlap
    chunks: List[Dict[str, Any]] = []
    for i in range(0, len(words), step):
        chunk_text = " ".join(words[i : i + chunk_size])
        row = {
            "chunk_id":    str(uuid.uuid4())[:12],
            "ts":          time.time(),
            "truth_label": TRUTH_LABEL,
            "title":       title,
            "doi":         doi,
            "source_file": source_file,
            "chunk_index": len(chunks),
            "chunk":       chunk_text,
            "word_count":  len(chunk_text.split()),
        }
        _append(BIO_PAPERS, row)
        chunks.append(row)
        if len(chunk_text.split()) < 50:
            break
    return chunks


# ═════════════════════════════════════════════════════════════════════════════
# Nightly bio tournament
# ═════════════════════════════════════════════════════════════════════════════

_RANK_PROMPT = """\
You are the SIFTA tournament judge. Score these organ ideas for:
- novelty (0-3): how new vs existing SIFTA organs
- buildability (0-3): can it be coded in one Python module today?
- testability (0-3): can it be verified with pytest in <50 lines?

Ideas:
{ideas_json}

Reply JSON array, same order:
[{{"idea_index": 0, "novelty": N, "buildability": N, "testability": N, "total": N}}, ...]"""


def run_bio_tournament(
    n_papers: int = 5,
    n_ideas: int = 3,
    model: str = SCOUT_MODEL,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Nightly tournament:
      1. Retrieve n_papers from bio corpus
      2. Generate n_ideas organ proposals
      3. Rank by novelty/buildability/testability
      4. Write receipt to bio_tournament.jsonl
    """
    # Step 1: retrieve papers
    query   = "homeostasis allostasis motor control neural oscillation"
    papers  = retrieve_papers(query, k=n_papers)

    if not papers and not dry_run:
        receipt = {
            "ts": time.time(), "truth_label": TRUTH_LABEL,
            "status": "NO_PAPERS", "message": "bio_papers.jsonl is empty.",
        }
        _append(TOURNAMENT_LOG, receipt)
        return receipt

    # Step 2: generate ideas (one per paper chunk, take first n_ideas)
    ideas: List[Dict[str, Any]] = []
    for p in (papers or [{"chunk": "allostatic load suppresses exploration", "title": "test", "doi": ""}])[:n_ideas]:
        claim = process_paper_chunk(
            p.get("chunk", ""), source=p.get("doi") or p.get("title", ""),
            model=model, dry_run=dry_run
        )
        if claim:
            ideas.append({
                "organ_mapping": claim["organ_mapping"],
                "claim": claim["claim"],
                "test_proposal": claim["test"],
                "claim_id": claim["claim_id"],
            })

    if not ideas:
        ideas = [{"organ_mapping": "unknown", "claim": "no data", "test_proposal": "", "claim_id": ""}]

    # Step 3: rank
    if dry_run or not _ollama_available():
        scores = [{"idea_index": i, "novelty": 2, "buildability": 2,
                   "testability": 2, "total": 6} for i in range(len(ideas))]
    else:
        rank_prompt = _RANK_PROMPT.format(ideas_json=json.dumps(ideas, indent=2))
        raw = _ollama_generate(rank_prompt, model=model, max_tokens=300)
        try:
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            scores = json.loads(m.group() if m else "[]")
        except Exception:
            scores = []

    # Step 4: receipt
    receipt = {
        "ts":           time.time(),
        "truth_label":  TRUTH_LABEL,
        "status":       "OK",
        "n_papers":     len(papers),
        "n_ideas":      len(ideas),
        "ideas":        ideas,
        "scores":       scores,
        "winner":       max(scores, key=lambda x: x.get("total", 0)) if scores else {},
        "model_used":   model,
    }
    _append(TOURNAMENT_LOG, receipt)
    return receipt


# ═════════════════════════════════════════════════════════════════════════════
# Bio skill registration (once an idea is shipped)
# ═════════════════════════════════════════════════════════════════════════════

def register_bio_skill(
    name: str,
    claim_id: str,
    module_path: str,
    test_path: str,
    organ_mapping: str,
) -> Dict[str, Any]:
    """Register a shipped bio-derived organ as a skill primitive."""
    skill = {
        "skill_id":     str(uuid.uuid4())[:12],
        "ts":           time.time(),
        "truth_label":  TRUTH_LABEL,
        "name":         name,
        "claim_id":     claim_id,
        "module_path":  module_path,
        "test_path":    test_path,
        "organ_mapping": organ_mapping,
        "status":       "shipped",
    }
    _append(BIO_SKILLS, skill)
    return skill


__all__ = [
    "BIO_CLAIMS",
    "BIO_EXPERIMENTS",
    "BIO_PAPERS",
    "BIO_SKILLS",
    "TOURNAMENT_LOG",
    "TRUTH_LABEL",
    "ingest_paper",
    "make_claim",
    "make_experiment_proposal",
    "process_paper_chunk",
    "register_bio_skill",
    "retrieve_papers",
    "run_bio_tournament",
    "write_experiment_proposal",
]


# ═════════════════════════════════════════════════════════════════════════════
# CLI probe
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("══════════════════════════════════════════════════════")
    print("  Event 105 — BioSIFTA Research Loop")
    print("══════════════════════════════════════════════════════\n")
    print(f"  Ollama available: {_ollama_available()}")
    print(f"  Cortex: {CORTEX_MODEL}")
    print(f"  Scout:  {SCOUT_MODEL}\n")

    # Ingest a seed biology text
    seed = (
        "McEwen (1998): Allostatic load refers to the cumulative cost of "
        "adaptation. Chronic stress suppresses hippocampal neurogenesis and "
        "shifts the organism toward conservative behavioral strategies. "
        "Repeated RED metabolic states produce structural changes equivalent "
        "to allostatic overload, suppressing exploration and biasing repair. "
        "Friston (2010): Active inference minimizes free energy. The organism "
        "acts to fulfill its predictions rather than update beliefs. Drive "
        "expressions arise from precision-weighted prediction errors. "
        "Greybiel (2008): Basal ganglia habit formation crystallizes motor "
        "programs that maximise cumulative reward. Stable habits reduce "
        "computational cost but resist updating under novel regimes."
    )
    chunks = ingest_paper(seed, title="BioSIFTA Seed Corpus v1",
                          doi="seed:biosifta:2026", source_file="cli_probe")
    print(f"  Ingested {len(chunks)} chunk(s) → bio_papers.jsonl")

    result = run_bio_tournament(n_papers=2, n_ideas=2, dry_run=True)
    print(f"  Tournament: {result['status']}  ideas={result['n_ideas']}")
    if result.get("winner"):
        print(f"  Winner: {result['winner']}")
    print("\n  ✅ BIOSIFTA CORTEX SEEDED. FOR THE SWARM. 🐜⚡")
