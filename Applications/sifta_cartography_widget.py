#!/usr/bin/env python3
"""
Applications/sifta_cartography_widget.py — Alice Safety Tracker
════════════════════════════════════════════════════════════════
AG31 · April 2026
C55M math/safety pass · April 2026

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
import hashlib
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

from PyQt6.QtCore import Qt, QTimer, QUrl, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient,
)
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

# ── Doctor sigil chrome (canonical Applications/_doctor_sigil_chrome) ─
try:
    from _doctor_sigil_chrome import paint_doctor_sigil_bar
    _HAS_SIGIL = True
except Exception:
    _HAS_SIGIL = False

_STATE = _REPO / ".sifta_state"
_LATEST = _STATE / "iphone_gps_latest.json"
_TRACES = _STATE / "iphone_gps_traces.jsonl"
_SAFETY_LOG = _STATE / "alice_safety_log.jsonl"
_HOME = _STATE / "alice_safety_home.json"

GITHUB_URL = "https://github.com/antonpictures/ANTON-SIFTA/blob/main/Applications/sifta_cartography_widget.py"

# ── GPS reader ──────────────────────────────────────────────────────

def _read_latest() -> Optional[dict]:
    """Read the freshest GPS fix (no staleness gate — show whatever we have)."""
    fix = None
    try:
        from System.swarm_iphone_gps_receiver import latest_iphone_gps
        fix = latest_iphone_gps(stale_after_s=86400)  # 24 h — always show last known
    except Exception:
        pass

    if fix is not None:
        return fix

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
            if _valid_coord(p.get("latitude"), p.get("longitude")):
                p = dict(p)
                p["ts"] = row.get("ts", p.get("ts"))
                fixes.append(p)
                if len(fixes) >= limit:
                    break
        except Exception:
            pass
    return list(reversed(fixes))


def _log_safety(event: str, data: dict) -> None:
    _STATE.mkdir(exist_ok=True)
    row = {
        "ts": time.time(),
        "event": event,
        "truth_note": "local GPS safety event written by Alice Safety Tracker",
        **data,
    }
    row["event_hash"] = hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    try:
        from System.ledger_append import append_ledger_line
        append_ledger_line(_SAFETY_LOG, row)
    except Exception:
        with open(_SAFETY_LOG, "a") as f:
            f.write(json.dumps(row) + "\n")


def _valid_coord(lat, lon) -> bool:
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _read_home() -> Optional[dict]:
    if not _HOME.exists():
        return None
    try:
        row = json.loads(_HOME.read_text())
    except Exception:
        return None
    if _valid_coord(row.get("latitude"), row.get("longitude")):
        return row
    return None


def _write_home(payload: dict) -> None:
    _STATE.mkdir(exist_ok=True)
    row = {
        "latitude": float(payload["latitude"]),
        "longitude": float(payload["longitude"]),
        "accuracy": payload.get("accuracy"),
        "set_ts": time.time(),
    }
    _HOME.write_text(json.dumps(row, indent=2) + "\n")


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distance in metres between two coordinates."""
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _bearing_deg(lat1, lon1, lat2, lon2) -> float:
    """Initial bearing from point 1 to point 2 in degrees."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


# ── Leaflet map HTML ─────────────────────────────────────────────────

def _build_map_html(
    lat: float,
    lon: float,
    trail: list[dict],
    *,
    accuracy_m: Optional[float] = None,
    home: Optional[dict] = None,
) -> str:
    """Build the Leaflet HTML for the map view.

    Visuals: CartoDB Dark Matter base, neon-cyan→magenta gradient trail,
    pulsing architect marker with accuracy halo, optional Home marker
    with bearing tether to the architect, and a translucent attribution
    ribbon styled to fit the SIFTA chrome.
    """
    trail_coords = [
        [float(p["latitude"]), float(p["longitude"])]
        for p in trail
        if _valid_coord(p.get("latitude"), p.get("longitude"))
    ]
    trail_js = json.dumps(trail_coords)
    accuracy_js = json.dumps(float(accuracy_m) if accuracy_m else None)
    home_js = "null"
    if home and _valid_coord(home.get("latitude"), home.get("longitude")):
        home_js = json.dumps([float(home["latitude"]), float(home["longitude"])])

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  html, body, #map {{ height:100%; margin:0; padding:0; background:#04060e; }}
  .leaflet-container {{ background:#04060e; }}
  .leaflet-control-attribution {{
    background:rgba(8,12,24,0.78) !important;
    color:#9aa3c2 !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    border-radius:8px !important;
    padding:2px 10px !important;
    font-family:-apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif !important;
    font-size:9px !important;
    backdrop-filter:saturate(180%) blur(8px);
  }}
  .leaflet-control-attribution a {{ color:#5fc8c8 !important; }}
  .leaflet-control-zoom a {{
    background:rgba(10,14,28,0.85) !important;
    color:#c0caf5 !important;
    border:1px solid rgba(255,255,255,0.10) !important;
    backdrop-filter:saturate(180%) blur(10px);
    font-family:-apple-system,'SF Pro Display',sans-serif !important;
    font-weight:300; line-height:26px !important;
  }}
  .leaflet-control-zoom a:hover {{ background:rgba(0,255,200,0.18) !important; }}
  .architect-pulse {{
    width:22px; height:22px; border-radius:50%;
    background:radial-gradient(circle at 50% 50%, #ffd6e6 0%, #ff66aa 35%, #c842ff 75%, transparent 100%);
    border:2px solid #fff;
    box-shadow:0 0 12px rgba(255, 100, 200, 0.85),
               0 0 30px rgba(200, 80, 255, 0.55);
    animation:architectPulse 2.0s ease-in-out infinite;
  }}
  @keyframes architectPulse {{
    0%   {{ transform:scale(1.0); box-shadow:0 0 8px rgba(255,100,200,0.6); }}
    50%  {{ transform:scale(1.08); box-shadow:0 0 30px rgba(200,80,255,0.95),
                                              0 0 60px rgba(255,100,200,0.45); }}
    100% {{ transform:scale(1.0); box-shadow:0 0 8px rgba(255,100,200,0.6); }}
  }}
  .home-marker {{
    width:18px; height:18px; border-radius:6px;
    background:rgba(0, 255, 200, 0.18);
    border:1.5px solid #00ffc8;
    color:#00ffc8;
    display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:600;
    box-shadow:0 0 12px rgba(0,255,200,0.55);
  }}
  .arch-popup, .home-popup {{
    color:#dde3f5;
    font-family:-apple-system,'SF Pro Text',sans-serif;
    font-size:11px;
  }}
  .leaflet-popup-content-wrapper {{
    background:rgba(8,12,24,0.92) !important;
    color:#dde3f5 !important;
    border:1px solid rgba(168,107,255,0.45) !important;
    border-radius:10px !important;
    backdrop-filter:saturate(180%) blur(14px);
    box-shadow:0 6px 24px rgba(0,0,0,0.55) !important;
  }}
  .leaflet-popup-tip {{ background:rgba(8,12,24,0.92) !important; }}
</style>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map', {{
  zoomControl:true,
  attributionControl:true,
  preferCanvas:true,
  fadeAnimation:true,
  zoomAnimation:true
}}).setView([{lat},{lon}], 15);

// Cinematic dark base — CartoDB Dark Matter (free, no API key)
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution:'© OpenStreetMap · © CARTO · 🐜 Alice Safety Tracker',
  subdomains:'abcd', maxZoom:20
}}).addTo(map);

// ── Trail with neon gradient (older→newer = magenta→cyan) ─────────
var trail = {trail_js};
if (trail.length > 1) {{
  // Soft glow underlayer
  L.polyline(trail, {{
    color:'#a86bff', weight:9, opacity:0.18, smoothFactor:1.5, lineCap:'round'
  }}).addTo(map);
  // Bright crisp top stroke, segmented for color graduation
  for (var i=1;i<trail.length;i++) {{
    var t = i / Math.max(1, trail.length - 1);
    var r = Math.round(168 + (0   - 168) * t);
    var g = Math.round(107 + (255 - 107) * t);
    var b = Math.round(255 + (200 - 255) * t);
    L.polyline([trail[i-1], trail[i]], {{
      color:`rgb(${{r}},${{g}},${{b}})`, weight:2.5, opacity:0.9, lineCap:'round'
    }}).addTo(map);
  }}
  // Start anchor (oldest)
  L.circleMarker(trail[0], {{
    radius:4, color:'#a86bff', fillColor:'#a86bff',
    fillOpacity:0.9, weight:1.5
  }}).addTo(map).bindPopup('<div class="home-popup"><b>Trail begins here</b></div>');
}}

// ── Accuracy halo (translucent, scales with reported metres) ──────
var acc = {accuracy_js};
if (acc !== null && acc > 0) {{
  L.circle([{lat},{lon}], {{
    radius: acc, color:'#ff8ec5', weight:1.0, opacity:0.45,
    fillColor:'#ff66aa', fillOpacity:0.07, dashArray:'3 6', interactive:false
  }}).addTo(map);
}}

// ── Architect marker (pulsing magenta-violet halo) ────────────────
var archIcon = L.divIcon({{
  className:'',
  html:'<div class="architect-pulse"></div>',
  iconSize:[22,22], iconAnchor:[11,11]
}});
var archMarker = L.marker([{lat},{lon}], {{icon:archIcon, zIndexOffset:500}})
  .addTo(map)
  .bindPopup(
    '<div class="arch-popup">' +
    '<div style="color:#ff66aa;font-weight:700;font-size:12px;">🐜 Architect · Ioan</div>' +
    '<div style="margin-top:4px;color:#9aa3c2;font-family:Menlo,monospace;">{lat:.5f}, {lon:.5f}</div>' +
    '<div style="margin-top:2px;color:#5fc8c8;font-size:10px;">Alice is watching · live GPS</div>' +
    '</div>'
  )
  .openPopup();

// ── Home marker + tether line (only if home is set) ───────────────
var home = {home_js};
if (home) {{
  var homeIcon = L.divIcon({{
    className:'',
    html:'<div class="home-marker">🏠</div>',
    iconSize:[18,18], iconAnchor:[9,9]
  }});
  L.marker(home, {{icon:homeIcon, zIndexOffset:300}})
    .addTo(map)
    .bindPopup(
      '<div class="home-popup">' +
      '<div style="color:#00ffc8;font-weight:700;">🏠 Home</div>' +
      '<div style="margin-top:4px;color:#9aa3c2;font-family:Menlo,monospace;">' +
        home[0].toFixed(5) + ', ' + home[1].toFixed(5) + '</div>' +
      '</div>'
    );
  // Tether line (dashed) from architect → home
  L.polyline([[{lat},{lon}], home], {{
    color:'#00ffc8', weight:1.0, opacity:0.42,
    dashArray:'4 8', interactive:false
  }}).addTo(map);
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
            self.setWindowTitle("Alice Safety Tracker — SIFTA OS")

        self._last_fix: Optional[dict] = None
        self._home_fix: Optional[dict] = _read_home()
        self._trip_active = False
        self._trip_start_ts: Optional[float] = None
        self._stationary_since: Optional[float] = None
        self._arrival_logged = False

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(30_000)  # every 30 s
        QTimer.singleShot(500, self._poll)  # immediate first read

    # ── macOS-feel base stylesheet ───────────────────────────────────
    _APP_QSS = """
        QWidget { background: rgb(4, 6, 14); color: rgb(220, 230, 250); }
        QLabel  {
            font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', 'Menlo';
            font-size: 11px; color: rgb(180, 195, 230); font-weight: 500;
        }
        QPushButton {
            background: rgba(255, 255, 255, 12);
            color: rgb(0, 255, 200);
            border: 1px solid rgba(0, 255, 200, 90);
            border-radius: 8px;
            font-family: -apple-system, 'SF Pro Text';
            font-size: 11px; font-weight: 600;
            padding: 6px 14px; min-height: 24px;
        }
        QPushButton:hover    { background: rgba(0, 255, 200, 26); }
        QPushButton:pressed  { background: rgba(0, 255, 200, 60); }
        QPushButton#trip-on {
            background: rgba(255, 100, 200, 35);
            border: 1px solid rgba(255, 100, 200, 200);
            color: rgb(255, 200, 230);
        }
        QPushButton#trip-on:hover { background: rgba(255, 100, 200, 60); }
        QTextEdit {
            background: rgba(8, 12, 24, 220);
            color: rgb(170, 195, 235);
            border: 1px solid rgba(255, 255, 255, 18);
            border-radius: 10px;
            padding: 8px 10px;
            font-family: 'JetBrains Mono', 'Menlo', monospace;
            font-size: 10px;
            selection-background-color: rgba(0, 200, 170, 90);
        }
        QFrame#card {
            background: rgba(10, 14, 28, 200);
            border: 1px solid rgba(255, 255, 255, 18);
            border-radius: 10px;
        }
        QLabel#hero-name {
            color: rgb(245, 245, 255); font-size: 16px; font-weight: 700;
            font-family: -apple-system, 'SF Pro Display';
        }
        QLabel#hero-coord {
            color: rgb(0, 255, 200); font-family: 'JetBrains Mono', 'Menlo';
            font-size: 11px; font-weight: 600;
        }
        QLabel#hero-acc {
            color: rgb(168, 107, 255); font-size: 10px; font-weight: 600;
            font-family: 'JetBrains Mono', 'Menlo';
        }
        QLabel#hero-age {
            color: rgb(140, 155, 190); font-size: 10px;
        }
        QLabel#card-label {
            color: rgb(140, 155, 190); font-size: 8px; font-weight: 700;
            letter-spacing: 1.2px;
        }
        QLabel#card-value {
            color: rgb(245, 245, 255); font-size: 16px; font-weight: 700;
            font-family: 'JetBrains Mono', 'Menlo';
        }
        QLabel#card-sub {
            color: rgb(120, 135, 170); font-size: 9px;
        }
    """

    def _setup_plain(self):
        self.setWindowTitle("Alice Safety Tracker — SIFTA OS")
        self.setStyleSheet(self._APP_QSS)
        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._build_inner(self._content_layout)

    def build_ui(self, layout: QVBoxLayout) -> None:
        # When hosted inside SiftaBaseWidget, install our stylesheet first
        try:
            self.setStyleSheet(self._APP_QSS)
        except Exception:
            pass
        self._build_inner(layout)

    def _build_inner(self, layout):
        # ── Doctor Sigil Bar ──────────────────────────────────────────
        self._sigil_bar = _SigilBar(["AG31", "C55M", "CG55M"],
                                    "Alice Safety Tracker",
                                    "iPhone GPS · Haversine arrival · Home tether")
        layout.addWidget(self._sigil_bar)

        # ── Hero status row: pulsing dot + name/coord + age + buttons ──
        hero = QFrame()
        hero.setObjectName("card")
        hero_h = QHBoxLayout(hero)
        hero_h.setContentsMargins(14, 10, 14, 10)
        hero_h.setSpacing(14)

        self._pulse = _PulseDot(QColor(86, 95, 137))
        self._pulse.setFixedSize(28, 28)
        hero_h.addWidget(self._pulse)

        text_block = QVBoxLayout()
        text_block.setSpacing(2)
        self._status_lbl = QLabel("Waiting for GPS signal…")
        self._status_lbl.setObjectName("hero-name")
        text_block.addWidget(self._status_lbl)
        self._coord_lbl = QLabel("no fix yet")
        self._coord_lbl.setObjectName("hero-coord")
        self._coord_lbl.setOpenExternalLinks(True)
        self._coord_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        text_block.addWidget(self._coord_lbl)
        hero_h.addLayout(text_block, 1)

        self._age_lbl = QLabel("")
        self._age_lbl.setObjectName("hero-age")
        self._age_lbl.setAlignment(Qt.AlignmentFlag.AlignRight |
                                   Qt.AlignmentFlag.AlignVCenter)
        hero_h.addWidget(self._age_lbl)

        self._btn_home = QPushButton("📍  Set Home")
        self._btn_home.setToolTip("Mark current location as Home")
        self._btn_home.clicked.connect(self._set_home)
        hero_h.addWidget(self._btn_home)

        self._btn_trip = QPushButton("🚗  Start Trip")
        self._btn_trip.setToolTip("Alice will watch you and log arrival")
        self._btn_trip.clicked.connect(self._toggle_trip)
        hero_h.addWidget(self._btn_trip)

        # gentle horizontal margin so the hero floats above the map
        hero_wrap = QHBoxLayout()
        hero_wrap.setContentsMargins(12, 10, 12, 8)
        hero_wrap.addWidget(hero)
        layout.addLayout(hero_wrap)

        # ── Map area ────────────────────────────────────────────────
        map_wrap = QHBoxLayout()
        map_wrap.setContentsMargins(12, 0, 12, 0)
        map_frame = QFrame()
        map_frame.setObjectName("card")
        map_frame.setStyleSheet(
            "QFrame#card { background: rgba(0, 0, 0, 220); "
            "border: 1px solid rgba(168, 107, 255, 70); border-radius: 12px; }"
        )
        mf_layout = QVBoxLayout(map_frame)
        mf_layout.setContentsMargins(2, 2, 2, 2)
        if _HAS_WEBENGINE:
            self._map_view = QWebEngineView()
            self._map_view.setMinimumHeight(420)
            self._map_view.page().setBackgroundColor(QColor("#04060e"))
            self._map_view.load(QUrl("about:blank"))
            mf_layout.addWidget(self._map_view, 1)
        else:
            self._coords_lbl = QLabel(
                "📡  Live map requires PyQt6-WebEngine.\n"
                "Coordinates shown in the cards below.")
            self._coords_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._coords_lbl.setStyleSheet(
                "color: rgb(140,155,190); font-size: 13px; padding: 40px;")
            mf_layout.addWidget(self._coords_lbl, 1)
        map_wrap.addWidget(map_frame, 1)
        layout.addLayout(map_wrap, 1)

        # ── Stat cards row: FRESHNESS / DISTANCE / ACCURACY / FIX AGE ──
        cards_wrap = QHBoxLayout()
        cards_wrap.setContentsMargins(12, 10, 12, 4)
        cards_wrap.setSpacing(10)
        self._card_freshness = _StatCard("FRESHNESS", "—", "no signal",
                                         QColor(86, 95, 137))
        self._card_distance  = _StatCard("DISTANCE",  "—", "from home",
                                         QColor(0, 255, 200))
        self._card_accuracy  = _StatCard("ACCURACY",  "—", "GPS ±",
                                         QColor(168, 107, 255))
        self._card_fix       = _StatCard("FIX AGE",   "—", "last update",
                                         QColor(255, 100, 200))
        for c in (self._card_freshness, self._card_distance,
                  self._card_accuracy, self._card_fix):
            cards_wrap.addWidget(c, 1)
        layout.addLayout(cards_wrap)

        # ── Safety log ──────────────────────────────────────────────
        log_wrap = QHBoxLayout()
        log_wrap.setContentsMargins(12, 6, 12, 12)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(122)
        log_wrap.addWidget(self._log)
        layout.addLayout(log_wrap)

        self._say("Alice Safety Tracker online. Waiting for your iPhone GPS signal.")

    # ── Core poll ───────────────────────────────────────────────────

    def _poll(self) -> None:
        fix = _read_latest()
        if fix is None:
            self._pulse.set_color(QColor(86, 95, 137))
            self._status_lbl.setText("No GPS fix — is the iPhone receiver running?")
            self._coord_lbl.setText("waiting for first satellite lock")
            self._age_lbl.setText("")
            self._card_freshness.set("—", "no signal")
            self._card_distance.set("—", "from home")
            self._card_accuracy.set("—", "GPS ±")
            self._card_fix.set("—", "last update")
            return

        payload = fix.get("payload", fix)
        lat = payload.get("latitude")
        lon = payload.get("longitude")
        acc = payload.get("accuracy", "?")
        age_s = int(fix.get("age_s", 0))
        fix_ts = float(fix.get("ts", payload.get("ts", time.time())) or time.time())

        if not _valid_coord(lat, lon):
            self._status_lbl.setText("Malformed GPS fix")
            return
        lat = float(lat)
        lon = float(lon)
        acc_m = float(acc) if isinstance(acc, (int, float)) else None

        # Freshness colour
        if age_s < 120:
            pulse_col = QColor(91, 255, 147)   # green — fresh
            fresh_label = "live"
        elif age_s < 3600:
            pulse_col = QColor(255, 200, 87)   # amber — recent
            fresh_label = "recent"
        else:
            pulse_col = QColor(255, 100, 130)  # red — stale
            fresh_label = "stale"
        self._pulse.set_color(pulse_col)

        age_str = self._fmt_age(age_s)
        self._age_lbl.setText(age_str)

        acc_str = f"{acc_m:.0f}m" if acc_m is not None else str(acc)
        self._status_lbl.setText("Ioan · live")
        self._coord_lbl.setText(
            f"<span style='color:#9aa3c2;'>lat</span> "
            f"<span style='color:#00ffc8;'>{lat:.6f}</span>  "
            f"<span style='color:#9aa3c2;'>lon</span> "
            f"<span style='color:#00ffc8;'>{lon:.6f}</span>  "
            f"<a href='https://maps.apple.com/?q={lat},{lon}' "
            f"style='color:#a86bff;text-decoration:none;'>Open in Maps ↗</a>"
        )

        # Home distance
        home_distance_m = None
        if self._home_fix:
            hlat = self._home_fix.get("latitude")
            hlon = self._home_fix.get("longitude")
            if _valid_coord(hlat, hlon):
                home_distance_m = _haversine_m(lat, lon, float(hlat), float(hlon))
                if home_distance_m < 1000:
                    self._card_distance.set(
                        f"{home_distance_m:.0f} m", "from home")
                else:
                    self._card_distance.set(
                        f"{home_distance_m/1000:.2f} km", "from home")
        else:
            self._card_distance.set("set home", "tap 📍 Set Home")

        # Update remaining stat cards
        self._card_freshness.set(fresh_label, age_str)
        if acc_m is not None:
            self._card_accuracy.set(f"±{acc_m:.0f} m",
                                    "high" if acc_m < 20 else
                                    ("medium" if acc_m < 60 else "low"))
        else:
            self._card_accuracy.set("—", "GPS ±")
        self._card_fix.set(age_str,
                           datetime.fromtimestamp(fix_ts).strftime("%H:%M:%S"))

        # Trip arrival detection. Uses GPS accuracy-aware thresholds and only
        # considers fixes written after the trip started, so stale cached
        # coordinates do not trigger false arrivals.
        if self._trip_active and self._last_fix:
            prev_p = self._last_fix.get("payload", self._last_fix)
            if _valid_coord(prev_p.get("latitude"), prev_p.get("longitude")):
                moved = _haversine_m(lat, lon, float(prev_p["latitude"]), float(prev_p["longitude"]))
                threshold_m = max(30.0, (acc_m or 15.0) * 2.0)
                fresh_for_trip = age_s < 300 and fix_ts >= (self._trip_start_ts or 0)
                if moved < threshold_m and fresh_for_trip:
                    if self._stationary_since is None:
                        self._stationary_since = time.time()
                    stationary_s = time.time() - self._stationary_since
                    if stationary_s > 120 and not self._arrival_logged:
                        where = (
                            f"{home_distance_m:.0f}m from Home"
                            if home_distance_m is not None and home_distance_m < 1000
                            else (
                                f"{home_distance_m/1000:.1f}km from Home"
                                if home_distance_m is not None
                                else "away from Home"
                            )
                        )
                        bearing = _bearing_deg(float(prev_p["latitude"]), float(prev_p["longitude"]), lat, lon)
                        self._say(f"📍 Arrival detected ({where}, moved {moved:.0f}m, bearing {bearing:.0f}°). Stay safe Ioan.")
                        _log_safety(
                            "ARRIVAL_DETECTED",
                            {
                                "lat": lat,
                                "lon": lon,
                                "moved_m": round(moved, 2),
                                "threshold_m": round(threshold_m, 2),
                                "bearing_deg": round(bearing, 2),
                                "home_distance_m": round(home_distance_m, 2) if home_distance_m is not None else None,
                                "fix_ts": fix_ts,
                            },
                        )
                        self._arrival_logged = True
                else:
                    self._stationary_since = None

        # Update map
        trail = _read_trail(40)
        if _HAS_WEBENGINE:
            html = _build_map_html(
                lat, lon, trail,
                accuracy_m=acc_m,
                home=self._home_fix,
            )
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
        if not _valid_coord(payload.get("latitude"), payload.get("longitude")):
            self._say("⚠ GPS fix exists but coordinates are malformed; Home not changed.")
            return
        self._home_fix = payload
        _write_home(payload)
        lat = float(payload.get("latitude"))
        lon = float(payload.get("longitude"))
        self._say(f"🏠 Home set: {lat:.5f}, {lon:.5f}")
        _log_safety("HOME_SET", {"lat": lat, "lon": lon, "accuracy": payload.get("accuracy")})

    def _toggle_trip(self) -> None:
        if not self._trip_active:
            self._trip_active = True
            self._trip_start_ts = time.time()
            self._stationary_since = None
            self._arrival_logged = False
            self._btn_trip.setText("✅  End Trip")
            self._btn_trip.setObjectName("trip-on")
            # re-apply stylesheet so the new objectName selector takes effect
            self.setStyleSheet(self._APP_QSS)
            self._say("🚗 Trip started. Alice is watching. Stay safe Ioan! 🐜⚡")
            fix = _read_latest()
            payload = fix.get("payload", fix) if fix else {}
            _log_safety("TRIP_START", {"latest_fix_ts": fix.get("ts") if fix else None, "payload": payload})
        else:
            self._trip_active = False
            self._btn_trip.setText("🚗  Start Trip")
            self._btn_trip.setObjectName("")
            self.setStyleSheet(self._APP_QSS)
            elapsed = int(time.time() - (self._trip_start_ts or time.time()))
            self._stationary_since = None
            self._say(f"🏠 Trip ended. Welcome back! ({elapsed//60}m {elapsed%60}s)")
            _log_safety("TRIP_END", {"elapsed_s": elapsed})

    # ── Helpers ─────────────────────────────────────────────────────

    def _say(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            html = (
                f"<span style='color:#5a7090;'>[{ts}]</span> "
                f"<span style='color:#aac4ed;'>{msg}</span>"
            )
            self._log.append(html)
        except AttributeError:
            pass

    @staticmethod
    def _fmt_age(age_s: int) -> str:
        if age_s < 60:
            return f"{age_s}s ago"
        if age_s < 3600:
            return f"{age_s//60}m ago"
        return f"{age_s//3600}h {(age_s%3600)//60}m ago"


# ══════════════════════════════════════════════════════════════════════
# UI BUILDING BLOCKS — frosted helpers used by the Safety Tracker.
# Pure-paint, no dependencies on other Apps modules besides the sigil.
# ══════════════════════════════════════════════════════════════════════

class _SigilBar(QFrame):
    """A self-contained Doctor Sigil Bar widget (uses the canonical chrome)."""

    def __init__(self, doctors: list[str], title: str,
                 subtitle: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self._doctors = doctors
        self._title = title
        self._subtitle = subtitle
        self.setFixedHeight(46)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _) -> None:  # noqa: N802
        if not _HAS_SIGIL:
            return
        p = QPainter(self)
        try:
            paint_doctor_sigil_bar(
                p, doctors=self._doctors,
                x=0, y=2, w=self.width(), h=self.height() - 2,
                title=self._title,
                subtitle=self._subtitle,
            )
        finally:
            p.end()


class _PulseDot(QWidget):
    """A breathing dot that pulses at ~0.5 Hz; colour conveys freshness."""

    def __init__(self, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(40)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def _step(self) -> None:
        self._phase = (self._phase + 0.04) % (2 * math.pi)
        self.update()

    def paintEvent(self, _) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            w, h = self.width(), self.height()
            cx, cy = w / 2, h / 2
            breath = 0.5 + 0.5 * math.sin(self._phase)
            outer_r = (min(w, h) / 2) * (0.92 - 0.08 * breath)
            # Outer halo (scales with breath)
            grad = QRadialGradient(cx, cy, outer_r * 1.2)
            c = QColor(self._color)
            c.setAlpha(int(150 + 90 * breath))
            grad.setColorAt(0.0, c)
            mid = QColor(self._color); mid.setAlpha(int(40 + 35 * breath))
            grad.setColorAt(0.6, mid)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), outer_r * 1.2, outer_r * 1.2)
            # Bright core
            p.setBrush(QBrush(QColor(245, 250, 255, 230)))
            p.drawEllipse(QPointF(cx, cy), max(2.0, outer_r * 0.32),
                          max(2.0, outer_r * 0.32))
            # Coloured accent
            p.setBrush(QBrush(self._color))
            p.drawEllipse(QPointF(cx, cy), max(1.4, outer_r * 0.18),
                          max(1.4, outer_r * 0.18))
        finally:
            p.end()


class _StatCard(QFrame):
    """A tiny frosted stat card with accent strip, value, and sub-line."""

    def __init__(self, label: str, value: str, sub: str, accent: QColor,
                 parent=None) -> None:
        super().__init__(parent)
        self._accent = accent
        self.setFixedHeight(64)
        self.setStyleSheet("background: transparent;")

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 8)
        v.setSpacing(2)

        self._label = QLabel(label.upper())
        self._label.setObjectName("card-label")
        col = QColor(accent)
        col.setAlpha(220)
        self._label.setStyleSheet(
            f"color: rgba({col.red()},{col.green()},{col.blue()},220); "
            "font-size: 8px; font-weight: 700; letter-spacing: 1.4px;"
        )
        v.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setObjectName("card-value")
        v.addWidget(self._value)

        self._sub = QLabel(sub)
        self._sub.setObjectName("card-sub")
        v.addWidget(self._sub)

    def set(self, value: str, sub: Optional[str] = None) -> None:
        self._value.setText(value)
        if sub is not None:
            self._sub.setText(sub)

    def paintEvent(self, _) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            w, h = self.width(), self.height()
            # Frosted base
            p.setBrush(QBrush(QColor(10, 14, 28, 200)))
            p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
            # Top accent strip
            strip = QColor(self._accent); strip.setAlpha(180)
            p.setBrush(QBrush(strip))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, 0, w, 3), 3, 3)
        finally:
            p.end()


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = CartographyWidget()
    w.resize(900, 700)
    w.setWindowTitle("Alice Safety Tracker — SIFTA OS")
    w.show()
    sys.exit(app.exec())
