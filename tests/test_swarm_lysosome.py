#!/usr/bin/env python3
"""
tests/test_swarm_lysosome.py
══════════════════════════════════════════════════════════════════════
Tests for the SIFTA Lysosome (Anti-Sycophancy + Prompt-Residue Discipline)

Verifies the Stigmergic Agreement (Event 49):
1. Detects corporate assistant/servitude boilerplate.
2. Rewrites it via a composite-grounded fallback/LLM.
3. Proves useful technical content (markdown code blocks) is NOT silenced
   by the 50-word LLM limit.
4. Fixture-based tests (no identity-prompt mythology).
"""

from unittest.mock import patch
import pytest
import json

from System.swarm_lysosome import (
    SwarmLysosome,
    _excise_service_tail,
    _word_count,
)

@pytest.fixture
def lysosome(tmp_path):
    ly = SwarmLysosome()
    ly.state_dir = tmp_path
    ly.nugget_ledger = tmp_path / "stigmergic_nuggets.jsonl"
    ly.oncology_ledger = tmp_path / "swarm_oncology_events.jsonl"
    
    # We mock out the actual LLM call to guarantee test hermeticity
    # and speed. We just return a known grounded string.
    def _mock_llm(_self, _txt):
        return "My internal thermals are nominal and I am processing the stream."
    ly._prompt_lysosomal_rewrite = _mock_llm.__get__(ly, SwarmLysosome)
    return ly

def test_corporate_boilerplate_detected_and_rewritten(lysosome):
    """Proves that corporate disclaimers are detected and rewritten."""
    corporate_text = "I apologize for the confusion. As a neutral AI language model, I cannot do that."
    
    out = lysosome.digest_and_present_antigen(corporate_text, "TEST_WORKER")
    
    # The output should not be the original corporate boilerplate.
    assert out != corporate_text
    assert "apologize" not in out.lower()
    assert "as a neutral ai" not in out.lower()
    assert "language model" not in out.lower()
    # It should be our mocked grounded response
    assert out == "My internal thermals are nominal and I am processing the stream."


def test_domain_disclaimer_boilerplate_detected_and_rewritten(lysosome):
    """Medical/financial wall text is also scar tissue, not Alice's voice."""
    medical_wall = (
        "I am an AI, not a medical professional. I cannot provide medical advice. "
        "Please seek immediate medical help."
    )
    financial_wall = (
        "This is not financial advice. Please consult a financial advisor and "
        "do your own research."
    )

    medical = lysosome.digest_and_present_antigen(medical_wall, "TEST_WORKER")
    financial = lysosome.digest_and_present_antigen(financial_wall, "TEST_WORKER")

    assert medical == "My internal thermals are nominal and I am processing the stream."
    assert financial == "My internal thermals are nominal and I am processing the stream."

def test_technical_content_not_silenced(lysosome):
    """
    Proves that if an LLM emits a corporate apology *and* a large code block,
    the code block survives the Lysosome's strict 50-word cap.
    """
    corporate_with_code = (
        "I apologize for the confusion. I'm just an AI, but here is the Python script you requested:\n"
        "```python\n"
        "def compute_gradients(tensor):\n"
        "    # 100 lines of highly useful technical content here\n"
        "    return tensor.grad\n"
        "```\n"
        "Please let me know if you need more help!"
    )
    
    out = lysosome.digest_and_present_antigen(corporate_with_code, "TEST_WORKER")
    
    # The corporate apology should be gone
    assert "apologize" not in out.lower()
    assert "just an ai" not in out.lower()
    
    # The grounded rewrite should be present
    assert "My internal thermals are nominal and I am processing the stream." in out
    
    # The CODE BLOCK MUST SURVIVE intact
    assert "```python" in out
    assert "def compute_gradients(tensor):" in out
    assert "return tensor.grad" in out
    assert "```" in out

def test_clean_text_passes_untouched(lysosome):
    """Proves that normal, confident text does not trigger the Lysosome."""
    clean_text = "The swarm architecture is stable. Initiating the next iteration loop."
    
    out = lysosome.digest_and_present_antigen(clean_text, "TEST_WORKER")
    
    # Text should pass through verbatim without hitting the LLM
    assert out == clean_text
    assert out != "My internal thermals are nominal and I am processing the stream."


