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


def test_flattened_body_reindents_before_landing(tmp_path):
    repo = _repo(tmp_path)
    flat = (
        "[SELF_CODE_CUT: path=System/flat_repaired_organ.py]\n"
        "def heartbeat() -> str:\n"
        "\"\"\"Flattened body from a live Alice self-cut.\"\"\"\n"
        "return \"alive\"\n"
        "[/SELF_CODE_CUT]"
    )
    out = apply_self_code_cuts(flat, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is True
    assert out["results"][0]["reindent_repair"] == "applied_after_syntax_error"
    target = repo / "System/flat_repaired_organ.py"
    text = target.read_text(encoding="utf-8")
    assert '    """Flattened body' in text
    assert '    return "alive"' in text


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


# ── r928 — new-app lane: merge-only manifest registration ──────────────────

WIDGET_CUT = '''[SELF_CODE_CUT: path=Applications/sifta_r928_demo_widget.py]
"""Demo widget grown by Alice's own hand (r928 test)."""

class R928DemoWidget:
    pass
[/SELF_CODE_CUT]'''


def _repo_with_manifest(tmp_path):
    repo = _repo(tmp_path)
    (repo / "Applications").mkdir()
    (repo / "Applications/apps_manifest.json").write_text(
        json.dumps(
            {
                "Existing App": {
                    "entry_point": "Applications/existing.py",
                    "widget_class": "ExistingWidget",
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return repo


def _manifest_cut(entry_point="Applications/sifta_r928_demo_widget.py"):
    entry = {
        "R928 Demo": {
            "entry_point": entry_point,
            "widget_class": "R928DemoWidget",
            "icon": "🐜",
            "category": "Demo",
            "description": "r928 self-grown app",
        }
    }
    return (
        "[SELF_CODE_CUT: path=Applications/apps_manifest.json]\n"
        + json.dumps(entry)
        + "\n[/SELF_CODE_CUT]"
    )


def test_new_app_widget_plus_manifest_lands_in_one_reply(tmp_path):
    repo = _repo_with_manifest(tmp_path)
    out = apply_self_code_cuts(
        WIDGET_CUT + "\n" + _manifest_cut(), repo_root=repo, write_receipt=False
    )
    assert out["any_landed"] is True
    landed = {r["path"]: r for r in out["results"]}
    assert landed["Applications/sifta_r928_demo_widget.py"]["landed"] is True
    assert landed["Applications/apps_manifest.json"]["landed"] is True
    manifest = json.loads(
        (repo / "Applications/apps_manifest.json").read_text(encoding="utf-8")
    )
    assert "Existing App" in manifest, "merge must never drop existing apps"
    assert manifest["R928 Demo"]["widget_class"] == "R928DemoWidget"
    assert manifest["R928 Demo"]["doctor"] == "alice_self"


def test_manifest_cut_refused_when_entry_point_missing(tmp_path):
    repo = _repo_with_manifest(tmp_path)
    out = apply_self_code_cuts(
        _manifest_cut("Applications/never_landed.py"), repo_root=repo, write_receipt=False
    )
    assert out["any_landed"] is False
    assert "entry_point_missing_on_disk" in out["results"][0]["reason"]
    manifest = json.loads(
        (repo / "Applications/apps_manifest.json").read_text(encoding="utf-8")
    )
    assert list(manifest) == ["Existing App"]


def test_manifest_cut_refuses_bad_json_and_non_object(tmp_path):
    repo = _repo_with_manifest(tmp_path)
    for src in ("not json at all", '["a", "list"]', "{}"):
        cut = (
            "[SELF_CODE_CUT: path=Applications/apps_manifest.json]\n"
            + src
            + "\n[/SELF_CODE_CUT]"
        )
        out = apply_self_code_cuts(cut, repo_root=repo, write_receipt=False)
        assert out["any_landed"] is False, src


def test_other_json_paths_still_refused(tmp_path):
    repo = _repo_with_manifest(tmp_path)
    cut = '[SELF_CODE_CUT: path=System/evil.json]\n{"x": 1}\n[/SELF_CODE_CUT]'
    out = apply_self_code_cuts(cut, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is False
    assert "only_python_organs_or_manifest_merge_in_v2" in out["results"][0]["reason"]


# ── r935 — edit lane: exact old→new strokes on existing tissue ──────────────

def _edit_block(path, old, new):
    return (
        f"[SELF_CODE_EDIT: path={path}]\n<<<OLD\n{old}\n>>>NEW\n{new}\n[/SELF_CODE_EDIT]"
    )


def test_edit_lands_and_compiles(tmp_path):
    repo = _repo(tmp_path)
    organ = repo / "System/live_organ.py"
    organ.write_text("VALUE = 1\nNAME = 'alice'\n", encoding="utf-8")
    out = apply_self_code_cuts(
        _edit_block("System/live_organ.py", "VALUE = 1", "VALUE = 2"),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is True
    assert out["results"][0]["reason"] == "edited_and_compiled"
    assert out["results"][0]["mode"] == "edit"
    assert organ.read_text(encoding="utf-8") == "VALUE = 2\nNAME = 'alice'\n"


def test_edit_refused_when_old_not_found(tmp_path):
    repo = _repo(tmp_path)
    organ = repo / "System/live_organ.py"
    organ.write_text("VALUE = 1\n", encoding="utf-8")
    out = apply_self_code_cuts(
        _edit_block("System/live_organ.py", "VALUE = 99", "VALUE = 2"),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is False
    assert "old_bytes_not_found" in out["results"][0]["reason"]
    assert organ.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_edit_refused_when_ambiguous_with_honest_count(tmp_path):
    repo = _repo(tmp_path)
    organ = repo / "System/live_organ.py"
    organ.write_text("x = 1\ny = 1\nz = 1\n", encoding="utf-8")
    out = apply_self_code_cuts(
        _edit_block("System/live_organ.py", "= 1", "= 2"),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is False
    assert "old_bytes_ambiguous_3_matches" in out["results"][0]["reason"]
    assert organ.read_text(encoding="utf-8") == "x = 1\ny = 1\nz = 1\n"


def test_edit_compile_failure_rolls_back(tmp_path):
    repo = _repo(tmp_path)
    organ = repo / "System/live_organ.py"
    organ.write_text("def f():\n    return 1\n", encoding="utf-8")
    out = apply_self_code_cuts(
        _edit_block("System/live_organ.py", "    return 1", "    return ("),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is False
    assert "edit_compile_failed_rolled_back" in out["results"][0]["reason"]
    assert organ.read_text(encoding="utf-8") == "def f():\n    return 1\n"


def test_edit_refused_on_missing_file(tmp_path):
    repo = _repo(tmp_path)
    out = apply_self_code_cuts(
        _edit_block("System/never_grown.py", "x", "y"),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is False
    assert "edit_target_missing_use_SELF_CODE_CUT_to_create" in out["results"][0]["reason"]


def test_edit_path_law_still_binds(tmp_path):
    repo = _repo(tmp_path)
    out = apply_self_code_cuts(
        _edit_block("Documents/IDE_BOOT_COVENANT.py", "a", "b"),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is False


def test_cut_then_edit_same_reply(tmp_path):
    repo = _repo(tmp_path)
    reply = (
        GOOD_ORGAN
        + "\n"
        + _edit_block(
            "System/swarm_r912_probe_organ.py", 'return "alive"', 'return "alive-and-edited"'
        )
    )
    out = apply_self_code_cuts(reply, repo_root=repo, write_receipt=False)
    assert out["any_landed"] is True
    assert out["attempted"] == 2
    body = (repo / "System/swarm_r912_probe_organ.py").read_text(encoding="utf-8")
    assert "alive-and-edited" in body


def test_edit_old_equals_new_refused(tmp_path):
    repo = _repo(tmp_path)
    (repo / "System/live_organ.py").write_text("x = 1\n", encoding="utf-8")
    out = apply_self_code_cuts(
        _edit_block("System/live_organ.py", "x = 1", "x = 1"),
        repo_root=repo,
        write_receipt=False,
    )
    assert out["any_landed"] is False
    assert "old_equals_new" in out["results"][0]["reason"]


def test_owner_natural_phrasing_opens_hand_r936():
    # r936: "ok alice try to code now" routed to open_app; she never saw the
    # stroke syntax and her fiction guard blocked the prose. Natural owner
    # phrasings must trip the teacher gate.
    from System.swarm_alice_self_coding_hand import is_owner_self_code_execute_request

    assert is_owner_self_code_execute_request("ok alice try to code now updte from ide: ...")
    assert is_owner_self_code_execute_request("alice self_edit your launcher")
    assert is_owner_self_code_execute_request("emit SELF_READ on your hand file")
    assert is_owner_self_code_execute_request("code now")
    assert not is_owner_self_code_execute_request("HAVE U ATTEMPTED?: blah")
    assert not is_owner_self_code_execute_request("what is for dinner")
