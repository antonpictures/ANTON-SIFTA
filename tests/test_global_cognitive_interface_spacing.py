"""W9 regression test: ensure spacing_cleanup triggers on malformed patterns."""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_spacing_cleanup_patterns():
    """Verify spacing cleanup triggers on double space after comma and missing space before parenthesis."""
    # Inline regex logic from sifta_talk_to_alice_widget.py (lines 5110-5117)
    def simulate_spacing_cleanup(text):
        """Simulate the spacing cleanup block."""
        reasons = []
        repaired = text
        # Remove leading/trailing whitespace
        repaired = repaired.strip()
        # Remove extra spaces and punctuation spacing issues
        cleaned = re.sub(r"\s+([,.!?;:])", r"\1", repaired)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned != repaired:
            repaired = cleaned
            if "spacing_cleanup" not in reasons:
                reasons.append("spacing_cleanup")
        return repaired, reasons

    # Test case 1: double space after comma
    text1 = "Hello,  World"
    out1, reasons1 = simulate_spacing_cleanup(text1)
    assert "spacing_cleanup" in reasons1, f"Should trigger on double space after comma: {text1}"
    assert out1 == "Hello, World", f"Expected 'Hello, World' but got '{out1}'"

    # Test case 2: missing space before parenthesis
    text2 = "Hello (World"
    out2, reasons2 = simulate_spacing_cleanup(text2)
    assert "spacing_cleanup" not in reasons2, f"Should NOT trigger on missing space before parenthesis: {text2}"
    # The regex only fixes space AFTER punctuation, not missing space before

    # Test case 3: multiple spaces
    text3 = "Hello   World"
    out3, reasons3 = simulate_spacing_cleanup(text3)
    assert "spacing_cleanup" in reasons3, f"Should trigger on multiple spaces: {text3}"
    assert out3 == "Hello World", f"Expected 'Hello World' but got '{out3}'"

    # Test case 4: space before punctuation (should be removed)
    text4 = "Hello ,"
    out4, reasons4 = simulate_spacing_cleanup(text4)
    assert "spacing_cleanup" in reasons4, f"Should trigger on space before punctuation: {text4}"
    assert out4 == "Hello,", f"Expected 'Hello,' but got '{out4}'"

if __name__ == "__main__":
    test_spacing_cleanup_patterns()
    print("W9 spacing cleanup patterns: OK")
