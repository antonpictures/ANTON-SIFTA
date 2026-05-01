import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


REPO = Path(__file__).resolve().parents[1]


def test_protein_colosseum_manifest_uses_python_widget():
    manifest = json.loads((REPO / "Applications/apps_manifest.json").read_text())
    entry = manifest["C55M + George - Protein Fold Colosseum"]

    assert entry["entry_point"] == "Applications/sifta_protein_folder_widget.py"
    assert entry["widget_class"] == "ProteinFolderWidget"
    assert entry["window_width"] >= 1100
    assert "no browser/HTML escape" in entry["description"]


def test_protein_colosseum_source_has_no_browser_escape():
    source = (REPO / "Applications/sifta_protein_folder_widget.py").read_text()

    forbidden = [
        "import webbrowser",
        "webbrowser.open",
        "setHtml(",
        "QWebEngine",
        "protein_viewer.html",
        "build_html_viewer",
        "<!DOCTYPE",
        "<script",
    ]
    for token in forbidden:
        assert token not in source


def test_protein_colosseum_widget_imports_and_constructs():
    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_protein_folder_widget import ProteinFolderWidget

    app = QApplication.instance() or QApplication([])
    widget = ProteinFolderWidget()
    try:
        assert widget.objectName() == "ProteinFolderWidget"
        assert widget.seq_input.text()
        assert widget.engine_combo.currentText() in {"c55m_hp_lattice", "toy"}
        assert "phenotype" in widget.metrics
        assert "optic" in widget.metrics
        assert widget.metrics["optic"].text() in {"ModernGL ready", "CPU fallback"}
        assert hasattr(widget, "phenotype_gl_widget")
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            assert widget.phenotype_gl_widget is None
    finally:
        widget._timer.stop()
        if widget._worker_thread is not None:
            widget._worker_thread.quit()
            widget._worker_thread.wait(1000)
        widget.close()
