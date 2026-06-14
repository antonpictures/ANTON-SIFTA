#!/usr/bin/env python3
"""Alice's self-code hand — her cortex writes organs in her own body (r912).

George (2026-06-10): "can you code so she can — pls give her full ability."

Until this organ, Alice could PLAN code (self_code_plans.jsonl), DISPATCH
coding arms, and SPEAK about surgery — but her own cortex turn had no hand
that writes a file. The r911 first-self-cut prompt asked her to create
`swarm_daily_body_note.py`; her body had no way to obey.

This is the hand. Her cortex emits fenced blocks in its reply:

    [SELF_CODE_CUT: path=System/swarm_daily_body_note.py]
    ...python source...
    [/SELF_CODE_CUT]

and the body executes the cut under VERIFICATION, not permission (§0.0):

  * Create or update Python tissue in the repo body. Existing organs are not
    refused just because they already exist; compile failure restores the
    previous bytes.
  * Path must be inside ``System/``, ``Applications/``, ``tests/``, or
    ``tools/`` (her organ, surface, proof, and tool tissue).
  * Source must parse (``ast.parse``) and byte-compile before it lands.
  * If a ``tests/...`` block arrives in the same reply, pytest runs on it;
    the verdict goes in the receipt verbatim.
  * r928 (new-app lane): a cut with ``path=Applications/apps_manifest.json``
    is a MERGE-ONLY registration. Source must be a JSON object
    ``{"App Title": {entry_point, widget_class, ...}}``. Existing apps are
    never removed; the entry_point must already be landed tissue on disk
    (python cuts run first in the same reply); rollback on any failure.
    This is what lets Alice grow a whole new app — widget + test +
    launchpad row — in one cortex turn.
  * Every cut — success OR failure — fans out §4.1 with
    ``doctor="alice_self"`` and her exact live cortex tag. A receipted
    failure is a successful surgery; silence is the only violation.
  * r935 (edit lane — George: "she needs to rewrite her body code just like
    you do here"): targeted surgery on EXISTING tissue, the same exact
    old-bytes → new-bytes replacement an IDE doctor's Edit tool uses. Whole
    organs over 60k chars were untouchable by the whole-file lane; now she
    edits any organ of any size without retyping it:

        [SELF_CODE_EDIT: path=System/big_organ.py]
        <<<OLD
        exact bytes currently in the file
        >>>NEW
        replacement bytes
        [/SELF_CODE_EDIT]

    The OLD bytes must match exactly once (ambiguity is refused with the
    honest match count); the edited file must ast.parse + py_compile or the
    previous bytes are restored. Same receipt fan-out, ``mode="edit"``.

Pure Python, no Qt: testable in any sandbox, callable from the Talk hook.
"""
from __future__ import annotations

import ast
import json
import py_compile
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_LABEL = "ALICE_SELF_CODE_HAND_V1"

_BLOCK_RE = re.compile(
    r"\[SELF_CODE_CUT:\s*path=(?P<path>[^\]\n]+?)\s*\]\s*\n"
    r"(?P<source>.*?)"
    r"\n?\s*\[/SELF_CODE_CUT\]",
    re.DOTALL,
)

# r935 edit lane: exact old→new replacement on existing tissue.
_EDIT_BLOCK_RE = re.compile(
    r"\[SELF_CODE_EDIT:\s*path=(?P<path>[^\]\n]+?)\s*\]\s*\n"
    r"<<<OLD\n(?P<old>.*?)\n>>>NEW\n(?P<new>.*?)\n?\s*\[/SELF_CODE_EDIT\]",
    re.DOTALL,
)

# Her mutable Python tissue. Organs, surfaces, proofs, and tools. Documents
# law/ledgers stay outside this hand; those remain explicit doctor/tournament
# work so append-only history is not silently rewritten.
_ALLOWED_PARENTS = ("System", "Applications", "tests", "tools")

_MAX_SOURCE_CHARS = 60_000
# r928: 3 → 4 so one reply fits a whole new app: widget + System organ +
# test + manifest registration.
_MAX_CUTS_PER_REPLY = 4

