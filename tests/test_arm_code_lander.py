#!/usr/bin/env python3
"""Tests for the deterministic agent-arm code lander."""

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_arm_code_lander as lander


HERMES_FENCED_OUTPUT = """\
I have ingested the covenant. Here is the file.

```python
def add(a, b):
    return a + b


if __name__ == "__main__":
    print(add(2, 3))
```

Done. Receipt follows.
"""


def test_extract_target_path_finds_applications_path() -> None:
    prompt = "Alice, ask hermes to write Applications/sifta_stigmergic_tictactoe.py: a game."
    assert lander.extract_target_path(prompt) == "Applications/sifta_stigmergic_tictactoe.py"


def test_extract_target_path_none_when_absent() -> None:
    assert lander.extract_target_path("just chat with me, no files") is None


def test_extract_code_takes_largest_fenced_block() -> None:
    code = lander.extract_code(HERMES_FENCED_OUTPUT)
    assert code is not None
    assert "def add(a, b):" in code
    assert "```" not in code  # fences stripped
    assert "I have ingested" not in code  # prose excluded


def test_land_writes_and_compiles(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lander, "_REPO", tmp_path)
    prompt = "Alice, ask hermes to write Applications/landed_demo.py: a tiny module."
    receipt = lander.land_arm_code(
        prompt=prompt, output=HERMES_FENCED_OUTPUT, arm="hermes_agent", receipt_id="r-1"
    )
    assert receipt["ok"] is True
    assert receipt["rel_path"] == "Applications/landed_demo.py"
    assert receipt["compiled"] is True
    assert receipt["truth_label"] == "ARM_CODE_LANDED_V1"
    written = tmp_path / "Applications" / "landed_demo.py"
    assert written.exists()
    assert "def add(a, b):" in written.read_text(encoding="utf-8")


def test_land_rejects_path_escape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lander, "_REPO", tmp_path)
    # A path token that resolves outside the repo must be refused.
    prompt = "write Applications/../../etc/Applications/evil.py please"
    receipt = lander.land_arm_code(
        prompt=prompt, output=HERMES_FENCED_OUTPUT, arm="hermes_agent"
    )
    assert receipt["ok"] is False
    assert receipt["reason"] in {"path_escapes_repo", "no_target_path_in_prompt"}


def test_land_honest_failure_when_no_code(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lander, "_REPO", tmp_path)
    prompt = "Alice, ask hermes to write Applications/empty.py."
    receipt = lander.land_arm_code(
        prompt=prompt, output="I will help! How can I assist you today?", arm="hermes_agent"
    )
    assert receipt["ok"] is False
    assert receipt["reason"] == "no_code_block_in_output"
    assert not (tmp_path / "Applications" / "empty.py").exists()


def test_land_honest_failure_on_syntax_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lander, "_REPO", tmp_path)
    broken = "```python\ndef oops(:\n    pass\n```"
    prompt = "Alice, ask hermes to write Applications/broken.py."
    receipt = lander.land_arm_code(prompt=prompt, output=broken, arm="hermes_agent")
    assert receipt["ok"] is False
    assert receipt["reason"].startswith("arm_code_syntax_error")
    assert not (tmp_path / "Applications" / "broken.py").exists()


# ── Regression: the catastrophe that ate the talk widget. ─────────────────
#
# George 2026-05-26 ~01:06 — Claude arm's evidence-mode capture contained no
# fenced ```python``` block (the arm did its work via Write/Edit tool calls,
# not by streaming code as chat text). My then-current extract_code() fell
# back to `ast.parse(output)`, which ACCEPTED the captured stream-JSON
# because every line is a valid Python dict-literal expression
# (`{"type": "stream_event", …}`). The lander then wrote 1107 lines of JSON
# to the talk widget path, destroying 20389 lines of real code. Restored
# from `git show HEAD:…`. extract_code now refuses fence-less input; these
# regression tests pin that.

CLAUDE_STREAM_JSON_DUMP = (
    '{"type":"system","subtype":"init","cwd":"/x","session_id":"abc","tools":["Read","Write"]}\n'
    '{"type":"stream_event","event":{"type":"message_start","message":{"model":"claude"}}}\n'
    '{"type":"stream_event","event":{"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"I will read the file."}}}\n'
    '{"type":"assistant","message":{"content":[{"type":"text","text":"done"}]}}\n'
)


def test_extract_code_refuses_fenceless_stream_json_dump() -> None:
    """The regression: Claude stream-JSON parses as Python dict literals but
    is not code. extract_code must NOT accept it just because ast.parse
    succeeds."""
    # Confirm ast.parse would happily accept it (the trap):
    import ast as _ast
    _ast.parse(CLAUDE_STREAM_JSON_DUMP)  # would raise if this premise is wrong
    # Now the lander must still refuse:
    assert lander.extract_code(CLAUDE_STREAM_JSON_DUMP) is None


def test_land_arm_code_refuses_to_overwrite_with_stream_json(
    tmp_path, monkeypatch
) -> None:
    """End-to-end: even with a valid .py path in the prompt and stream-JSON
    that ast-parses, the lander must NOT write the file."""
    monkeypatch.setattr(lander, "_REPO", tmp_path)
    target = tmp_path / "Applications" / "sifta_talk_to_alice_widget.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    pristine = "# original widget content — must survive\n"
    target.write_text(pristine, encoding="utf-8")

    prompt = (
        "Refactor on Applications/sifta_talk_to_alice_widget.py. "
        "Write System/swarm_memory_card.py."
    )
    receipt = lander.land_arm_code(
        prompt=prompt, output=CLAUDE_STREAM_JSON_DUMP, arm="claude_agent"
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "no_code_block_in_output"
    # Pristine target must be untouched.
    assert target.read_text(encoding="utf-8") == pristine
