#!/usr/bin/env python3
"""
sifta_iot_connector.py — Swarm IoT Gateway & Form
═══════════════════════════════════════════════════════════════════════════════
Extends SIFTA's nervous system into the smart home by cataloging
physical hardware (appliances, smart bulbs, doors) into its context.
"""

import sys
import json
import socket
from pathlib import Path

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFrame
)
from PyQt6.QtCore import Qt

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget

IOT_REGISTRY_FILE = _REPO / ".sifta_state" / "iot_devices.json"

class IoTConnectorWidget(SiftaBaseWidget):
    APP_NAME = "IoT Swarm Connector"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.set_status("Initializing Home IoT Gateway...")
        
        # Make state directory if it doesn't exist
        IOT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not IOT_REGISTRY_FILE.exists():
            with open(IOT_REGISTRY_FILE, "w") as f:
                json.dump({"devices": []}, f)

        # ─── Form Area ────────────────────────────────────────────────────────
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame { background: #121420; border: 1px solid #3b4261; border-radius: 6px; }
            QLabel { border: none; background: transparent; color: #a9b1d6; font-size: 11px; }
        """)
        form_layout = QVBoxLayout(form_frame)
        
        title_label = QLabel("<b>Register New Device</b> (Tell ALICE what to control)")
        title_label.setStyleSheet("color: #7dcfff; font-size: 13px; font-weight: bold; border:none;")
        form_layout.addWidget(title_label)

        h_form = QHBoxLayout()
        
        # Name
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("e.g. Smart Fridge")
        h_form.addWidget(QLabel("Alias:"))
        h_form.addWidget(self.inp_name)
        
        # IP
        self.inp_ip = QLineEdit()
        self.inp_ip.setPlaceholderText("192.168.1.55")
        h_form.addWidget(QLabel("IP Addr:"))
        h_form.addWidget(self.inp_ip)
        
        # Port
        self.inp_port = QLineEdit()
        self.inp_port.setPlaceholderText("80")
        self.inp_port.setFixedWidth(60)
        h_form.addWidget(QLabel("Port:"))
        h_form.addWidget(self.inp_port)
        
        # Protocol Type
        self.inp_type = QLineEdit()
        self.inp_type.setPlaceholderText("REST / TCP / HTTP")
        self.inp_type.setFixedWidth(120)
        h_form.addWidget(QLabel("Protocol:"))
        h_form.addWidget(self.inp_type)

        btn_add = QPushButton("🔌 Inject Hardware Node")
        btn_add.setStyleSheet("""
            QPushButton { background-color: #9ece6a; color: #15161e; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #b9f27c; }
            QPushButton:pressed { background-color: #73daca; }
        """)
        btn_add.clicked.connect(self._add_device)
        h_form.addWidget(btn_add)

        form_layout.addLayout(h_form)
        layout.addWidget(form_frame)
        
        # ─── Registered Devices Table ──────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Alias", "IP", "Port", "Protocol", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.table)
        
        # Populate table
        self._refresh_table()
        self.set_status("IoT Gateway Online.")

    def _add_device(self):
        name = self.inp_name.text().strip()
        ip = self.inp_ip.text().strip()
        port = self.inp_port.text().strip()
        proto = self.inp_type.text().strip()
        
        if not name or not ip or not port:
            QMessageBox.warning(self, "Invalid Entry", "Alias, IP, and Port are strictly required.")
            return

        try:
            with open(IOT_REGISTRY_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {"devices": []}
            
        data["devices"].append({
            "alias": name,
            "ip": ip,
            "port": int(port),
            "protocol": proto
        })
        
        with open(IOT_REGISTRY_FILE, "w") as f:
            json.dump(data, f, indent=2)
            
        self.inp_name.clear()
        self.inp_ip.clear()
        self.inp_port.clear()
        self.inp_type.clear()
        
        self._refresh_table()
        self.set_status(f"Added node '{name}' to SIFTA organic map.")
        
        # Post to GCI memory if available
        if self._gci and hasattr(self._gci, "_bus") and self._gci._bus:
            self._gci._bus.remember(f"Architect securely bonded a new hardware node: {name} at {ip}:{port}", app_context="IoT Networking")

    def _refresh_table(self):
        try:
            with open(IOT_REGISTRY_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {"devices": []}
            
        devs = data.get("devices", [])
        self.table.setRowCount(len(devs))
        
        for row_idx, dev in enumerate(devs):
            self.table.setItem(row_idx, 0, QTableWidgetItem(dev.get("alias", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(dev.get("ip", "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(dev.get("port", ""))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(dev.get("protocol", "")))
            
            # Ping Button
            btn_ping = QPushButton("Ping")
            # We capture local row_idx explicitly so lambda loops bind correctly 
            btn_ping.clicked.connect(lambda _, i=dev.get("ip"), p=dev.get("port"): self._ping_device(i, p))
            self.table.setCellWidget(row_idx, 4, btn_ping)

    def _ping_device(self, ip: str, port: int):
        self.set_status(f"Pinging {ip}:{port}...")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            result = s.connect_ex((ip, int(port)))
            s.close()
            if result == 0:
                QMessageBox.information(self, "Ping Result", f"SUCCESS! Port {port} is physically OPEN at {ip}.")
                self.set_status(f"{ip} is LIVE. Node attached successfully.")
            else:
                QMessageBox.warning(self, "Ping Result", f"FAILED! Port {port} is CLOSED or unreachable at {ip}.\n(Make sure the device is on your home WiFi).")
                self.set_status(f"Failed to ping {ip}:{port}.")
        except Exception as e:
            QMessageBox.critical(self, "Ping Error", f"Socket raised exception: {e}")
            self.set_status("Socket exception during ping.")

        
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = IoTConnectorWidget()
    w.resize(960, 620)
    w.show()
    sys.exit(app.exec())