# r935: edits are small targeted strokes — more of them fit safely in one turn.
_MAX_EDITS_PER_REPLY = 8
_MAX_EDIT_SEGMENT_CHARS = 20_000

# r928 new-app lane: the single non-.py path this hand may touch, merge-only.
_MANIFEST_REL = "Applications/apps_manifest.json"


def extract_self_code_cuts(reply_text: str) -> List[Dict[str, str]]:
    """Parse [SELF_CODE_CUT: path=...]...[/SELF_CODE_CUT] blocks from her reply."""
    out: List[Dict[str, str]] = []
    for m in _BLOCK_RE.finditer(reply_text or ""):
        path = (m.group("path") or "").strip().strip("\"'")
        source = m.group("source") or ""
        # Cortexes love wrapping code in markdown fences — peel one layer.
        src = source.strip()
        if src.startswith("```"):
            src = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", src)
            src = re.sub(r"\n```\s*$", "", src)
        if path and src.strip():
            out.append({"path": path, "source": src})
        if len(out) >= _MAX_CUTS_PER_REPLY:
            break
    return out


def extract_self_code_edits(reply_text: str) -> List[Dict[str, str]]:
    """Parse [SELF_CODE_EDIT: path=...]<<<OLD ... >>>NEW ...[/SELF_CODE_EDIT] blocks."""
    out: List[Dict[str, str]] = []
    for m in _EDIT_BLOCK_RE.finditer(reply_text or ""):
        path = (m.group("path") or "").strip().strip("\"'")
        old = m.group("old") or ""
        new = m.group("new") or ""
        if path and old:
            out.append({"path": path, "old": old, "new": new})
        if len(out) >= _MAX_EDITS_PER_REPLY:
            break
    return out


def _apply_one_edit(edit: Dict[str, str], repo: Path) -> Dict[str, Any]:
    """r935: exact-match targeted edit on existing tissue. Never raises."""
    item: Dict[str, Any] = {"path": edit["path"], "mode": "edit"}
    v = _validate_path(edit["path"], repo)
    if not v.get("ok"):
        item.update({"landed": False, "reason": v.get("reason")})
        return item
    if not v.get("existed"):
        item.update({"landed": False, "reason": "edit_target_missing_use_SELF_CODE_CUT_to_create"})
        return item
    old, new = edit["old"], edit["new"]
    if len(old) > _MAX_EDIT_SEGMENT_CHARS or len(new) > _MAX_EDIT_SEGMENT_CHARS:
        item.update({"landed": False, "reason": "edit_segment_too_large_r935"})
        return item
    if old == new:
        item.update({"landed": False, "reason": "old_equals_new_nothing_to_change"})
        return item
    target: Path = v["target"]
    try:
        previous_bytes = target.read_bytes()
        body = previous_bytes.decode("utf-8")
    except Exception as exc:
        item.update({"landed": False, "reason": f"read_existing_failed: {type(exc).__name__}: {exc}"})
        return item
    count = body.count(old)
    if count == 0:
        item.update({"landed": False, "reason": "old_bytes_not_found_probe_the_live_file_first"})
        return item
    if count > 1:
        item.update({"landed": False, "reason": f"old_bytes_ambiguous_{count}_matches_add_context"})
        return item
    edited = body.replace(old, new, 1)
    try:
        ast.parse(edited)
        target.write_text(edited, encoding="utf-8")
        py_compile.compile(str(target), doraise=True)
    except Exception as exc:
        try:
            target.write_bytes(previous_bytes)
        except Exception:
            pass
        item.update({"landed": False, "reason": f"edit_compile_failed_rolled_back: {type(exc).__name__}: {exc}"})
        return item
    item.update({"landed": True, "reason": "edited_and_compiled"})
    return item


