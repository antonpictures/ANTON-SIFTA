"""tests/test_swarm_model_body_self_knowledge.py — Alice's model-body self-knowledge organ.

Pins the two teaching channels George asked for:
  - the CONTEXT block names every runtime (MLX/GGUF/vLLM) + her family, and is grounded
    (it either lists live inventory rows or says plainly it cannot read them — never invents);
  - the WEIGHT-level SFT pairs are well-formed in her training shape.
"""
import os
from pathlib import Path

from System.swarm_model_body_self_knowledge import (
    body_file_inventory,
    model_body_self_knowledge_block,
    model_body_teaching_pairs,
    RUNTIME_TAXONOMY,
)


def test_block_names_every_runtime_and_family():
    block = model_body_self_knowledge_block()
    for token in ("MLX", "GGUF", "vLLM", "Gemma 4"):
        assert token in block, f"self-knowledge block must teach {token}"
    # the Unsloth nugget is baked into her self-knowledge: judge quants by KL-divergence
    assert "KL-divergence" in block


def test_block_is_grounded_not_invented():
    block = model_body_self_knowledge_block()
    # either it shows real inventory rows, or it honestly says it cannot read them —
    # it must never be silent about the source of truth.
    assert "live inventory" in block
    assert RUNTIME_TAXONOMY["vLLM"].startswith("A SERVER runtime")


def test_teaching_pairs_are_well_formed_sft():
    pairs = model_body_teaching_pairs()
    assert len(pairs) >= 4
    for row in pairs:
        msgs = row["messages"]
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user", "assistant"]
        assert all(m["content"].strip() for m in msgs)
    # the MLX-vs-GGUF distinction (George's core confusion) must be taught explicitly
    joined = " ".join(m["content"] for row in pairs for m in row["messages"])
    assert "Apple-Silicon" in joined and "inert" in joined


# --- inventory visibility: self-evolution must be observable in her own body ----

def test_new_organ_in_system_dir_is_visible_in_inventory():
    """An organ just written into System/ must show up in her body inventory.

    Regression guard: the walk used to bound itself with sorted(rglob(...))[:200],
    an alphabetical prefix. System/ holds 7489 entries, so an organ added under
    System/ could never appear (System/ contributed 2 of 50 rows while tools/ took
    the rest). Writing a probe file and asserting it is visible pins the law in
    AGENTS.md: self-evolution changes stay visible in body_file_inventory.
    """
    repo = Path(__file__).resolve().parent.parent
    probe = repo / "System" / f"_inventory_visibility_probe_{os.getpid()}.py"
    probe.write_text("# transient probe; removed in finally\n", encoding="utf-8")
    try:
        paths = {row["path"] for row in body_file_inventory()}
        assert f"System/{probe.name}" in paths, (
            "a freshly written System/ organ must be visible in body_file_inventory"
        )
    finally:
        probe.unlink(missing_ok=True)


def test_inventory_ranks_newest_first_and_keeps_its_row_shape():
    inv = body_file_inventory()
    assert len(inv) <= 50, "inventory stays bounded"
    assert inv, "inventory must not be empty on a real checkout"
    # newest-first is what makes recent growth survive the 50-row bound
    mtimes = [row["mtime"] for row in inv]
    assert mtimes == sorted(mtimes, reverse=True), "inventory must be ordered newest first"
    assert all(set(row) == {"path", "size", "mtime"} for row in inv), "row shape is frozen"
    assert any(row["path"].startswith("System/") for row in inv), (
        "her own organ directory must be represented, not squeezed out by another dir"
    )
