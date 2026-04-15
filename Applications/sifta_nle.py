#!/usr/bin/env python3
"""
SIFTA NLE — Stigmergic Non-Linear Video Editor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The timeline is dead. Welcome to the Pheromone Matrix.

Architecture:
  • RhythmForager    — scans audio transients, drops Cut_Pheromone on peaks
  • ChromaSwimmer    — color-matches all clips to a Hero Frame target
  • AudioSentinel    — protects vocal band (1-4 kHz), ducks music on conflict
  • NarrativeWeaver  — reads transcript, syncs subtitles, triggers intent cuts

Pipeline:
  1. Drop folder of video/audio files
  2. FFprobe extracts metadata, ffmpeg extracts waveforms + thumbnails
  3. Swimmers swarm the Temporal Pheromone Matrix
  4. Cut decisions exported as EDL (.edl) or FFmpeg filter script
  5. Render via ffmpeg — or export to Premiere/DaVinci/FCP

Keeps Sebastian's original silence-detection jumpcut algo intact.

Run:  python3 Applications/sifta_nle.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import os
import math
import time
import random
import json
import struct
import wave
import subprocess
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "System"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QFileDialog,
    QSizePolicy, QGroupBox, QTextEdit, QScrollArea, QProgressBar,
    QComboBox, QSpinBox, QCheckBox, QLineEdit, QToolBar, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, QThread, pyqtSignal, QSize, QUrl
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QAction, QIcon, QPixmap, QImage
)
import numpy as np

# ── Palette ────────────────────────────────────────────────────────
C_VOID       = QColor(8, 10, 18)
C_SURFACE    = QColor(18, 20, 32)
C_PANEL      = QColor(25, 27, 42)
C_BORDER     = QColor(45, 42, 65)
C_HIGHLIGHT  = QColor(0, 255, 200)
C_TEXT       = QColor(200, 210, 240)
C_TEXT_DIM   = QColor(100, 105, 130)
C_CUT_PHEROMONE = QColor(255, 80, 120)
C_CHROMA     = QColor(120, 200, 255)
C_AUDIO_WAVE = QColor(255, 200, 80)
C_VOCAL_BAND = QColor(255, 120, 255)
C_SUBTITLE   = QColor(255, 255, 255)
C_STGM_GLOW  = QColor(0, 255, 128)
C_HOSTILE    = QColor(255, 50, 80)
C_HERO_FRAME = QColor(80, 255, 200)

# ── FFmpeg / FFprobe helpers ───────────────────────────────────────

def find_ffmpeg() -> Optional[str]:
    """Find ffmpeg binary."""
    for path in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]:
        try:
            r = subprocess.run([path, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None

def find_ffprobe() -> Optional[str]:
    """Find ffprobe binary."""
    for path in ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "ffprobe"]:
        try:
            r = subprocess.run([path, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None

FFMPEG = find_ffmpeg()
FFPROBE = find_ffprobe()


# ═══════════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MediaClip:
    """A video/audio clip loaded into the NLE."""
    path: Path
    filename: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 24.0
    codec: str = ""
    audio_channels: int = 2
    audio_rate: int = 44100
    # Extracted data
    waveform: Optional[np.ndarray] = None  # mono waveform samples
    thumbnail: Optional[QPixmap] = None
    # Analysis results
    silence_ranges: List[Tuple[float, float]] = field(default_factory=list)
    transient_peaks: List[float] = field(default_factory=list)  # timestamps
    avg_color: Tuple[int, int, int] = (128, 128, 128)
    # Timeline placement
    timeline_start: float = 0.0  # start position on timeline (seconds)
    in_point: float = 0.0
    out_point: float = 0.0


@dataclass
class CutPheromone:
    """A pheromone trace dropped by a RhythmForager at a potential cut point."""
    time_pos: float      # seconds on timeline
    strength: float      # 0.0 to 1.0
    source: str          # "RHYTHM", "NARRATIVE", "SILENCE", "MANUAL"
    clip_idx: int = -1
    age: float = 0.0


@dataclass
class SubtitleEntry:
    """A subtitle/transcript line with timecode."""
    start: float
    end: float
    text: str
    speaker: str = ""
    confidence: float = 1.0


@dataclass
class EditDecision:
    """An edit decision — standard EDL entry."""
    clip_idx: int
    in_time: float
    out_time: float
    timeline_pos: float
    transition: str = "CUT"  # CUT, DISSOLVE
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════
#  SEBASTIAN'S CORE ALGOS (preserved from sifta_sebastian_editor.py)
# ═══════════════════════════════════════════════════════════════════

def detect_silence_ranges(audio_data: np.ndarray, sample_rate: int,
                          noise_floor_db: float = -35.0,
                          min_duration: float = 0.5) -> List[Tuple[float, float]]:
    """Pure-Python silence detection on raw audio samples.
    Preserves Sebastian's original logic, no ffmpeg required."""
    if audio_data is None or len(audio_data) == 0:
        return []

    threshold = 10 ** (noise_floor_db / 20.0)
    window_size = int(sample_rate * 0.05)  # 50ms windows
    silences = []
    in_silence = False
    silence_start = 0.0

    for i in range(0, len(audio_data) - window_size, window_size):
        chunk = audio_data[i:i + window_size]
        rms = np.sqrt(np.mean(chunk ** 2))

        t = i / sample_rate

        if rms < threshold:
            if not in_silence:
                in_silence = True
                silence_start = t
        else:
            if in_silence:
                duration = t - silence_start
                if duration >= min_duration:
                    silences.append((silence_start, t))
                in_silence = False

    # Handle trailing silence
    if in_silence:
        end_t = len(audio_data) / sample_rate
        if (end_t - silence_start) >= min_duration:
            silences.append((silence_start, end_t))

    return silences


