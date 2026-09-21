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
    body_file_inventory_page,
    body_file_lookup,
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


# --- INV-2: full inventory must be reachable beyond the 50-row recent view ----

def _make_body(tmp_path, count, old_name="old_organ_alpha.py", old_at_days_ago=90):
    """A tiny body: one old organ plus `count` newer churn files, deterministic mtimes."""
    import time
    now = time.time()
    body = tmp_path / "body"
    body.mkdir(parents=True, exist_ok=True)
    old = body / old_name
    old.write_text("# an old organ that churn must not hide\n", encoding="utf-8")
    os.utime(old, (now - old_at_days_ago * 86400, now - old_at_days_ago * 86400))
    for i in range(count):
        churn = body / f"generated_output_{i:03d}.txt"
        churn.write_text(f"churn row {i}\n", encoding="utf-8")
        os.utime(churn, (now - i, now - i))  # every churn file newer than the organ
    return body, old


def test_exact_lookup_finds_old_organ_beneath_recent_churn(tmp_path):
    """INV-2 acceptance: generated churn cannot hide a requested source file."""
    body, old = _make_body(tmp_path, count=60)
    recent = body_file_inventory(key_dirs=(str(body),))  # the D3g recent view, 50 rows
    assert f"{old.name}" not in {Path(r["path"]).name for r in recent}, (
        "with 60 newer files the old organ must be outside the 50-row recent view"
    )
    hit = body_file_lookup(str(old), key_dirs=(str(body),))
    assert hit["found"] is True, "exact lookup must not be bounded by the recent view"
    assert hit["in_inventory_scope"] is True
    assert hit["size"] == old.stat().st_size
    # ...and the same body stays paged and reachable in full
    page = body_file_inventory_page(1, 50, key_dirs=(str(body),))
    assert page["total"] == 61 and page["whole_body"] is False


def test_pagination_metadata_never_claims_whole_body_from_one_page(tmp_path):
    """A 50-row page is a window; only a page spanning every row may say whole_body."""
    body, _old = _make_body(tmp_path, count=119, old_name="old_organ_beta.py")
    first = body_file_inventory_page(0, 50, key_dirs=(str(body),))
    assert first["total"] == 120 and first["pages"] == 3
    assert first["whole_body"] is False and first["complete"] is False
    assert len(first["rows"]) == 50
    # deterministic order: identical rows across two calls, mtime ties broken by path
    again = body_file_inventory_page(0, 50, key_dirs=(str(body),))
    assert first["rows"] == again["rows"]
    mtimes = [r["mtime"] for r in first["rows"]]
    assert mtimes == sorted(mtimes, reverse=True)
    tied = [r for r in first["rows"] if r["mtime"] == first["rows"][0]["mtime"]]
    paths = [r["path"] for r in tied]
    assert paths == sorted(paths), "equal-mtime rows must break ties by path"
    # walking every page yields exactly the full body, no row lost or duplicated
    seen = []
    for p in range(first["pages"]):
        pg = body_file_inventory_page(p, 50, key_dirs=(str(body),))
        seen.extend(pg["rows"])
        if p == first["pages"] - 1:
            assert pg["complete"] is True, "the final page spans every row"
        else:
            assert pg["complete"] is False
    assert len(seen) == 120 and len({r["path"] for r in seen}) == 120


def test_recent_view_default_contract_is_unchanged():
    """D3g's view survives INV-2: bounded, newest first, frozen row shape."""
    inv = body_file_inventory()
    assert inv and len(inv) <= 50
    mtimes = [row["mtime"] for row in inv]
    assert mtimes == sorted(mtimes, reverse=True)
    assert all(set(row) == {"path", "size", "mtime"} for row in inv)
    assert len(body_file_inventory(max_rows=5)) == 5


def test_lookup_reports_absent_and_refuses_paths_outside_the_body():
    assert body_file_lookup("System/no_such_organ_zz9.py") == {
        "found": False, "reason_code": "ABSENT", "path": "System/no_such_organ_zz9.py",
    }
    outside = body_file_lookup("../outside_the_body.txt")
    assert outside["found"] is False and outside["reason_code"] == "PATH_OUTSIDE_BODY"
    deep = body_file_lookup("../../etc/passwd")
    assert deep["found"] is False and deep["reason_code"] == "PATH_OUTSIDE_BODY"
