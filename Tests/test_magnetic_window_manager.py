import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication, QMdiArea, QWidget

from sifta_os_desktop import (
    MagneticSubWindow,
    clamp_mdi_subwindow_top_left,
    resolve_mdi_subwindow_position,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def mdi(qapp):
    area = QMdiArea()
    area.resize(500, 400)
    area.show()
    qapp.processEvents()
    yield area
    area.closeAllSubWindows()
    area.close()
    qapp.processEvents()


def _sub(area: QMdiArea, rect: QRect) -> MagneticSubWindow:
    sub = MagneticSubWindow()
    sub.setWidget(QWidget())
    area.addSubWindow(sub)
    sub.setGeometry(rect)
    sub.show()
    QApplication.processEvents()
    return sub


def test_clamp_keeps_window_inside_viewport():
    viewport = QRect(0, 0, 500, 400)
    assert clamp_mdi_subwindow_top_left(480, 390, 200, 120, viewport) == (300, 280)
    assert clamp_mdi_subwindow_top_left(-50, -20, 200, 120, viewport) == (0, 0)


def test_resolve_position_uses_full_rect_intersection(mdi):
    first = _sub(mdi, QRect(30, 30, 200, 200))
    new_sub = MagneticSubWindow()
    new_sub.setWidget(QWidget())
    mdi.addSubWindow(new_sub)
    x, y = resolve_mdi_subwindow_position(mdi, new_sub, 200, 200, 30, 30)
    candidate = QRect(x, y, 200, 200)
    assert not candidate.intersects(first.geometry())
    assert QRect(0, 0, 500, 400).contains(candidate)


def test_resolve_position_is_bounded_when_viewport_is_crowded(mdi):
    blocker = _sub(mdi, QRect(0, 0, 500, 400))
    x, y = resolve_mdi_subwindow_position(mdi, blocker, 200, 120, 480, 390, max_attempts=8)
    candidate = QRect(x, y, 200, 120)
    assert QRect(0, 0, 500, 400).contains(candidate)


def test_magnetic_snap_uses_exclusive_edges_and_clamps(mdi, qapp):
    _sub(mdi, QRect(10, 10, 100, 100))
    moving = _sub(mdi, QRect(128, 20, 100, 100))

    moving.move(109, 20)
    qapp.processEvents()

    assert moving.x() == 110
    assert moving.y() == 20
    assert QRect(0, 0, 500, 400).contains(moving.geometry())