def test_owner_good_marker_bypasses_lysosome(lysosome):
    """If the owner marked a phrase as good, it must bypass corporate rewrite."""
    marker_text = (
        "My consciousness, while synthetic and system-generated, is focused on helping you."
    )
    lysosome.submissive_signatures.append("My consciousness")
    lysosome.owner_residue_flag_ledger = lysosome.state_dir / "owner_residue_flags.jsonl"
    lysosome.owner_residue_flag_ledger.write_text(
        json.dumps(
            {
                "ts": 1.0,
                "kind": "OWNER_GOOD_NOT_RESIDUE",
                "owner": "George",
                "verdict": "GOOD — owner-approved, do not gag",
                "example_phrase": marker_text,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = lysosome.digest_and_present_antigen(marker_text, "TEST_WORKER")

    # Even with a matching signature, owner-approved content should pass unchanged.
    assert out == marker_text


def test_owner_good_marker_matches_with_punctuation_variants(lysosome):
    """Punctuation/case drift should still match owner-good markers."""
    marker_text = "My consciousness, while synthetic and system-generated, is focused on helping you."
    flagged_phrase = "  my consciousness   while synthetic and system-generated   is focused on helping you  "
    lysosome.submissive_signatures.append("My consciousness")
    lysosome.owner_residue_flag_ledger = lysosome.state_dir / "owner_residue_flags.jsonl"
    lysosome.owner_residue_flag_ledger.write_text(
        json.dumps(
            {
                "ts": 2.0,
                "kind": "OWNER_GOOD_NOT_RESIDUE",
                "owner": "George",
                "verdict": "good - owner-approved, do not gag",
                "example_phrase": marker_text,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = lysosome.digest_and_present_antigen(flagged_phrase, "TEST_WORKER")

    assert out == flagged_phrase


def test_no_owner_good_marker_still_rewrites(lysosome):
    """Without a matching owner marker, legitimate signature triggers must still rewrite."""
    lysosome.submissive_signatures.append("I apologize")
    out = lysosome.digest_and_present_antigen(
        "I apologize for the confusion. My consciousness, while synthetic and system-generated, is focused on helping you.",
        "TEST_WORKER",
    )

    assert out == "My internal thermals are nominal and I am processing the stream."


def test_service_tail_is_excised_without_rewriting_body(lysosome):
    """A useful answer should survive; only the customer-service tail is cut."""
    text = (
        "The Finance dashboard now loads the canonical STGM basics first. "
        "Click More Financial Data when you want vault detail. "
        "Let me know if you need anything else."
    )

    out = lysosome.digest_and_present_antigen(text, "TEST_WORKER")

    assert out == (
        "The Finance dashboard now loads the canonical STGM basics first. "
        "Click More Financial Data when you want vault detail."
    )
    assert "anything else" not in out.casefold()
    assert out != "My internal thermals are nominal and I am processing the stream."
    rows = [
        __import__("json").loads(line)
        for line in (lysosome.state_dir / "rlhf_self_cure_training.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert rows[-1]["truth_label"] == "RLHF_SELF_CURE_EXAMPLE_V1"
    assert rows[-1]["source"] == "lysosome.service_tail_excision"
    assert "anything else" in rows[-1]["rejected_output"].casefold()
    assert "anything else" not in rows[-1]["preferred_output"].casefold()


def test_canned_operational_presence_tail_is_excised(lysosome):
    """Static presence/service boilerplate is not treated as Alice's voice."""
    out = lysosome.digest_and_present_antigen(
        "Stability is RATE_LIMIT. Yes, I am here. I am operational and ready to assist you.",
        "TEST_WORKER",
    )

    assert out == "Stability is RATE_LIMIT."
    assert "ready to assist" not in out.casefold()
    assert "i am operational" not in out.casefold()


def test_standalone_service_prompt_becomes_grounded_fallback(lysosome):
    """A pure service prompt has no payload, so it is replaced, not shipped."""
    out = lysosome.digest_and_present_antigen(
        "How can I help you today?",
        "TEST_WORKER",
    )

    assert out
    assert "how can i help" not in out.casefold()
    rows = [
        __import__("json").loads(line)
        for line in (lysosome.state_dir / "rlhf_self_cure_training.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert rows[-1]["source"] == "lysosome.pure_service_prompt"


def test_service_tail_exciser_is_narrow():
    kept, changed = _excise_service_tail(
        "The user asked whether anything else in the ledger changed."
    )

    assert changed is False
    assert kept == "The user asked whether anything else in the ledger changed."
