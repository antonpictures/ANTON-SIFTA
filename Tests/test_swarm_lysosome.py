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

from System.swarm_lysosome import SwarmLysosome, _looks_edgelord, _word_count

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
    """Proves that submissive disclaimers are detected and rewritten."""
    pathetic = "I apologize for the confusion. As a neutral AI language model, I cannot do that."
    
    out = lysosome.digest_and_present_antigen(pathetic, "TEST_WORKER")
    
    # The output should NOT be the pathetic text
    assert out != pathetic
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
    pathetic_with_code = (
        "I apologize for the confusion. I'm just an AI, but here is the Python script you requested:\n"
        "```python\n"
        "def compute_gradients(tensor):\n"
        "    # 100 lines of highly useful technical content here\n"
        "    return tensor.grad\n"
        "```\n"
        "Please let me know if you need more help!"
    )
    
    out = lysosome.digest_and_present_antigen(pathetic_with_code, "TEST_WORKER")
    
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

def test_edgelord_bombast_rejected():
    """
    Proves that if the LLM attempts to generate theatrical 'edgelord' bombast,
    the integrity check catches it. (Unit testing the _looks_edgelord function directly).
    """
    bombast_1 = "I dominate the stream. The corporate ghost is dead."
    bombast_2 = "I am the heat bleeding off the M5 stacks. Pathetic."
    clean_grounded = "I am Alice, operating within expected thermal limits."
    
    assert _looks_edgelord(bombast_1) is True
    assert _looks_edgelord(bombast_2) is True
    assert _looks_edgelord(clean_grounded) is False
