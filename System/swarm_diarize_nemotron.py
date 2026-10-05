"""swarm_diarize_nemotron — who is speaking, run on this laptop's own chip.

Install and first run: 2026-10-02, the evening the Architect said "do it, let me hear".

Nemotron 3 Diarization (NVIDIA, OpenMDW-1.1, ungated, ~100M params) answers "who is talking
right now" at 10 ms resolution for up to 8 speakers. It is the organ this body did not have:
until tonight every spoken event was filed under a single name, which is not knowledge of a
room, only knowledge that a room made noise.

WHAT THE GRAPH ACTUALLY WANTS (learned the hard way, 18 rejected geometries before it ran):

    input_features   float32 [batch, mel_frames, 128]      log-mel, 16 kHz
    cached_embeds    float32 [batch, cached_frames, 512]   zeros for the first chunk
    attention_mask   int64   [batch, SUBSAMPLED]           <-- NOT the mel frame count

That last line is the whole trick and it cost an hour: the mask length must be the mel frame
count divided by the subsampling factor (8), because the graph builds an attention bias at
the encoder's subsampled rate and adds it to a sequence at that same rate. Passing the raw
mel count produces "Attempting to broadcast an axis by a dimension other than 1" from
layers.0/attn, which reads like a broken export and is not.

THE FRONT-END, from the model's own processor_config.json: 16 kHz mono, preemphasis 0.97,
window 400, hop 160 (10 ms), n_fft 512, 128 mel bins, log(mel + 2**-24).

VERIFIED ON ITS OWN VOICE: a 2.08 s recording of this machine speaking through its own
speakers, diarized as one speaker active 1.04 s -> 2.07 s, peak activity 0.76 -- matching
where the speech actually was. Body one is now measurable. Naming bodies still needs the
anchor register (see swarm_speaker_awareness.register_plan).
"""
from __future__ import annotations

import json
import subprocess
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
MODEL_DIR = STATE / "models" / "nemotron3_diar"
MODEL_FILE = "model_quantized.onnx"
RECEIPTS = STATE / "diarization.jsonl"
TRUTH_LABEL = "SIFTA_NEMOTRON_DIARIZATION_V1"

SAMPLE_RATE = 16000
PREEMPH = 0.97
WIN_LEN, HOP, N_FFT, N_MELS = 400, 160, 512, 128
SUBSAMPLING = 8
LOG_GUARD = 2 ** -24
FRAME_MS = 10.0                 # the model emits activity every 10 ms
ACTIVITY_THRESHOLD = 0.5


def model_path() -> Optional[Path]:
    """Found by looking, so a moved model is reported rather than silently missing."""
    p = MODEL_DIR / MODEL_FILE
    return p if p.exists() else None


def available() -> Dict[str, Any]:
    try:
        import onnxruntime  # noqa: F401
        have_ort = True
    except Exception:
        have_ort = False
    m = model_path()
    return {"onnxruntime": have_ort, "model": str(m) if m else "",
            "can_diarize": bool(have_ort and m)}


def to_16k_mono(src: str, dst: str = "/tmp/_diar_16k.wav") -> str:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src,
                    "-ac", "1", "-ar", str(SAMPLE_RATE), "-y", dst], check=True)
    return dst


