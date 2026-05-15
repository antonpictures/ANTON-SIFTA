from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_wallpaper_text_edit_paints_nonblack_background(tmp_path):
    from PyQt6.QtGui import QColor, QImage, QPainter
    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_talk_to_alice_widget import _WallpaperTextEdit

    app = QApplication.instance() or QApplication(sys.argv)

    bg = QImage(128, 96, QImage.Format.Format_ARGB32)
    bg.fill(QColor(204, 150, 38, 255))
    bg_path = tmp_path / "chat_wallpaper.png"
    assert bg.save(str(bg_path))

    widget = _WallpaperTextEdit()
    widget.resize(360, 240)
    widget.setReadOnly(True)
    widget.setStyleSheet(
        "QTextEdit { background: transparent; color: white; border: 0; "
        "font-size: 15px; font-weight: 700; padding: 8px; }"
    )
    assert widget.set_wallpaper_path(bg_path)
    widget.setPlainText("Alice\nrender proof")
    widget.show()
    app.processEvents()

    rendered = QImage(widget.size(), QImage.Format.Format_ARGB32)
    rendered.fill(QColor(0, 0, 0, 255))
    painter = QPainter(rendered)
    widget.render(painter)
    painter.end()

    samples = 0
    nonblack = 0
    for y in range(60, rendered.height(), 20):
        for x in range(60, rendered.width(), 20):
            color = QColor(rendered.pixel(x, y))
            samples += 1
            if color.red() > 18 or color.green() > 18 or color.blue() > 18:
                nonblack += 1

    assert samples > 0
    assert nonblack > samples * 0.8
