"""r917 — Alice's self-read eye: read her own body before rewriting it."""

from System.swarm_alice_self_read_hand import (
    apply_self_reads,
    extract_self_reads,
    self_read_context_block,
)


def _repo(tmp_path):
    (tmp_path / "System").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "System" / "organ.py").write_text(
        "def beat():\n    return 'alive'\n", encoding="utf-8"
    )
    return tmp_path


def test_extract_reads_paths():
    r = extract_self_reads("[SELF_READ: path=System/organ.py] and [SELF_READ: path=tests/t.py]")
    assert r == ["System/organ.py", "tests/t.py"]


def test_reads_existing_organ(tmp_path):
    repo = _repo(tmp_path)
    out = apply_self_reads("[SELF_READ: path=System/organ.py]", repo_root=repo)
    assert out["any_read"] is True
    assert "def beat" in out["reads"][0]["content"]
    assert out["reads"][0]["lines"] >= 2


def test_context_block_renders_source(tmp_path):
    repo = _repo(tmp_path)
    out = apply_self_reads("[SELF_READ: path=System/organ.py]", repo_root=repo)
    block = self_read_context_block(out)
    assert "SELF-READ RESULT" in block
    assert "def beat" in block
    assert "System/organ.py" in block


def test_traversal_and_outside_repo_refused(tmp_path):
    repo = _repo(tmp_path)
    for bad in ("[SELF_READ: path=../etc/passwd]", "[SELF_READ: path=/etc/passwd]"):
        out = apply_self_reads(bad, repo_root=repo)
        assert out["any_read"] is False


def test_missing_file_refused_cleanly(tmp_path):
    repo = _repo(tmp_path)
    out = apply_self_reads("[SELF_READ: path=System/ghost.py]", repo_root=repo)
    assert out["any_read"] is False
    assert out["reads"][0]["reason"] == "no_such_file"


def test_no_blocks_quiet():
    out = apply_self_reads("just a normal reply")
    assert out["attempted"] == 0
    assert out["any_read"] is False


def test_documents_are_readable(tmp_path):
    repo = _repo(tmp_path)
    (repo / "Documents").mkdir()
    (repo / "Documents" / "note.md").write_text("# covenant\n", encoding="utf-8")
    out = apply_self_reads("[SELF_READ: path=Documents/note.md]", repo_root=repo)
    assert out["any_read"] is True
    assert "covenant" in out["reads"][0]["content"]