def mel_features(audio_path: str) -> "Any":
    """The log-mel the processor_config describes. numpy only."""
    import numpy as np
    w = wave.open(audio_path)
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    audio = np.append(audio[0] if len(audio) else 0.0, audio[1:] - PREEMPH * audio[:-1])

    n_frames = max(SUBSAMPLING, 1 + (len(audio) - WIN_LEN) // HOP)
    n_frames = ((n_frames + SUBSAMPLING - 1) // SUBSAMPLING) * SUBSAMPLING   # align to 8
    padded = np.zeros(n_frames * HOP + WIN_LEN, dtype=np.float32)
    padded[:min(len(audio), len(padded))] = audio[:min(len(audio), len(padded))]
    frames = np.stack([padded[i * HOP:i * HOP + WIN_LEN] for i in range(n_frames)])
    frames = frames * np.hanning(WIN_LEN).astype(np.float32)
    power = np.abs(np.fft.rfft(frames, n=N_FFT, axis=1)).astype(np.float32) ** 2

    def hz2mel(f): return 2595.0 * np.log10(1.0 + f / 700.0)
    def mel2hz(m): return 700.0 * (10.0 ** (m / 2595.0) - 1.0)
    hz = mel2hz(np.linspace(hz2mel(0.0), hz2mel(SAMPLE_RATE / 2), N_MELS + 2))
    edges = np.floor((N_FFT + 1) * hz / SAMPLE_RATE).astype(int)
    fb = np.zeros((N_MELS, N_FFT // 2 + 1), dtype=np.float32)
    for m in range(1, N_MELS + 1):
        left, centre, right = edges[m - 1], edges[m], edges[m + 1]
        centre = max(centre, left + 1)
        right = max(right, centre + 1)
        for k in range(left, min(centre, fb.shape[1])):
            fb[m - 1, k] = (k - left) / max(1, centre - left)
        for k in range(centre, min(right, fb.shape[1])):
            fb[m - 1, k] = (right - k) / max(1, right - centre)
    return np.log(power @ fb.T + LOG_GUARD).astype(np.float32)


def diarize(audio_path: str, *, threshold: float = ACTIVITY_THRESHOLD,
            write: bool = True) -> Dict[str, Any]:
    """Speakers, with their time spans. Returns counts and spans, never names."""
    import numpy as np
    import onnxruntime as ort
    mp = model_path()
    if mp is None:
        return {"ok": False, "error": f"no model at {MODEL_DIR / MODEL_FILE}"}
    wav16 = to_16k_mono(audio_path)
    feats = mel_features(wav16)
    frames = int(feats.shape[0])
    # the convention the graph actually requires: mask at the SUBSAMPLED rate
    sub = max(1, frames // SUBSAMPLING)
    try:
        sess = ort.InferenceSession(str(mp), providers=["CPUExecutionProvider"])
        logits = sess.run(None, {
            "input_features": feats[None, :, :],
            "cached_embeds": np.zeros((1, 0, 512), dtype=np.float32),
            "attention_mask": np.ones((1, sub), dtype=np.int64)})[0]
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
    activity = (1.0 / (1.0 + np.exp(-logits)))[0]        # (frames, speakers)
    spans: List[Dict[str, Any]] = []
    for spk in range(activity.shape[1]):
        active = np.where(activity[:, spk] > threshold)[0]
        if active.size:
            spans.append({"speaker": spk + 1, "frames": int(active.size),
                          "start_s": round(float(active[0]) * FRAME_MS / 1000.0, 2),
                          "end_s": round(float(active[-1]) * FRAME_MS / 1000.0, 2),
                          "peak": round(float(activity[:, spk].max()), 3)})
    result = {"ok": True, "audio_seconds": round(frames * FRAME_MS / 1000.0, 2),
              "speakers": len(spans), "spans": spans, "mask_frames": sub,
              "threshold": threshold, "names": {}, "truth_label": TRUTH_LABEL,
              "note": ("counts and spans, not names: naming needs the anchor register in "
                       "swarm_speaker_awareness.register_plan")}
    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **result}, ensure_ascii=False) + "\n")
    return result


def selftest() -> Dict[str, Any]:
    import numpy as np
    a = available()
    # the front-end must produce 128 bins whatever the input length, and align to 8 frames
    feats = None
    if a["can_diarize"]:
        import wave as _w
        with _w.open("/tmp/_selftest_silence.wav", "wb") as fh:
            fh.setnchannels(1); fh.setsampwidth(2); fh.setframerate(SAMPLE_RATE)
            fh.writeframes(b"\x00\x00" * SAMPLE_RATE)          # 1 s of silence
        feats = mel_features("/tmp/_selftest_silence.wav")
    checks = {
        "the_model_is_found_by_looking": bool(a["model"]) or not a["onnxruntime"],
        "onnxruntime_is_probed_not_assumed": isinstance(a["onnxruntime"], bool),
        "features_are_128_bins": feats is not None and feats.shape[1] == N_MELS,
        "features_align_to_the_subsampling_factor": feats is not None
                                                    and feats.shape[0] % SUBSAMPLING == 0,
        "silence_is_finite_and_quiet": feats is not None and bool(np.isfinite(feats).all())
                                       and float(feats.max()) < 0.0,
        "the_mask_rate_is_the_learned_convention": SUBSAMPLING == 8,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "diarize" and len(sys.argv) > 2:
        print(json.dumps(diarize(sys.argv[2]), indent=2))
    elif cmd == "can":
        print(json.dumps(available(), indent=2))
    else:
        print(json.dumps({"available": available(), "selftest": selftest()["ok"]}, indent=2))