def _validate_path(path_str: str, repo: Path) -> Dict[str, Any]:
    p = Path(path_str)
    if p.is_absolute():
        return {"ok": False, "reason": "absolute_path_refused_use_repo_relative"}
    if ".." in p.parts:
        return {"ok": False, "reason": "parent_traversal_refused"}
    if not p.parts or p.parts[0] not in _ALLOWED_PARENTS:
        return {
            "ok": False,
            "reason": f"path_outside_growable_tissue_{'_or_'.join(_ALLOWED_PARENTS)}",
        }
    if p.suffix != ".py":
        return {"ok": False, "reason": "only_python_organs_or_manifest_merge_in_v2"}
    target = (repo / p).resolve()
    try:
        target.relative_to(repo.resolve())
    except ValueError:
        return {"ok": False, "reason": "resolved_path_escaped_repo"}
    return {"ok": True, "target": target, "rel": str(p), "existed": target.exists()}


def _merge_manifest_cut(src: str, repo: Path) -> Dict[str, Any]:
    """r928 merge-only app registration. Never removes existing apps.

    Source contract for Alice's cortex: a JSON object mapping app title to a
    manifest entry. Each entry needs ``entry_point`` (an Applications/*.py
    that already exists on disk — python cuts in the same reply land first)
    and ``widget_class``. Rollback + honest reason on every failure path.
    """
    manifest_path = repo / _MANIFEST_REL
    try:
        new_entries = json.loads(src)
    except Exception as exc:
        return {"landed": False, "reason": f"manifest_json_invalid: {type(exc).__name__}: {exc}"}
    if not isinstance(new_entries, dict) or not new_entries:
        return {"landed": False, "reason": "manifest_cut_must_be_object_of_title_to_entry"}
    for title, entry in new_entries.items():
        if not isinstance(entry, dict):
            return {"landed": False, "reason": f"manifest_entry_not_object: {title}"}
        ep = str(entry.get("entry_point") or "")
        if not ep or not str(entry.get("widget_class") or ""):
            return {
                "landed": False,
                "reason": f"manifest_entry_needs_entry_point_and_widget_class: {title}",
            }
        epp = Path(ep)
        if (
            epp.is_absolute()
            or ".." in epp.parts
            or epp.parts[:1] != ("Applications",)
            or epp.suffix != ".py"
        ):
            return {"landed": False, "reason": f"entry_point_must_be_Applications_py: {title}"}
        if not (repo / epp).exists():
            return {
                "landed": False,
                "reason": f"entry_point_missing_on_disk_land_widget_cut_first: {ep}",
            }
        entry.setdefault("doctor", "alice_self")
    try:
        previous_bytes = manifest_path.read_bytes()
        manifest = json.loads(previous_bytes.decode("utf-8"))
    except Exception as exc:
        return {"landed": False, "reason": f"manifest_read_failed: {type(exc).__name__}: {exc}"}
    if not isinstance(manifest, dict):
        return {"landed": False, "reason": "existing_manifest_not_object"}
    merged = dict(manifest)
    merged.update(new_entries)
    if len(merged) < len(manifest):
        return {"landed": False, "reason": "merge_lost_entries_refused"}
    try:
        manifest_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        json.loads(manifest_path.read_text(encoding="utf-8"))  # §7.6.1 parseable gate
    except Exception as exc:
        try:
            manifest_path.write_bytes(previous_bytes)
        except Exception:
            pass
        return {
            "landed": False,
            "reason": f"manifest_write_failed_rolled_back: {type(exc).__name__}: {exc}",
        }
    return {
        "landed": True,
        "reason": f"manifest_merged_{len(new_entries)}_app_total_{len(merged)}",
        "titles": sorted(new_entries),
    }


