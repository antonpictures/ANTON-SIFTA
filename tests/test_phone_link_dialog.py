import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from Applications.sifta_phone_link_dialog import PhoneLinkDialog, qr_pixmap
from System import sifta_phone_link as phone


def test_settings_pairing_panel_and_qr(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(phone, 'lan_addresses', lambda: ['192.168.1.10'])
    monkeypatch.setattr(phone, 'ollama_json', lambda *_: {'models': [
        {'name': 'local', 'size': 6_300_000_000}, {'name': 'remote:cloud', 'size': 100}]})
    dialog = PhoneLinkDialog()
    assert dialog.model.count() == 1
    assert '6.3 GB' in dialog.model.itemText(0)
    assert dialog.address.currentText() == '192.168.1.10'
    assert not dialog.copy_btn.isEnabled()
    pixmap = qr_pixmap('http://192.168.1.10:8123/#pair=test')
    assert not pixmap.isNull() and pixmap.width() >= 200
    dialog.show()
    app.processEvents()
    assert dialog.width() < 1000 and dialog.height() < 900
    dialog.close()
