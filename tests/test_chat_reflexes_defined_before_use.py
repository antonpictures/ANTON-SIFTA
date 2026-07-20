#!/usr/bin/env python3
"""Regression guard for the chat_reflexes_enabled use-before-define disease.

Twice now this exact bug has aborted Alice:
  - r1354: UnboundLocalError in _start_brain (used at 32348, assigned at 32670).
  - 2026-06-21 crash: NameError in _on_stt_done (used before any assignment).

Both are the same class: a method references `chat_reflexes_enabled` before it is
assigned in that method's scope. A Python exception in a Qt slot -> PyQt6 abort().

This test AST-scans the Talk widget and fails if ANY function references
`chat_reflexes_enabled` with a Load before its first Store. It catches the third
method before it crashes, instead of re-patching method by method.
"""
import ast
import pathlib

TALK = (
    pathlib.Path(__file__).resolve().parents[1]
    / "Applications"
    / "sifta_talk_to_alice_widget.py"
)
NAME = "chat_reflexes_enabled"


def _offenders():
    tree = ast.parse(TALK.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            refs = sorted(
                (n.lineno, n.col_offset, type(n.ctx).__name__)
                for n in ast.walk(node)
                if isinstance(n, ast.Name) and n.id == NAME
            )
            if refs and refs[0][2] != "Store":
                bad.append((node.name, refs[0][0], refs[0][2]))
    return bad


def test_chat_reflexes_enabled_defined_before_use():
    bad = _offenders()
    assert not bad, (
        f"{NAME} is used before assignment in: {bad}. "
        f"Add `{NAME} = _allow_pre_cortex_chat_reflexes()` before its first use "
        f"in each listed method (same fix as r1354)."
    )


if __name__ == "__main__":
    b = _offenders()
    print("OFFENDERS:", b if b else "none — clean")
    raise SystemExit(1 if b else 0)
