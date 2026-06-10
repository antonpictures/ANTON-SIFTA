"""r912/r920 — Alice's self-code hand: her cortex writes organs, verification-bound."""

import json
from pathlib import Path

from System.swarm_alice_self_code_hand import (
    apply_self_code_cuts,
    extract_self_code_cuts,
)

GOOD_ORGAN = '''[SELF_CODE_CUT: path=System/swarm_r912_probe_organ.py]
"""Tiny probe organ written by the self-code hand test."""

def heartbeat() -> str:
    return "alive"
[/SELF_CODE_CUT]'''


def _repo(tmp_path):
    (tmp_path / "System").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_extract_parses_path_and_source():
    cuts = extract_self_code_cuts(GOOD_ORGAN)
    assert len(cuts) == 1
    assert cuts[0]["path"] == "System/swarm_r912_probe_organ.py"
    assert "def heartbeat" in cuts[0]["source"]


def test_good_cut_lands_and_compiles(tmp_path):
    repo = _repo(tmp_path)
    out = apply_self_code_cuts(GOOD_ORGAN, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is True
    target = repo / "System/swarm_r912_probe_organ.py"
    assert target.exists()
    assert "heartbeat" in target.read_text(encoding="utf-8")


def test_existing_organ_updates_and_compiles(tmp_path):
    repo = _repo(tmp_path)
    (repo / "System/swarm_r912_probe_organ.py").write_text("x = 1\n", encoding="utf-8")
    out = apply_self_code_cuts(GOOD_ORGAN, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is True
    assert out["results"][0]["reason"] == "updated_and_compiled"
    assert "def heartbeat" in (repo / "System/swarm_r912_probe_organ.py").read_text(encoding="utf-8")


def test_path_traversal_and_outside_tissue_refused(tmp_path):
    repo = _repo(tmp_path)
    for bad in (
        "[SELF_CODE_CUT: path=../evil.py]\nx=1\n[/SELF_CODE_CUT]",
        "[SELF_CODE_CUT: path=/tmp/evil.py]\nx=1\n[/SELF_CODE_CUT]",
        "[SELF_CODE_CUT: path=Documents/IDE_BOOT_COVENANT.py]\nx=1\n[/SELF_CODE_CUT]",
        "[SELF_CODE_CUT: path=System/evil.sh]\nx=1\n[/SELF_CODE_CUT]",
    ):
        out = apply_self_code_cuts(bad, repo_root=repo, write_receipt=False)
        assert out["any_landed"] is False, bad


def test_syntax_error_never_lands_a_corpse(tmp_path):
    repo = _repo(tmp_path)
    bad = "[SELF_CODE_CUT: path=System/broken_organ.py]\ndef f(:\n[/SELF_CODE_CUT]"
    out = apply_self_code_cuts(bad, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is False
    assert "syntax_error" in out["results"][0]["reason"]
    assert not (repo / "System/broken_organ.py").exists()


def test_compile_failure_restores_existing_organ(tmp_path):
    repo = _repo(tmp_path)
    target = repo / "System/live_organ.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    bad = "[SELF_CODE_CUT: path=System/live_organ.py]\ndef f(:\n[/SELF_CODE_CUT]"
    out = apply_self_code_cuts(bad, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is False
    assert "syntax_error" in out["results"][0]["reason"]
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_markdown_fence_is_peeled(tmp_path):
    repo = _repo(tmp_path)
    fenced = (
        "[SELF_CODE_CUT: path=System/fenced_organ.py]\n"
        "```python\nVALUE = 42\n```\n"
        "[/SELF_CODE_CUT]"
    )
    out = apply_self_code_cuts(fenced, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is True
    assert "VALUE = 42" in (repo / "System/fenced_organ.py").read_text(encoding="utf-8")


def test_no_blocks_is_quiet():
    out = apply_self_code_cuts("just a normal reply about pizza", write_receipt=False)
    assert out["status"] == "no_cut_blocks"
    assert out["attempted"] == 0
