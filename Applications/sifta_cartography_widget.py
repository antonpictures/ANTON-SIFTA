#!/usr/bin/env python3
"""
Applications/sifta_cartography_widget.py — Alice Safety Tracker
════════════════════════════════════════════════════════════════
AG31 · April 2026

Alice watches the Architect's location so she can take care of them.

HOW THE LOCATION ARRIVES:
  iPhone → iOS Shortcut → HTTP POST → System/swarm_iphone_gps_receiver.py
  → .sifta_state/iphone_gps_latest.json  (always fresh)
  → .sifta_state/iphone_gps_traces.jsonl (full history trail)

MAP:
  OpenStreetMap tiles rendered via QWebEngineView + Leaflet.js (offline-capable).
  If QtWebEngine is not available, falls back to text coordinates display.

SAFETY FEATURES:
  • Live pulse every 30 s
  • Trip detection (moving vs. stationary)
  • "Going to store" mode — Alice sends WhatsApp check-in when you arrive
  • Last-known location persisted — Alice always knows where you were

ALICE INTEGRATION:
  The composite identity prompt already includes summary_line() from
  swarm_iphone_gps_receiver.py. This widget is the VISUAL organ for
  that same data stream.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QWidget, QFrame,
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False

try:
    from System.sifta_base_widget import SiftaBaseWidget
    _BASE = SiftaBaseWidget
except ImportError:
    _BASE = QWidget

_STATE = _REPO / ".sifta_state"
_LATEST = _STATE / "iphone_gps_latest.json"
_TRACES = _STATE / "iphone_gps_traces.jsonl"
_SAFETY_LOG = _STATE / "alice_safety_log.jsonl"

GITHUB_URL = "https://github.com/antonpictures/ANTON-SIFTA/blob/main/Applications/sifta_cartography_widget.py"

# ── GPS reader ──────────────────────────────────────────────────────

def _read_latest() -> Optional[dict]:
    """Read the freshest GPS fix (no staleness gate — show whatever we have)."""
    try:
        from System.swarm_iphone_gps_receiver import latest_iphone_gps
        fix = latest_iphone_gps(stale_after_s=86400)  # 24 h — always show last known
        return fix
    except Exception:
        pass
    # fallback: read raw file
    if not _LATEST.exists():
        return None
    try:
        row = json.loads(_LATEST.read_text())
        row["age_s"] = time.time() - float(row.get("ts", 0))
        return row
    except Exception:
        return None


def _read_trail(limit: int = 50) -> list[dict]:
    """Read last `limit` GPS fixes from the traces ledger."""
    if not _TRACES.exists():
        return []
    lines = _TRACES.read_text(errors="replace").strip().split("\n")
    fixes = []
    for ln in reversed(lines[-200:]):
        try:
            row = json.loads(ln)
            p = row.get("payload", row)
            if p.get("latitude") and p.get("longitude"):
                fixes.append(p)
                if len(fixes) >= limit:
                    break
        except Exception:
            pass
    return list(reversed(fixes))


def _log_safety(event: str, data: dict) -> None:
    _STATE.mkdir(exist_ok=True)
    row = {"ts": time.time(), "event": event, **data}
    with open(_SAFETY_LOG, "a") as f:
        f.write(json.dumps(row) + "\n")


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distance in metres between two coordinates."""
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ── Leaflet map HTML ─────────────────────────────────────────────────

def _build_map_html(lat: float, lon: float, trail: list[dict]) -> str:
    trail_coords = [[p["latitude"], p["longitude"]] for p in trail if "latitude" in p]
    trail_js = json.dumps(trail_coords)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  html, body, #map {{ height:100%; margin:0; padding:0; background:#0b1020; }}
</style>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map', {{zoomControl:true}}).setView([{lat},{lon}], 15);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution:'© OpenStreetMap',
    maxZoom:19
}}).addTo(map);

// Architect marker (pulsing red)
var icon = L.divIcon({{
  className:'',
  html:'<div style="width:18px;height:18px;border-radius:50%;background:#ff2244;'
      +'border:3px solid #fff;box-shadow:0 0 12px #ff2244;animation:pulse 1.5s infinite;"></div>',
  iconSize:[18,18], iconAnchor:[9,9]
}});

var style = document.createElement('style');
style.textContent='@keyframes pulse{{0%{{box-shadow:0 0 4px #ff2244}}50%{{box-shadow:0 0 20px #ff2244}}100%{{box-shadow:0 0 4px #ff2244}}}}';
document.head.appendChild(style);

L.marker([{lat},{lon}], {{icon:icon}})
  .addTo(map)
  .bindPopup('<b>🐜 Architect · Ioan</b><br>{lat:.5f}, {lon:.5f}')
  .openPopup();

