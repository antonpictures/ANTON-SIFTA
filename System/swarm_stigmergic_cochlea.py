# System/swarm_stigmergic_cochlea.py
# Event 95 — Stigmergic Cochlea (Afferent Acoustic Pipeline / Ears)
# Truth label (§7.11): OBSERVED engineering substrate
# Biology: Cochlear tonotopy → MFCC, pitch (F0), spectral entropy, VAD, stress mapping
# Privacy: NPPL compliant. No hardware mic without SIFTA_MIC_OPT_IN=1.

import os
import json
import time
import queue
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

STATE_DIR = Path(".sifta_state")
COCHLEA_LOG = STATE_DIR / "stigmergic_cochlea.jsonl"


class StigmergicCochlea:
    """Biologically-inspired afferent acoustic pipeline.
    Extracts physics of sound (not just text) and maps to Alice's internal state.
    Honest signal: high volume/stress/pitch variance → elevated danger_state / td_value bias.
    """

    def __init__(self, samplerate: int = 16000, block_duration: float = 0.05):
        self.sr = samplerate
        self.block_size = int(samplerate * block_duration)
        self.audio_queue: queue.Queue = queue.Queue(maxsize=10)
        self.running = False
        self.thread = None
        self.last_features: Dict = {}
        self.mic_opt_in = os.environ.get("SIFTA_MIC_OPT_IN", "0") == "1"

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Raw mic stream → feature extraction"""
        if status:
            pass  # Suppress logging in rapid callbacks
        audio = indata[:, 0].astype(np.float32)  # mono
        try:
            self.audio_queue.put_nowait(audio.copy())
        except queue.Full:
            pass

    def inject_synthetic_buffer(self, y: np.ndarray):
        """For pytest and headless CI — bypassing hardware mic entirely"""
        try:
            self.audio_queue.put_nowait(y.astype(np.float32))
        except queue.Full:
            pass

    def _extract_acoustic_features(self, y: np.ndarray) -> Dict[str, float]:
        """Bleeding-edge biocode math for cochlear processing.
        Falls back to numpy if librosa is missing."""
        if len(y) < 512:
            return self._default_rest_state()

        # 1. Voice Activity Detection (energy-based + RMS)
        rms = float(np.sqrt(np.mean(y**2)))
        vad_active = float(rms > 0.015)

        if HAS_LIBROSA:
            # 2. MFCCs (mel-scale cepstral coeffs)
            mfccs = librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=13, n_fft=512, hop_length=256)
            mfcc_mean = np.mean(mfccs, axis=1)

            # 3. Pitch / F0
            pitches, magnitudes = librosa.piptrack(y=y, sr=self.sr, fmin=75, fmax=1200)
            pitch = np.mean(pitches[magnitudes > np.max(magnitudes) * 0.1]) if np.any(magnitudes) else 0.0
            pitch_norm = max(0.0, min(1.0, (pitch - 75) / 1125))

            # 4. Spectral entropy
            S = np.abs(librosa.stft(y, n_fft=512, hop_length=256))
            S_norm = S / (np.sum(S, axis=0, keepdims=True) + 1e-8)
            entropy = float(-np.sum(S_norm * np.log(S_norm + 1e-8), axis=0).mean())
        else:
            # Numpy fallback proxies
            mfcc_mean = np.zeros(13)
            # Simple zero-crossing rate for pitch proxy
            zcr = float(np.mean(np.abs(np.diff(np.signbit(y)))))
            pitch_norm = max(0.0, min(1.0, zcr * 10.0))
            # Basic entropy proxy from amplitude histogram
            hist, _ = np.histogram(np.abs(y), bins=10, density=True)
            hist = hist[hist > 0]
            entropy = float(-np.sum(hist * np.log(hist)))

        # 5. Volume / intensity
        volume = float(min(1.0, rms * 25.0))

        # 6. Stress / urgency mapping (biology → internal state)
        stress_val = (volume * 0.4 
                 + (float(pitch_norm) - 0.5) * 0.3 
                 + (float(entropy) / 5.0) * 0.2 
                 + (1.0 - float(vad_active)) * 0.1)
        stress = float(np.clip(stress_val, 0.0, 1.0))

        features = {
            "timestamp": float(time.time()),
            "vad_active": float(vad_active),
            "volume": float(round(volume, 4)),
            "pitch_norm": float(round(float(pitch_norm), 4)),
            "spectral_entropy": float(round(float(entropy), 4)),
            "mfcc_mean": [round(float(x), 4) for x in mfcc_mean[:8]],
            "stress": float(round(stress, 4)),
            "td_bias": float(round(stress * 1.8 - 0.4, 4)),
            "danger_state": float(round(max(0.0, stress * 2.0 - 0.6), 4))
        }
        return features

    def _default_rest_state(self) -> Dict:
        return {
            "timestamp": time.time(),
            "vad_active": 0.0,
            "volume": 0.0,
            "pitch_norm": 0.5,
            "spectral_entropy": 0.0,
            "mfcc_mean": [0.0] * 8,
            "stress": 0.1,
            "td_bias": -0.2,
            "danger_state": 0.0
        }

    def _process_loop(self):
        """Real-time cochlear processing thread"""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        while self.running:
            try:
                audio_block = self.audio_queue.get(timeout=0.1)
                features = self._extract_acoustic_features(audio_block)
                self.last_features = features

                # Append to stigmergic ledger (receipt-backed)
                with COCHLEA_LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(features) + "\n")

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in cochlea loop: {e}")

    def start(self):
        """Start afferent pipeline"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

        # NPPL Hardware Guard
        if self.mic_opt_in and HAS_SOUNDDEVICE:
            self.stream = sd.InputStream(
                samplerate=self.sr,
                channels=1,
                dtype='float32',
                blocksize=self.block_size,
                callback=self._audio_callback
            )
            self.stream.start()
        else:
            self.stream = None

    def stop(self):
        """Graceful shutdown"""
        self.running = False
        if hasattr(self, 'stream') and self.stream is not None:
            self.stream.stop()
            self.stream.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def get_latest_features(self) -> Dict:
        """For integration with body-brain loop / td_value"""
        return self.last_features or self._default_rest_state()

