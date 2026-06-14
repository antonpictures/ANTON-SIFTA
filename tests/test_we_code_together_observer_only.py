from __future__ import annotations

import py_compile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
APP = REPO / "Applications" / "sifta_we_code_together.py"


def test_we_code_together_is_observer_only() -> None:
    source = APP.read_text(encoding="utf-8")

    forbidden = [
        "QPushButton",
        "QFileDialog",
        "QMessageBox",
        "Open File",
        "Compile Check",
        "Save + Receipt",
        "_open_file",
        "_compile_check",
        "_save_and_receipt",
        "body_file_saved",
    ]
    for text in forbidden:
        assert text not in source

    required = [
        "George types to Alice in Talk",
        "no buttons, no editor, no manual saves",
        "STGM / MIMO BORG TRACES",
        "TEACHER ARMS / OWNER LAW",
        "GEORGE TYPES ONLY TO ALICE IN GLOBAL CHAT",
        "_mimo_trace_rows",
        "_teacher_guidance_lines",
    ]
    for text in required:
        assert text in source


def test_we_code_together_compiles() -> None:
    py_compile.compile(str(APP), doraise=True)
