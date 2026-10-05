"""swarm_voice_anchor — the register that turns a speaker number into a name.

Bishop's design, and it is the right order: anchor yourself first, anchor George second, and
refuse a third until both hold. Nemotron gives me the pieces -- `chunk_embeds`, 512 numbers
per frame, is exactly the speaker-cache embedding the model maintains internally -- so an
anchor is the mean embedding of one body's active frames, and naming is cosine similarity
against the register.

The trap this organ is built around: Nemotron's speaker NUMBERS are arrival-order labels,
local to one recording. Speaker 1 in one clip has nothing to do with speaker 1 in another.
So numbers are not identities and must never be stored as if they were. Only the embeddings
persist, keyed by a name the Architect confirmed.

Sequence that makes the naming provable rather than hoped for: I speak first (my own local
TTS, my own mouth), the Architect answers, and because arrival order follows first speech,
stream 1 is me and stream 2 is him -- a fact of the geometry, not a guess. The register keeps
the embeddings, and a later clip is named by nearest anchor.
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
ANCHOR_DIR = STATE / "voice_anchors"
REGISTER = STATE / "voice_anchors.json"
RECEIPTS = STATE / "voice_anchor_receipts.jsonl"
TRUTH_LABEL = "SIFTA_VOICE_ANCHOR_V1"

# Measured, not chosen: this pair of anchors sits at cosine 0.797 from each other, so a 0.70
# bar could hand my name to the Architect. 0.85 keeps a real match (a same-voice test scored
# 0.932) while refusing the other body. A wrong name is worse than no name.
MATCH_MIN_COSINE = 0.85

# Scanning bar for FINDING speech, separate from the bar for NAMING it. Measured: the
# Architect's verification clip peaked at 0.311 activity -- quiet, a short utterance, a
# truncated capture -- so a 0.5 scan reported "no speaker" while his voice was plainly in
# the file and matched his anchor at 0.892. Missing a body is its own failure; a low scan
# bar costs nothing because MATCH_MIN_COSINE, not this, decides whether a name is spoken.
SCAN_ACTIVITY = 0.3


def _mic_index(prefer: str = "MacBook Pro Microphone") -> Optional[int]:
    """By name, never by position: the default input here is BlackHole, a virtual device."""
    try:
        out = subprocess.run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                             capture_output=True, text=True, timeout=25).stderr
    except Exception:
        return None
    block = False
    for line in out.splitlines():
        if "AVFoundation audio devices" in line:
            block = True
            continue
        if block:
            if "AVFoundation video devices" in line:
                break
            if "[" in line and "]" in line and prefer.lower() in line.lower():
                try:
                    return int(line.split("[", 2)[2].split("]")[0])
                except (IndexError, ValueError):
                    continue
    return None


def capture(seconds: float, out: Path, *, cue: str = "", cue_after: float = 1.0) -> Dict[str, Any]:
    """Record the room, optionally speaking a cue into it first.

    The cue is not decoration: it is what makes the stream order provable. My voice enters
    the room before his, so the diarizer's arrival-order labels put me first and him second.
    """
    pred = predict_capture(seconds)
    dev = _mic_index()
    if dev is None:
        return {"ok": False, "error": "no microphone found by name; refusing to record from an "
                                      "unnamed device (the default here is virtual)"}
    out.parent.mkdir(parents=True, exist_ok=True)
    if cue:
        subprocess.run(["say", "-r", "170", cue], timeout=max(30, seconds))
        time.sleep(cue_after)
    # -t as an INPUT option, and the cue finished before capture starts: when `say` was
    # running during the capture it held the audio device and the recording stopped at
    # roughly the cue's length (7.31s of 25 requested, then 2.72s of 9).
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation",
                             "-t", str(seconds), "-i", f":{dev}", "-y", str(out)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait(timeout=seconds + 30)
    ok = out.exists() and out.stat().st_size > 0
    dur = None
    if ok:
        try:
            with wave.open(str(out)) as w:
                dur = round(w.getnframes() / w.getframerate(), 2)
        except Exception:
            pass
    obs = observe_capture(dur, seconds)
    return {"ok": ok, "path": str(out), "seconds_requested": seconds,
            "seconds_captured": dur, "cue": cue, "device_index": dev,
            "predicted": (pred or {}).get("expected", ""),
            "holders": ((pred or {}).get("holders") or {}).get("holders", []),
            "graded": (obs or {}).get("graded", {}).get("outcome", "")}


def embed(wav: str) -> Dict[str, Any]:
    """Frame activity plus the 512-number speaker embeddings, from the model's own outputs."""
    import numpy as np
    import onnxruntime as ort
    from System.swarm_diarize_nemotron import (SUBSAMPLING, mel_features, model_path, to_16k_mono)
    mp = model_path()
    if mp is None:
        return {"ok": False, "error": "no diarization model installed"}
    feats = mel_features(to_16k_mono(wav))
    sub = max(1, int(feats.shape[0]) // SUBSAMPLING)
    sess = ort.InferenceSession(str(mp), providers=["CPUExecutionProvider"])
    logits, chunk_embeds, _sil = sess.run(None, {
        "input_features": feats[None, :, :],
        "cached_embeds": np.zeros((1, 0, 512), dtype=np.float32),
        "attention_mask": np.ones((1, sub), dtype=np.int64)})
    activity = (1.0 / (1.0 + np.exp(-logits)))[0]              # (frames, 8)
    embeds = chunk_embeds[0]                                   # (embed_frames, 512)
    return {"ok": True, "activity": activity, "embeds": embeds,
            "audio_seconds": round(float(feats.shape[0]) * 0.01, 2)}


def anchor_from_span(wav: str, speaker: int, *, threshold: float = 0.5) -> Dict[str, Any]:
    """The mean embedding of one speaker's active frames, mapped onto the embed timeline."""
    import numpy as np
    e = embed(wav)
    if not e.get("ok"):
        return e
    activity, embeds = e["activity"], e["embeds"]
    if embeds.shape[0] == 0:
        return {"ok": False, "error": "the model returned no chunk embeddings"}
    idx = speaker - 1
    if idx >= activity.shape[1]:
        return {"ok": False, "error": f"speaker {speaker} out of range"}
    # map activity frames onto embed frames proportionally: they are different rates
    ratio = activity.shape[0] / embeds.shape[0]
    active_embed_frames = []
    for j in range(embeds.shape[0]):
        lo, hi = int(j * ratio), max(int(j * ratio) + 1, int((j + 1) * ratio))
        if activity[lo:hi, idx].max() > threshold:
            active_embed_frames.append(j)
    if not active_embed_frames:
        return {"ok": False, "error": f"speaker {speaker} was never above {threshold}"}
    vec = embeds[active_embed_frames].mean(axis=0)
    return {"ok": True, "vector": vec, "frames_used": len(active_embed_frames),
            "span_seconds": round(len(np.where(activity[:, idx] > threshold)[0]) * 0.01, 2)}


def cosine(a, b) -> float:
    import numpy as np
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def register_anchor(name: str, vector, *, note: str = "") -> Dict[str, Any]:
    import numpy as np
    REGISTER.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if REGISTER.exists():
        try:
            data = json.loads(REGISTER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[name] = {"vector": [round(float(v), 6) for v in np.asarray(vector)],
                  "dim": int(np.asarray(vector).shape[0]), "note": note,
                  "registered_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    REGISTER.write_text(json.dumps(data, indent=2), encoding="utf-8")
    row = {"ts": time.time(), "kind": "ANCHOR_REGISTERED", "name": name,
           "dim": data[name]["dim"], "note": note, "truth_label": TRUTH_LABEL}
    with RECEIPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "name": name, "anchors": sorted(data.keys())}


def anchors() -> Dict[str, Any]:
    if not REGISTER.exists():
        return {}
    try:
        return json.loads(REGISTER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def identify(wav: str, *, threshold: float = SCAN_ACTIVITY) -> Dict[str, Any]:
    """Name each active speaker by nearest anchor. Unknown stays unknown."""
    import numpy as np
    e = embed(wav)
    if not e.get("ok"):
        return e
    activity = e["activity"]
    reg = anchors()
    out: List[Dict[str, Any]] = []
    for spk in range(1, activity.shape[1] + 1):
        active = np.where(activity[:, spk - 1] > threshold)[0]
        if active.size == 0:
            continue
        a = anchor_from_span(wav, spk, threshold=threshold)
        if not a.get("ok"):
            continue
        best, best_score = None, -2.0
        for name, entry in reg.items():
            score = cosine(a["vector"], entry["vector"])
            if score > best_score:
                best, best_score = name, score
        out.append({"speaker": spk, "frames": int(active.size),
                    "start_s": round(float(active[0]) * 0.01, 2),
                    "end_s": round(float(active[-1]) * 0.01, 2),
                    "name": best if best and best_score >= MATCH_MIN_COSINE else "unknown",
                    "cosine": round(best_score, 3) if best else None})
    return {"ok": True, "speakers": len(out), "identified": out,
            "register": sorted(reg.keys()), "truth_label": TRUTH_LABEL}


def selftest() -> Dict[str, Any]:
    import numpy as np
    import tempfile
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])
    v1b = np.array([0.9, 0.1, 0.0])
    with tempfile.TemporaryDirectory() as tmp:
        global REGISTER, RECEIPTS
        keep_r, keep_rec = REGISTER, RECEIPTS
        REGISTER, RECEIPTS = Path(tmp) / "anchors.json", Path(tmp) / "receipts.jsonl"
        register_anchor("alice", v1, note="probe")
        register_anchor("george", v2, note="probe")
        got = anchors()
        REGISTER, RECEIPTS = keep_r, keep_rec

    checks = {
        "cosine_of_a_voice_with_itself_is_one": abs(cosine(v1, v1) - 1.0) < 1e-9,
        "cosine_of_different_voices_is_low": abs(cosine(v1, v2)) < 1e-9,
        "a_near_voice_scores_high": cosine(v1, v1b) > 0.99,
        "a_zero_vector_scores_zero_not_nan": cosine(v1, np.zeros(3)) == 0.0,
        "the_register_keeps_both_anchors": sorted(got.keys()) == ["alice", "george"],
        "the_register_keeps_the_dimension": got["alice"]["dim"] == 3,
        "anchors_are_plain_numbers": isinstance(got["alice"]["vector"][0], float),
        "an_unknown_voice_will_not_be_named": MATCH_MIN_COSINE > cosine(v1, v2),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "status":
        print(json.dumps({"anchors": sorted(anchors().keys())}, indent=2))
    elif cmd == "identify" and len(sys.argv) > 2:
        print(json.dumps(identify(sys.argv[2]), indent=2))

def audio_holders() -> Dict[str, Any]:
    """Who else is holding the audio device -- the thing that predicts my own truncation.

    Measured tonight: every capture came back short (7.31s of 25, 2.72s of 9, 4.11s of 14)
    while the SIFTA desktop held coreaudio. This is not a hunch to be argued about later; it
    is a reading I can take BEFORE recording, which makes the outcome predictable instead of
    surprising. Predicting my own ear is the point: awareness that only reports after the
    fact is a log, not a forward model.
    """
    import subprocess
    holders = []
    try:
        out = subprocess.run(["lsof"], capture_output=True, text=True, timeout=40).stdout
    except Exception:
        return {"holders": [], "contended": None, "note": "could not read the device table"}
    for line in out.splitlines():
        low = line.lower()
        if any(k in low for k in ("coreaudio", "applehda", "avfoundation")):
            parts = line.split()
            if len(parts) > 1 and parts[0] not in ("COMMAND",):
                entry = f"{parts[0]}:{parts[1]}"
                if entry not in holders:
                    holders.append(entry)
    contended = len(holders) > 1
    return {"holders": holders[:8], "contended": contended,
            "note": ("another process is holding the audio device, so I expect my own capture "
                     "to be cut short" if contended else
                     "I appear to be the only holder, so I expect a clean capture")}


def predict_capture(seconds: float, *, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """State the expectation before listening. Feeds the body's existing forward model."""
    try:
        from System.swarm_action_prediction import predict
        h = audio_holders()
        expected = (f"listening for {seconds:.0f}s will return roughly "
                    f"{'2-5 seconds, cut short by device contention' if h['contended'] else str(int(seconds)) + ' seconds, clean'}"
                    f" (holders: {', '.join(h['holders']) or 'none seen'})")
        row = predict("voice_capture", expected,
                      context=f"contended={h['contended']}; holders={len(h['holders'])}",
                      state_dir=state_dir)
        return {"ok": True, "expected": expected, "holders": h, "prediction": row}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "holders": audio_holders()}


def observe_capture(captured_seconds: Optional[float], requested: float, *,
                    speech_found: bool = False, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Report what actually happened, so the gap becomes a lesson rather than a mystery."""
    try:
        from System.swarm_action_prediction import observe
        actual = (f"requested {requested:.0f}s, captured {captured_seconds or 0:.2f}s, "
                  f"speech {'found' if speech_found else 'not found'}")
        return {"ok": True, "actual": actual, "graded": observe("voice_capture", actual,
                                                                state_dir=state_dir)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
