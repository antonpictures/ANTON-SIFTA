#!/usr/bin/env python3
"""
sifta_genesis_widget.py — Owner Genesis Ceremony (Visual)
═════════════════════════════════════════════════════════════
The first thing a new owner sees. Full-screen onboarding.

1. "Welcome to SIFTA OS. The Swarm needs to know its owner."
2. Owner selects a photo (face, document, anything).
3. Photo is hashed + bound to silicon serial.
4. Ed25519-signed genesis anchor is created.
5. "Genesis complete. The Swarm is yours."

On subsequent boots: genesis is verified silently.
If photo is missing or tampered: warning displayed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
    QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

from System.sifta_base_widget import SiftaBaseWidget, SIFTA_STYLESHEET
from System.owner_genesis import (
    perform_genesis, verify_genesis, is_genesis_complete,
    GENESIS_FILE, OWNER_DIR,
)


class GenesisWidget(SiftaBaseWidget):
    """Owner Genesis Ceremony — bonds the owner to the silicon."""

    APP_NAME = "Owner Genesis"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self._photo_path = ""

        # Check current genesis state
        vg = verify_genesis()
        if vg["exists"] and vg["status"] == "ACTIVE":
            self._build_verified_ui(layout, vg)
        else:
            self._build_ceremony_ui(layout)

    def _build_ceremony_ui(self, layout: QVBoxLayout):
        """First boot — the genesis ceremony."""

        # Header
        header = QLabel("OWNER GENESIS CEREMONY")
        header.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: rgb(0,255,200); padding: 12px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        msg = QLabel(
            "The Swarm needs to know its owner.\n\n"
            "Select a photo of yourself. It will be SHA-256 hashed and\n"
            "cryptographically bound to this machine's silicon serial.\n"
            "The photo stays LOCAL ONLY — never uploaded, never in git.\n"
            "Only the hash enters the ledger.\n\n"
            "This is the root of all trust."
        )
        msg.setStyleSheet("color: rgb(180,190,220); font-size: 12px; padding: 8px;")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        layout.addSpacing(12)

        # Photo preview
        self.photo_label = QLabel("No photo selected")
        self.photo_label.setStyleSheet(
            "background: rgb(15,13,25); border: 2px dashed rgb(50,45,70);"
            "border-radius: 8px; color: rgb(100,108,140); font-size: 11px;"
            "padding: 20px;"
        )
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setMinimumHeight(200)
        self.photo_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.photo_label, 1)

        # Photo select button
        btn_select = QPushButton("Select Owner Photo")
        btn_select.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 12px 30px;"
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgb(0,80,60), stop:1 rgb(0,50,40));"
            "border: 1px solid rgb(0,255,200); color: rgb(0,255,200); }"
        )
        btn_select.clicked.connect(self._select_photo)
        layout.addWidget(btn_select, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        # Owner name (optional)
        name_row = QHBoxLayout()
        name_lbl = QLabel("Owner name (optional):")
        name_lbl.setStyleSheet("font-size: 11px;")
        name_row.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Ioan George Anton")
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        layout.addSpacing(8)

        # Genesis button (disabled until photo selected)
        self.btn_genesis = QPushButton("PERFORM GENESIS CEREMONY")
        self.btn_genesis.setEnabled(False)
        self.btn_genesis.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 14px 40px; font-weight: bold;"
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgb(60,0,60), stop:1 rgb(40,0,40));"
            "border: 2px solid rgb(255,40,200); color: rgb(255,40,200); }"
            "QPushButton:disabled { border-color: rgb(60,50,70); color: rgb(60,50,70); }"
        )
        self.btn_genesis.clicked.connect(self._perform_genesis)
        layout.addWidget(self.btn_genesis, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: rgb(100,108,140); font-size: 10px; padding: 4px;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)

    def _build_verified_ui(self, layout: QVBoxLayout, vg: dict):
        """Subsequent boots — show genesis status."""

        header = QLabel("OWNER GENESIS — VERIFIED")
        header.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: rgb(0,255,200); padding: 12px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Show photo if present
        if vg["photo_present"]:
            for ext in [".jpg", ".jpeg", ".png", ".heic", ".webp"]:
                p = OWNER_DIR / f"genesis_photo{ext}"
                if p.exists():
                    pixmap = QPixmap(str(p))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            200, 200,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        photo_lbl = QLabel()
                        photo_lbl.setPixmap(scaled)
                        photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        photo_lbl.setStyleSheet(
                            "border: 2px solid rgb(0,255,200); border-radius: 8px; padding: 4px;"
                        )
                        layout.addWidget(photo_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
                    break

        layout.addSpacing(12)

        # Status info
        info_lines = [
            f"Owner:          {vg['owner_name'] or '(unnamed)'}",
            f"Silicon:        {vg['silicon']}",
            f"Generation:     {vg['generation']}",
            f"Signature:      {'VALID' if vg['valid'] else 'INVALID'}",
            f"Photo on disk:  {'YES' if vg['photo_present'] else 'MISSING'}",
            f"Photo matches:  {'YES' if vg['photo_match'] else 'TAMPERED' if vg['photo_present'] else 'N/A'}",
            f"Status:         {vg['status']}",
        ]
        info = QLabel("\n".join(info_lines))
        info.setFont(QFont("Menlo", 11))
        info.setStyleSheet("color: rgb(180,190,220); padding: 12px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        # Warnings
        if not vg["valid"]:
            warn = QLabel("WARNING: Genesis signature is INVALID. The scar may have been tampered with.")
            warn.setStyleSheet("color: rgb(255,60,60); font-weight: bold; padding: 8px;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warn)
        elif not vg["photo_match"] and vg["photo_present"]:
            warn = QLabel("WARNING: Photo on disk does NOT match genesis hash. File was modified.")
            warn.setStyleSheet("color: rgb(255,180,30); font-weight: bold; padding: 8px;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warn)
        elif not vg["photo_present"]:
            warn = QLabel("NOTE: Genesis photo not on local disk. Hash still in ledger.")
            warn.setStyleSheet("color: rgb(255,180,30); padding: 8px;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warn)
        else:
            ok = QLabel("The Swarm knows its owner. All anchors intact.")
            ok.setStyleSheet("color: rgb(0,255,200); font-weight: bold; padding: 8px;")
            ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(ok)

        layout.addStretch()

    # ── Actions ───────────────────────────────────────────────────────

    def _select_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Owner Photo",
            str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.heic *.webp);;All Files (*)",
        )
        if not path:
            return

        self._photo_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                300, 300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.photo_label.setPixmap(scaled)
            self.photo_label.setText("")
        else:
            self.photo_label.setText(f"Selected: {Path(path).name}\n(preview not available)")

        self.btn_genesis.setEnabled(True)
        self.status_lbl.setText(f"Photo selected: {Path(path).name}")

    def _perform_genesis(self):
        if not self._photo_path:
            return

        owner_name = self.name_input.text().strip()

        reply = QMessageBox.question(
            self,
            "Confirm Genesis",
            f"Bind this photo to this silicon?\n\n"
            f"Photo: {Path(self._photo_path).name}\n"
            f"Owner: {owner_name or '(unnamed)'}\n\n"
            f"This creates the cryptographic root of trust.\n"
            f"The photo stays LOCAL ONLY.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            scar = perform_genesis(self._photo_path, owner_name)
            QMessageBox.information(
                self,
                "Genesis Complete",
                f"The Swarm is yours.\n\n"
                f"Silicon:  {scar['silicon']}\n"
                f"Anchor:   {scar['genesis_anchor'][:32]}...\n"
                f"Signed:   {scar['sig'][:24]}...\n"
                f"Gen:      {scar['generation']}\n\n"
                f"Photo stored locally at:\n{OWNER_DIR}",
            )
            self.set_status("Genesis complete")
            self.btn_genesis.setEnabled(False)
            self.status_lbl.setText("Genesis ceremony completed. Restart the OS to see verified status.")
        except Exception as e:
            QMessageBox.critical(self, "Genesis Failed", f"Error: {e}")


# ── Standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = GenesisWidget()
    w.resize(600, 700)
    w.setWindowTitle("Owner Genesis — SIFTA OS")
    w.show()
    sys.exit(app.exec())
