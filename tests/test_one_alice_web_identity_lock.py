"""W2 regression test: the One Alice identity doctrine is locked into web-lane prompts.

Verifies that ONE_ALICE_DOCTRINE_BLOCK is module-level and is prepended to BOTH
web prompt builders (typed + attachment), so no web lane can answer as anything
other than Alice.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def _gate():
    from System import swarm_web_global_chat_gate as gate
    return gate


def test_doctrine_block_exists_and_is_one_alice():
    gate = _gate()
    block = gate.ONE_ALICE_DOCTRINE_BLOCK
    assert isinstance(block, str) and block.strip(), "doctrine block must be a non-empty string"
    low = block.lower()
    assert "one alice" in low or "only one alice" in low, "must state the One Alice rule"
    assert "mercury" in low, "must lock the Mercury-is-an-organ clause"


def test_typed_prompt_includes_doctrine():
    gate = _gate()
    out = gate.web_typed_prompt_block(speak_requested=False)
    assert isinstance(out, str) and out.strip()
    assert "one Alice" in out or "only one Alice" in out, "typed prompt must carry the doctrine"
    # doctrine must come first (prepended, not appended)
    assert out.strip().startswith("You are Alice") or out.strip().startswith(gate.ONE_ALICE_DOCTRINE_BLOCK.strip()[:20]), \
        "doctrine block must be prepended to the typed prompt"


def test_attachment_prompt_includes_doctrine():
    gate = _gate()
    out = gate.web_attachment_prompt_block(attachments=None)
    assert isinstance(out, str) and out.strip()
    assert "one Alice" in out or "only one Alice" in out, "attachment prompt must carry the doctrine"


def test_no_second_doctrine_definition():
    import inspect
    src = inspect.getsource(_gate())
    assert src.count("ONE_ALICE_DOCTRINE_BLOCK = (") == 1, "doctrine block must be defined exactly once at module level"


if __name__ == "__main__":
    test_doctrine_block_exists_and_is_one_alice()
    test_typed_prompt_includes_doctrine()
    test_attachment_prompt_includes_doctrine()
    test_no_second_doctrine_definition()
    print("W2 identity-lock checks: OK")