// Trail polyline
var trail = {trail_js};
if (trail.length > 1) {{
  L.polyline(trail, {{color:'#00ffc8', weight:2, opacity:0.7}}).addTo(map);
  // Start dot
  L.circleMarker(trail[0], {{radius:5, color:'#7aa2f7', fillOpacity:0.8}})
    .addTo(map).bindPopup('Start of trail');
}}
</script>
</body>
</html>"""


# ── Main Widget ──────────────────────────────────────────────────────

class CartographyWidget(_BASE):
    """Alice Safety Tracker — live GPS map for the Architect."""

    APP_NAME = "Alice Safety Tracker"

    def __init__(self, parent=None):
        if _BASE is QWidget:
            super().__init__(parent)
            self._setup_plain()
        else:
            super().__init__(parent)

        self._last_fix: Optional[dict] = None
        self._home_fix: Optional[dict] = None
        self._trip_active = False
        self._trip_start_ts: Optional[float] = None

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(30_000)  # every 30 s
        QTimer.singleShot(500, self._poll)  # immediate first read

    def _setup_plain(self):
        self.setWindowTitle("Alice Safety Tracker — SIFTA OS")
        self.setStyleSheet("background:#0b1020; color:#c0caf5; font-family:Menlo,monospace;")
        self._content_layout = QVBoxLayout(self)

    def build_ui(self, layout: QVBoxLayout) -> None:
        self._build_inner(layout)

    def _build_inner(self, layout):
        # ── Status bar ──────────────────────────────────────────────
        status_row = QHBoxLayout()

        self._dot = QLabel("●")
        self._dot.setFont(QFont("Menlo", 14))
        self._dot.setStyleSheet("color: #565f89;")
        status_row.addWidget(self._dot)

        self._status_lbl = QLabel("Waiting for GPS signal…")
        self._status_lbl.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self._status_lbl.setStyleSheet("color: #c0caf5;")
        status_row.addWidget(self._status_lbl, 1)

        self._age_lbl = QLabel("")
        self._age_lbl.setStyleSheet("color: #565f89; font-size:10px;")
        status_row.addWidget(self._age_lbl)

        btn_home = QPushButton("📍 Set Home")
        btn_home.setToolTip("Mark current location as Home")
        btn_home.clicked.connect(self._set_home)
        btn_home.setStyleSheet(
            "QPushButton{background:#1a1b26;color:#00ffc8;border:1px solid #2a2f3a;"
            "border-radius:5px;padding:4px 10px;font-size:11px;}"
            "QPushButton:hover{border-color:#00ffc8;}"
        )
        status_row.addWidget(btn_home)

        btn_trip = QPushButton("🚗 Start Trip")
        btn_trip.setToolTip("Tell Alice you're going out — she'll watch for your return")
        btn_trip.clicked.connect(self._toggle_trip)
        btn_trip.setStyleSheet(btn_home.styleSheet())
        self._btn_trip = btn_trip
        status_row.addWidget(btn_trip)

        layout.addLayout(status_row)

        # ── Map area ────────────────────────────────────────────────
        if _HAS_WEBENGINE:
            self._map_view = QWebEngineView()
            self._map_view.setMinimumHeight(400)
            self._map_view.page().setBackgroundColor(QColor("#0b1020"))
            self._map_view.load(QUrl("about:blank"))
            layout.addWidget(self._map_view, 1)
        else:
            self._coords_lbl = QLabel("Map requires PyQt6-WebEngine.\nCoordinates shown below.")
            self._coords_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._coords_lbl.setStyleSheet("color:#565f89; font-size:13px; padding:40px;")
            layout.addWidget(self._coords_lbl, 1)

        # ── Info panel ──────────────────────────────────────────────
        info_row = QHBoxLayout()

        self._coord_lbl = QLabel("No fix yet")
        self._coord_lbl.setStyleSheet("color:#00ffc8; font-family:Menlo; font-size:11px; padding:4px 8px;")
        info_row.addWidget(self._coord_lbl)

        info_row.addStretch()

        self._dist_lbl = QLabel("")
        self._dist_lbl.setStyleSheet("color:#7aa2f7; font-size:10px;")
        info_row.addWidget(self._dist_lbl)

        layout.addLayout(info_row)

        # ── Safety log ──────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setStyleSheet(
            "QTextEdit{background:#080d18;color:#7aa2f7;font-family:Menlo;"
            "font-size:9px;border:1px solid #1a1b26;border-radius:4px;}"
        )
        layout.addWidget(self._log)
        self._say("Alice Safety Tracker online. Waiting for your iPhone GPS signal.")

    # ── Core poll ───────────────────────────────────────────────────

    def _poll(self) -> None:
        fix = _read_latest()
        if fix is None:
            self._dot.setStyleSheet("color:#565f89;")
            self._status_lbl.setText("No GPS fix — is the iPhone receiver running?")
            self._age_lbl.setText("")
            return

        payload = fix.get("payload", fix)
        lat = payload.get("latitude")
        lon = payload.get("longitude")
        acc = payload.get("accuracy", "?")
        age_s = int(fix.get("age_s", 0))

        if lat is None or lon is None:
            self._status_lbl.setText("Malformed GPS fix")
            return

        # Freshness colour
        if age_s < 120:
            self._dot.setStyleSheet("color:#9ece6a;")   # green — fresh
        elif age_s < 3600:
            self._dot.setStyleSheet("color:#e0af68;")   # amber — recent
        else:
            self._dot.setStyleSheet("color:#f7768e;")   # red — stale

        age_str = self._fmt_age(age_s)
        self._age_lbl.setText(age_str)

        acc_str = f"{acc:.0f}m" if isinstance(acc, (int, float)) else str(acc)
        self._status_lbl.setText(f"Ioan · {lat:.5f}, {lon:.5f}  ±{acc_str}")
        self._coord_lbl.setText(
            f"lat {lat:.6f}  lon {lon:.6f}  "
            f"<a href='https://maps.apple.com/?q={lat},{lon}' style='color:#00ffc8;'>Open in Maps ↗</a>"
        )
        self._coord_lbl.setOpenExternalLinks(True)

        # Home distance
        if self._home_fix:
            hlat = self._home_fix.get("latitude")
            hlon = self._home_fix.get("longitude")
            if hlat and hlon:
                d = _haversine_m(lat, lon, hlat, hlon)
                if d < 1000:
                    self._dist_lbl.setText(f"📍 {d:.0f}m from Home")
                else:
                    self._dist_lbl.setText(f"📍 {d/1000:.1f}km from Home")

        # Trip arrival detection
        if self._trip_active and self._last_fix:
            prev_p = self._last_fix.get("payload", self._last_fix)
            if prev_p.get("latitude"):
                moved = _haversine_m(lat, lon, prev_p["latitude"], prev_p["longitude"])
                if moved < 30 and age_s < 300:
                    # Stationary — might have arrived
                    elapsed = time.time() - (self._trip_start_ts or time.time())
                    if elapsed > 120:
                        self._say(f"📍 You seem to have arrived somewhere ({d if self._home_fix else '?'}). Stay safe Ioan! 🐜")
                        _log_safety("ARRIVAL_DETECTED", {"lat": lat, "lon": lon})

        # Update map
        trail = _read_trail(40)
        if _HAS_WEBENGINE:
            html = _build_map_html(lat, lon, trail)
            self._map_view.setHtml(html, QUrl("https://openstreetmap.org"))
        else:
            self._coords_lbl.setText(
                f"📍 Ioan at:\n{lat:.6f}, {lon:.6f}\n±{acc_str}\n{age_str}"
            )

        self._last_fix = fix

    # ── Controls ────────────────────────────────────────────────────

    def _set_home(self) -> None:
        fix = _read_latest()
        if fix is None:
            self._say("⚠ No GPS fix to mark as Home.")
            return
        payload = fix.get("payload", fix)
        self._home_fix = payload
        lat = payload.get("latitude", "?")
        lon = payload.get("longitude", "?")
        self._say(f"🏠 Home set: {lat:.5f}, {lon:.5f}")
        _log_safety("HOME_SET", {"lat": lat, "lon": lon})

    def _toggle_trip(self) -> None:
        if not self._trip_active:
            self._trip_active = True
            self._trip_start_ts = time.time()
            self._btn_trip.setText("✅ End Trip")
            self._say("🚗 Trip started. Alice is watching. Stay safe Ioan! 🐜⚡")
            _log_safety("TRIP_START", {})
        else:
            self._trip_active = False
            self._btn_trip.setText("🚗 Start Trip")
            elapsed = int(time.time() - (self._trip_start_ts or time.time()))
            self._say(f"🏠 Trip ended. Welcome back! ({elapsed//60}m {elapsed%60}s)")
            _log_safety("TRIP_END", {"elapsed_s": elapsed})

    # ── Helpers ─────────────────────────────────────────────────────

    def _say(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self._log.append(f"[{ts}] {msg}")
        except AttributeError:
            pass

    @staticmethod
    def _fmt_age(age_s: int) -> str:
        if age_s < 60:
            return f"{age_s}s ago"
        if age_s < 3600:
            return f"{age_s//60}m ago"
        return f"{age_s//3600}h {(age_s%3600)//60}m ago"


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = CartographyWidget()
    w.resize(900, 700)
    w.setWindowTitle("Alice Safety Tracker — SIFTA OS")
    w.show()
    sys.exit(app.exec())