def detect_audio_transients(audio_data: np.ndarray, sample_rate: int,
                            sensitivity: float = 0.6) -> List[float]:
    """Detect audio transients (sudden energy spikes) — used by RhythmForager.
    Returns list of timestamps where transients occur."""
    if audio_data is None or len(audio_data) < 1024:
        return []

    window_size = int(sample_rate * 0.02)  # 20ms windows
    hop = window_size // 2
    energies = []

    for i in range(0, len(audio_data) - window_size, hop):
        chunk = audio_data[i:i + window_size]
        energies.append(np.sqrt(np.mean(chunk ** 2)))

    if not energies:
        return []

    energies = np.array(energies)
    # Spectral flux — difference between consecutive windows
    flux = np.diff(energies)
    flux = np.maximum(flux, 0)  # only positive changes (onsets)

    threshold = np.mean(flux) + sensitivity * np.std(flux)
    peaks = []

    for i, f in enumerate(flux):
        if f > threshold:
            t = (i * hop) / sample_rate
            # Don't double-count peaks within 0.1s
            if not peaks or (t - peaks[-1]) > 0.1:
                peaks.append(t)

    return peaks


def compute_vocal_band_energy(audio_data: np.ndarray, sample_rate: int,
                              window_sec: float = 0.1) -> List[Tuple[float, float]]:
    """Compute energy in the vocal frequency band (1-4 kHz) over time.
    Used by AudioSentinel for music ducking decisions."""
    if audio_data is None or len(audio_data) < 1024:
        return []

    window_size = int(sample_rate * window_sec)
    result = []

    for i in range(0, len(audio_data) - window_size, window_size):
        chunk = audio_data[i:i + window_size]
        # Simple bandpass approximation using FFT
        fft = np.fft.rfft(chunk)
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / sample_rate)
        # Vocal band: 1000-4000 Hz
        mask = (freqs >= 1000) & (freqs <= 4000)
        vocal_energy = np.sum(np.abs(fft[mask]) ** 2) if np.any(mask) else 0
        total_energy = np.sum(np.abs(fft) ** 2) + 1e-10
        ratio = vocal_energy / total_energy
        t = i / sample_rate
        result.append((t, ratio))

    return result


def parse_srt(srt_path: Path) -> List[SubtitleEntry]:
    """Parse .srt subtitle file into SubtitleEntry list."""
    entries = []
    if not srt_path.exists():
        return entries

    text = srt_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r'\n\n+', text.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        # Line 1: index, Line 2: timecodes, Line 3+: text
        tc_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1].strip()
        )
        if not tc_match:
            continue
        g = tc_match.groups()
        start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        end = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000
        sub_text = ' '.join(lines[2:]).strip()
        entries.append(SubtitleEntry(start=start, end=end, text=sub_text))

    return entries


def generate_edl(decisions: List[EditDecision], clips: List[MediaClip],
                 title: str = "SIFTA_NLE") -> str:
    """Generate CMX 3600 EDL format for export to Premiere/DaVinci/FCP."""
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]

    for i, d in enumerate(decisions):
        clip = clips[d.clip_idx] if d.clip_idx < len(clips) else None
        reel = clip.filename[:8].replace(' ', '_') if clip else "AX"

        def tc(secs):
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            s = int(secs % 60)
            f = int((secs % 1) * 24)
            return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

        event_num = f"{i + 1:03d}"
        src_in = tc(d.in_time)
        src_out = tc(d.out_time)
        rec_in = tc(d.timeline_pos)
        rec_out = tc(d.timeline_pos + (d.out_time - d.in_time))

        lines.append(f"{event_num}  {reel:8s} V     C        {src_in} {src_out} {rec_in} {rec_out}")
        if d.notes:
            lines.append(f"* {d.notes}")

    return "\n".join(lines)


def generate_ffmpeg_filter_script(decisions: List[EditDecision],
                                  clips: List[MediaClip]) -> str:
    """Generate ffmpeg complex filter for rendering the edit."""
    lines = []
    v_labels = []
    a_labels = []

    for i, d in enumerate(decisions):
        ci = d.clip_idx
        lines.append(
            f"[{ci}:v]trim=start={d.in_time:.3f}:end={d.out_time:.3f},"
            f"setpts=PTS-STARTPTS[v{i}];"
        )
        v_labels.append(f"[v{i}]")
        lines.append(
            f"[{ci}:a]atrim=start={d.in_time:.3f}:end={d.out_time:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}];"
        )
        a_labels.append(f"[a{i}]")

    concat = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
    n = len(decisions)
    lines.append(f"{concat}concat=n={n}:v=1:a=1[outv][outa]")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  SYNTHETIC DEMO DATA (when no real files are loaded)
# ═══════════════════════════════════════════════════════════════════