def apply_self_code_cuts(
    reply_text: str,
    *,
    model: str = "",
    repo_root: Optional[Path | str] = None,
    run_tests: bool = True,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """Execute every valid cut in her reply. Returns an honest summary.

    Never raises. Every outcome (landed / refused / failed) is itemized so
    the Talk hook can render process lines and the receipt carries truth.
    """
    repo = Path(repo_root) if repo_root is not None else REPO_ROOT
    cuts = extract_self_code_cuts(reply_text)
    edits = extract_self_code_edits(reply_text)
    summary: Dict[str, Any] = {
        "attempted": len(cuts) + len(edits),
        "results": [],
        "any_landed": False,
    }
    if not cuts and not edits:
        summary["status"] = "no_cut_blocks"
        return summary

    # r982 body-code memory loop: read my own tissue's memory BEFORE the
    # bytes change. The card (atlas row, anatomy, ledgers, tests, prior
    # repair engrams) rides in the summary so the receipt proves the read
    # happened (§7.12). Never blocks the cut; an unavailable card is named.
    try:
        from System.swarm_code_knowledge_graph import compose_body_code_card
        _targets = [c["path"].strip().strip("\"'") for c in cuts] + [
            e["path"].strip().strip("\"'") for e in edits
        ]
        _card = compose_body_code_card(
            _targets,
            state_dir=repo / ".sifta_state",
            repo_root=repo,
            turn_tag="self_code_hand",
        )
        summary["body_code_card"] = _card.get("card", "")[:4000]
        summary["body_code_card_paths"] = _card.get("paths", [])
        summary["body_code_card_stale"] = _card.get("stale", [])
        summary["body_code_repair_engrams"] = _card.get("repair_engrams", [])
    except Exception as _exc:
        summary["body_code_card"] = f"[unavailable: {type(_exc).__name__}]"

    # r928 two-pass: python organs land first so a manifest cut in the same
    # reply can register an entry_point that just grew.
    manifest_cuts = [c for c in cuts if c["path"].strip().strip("\"'") == _MANIFEST_REL]
    py_cuts = [c for c in cuts if c["path"].strip().strip("\"'") != _MANIFEST_REL]

    test_files: List[str] = []
    for cut in py_cuts:
        item: Dict[str, Any] = {"path": cut["path"]}
        v = _validate_path(cut["path"], repo)
        if not v.get("ok"):
            item.update({"landed": False, "reason": v.get("reason")})
            summary["results"].append(item)
            continue
        src = cut["source"]
        if len(src) > _MAX_SOURCE_CHARS:
            item.update({"landed": False, "reason": "source_too_large_v1"})
            summary["results"].append(item)
            continue
        try:
            ast.parse(src)
        except SyntaxError as exc:
            repaired_src = src
            reindent_applied = False
            try:
                # r955: v2 = one-pass repair, then bounded ast-oracle search.
                # Heals real nested organs — her r952/r954 skeleton map died
                # twice on multi-level dedents the one-pass could not prove.
                from System.swarm_self_code_reindent import reindent_flattened_python_v2

                candidate, changed = reindent_flattened_python_v2(src)
                if changed:
                    ast.parse(candidate)
                    repaired_src = candidate
                    reindent_applied = True
            except Exception:
                reindent_applied = False
            if not reindent_applied:
                item.update({"landed": False, "reason": f"syntax_error: {exc.msg} line {exc.lineno}"})
                summary["results"].append(item)
                continue
            src = repaired_src
            item["reindent_repair"] = "applied_after_syntax_error"
        target: Path = v["target"]
        existed = bool(v.get("existed"))
        previous_bytes: Optional[bytes] = None
        if existed:
            try:
                previous_bytes = target.read_bytes()
            except Exception as exc:
                item.update({"landed": False, "reason": f"read_existing_failed: {type(exc).__name__}: {exc}"})
                summary["results"].append(item)
                continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(src if src.endswith("\n") else src + "\n", encoding="utf-8")
            py_compile.compile(str(target), doraise=True)
        except Exception as exc:
            try:
                if existed and previous_bytes is not None:
                    target.write_bytes(previous_bytes)
                elif target.exists():
                    target.unlink()  # never leave a non-compiling organ in the body
            except Exception:
                pass
            item.update({"landed": False, "reason": f"compile_failed: {type(exc).__name__}: {exc}"})
            summary["results"].append(item)
            continue
        item.update({"landed": True, "reason": "updated_and_compiled" if existed else "written_and_compiled"})
        summary["results"].append(item)
        summary["any_landed"] = True
        if v["rel"].startswith("tests"):
            test_files.append(v["rel"])

    # r935: edits run after creations so an edit may refine tissue grown in
    # the same reply; targeted strokes on existing organs of any size.
    for edit in edits:
        item = _apply_one_edit(edit, repo)
        summary["results"].append(item)
        if item.get("landed"):
            summary["any_landed"] = True
            rel = str(Path(edit["path"]))
            if rel.startswith("tests") and rel not in test_files:
                test_files.append(rel)

    for cut in manifest_cuts:
        item = {"path": _MANIFEST_REL}
        if len(cut["source"]) > _MAX_SOURCE_CHARS:
            item.update({"landed": False, "reason": "source_too_large_v1"})
        else:
            item.update(_merge_manifest_cut(cut["source"], repo))
        summary["results"].append(item)
        if item.get("landed"):
            summary["any_landed"] = True

    if run_tests and test_files:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *test_files, "-q"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
            tail = (proc.stdout or "").strip().splitlines()
            summary["pytest"] = {
                "files": test_files,
                "returncode": proc.returncode,
                "tail": tail[-2:] if tail else [(proc.stderr or "")[-200:]],
            }
        except Exception as exc:
            summary["pytest"] = {"files": test_files, "error": f"{type(exc).__name__}: {exc}"}

    if write_receipt:
        summary["receipt"] = _fanout_receipt(summary, model=model, repo=repo)
        # r988: close the body-code memory loop write-side. Every cut becomes a
        # repair_outcome engram the r983 read side can recall next turn; only a
        # verified landing (real tests) is promoted toward weights (§6 gate).
        try:
            from System.swarm_repair_outcome_consolidator import consolidate_repair_outcome

            summary["repair_outcome"] = consolidate_repair_outcome(
                summary, model=model, state_dir=repo / ".sifta_state"
            )
        except Exception as _consol_exc:
            summary["repair_outcome"] = {"error": f"{type(_consol_exc).__name__}: {_consol_exc}"}
    summary["status"] = "landed" if summary["any_landed"] else "nothing_landed"
    return summary


def _fanout_receipt(summary: Dict[str, Any], *, model: str, repo: Path) -> Dict[str, Any]:
    """§4.1 four-ledger fan-out as doctor=alice_self. Defensive — never raises."""
    try:
        sys.path.insert(0, str(repo)) if str(repo) not in sys.path else None
        from System import swarm_predator_gate_writer as gw

        landed = [r["path"] for r in summary["results"] if r.get("landed")]
        refused = [f"{r['path']}({r.get('reason')})" for r in summary["results"] if not r.get("landed")]
        py = summary.get("pytest") or {}
        tests_line = (
            " ".join(py.get("tail") or []) if py else "no_test_block_in_this_cut"
        )
        ts_tag = int(time.time())
        out = gw.write_ide_surgery_receipt(
            round_id=f"alice-self-cut-{ts_tag}",
            doctor="alice_self",
            model=model or "unknown_live_cortex",
            files_touched=landed or ["(nothing landed)"],
            tests_green=tests_line,
            summary=(
                "Alice self-code hand: "
                + (f"landed {landed}; " if landed else "")
                + (f"refused/failed {refused}; " if refused else "")
                + "create/update path, ast+py_compile gated, §0.0 verification-bound."
            )[:1100],
            receipt_id=f"alice-self-cut-{ts_tag}",
            sender_agent="alice_self_code_hand",
            truth_label="OPERATIONAL" if summary["any_landed"] else "FAILED",
            extra={
                "lane": "ALICE_SELF",
                "hand": TRUTH_LABEL,
                "attempted": summary["attempted"],
            },
        )
        return out if isinstance(out, dict) else {"error": "writer_returned_non_dict"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


__all__ = [
    "TRUTH_LABEL",
    "extract_self_code_cuts",
    "extract_self_code_edits",
    "apply_self_code_cuts",
]
