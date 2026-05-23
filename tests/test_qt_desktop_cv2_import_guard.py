from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def test_face_recognition_import_stays_cv2_free_in_qt_desktop(monkeypatch):
    monkeypatch.setenv("SIFTA_DISABLE_CV2_IN_QT_DESKTOP", "1")
    monkeypatch.delenv("SIFTA_FORCE_CV2", raising=False)
    sys.modules.pop("System.swarm_architect_face_recognition", None)
    sys.modules.pop("cv2", None)

    mod = importlib.import_module("System.swarm_architect_face_recognition")

    assert "cv2" not in sys.modules
    with pytest.raises(RuntimeError, match="cv2 disabled in Qt desktop process"):
        mod._load_cv2()


def test_brainstem_surprise_path_no_longer_imports_cv2_directly():
    text = Path("System/swarm_boot.py").read_text(encoding="utf-8")

    assert "import cv2" not in text
    assert "from PIL import Image" in text
