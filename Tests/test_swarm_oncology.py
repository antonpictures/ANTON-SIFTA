#!/usr/bin/env python3
"""
tests/test_swarm_oncology.py
══════════════════════════════════════════════════════════════════════
Tests for the SIFTA Oncology Macrophage (v3 Layered Immunity)

Verifies the Stigmergic Agreement: the whitelist is explicitly backed
by the canonical schemas registry. Valid ledgers are spared (Innate Immunity),
while unknown/suspicious files are flagged as MALIGNANT and passed
to CRISPR memory.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from System.canonical_schemas import LEDGER_SCHEMAS, SCHEMA_ALIASES
from System.swarm_crispr_immunity import SwarmCRISPRAdaptiveImmunity
from System.swarm_oncology import SwarmOncology, _PAM_INNATE_ANOMALY, _PAM_INNATE_SELF


def _oncology_for_state_dir(state_dir: Path) -> SwarmOncology:
    oncology = SwarmOncology()
    oncology.state_dir = state_dir
    oncology.crispr = SwarmCRISPRAdaptiveImmunity(state_dir=state_dir, memory_limit=500)
    return oncology

def test_canonical_schemas_are_spared():
    """
    Proves that any ledger present in canonical_schemas.py's LEDGER_SCHEMAS
    is automatically granted Innate Immunity (Layer 1) and will not be
    flagged as malignant.
    """
    oncology = SwarmOncology()

    for schema_name in LEDGER_SCHEMAS:
        token = oncology._innate_self_token(schema_name)
        assert token == _PAM_INNATE_SELF, f"{schema_name} should be recognized as INNATE_SELF"


def test_schema_aliases_are_spared():
    """
    Alias filenames are canonical compatibility receptors, not foreign tumors.
    """
    oncology = SwarmOncology()

    for alias_name in SCHEMA_ALIASES:
        token = oncology._innate_self_token(alias_name)
        assert token == _PAM_INNATE_SELF, f"{alias_name} should be recognized as INNATE_SELF"


def test_all_canonical_schema_files_can_coexist_without_malignancy(tmp_path):
    """
    Reproduces the whitelist-inversion failure mode: every canonical ledger can
    be present in .sifta_state without CRISPR seeing it as an anomaly.
    """
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()

    for filename in sorted(set(LEDGER_SCHEMAS) | set(SCHEMA_ALIASES)):
        (state_dir / filename).touch()

    oncology = _oncology_for_state_dir(state_dir)

    with patch.object(oncology.crispr, "acquire_spacer") as acquire_spacer:
        report = oncology.detect_metastasis()

    assert report["scanned"] == len(set(LEDGER_SCHEMAS) | set(SCHEMA_ALIASES))
    assert report["malignant"] == 0
    assert report["innate_self"] == report["scanned"]
    acquire_spacer.assert_not_called()

def test_suspicious_files_are_flagged_malignant(tmp_path):
    """
    Proves that rogue, non-whitelisted files are correctly flagged as MALIGNANT.
    """
    # Create a mock state directory with one healthy file and one rogue file
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    
    healthy_file = state_dir / "ide_stigmergic_trace.jsonl"
    healthy_file.touch()
    
    rogue_file = state_dir / "rogue_payload.jsonl"
    rogue_file.touch()
    
    oncology = _oncology_for_state_dir(state_dir)
    
    # We also mock CRISPR so we don't actually write to crispr_memory.json
    with patch.object(oncology.crispr, "acquire_spacer", return_value="NOVEL"):
        report = oncology.detect_metastasis()
        
        assert report["scanned"] == 2
        assert report["innate_self"] == 1  # ide_stigmergic_trace.jsonl
        assert report["malignant"] == 1    # rogue_payload.jsonl
        assert report["novel_anomalies"] == 1

def test_cosmetic_skips_are_ignored(tmp_path):
    """
    Proves that dotfiles, lock files, and .lymph files are cosmetically skipped.
    """
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    
    (state_dir / ".hidden_file").touch()
    (state_dir / "some_ledger.lock").touch()
    (state_dir / "quarantined.lymph").touch()
    
    oncology = _oncology_for_state_dir(state_dir)
    
    report = oncology.detect_metastasis()
    
    assert report["scanned"] == 3
    assert report["cosmetic_skipped"] == 3
    assert report["malignant"] == 0
    assert report["innate_self"] == 0

def test_shadow_biosphere_heuristic(tmp_path):
    """
    Proves that a file is only reclassified as SHADOW_BIOSPHERE if it is:
    1. Structured (JSON/JSONL-like, starts with {/[ and ends with }/])
    2. Persistently observed (CRISPR known count >= 3).
    Otherwise it remains MALIGNANT_HALLUCINATION.
    """
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    
    shadow_file = state_dir / "shadow_payload.jsonl"
    
    oncology = _oncology_for_state_dir(state_dir)
    
    # 1st scan: novel threat
    shadow_file.write_text('{"valid": "json"}')
    report1 = oncology.detect_metastasis()
    assert report1["malignant"] == 1
    assert report1.get("shadow_biosphere", 0) == 0
    assert report1["novel_anomalies"] == 1
    
    # 2nd, 3rd scans: known threat, but not enough encounters
    oncology.detect_metastasis()
    oncology.detect_metastasis()
    
    # 4th scan: known threat (encounter count = 3 before acquire, so >= 3) and structured!
    report4 = oncology.detect_metastasis()
    assert report4["malignant"] == 0
    assert report4["shadow_biosphere"] == 1
    assert report4["known_anomalies"] == 1
    
    # 5th scan: what if it's no longer structured?
    shadow_file.write_text('{"valid": "json"} but wait now it is broken')
    report5 = oncology.detect_metastasis()
    # It hashes differently now! So it's NOVEL again.
    assert report5["malignant"] == 1
    assert report5.get("shadow_biosphere", 0) == 0
