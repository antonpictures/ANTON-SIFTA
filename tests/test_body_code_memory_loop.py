"""tests/test_body_code_memory_loop.py — r982 body-code memory loop proof.

The bar set in r980 (answering r977 Q4 / r978 Q5): nobody says
"continuous self-improvement" until a test proves a prior repair memory,
read from disk, changes the next self-code choice — and the read itself
is receipted. This file is that test.

Loop under proof:
  walk own tissue → compose body-code card (receipted read) →
  prior repair engram changes suggest_next_cut → hand attaches card
  before bytes change.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_code_knowledge_graph import (  # noqa: E402
    READS_LEDGER_FILENAME,
    ENGRAMS_LEDGER_FILENAME,
    compose_body_code_card,
    suggest_next_cut,
    walk_repo,
)

_FAKE_ORGAN = '''"""fake_pump.py — toy organ for the body-code memory loop test."""
import json
from pathlib import Path

LEDGER = ".sifta_state/fake_pump_beats.jsonl"


def beat(state_dir):
    """One pump beat; writes a receipt row."""
    row = {"ts": 0.0, "beat": True}
    p = Path(state_dir) / "fake_pump_beats.jsonl"
    with p.open("a") as f:
        f.write(json.dumps(row) + "\\n")
    return row


def tangled(a, b, c):
    """Deliberately branchy so complexity ranks it first."""
    if a:
        if b:
            if c:
                return 3
            return 2
        return 1
    for i in range(3):
        if i == a:
            return i
    return 0
'''


@pytest.fixture()
def body(tmp_path: Path):
    """Tiny repo body: one organ, walked into a fresh atlas."""
    repo = tmp_path / "repo"
    (repo / "System").mkdir(parents=True)
    (repo / "tests").mkdir()
    state = repo / ".sifta_state"
    state.mkdir()
    organ = repo / "System" / "fake_pump.py"
    organ.write_text(_FAKE_ORGAN, encoding="utf-8")
    (repo / "tests" / "test_fake_pump.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )
    walk_repo(repo, state_dir=state)
    return repo, state


def test_card_reads_own_anatomy_and_receipts_the_read(body):
    repo, state = body
    out = compose_body_code_card(
        ["System/fake_pump.py"], state_dir=state, repo_root=repo, turn_tag="loop_test"
    )
    card = out["card"]
    assert "organ: System/fake_pump.py" in card
    assert "purpose:" in card and "fake_pump.py" in card  # docstring head
    assert "anatomy:" in card and "tangled" in card        # children from atlas
    assert "fake_pump_beats.jsonl" in card                  # ledger literal found
    assert "tests/test_fake_pump.py" in card                # proof file found
    # the read is receipted — the loop is OBSERVED, not narrated
    reads = (state / READS_LEDGER_FILENAME).read_text().strip().splitlines()
    row = json.loads(reads[-1])
    assert row["truth_label"] == "BODY_CODE_CARD_READ_V1"
    assert row["paths"] == ["System/fake_pump.py"]
    assert row["turn_tag"] == "loop_test"


def test_prior_repair_memory_changes_the_next_cut(body):
    repo, state = body
    target = "System/fake_pump.py"
    # without any repair memory: grounded in atlas complexity
    before = suggest_next_cut([target], state_dir=state, repo_root=repo)
    assert before["grounded_in"] == "complexity"
    assert "tangled" in before["suggestion"]
    # a previous repair landed and left an engram with a named next risk
    engram = {
        "ts": time.time(),
        "engram_id": "eng-loop-test-001",
        "kind": "repair_outcome",
        "files": [target],
        "why": "beat() lost rows under concurrent writers",
        "result": "tests_green",
        "next_risk": "beat() has no file lock; add one before adding callers",
        "truth_label": "TEST_SEED",
    }
    with (state / ENGRAMS_LEDGER_FILENAME).open("a") as f:
        f.write(json.dumps(engram) + "\n")
    after = suggest_next_cut([target], state_dir=state, repo_root=repo)
    # THE LOOP: the choice changed because a repair memory was read,
    # and the suggestion names the engram it read.
    assert after["grounded_in"] == "repair_engram"
    assert after["engram_id"] == "eng-loop-test-001"
    assert "file lock" in after["suggestion"]
    assert after["suggestion"] != before["suggestion"]
    # and the card now carries the repair memory too
    out = compose_body_code_card([target], state_dir=state, repo_root=repo)
    assert "repair-memory[eng-loop-test-001]" in out["card"]
    assert "eng-loop-test-001" in out["repair_engrams"]


def test_stale_flag_when_disk_moves_past_atlas(body):
    repo, state = body
    organ = repo / "System" / "fake_pump.py"
    future = time.time() + 120
    os.utime(organ, (future, future))
    out = compose_body_code_card(["System/fake_pump.py"], state_dir=state, repo_root=repo)
    assert "System/fake_pump.py" in out["stale"]
    assert "STALE" in out["card"]


def test_unwalked_organ_is_named_not_invented(body):
    repo, state = body
    out = compose_body_code_card(["System/never_walked.py"], state_dir=state, repo_root=repo)
    assert "NO ROW" in out["card"]


def test_self_code_hand_reads_card_before_cutting(body, monkeypatch):
    repo, state = body
    from System.swarm_alice_self_code_hand import apply_self_code_cuts

    reply = (
        "[SELF_CODE_CUT: path=System/fake_pump.py]\n"
        + _FAKE_ORGAN
        + "\n[/SELF_CODE_CUT]"
    )
    summary = apply_self_code_cuts(
        reply, model="loop-test", repo_root=repo, run_tests=False, write_receipt=False
    )
    # the hand read the body-code card before the bytes changed
    assert "organ: System/fake_pump.py" in summary.get("body_code_card", "")
    assert summary.get("body_code_card_paths") == ["System/fake_pump.py"]
    rows = (state / READS_LEDGER_FILENAME).read_text().strip().splitlines()
    last = json.loads(rows[-1])
    assert last["turn_tag"] == "self_code_hand"
    # and the cut itself still landed
    assert summary["any_landed"] is True
