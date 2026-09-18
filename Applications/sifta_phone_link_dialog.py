"""Local-only phone pairing controls, opened from SIFTA Network settings."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout,
                            QLabel, QPushButton, QVBoxLayout)

from System import sifta_phone_link as phone


def qr_pixmap(url):
    try:
        import qrcode
    except ModuleNotFoundError:
        raise RuntimeError(
            "Lipseste modulul 'qrcode'. Instaleaza-l cu: "
            "/usr/local/bin/python3 -m pip install qrcode"
        ) from None
    qr = qrcode.QRCode(border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    cells = qr.get_matrix()
    scale = max(3, 280 // len(cells))
    pixmap = QPixmap(len(cells)*scale, len(cells)*scale)
    pixmap.fill(QColor('white'))
    painter = QPainter(pixmap)
    for y, row in enumerate(cells):
        for x, dark in enumerate(row):
            if dark:
                painter.fillRect(x*scale, y*scale, scale, scale, QColor('black'))
    painter.end()
    return pixmap


class PhoneLinkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Alice / Telefon local')
        self.setMinimumWidth(370)
        self.url = ''
        root = QVBoxLayout(self)
        title = QLabel('Alice pe telefonul tau')
        title.setStyleSheet('font: 26px Georgia; padding: 12px 0;')
        root.addWidget(title)
        help_text = QLabel('1. Telefonul si laptopul pe acelasi Wi-Fi.\n'
                           '2. Alege modelul local si porneste legatura.\n'
                           '3. Scaneaza QR-ul si apasa Conecteaza pe telefon.\n\n'
                           'Fara cont, abonament sau cloud. Laptopul trebuie sa ramana pornit.\n'
                           'HTTP necriptat: foloseste numai o retea de incredere.\n'
                           'Chat text; nu acorda acces la comenzi, camera sau fisiere.')
        help_text.setWordWrap(True)
        root.addWidget(help_text)
        self.address = QComboBox()
        self.address.addItems(phone.lan_addresses())
        root.addWidget(QLabel('Adresa laptopului in reteaua locala'))
        root.addWidget(self.address)
        self.model = QComboBox()
        root.addWidget(QLabel('Model instalat in Ollama'))
        root.addWidget(self.model)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.qr)
        root.addWidget(self.status)
        buttons = QHBoxLayout()
        self.start_btn = QPushButton('Porneste / QR nou')
        self.copy_btn = QPushButton('Copiaza linkul')
        self.stop_btn = QPushButton('Opreste si revoca')
        self.start_btn.clicked.connect(self.start_link)
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.url))
        self.stop_btn.clicked.connect(self.stop_link)
        for button in (self.start_btn, self.copy_btn, self.stop_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        refresh = QPushButton('Reverifica modelele / reteaua')
        refresh.clicked.connect(self.refresh_choices)
        root.addWidget(refresh)
        self.copy_btn.setEnabled(False)
        self.refresh_choices()

    def refresh_choices(self):
        try:
            self.address.clear()
            self.address.addItems(phone.lan_addresses())
            self.model.clear()
            for model in phone.ollama_json('/api/tags').get('models', []):
                name = str(model.get('name') or '')
                if name and not model.get('remote_host') and 'cloud' not in name.lower():
                    size = float(model.get('size') or 0) / 1e9
                    self.model.addItem(f'{name} / {size:.1f} GB', name)
            from System.sifta_inference_defaults import resolve_ollama_model
            index = self.model.findData(resolve_ollama_model(app_context='talk_to_alice'))
            if index >= 0:
                self.model.setCurrentIndex(index)
            self.status.setText('Legatura este oprita.' if phone.active_link is None else
                                f'Legatura activa: {phone.active_link.origin}\nQR nou pentru alt telefon; Opreste revoca toate telefoanele.')
        except Exception:
            self.status.setText('Ollama nu raspunde. Porneste Ollama si reverifica modelele.')

    def start_link(self):
        try:
            address, model = self.address.currentText(), self.model.currentData()
            if not address or not model:
                raise ValueError('Alege o adresa Wi-Fi si un model local instalat.')
            if phone.active_link:
                if phone.active_link.model != model or not phone.active_link.origin.startswith(f'http://{address}:'):
                    raise ValueError('Opreste legatura inainte de a schimba modelul sau reteaua.')
                url = phone.active_link.new_ticket()
                pixmap = qr_pixmap(url)
            else:
                # Verify dependencies and weights before opening a network listener.
                qr_pixmap('SIFTA')
                phone.verify_local_model(model)
                link = phone.PhoneLink(model)
                url = link.start(address)
                phone.active_link = link
                pixmap = qr_pixmap(url)
            self.url = url
            self.qr.setPixmap(pixmap)
            self.copy_btn.setEnabled(True)
            self.status.setText(f'{phone.active_link.origin}\nCod unic, valabil 5 minute. Conexiunea telefonului expira dupa 12 ore.\n'
                                'Inchiderea acestui panou pastreaza legatura; Opreste revoca accesul.')
        except Exception as exc:
            self.status.setText(f'Nu s-a putut conecta: {exc}')

    def stop_link(self):
        if phone.active_link:
            phone.active_link.stop()
            phone.active_link = None
        self.url = ''
        self.qr.clear()
        self.copy_btn.setEnabled(False)
        self.status.setText('Oprit. Toate telefoanele au fost deconectate.')