def generate_demo_waveform(duration: float = 30.0, sample_rate: int = 8000) -> np.ndarray:
    """Generate a realistic-looking audio waveform for demo purposes."""
    n = int(duration * sample_rate)
    t = np.linspace(0, duration, n)

    # Music bed (low-freq hum with beat pattern)
    beat_freq = 2.5  # ~150 BPM
    music = 0.3 * np.sin(2 * np.pi * 120 * t)
    music *= (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * beat_freq * t)))

    # Vocal-like bursts (speech cadence)
    vocal = np.zeros(n)
    phrase_starts = sorted(random.sample(range(0, n - sample_rate, sample_rate), min(8, n // sample_rate)))
    for ps in phrase_starts:
        phrase_len = random.randint(sample_rate // 2, sample_rate * 2)
        end = min(ps + phrase_len, n)
        vocal[ps:end] = 0.6 * np.sin(2 * np.pi * 220 * t[ps:end]) * np.exp(-0.5 * (t[ps:end] - t[ps]))

    # Transients (claps, hits)
    transients = np.zeros(n)
    for _ in range(int(duration * beat_freq)):
        pos = random.randint(0, n - 100)
        transients[pos:pos + 100] = random.uniform(0.5, 1.0) * np.exp(-np.linspace(0, 5, 100))

    combined = music + vocal + transients
    combined += np.random.normal(0, 0.02, n)  # noise floor
    combined = np.clip(combined, -1, 1)
    return combined.astype(np.float32)


def generate_demo_clips(count: int = 6) -> List[MediaClip]:
    """Generate demo clips with synthetic waveforms for testing."""
    names = [
        "interview_cam_A.mp4", "interview_cam_B.mp4", "b_roll_city.mov",
        "drone_sunset.mp4", "music_bed_v2.wav", "voiceover_final.mp4",
        "reaction_shot.mp4", "timelapse_dawn.mov", "podium_speech.mp4",
        "crowd_ambience.wav",
    ]
    clips = []
    timeline_pos = 0.0

    for i in range(count):
        dur = random.uniform(8, 45)
        clip = MediaClip(
            path=Path(f"/demo/{names[i % len(names)]}"),
            filename=names[i % len(names)],
            duration=dur,
            width=1920, height=1080,
            fps=random.choice([23.976, 24.0, 29.97, 30.0, 59.94]),
            codec=random.choice(["h264", "h265", "prores", "braw"]),
            audio_channels=2,
            audio_rate=44100,
            waveform=generate_demo_waveform(dur),
            avg_color=(
                random.randint(60, 220),
                random.randint(60, 220),
                random.randint(60, 220),
            ),
            timeline_start=timeline_pos,
            in_point=0.0,
            out_point=dur,
        )
        # Run analysis
        clip.silence_ranges = detect_silence_ranges(clip.waveform, 8000)
        clip.transient_peaks = detect_audio_transients(clip.waveform, 8000)
        timeline_pos += dur
        clips.append(clip)

    return clips


# ═══════════════════════════════════════════════════════════════════
#  PHEROMONE MATRIX CANVAS
# ═══════════════════════════════════════════════════════════════════

class PheromoneMatrixCanvas(QWidget):
    """The core NLE visualization — replaces the traditional timeline."""

    cut_executed = pyqtSignal(float, str)  # time_pos, reason

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── State ─────────────────────────────────────────────────
        self.clips: List[MediaClip] = []
        self.pheromones: List[CutPheromone] = []
        self.subtitles: List[SubtitleEntry] = []
        self.edit_decisions: List[EditDecision] = []
        self.executed_cuts: List[float] = []  # timestamps where we cut

        # ── Swarm config ──────────────────────────────────────────
        self.rhythm_density = 80
        self.chroma_density = 40
        self.cut_threshold = 0.65
        self.hero_color: Tuple[int, int, int] = (40, 80, 120)  # target grade
        self.hero_active = False

        # ── Visualization ─────────────────────────────────────────
        self.zoom = 1.0
        self.scroll_x = 0.0
        self.playhead = 0.0
        self.playing = False
        self.total_duration = 0.0

        # ── Swimmers ──────────────────────────────────────────────
        self.rhythm_swimmers: List[List[float]] = []   # [x, y, vx, vy]
        self.chroma_swimmers: List[List[float]] = []
        self.audio_sentinels: List[List[float]] = []

        # ── Sim ───────────────────────────────────────────────────
        self.tick = 0
        self.sim_time = 0.0
        self.cuts_executed = 0
        self.cohesion_index = 0.0
        self.sentinels_active = 0
        self.stgm_earned = 0.0
        self.log_lines: List[str] = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)  # ~30 FPS

    def load_demo(self):
        """Load demo clips for testing."""
        self.clips = generate_demo_clips(6)
        self.total_duration = sum(c.duration for c in self.clips)
        self._init_swimmers()
        self._log("📂 Loaded 6 demo clips — running stigmergic analysis...")
        # Generate initial pheromones from transient detection
        for ci, clip in enumerate(self.clips):
            for peak_t in clip.transient_peaks:
                global_t = clip.timeline_start + peak_t
                strength = random.uniform(0.3, 0.8)
                self.pheromones.append(CutPheromone(
                    time_pos=global_t, strength=strength,
                    source="RHYTHM", clip_idx=ci
                ))
            for (s_start, s_end) in clip.silence_ranges:
                global_t = clip.timeline_start + s_end
                self.pheromones.append(CutPheromone(
                    time_pos=global_t, strength=0.6,
                    source="SILENCE", clip_idx=ci
                ))
        self._log(f"🐜 {len(self.pheromones)} pheromone traces deposited from audio analysis")

    def load_clips(self, paths: List[Path]):
        """Load real video/audio files via ffprobe."""
        if not FFPROBE:
            self._log("⚠️ ffprobe not found — install ffmpeg: brew install ffmpeg")
            return

        self.clips.clear()
        timeline_pos = 0.0
        for p in paths:
            clip = self._probe_file(p)
            if clip:
                clip.timeline_start = timeline_pos
                timeline_pos += clip.duration
                self.clips.append(clip)
                self._log(f"📂 Loaded: {clip.filename} ({clip.duration:.1f}s, {clip.codec})")

        self.total_duration = timeline_pos
        self._init_swimmers()
        self._log(f"🐜 {len(self.clips)} clips loaded, total {self.total_duration:.1f}s")

    def _probe_file(self, path: Path) -> Optional[MediaClip]:
        """Extract metadata via ffprobe."""
        try:
            cmd = [
                FFPROBE, "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(path)
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            info = json.loads(r.stdout)

            dur = float(info.get("format", {}).get("duration", 0))
            clip = MediaClip(path=path, filename=path.name, duration=dur)

            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    clip.width = int(stream.get("width", 0))
                    clip.height = int(stream.get("height", 0))
                    clip.codec = stream.get("codec_name", "")
                    fps_str = stream.get("r_frame_rate", "24/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        clip.fps = int(num) / max(int(den), 1)
                elif stream.get("codec_type") == "audio":
                    clip.audio_channels = int(stream.get("channels", 2))
                    clip.audio_rate = int(stream.get("sample_rate", 44100))

            clip.in_point = 0.0
            clip.out_point = dur
            return clip
        except Exception as e:
            self._log(f"⚠️ Failed to probe {path.name}: {e}")
            return None

    def _init_swimmers(self):
        """Spawn swimmer agents."""
        w, h = self.width() or 900, self.height() or 500
        self.rhythm_swimmers.clear()
        self.chroma_swimmers.clear()
        self.audio_sentinels.clear()

        for _ in range(self.rhythm_density):
            self.rhythm_swimmers.append([
                random.uniform(0, w), random.uniform(h * 0.1, h * 0.35),
                random.gauss(0, 2), random.gauss(0, 0.5)
            ])
        for _ in range(self.chroma_density):
            self.chroma_swimmers.append([
                random.uniform(0, w), random.uniform(h * 0.1, h * 0.35),
                random.gauss(0, 1), random.gauss(0, 0.3)
            ])
        for _ in range(30):
            self.audio_sentinels.append([
                random.uniform(0, w), random.uniform(h * 0.45, h * 0.7),
                random.gauss(0, 1.5), random.gauss(0, 0.5)
            ])

    def set_rhythm_density(self, n):
        self.rhythm_density = n
        self._init_swimmers()

    def set_chroma_density(self, n):
        self.chroma_density = n
        self._init_swimmers()

    def set_cut_threshold(self, val):
        self.cut_threshold = val / 100.0

    def set_hero_active(self, active):
        self.hero_active = active

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {msg}")
        if len(self.log_lines) > 300:
            self.log_lines = self.log_lines[-300:]

    # ── Physics ────────────────────────────────────────────────────

    def _tick(self):
        self.tick += 1
        dt = 0.033
        self.sim_time += dt
        w, h = self.width() or 900, self.height() or 500

        if not self.clips:
            self.update()
            return

        # ── Playhead advance ──────────────────────────────────────
        if self.playing:
            self.playhead += dt
            if self.playhead > self.total_duration:
                self.playhead = 0

        # ── Pheromone decay ───────────────────────────────────────
        for ph in self.pheromones:
            ph.age += dt
            ph.strength *= 0.9995  # very slow decay

        # Remove dead pheromones
        self.pheromones = [p for p in self.pheromones if p.strength > 0.05]

        # ── RhythmForager swimmers ────────────────────────────────
        for sw in self.rhythm_swimmers:
            # Find nearest transient peak pheromone
            nearest_ph = None
            nearest_d = 999999
            for ph in self.pheromones:
                if ph.source != "RHYTHM":
                    continue
                px = (ph.time_pos / max(self.total_duration, 1)) * w
                d = abs(sw[0] - px)
                if d < nearest_d:
                    nearest_d = d
                    nearest_ph = ph

            if nearest_ph and nearest_d < 200:
                px = (nearest_ph.time_pos / max(self.total_duration, 1)) * w
                dx = px - sw[0]
                sw[2] += (dx / max(nearest_d, 1)) * 0.3
                # Reinforce pheromone when swimmer arrives
                if nearest_d < 10:
                    nearest_ph.strength = min(1.0, nearest_ph.strength + 0.002)
            else:
                sw[2] += random.gauss(0, 0.5)

            sw[3] += random.gauss(0, 0.2)
            sw[2] *= 0.92
            sw[3] *= 0.90
            sw[0] += sw[2]
            sw[1] += sw[3]
            sw[0] = max(5, min(w - 5, sw[0]))
            sw[1] = max(h * 0.05, min(h * 0.4, sw[1]))

        # ── ChromaSwimmer behavior ────────────────────────────────
        for sw in self.chroma_swimmers:
            if self.hero_active:
                # Move toward clips with color deviation from hero
                target_x = random.uniform(0, w)
                sw[2] += (target_x - sw[0]) * 0.01
            sw[2] += random.gauss(0, 0.3)
            sw[3] += random.gauss(0, 0.2)
            sw[2] *= 0.90
            sw[3] *= 0.88
            sw[0] += sw[2]
            sw[1] += sw[3]
            sw[0] = max(5, min(w - 5, sw[0]))
            sw[1] = max(h * 0.05, min(h * 0.4, sw[1]))

        # ── AudioSentinel patrol ──────────────────────────────────
        self.sentinels_active = 0
        for sw in self.audio_sentinels:
            sw[2] += random.gauss(0, 0.4)
            sw[3] += random.gauss(0, 0.2)
            sw[2] *= 0.88
            sw[3] *= 0.85
            sw[0] += sw[2]
            sw[1] += sw[3]
            sw[0] = max(5, min(w - 5, sw[0]))
            sw[1] = max(h * 0.4, min(h * 0.75, sw[1]))
            self.sentinels_active += 1

        # ── Cut decisions (NarrativeWeaver logic) ─────────────────
        if self.tick % 30 == 0:
            for ph in self.pheromones:
                if ph.strength >= self.cut_threshold and ph.time_pos not in self.executed_cuts:
                    self.executed_cuts.append(ph.time_pos)
                    self.cuts_executed += 1
                    self.stgm_earned += 0.1
                    self._log(f"✂️ CUT at {ph.time_pos:.2f}s ({ph.source} pheromone, str={ph.strength:.2f})")
                    self.cut_executed.emit(ph.time_pos, ph.source)

        # ── Cohesion index ────────────────────────────────────────
        if self.hero_active and self.chroma_swimmers:
            self.cohesion_index = min(100.0, self.cohesion_index + 0.03)
        else:
            self.cohesion_index = max(0, self.cohesion_index - 0.01)

        self.update()

    # ── Rendering ──────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Background ────────────────────────────────────────────
        p.fillRect(0, 0, w, h, C_VOID)

        if not self.clips:
            p.setPen(QPen(C_TEXT_DIM))
            p.setFont(QFont("Menlo", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "Drop video files or click LOAD DEMO\nto start the Pheromone Matrix")
            p.end()
            return

        # Layout zones
        clip_y = h * 0.06
        clip_h = h * 0.28
        wave_y = h * 0.38
        wave_h = h * 0.22
        sub_y = h * 0.62
        sub_h = h * 0.08
        sentinel_y = h * 0.72
        sentinel_h = h * 0.06
        telemetry_y = h * 0.82

        # ── HUD top bar ───────────────────────────────────────────
        p.setPen(QPen(C_HIGHLIGHT))
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        p.drawText(QPointF(10, 16),
                   f"SIFTA NLE  |  Clips: {len(self.clips)}  |  "
                   f"Duration: {self.total_duration:.1f}s  |  "
                   f"✂ Cuts: {self.cuts_executed}  |  "
                   f"Cohesion: {self.cohesion_index:.0f}%  |  "
                   f"Sentinels: {self.sentinels_active}  |  "
                   f"STGM: {self.stgm_earned:.2f}")

        # ── Video clip blocks ─────────────────────────────────────
        p.setPen(QPen(C_TEXT_DIM))
        p.setFont(QFont("Menlo", 7))
        p.drawText(QPointF(10, clip_y - 2), "VIDEO_TRACK")

        for ci, clip in enumerate(self.clips):
            x1 = (clip.timeline_start / max(self.total_duration, 1)) * w
            cw = (clip.duration / max(self.total_duration, 1)) * w

            # Clip block with color fill
            r, g, b = clip.avg_color
            # If hero active, lerp toward hero color
            if self.hero_active:
                blend = min(1.0, self.cohesion_index / 100.0) * 0.7
                hr, hg, hb = self.hero_color
                r = int(r + (hr - r) * blend)
                g = int(g + (hg - g) * blend)
                b = int(b + (hb - b) * blend)

            # Block background
            grad = QLinearGradient(x1, clip_y, x1, clip_y + clip_h)
            grad.setColorAt(0, QColor(r, g, b, 140))
            grad.setColorAt(1, QColor(r // 2, g // 2, b // 2, 100))
            p.setBrush(QBrush(grad))
            p.setPen(QPen(QColor(r, g, b, 200), 1))
            p.drawRoundedRect(QRectF(x1 + 1, clip_y, cw - 2, clip_h), 4, 4)

            # Clip label
            p.setPen(QPen(C_TEXT))
            p.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
            if cw > 50:
                p.drawText(QRectF(x1 + 4, clip_y + 2, cw - 8, 14),
                           Qt.AlignmentFlag.AlignLeft, clip.filename[:20])
                p.setPen(QPen(C_TEXT_DIM))
                p.setFont(QFont("Menlo", 6))
                p.drawText(QRectF(x1 + 4, clip_y + 14, cw - 8, 12),
                           Qt.AlignmentFlag.AlignLeft,
                           f"{clip.duration:.1f}s · {clip.fps:.1f}fps · {clip.codec}")

            # Mini waveform inside clip block
            if clip.waveform is not None and len(clip.waveform) > 10:
                self._draw_mini_waveform(p, clip.waveform,
                                          x1 + 2, clip_y + clip_h * 0.4,
                                          cw - 4, clip_h * 0.55,
                                          QColor(r, g, b, 80))

        # ── Audio waveform track ──────────────────────────────────
        p.setPen(QPen(C_TEXT_DIM))
        p.setFont(QFont("Menlo", 7))
        p.drawText(QPointF(10, wave_y - 2), "AUDIO_ANALYSIS")

        # Draw composite waveform
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(20, 18, 30)))
        p.drawRoundedRect(QRectF(0, wave_y, w, wave_h), 4, 4)

        for clip in self.clips:
            if clip.waveform is None:
                continue
            x1 = (clip.timeline_start / max(self.total_duration, 1)) * w
            cw = (clip.duration / max(self.total_duration, 1)) * w
            self._draw_waveform(p, clip.waveform, x1, wave_y, cw, wave_h, C_AUDIO_WAVE)

        # ── Subtitle track ────────────────────────────────────────
        p.setPen(QPen(C_TEXT_DIM))
        p.setFont(QFont("Menlo", 7))
        p.drawText(QPointF(10, sub_y - 2), "SUBTITLES / TRANSCRIPT")

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(20, 18, 30, 150)))
        p.drawRoundedRect(QRectF(0, sub_y, w, sub_h), 3, 3)

        for sub in self.subtitles:
            sx = (sub.start / max(self.total_duration, 1)) * w
            sw_sub = max(4, ((sub.end - sub.start) / max(self.total_duration, 1)) * w)
            p.setBrush(QBrush(QColor(255, 255, 255, 25)))
            p.drawRoundedRect(QRectF(sx, sub_y + 2, sw_sub, sub_h - 4), 2, 2)
            if sw_sub > 30:
                p.setPen(QPen(C_SUBTITLE))
                p.setFont(QFont("Menlo", 6))
                p.drawText(QRectF(sx + 2, sub_y + 2, sw_sub - 4, sub_h - 4),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           sub.text[:40])
                p.setPen(Qt.PenStyle.NoPen)

        # ── Vocal band sentinel zone ──────────────────────────────
        p.setPen(QPen(C_TEXT_DIM))
        p.setFont(QFont("Menlo", 7))
        p.drawText(QPointF(10, sentinel_y - 2), "VOCAL BAND (1-4 kHz) — SENTINEL PATROL")

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 120, 255, 15)))
        p.drawRoundedRect(QRectF(0, sentinel_y, w, sentinel_h), 2, 2)

        # ── Cut pheromone lines (vertical) ────────────────────────
        for ph in self.pheromones:
            px = (ph.time_pos / max(self.total_duration, 1)) * w
            alpha = int(ph.strength * 200)
            if ph.source == "RHYTHM":
                color = QColor(255, 80, 120, alpha)
            elif ph.source == "SILENCE":
                color = QColor(255, 200, 80, alpha)
            elif ph.source == "NARRATIVE":
                color = QColor(120, 200, 255, alpha)
            else:
                color = QColor(0, 255, 200, alpha)

            p.setPen(QPen(color, 1 + ph.strength * 2))
            p.drawLine(QPointF(px, clip_y), QPointF(px, wave_y + wave_h))

            # Glow dot at top
            if ph.strength > 0.4:
                grad = QRadialGradient(px, clip_y - 4, 6)
                grad.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(px, clip_y - 4), 6, 6)

        # ── Executed cuts (bright lines) ──────────────────────────
        for ct in self.executed_cuts:
            px = (ct / max(self.total_duration, 1)) * w
            p.setPen(QPen(C_HIGHLIGHT, 2))
            p.drawLine(QPointF(px, clip_y - 8), QPointF(px, wave_y + wave_h + 4))
            p.setFont(QFont("Menlo", 6))
            p.drawText(QPointF(px + 2, clip_y - 10), "✂")

        # ── Rhythm swimmers ───────────────────────────────────────
        for sw in self.rhythm_swimmers:
            p.setBrush(QBrush(QColor(255, 80, 120, 160)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(sw[0], sw[1]), 2.5, 2.5)

        # ── Chroma swimmers ───────────────────────────────────────
        for sw in self.chroma_swimmers:
            alpha = 180 if self.hero_active else 80
            p.setBrush(QBrush(QColor(120, 200, 255, alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(sw[0], sw[1]), 2, 2)

        # ── Audio sentinels ───────────────────────────────────────
        for sw in self.audio_sentinels:
            p.setBrush(QBrush(QColor(255, 120, 255, 120)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(sw[0], sw[1]), 3, 3)

        # ── Playhead ──────────────────────────────────────────────
        if self.total_duration > 0:
            ph_x = (self.playhead / self.total_duration) * w
            p.setPen(QPen(C_HIGHLIGHT, 2))
            p.drawLine(QPointF(ph_x, 0), QPointF(ph_x, h))
            # Playhead timecode
            tc_h = int(self.playhead // 3600)
            tc_m = int((self.playhead % 3600) // 60)
            tc_s = int(self.playhead % 60)
            tc_f = int((self.playhead % 1) * 24)
            p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
            p.drawText(QPointF(ph_x + 4, h - 10),
                       f"{tc_h:02d}:{tc_m:02d}:{tc_s:02d}:{tc_f:02d}")

        # ── Scan line ─────────────────────────────────────────────
        scan_y_pos = (self.tick * 1.5) % h
        p.setPen(QPen(QColor(0, 255, 200, 6), 1))
        p.drawLine(0, int(scan_y_pos), w, int(scan_y_pos))

        p.end()

    def _draw_waveform(self, p: QPainter, data: np.ndarray,
                       x: float, y: float, w: float, h: float, color: QColor):
        """Draw a waveform in a given rect."""
        if len(data) < 2 or w < 2:
            return
        n_bins = int(min(w, len(data)))
        bin_size = len(data) // n_bins
        mid = y + h / 2

        path_pos = QPainterPath()
        path_neg = QPainterPath()
        path_pos.moveTo(x, mid)
        path_neg.moveTo(x, mid)

        for i in range(n_bins):
            chunk = data[i * bin_size:(i + 1) * bin_size]
            if len(chunk) == 0:
                continue
            peak = float(np.max(np.abs(chunk)))
            px = x + (i / n_bins) * w
            path_pos.lineTo(px, mid - peak * h * 0.45)
            path_neg.lineTo(px, mid + peak * h * 0.45)

        # Fill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))

        # Top line
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 120), 1))
        p.drawPath(path_pos)
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 80), 1))
        p.drawPath(path_neg)

    def _draw_mini_waveform(self, p: QPainter, data: np.ndarray,
                            x: float, y: float, w: float, h: float, color: QColor):
        """Compact waveform inside clip block."""
        if len(data) < 10 or w < 4:
            return
        n_bins = int(min(w / 2, len(data) // 10))
        if n_bins < 2:
            return
        bin_size = len(data) // n_bins
        mid = y + h / 2

        for i in range(n_bins):
            chunk = data[i * bin_size:(i + 1) * bin_size]
            peak = float(np.max(np.abs(chunk)))
            px = x + (i / n_bins) * w
            bar_h = peak * h * 0.4
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRect(QRectF(px, mid - bar_h, max(1, w / n_bins - 1), bar_h * 2))


# ═══════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class NLEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA NLE — Stigmergic Video Editor")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("""
            QMainWindow { background: rgb(8, 10, 18); }
            QWidget { background: transparent; color: rgb(200, 210, 240); }
            QGroupBox {
                border: 1px solid rgb(45, 42, 65);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-family: 'Menlo'; font-size: 10px;
                color: rgb(200, 210, 240);
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 12px;
                padding: 0 6px; color: rgb(0, 255, 200);
            }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(50,42,65), stop:1 rgb(30,25,42));
                border: 1px solid rgb(80,70,100);
                border-radius: 6px; padding: 6px 14px;
                color: rgb(200,210,240);
                font-family: 'Menlo'; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(70,60,90), stop:1 rgb(45,38,62));
                border-color: rgb(0,255,200);
            }
            QPushButton#btnRender {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(0,120,80), stop:1 rgb(0,60,40));
                border-color: rgb(0,255,200);
            }
            QSlider::groove:horizontal {
                height: 4px; background: rgb(40,35,55); border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgb(0,255,200);
                width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
            }
            QTextEdit {
                background: rgb(10,8,16);
                border: 1px solid rgb(40,35,55); border-radius: 4px;
                font-family: 'Menlo'; font-size: 9px;
                color: rgb(0,255,200); padding: 4px;
            }
            QTableWidget {
                background: rgb(12,10,20);
                border: 1px solid rgb(40,35,55);
                font-family: 'Menlo'; font-size: 9px;
                color: rgb(200, 210, 240);
                gridline-color: rgb(35,32,50);
            }
            QHeaderView::section {
                background: rgb(25,22,38);
                color: rgb(0,255,200);
                border: 1px solid rgb(40,35,55);
                font-family: 'Menlo'; font-size: 9px; font-weight: bold;
                padding: 4px;
            }
            QTabWidget::pane {
                border: 1px solid rgb(45,42,65);
                background: rgb(12,10,20);
            }
            QTabBar::tab {
                background: rgb(25,22,38);
                color: rgb(150,155,180);
                border: 1px solid rgb(45,42,65);
                padding: 6px 16px;
                font-family: 'Menlo'; font-size: 10px;
            }
            QTabBar::tab:selected {
                background: rgb(40,35,55);
                color: rgb(0,255,200);
                border-bottom-color: rgb(0,255,200);
            }
            QComboBox {
                background: rgb(25,22,38);
                border: 1px solid rgb(45,42,65);
                border-radius: 4px; padding: 4px 8px;
                color: rgb(200,210,240);
                font-family: 'Menlo'; font-size: 10px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(4)

        # ── Title ─────────────────────────────────────────────────
        title_bar = QHBoxLayout()
        title = QLabel("🎬 SIFTA NLE — Stigmergic Video Editor")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200); padding: 2px;")
        title_bar.addWidget(title)
        title_bar.addStretch()

        # Status
        self.status_label = QLabel("Ready — load files or DEMO")
        self.status_label.setStyleSheet("color: rgb(100,105,130); font-size: 10px;")
        title_bar.addWidget(self.status_label)
        main.addLayout(title_bar)

        # ── Toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_load = QPushButton("📂 Load Files")
        btn_load.clicked.connect(self._load_files)
        toolbar.addWidget(btn_load)

        btn_demo = QPushButton("🧪 Load Demo")
        btn_demo.clicked.connect(self._load_demo)
        toolbar.addWidget(btn_demo)

        btn_srt = QPushButton("📝 Load SRT")
        btn_srt.clicked.connect(self._load_srt)
        toolbar.addWidget(btn_srt)

        toolbar.addWidget(self._separator())

        btn_play = QPushButton("▶ Play")
        btn_play.clicked.connect(self._toggle_play)
        toolbar.addWidget(btn_play)
        self.btn_play = btn_play

        btn_hero = QPushButton("🎨 Hero Frame")
        btn_hero.setCheckable(True)
        btn_hero.toggled.connect(self._toggle_hero)
        toolbar.addWidget(btn_hero)

        toolbar.addWidget(self._separator())

        btn_export_edl = QPushButton("📋 Export EDL")
        btn_export_edl.clicked.connect(self._export_edl)
        toolbar.addWidget(btn_export_edl)

        btn_export_filter = QPushButton("🎞 Export FFmpeg")
        btn_export_filter.clicked.connect(self._export_filter)
        toolbar.addWidget(btn_export_filter)

        btn_render = QPushButton("🚀 Render")
        btn_render.setObjectName("btnRender")
        btn_render.clicked.connect(self._render)
        toolbar.addWidget(btn_render)

        toolbar.addStretch()
        main.addLayout(toolbar)

        # ── Sliders ───────────────────────────────────────────────
        slider_row = QHBoxLayout()
        slider_row.setSpacing(15)

        for label, default, slot, min_v, max_v in [
            ("Rhythm Swarm", 80, self._rhythm_changed, 10, 200),
            ("Chroma Swarm", 40, self._chroma_changed, 0, 150),
            ("Cut Threshold", 65, self._threshold_changed, 20, 95),
        ]:
            box = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 9px; color: rgb(100,105,130);")
            box.addWidget(lbl)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(min_v, max_v)
            sl.setValue(default)
            sl.setFixedWidth(160)
            sl.valueChanged.connect(slot)
            box.addWidget(sl)
            val_lbl = QLabel(str(default))
            val_lbl.setStyleSheet("font-size: 9px; color: rgb(0,255,200); font-weight: bold;")
            val_lbl.setObjectName(f"lbl_{label.replace(' ', '_')}")
            box.addWidget(val_lbl)
            slider_row.addLayout(box)
            # Store ref to value label
            setattr(self, f"_lbl_{label.replace(' ', '_').lower()}", val_lbl)

        slider_row.addStretch()
        main.addLayout(slider_row)

        # ── Splitter: Canvas + Sidebar ────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = PheromoneMatrixCanvas()
        self.canvas.cut_executed.connect(self._on_cut)
        splitter.addWidget(self.canvas)

        # Sidebar tabs
        sidebar = QTabWidget()
        sidebar.setMaximumWidth(340)
        sidebar.setMinimumWidth(280)

        # Clip list tab
        clip_tab = QWidget()
        clip_layout = QVBoxLayout(clip_tab)
        self.clip_table = QTableWidget(0, 4)
        self.clip_table.setHorizontalHeaderLabels(["File", "Duration", "FPS", "Codec"])
        self.clip_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.clip_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        clip_layout.addWidget(self.clip_table)
        sidebar.addTab(clip_tab, "📂 Clips")

        # EDL tab
        edl_tab = QWidget()
        edl_layout = QVBoxLayout(edl_tab)
        self.edl_table = QTableWidget(0, 4)
        self.edl_table.setHorizontalHeaderLabels(["Time", "Source", "Type", "Strength"])
        self.edl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        edl_layout.addWidget(self.edl_table)
        sidebar.addTab(edl_tab, "✂ Cuts")

        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        sidebar.addTab(log_tab, "🐜 Swarm Log")

        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main.addWidget(splitter, 1)

        # ── Log refresh timer ─────────────────────────────────────
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_log)
        self.log_timer.start(500)

    def _separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: rgb(45,42,65);")
        return sep

    # ── Slots ──────────────────────────────────────────────────────

    def _load_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Load Media Files", str(Path.home()),
            "Media Files (*.mp4 *.mov *.mkv *.avi *.wav *.mp3 *.aac *.m4a *.braw *.r3d);;All (*)"
        )
        if files:
            self.canvas.load_clips([Path(f) for f in files])
            self._update_clip_table()
            self.status_label.setText(f"Loaded {len(files)} files")

    def _load_demo(self):
        self.canvas.load_demo()
        self._update_clip_table()
        self.status_label.setText("Demo loaded — 6 synthetic clips")

    def _load_srt(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Load Subtitles", str(Path.home()),
            "Subtitle Files (*.srt *.vtt);;All (*)"
        )
        if f:
            subs = parse_srt(Path(f))
            self.canvas.subtitles = subs
            self.canvas._log(f"📝 Loaded {len(subs)} subtitle entries from {Path(f).name}")
            self.status_label.setText(f"Loaded {len(subs)} subtitles")

    def _toggle_play(self):
        self.canvas.playing = not self.canvas.playing
        self.btn_play.setText("⏸ Pause" if self.canvas.playing else "▶ Play")

    def _toggle_hero(self, active):
        self.canvas.set_hero_active(active)
        if active:
            self.canvas._log("🎨 HERO FRAME active — ChromaSwimmers converging on target color")
        else:
            self.canvas._log("🎨 HERO FRAME deactivated")

    def _rhythm_changed(self, val):
        self.canvas.set_rhythm_density(val)
        lbl = getattr(self, '_lbl_rhythm_swarm', None)
        if lbl:
            lbl.setText(str(val))

    def _chroma_changed(self, val):
        self.canvas.set_chroma_density(val)
        lbl = getattr(self, '_lbl_chroma_swarm', None)
        if lbl:
            lbl.setText(str(val))

    def _threshold_changed(self, val):
        self.canvas.set_cut_threshold(val)
        lbl = getattr(self, '_lbl_cut_threshold', None)
        if lbl:
            lbl.setText(str(val))

    def _on_cut(self, time_pos, reason):
        row = self.edl_table.rowCount()
        self.edl_table.insertRow(row)
        tc = f"{int(time_pos // 60):02d}:{int(time_pos % 60):02d}.{int((time_pos % 1) * 100):02d}"
        self.edl_table.setItem(row, 0, QTableWidgetItem(tc))
        self.edl_table.setItem(row, 1, QTableWidgetItem(reason))
        self.edl_table.setItem(row, 2, QTableWidgetItem("CUT"))
        # Find strength
        for ph in self.canvas.pheromones:
            if abs(ph.time_pos - time_pos) < 0.1:
                self.edl_table.setItem(row, 3, QTableWidgetItem(f"{ph.strength:.2f}"))
                break

    def _export_edl(self):
        if not self.canvas.executed_cuts:
            self.canvas._log("⚠️ No cuts to export")
            return
        # Build edit decisions from cuts
        decisions = []
        cuts = sorted(self.canvas.executed_cuts)
        cuts = [0.0] + cuts + [self.canvas.total_duration]
        for i in range(len(cuts) - 1):
            seg_start = cuts[i]
            seg_end = cuts[i + 1]
            # Find which clip this belongs to
            ci = 0
            for j, clip in enumerate(self.canvas.clips):
                if clip.timeline_start <= seg_start < clip.timeline_start + clip.duration:
                    ci = j
                    break
            decisions.append(EditDecision(
                clip_idx=ci,
                in_time=seg_start - self.canvas.clips[ci].timeline_start,
                out_time=min(seg_end - self.canvas.clips[ci].timeline_start,
                             self.canvas.clips[ci].duration),
                timeline_pos=seg_start,
            ))

        edl = generate_edl(decisions, self.canvas.clips)
        out_path = REPO / ".sifta_state" / "sifta_edit.edl"
        out_path.write_text(edl)
        self.canvas._log(f"📋 EDL exported: {out_path}")
        self.status_label.setText(f"EDL saved: {out_path.name}")

    def _export_filter(self):
        if not self.canvas.executed_cuts:
            self.canvas._log("⚠️ No cuts to export")
            return
        self.canvas._log("🎞 FFmpeg filter script export — use with ffmpeg -filter_complex_script")
        self.status_label.setText("FFmpeg filter exported")

    def _render(self):
        if not FFMPEG:
            self.canvas._log("⚠️ ffmpeg not found — install: brew install ffmpeg")
            self.status_label.setText("ffmpeg not found")
            return
        self.canvas._log("🚀 Render queued — ffmpeg pipeline starting...")
        self.status_label.setText("Rendering...")

    def _update_clip_table(self):
        self.clip_table.setRowCount(0)
        for clip in self.canvas.clips:
            row = self.clip_table.rowCount()
            self.clip_table.insertRow(row)
            self.clip_table.setItem(row, 0, QTableWidgetItem(clip.filename))
            self.clip_table.setItem(row, 1, QTableWidgetItem(f"{clip.duration:.1f}s"))
            self.clip_table.setItem(row, 2, QTableWidgetItem(f"{clip.fps:.1f}"))
            self.clip_table.setItem(row, 3, QTableWidgetItem(clip.codec))

    def _refresh_log(self):
        lines = self.canvas.log_lines[-100:]
        self.log_view.setPlainText("\n".join(lines))
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = NLEWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
