"""tests/test_swarm_model_body_self_knowledge.py — Alice's model-body self-knowledge organ.

Pins the two teaching channels George asked for:
  - the CONTEXT block names every runtime (MLX/GGUF/vLLM) + her family, and is grounded
    (it either lists live inventory rows or says plainly it cannot read them — never invents);
  - the WEIGHT-level SFT pairs are well-formed in her training shape.
"""
from System.swarm_model_body_self_knowledge import (
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
